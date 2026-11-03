"""Versioned policies, primary-source evidence and release findings, not verdicts."""

from datetime import date, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from pii_redactor.governance.commands import identifier
from pii_redactor.governance.control_register import Binding, ControlInput, Register
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.models import ClosedModel, Department
from pii_redactor.governance.permissions import require_member
from pii_redactor.governance.registry import RecordID, Reference, _validated

CONTROL_KEYS = (
    "scope_roles",
    "consent_notice",
    "processing_conditions",
    "international_transfers",
    "rights",
    "security_retention_incidents",
    "responsibility_records_processors",
    "dpo",
)


class Instrument(ClosedModel):
    url: str = Field(max_length=2048)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0, le=20000000)
    fetched_at: datetime = Field(strict=False)
    version: Reference
    effective_on: date = Field(strict=False)
    amendment_review: Literal["pending", "reviewer_attested"]
    qualified_review_ref: RecordID | None = None

    @field_validator("url")
    @classmethod
    def official(cls, value):
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not (
                parsed.hostname.endswith(".go.th")
                or parsed.hostname in {"pdpc.or.th", "www.pdpc.or.th"}
            )
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("official HTTPS source required")
        return value

    @field_validator("fetched_at")
    @classmethod
    def zoned(cls, value):
        from datetime import UTC

        if value.tzinfo is None or value > datetime.now(UTC):
            raise ValueError("actual fetch time required")
        return value


class PolicyInput(ControlInput):
    policy_kind: Literal["security", "privacy", "training", "incident", "records", "source"]
    version_ref: RecordID
    instrument: Instrument | None = None

    @model_validator(mode="after")
    def source_required(self):
        if (self.policy_kind == "source") != (self.instrument is not None):
            raise ValueError("source metadata required only for source policy")
        return self


class Policies(Register):
    kind = "policy"
    input_model = PolicyInput

    def validate_activation(self, tx, row):
        source = row["data"]["instrument"]
        if source and (
            source["amendment_review"] != "reviewer_attested" or not source["qualified_review_ref"]
        ):
            raise GovernanceError("source_unverified")
        if source and date.fromisoformat(source["effective_on"]) > date.today():
            raise GovernanceError("source_not_effective")


class LegalInput(ControlInput):
    control_key: Literal[
        "scope_roles",
        "consent_notice",
        "processing_conditions",
        "international_transfers",
        "rights",
        "security_retention_incidents",
        "responsibility_records_processors",
        "dpo",
    ]
    applicability: Literal["unknown", "required", "reviewed_not_applicable"]
    rationale_ref: RecordID
    source: Binding
    implementation_ref: RecordID | None = None
    operational_ref: RecordID | None = None


class ReleaseScope(ClosedModel):
    department_id: Department

    @field_validator("department_id")
    @classmethod
    def concrete(cls, value):
        if value == "*":
            raise ValueError("concrete department required")
        return value


class LegalControls(Register):
    kind = "legal"
    input_model = LegalInput

    def _pending_obligations(self, tx, row, seen=None):
        seen = set() if seen is None else seen
        if row["control_id"] in seen:
            return False
        seen.add(row["control_id"])
        if len(seen) > 256:
            raise GovernanceError("control_stale")
        if row["kind"] == "incident":
            from pii_redactor.governance.incidents import Incidents

            incident = Incidents(self.store, case_checker=self.case_checker)._view(tx, row)
            if (
                not incident["usable"]
                or row["data"]["risk"] == "unknown"
                or not row["data"]["awareness_at"]
                or incident["outstanding_tasks"]
            ):
                return True
        if row["kind"] == "assessment" and row["data"]["outcome"] == "pending":
            return True
        for dep in row["data"]["dependencies"]:
            target = tx.execute(
                "SELECT * FROM governance_organization_controls WHERE control_id=%s AND organization_id=%s",
                (dep["id"], self.store.organization_id),
            ).fetchone()
            if not target or self._pending_obligations(tx, target, seen):
                return True
        return False

    def validate_activation(self, tx, row):
        data = row["data"]
        if data["applicability"] == "unknown":
            raise GovernanceError("applicability_unresolved")
        if data["applicability"] == "required" and (
            not data["implementation_ref"] or not data["operational_ref"]
        ):
            raise GovernanceError("evidence_required")
        binding = data["source"]
        source = tx.execute(
            "SELECT * FROM governance_organization_controls WHERE control_id=%s AND organization_id=%s FOR SHARE",
            (identifier(binding["id"]), self.store.organization_id),
        ).fetchone()
        if (
            not source
            or source["kind"] != "policy"
            or source["data"]["policy_kind"] != "source"
            or source["revision"] != binding["revision"]
            or source["department_id"] != row["department_id"]
            or binding not in data["dependencies"]
        ):
            raise GovernanceError("source_unverified")
        self._current(tx, source)
        if self._pending_obligations(tx, row):
            raise GovernanceError("operational_obligations_unresolved")
        existing = tx.execute(
            "SELECT control_id FROM governance_organization_controls WHERE organization_id=%s AND department_id=%s AND kind='legal' AND state='active' AND data->>'control_key'=%s AND control_id<>%s",
            (
                self.store.organization_id,
                row["department_id"],
                data["control_key"],
                row["control_id"],
            ),
        ).fetchone()
        if existing and (
            not data["supersedes"] or str(existing["control_id"]) != data["supersedes"]["id"]
        ):
            raise GovernanceError("supersession_required")

    def release_findings(self, principal, release_scope):
        scope = _validated(ReleaseScope, release_scope)
        with self.store.transaction() as tx:
            self.store.lock(tx)
            require_member(
                tx, self.store.organization_id, principal, "retention.read", scope.department_id
            )
            rows = tx.execute(
                "SELECT * FROM governance_organization_controls WHERE organization_id=%s AND department_id=%s AND kind='legal' AND state='active'",
                (self.store.organization_id, scope.department_id),
            ).fetchall()
            items = []
            for key in CONTROL_KEYS:
                candidates = [r for r in rows if r["data"]["control_key"] == key]
                item = {
                    "control_key": key,
                    "decision": "unresolved",
                    "source": None,
                    "reviewer": None,
                    "evidence": None,
                    "reason": "review_required",
                }
                if len(candidates) == 1:
                    row = candidates[0]
                    item.update(
                        id=str(row["control_id"]),
                        revision=row["revision"],
                        reviewer=str(row["reviewed_by"]),
                        evidence=row["review_evidence_ref"] and str(row["review_evidence_ref"]),
                        reviewer_revision=row["reviewer_revision"],
                        reviewed_at=row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
                        source_binding=row["data"]["source"],
                    )
                    source = tx.execute(
                        "SELECT h.snapshot FROM governance_control_history h JOIN governance_organization_controls c USING(control_id) WHERE c.control_id=%s AND c.organization_id=%s AND h.revision=%s",
                        (
                            row["data"]["source"]["id"],
                            self.store.organization_id,
                            row["data"]["source"]["revision"],
                        ),
                    ).fetchone()
                    item["source"] = (
                        source["snapshot"]["data"].get("instrument") if source else None
                    )
                    try:
                        self._current(tx, row)
                        self.validate_activation(tx, row)
                        if self._pending_obligations(tx, row):
                            raise GovernanceError("notification_tasks_unresolved")
                        item.update(
                            decision=row["data"]["applicability"],
                            reason=None,
                            implementation_ref=row["data"]["implementation_ref"],
                            operational_ref=row["data"]["operational_ref"],
                            rationale_ref=row["data"]["rationale_ref"],
                        )
                    except GovernanceError as exc:
                        item["reason"] = str(exc)
                items.append(item)
            incidents = tx.execute(
                "SELECT * FROM governance_organization_controls WHERE organization_id=%s AND department_id=%s AND kind='incident' AND state NOT IN ('superseded','rejected')",
                (self.store.organization_id, scope.department_id),
            ).fetchall()
            for incident in incidents:
                if incident["state"] != "active" or self._pending_obligations(tx, incident):
                    items.append(
                        {
                            "control_key": "incident_tasks",
                            "id": str(incident["control_id"]),
                            "revision": incident["revision"],
                            "decision": "unresolved",
                            "reason": "incident_review_required",
                            "reviewer": str(incident["reviewed_by"])
                            if incident["reviewed_by"]
                            else None,
                            "evidence": str(incident["review_evidence_ref"])
                            if incident["review_evidence_ref"]
                            else None,
                            "source": None,
                        }
                    )
            return {
                "items": items,
                "blocked": any(r["decision"] == "unresolved" for r in items),
                "legal_clearance": False,
                "scope": scope.model_dump(),
                "notification_closed": False,
            }
