"""Risk, complaint and review evidence without subject values."""

from typing import Literal

from pii_redactor.governance.control_register import ControlInput, Register
from pii_redactor.governance.registry import RecordID


class AssessmentInput(ControlInput):
    assessment_kind: Literal["risk", "complaint", "training", "periodic_review"]
    subject_ref: RecordID
    findings_ref: RecordID
    mitigation_ref: RecordID
    followup_ref: RecordID
    outcome: Literal["pending", "evidence_recorded"]


class Assessments(Register):
    kind = "assessment"
    input_model = AssessmentInput
