"""A real nonowner runtime role must work and cannot obtain release authority."""

import secrets
from contextlib import contextmanager
from uuid import uuid4

import pytest

psycopg = pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")
from psycopg import sql
from psycopg.conninfo import make_conninfo

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.operations import check_runtime_role
from pii_redactor.governance.runtime_roles import grant_statements
from pii_redactor.governance.store import Store
from tests import governance_helpers as fixtures

context = fixtures.context
database = fixtures.database


@contextmanager
def runtime(c, *, readonly=False):
    name = "m10_role_" + uuid4().hex
    password = secrets.token_urlsafe(32)
    with c.store.transaction() as tx:
        schema = tx.execute("SELECT current_schema() AS name").fetchone()["name"]
        tx.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(name), sql.Literal(password)
            )
        )
        if readonly:
            tx.execute(
                sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                    sql.Identifier(schema), sql.Identifier(name)
                )
            )
            tx.execute(
                sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(
                    sql.Identifier(schema), sql.Identifier(name)
                )
            )
        else:
            for statement in grant_statements(schema, name):
                tx.execute(statement)
    try:
        yield (
            Store(
                make_conninfo(c.store._dsn, user=name, password=password), c.store.organization_id
            ),
            name,
        )
    finally:
        assert name.startswith("m10_role_") and len(name) == 41
        with c.store.transaction() as tx:
            for category in ("TABLES", "SEQUENCES", "FUNCTIONS"):
                tx.execute(
                    sql.SQL("REVOKE ALL ON ALL {} IN SCHEMA {} FROM {}").format(
                        sql.SQL(category), sql.Identifier(schema), sql.Identifier(name)
                    )
                )
            tx.execute(
                sql.SQL("REVOKE ALL ON SCHEMA {} FROM {}").format(
                    sql.Identifier(schema), sql.Identifier(name)
                )
            )
            tx.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(name)))


def test_readonly_role_cannot_claim_runtime_readiness(context):
    with runtime(context, readonly=True) as (store, _name):
        with pytest.raises(GovernanceError, match="runtime_role_insufficient"):
            check_runtime_role(store)


@pytest.mark.parametrize(
    "grant",
    [
        "UPDATE ON governance_operations",
        "UPDATE(state) ON governance_operations",
        "INSERT ON governance_schema",
        "UPDATE(digest) ON governance_schema",
        "UPDATE ON governance_audit",
        "DELETE ON governance_rights_history",
        "UPDATE(plan_version) ON governance_rights_instruction_bindings",
        "TRIGGER ON governance_members",
        "TRUNCATE ON governance_control_history",
        "UPDATE ON governance_instruction_controls",
        "UPDATE ON governance_restore_sessions",
        "INSERT ON governance_restore_journal",
        "UPDATE ON governance_initial_activations",
        "INSERT ON governance_initial_journal",
    ],
)
def test_forbidden_table_or_column_grants_are_rejected(context, grant):
    with runtime(context) as (store, name):
        with context.store.transaction() as tx:
            tx.execute(sql.SQL("GRANT {} TO {}").format(sql.SQL(grant), sql.Identifier(name)))
        with pytest.raises(GovernanceError, match="runtime_role_overprivileged"):
            check_runtime_role(store)


def test_actual_runtime_login_and_registry_mutation_work_with_quarantine_fences(context):
    from app.enterprise.sessions import StaffSessions
    from pii_redactor.governance.registry import Registry
    from tests.test_governance_registry import activity

    c = context
    with runtime(c) as (store, _name):
        assert check_runtime_role(store)
        with c.store.transaction() as tx:
            tx.execute(
                "UPDATE governance_operations SET state='reconciled',active_key_version='v1'"
            )
        store.production_operations_required, store.runtime_key_version = True, "v1"
        sessions = StaffSessions(store)
        binding = "b" * 43
        attempt = sessions.begin_login(binding)
        assert sessions.consume_login(attempt.state, binding).state == attempt.state
        grant = sessions.issue(c.a)
        principal = sessions.resolve(grant.cookie)
        created = Registry(store).create_activity(principal, uuid4(), activity())
        assert created["revision"] == 1
        with c.store.transaction() as tx:
            tx.execute("UPDATE governance_operations SET state='quarantined'")
        with pytest.raises(GovernanceError, match="storage_failure"):
            sessions.resolve(grant.cookie)


def test_runtime_cannot_disable_database_fence_or_change_active_key(context):
    c = context
    with runtime(c) as (store, _name):
        with pytest.raises(GovernanceError, match="storage_failure"):
            with store.transaction() as tx:
                tx.execute("SET LOCAL aiguard.production_operations='off'")
                tx.execute(
                    "UPDATE governance_members SET revision=revision+1 WHERE member_id=%s",
                    (c.ids[0],),
                )
        with c.store.transaction() as tx:
            tx.execute(
                "UPDATE governance_operations SET state='reconciled',active_key_version='v2'"
            )
        with pytest.raises(GovernanceError, match="storage_failure"):
            with store.transaction() as tx:
                tx.execute("SET LOCAL aiguard.production_operations='off'")
                tx.execute("SET LOCAL aiguard.key_version='v1'")
                tx.execute(
                    "UPDATE governance_members SET revision=revision+1 WHERE member_id=%s",
                    (c.ids[0],),
                )
        with pytest.raises(GovernanceError, match="storage_failure"):
            with store.transaction() as tx:
                tx.execute(
                    "UPDATE governance_operations SET state='reconciled',active_key_version='v1'"
                )


def test_runtime_sequence_grants_are_functional_and_cannot_reset_counters(context):
    with context.store.transaction() as tx:
        tx.execute("CREATE SEQUENCE m10_runtime_sequence")
    with runtime(context) as (store, name):
        assert check_runtime_role(store)
        with store.transaction() as tx:
            assert tx.execute("SELECT nextval('m10_runtime_sequence') AS n").fetchone()["n"] == 1
        with context.store.transaction() as tx:
            tx.execute(
                sql.SQL("GRANT UPDATE ON SEQUENCE m10_runtime_sequence TO {}").format(
                    sql.Identifier(name)
                )
            )
        with pytest.raises(GovernanceError, match="runtime_role_overprivileged"):
            check_runtime_role(store)


def test_runtime_cannot_use_public_definer_execution(context):
    with runtime(context) as (store, name):
        with context.store.transaction() as tx:
            tx.execute("GRANT EXECUTE ON FUNCTION governance_runtime_guard() TO PUBLIC")
        with pytest.raises(GovernanceError, match="runtime_role_overprivileged"):
            check_runtime_role(store)
        with context.store.transaction() as tx:
            tx.execute("REVOKE EXECUTE ON FUNCTION governance_runtime_guard() FROM PUBLIC")
        assert check_runtime_role(store)


def test_runtime_cannot_inherit_another_role(context):
    auxiliary = "m10_aux_" + uuid4().hex
    with context.store.transaction() as tx:
        tx.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(auxiliary)))
    try:
        with runtime(context) as (store, name):
            with context.store.transaction() as tx:
                tx.execute(
                    sql.SQL("GRANT {} TO {}").format(
                        sql.Identifier(auxiliary), sql.Identifier(name)
                    )
                )
            try:
                with pytest.raises(GovernanceError, match="runtime_role_overprivileged"):
                    check_runtime_role(store)
            finally:
                with context.store.transaction() as tx:
                    tx.execute(
                        sql.SQL("REVOKE {} FROM {}").format(
                            sql.Identifier(auxiliary), sql.Identifier(name)
                        )
                    )
    finally:
        with context.store.transaction() as tx:
            tx.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(auxiliary)))


def test_runtime_cannot_be_a_set_role_view_of_an_operator_session(context):
    from pii_redactor.governance.runtime_roles import check_runtime_role as scoped_check

    with runtime(context) as (store, name):
        with context.store.transaction() as tx:
            tx.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(name)))
            with pytest.raises(GovernanceError, match="runtime_role_overprivileged"):
                scoped_check(store, tx=tx)
