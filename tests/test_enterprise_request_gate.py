"""Request work stays bounded while one background task qualifies history."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip("fastapi", reason="optional enterprise HTTP dependency")
pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from fastapi.testclient import TestClient

from app.enterprise.server import create_app
from app.enterprise.settings import Settings
from pii_redactor.governance.errors import GovernanceError
from tests import governance_helpers as fixtures
from tests.test_audit_checkpoint import client
from tests.test_audit_checkpoint import witness as independent_witness

context = fixtures.context
database = fixtures.database
witness = independent_witness


@pytest.fixture
def qualified(context, witness, tmp_path, monkeypatch):
    from app.enterprise.operations import RuntimeGate
    from pii_redactor.governance import operations
    from tests.test_enterprise_key_fences import keys
    from tests.test_enterprise_runtime_role import runtime
    from tests.test_governance_collection import runtime as managed_fixture

    c = context
    managed_fixture(c)
    provider = keys(c, tmp_path, "v1", {"v1": b"k" * 32})
    with runtime(c) as (store, role):
        with c.store.transaction() as tx:
            tx.execute(
                "UPDATE governance_operations SET state='reconciled',active_key_version='v1',control_digest=%s",
                ("e" * 64,),
            )
        store.production_operations_required, store.runtime_key_version = True, "v1"
        cp = client(witness, store.organization_id)
        cp.check(store, publish=True)
        identity = {"artifact": "a" * 64}
        monkeypatch.setattr(operations, "artifact_identity", lambda: identity["artifact"])
        profile_data = json.loads(
            Path("deployment/enterprise/production-profile.example.json").read_text()
        )
        profile_data.update(
            artifact=identity["artifact"],
            schema=operations.digest(operations.schema_identity()),
            public_origin="https://guard.example.test",
        )
        profile_data["evidence"] = dict.fromkeys(profile_data["evidence"], "synthetic-fixture-only")
        profile = operations.ProductionProfile.parse(profile_data)
        monkeypatch.setattr(
            "app.enterprise.operations.configuration", lambda _settings: (profile, cp)
        )
        filenames = []
        for name in (
            "PROFILE",
            "CHECKPOINT",
            "DB",
            "OIDC_SECRET",
            "MANAGED_KEYS",
            "SUBJECT_OIDC_SECRET",
        ):
            filename = tmp_path / (name + ".json")
            filename.write_text("{}")
            if name == "MANAGED_KEYS":
                filename = tmp_path / "v1.key"
            monkeypatch.setenv("AIGUARD_ENTERPRISE_" + name + "_FILE", str(filename))
            filenames.append(filename)
        settings = Settings(
            store.organization_id,
            store._dsn,
            c.a.issuer,
            "synthetic-client",
            "synthetic-secret",
            profile.public_origin,
        )
        from app.enterprise.subject_auth import SubjectOIDCSettings

        subject = SubjectOIDCSettings(
            issuer=settings.issuer,
            client_id="synthetic-subject",
            client_secret="synthetic-subject-secret",
            public_origin=settings.public_origin,
            staff_client_id=settings.client_id,
        )
        filenames[2].write_text(
            json.dumps({"dsn": store._dsn, "purpose": "synthetic_enterprise_tests"})
        )
        filenames[3].write_text(json.dumps({"client_secret": settings.client_secret}))
        filenames[5].write_text(json.dumps({"client_secret": subject.client_secret}))
        gate = RuntimeGate(settings, store, provider)
        gate.subject_settings = subject
        assert gate.refresh()["status"] == "ready"
        try:
            yield gate, c, store, role, provider, cp, identity, filenames
        finally:
            gate.close()


def test_cold_concurrent_unauthenticated_requests_do_not_run_full_readiness(monkeypatch):
    full_calls = []

    def full(*_args, **_kwargs):
        full_calls.append(True)
        return {"status": "blocked", "checks": {"synthetic_full_scan": "blocked"}}

    monkeypatch.setattr("app.enterprise.operations.runtime_report", full)
    settings = Settings(
        uuid4(),
        "host=127.0.0.1 port=1 dbname=synthetic",
        "https://idp.example.test",
        "synthetic-client",
        "synthetic-secret",
        "https://guard.example.test",
    )
    app = create_app(settings, subject_settings=None, managed_key_provider=None)
    http = TestClient(app, base_url=settings.public_origin)
    paths = ["/static/tokens.css", "/api/activities", "/health/ready"] * 4
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda path: http.get(path).status_code, paths))
    assert results == [503] * len(paths)
    assert full_calls == []
    assert http.get("/health/live").status_code == 200
    http.close()


def test_http_admission_does_not_reuse_local_success_across_identity_io():
    import asyncio
    from types import SimpleNamespace

    from app.enterprise.server import _production_readiness

    class Gate:
        ready = True

        def request_report(self):
            status = "ready" if self.ready else "blocked"
            return {"status": status, "checks": {"synthetic_scope": status}}

    gate = Gate()

    class Identity:
        async def check_ready(self, **_kwargs):
            gate.ready = False

    report = asyncio.run(
        _production_readiness(
            None, None, None, Identity(), SimpleNamespace(subject_oidc=Identity()), gate
        )
    )
    assert report["status"] == "blocked"


def test_overlapping_identity_probes_share_only_the_live_flight_and_retry_failures():
    import asyncio
    from types import SimpleNamespace

    from app.enterprise.server import _IdentityFlight, _production_readiness

    async def scenario():
        joined, started, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        counts = {"joined": 0, "staff": 0, "subject": 0}

        class Gate:
            def request_report(self):
                return {"status": "ready", "checks": {"synthetic_local_scope": "ready"}}

        class Flight(_IdentityFlight):
            async def check(self, operation):
                counts["joined"] += 1
                if counts["joined"] == 6:
                    joined.set()
                return await super().check(operation)

        class Staff:
            fail = False

            async def check_ready(self, **_kwargs):
                counts["staff"] += 1
                started.set()
                await release.wait()
                if self.fail:
                    raise GovernanceError("identity_unavailable")

        class Subject:
            async def check_ready(self, **_kwargs):
                counts["subject"] += 1

        staff, router, flight, gate = (
            Staff(),
            SimpleNamespace(subject_oidc=Subject()),
            Flight(),
            Gate(),
        )
        tasks = [
            asyncio.create_task(
                _production_readiness(None, None, None, staff, router, gate, flight)
            )
            for _ in range(6)
        ]
        await asyncio.wait_for(joined.wait(), 5)
        await asyncio.wait_for(started.wait(), 5)
        assert counts["staff"] == 1
        release.set()
        assert all(report["status"] == "ready" for report in await asyncio.gather(*tasks))
        assert counts["subject"] == 1
        staff.fail = True
        assert (await _production_readiness(None, None, None, staff, router, gate, flight))[
            "status"
        ] == "blocked"
        assert counts["staff"] == 2

    asyncio.run(scenario())


def append(store, count=1):
    with store.transaction() as tx:
        store.lock(tx)
        for _ in range(count):
            store.append_event(tx, event_code="operations.synthetic_extension")
        row = tx.execute(
            "SELECT sequence,event_hash FROM governance_audit ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
    return row["sequence"], row["event_hash"]


def test_signed_extension_checks_new_events_without_full_historical_or_crypto_scans(
    context, witness, monkeypatch
):
    from pii_redactor.governance.evidence import ProtectedStorage

    store = context.store
    cp = client(witness, store.organization_id)
    receipt = cp.check(store, publish=True)
    verified = (receipt["sequence"], receipt["event_hash"])
    current = append(store, 3)
    cp.publish(*current, previous=verified)

    def full_forbidden(*_args, **_kwargs):
        raise AssertionError("Request attempted full historical qualification")

    monkeypatch.setattr(store, "verify_audit", full_forbidden)
    monkeypatch.setattr(ProtectedStorage, "open", full_forbidden)
    fresh = cp.check_extension(store, verified, receipt)
    assert fresh["sequence"] == current[0]


def test_qualified_concurrent_requests_never_decrypt_or_rescan_history(qualified, monkeypatch):
    import psycopg

    from pii_redactor.governance.evidence import ProtectedStorage

    gate, c, store, _role, _provider, cp, _identity, _files = qualified
    previous = gate._proof["witness"]
    current = append(c.store, 500)
    cp.publish(*current, previous=(previous["sequence"], previous["event_hash"]))
    assert gate.refresh()["status"] == "ready"
    scans = []
    queries = []
    execute = psycopg.Connection.execute

    def counted(connection, *args, **kwargs):
        queries.append(True)
        return execute(connection, *args, **kwargs)

    def full_forbidden(*_args, **_kwargs):
        scans.append(True)
        raise AssertionError("Request attempted full qualification")

    monkeypatch.setattr(store, "verify_audit", full_forbidden)
    monkeypatch.setattr(ProtectedStorage, "open", full_forbidden)
    monkeypatch.setattr(psycopg.Connection, "execute", counted)
    with ThreadPoolExecutor(max_workers=4) as pool:
        reports = list(pool.map(lambda _i: gate.request_report(), range(8)))
    assert all(r["status"] == "ready" for r in reports)
    assert scans == []
    assert len(queries) <= 8 * 32


@pytest.mark.parametrize("change", ["malformed", "different_key"])
def test_refresh_never_qualifies_a_key_file_that_no_longer_matches_memory(qualified, change):
    gate, _c, _store, _role, _provider, _cp, _identity, filenames = qualified
    path = filenames[4]
    if change == "malformed":
        path.write_text("{}")
    else:
        record = json.loads(path.read_text())
        record["keys"][0]["key_hex"] = (b"z" * 32).hex()
        path.write_text(json.dumps(record))
    assert gate.request_report()["status"] == "blocked"
    assert gate.refresh()["status"] == "blocked"
    assert gate.request_report()["status"] == "blocked"


@pytest.mark.parametrize("kind,index", [("database", 2), ("staff", 3), ("subject", 5)])
@pytest.mark.parametrize("change", ["malformed", "different_valid_value"])
def test_refresh_never_blesses_credential_file_drift_against_loaded_clients(
    qualified, kind, index, change
):
    gate, _c, _store, _role, _provider, _cp, _identity, filenames = qualified
    path = filenames[index]
    if change == "malformed":
        path.write_text("{}")
    else:
        record = json.loads(path.read_text())
        record["dsn" if kind == "database" else "client_secret"] = (
            "host=127.0.0.1 port=1 dbname=synthetic"
            if kind == "database"
            else "changed-synthetic-secret"
        )
        path.write_text(json.dumps(record))
    assert gate.request_report()["status"] == "blocked"
    assert gate.refresh()["status"] == "blocked"
    assert gate.request_report()["status"] == "blocked"


@pytest.mark.parametrize(
    "change",
    [
        "profile",
        "artifact",
        "schema",
        "key_file",
        "key_memory",
        "key_epoch",
        "quarantine",
        "role",
        "witness",
        "expiry",
        "acl",
    ],
)
def test_qualified_request_proof_is_invalidated_by_current_boundary_changes(qualified, change):
    from psycopg import sql

    gate, c, _store, role, provider, cp, identity, filenames = qualified
    if change == "profile":
        filenames[0].write_text('{"changed":true}')
    elif change == "artifact":
        identity["artifact"] = "b" * 64
    elif change == "key_file":
        filenames[4].write_text("{}")
    elif change == "key_memory":
        provider._keys.clear()
    elif change == "witness":
        cp._token = "changed-synthetic-authority"
    elif change == "expiry":
        gate._proof["until"] = 0
    elif change == "acl":
        if os.name == "nt":
            import subprocess

            subprocess.run(
                ["icacls", str(filenames[4]), "/grant", "*S-1-1-0:R"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            filenames[4].chmod(0o644)
    else:
        with c.store.transaction() as tx:
            if change == "schema":
                tx.execute("UPDATE governance_schema SET digest=%s WHERE version=1", ("f" * 64,))
            elif change == "role":
                tx.execute(
                    sql.SQL("GRANT UPDATE(state) ON governance_operations TO {}").format(
                        sql.Identifier(role)
                    )
                )
            elif change == "key_epoch":
                tx.execute("UPDATE governance_operations SET active_key_version='v2'")
            else:
                tx.execute("UPDATE governance_operations SET state='quarantined'")
    assert gate.request_report()["status"] == "blocked"


def test_request_cannot_publish_ready_after_its_full_proof_expires_during_witness_io(
    qualified, monkeypatch
):
    gate, _c, _store, _role, _provider, cp, _identity, _files = qualified
    fetch = cp.fetch

    def expiry(*args, **kwargs):
        receipt = fetch(*args, **kwargs)
        gate._proof["until"] = 0
        return receipt

    monkeypatch.setattr(cp, "fetch", expiry)
    assert gate.request_report()["status"] == "blocked"


def test_an_old_request_cannot_erase_a_new_background_qualification(qualified, monkeypatch):
    import threading

    gate, _c, _store, _role, _provider, cp, _identity, _files = qualified
    reached, release = threading.Event(), threading.Event()
    fetch = cp.fetch

    def paused(*args, **kwargs):
        receipt = fetch(*args, **kwargs)
        if threading.current_thread().name.startswith("old-request"):
            reached.set()
            assert release.wait(10)
        return receipt

    monkeypatch.setattr(cp, "fetch", paused)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="old-request") as pool:
        old = pool.submit(gate.request_report)
        assert reached.wait(10)
        try:
            assert gate.refresh()["status"] == "ready"
            replacement = gate._proof
        finally:
            release.set()
        assert old.result(timeout=10)["status"] == "blocked"
    assert gate._proof is replacement
    assert gate.request_report()["status"] == "ready"


@pytest.mark.parametrize(
    "failure", ["prefix", "extension", "truncated", "lag", "sink", "organization"]
)
def test_signed_extension_rejects_changed_prefix_truncation_divergence_lag_and_sink(
    context, witness, failure
):
    store = context.store
    cp = client(witness, store.organization_id, max_events=1)
    receipt = cp.check(store, publish=True)
    verified = (receipt["sequence"], receipt["event_hash"])
    if failure == "sink":
        cp.url = "http://127.0.0.1:1"
    elif failure == "lag":
        append(store, 2)
    else:
        current = append(store)
        if failure == "extension":
            cp.publish(*current, previous=verified)
        with store.transaction() as tx:
            tx.execute("ALTER TABLE governance_audit DISABLE TRIGGER governance_audit_immutable")
            if failure == "prefix":
                tx.execute(
                    "UPDATE governance_audit SET event_hash=%s WHERE sequence=%s",
                    ("f" * 64, verified[0]),
                )
            elif failure == "extension":
                tx.execute(
                    "UPDATE governance_audit SET previous_hash=%s WHERE sequence=%s",
                    ("f" * 64, current[0]),
                )
            elif failure == "organization":
                from pii_redactor.governance.store import _event_digest

                assert (
                    tx.execute("SELECT current_schema() AS name")
                    .fetchone()["name"]
                    .startswith("test_gov_")
                )
                tx.execute(
                    "ALTER TABLE governance_audit DROP CONSTRAINT governance_audit_organization_id_fkey"
                )
                event = tx.execute(
                    "SELECT * FROM governance_audit WHERE sequence=%s", (current[0],)
                ).fetchone()
                event["organization_id"] = uuid4()
                changed_hash = _event_digest(event)
                tx.execute(
                    "UPDATE governance_audit SET organization_id=%s,event_hash=%s WHERE sequence=%s",
                    (event["organization_id"], changed_hash, current[0]),
                )
            else:
                tx.execute("DELETE FROM governance_audit WHERE sequence=%s", (verified[0],))
            tx.execute("ALTER TABLE governance_audit ENABLE TRIGGER governance_audit_immutable")
        if failure == "organization":
            cp.publish(current[0], changed_hash, previous=verified)
    with pytest.raises(GovernanceError, match="checkpoint_(integrity_failure|unavailable)"):
        cp.check_extension(store, verified, receipt)


def test_full_readiness_requires_a_concrete_matching_active_key_even_for_offline_probe(qualified):
    from pii_redactor.governance.key_operations import verify_keys
    from pii_redactor.governance.operations import readiness

    gate, c, store, _role, provider, cp, _identity, _files = qualified
    store.production_operations_required = False
    with c.store.transaction() as tx:
        tx.execute("UPDATE governance_operations SET active_key_version=NULL")
    report = readiness(store, gate._proof["profile"], cp, lambda: verify_keys(store, provider))
    assert report["status"] == "blocked"
    assert report["checks"]["restore"] == "blocked"


def test_http_readiness_rechecks_local_proof_after_identity_io(qualified):
    import asyncio
    from types import SimpleNamespace

    from app.enterprise.server import _production_readiness

    gate, _c, store, _role, provider, _cp, _identity, _files = qualified

    class Identity:
        async def check_ready(self, **_kwargs):
            gate._proof["until"] = 0

    report = asyncio.run(
        _production_readiness(
            gate.settings,
            store,
            provider,
            Identity(),
            SimpleNamespace(subject_oidc=Identity()),
            gate,
        )
    )
    assert report["status"] == "blocked"
