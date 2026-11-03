"""Real PostgreSQL authority tests. No SQLite or store mocks."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from uuid import UUID, uuid4

import pytest

psycopg = pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")
from psycopg import sql
from psycopg.conninfo import make_conninfo

ORG = UUID("b5186bb1-3431-4330-9b39-f365db8d4813")


@pytest.fixture
def database():
    filename = os.environ.get("AIGUARD_TEST_DB_FILE")
    if not filename:
        pytest.fail("Enterprise integration requires AIGUARD_TEST_DB_FILE")
    dsn = json.loads(Path(filename).read_text(encoding="utf-8"))["dsn"]
    schema = "test_gov_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    scoped = make_conninfo(dsn, options=f"-csearch_path={schema}")
    yield scoped
    assert re.fullmatch(r"test_gov_[0-9a-f]{32}", schema)
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def enrollments():
    from pii_redactor.governance.models import Enrollment, Principal

    return [
        Enrollment(
            principal=Principal(issuer="https://idp.example.test/realms/staff", subject="staff-a"),
            roles=["system_administrator", "data_steward"],
            departments=["operations"],
        ),
        Enrollment(
            principal=Principal(issuer="https://idp.example.test/realms/staff", subject="staff-b"),
            roles=["authority_reviewer", "privacy_reviewer", "auditor"],
            departments=["operations"],
        ),
    ]


def test_bootstrap_is_durable_and_audited_without_subject_values(database):
    from pii_redactor.governance.store import Store

    store = Store(database, ORG)
    store.migrate()
    members = store.bootstrap(enrollments())
    assert len(members) == 2 and members[0] != members[1]
    restarted = Store(database, ORG)
    restarted.migrate()
    with restarted.transaction() as tx:
        assert tx.execute("SELECT count(*) AS n FROM governance_members").fetchone()["n"] == 2
        events = tx.execute("SELECT event_code, details FROM governance_audit").fetchall()
    assert [row["event_code"] for row in events] == ["organization.enrolled"]
    assert "staff-a" not in json.dumps(events) and "staff-b" not in json.dumps(events)


def test_database_cannot_be_rebound_to_another_organization(database):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.store import Store

    Store(database, ORG).migrate()
    with pytest.raises(GovernanceError, match="organization_mismatch"):
        Store(database, uuid4()).migrate()


def test_bootstrap_requires_distinct_authorities_and_is_one_time(database):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.store import Store

    store = Store(database, ORG)
    store.migrate()
    pair = enrollments()
    with pytest.raises(GovernanceError, match="enrollment_invalid"):
        store.bootstrap([pair[0], pair[0]])
    store.bootstrap(pair)
    with pytest.raises(GovernanceError, match="already_enrolled"):
        store.bootstrap(pair)


def test_audit_failure_rolls_back_all_enrollment_state(database):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.store import Store

    store = Store(database, ORG)
    store.migrate()
    with store.transaction() as tx:
        tx.execute("""
            CREATE FUNCTION refuse_audit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic audit failure'; END $$;
            CREATE TRIGGER refuse BEFORE INSERT ON governance_audit
            FOR EACH ROW EXECUTE FUNCTION refuse_audit();
        """)
    with pytest.raises(GovernanceError, match="storage_failure"):
        store.bootstrap(enrollments())
    with store.transaction() as tx:
        assert tx.execute("SELECT count(*) AS n FROM governance_members").fetchone()["n"] == 0
        assert (
            tx.execute("SELECT enrolled_at FROM governance_organization").fetchone()["enrolled_at"]
            is None
        )


def test_changed_migration_fingerprint_is_rejected(database):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.store import Store

    store = Store(database, ORG)
    store.migrate()
    with store.transaction() as tx:
        tx.execute("UPDATE governance_schema SET digest = %s", ("0" * 64,))
    with pytest.raises(GovernanceError, match="migration_mismatch"):
        store.migrate()


def test_ordinary_transaction_failure_does_not_commit(database):
    from pii_redactor.governance.store import Store

    store = Store(database, ORG)
    store.migrate()
    with pytest.raises(RuntimeError, match="rollback"):
        with store.transaction() as tx:
            tx.execute("UPDATE governance_organization SET enrolled_at = now()")
            raise RuntimeError("rollback")
    with store.transaction() as tx:
        assert (
            tx.execute("SELECT enrolled_at FROM governance_organization").fetchone()["enrolled_at"]
            is None
        )


def test_bootstrap_revalidates_inputs_and_requires_review_authority(database):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.store import Store

    store = Store(database, ORG)
    store.migrate()
    pair = enrollments()
    pair[1].roles[:] = ["auditor"]
    with pytest.raises(GovernanceError, match="enrollment_invalid"):
        store.bootstrap(pair)
    pair = enrollments()
    pair[0].roles.append("invented_privilege")
    with pytest.raises(GovernanceError, match="enrollment_invalid"):
        store.bootstrap(pair)


def test_audit_is_append_only_and_chain_verification_detects_tampering(database):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.store import Store

    store = Store(database, ORG)
    store.migrate()
    store.bootstrap(enrollments())
    assert store.verify_audit()["events"] == 1
    with pytest.raises(GovernanceError, match="storage_failure"):
        with store.transaction() as tx:
            tx.execute("DELETE FROM governance_audit")
    with store.transaction() as tx:
        tx.execute("ALTER TABLE governance_audit DISABLE TRIGGER governance_audit_immutable")
        tx.execute("UPDATE governance_audit SET details = '{\"member_count\":3}'::jsonb")
        tx.execute("ALTER TABLE governance_audit ENABLE TRIGGER governance_audit_immutable")
    with pytest.raises(GovernanceError, match="audit_integrity_failure"):
        store.verify_audit()


def test_enrolled_organization_cannot_verify_a_missing_audit_history(database):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.store import Store

    store = Store(database, ORG)
    store.migrate()
    store.bootstrap(enrollments())
    with store.transaction() as tx:
        tx.execute("ALTER TABLE governance_audit DISABLE TRIGGER governance_audit_immutable")
        tx.execute("DELETE FROM governance_audit")
        tx.execute("ALTER TABLE governance_audit ENABLE TRIGGER governance_audit_immutable")
    with pytest.raises(GovernanceError, match="audit_integrity_failure"):
        store.verify_audit()
