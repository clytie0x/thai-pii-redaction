"""Populated upgrades, concurrent migration and interruption use real PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from pii_redactor.governance import store as store_module
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.store import Store
from tests import test_governance_store as fixtures

database = fixtures.database
ROOT = Path(__file__).resolve().parents[1]


def old_schema(database, tmp_path, monkeypatch):
    package = tmp_path / "old-package"
    migrations = package / "migrations"
    migrations.mkdir(parents=True)
    for name in ["001_foundation.sql", "002_registry.sql"]:
        (migrations / name).write_bytes(
            (ROOT / "pii_redactor/governance/migrations" / name).read_bytes()
        )
    store = Store(database, fixtures.ORG)
    with monkeypatch.context() as patch:
        patch.setattr(store_module, "files", lambda _package: package)
        store.migrate()
        store.bootstrap(fixtures.enrollments())
    return store, package


def test_populated_version_two_upgrades_without_losing_authority(database, tmp_path, monkeypatch):
    store, _package = old_schema(database, tmp_path, monkeypatch)
    before = store.verify_audit()
    store.migrate()
    assert store.check_ready() == 6 and store.verify_audit() == before
    with store.transaction() as tx:
        assert tx.execute("SELECT count(*) AS n FROM governance_members").fetchone()["n"] == 2
        assert (
            tx.execute("SELECT count(*) AS n FROM enterprise_staff_sessions").fetchone()["n"] == 0
        )


def test_two_migrators_publish_one_complete_schema(database):
    stores = [Store(database, fixtures.ORG), Store(database, fixtures.ORG)]
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda s: s.migrate(), stores))
    with stores[0].transaction() as tx:
        assert tx.execute("SELECT count(*) AS n FROM governance_schema").fetchone()["n"] == 6
        assert tx.execute("SELECT count(*) AS n FROM governance_organization").fetchone()["n"] == 1


def test_failed_upgrade_rolls_back_new_ddl_and_preserves_existing_data(
    database, tmp_path, monkeypatch
):
    store, package = old_schema(database, tmp_path, monkeypatch)
    (package / "migrations/003_failure.sql").write_text(
        "CREATE TABLE incomplete_upgrade(id integer); SELECT 1/0;", encoding="utf-8"
    )
    before = store.verify_audit()
    with monkeypatch.context() as patch:
        patch.setattr(store_module, "files", lambda _package: package)
        with pytest.raises(GovernanceError, match="^storage_failure$"):
            store.migrate()
    assert store.verify_audit() == before
    with store.transaction() as tx:
        assert tx.execute("SELECT count(*) AS n FROM governance_schema").fetchone()["n"] == 2
        assert (
            tx.execute("SELECT to_regclass('incomplete_upgrade') AS relation").fetchone()[
                "relation"
            ]
            is None
        )
        assert tx.execute("SELECT count(*) AS n FROM governance_members").fetchone()["n"] == 2
    store.migrate()
    assert store.check_ready() == 6
