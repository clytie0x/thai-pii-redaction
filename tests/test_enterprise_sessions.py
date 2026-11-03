"""Real PostgreSQL login/session authority, never browser-declared roles."""

import secrets

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from app.enterprise.sessions import StaffSessions
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.registry import Registry
from tests import governance_helpers

context = governance_helpers.context
database = governance_helpers.database


@pytest.fixture
def sessions(context):
    return StaffSessions(context.store)


def test_login_state_is_browser_bound_and_single_use(sessions):
    binding = secrets.token_urlsafe(32)
    attempt = sessions.begin_login(binding)
    with pytest.raises(GovernanceError, match="^authentication_failed$"):
        sessions.consume_login(attempt.state, secrets.token_urlsafe(32))
    recovered = sessions.consume_login(attempt.state, binding)
    assert recovered.nonce == attempt.nonce
    assert recovered.code_verifier == attempt.code_verifier
    with pytest.raises(GovernanceError, match="^authentication_failed$"):
        sessions.consume_login(attempt.state, binding)


def test_expired_login_state_does_not_return_verifier(context, sessions):
    binding = secrets.token_urlsafe(32)
    attempt = sessions.begin_login(binding)
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE enterprise_login_states SET expires_at=clock_timestamp()-interval '1 second'"
        )
    with pytest.raises(GovernanceError, match="^authentication_failed$"):
        sessions.consume_login(attempt.state, binding)


def test_session_is_hash_only_and_returns_no_claimed_roles(context, sessions):
    grant = sessions.issue(context.a)
    principal = sessions.resolve(grant.cookie)
    assert principal.issuer == context.a.issuer and principal.subject == context.a.subject
    assert "roles" not in principal.model_dump()
    assert grant.cookie not in repr(grant) and grant.csrf not in repr(grant)
    with context.store.transaction() as tx:
        row = tx.execute("SELECT * FROM enterprise_staff_sessions").fetchone()
        assert grant.cookie not in str(row) and grant.csrf not in str(row)
    assert Registry(context.store).list_activities(principal) == []


def test_revocation_invalidates_already_resolved_principal(context, sessions):
    grant = sessions.issue(context.a)
    principal = sessions.resolve(grant.cookie)
    sessions.logout(grant.cookie, grant.csrf)
    with pytest.raises(GovernanceError, match="^authentication_required$"):
        Registry(context.store).list_activities(principal)
    with pytest.raises(GovernanceError, match="^authentication_required$"):
        sessions.resolve(grant.cookie)


def test_membership_revision_invalidates_cookie_after_reactivation(context, sessions):
    grant = sessions.issue(context.a)
    principal = sessions.resolve(grant.cookie)
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET enabled=false,revision=revision+1 WHERE member_id=%s",
            (context.ids[0],),
        )
        tx.execute(
            "UPDATE governance_members SET enabled=true,revision=revision+1 WHERE member_id=%s",
            (context.ids[0],),
        )
    with pytest.raises(GovernanceError, match="^authentication_required$"):
        sessions.resolve(grant.cookie)
    with pytest.raises(GovernanceError, match="^authentication_required$"):
        Registry(context.store).list_activities(principal)


def test_invalid_csrf_cannot_logout_an_active_session(context, sessions):
    grant = sessions.issue(context.a)
    with pytest.raises(GovernanceError, match="^forbidden$"):
        sessions.logout(grant.cookie, secrets.token_urlsafe(32))
    assert sessions.resolve(grant.cookie).subject == context.a.subject


@pytest.mark.parametrize("column", ["idle_until", "absolute_until"], ids=str)
def test_expired_sessions_cannot_renew(context, sessions, column):
    grant = sessions.issue(context.a)
    # The column comes only from this fixed test parameter set.
    with context.store.transaction() as tx:
        tx.execute(
            f"UPDATE enterprise_staff_sessions SET {column}=clock_timestamp()-interval '1 second'"
        )
        before = tx.execute("SELECT idle_until FROM enterprise_staff_sessions").fetchone()[
            "idle_until"
        ]
    with pytest.raises(GovernanceError, match="^authentication_required$"):
        sessions.resolve(grant.cookie)
    with context.store.transaction() as tx:
        assert (
            tx.execute("SELECT idle_until FROM enterprise_staff_sessions").fetchone()["idle_until"]
            == before
        )


def test_audit_failure_cannot_publish_session(context, sessions, monkeypatch):
    def fail(*_args, **_kwargs):
        raise GovernanceError("storage_failure")

    monkeypatch.setattr(context.store, "append_event", fail)
    with pytest.raises(GovernanceError, match="^storage_failure$"):
        sessions.issue(context.a)
    with context.store.transaction() as tx:
        assert (
            tx.execute("SELECT count(*) AS n FROM enterprise_staff_sessions").fetchone()["n"] == 0
        )


def test_wrong_identity_is_not_enrolled_by_login(context, sessions):
    from pii_redactor.governance.models import Principal

    foreign = Principal(issuer=context.a.issuer, subject="unknown-staff")
    with pytest.raises(GovernanceError, match="^authentication_required$"):
        sessions.issue(foreign)


def test_session_state_persists_across_service_objects(context, sessions):
    grant = sessions.issue(context.a)
    replacement = StaffSessions(context.store)
    assert replacement.resolve(grant.cookie).subject == context.a.subject


def test_concurrent_login_callback_has_only_one_winner(sessions):
    from concurrent.futures import ThreadPoolExecutor

    binding = secrets.token_urlsafe(32)
    attempt = sessions.begin_login(binding)

    def consume(_index):
        try:
            sessions.consume_login(attempt.state, binding)
        except GovernanceError as error:
            assert error.code == "authentication_failed"
            return "denied"
        return "accepted"

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(consume, range(2))) == ["accepted", "denied"]


def test_replayed_logout_does_not_append_a_second_outcome(context, sessions):
    grant = sessions.issue(context.a)
    sessions.logout(grant.cookie, grant.csrf)
    with context.store.transaction() as tx:
        before = tx.execute("SELECT count(*) AS n FROM governance_audit").fetchone()["n"]
    sessions.logout(grant.cookie, grant.csrf)
    with context.store.transaction() as tx:
        assert tx.execute("SELECT count(*) AS n FROM governance_audit").fetchone()["n"] == before


@pytest.mark.parametrize("column", ["idle_until", "absolute_until"], ids=str)
def test_session_deadline_is_rechecked_after_waiting_for_lock(
    context, sessions, monkeypatch, column
):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager

    grant = sessions.issue(context.a)
    transaction = context.store.transaction
    with transaction() as tx:
        tx.execute(
            f"UPDATE enterprise_staff_sessions SET {column}=clock_timestamp()+interval '2 seconds'"
        )
    ready = threading.Event()
    backend = {}

    @contextmanager
    def observed_transaction():
        with transaction() as tx:
            backend["pid"] = tx.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
            ready.set()
            yield tx

    monkeypatch.setattr(context.store, "transaction", observed_transaction)
    with ThreadPoolExecutor(max_workers=1) as executor:
        with transaction() as holder:
            holder.execute("SELECT session_id FROM enterprise_staff_sessions FOR SHARE")
            future = executor.submit(sessions.resolve, grant.cookie)
            assert ready.wait(1), "Resolver did not reach its database transaction"
            until = time.monotonic() + 1
            while time.monotonic() < until:
                row = holder.execute(
                    "SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s", (backend["pid"],)
                ).fetchone()
                if row and row["wait_event_type"] == "Lock":
                    break
                time.sleep(0.01)
            else:
                pytest.fail("Resolver did not block on the controlled session lock")
            holder.execute("SELECT pg_sleep(2.05)")
        with pytest.raises(GovernanceError, match="^authentication_required$"):
            future.result(timeout=5)


@pytest.mark.parametrize("column", ["idle_until", "absolute_until"], ids=str)
def test_domain_authorization_rechecks_deadline_after_lock(context, sessions, monkeypatch, column):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager

    grant = sessions.issue(context.a)
    principal = sessions.resolve(grant.cookie)
    transaction = context.store.transaction
    with transaction() as tx:
        tx.execute(
            f"UPDATE enterprise_staff_sessions SET {column}=clock_timestamp()+interval '2 seconds'"
        )
    ready = threading.Event()
    backend = {}

    @contextmanager
    def observed_transaction():
        with transaction() as tx:
            backend["pid"] = tx.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
            ready.set()
            yield tx

    monkeypatch.setattr(context.store, "transaction", observed_transaction)
    with ThreadPoolExecutor(max_workers=1) as executor:
        with transaction() as holder:
            holder.execute("SELECT session_id FROM enterprise_staff_sessions FOR UPDATE")
            future = executor.submit(Registry(context.store).list_activities, principal)
            assert ready.wait(1), "Domain authorization did not reach its transaction"
            until = time.monotonic() + 1
            while time.monotonic() < until:
                row = holder.execute(
                    "SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s", (backend["pid"],)
                ).fetchone()
                if row and row["wait_event_type"] == "Lock":
                    break
                time.sleep(0.01)
            else:
                pytest.fail("Domain authorization did not wait on the controlled session lock")
            holder.execute("SELECT pg_sleep(2.05)")
        with pytest.raises(GovernanceError, match="^authentication_required$"):
            future.result(timeout=5)
