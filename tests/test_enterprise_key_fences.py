"""Real key activation races and encrypted rights-delivery key coverage."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from app.enterprise.capabilities import ConfiguredKeyProvider
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.key_operations import activate_rotation, verify_keys
from tests import governance_helpers as fixtures
from tests import test_governance_rights as rights_fixtures

database = fixtures.database
context = fixtures.context
rights_context = rights_fixtures.rights_context


def keys(c, tmp_path, active, versions):
    filename = tmp_path / (active + ".key")
    filename.write_text(
        json.dumps(
            {
                "organization_id": str(c.store.organization_id),
                "active_version": active,
                "keys": [{"version": v, "key_hex": value.hex()} for v, value in versions.items()],
            }
        )
    )
    return ConfiguredKeyProvider(filename, c.store.organization_id)


def test_stale_concurrent_rotation_cannot_drop_an_intervening_current_key(
    context, tmp_path, monkeypatch
):
    from pii_redactor.governance.collections import Collection
    from tests.test_governance_collection import runtime

    c = context
    _collection, _evidence, _execution, bucket, _document = runtime(c)
    old = keys(c, tmp_path, "v1", {"v1": b"k" * 32})
    first = keys(c, tmp_path, "v2", {"v1": b"k" * 32, "v2": b"b" * 32})
    stale = keys(c, tmp_path, "v3", {"v1": b"k" * 32, "v3": b"c" * 32})
    with c.store.transaction() as tx:
        tx.execute("UPDATE governance_operations SET active_key_version='v1'")
    reached, release = threading.Event(), threading.Event()
    original_lock = c.store.lock

    def paused_lock(tx):
        if threading.current_thread().name.startswith("stale-key"):
            reached.set()
            assert release.wait(10)
        return original_lock(tx)

    monkeypatch.setattr(c.store, "lock", paused_lock)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="stale-key") as executor:
        pending = executor.submit(activate_rotation, c.store, old, stale)
        assert reached.wait(10)
        try:
            activate_rotation(c.store, old, first)
            with c.store.transaction() as tx:
                tx.execute("UPDATE governance_operations SET state='reconciled'")
            current = Collection(
                c.store, first, key_version="v2", consent_check=lambda *_a, **_k: True
            )
            current.put(c.a, uuid4(), bucket["id"], "Synthetic post-rotation document")
        finally:
            release.set()
        with pytest.raises(GovernanceError, match="key_rotation_conflict"):
            pending.result(timeout=10)
    with c.store.transaction() as tx:
        assert (
            tx.execute("SELECT active_key_version FROM governance_operations").fetchone()[
                "active_key_version"
            ]
            == "v2"
        )
    assert verify_keys(c.store, first)


def test_key_validation_covers_encrypted_rights_deliveries(rights_context, tmp_path):
    from pii_redactor.governance.delivery import Delivery
    from pii_redactor.governance.evidence import ProtectedStorage
    from tests.test_rights_delivery import issued

    c = rights_context
    _row, delivery = issued(c)
    full = keys(c, tmp_path, "v2", {"v1": b"k" * 32, "v2": b"b" * 32})
    old = keys(c, tmp_path, "v1", {"v1": b"k" * 32})
    with c.store.transaction() as tx:
        row = tx.execute(
            "SELECT * FROM governance_rights_deliveries WHERE delivery_id=%s", (delivery["id"],)
        ).fetchone()
        encrypted = ProtectedStorage(full).seal(
            c.store.organization_id,
            row["collection_id"],
            "v2",
            "Synthetic delivery",
            Delivery._context(row),
        )
        tx.execute(
            "UPDATE governance_rights_deliveries SET key_version=%s,nonce=%s,ciphertext=%s,ciphertext_digest=%s WHERE delivery_id=%s",
            (
                "v2",
                encrypted["nonce"],
                encrypted["ciphertext"],
                encrypted["ciphertext_digest"],
                row["delivery_id"],
            ),
        )
    with pytest.raises(GovernanceError, match="key_version_unavailable"):
        verify_keys(c.store, old)
    assert verify_keys(c.store, full)
