"""Closed browser commands; staff identity never comes from request JSON."""

from typing import Annotated

from pydantic import Field

from pii_redactor.governance.models import ClosedModel, Department, Role
from pii_redactor.governance.registry import ActivityInput, NoticeInput, RecordID, ReviewInput

Revision = Annotated[int, Field(ge=1)]


class Command(ClosedModel):
    command_key: RecordID


class ActivityCreate(Command):
    data: ActivityInput


class ActivityUpdate(ActivityCreate):
    expected_revision: Revision


class Transition(Command):
    expected_revision: Revision


class ActivityReview(Transition):
    data: ReviewInput


class NoticeCreate(Command):
    data: NoticeInput
    expected_activity_revision: Revision


class EnrollmentTarget(ClosedModel):
    subject: str = Field(min_length=1, max_length=255)
    roles: list[Role] = Field(min_length=1, max_length=8)
    departments: list[Department] = Field(min_length=1, max_length=32)


class EnrollmentProposal(Command):
    data: EnrollmentTarget


class GrantProposal(Command):
    roles: list[Role] = Field(min_length=1, max_length=8)
    departments: list[Department] = Field(min_length=1, max_length=32)
    enabled: bool | None = None
