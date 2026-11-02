"""Incident review and conditional notification evidence. Never sends notices."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import Field, field_validator, model_validator

from pii_redactor.governance.control_register import ControlInput, Register
from pii_redactor.governance.models import ClosedModel
from pii_redactor.governance.registry import RecordID


class NotificationTask(ClosedModel):
    audience: Literal["authority", "subjects", "controller"]
    applicability: Literal["unknown", "required", "reviewed_not_applicable"]
    state: Literal["pending", "draft", "external_evidence_recorded"]
    rationale_ref: RecordID
    outcome_evidence_ref: RecordID | None = None

    @model_validator(mode="after")
    def actual_evidence(self):
        if self.state == "external_evidence_recorded" and not self.outcome_evidence_ref:
            raise ValueError("external outcome evidence required")
        return self


class IncidentInput(ControlInput):
    awareness_at: datetime | None = Field(default=None, strict=False)
    awareness_evidence_ref: RecordID
    uncertainty_ref: RecordID
    risk: Literal["unknown", "low", "risk", "high"]
    risk_review_ref: RecordID
    escalation_ref: RecordID
    triage_evidence_ref: RecordID | None = None
    tasks: list[NotificationTask] = Field(min_length=1, max_length=3)

    @field_validator("awareness_at")
    @classmethod
    def actual_awareness(cls, value):
        if value is not None and (value.tzinfo is None or value > datetime.now(UTC)):
            raise ValueError("actual zoned awareness required")
        return value

    @model_validator(mode="after")
    def distinct_tasks(self):
        if len({t.audience for t in self.tasks}) != len(self.tasks):
            raise ValueError("duplicate audience")
        return self


class Incidents(Register):
    kind = "incident"
    input_model = IncidentInput

    def _view(self, tx, row):
        result = super()._view(tx, row)
        data = row["data"]
        result["conditional_authority_target_at"] = (
            (datetime.fromisoformat(data["awareness_at"]) + timedelta(hours=72)).isoformat()
            if data["awareness_at"]
            else None
        )
        result["clock_status"] = "conditional_human_review_required"
        result["notification_closed"] = False
        result["outstanding_tasks"] = [
            t["audience"]
            for t in data["tasks"]
            if t["applicability"] == "unknown"
            or (t["applicability"] == "required" and t["state"] != "external_evidence_recorded")
        ]
        result["triage_tool"] = (
            "pii_redactor.breach.assess_breach (advice only; no automatic file access)"
        )
        return result
