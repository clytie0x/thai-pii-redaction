"""Explicit enterprise configuration with private file-backed credentials."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import psycopg
from psycopg.conninfo import conninfo_to_dict

from pii_redactor.governance.errors import GovernanceError


def _url(value: str):
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        raise ValueError
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or any(ord(c) < 33 or ord(c) == 127 for c in value)
    ):
        raise ValueError
    _ = parsed.port
    return parsed


def _secret_file(path: str, key: str) -> str:
    file = Path(path)
    if file.stat().st_size > 65536:
        raise ValueError
    data = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {key} or not isinstance(data[key], str):
        raise ValueError
    return data[key]


@dataclass(frozen=True)
class Settings:
    organization_id: UUID
    database_dsn: str = field(repr=False)
    issuer: str
    client_id: str
    client_secret: str = field(repr=False)
    public_origin: str
    development: bool = False

    def __post_init__(self):
        try:
            issuer, origin = _url(self.issuer), _url(self.public_origin)
            if (
                not isinstance(self.organization_id, UUID)
                or type(self.development) is not bool
                or origin.path
                or not isinstance(self.client_id, str)
                or not 1 <= len(self.client_id) <= 255
                or any(ord(c) < 32 or ord(c) == 127 for c in self.client_id)
                or not isinstance(self.client_secret, str)
                or not 1 <= len(self.client_secret) <= 4096
                or not isinstance(self.database_dsn, str)
                or not 1 <= len(self.database_dsn) <= 8192
            ):
                raise ValueError
            if not conninfo_to_dict(self.database_dsn).get("dbname"):
                raise ValueError
            if self.development:
                if any(
                    p.hostname not in {"127.0.0.1", "localhost", "::1"} for p in (issuer, origin)
                ):
                    raise ValueError
            elif issuer.scheme != "https" or origin.scheme != "https":
                raise ValueError
            return
        except (ValueError, TypeError, AttributeError, psycopg.Error):
            pass
        raise GovernanceError("configuration_invalid") from None

    @property
    def redirect_uri(self) -> str:
        return self.public_origin + "/auth/callback"

    @property
    def cookie_prefix(self) -> str:
        return "aiguard_dev_" if self.development else "__Host-aiguard_"

    @classmethod
    def from_env(cls, environment=None):
        env = os.environ if environment is None else environment
        try:
            mode = env.get("AIGUARD_ENTERPRISE_MODE", "production")
            if mode not in {"production", "development"}:
                raise ValueError
            return cls(
                organization_id=UUID(env["AIGUARD_ENTERPRISE_ORGANIZATION_ID"]),
                database_dsn=_secret_file(env["AIGUARD_ENTERPRISE_DB_FILE"], "dsn"),
                issuer=env["AIGUARD_ENTERPRISE_ISSUER"],
                client_id=env["AIGUARD_ENTERPRISE_CLIENT_ID"],
                client_secret=_secret_file(
                    env["AIGUARD_ENTERPRISE_OIDC_SECRET_FILE"], "client_secret"
                ),
                public_origin=env["AIGUARD_ENTERPRISE_PUBLIC_ORIGIN"],
                development=mode == "development",
            )
        except (KeyError, ValueError, TypeError, OSError):
            pass
        raise GovernanceError("configuration_invalid") from None
