"""Explicit enterprise capabilities share one authenticated application."""

import json
from uuid import UUID

import pytest

pytest.importorskip("authlib", reason="optional enterprise identity dependency")
pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from app.enterprise.server import create_app
from app.enterprise.settings import Settings
from app.enterprise.subject_auth import SubjectOIDCSettings
from pii_redactor.governance.evidence import SyntheticKeyProvider


class ConfigurationStore:
    organization_id = UUID("b5186bb1-3431-4330-9b39-f365db8d4813")

    def check_ready(self):
        return 5


def settings():
    return Settings(
        organization_id=ConfigurationStore.organization_id,
        database_dsn="dbname=synthetic_configuration",
        issuer="https://idp.example.test/realms/organization",
        client_id="staff-client",
        client_secret="synthetic-staff-secret",
        public_origin="https://guard.example.test",
    )


def test_explicit_subject_and_protected_collection_routes_are_reachable():
    staff = settings()
    subject = SubjectOIDCSettings(
        issuer=staff.issuer,
        client_id="subject-client",
        client_secret="synthetic-subject-secret",
        public_origin=staff.public_origin,
        staff_client_id=staff.client_id,
    )
    keys = SyntheticKeyProvider({(staff.organization_id, None, "v1"): b"s" * 32})
    app = create_app(
        staff,
        store=ConfigurationStore(),
        subject_settings=subject,
        managed_key_provider=keys,
    )
    from fastapi.testclient import TestClient

    client = TestClient(app, base_url=staff.public_origin, follow_redirects=False)
    assert client.get("/subject").status_code in {200, 303}
    assert client.get("/subject/staff").status_code in {200, 401}
    assert client.get("/managed").status_code == 401
    assert 'href="/managed"' in client.get("/").text
    assert 'href="/subject/staff"' in client.get("/").text
    assert client.get("/retention").status_code == 200
    assert (
        client.get(
            f"/api/enterprise/v1/retention/collections/{staff.organization_id}/policies"
        ).status_code
        == 401
    )
    assert client.get("/api/enterprise/v1/managed/collections").status_code == 401
    assert app.state.subjects_enabled and app.state.managed_enabled


def test_unconfigured_capabilities_are_explicitly_disabled():
    app = create_app(
        settings(),
        store=ConfigurationStore(),
        subject_settings=None,
        managed_key_provider=None,
    )
    from fastapi.testclient import TestClient

    assert TestClient(app, base_url=settings().public_origin).get("/managed").status_code == 404
    assert 'href="/managed"' not in TestClient(app, base_url=settings().public_origin).get("/").text
    assert not app.state.subjects_enabled and not app.state.managed_enabled


def test_configured_key_file_enables_managed_path_without_a_runtime_default(monkeypatch, tmp_path):
    path = tmp_path / "synthetic-managed.key"
    path.write_text(
        json.dumps(
            {
                "organization_id": str(ConfigurationStore.organization_id),
                "active_version": "v1",
                "keys": [{"version": "v1", "key_hex": "73" * 32}],
            }
        )
    )
    monkeypatch.setenv("AIGUARD_ENTERPRISE_MANAGED_KEYS_FILE", str(path))
    app = create_app(settings(), store=ConfigurationStore(), subject_settings=None)
    assert app.state.managed_enabled
    provider = app.state.managed_collection.protection.key_provider
    assert provider.key_for(ConfigurationStore.organization_id, None, "v1") == b"s" * 32


def test_invalid_configured_key_file_fails_closed_without_echo(monkeypatch, tmp_path):
    from pii_redactor.governance.errors import GovernanceError

    path = tmp_path / "invalid-managed.key"
    path.write_text('{"synthetic-private-key-canary":"invalid"}')
    monkeypatch.setenv("AIGUARD_ENTERPRISE_MANAGED_KEYS_FILE", str(path))
    with pytest.raises(GovernanceError) as caught:
        create_app(settings(), store=ConfigurationStore(), subject_settings=None)
    assert caught.value.code == "key_configuration_invalid"
    assert "synthetic-private-key-canary" not in str(caught.value)
