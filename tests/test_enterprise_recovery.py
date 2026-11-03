"""Authenticated bounded backup format and fail-closed operator contracts."""

import io
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from tests.test_audit_checkpoint import witness as checkpoint_witness

witness = checkpoint_witness


@pytest.fixture
def whole_database():
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    from pii_redactor.governance.store import Store
    from tests.test_governance_store import ORG, enrollments

    config = json.loads(Path(os.environ["AIGUARD_TEST_DB_FILE"]).read_text())
    name = "aig_restore_" + uuid4().hex
    dsn = make_conninfo(config["dsn"], dbname=name)
    with psycopg.connect(config["dsn"], autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    store = Store(dsn, ORG)
    store.migrate()
    store.bootstrap(enrollments())
    yield store, config["dsn"]
    with psycopg.connect(config["dsn"], autocommit=True) as admin:
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def test_real_postgres_whole_database_backup_restore_quarantine_and_readonly_validation(
    whole_database, witness
):
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    from pii_redactor.governance.backup import backup_database, restore_database, validate_archive
    from pii_redactor.governance.operations import Operations
    from pii_redactor.governance.store import Store
    from tests.test_audit_checkpoint import client

    store, admin_dsn = whole_database
    checkpoint = client(witness, store.organization_id)
    checkpoint.check(store, publish=True)
    archive = Path(os.environ["AIGUARD_OPERATIONS_PRIVATE_DIR"]) / (uuid4().hex + ".aigdb")
    binary = os.environ["AIGUARD_OPERATIONS_PG_BIN"]
    key = os.urandom(32)
    before = store.verify_audit()
    assert (
        backup_database(store, binary, archive, key, checkpoint=checkpoint)["state"] == "validated"
    )
    assert validate_archive(archive, key)["organization"] == str(store.organization_id)
    assert store.verify_audit() == before
    target = "aig_restore_" + uuid4().hex
    try:
        assert (
            restore_database(admin_dsn, binary, archive, key, name=target, confirmation=target)[
                "state"
            ]
            == "quarantined"
        )
        restored = Store(make_conninfo(admin_dsn, dbname=target), store.organization_id)
        restored.check_ready()
        with pytest.raises(Exception, match="restore_quarantined"):
            Operations(restored).require_reconciled()
        with restored.transaction() as tx:
            assert tx.execute("SELECT count(*) AS n FROM governance_members").fetchone()["n"] == 2
        with pytest.raises(Exception, match="restore_target_exists"):
            restore_database(admin_dsn, binary, archive, key, name=target, confirmation=target)
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(target))
            )


def test_real_database_connection_kill_rolls_back_uncommitted_but_preserves_commit(whole_database):
    import psycopg

    store, admin_dsn = whole_database
    baseline = store.verify_audit()
    db = psycopg.connect(store._dsn)
    pid = db.info.backend_pid
    db.execute("UPDATE governance_organization SET enrolled_at=NULL")
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("SELECT pg_terminate_backend(%s)", (pid,))
    db.close()
    assert store.check_ready()
    assert store.verify_audit() == baseline
    with store.transaction() as tx:
        store.append_event(tx, event_code="operations.synthetic_commit")
    restarted = type(store)(store._dsn, store.organization_id)
    assert restarted.verify_audit() != baseline


def test_old_binary_refuses_new_schema_without_downgrade(whole_database, monkeypatch, tmp_path):
    import pii_redactor.governance.store as module

    store, _ = whole_database
    package = tmp_path / "old"
    (package / "migrations").mkdir(parents=True)
    source = Path(module.__file__).parent / "migrations"
    for file in sorted(source.glob("*.sql"))[:-1]:
        (package / "migrations" / file.name).write_bytes(file.read_bytes())
    before = store.verify_audit()
    monkeypatch.setattr(module, "files", lambda _: package)
    with pytest.raises(Exception, match="migration_mismatch"):
        store.check_ready()
    with pytest.raises(Exception, match="migration_mismatch"):
        store.migrate()
    assert store.verify_audit() == before


def test_stream_backup_is_encrypted_bound_to_manifest_and_detects_truncation():
    from pii_redactor.governance.backup import open_stream, seal_stream

    key = os.urandom(32)
    raw = b"Synthetic database payload" * 10000
    output = io.BytesIO()
    seal_stream(io.BytesIO(raw), output, key, {"schema": "synthetic"})
    encrypted = output.getvalue()
    assert b"Synthetic database payload" not in encrypted
    restored = io.BytesIO()
    assert open_stream(io.BytesIO(encrypted), restored, key) == {"schema": "synthetic"}
    assert restored.getvalue() == raw
    for bad in (
        encrypted[:-1],
        encrypted + b"x",
        encrypted[:100] + bytes([encrypted[100] ^ 1]) + encrypted[101:],
    ):
        with pytest.raises(Exception, match="backup_integrity_failure"):
            open_stream(io.BytesIO(bad), io.BytesIO(), key)
    with pytest.raises(Exception, match="backup_integrity_failure"):
        open_stream(io.BytesIO(encrypted), io.BytesIO(), os.urandom(32))


def test_disk_failure_never_returns_a_valid_backup():
    from pii_redactor.governance.backup import seal_stream

    class FullDisk(io.BytesIO):
        def write(self, value):
            raise OSError("synthetic disk full")

    with pytest.raises(Exception, match="backup_io_failure"):
        seal_stream(io.BytesIO(b"synthetic"), FullDisk(), os.urandom(32), {})


def test_failed_dump_cannot_leave_an_authenticated_complete_archive():
    from pii_redactor.governance.backup import DumpReader, open_stream, seal_stream

    class FailedDump:
        stdout = io.BytesIO(b"synthetic partial dump")

        def wait(self, **_kwargs):
            return 1

    output, key = io.BytesIO(), os.urandom(32)
    with pytest.raises(Exception, match="backup_integrity_failure"):
        seal_stream(DumpReader(FailedDump()), output, key, {})
    with pytest.raises(Exception, match="backup_integrity_failure"):
        open_stream(io.BytesIO(output.getvalue()), io.BytesIO(), key)


def test_restore_cannot_select_existing_or_owner_target():
    from pii_redactor.governance.backup import validate_target

    for name in ("postgres", "owner", "aig_restore_x", "aig_restore_" + "a" * 32):
        with pytest.raises(Exception, match="restore_target_invalid"):
            validate_target(name, confirmation="wrong")
