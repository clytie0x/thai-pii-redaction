"""Processor agreements, instructions and actual access inventories."""

from pydantic import Field

from pii_redactor.governance.control_register import ControlInput, Register
from pii_redactor.governance.registry import RecordID


class ProcessorInput(ControlInput):
    agreement_ref: RecordID
    instruction_ref: RecordID
    purpose_ref: RecordID
    recipient_ref: RecordID
    subprocessors: list[RecordID] = Field(max_length=64)
    destination_ref: RecordID
    access_evidence_ref: RecordID


class Processors(Register):
    kind = "processor"
    input_model = ProcessorInput
