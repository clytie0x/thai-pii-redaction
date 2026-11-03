"""Operator privacy, additive key history and readiness failure contracts."""

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from tests import governance_helpers as fixtures

context = fixtures.context
database = fixtures.database


def test_operator_errors_are_value_free_and_dsn_never_needed_on_argv(capsys, monkeypatch):
    from app.enterprise.operations import main

    monkeypatch.setenv("AIGUARD_ENTERPRISE_DB_FILE", "synthetic-secret-invalid-file")
    assert main(["keys-verify"]) == 1
    output = capsys.readouterr()
    assert "synthetic-secret" not in output.err + output.out


def test_witness_operator_error_never_echoes_private_file(capsys):
    from pii_redactor.governance.witness_operator import main

    assert main(["--config-file", "synthetic-private-witness-missing"]) == 1
    output = capsys.readouterr()
    assert output.err.strip() == "witness_operation_failed" and not output.out


def test_private_files_reject_broad_acl(tmp_path):
    from pii_redactor.governance.operator_files import require_private

    file = tmp_path / "synthetic.json"
    file.write_text("{}")
    if os.name == "nt":
        import subprocess

        subprocess.run(
            ["icacls", str(file), "/grant", "*S-1-1-0:R"], check=True, stdout=subprocess.DEVNULL
        )
    else:
        file.chmod(0o644)
    with pytest.raises(Exception, match="operator_file_unprotected"):
        require_private(file)


def test_versioned_key_rotation_loss_recovery_preserves_history_and_snapshots(context):
    from app.enterprise.capabilities import ConfiguredKeyProvider
    from pii_redactor.governance.evidence import ProtectedStorage
    from pii_redactor.governance.key_operations import (
        activate_rotation,
        prepare_rotation,
        verify_keys,
    )
    from pii_redactor.governance.operations import Operations
    from tests.test_governance_collection import runtime

    collection, _, _, bucket, _ = runtime(context)
    collection.snapshot(context.a, uuid4(), bucket["id"])
    with context.store.transaction() as tx:
        versions_before = tx.execute("SELECT * FROM governance_document_versions").fetchall()
        snapshots_before = tx.execute("SELECT * FROM governance_collection_snapshots").fetchall()

    root = Path(os.environ["AIGUARD_OPERATIONS_PRIVATE_DIR"])
    old_file, new_file = (root / (uuid4().hex + ".json") for _ in range(2))
    old_file.write_text(
        json.dumps(
            {
                "organization_id": str(context.store.organization_id),
                "active_version": "v1",
                "keys": [{"version": "v1", "key_hex": (b"k" * 32).hex()}],
            }
        )
    )
    old = ConfiguredKeyProvider(old_file, context.store.organization_id)
    crypto = ProtectedStorage(old)
    archived = crypto.seal(context.store.organization_id, None, "v1", "Synthetic history", {})
    assert prepare_rotation(old_file, new_file, version="v2")["retired_keys"] == 0
    new = ConfiguredKeyProvider(new_file, context.store.organization_id)
    before = context.store.verify_audit()
    assert activate_rotation(context.store, old, new)["state"] == "quarantined"
    assert context.store.verify_audit() != before
    assert verify_keys(context.store, new)
    with context.store.transaction() as tx:
        assert (
            tx.execute("SELECT * FROM governance_document_versions").fetchall() == versions_before
        )
        assert (
            tx.execute("SELECT * FROM governance_collection_snapshots").fetchall()
            == snapshots_before
        )
    assert (
        ProtectedStorage(new).open(context.store.organization_id, None, archived, {})
        == b"Synthetic history"
    )
    with pytest.raises(Exception, match="restore_quarantined"):
        Operations(context.store).require_reconciled()
    saved = new._keys.pop("v1")
    with pytest.raises(Exception, match="key_version_unavailable"):
        verify_keys(context.store, new)
    with pytest.raises(Exception, match="key_version_unavailable"):
        ProtectedStorage(new).open(context.store.organization_id, None, archived, {})
    new._keys["v1"] = saved
    assert (
        ProtectedStorage(new).open(context.store.organization_id, None, archived, {})
        == b"Synthetic history"
    )


def test_readiness_independently_reports_missing_profile_key_sink_restore(context):
    from pii_redactor.governance.operations import readiness

    report = readiness(context.store, None, None, None)
    assert report["status"] == "blocked"
    assert report["checks"]["database"] == "ready"
    assert report["checks"]["schema"] == "ready"
    assert report["checks"]["enrollment"] == "ready"
    for name in ("profile", "keys", "checkpoint", "restore"):
        assert report["checks"][name] == "blocked"


def test_runtime_database_fence_denies_quarantine_and_stale_key(context):
    from pii_redactor.governance.store import Store

    runtime = Store(context.store._dsn, context.store.organization_id)
    runtime.production_operations_required = True
    with pytest.raises(Exception, match="storage_failure"):
        with runtime.transaction() as tx:
            tx.execute("UPDATE governance_members SET revision=revision+1")
    with context.store.transaction() as tx:
        # Synthetic commissioning of the fence only, not recovery acceptance.
        tx.execute("UPDATE governance_operations SET state='reconciled',active_key_version='v2'")
    runtime.runtime_key_version = "v1"
    with pytest.raises(Exception, match="storage_failure"):
        with runtime.transaction() as tx:
            tx.execute("UPDATE governance_members SET revision=revision+1")
    runtime.runtime_key_version = "v2"
    with runtime.transaction() as tx:
        tx.execute("UPDATE governance_members SET revision=revision+1")


def test_real_application_and_worker_process_kill_before_and_after_commit(context):
    import signal
    import subprocess
    import sys
    import time

    from pii_redactor.governance.outbox import Outbox
    from tests.test_governance_execution import proposed

    _, _, execution, _, _, record = proposed(context)
    execution.approve(context.b, uuid4(), record["id"], 1)
    root = Path(os.environ["AIGUARD_OPERATIONS_PRIVATE_DIR"])
    config = root / (uuid4().hex + ".json")
    marker = root / (uuid4().hex + ".signal")
    config.write_text(
        json.dumps({"dsn": context.store._dsn, "organization": str(context.store.organization_id)})
    )
    code = """
import json,os,pathlib,threading
from uuid import UUID
from pii_redactor.governance.store import Store
from pii_redactor.governance.outbox import Outbox
c=json.loads(pathlib.Path(os.environ['OP_DRILL_CONFIG']).read_text())
s=Store(c['dsn'],UUID(c['organization']))
marker=pathlib.Path(os.environ['OP_DRILL_MARKER'])
if os.environ['OP_DRILL_MODE']=='before_commit':
    with s.transaction() as tx:
        s.append_event(tx,event_code='operations.synthetic_uncommitted')
        marker.write_text(str(os.getpid()))
        threading.Event().wait(60)
else:
    Outbox(s).claim('synthetic-killed-worker')
    marker.write_text(str(os.getpid()))
    threading.Event().wait(60)
"""
    before = context.store.verify_audit()
    for mode in ("before_commit", "after_commit"):
        process = subprocess.Popen(
            [sys.executable, "-c", code],
            env={
                **os.environ,
                "OP_DRILL_CONFIG": str(config),
                "OP_DRILL_MARKER": str(marker),
                "OP_DRILL_MODE": mode,
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 15
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            assert marker.exists(), "synthetic_child_not_ready"
            os.kill(int(marker.read_text()), signal.SIGTERM)
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            marker.unlink(missing_ok=True)
        if mode == "before_commit":
            assert context.store.verify_audit() == before
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_execution_tasks SET lease_until=clock_timestamp()-interval '1 second' WHERE state='running'"
        )
    assert Outbox(context.store).claim("synthetic-restarted-worker") is None
    with context.store.transaction() as tx:
        assert (
            tx.execute("SELECT state FROM governance_execution_tasks").fetchone()["state"]
            == "unknown"
        )
        assert (
            tx.execute("SELECT count(*) AS n FROM governance_execution_outcomes").fetchone()["n"]
            == 0
        )


def test_quarantine_serializes_with_running_runtime_transaction(context):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from pii_redactor.governance.operations import Operations
    from pii_redactor.governance.store import Store

    runtime = Store(context.store._dsn, context.store.organization_id)
    runtime.production_operations_required = True
    runtime.runtime_key_version = "v1"
    with context.store.transaction() as tx:
        tx.execute("UPDATE governance_operations SET state='reconciled',active_key_version='v1'")
    entered = Event()

    def quarantine():
        entered.set()
        Operations(context.store).quarantine(uuid4())

    with ThreadPoolExecutor(1) as pool:
        with runtime.transaction() as tx:
            tx.execute("UPDATE governance_members SET revision=revision+1")
            future = pool.submit(quarantine)
            assert entered.wait(2)
            assert not future.done()
        future.result(timeout=10)
    with pytest.raises(Exception, match="storage_failure"):
        with runtime.transaction() as tx:
            tx.execute("UPDATE governance_members SET revision=revision+1")
