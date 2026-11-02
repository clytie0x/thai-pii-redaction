"""Reviewed destinations and safeguards; a cloud label is never evidence."""

from typing import Literal

from pii_redactor.governance.control_register import Binding, ControlInput, Register
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.registry import RecordID


class TransferInput(ControlInput):
    processor: Binding
    destination_ref: RecordID
    recipient_ref: RecordID
    access_evidence_ref: RecordID
    classification: Literal["unknown", "international", "reviewed_domestic"]
    route: Literal["unknown", "adequacy", "section29_safeguard", "reviewed_exception", "domestic"]
    safeguard_ref: RecordID
    source: Binding


class Transfers(Register):
    kind = "transfer"
    input_model = TransferInput

    def validate_activation(self, tx, row):
        data = row["data"]
        if (
            data["classification"] == "unknown"
            or data["route"] == "unknown"
            or ((data["classification"] == "reviewed_domestic") != (data["route"] == "domestic"))
        ):
            raise GovernanceError("applicability_unresolved")
        for key, kind in [("processor", "processor"), ("source", "policy")]:
            binding = data[key]
            target = tx.execute(
                "SELECT * FROM governance_organization_controls WHERE control_id=%s AND organization_id=%s FOR SHARE",
                (binding["id"], self.store.organization_id),
            ).fetchone()
            if (
                not target
                or target["kind"] != kind
                or target["department_id"] != row["department_id"]
                or target["revision"] != binding["revision"]
                or binding not in data["dependencies"]
            ):
                raise GovernanceError("control_stale")
            self._current(tx, target)
            if key == "processor" and (
                target["data"]["destination_ref"] != data["destination_ref"]
                or target["data"]["recipient_ref"] != data["recipient_ref"]
            ):
                raise GovernanceError("destination_changed")
            if key == "source" and target["data"]["policy_kind"] != "source":
                raise GovernanceError("source_unverified")
