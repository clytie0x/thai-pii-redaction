"""The approved worker uses DB/key authority and public IdP health, not login secrets."""

import json
import os
import runpy
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")
pytest.importorskip("authlib", reason="optional enterprise identity dependency")

import httpx

from app.enterprise import worker_runtime as runtime
from pii_redactor.governance.errors import GovernanceError
from tests import test_governance_integration as production
from tests.test_audit_checkpoint import client as checkpoint_client
from tests.test_audit_checkpoint import witness as independent_witness

database = production.database
context = production.context
subject_context = production.subject_context
consent_context = production.consent_context
integrated = production.integrated
witness = independent_witness


class UnitProof:
    """Unit wiring only; actual qualification uses the signed PostgreSQL fixtures."""

    prepared = False

    def prepare_current(self):
        self.prepared = True

    def validate_locked(self, _tx):
        assert self.prepared


def unit_store():
    return SimpleNamespace(organization_id=uuid4(), transaction=lambda: nullcontext(None))


def declared_qualification(*_args):
    return {"status": "ready", "checks": {}}, UnitProof()


@pytest.fixture
def live_worker(integrated, witness, tmp_path, monkeypatch):
    from dataclasses import asdict

    from app.enterprise.capabilities import ConfiguredKeyProvider
    from pii_redactor.governance import operations
    from pii_redactor.governance.operator_files import read_private
    from tests.test_enterprise_runtime_role import runtime as runtime_role
    from tests.test_governance_processing_controls import controls, enabled, production_mode

    c = integrated
    production.consent_fixtures.command(c, "grant")
    rows, _law = controls(c)
    enabled(c, rows)
    production_mode(c)
    c.bucket, c.document, c.instruction = production.queued_document(c)
    private = tmp_path / "private-worker"
    runpy.run_path(str(Path.cwd() / "scripts/run_operations_drill.py"))["private_directory"](
        private
    )
    provider = c.collection.protection.key_provider
    keyfile = private / "keys.json"
    keyfile.write_text(
        json.dumps(
            {
                "organization_id": str(c.store.organization_id),
                "active_version": provider.active_version,
                "keys": [{"version": v, "key_hex": key.hex()} for v, key in provider._keys.items()],
            }
        )
    )
    keys = ConfiguredKeyProvider(keyfile, c.store.organization_id)
    monkeypatch.setattr(operations, "artifact_identity", lambda: "a" * 64)
    with runtime_role(c) as (store, role):
        dbfile = private / "database.json"
        dbfile.write_text(json.dumps({"dsn": store._dsn, "purpose": "synthetic_enterprise_tests"}))
        paths = {
            "DB": dbfile,
            "MANAGED_KEYS": keyfile,
            "PROFILE": private / "profile.json",
            "CHECKPOINT": private / "checkpoint.json",
        }
        cp_holder = {}

        def profile(max_age=30, max_events=100):
            data = json.loads(
                Path("deployment/enterprise/production-profile.example.json").read_text()
            )
            data.update(
                artifact="a" * 64,
                schema=operations.digest(operations.schema_identity()),
                public_origin="https://guard.example.test",
                checkpoint_max_age=max_age,
                checkpoint_max_events=max_events,
            )
            data["evidence"] = dict.fromkeys(data["evidence"], "synthetic-worker-fixture")
            selected = operations.ProductionProfile.parse(data)
            paths["PROFILE"].write_text(
                json.dumps({"profile": "single_organization_production_v1", **asdict(selected)})
            )
            cp = checkpoint_client(
                witness, store.organization_id, max_age=max_age, max_events=max_events
            )
            cp.check(c.store, publish=True)
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

            paths["CHECKPOINT"].write_text(
                json.dumps(
                    {
                        "url": cp.url,
                        "token": cp._token,
                        "public_key_hex": cp.public_key.public_bytes(
                            Encoding.Raw, PublicFormat.Raw
                        ).hex(),
                    }
                )
            )
            cp_holder.update(profile=selected, client=cp)

        profile()
        for name, path in paths.items():
            monkeypatch.setenv("AIGUARD_ENTERPRISE_" + name + "_FILE", str(path))
        monkeypatch.setenv("AIGUARD_ENTERPRISE_OIDC_SECRET_FILE", "must-not-read-staff-login.key")
        monkeypatch.setenv(
            "AIGUARD_ENTERPRISE_SUBJECT_OIDC_SECRET_FILE", "must-not-read-subject-login.key"
        )
        monkeypatch.setenv("AIGUARD_ENTERPRISE_ISSUER", "https://idp.example.test/staff")

        def load(org):
            assert org == store.organization_id
            return operations.ProductionProfile.parse(read_private(paths["PROFILE"])), cp_holder[
                "client"
            ]

        monkeypatch.setattr(runtime, "load_profile_checkpoint", load)
        yield SimpleNamespace(
            c=c,
            store=store,
            keys=keys,
            profile=profile,
            checkpoint=cp_holder,
            paths=paths,
            role=role,
        )


def public_metadata(request):
    assert (
        request.method == "GET" and not request.content and "authorization" not in request.headers
    )
    issuer = str(request.url).removesuffix("/.well-known/openid-configuration")
    return httpx.Response(
        200,
        json={
            "issuer": issuer,
            "authorization_endpoint": issuer + "/authorize",
            "token_endpoint": issuer + "/token",
            "jwks_uri": issuer + "/certs",
        },
    )


@pytest.mark.parametrize("change", ["age", "lag"])
def test_real_worker_qualification_is_invalidated_after_public_identity_io(live_worker, change):
    w = live_worker
    w.profile(max_age=1 if change == "age" else 30, max_events=0 if change == "lag" else 100)

    def provider(request):
        if change == "age":
            time.sleep(2)
        else:
            with w.c.store.transaction() as tx:
                w.c.store.append_event(tx, event_code="operations.synthetic_worker_lag")
        return public_metadata(request)

    report = runtime.worker_readiness(
        w.store, w.keys, identity_transport=httpx.MockTransport(provider)
    )
    assert report["status"] == "blocked"
    assert production.queued_state(w.c, w.c.instruction["id"])["state"] == "pending"


def test_real_healthy_worker_executes_current_approved_action_without_mutating_original_store(
    live_worker,
):
    w = live_worker
    original = (w.store.production_operations_required, w.store.runtime_key_version)
    result = runtime.run_qualified_once(
        w.store,
        w.keys,
        "synthetic-proof-worker",
        identity_transport=httpx.MockTransport(public_metadata),
    )
    assert result["primary_verified"] is True
    assert production.primary(w.c, w.c.document["id"])["state"] == "suppressed"
    assert (w.store.production_operations_required, w.store.runtime_key_version) == original


@pytest.mark.parametrize("change", ["age", "lag"])
def test_expired_or_lagging_worker_does_not_claim_or_mutate(live_worker, change):
    w = live_worker
    w.profile(max_age=1 if change == "age" else 30, max_events=0 if change == "lag" else 100)

    def provider(request):
        if change == "age":
            time.sleep(2)
        else:
            with w.c.store.transaction() as tx:
                w.c.store.append_event(tx, event_code="operations.synthetic_worker_lag")
        return public_metadata(request)

    with pytest.raises(GovernanceError, match="production_prerequisites_unverified"):
        runtime.run_qualified_once(
            w.store,
            w.keys,
            "synthetic-expired-worker",
            identity_transport=httpx.MockTransport(provider),
        )
    assert production.queued_state(w.c, w.c.instruction["id"])["state"] == "pending"
    assert production.primary(w.c, w.c.document["id"])["state"] == "active"


def test_proof_expires_while_waiting_for_the_actual_claim_lock_without_claiming(
    live_worker, monkeypatch
):
    w = live_worker
    w.profile(max_age=1)
    qualified, proceed = Event(), Event()
    original = runtime.worker_readiness

    def pause_after_success(*args, **kwargs):
        report = original(*args, **kwargs)
        assert report["status"] == "ready"
        qualified.set()
        assert proceed.wait(10)
        return report

    monkeypatch.setattr(runtime, "worker_readiness", pause_after_success)
    with ThreadPoolExecutor(max_workers=1) as pool:
        job = pool.submit(
            runtime.run_qualified_once,
            w.store,
            w.keys,
            "synthetic-waiting-worker",
            identity_transport=httpx.MockTransport(public_metadata),
        )
        assert qualified.wait(15)
        try:
            with w.c.store.transaction() as tx:
                w.c.store.lock(tx)
                proceed.set()
                time.sleep(1.4)
            with pytest.raises(GovernanceError, match="production_prerequisites_unverified"):
                job.result(timeout=10)
        finally:
            proceed.set()
    state = production.queued_state(w.c, w.c.instruction["id"])
    assert state["state"] == "pending"
    with w.c.store.transaction() as tx:
        assert (
            tx.execute(
                "SELECT attempts FROM governance_execution_tasks WHERE instruction_id=%s",
                (w.c.instruction["id"],),
            ).fetchone()["attempts"]
            == 0
        )
    assert production.primary(w.c, w.c.document["id"])["state"] == "active"


def test_post_identity_validation_does_not_repeat_full_crypto_or_audit_scans(
    live_worker, monkeypatch
):
    from pii_redactor.governance import store as store_module
    from pii_redactor.governance.evidence import ProtectedStorage

    after = {"identity": False}
    original_open, original_audit = ProtectedStorage.open, store_module._audit_rows

    def guarded_open(*args, **kwargs):
        assert not after["identity"], "Full crypto scan repeated after public IdP I/O"
        return original_open(*args, **kwargs)

    def guarded_audit(*args, **kwargs):
        assert not after["identity"], "Full audit scan repeated after public IdP I/O"
        return original_audit(*args, **kwargs)

    monkeypatch.setattr(ProtectedStorage, "open", guarded_open)
    monkeypatch.setattr(store_module, "_audit_rows", guarded_audit)

    def provider(request):
        after["identity"] = True
        return public_metadata(request)

    assert (
        runtime.worker_readiness(
            live_worker.store, live_worker.keys, identity_transport=httpx.MockTransport(provider)
        )["status"]
        == "ready"
    )


def test_final_input_io_expiry_rolls_back_the_actual_claim(live_worker, monkeypatch):
    w = live_worker
    original_readiness = runtime.worker_readiness
    delayed = {"calls": 0}

    def qualify(*args, **kwargs):
        report = original_readiness(*args, **kwargs)
        assert report["status"] == "ready"
        proof = kwargs["qualification"]["proof"]
        original_inputs = proof._fresh_inputs

        def inputs():
            delayed["calls"] += 1
            if delayed["calls"] == 4:
                # The last precommit input read crosses the qualified deadline.
                def artifact():
                    proof.until = time.monotonic() - 1
                    return "a" * 64

                with monkeypatch.context() as patch:
                    patch.setattr(runtime.governance, "artifact_identity", artifact)
                    return original_inputs()
            return original_inputs()

        monkeypatch.setattr(proof, "_fresh_inputs", inputs)
        return report

    monkeypatch.setattr(runtime, "worker_readiness", qualify)
    with pytest.raises(GovernanceError, match="production_prerequisites_unverified"):
        runtime.run_qualified_once(
            w.store,
            w.keys,
            "synthetic-final-io-worker",
            identity_transport=httpx.MockTransport(public_metadata),
        )
    assert delayed["calls"] >= 4
    assert production.queued_state(w.c, w.c.instruction["id"])["state"] == "pending"
    with w.c.store.transaction() as tx:
        assert (
            tx.execute(
                "SELECT attempts FROM governance_execution_tasks WHERE instruction_id=%s",
                (w.c.instruction["id"],),
            ).fetchone()["attempts"]
            == 0
        )
    assert production.primary(w.c, w.c.document["id"])["state"] == "active"


def test_development_worker_requires_an_explicit_loopback_database():
    runtime.require_loopback(SimpleNamespace(_dsn="host=127.0.0.1 dbname=synthetic"))
    for dsn in (
        "host=remote.example.test dbname=synthetic",
        "dbname=synthetic",
        "host=127.0.0.1 hostaddr=192.0.2.1 dbname=synthetic",
    ):
        with pytest.raises(GovernanceError, match="configuration_invalid"):
            runtime.require_loopback(SimpleNamespace(_dsn=dsn))


def test_worker_checks_public_metadata_without_loading_oidc_secrets(monkeypatch):
    store, keys = unit_store(), SimpleNamespace(active_version="v1")
    monkeypatch.setattr(runtime, "_qualify_snapshot", declared_qualification)
    requested = []

    def provider(request):
        requested.append(request)
        issuer = str(request.url).removesuffix("/.well-known/openid-configuration")
        return httpx.Response(
            200,
            json={
                "issuer": issuer,
                "authorization_endpoint": issuer + "/authorize",
                "token_endpoint": issuer + "/token",
                "jwks_uri": issuer + "/certs",
            },
        )

    result = runtime.worker_readiness(
        store,
        keys,
        environment={
            "AIGUARD_ENTERPRISE_ISSUER": "https://idp.example.test/staff",
            "AIGUARD_ENTERPRISE_SUBJECT_ISSUER": "https://idp.example.test/subjects",
        },
        identity_transport=httpx.MockTransport(provider),
    )
    assert result["status"] == "ready"
    assert len(requested) == 2
    assert all(
        request.method == "GET" and not request.content and "authorization" not in request.headers
        for request in requested
    )


def test_worker_stops_on_missing_or_unreachable_public_identity(monkeypatch):
    store, keys = unit_store(), SimpleNamespace(active_version="v1")
    monkeypatch.setattr(runtime, "_qualify_snapshot", declared_qualification)
    with pytest.raises(GovernanceError, match="configuration_invalid"):
        runtime.worker_readiness(store, keys, environment={})
    result = runtime.worker_readiness(
        store,
        keys,
        environment={"AIGUARD_ENTERPRISE_ISSUER": "https://idp.example.test/staff"},
        identity_transport=httpx.MockTransport(lambda _request: httpx.Response(503)),
    )
    assert result["status"] == "blocked" and result["checks"]["idp"] == "blocked"


def test_development_cli_rejects_foreign_database_before_connecting(monkeypatch):
    from app.enterprise import __main__ as cli

    attempts = []

    def connect():
        attempts.append(True)
        raise GovernanceError("storage_failure")

    monkeypatch.setenv("AIGUARD_ENTERPRISE_MODE", "development")
    monkeypatch.setenv("AIGUARD_ENTERPRISE_MANAGED_KEYS_FILE", "synthetic.key")
    monkeypatch.setattr(
        cli,
        "_store",
        lambda: SimpleNamespace(
            _dsn="host=remote.example.test dbname=synthetic", check_ready=connect
        ),
    )
    assert cli.main(["work-once", "--worker-id", "synthetic-worker"]) == 1
    assert attempts == []


def test_worker_binds_current_key_and_runtime_fence_before_qualification(monkeypatch):
    store = unit_store()

    def qualified(actual, *_args):
        assert actual.runtime_key_version == "v2"
        assert actual.production_operations_required is True
        return {"status": "ready", "checks": {}}, UnitProof()

    monkeypatch.setattr(runtime, "_qualify_snapshot", qualified)
    issuer = "https://idp.example.test/staff"
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json={
                "issuer": issuer,
                "authorization_endpoint": issuer + "/authorize",
                "token_endpoint": issuer + "/token",
                "jwks_uri": issuer + "/certs",
            },
        )
    )
    assert (
        runtime.worker_readiness(
            store,
            SimpleNamespace(active_version="v2"),
            environment={"AIGUARD_ENTERPRISE_ISSUER": issuer},
            identity_transport=transport,
        )["status"]
        == "ready"
    )


@pytest.mark.parametrize("mode", ["production", "development"])
def test_cli_worker_keeps_login_credentials_out_of_its_authority(monkeypatch, mode):
    from app.enterprise import __main__ as cli
    from app.enterprise import capabilities
    from app.enterprise.settings import Settings
    from pii_redactor.governance import operator_files

    store = SimpleNamespace(
        organization_id=uuid4(),
        _dsn="host=127.0.0.1 dbname=synthetic",
        check_ready=lambda: None,
        production_operations_required=False,
        runtime_key_version="",
    )
    private = []
    monkeypatch.setenv("AIGUARD_ENTERPRISE_MODE", mode)
    monkeypatch.setenv("AIGUARD_ENTERPRISE_DB_FILE", "synthetic-database.key")
    monkeypatch.setenv("AIGUARD_ENTERPRISE_MANAGED_KEYS_FILE", "synthetic-managed.key")
    monkeypatch.setattr(cli, "_store", lambda: store)
    monkeypatch.setattr(operator_files, "require_private", lambda path: private.append(path))
    qualified_calls = []

    def run_qualified(actual, keys, worker_id):
        assert mode == "production" and actual is store
        assert actual.production_operations_required is False and actual.runtime_key_version == ""
        qualified_calls.append(worker_id)
        return {"state": "idle", "primary_verified": False}

    monkeypatch.setattr(runtime, "run_qualified_once", run_qualified)
    monkeypatch.setattr(Settings, "from_env", lambda: pytest.fail("worker loaded login secrets"))
    monkeypatch.setattr(
        capabilities, "ConfiguredKeyProvider", lambda *_args: SimpleNamespace(active_version="v1")
    )
    worker = SimpleNamespace(run_once=lambda _name: {"state": "idle", "primary_verified": False})

    def managed(*_args):
        assert mode == "development", "Production must not use an unqualified factory path"
        return None, None, None, worker

    monkeypatch.setattr(capabilities, "managed_services", managed)
    assert cli.main(["work-once", "--worker-id", "synthetic-worker"]) == 0
    assert store.production_operations_required is False
    assert qualified_calls == (["synthetic-worker"] if mode == "production" else [])
    assert private == (
        ["synthetic-database.key", "synthetic-managed.key"] if mode == "production" else []
    )
