"""Audit request bounds preserve oversized legacy rows without loading payloads."""

from pathlib import Path

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from pii_redactor.governance import store as store_module
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.operations import readiness
from pii_redactor.governance.store import Store
from tests import governance_helpers as fixtures
from tests import test_governance_store as foundation
from tests.test_audit_checkpoint import client
from tests.test_audit_checkpoint import witness as independent_witness

context = fixtures.context
database = fixtures.database
witness = independent_witness


def test_extension_byte_budget_fails_before_fetching_full_event_payloads(context, witness):
    store = context.store
    cp = client(witness, store.organization_id)
    receipt = cp.check(store, publish=True)
    verified = (receipt["sequence"], receipt["event_hash"])
    with store.transaction() as tx:
        store.lock(tx)
        for _ in range(270):
            store.append_event(
                tx, event_code="operations.synthetic_bounded", details={"synthetic": "x" * 4000}
            )
        latest = tx.execute(
            "SELECT sequence,event_hash FROM governance_audit ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
    cp.publish(latest["sequence"], latest["event_hash"], previous=verified)
    with pytest.raises(GovernanceError, match="checkpoint_extension_limit"):
        cp.check_extension(store, verified, receipt)


def test_oversized_legacy_metadata_survives_upgrade_but_blocks_full_qualification(
    database, tmp_path, monkeypatch
):
    old_package = tmp_path / "old_package"
    old_migrations = old_package / "migrations"
    old_migrations.mkdir(parents=True)
    source = Path(store_module.__file__).parent / "migrations"
    for path in sorted(source.glob("*.sql"))[:10]:
        (old_migrations / path.name).write_bytes(path.read_bytes())
    store = Store(database, foundation.ORG)
    with monkeypatch.context() as patch:
        patch.setattr(store_module, "files", lambda _package: old_package)
        store.migrate()
        store.bootstrap(foundation.enrollments())
        with store.transaction() as tx:
            store.append_event(
                tx, event_code="operations.synthetic_legacy", details={"synthetic": "x" * 5000}
            )
    with store.transaction() as tx:
        before = tx.execute(
            "SELECT sequence,event_hash FROM governance_audit ORDER BY sequence"
        ).fetchall()
    store.migrate()
    scans = []

    def forbidden_scan():
        scans.append(True)
        raise AssertionError("Oversized legacy payload must not be loaded")

    monkeypatch.setattr(store, "verify_audit", forbidden_scan)
    report = readiness(store, None, None, None)
    assert report["checks"].get("audit_metadata") == "blocked"
    assert scans == []
    with store.transaction() as tx:
        assert (
            tx.execute(
                "SELECT sequence,event_hash FROM governance_audit ORDER BY sequence"
            ).fetchall()
            == before
        )


@pytest.mark.parametrize("field", ["details", "event_code"])
def test_new_oversized_audit_metadata_is_rejected_atomically(context, field):
    with context.store.transaction() as tx:
        count = tx.execute("SELECT count(*) AS n FROM governance_audit").fetchone()["n"]
    with pytest.raises(GovernanceError, match="storage_failure"):
        with context.store.transaction() as tx:
            context.store.append_event(
                tx,
                event_code="x" * 129 if field == "event_code" else "operations.synthetic_limit",
                details={"synthetic": "x" * 4096} if field == "details" else {},
            )
    with context.store.transaction() as tx:
        assert tx.execute("SELECT count(*) AS n FROM governance_audit").fetchone()["n"] == count
