"""Accountable responsibilities and reviewed DPO/conflicting-duty decisions."""

from typing import Literal

from pii_redactor.governance.control_register import ControlInput, Register
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.registry import RecordID


class ResponsibilityInput(ControlInput):
    responsibility: Literal[
        "dpo",
        "representative",
        "controller",
        "processor",
        "incident_lead",
        "training_owner",
        "complaints_owner",
    ]
    applicability: Literal["unknown", "required", "reviewed_not_applicable"]
    rationale_ref: RecordID
    designation_ref: RecordID
    independence_ref: RecordID
    conflict_review_ref: RecordID
    escalation_ref: RecordID
    backup_ref: RecordID


class Responsibilities(Register):
    kind = "responsibility"
    input_model = ResponsibilityInput

    def validate_activation(self, tx, row):
        if row["data"]["applicability"] == "unknown":
            raise GovernanceError("applicability_unresolved")
