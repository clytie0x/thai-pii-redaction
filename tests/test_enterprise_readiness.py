"""Readiness failures must not turn process liveness into permission to serve."""

import pytest

from tests import governance_helpers as fixtures
from tests.test_audit_checkpoint import witness as independent_witness

context = fixtures.context
database = fixtures.database
witness = independent_witness


def test_profile_is_explicit_and_protection_fields_are_mandatory():
    from pii_redactor.governance.operations import ProductionProfile

    with pytest.raises(Exception, match="production_profile_invalid"):
        ProductionProfile.parse({})


def test_new_database_is_quarantined_and_missing_rights_handler_blocks(context):
    from pii_redactor.governance.operations import Operations

    ops = Operations(context.store)
    with pytest.raises(Exception, match="restore_quarantined"):
        ops.require_reconciled()
    with pytest.raises(Exception, match="recovery_handler_missing"):
        ops.reconcile(context.store, handlers={})
    with context.store.transaction() as tx:
        assert (
            tx.execute("SELECT state FROM governance_operations").fetchone()["state"]
            == "quarantined"
        )


def test_live_works_with_database_down_but_production_ready_and_mutations_fail():
    from uuid import uuid4

    from fastapi.testclient import TestClient

    from app.enterprise.server import create_app
    from app.enterprise.settings import Settings

    settings = Settings(
        uuid4(),
        "host=127.0.0.1 port=1 dbname=synthetic",
        "https://idp.example.test",
        "synthetic",
        "synthetic",
        "https://staff.example.test",
    )
    import httpx

    app = create_app(
        settings,
        subject_settings=None,
        managed_key_provider=None,
        oidc_transport=httpx.MockTransport(lambda _: httpx.Response(503)),
    )
    with TestClient(app, base_url=settings.public_origin) as http:
        assert http.get("/health/live").status_code == 200
        assert http.get("/health/ready").status_code == 503
        assert http.get("/health/ready", headers={"Host": "other.example.test"}).status_code == 400
        assert http.post("/api/activities", json={}).status_code == 503


def test_readiness_profile_cannot_make_overprivileged_runtime_ready(context):
    from pii_redactor.governance.operations import check_runtime_role

    with pytest.raises(Exception, match="runtime_role_overprivileged"):
        check_runtime_role(context.store)


def test_missing_recovery_source_cannot_be_filled_with_success_callbacks(context):
    from pii_redactor.governance.operations import Operations, control_handlers

    handlers = dict.fromkeys(control_handlers(), lambda *_: "a" * 64)
    with pytest.raises(Exception, match="recovery_handler_missing"):
        Operations(context.store).reconcile(None, handlers=handlers)
    with pytest.raises(Exception, match="recovery_source_unavailable"):
        Operations(context.store).reconcile(None, handlers=control_handlers())


def test_recovery_cannot_substitute_or_drop_authority_and_registry_scopes(context):
    from pii_redactor.governance.operations import Operations, control_handlers

    actual = control_handlers()
    substituted = {**actual, "authority": actual["managed"]}
    missing_registry = {key: value for key, value in actual.items() if key != "registry"}
    for handlers in (substituted, missing_registry):
        with pytest.raises(Exception, match="recovery_handler_missing"):
            Operations(context.store).reconcile(None, handlers=handlers)


def test_identity_outage_is_reported_after_local_prerequisites(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from app.enterprise.server import _production_readiness

    monkeypatch.setattr(
        "app.enterprise.operations.runtime_request_report",
        lambda *_: {"status": "ready", "checks": {"synthetic_local_prerequisites": "ready"}},
    )

    class Unavailable:
        async def check_ready(self, **_kwargs):
            raise RuntimeError("synthetic_identity_outage")

    report = asyncio.run(
        _production_readiness(
            None, None, None, Unavailable(), SimpleNamespace(subject_oidc=Unavailable())
        )
    )
    assert report["status"] == "blocked" and report["checks"]["idp"] == "blocked"


def test_declared_synthetic_readiness_with_actual_least_privilege_db_and_signed_sink(
    context, witness, monkeypatch
):
    import secrets
    from uuid import uuid4

    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    from pii_redactor.governance.evidence import SyntheticKeyProvider
    from pii_redactor.governance.key_operations import verify_keys
    from pii_redactor.governance.operations import (
        ProductionProfile,
        digest,
        readiness,
        schema_identity,
    )
    from pii_redactor.governance.runtime_roles import grant_statements
    from pii_redactor.governance.store import Store
    from tests.test_audit_checkpoint import client

    # This test qualifies DB/sink composition; artifact bytes have a separate gate.
    monkeypatch.setattr("pii_redactor.governance.operations.artifact_identity", lambda: "a" * 64)
    role = "m10_runtime_" + uuid4().hex
    password = secrets.token_urlsafe(32)
    with context.store.transaction() as tx:
        schema = tx.execute("SELECT current_schema() AS name").fetchone()["name"]
        tx.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        for statement in grant_statements(schema, role):
            tx.execute(statement)
        # Proves readiness composition only; bypasses no production recovery acceptance.
        tx.execute("UPDATE governance_operations SET state='reconciled',active_key_version='v1'")
    try:
        runtime = Store(
            make_conninfo(context.store._dsn, user=role, password=password),
            context.store.organization_id,
        )
        runtime.production_operations_required, runtime.runtime_key_version = True, "v1"
        provider = SyntheticKeyProvider({(runtime.organization_id, None, "v1"): b"s" * 32})
        provider.active_version = "v1"
        checkpoint = client(witness, runtime.organization_id)
        checkpoint.check(context.store, publish=True)
        profile = ProductionProfile.parse(
            {
                "profile": "single_organization_production_v1",
                "artifact": "a" * 64,
                "schema": digest(schema_identity()),
                "public_origin": "https://synthetic.example.test",
                "checkpoint_max_age": 300,
                "checkpoint_max_events": 100,
                "evidence": dict.fromkeys(
                    (
                        "tls_proxy",
                        "database_runtime_role",
                        "storage_acl",
                        "secret_custody",
                        "key_custody",
                        "sink_custody",
                        "backup_custody",
                        "rpo_rto_drill",
                        "capacity",
                        "idp",
                        "release_scope",
                        "image_inventory",
                        "rollback",
                    ),
                    "synthetic-evidence-only",
                ),
            }
        )
        report = readiness(runtime, profile, checkpoint, lambda: verify_keys(runtime, provider))
        assert report["status"] == "ready"
        assert report["checks"]["runtime_role"] == "ready"
    finally:
        with context.store.transaction() as tx:
            tx.execute(
                sql.SQL("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {} FROM {}").format(
                    sql.Identifier(schema), sql.Identifier(role)
                )
            )
            tx.execute(
                sql.SQL("REVOKE ALL ON ALL SEQUENCES IN SCHEMA {} FROM {}").format(
                    sql.Identifier(schema), sql.Identifier(role)
                )
            )
            tx.execute(
                sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM {}").format(
                    sql.Identifier(schema), sql.Identifier(role)
                )
            )
            tx.execute(
                sql.SQL("REVOKE ALL ON SCHEMA {} FROM {}").format(
                    sql.Identifier(schema), sql.Identifier(role)
                )
            )
            tx.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
