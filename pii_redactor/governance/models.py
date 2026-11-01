"""Closed, bounded inputs. Principals carry identity, never claimed authority."""

from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Role = Literal[
    "system_administrator",
    "authority_reviewer",
    "data_steward",
    "privacy_reviewer",
    "case_manager",
    "identity_steward",
    "custodian",
    "auditor",
]
Department = Annotated[str, Field(pattern=r"^(?:\*|[a-z][a-z0-9_-]{0,63})$")]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Principal(ClosedModel):
    issuer: str = Field(min_length=1, max_length=2048)
    subject: str = Field(min_length=1, max_length=255)

    @field_validator("issuer")
    @classmethod
    def issuer_is_safe(cls, value):
        try:
            parsed = urlsplit(value)
            valid_scheme = parsed.scheme == "https" or (
                parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1", "localhost"}
            )
            if (
                not valid_scheme
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or any(ord(c) < 33 or ord(c) == 127 for c in value)
            ):
                raise ValueError("invalid identity issuer")
            _ = parsed.port
        except ValueError:
            raise ValueError("invalid identity issuer") from None
        return value

    @field_validator("subject")
    @classmethod
    def subject_has_no_controls(cls, value):
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("invalid identity subject")
        return value


class Enrollment(ClosedModel):
    principal: Principal
    roles: list[Role] = Field(min_length=1, max_length=8)
    departments: list[Department] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def explicit_unique_scope(self):
        if (
            len(set(self.roles)) != len(self.roles)
            or len(set(self.departments)) != len(self.departments)
            or ("*" in self.departments and len(self.departments) != 1)
        ):
            raise ValueError("invalid enrollment scope")
        return self


class StaffPrincipal(Principal):
    """Backend-only session identity, rechecked in each domain transaction."""

    session_id: UUID
    member_revision: int = Field(ge=1)
