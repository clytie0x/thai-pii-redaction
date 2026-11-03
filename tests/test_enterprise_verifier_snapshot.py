"""Historical qualification cannot block current runtime sessions and reads."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")
pytest.importorskip("fastapi", reason="optional enterprise HTTP dependency")

from fastapi.testclient import TestClient
from starlette.concurrency import run_in_threadpool

from app.enterprise.server import create_app
from app.enterprise.sessions import StaffSessions
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.evidence import ProtectedStorage
from tests import test_enterprise_request_gate as fixtures

context = fixtures.context
database = fixtures.database
witness = fixtures.witness
qualified = fixtures.qualified


@contextmanager
def paused_refresh(gate, monkeypatch):
    reached, release = threading.Event(), threading.Event()
    original = ProtectedStorage.open
    paused_at = []

    def paused(protection, *args, **kwargs):
        if threading.current_thread().name.startswith("full-snapshot") and not reached.is_set():
            paused_at.append(time.monotonic())
            reached.set()
            assert release.wait(15)
        return original(protection, *args, **kwargs)

    monkeypatch.setattr(ProtectedStorage, "open", paused)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="full-snapshot") as pool:
        future = pool.submit(gate.refresh)
        assert reached.wait(10)
        try:
            yield future, release, paused_at
        finally:
            release.set()
            future.result(timeout=10)


def app_client(gate, store, provider, principal, monkeypatch):
    sessions = StaffSessions(store)
    grant = sessions.issue(principal)

    async def ready(*_args):
        # Uses the actual already-qualified infrastructure gate; auth/DB stay real.
        return await run_in_threadpool(gate.request_report)

    monkeypatch.setattr("app.enterprise.server._production_readiness", ready)
    app = create_app(
        gate.settings, store=store, subject_settings=None, managed_key_provider=provider
    )
    client = TestClient(app, base_url=gate.settings.public_origin, raise_server_exceptions=False)
    client.cookies.set(gate.settings.cookie_prefix + "session", grant.cookie)
    return client, sessions, grant


def test_full_verifier_paused_over_runtime_lock_timeout_does_not_block_real_session_or_route(
    qualified, monkeypatch
):
    gate, c, store, _role, provider, _cp, _identity, _files = qualified
    http, sessions, grant = app_client(gate, store, provider, c.a, monkeypatch)
    try:
        with paused_refresh(gate, monkeypatch) as (verification, release, paused_at):
            timer = threading.Timer(6.2, release.set)
            timer.start()
            try:
                with ThreadPoolExecutor(max_workers=2) as readers:
                    actual_session = readers.submit(sessions.resolve, grant.cookie)
                    actual_route = readers.submit(http.get, "/api/enterprise/v1/activities")
                    assert actual_session.result(timeout=10).subject == c.a.subject
                    assert actual_route.result(timeout=10).status_code == 200
                assert not release.is_set(), (
                    "Current callers must finish while the scan is still paused"
                )
                assert verification.result(timeout=10)["status"] == "ready"
                assert time.monotonic() - paused_at[0] >= 6
            finally:
                timer.cancel()
                release.set()
                timer.join()
    finally:
        http.close()


def test_private_verifier_snapshot_is_sql_read_only_and_not_a_runtime_store(qualified):
    gate, c, store, _role, _provider, cp, _identity, _files = qualified
    with store.private_snapshot() as snapshot:
        with snapshot.transaction() as tx:
            assert (
                tx.execute("SHOW transaction_read_only").fetchone()["transaction_read_only"] == "on"
            )
            assert (
                tx.execute("SHOW transaction_isolation").fetchone()["transaction_isolation"]
                == "repeatable read"
            )
        assert snapshot.verify_audit() == snapshot.verify_audit()
        with pytest.raises(GovernanceError, match="verifier_snapshot_only"):
            snapshot.lock(None)
        with pytest.raises(GovernanceError, match="verifier_snapshot_only"):
            cp.check(snapshot, publish=True)
        with pytest.raises(AttributeError):
            create_app(
                gate.settings, store=snapshot, subject_settings=None, managed_key_provider=None
            )
    with pytest.raises(GovernanceError, match="verifier_snapshot_closed"):
        snapshot.verify_audit()
    with pytest.raises(GovernanceError, match="storage_failure|verifier_snapshot_read_only"):
        with store.private_snapshot() as snapshot:
            with snapshot.transaction() as tx:
                tx.execute(
                    "UPDATE governance_members SET revision=revision+1 WHERE member_id=%s",
                    (c.ids[0],),
                )


def test_background_full_proof_uses_one_audit_scan_in_its_private_snapshot(qualified, monkeypatch):
    import psycopg

    from pii_redactor.governance import store as store_module

    gate = qualified[0]
    calls, original = [], store_module._audit_rows
    metadata, execute = [], psycopg.Connection.execute

    def counted(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    def observed(connection, query, *args, **kwargs):
        if "SELECT EXISTS(SELECT 1 FROM governance_audit" in str(query):
            metadata.append(True)
        return execute(connection, query, *args, **kwargs)

    monkeypatch.setattr(store_module, "_audit_rows", counted)
    monkeypatch.setattr(psycopg.Connection, "execute", observed)
    assert gate.refresh()["status"] == "ready"
    assert len(calls) == 1
    assert len(metadata) == 1


def test_verifier_repeated_queries_keep_one_mvcc_point_while_live_transactions_advance(qualified):
    _gate, c, store, _role, _provider, _cp, _identity, _files = qualified
    with store.private_snapshot() as snapshot:
        with snapshot.transaction() as tx:
            before = tx.execute(
                "SELECT revision FROM governance_members WHERE member_id=%s", (c.ids[1],)
            ).fetchone()["revision"]
        with c.store.transaction() as tx:
            tx.execute(
                "UPDATE governance_members SET revision=revision+1 WHERE member_id=%s", (c.ids[1],)
            )
        with snapshot.transaction() as tx:
            assert (
                tx.execute(
                    "SELECT revision FROM governance_members WHERE member_id=%s", (c.ids[1],)
                ).fetchone()["revision"]
                == before
            )
        with store.transaction() as tx:
            assert (
                tx.execute(
                    "SELECT revision FROM governance_members WHERE member_id=%s", (c.ids[1],)
                ).fetchone()["revision"]
                == before + 1
            )


def test_proof_publication_still_holds_the_real_current_transaction_fence(qualified, monkeypatch):
    gate, c, _store, _role, _provider, _cp, _identity, _files = qualified
    original, acquired = gate._proof_lock, []

    class ObservedLock:
        def __enter__(self):
            with c.store.transaction() as tx:
                acquired.append(
                    tx.execute(
                        "SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS acquired",
                        ("aiguard-governance:" + str(c.store.organization_id),),
                    ).fetchone()["acquired"]
                )
            return original.__enter__()

        def __exit__(self, *args):
            return original.__exit__(*args)

    monkeypatch.setattr(gate, "_proof_lock", ObservedLock())
    assert gate.refresh()["status"] == "ready"
    assert acquired == [False]


def test_current_membership_denial_is_never_served_from_the_verifier_snapshot(
    qualified, monkeypatch
):
    from pii_redactor.governance.authority import Authority

    gate, c, store, _role, provider, _cp, _identity, _files = qualified
    healthy, sessions, grant = app_client(gate, store, provider, c.a, monkeypatch)
    revoked, _sessions, _grant = app_client(gate, store, provider, c.b, monkeypatch)
    try:
        with paused_refresh(gate, monkeypatch) as (verification, release, _paused_at):
            Authority(store).suspend_member(c.a, uuid4(), c.ids[1], 1)
            assert sessions.resolve(grant.cookie).subject == c.a.subject
            assert healthy.get("/api/enterprise/v1/activities").status_code == 200
            assert revoked.get("/api/enterprise/v1/activities").status_code == 401
            release.set()
            assert verification.result(timeout=10)["status"] == "ready"
    finally:
        healthy.close()
        revoked.close()


def test_new_canonical_events_and_checkpoint_heads_extend_the_snapshot_proof(
    qualified, monkeypatch
):
    gate, _c, store, _role, _provider, cp, _identity, _files = qualified
    with paused_refresh(gate, monkeypatch) as (verification, release, _paused_at):
        previous = cp.fetch()
        current = fixtures.append(store, 3)
        cp.publish(*current, previous=(previous["sequence"], previous["event_hash"]))
        release.set()
        assert verification.result(timeout=10)["status"] == "ready"
    assert gate.request_report()["status"] == "ready"


def test_snapshot_checks_every_retained_witness_head_not_only_a_new_latest_head(qualified):
    from psycopg.types.json import Jsonb

    from pii_redactor.governance.store import _event_digest

    gate, c, _store, _role, _provider, cp, _identity, _files = qualified
    previous = cp.fetch()
    with c.store.transaction() as tx:
        assert (
            tx.execute("SELECT current_schema() AS name").fetchone()["name"].startswith("test_gov_")
        )
        tx.execute("ALTER TABLE governance_audit DISABLE TRIGGER governance_audit_immutable")
        events = tx.execute("SELECT * FROM governance_audit ORDER BY sequence").fetchall()
        prior = "0" * 64
        for index, event in enumerate(events):
            if index == 0:
                event["details"] = {"synthetic_rewrite": True}
            event["previous_hash"] = prior
            prior = event["event_hash"] = _event_digest(event)
            tx.execute(
                "UPDATE governance_audit SET details=%s,previous_hash=%s,event_hash=%s WHERE sequence=%s",
                (Jsonb(event["details"]), event["previous_hash"], prior, event["sequence"]),
            )
        tx.execute("ALTER TABLE governance_audit ENABLE TRIGGER governance_audit_immutable")
    newest = fixtures.append(c.store)
    cp.publish(*newest, previous=(previous["sequence"], previous["event_hash"]))
    assert c.store.verify_audit()["events"] == newest[0]
    assert gate.refresh()["status"] == "blocked"
    assert gate._proof is None


@pytest.mark.parametrize(
    "change",
    ["quarantine", "key", "role", "enrollment", "schema", "config", "sink", "signer", "identity"],
)
def test_changed_live_infrastructure_cannot_publish_an_old_snapshot_proof(
    qualified, monkeypatch, change
):
    from psycopg import sql

    gate, c, store, role, provider, cp, _identity, files = qualified
    with paused_refresh(gate, monkeypatch) as (verification, release, _paused_at):
        if change == "config":
            files[0].write_text('{"changed":true}')
        elif change == "sink":
            cp.url = "http://127.0.0.1:1"
        elif change == "signer":
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            cp.public_key = Ed25519PrivateKey.generate().public_key()
        elif change == "key":
            from pii_redactor.governance.key_operations import activate_rotation
            from tests.test_enterprise_key_fences import keys

            newer = keys(c, files[0].parent, "v2", {"v1": b"k" * 32, "v2": b"b" * 32})
            activate_rotation(c.store, provider, newer)
        elif change == "identity":
            original_dsn = store._dsn
            store._dsn = c.store._dsn
        else:
            with c.store.transaction() as tx:
                if change == "quarantine":
                    tx.execute("UPDATE governance_operations SET state='quarantined'")
                elif change == "enrollment":
                    tx.execute("UPDATE governance_organization SET enrolled_at=NULL")
                elif change == "schema":
                    tx.execute(
                        "UPDATE governance_schema SET digest=%s WHERE version=1", ("f" * 64,)
                    )
                else:
                    tx.execute(
                        sql.SQL("GRANT UPDATE(state) ON governance_operations TO {}").format(
                            sql.Identifier(role)
                        )
                    )
        release.set()
        try:
            assert verification.result(timeout=10)["status"] == "blocked"
        finally:
            if change == "identity":
                store._dsn = original_dsn
    assert gate._proof is None
