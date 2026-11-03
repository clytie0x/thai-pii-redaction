"""Independent Ed25519 witness contracts; synthetic loopback traffic only."""

import time
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from threading import Thread
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tests import governance_helpers as fixtures

context = fixtures.context
database = fixtures.database


@pytest.fixture
def witness(tmp_path):
    from pii_redactor.governance.checkpoints import Witness, witness_handler

    key = Ed25519PrivateKey.generate()
    authority = Witness(tmp_path / "witness.sqlite", key)
    server = ThreadingHTTPServer(("127.0.0.1", 0), witness_handler(authority, "synthetic-token"))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield authority, key.public_key(), f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def client(witness, org=None, **kwargs):
    from pii_redactor.governance.checkpoints import CheckpointClient

    return CheckpointClient(
        witness[2], "synthetic-token", witness[1], org or uuid4(), development=True, **kwargs
    )


def test_actual_http_signed_checkpoint_and_restart(witness):
    c = client(witness)
    c.publish(1, "a" * 64)
    receipt = c.fetch()
    assert receipt["sequence"] == 1
    assert c.verify_chain({1: "a" * 64}, receipt) is True
    # Separate client has no witness signing key, including after restart.
    assert not hasattr(c, "private_key")
    assert client(witness, c.organization_id).fetch()["event_hash"] == "a" * 64


def test_truncated_divergent_and_lagging_chain_fail(witness):
    c = client(witness, max_age=1, max_events=1)
    c.publish(1, "a" * 64)
    r = c.fetch()
    for chain in ({}, {1: "b" * 64}, {1: "a" * 64, 2: "b" * 64, 3: "c" * 64}):
        with pytest.raises(Exception, match="checkpoint_integrity_failure"):
            c.verify_chain(chain, r)
    r["checkpointed_at"] = time.time() - 2
    with pytest.raises(Exception, match="checkpoint_integrity_failure"):
        c.verify_chain({1: "a" * 64, 2: "b" * 64}, r)


def test_witness_denies_rewrite_race_and_bad_signature(witness):
    c = client(witness)
    c.publish(1, "a" * 64)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda h: _publish(c, h), ("b" * 64, "c" * 64)))
    assert sorted(results) == [False, True]
    bad = (witness[0], Ed25519PrivateKey.generate().public_key(), witness[2])
    with pytest.raises(Exception, match="checkpoint_unavailable"):
        client(bad, c.organization_id).fetch()


def _publish(c, h):
    try:
        c.publish(2, h, previous=(1, "a" * 64))
        return True
    except Exception:
        return False


def test_sink_unreachable_and_credentials_denied(witness):
    from pii_redactor.governance.checkpoints import CheckpointClient

    for url, token in ((witness[2], "wrong"), ("http://127.0.0.1:1", "synthetic-token")):
        c = CheckpointClient(url, token, witness[1], uuid4(), development=True)
        with pytest.raises(Exception, match="checkpoint_unavailable"):
            c.fetch()


def test_real_database_truncation_cannot_be_hidden_by_a_valid_local_chain(context, witness):
    from pii_redactor.governance.store import Store

    c = client(witness, context.store.organization_id)
    with context.store.transaction() as tx:
        context.store.append_event(tx, event_code="operations.synthetic_tail")
    c.check(context.store, publish=True)
    with context.store.transaction() as tx:
        tx.execute("ALTER TABLE governance_audit DISABLE TRIGGER governance_audit_immutable")
        tx.execute("DELETE FROM governance_audit WHERE sequence=2")
        tx.execute("ALTER TABLE governance_audit ENABLE TRIGGER governance_audit_immutable")
    assert Store(context.store._dsn, context.store.organization_id).verify_audit()["events"] == 1
    with pytest.raises(Exception, match="checkpoint_integrity_failure"):
        c.check(context.store)


def test_compromised_submitter_cannot_hide_rewritten_older_checkpoint(context, witness):
    from psycopg.types.json import Jsonb

    from pii_redactor.governance.store import _event_digest

    c = client(witness, context.store.organization_id)
    with context.store.transaction() as tx:
        context.store.append_event(tx, event_code="operations.synthetic_second")
    old = c.check(context.store, publish=True)
    with context.store.transaction() as tx:
        tx.execute("ALTER TABLE governance_audit DISABLE TRIGGER governance_audit_immutable")
        row = tx.execute("SELECT * FROM governance_audit WHERE sequence=2").fetchone()
        row["details"] = {"synthetic_rewrite": True}
        tx.execute(
            "UPDATE governance_audit SET details=%s,event_hash=%s WHERE sequence=2",
            (Jsonb(row["details"]), _event_digest(row)),
        )
        tx.execute("ALTER TABLE governance_audit ENABLE TRIGGER governance_audit_immutable")
        context.store.append_event(tx, event_code="operations.synthetic_third")
    local = context.store.verify_audit()
    # The attacker has submit credentials, but cannot delete witness history.
    c.publish(3, local["tail_hash"], previous=(old["sequence"], old["event_hash"]))
    with pytest.raises(Exception, match="checkpoint_integrity_failure"):
        c.check(context.store)
