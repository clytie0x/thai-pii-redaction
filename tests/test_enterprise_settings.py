"""Configured staff authority is server-owned and secret-file based."""

import json
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from app.enterprise.settings import Settings
from pii_redactor.governance.errors import GovernanceError


def values(**changes):
    return dict(
        organization_id=uuid4(),
        database_dsn="dbname=synthetic user=synthetic",
        issuer="https://staff.example.test/realms/staff",
        client_id="aiguard-staff",
        client_secret="synthetic-client-secret",
        public_origin="https://guard.example.test",
        **changes,
    )


def test_no_unconfigured_application_defaults():
    with pytest.raises(GovernanceError, match="^configuration_invalid$"):
        Settings.from_env({})


def test_configuration_does_not_represent_secrets():
    settings = Settings(**values())
    assert settings.redirect_uri == "https://guard.example.test/auth/callback"
    assert settings.client_secret not in repr(settings)
    assert settings.database_dsn not in repr(settings)


@pytest.mark.parametrize(
    "changes",
    [
        {"public_origin": "http://guard.example.test"},
        {"issuer": "http://staff.example.test/realms/staff"},
        {"public_origin": "https://guard.example.test/path"},
        {"public_origin": "https://user:secret@guard.example.test"},
        {"issuer": "https://staff.example.test/realms/staff?target=elsewhere"},
        {"issuer": "https://staff.example.test/#fragment"},
        {"client_id": ""},
        {"client_secret": ""},
        {"database_dsn": "not a connection string"},
    ],
    ids=[
        "public-http",
        "issuer-http",
        "origin-path",
        "userinfo",
        "query",
        "fragment",
        "empty-client",
        "empty-secret",
        "bad-database",
    ],
)
def test_invalid_configuration_is_value_free(changes):
    data = values()
    data.update(changes)
    with pytest.raises(GovernanceError) as caught:
        Settings(**data)
    assert str(caught.value) == "configuration_invalid"
    assert caught.value.__context__ is None


def test_http_development_requires_only_loopback_endpoints():
    data = values()
    data.update(
        development=True,
        issuer="http://127.0.0.1:8080/realms/staff",
        public_origin="http://localhost:8765",
    )
    assert Settings(**data).development is True
    data["public_origin"] = "https://guard.example.test"
    with pytest.raises(GovernanceError, match="^configuration_invalid$"):
        Settings(**data)


def test_env_loader_reads_only_private_file_references(tmp_path):
    db = tmp_path / "database.key"
    secret = tmp_path / "oidc.key"
    db.write_text(json.dumps({"dsn": "dbname=synthetic user=synthetic"}))
    secret.write_text(json.dumps({"client_secret": "synthetic-client-secret"}))
    env = {
        "AIGUARD_ENTERPRISE_ORGANIZATION_ID": str(uuid4()),
        "AIGUARD_ENTERPRISE_DB_FILE": str(db),
        "AIGUARD_ENTERPRISE_OIDC_SECRET_FILE": str(secret),
        "AIGUARD_ENTERPRISE_ISSUER": "https://staff.example.test/realms/staff",
        "AIGUARD_ENTERPRISE_CLIENT_ID": "aiguard-staff",
        "AIGUARD_ENTERPRISE_PUBLIC_ORIGIN": "https://guard.example.test",
    }
    settings = Settings.from_env(env)
    assert settings.client_id == "aiguard-staff" and not settings.development
    assert "synthetic-client-secret" not in repr(settings)


def test_secret_file_parse_failure_does_not_expose_contents(tmp_path):
    secret = tmp_path / "private.key"
    secret.write_text("sensitive malformed content")
    with pytest.raises(GovernanceError, match="^configuration_invalid$") as caught:
        Settings.from_env({"AIGUARD_ENTERPRISE_DB_FILE": str(secret)})
    assert caught.value.__context__ is None
