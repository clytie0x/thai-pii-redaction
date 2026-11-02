"""Synthetic protected-storage contracts; database checks are run separately."""

import importlib
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from tests import governance_helpers as fixtures

context = fixtures.context
database = fixtures.database


def module(name):
    path = "pii_redactor.governance." + name
    assert importlib.util.find_spec(path) is not None, "managed storage is not implemented"
    return importlib.import_module(path)


def test_encrypted_envelope_round_trip_and_target_binding():
    crypto = module("evidence")
    organization, collection = uuid4(), uuid4()
    provider = crypto.SyntheticKeyProvider({(organization, collection, "v1"): b"k" * 32})
    cipher = crypto.ProtectedStorage(provider)
    context = {"organization": str(organization), "collection": str(collection), "version": 1}
    envelope = cipher.seal(organization, collection, "v1", b"Synthetic document", context)
    assert b"Synthetic document" not in envelope["ciphertext"]
    assert cipher.open(organization, collection, envelope, context) == b"Synthetic document"
    with pytest.raises(Exception, match="^protected_content_invalid$"):
        cipher.open(organization, collection, envelope, {**context, "version": 2})


def test_tampering_and_key_service_failure_have_value_free_errors():
    crypto = module("evidence")
    organization, collection = uuid4(), uuid4()
    cipher = crypto.ProtectedStorage(
        crypto.SyntheticKeyProvider({(organization, collection, "v1"): b"k" * 32})
    )
    envelope = cipher.seal(organization, collection, "v1", b"Synthetic secret", {})
    broken = {**envelope, "ciphertext": envelope["ciphertext"][:-1] + b"\x00"}
    with pytest.raises(Exception, match="^protected_content_invalid$"):
        cipher.open(organization, collection, broken, {})
    missing = crypto.ProtectedStorage(None)
    with pytest.raises(Exception, match="^key_service_unavailable$"):
        missing.seal(organization, collection, "v1", b"Synthetic secret", {})
    with pytest.raises(Exception, match="^key_version_unavailable$"):
        cipher.seal(organization, collection, "missing", b"Synthetic secret", {})


@pytest.mark.parametrize("key", [b"", b"x" * 16, "not-a-key", None])
def test_invalid_keys_never_fall_back_to_plaintext(key):
    crypto = module("evidence")
    organization, collection = uuid4(), uuid4()
    with pytest.raises(Exception, match="^key_configuration_invalid$"):
        crypto.SyntheticKeyProvider({(organization, collection, "v1"): key})


@pytest.mark.parametrize("content_type", ["text/html", "application/javascript", "image/svg+xml"])
def test_protected_evidence_accepts_only_bounded_passive_content(content_type):
    from pydantic import ValidationError

    evidence = module("evidence")
    with pytest.raises(ValidationError):
        evidence.EvidenceInput(
            collection_id=uuid4(), content_type=content_type, content="synthetic"
        )


def test_collection_request_rejects_caller_connector_targets():
    from pydantic import ValidationError

    storage = module("collections")
    for field in ("url", "sql", "path", "key", "key_version"):
        with pytest.raises(ValidationError):
            storage.CollectionInput(
                activity_id=uuid4(), expected_activity_revision=1, **{field: "x"}
            )


def test_envelope_nonce_is_unique_for_identical_content():
    crypto = module("evidence")
    organization, collection = uuid4(), uuid4()
    cipher = crypto.ProtectedStorage(
        crypto.SyntheticKeyProvider({(organization, collection, "v1"): b"k" * 32})
    )
    one = cipher.seal(organization, collection, "v1", b"Synthetic document", {})
    two = cipher.seal(organization, collection, "v1", b"Synthetic document", {})
    assert one["nonce"] != two["nonce"] and one["ciphertext"] != two["ciphertext"]


def test_ciphertext_cannot_be_relabelled_as_another_existing_key_version():
    crypto = module("evidence")
    organization, collection = uuid4(), uuid4()
    cipher = crypto.ProtectedStorage(
        crypto.SyntheticKeyProvider(
            {
                (organization, collection, "v1"): b"k" * 32,
                (organization, collection, "v2"): b"k" * 32,
            }
        )
    )
    envelope = cipher.seal(organization, collection, "v1", b"Synthetic document", {})
    with pytest.raises(Exception, match="^protected_content_invalid$"):
        cipher.open(organization, collection, {**envelope, "key_version": "v2"}, {})


def test_evidence_size_limit_is_utf8_bytes_and_json_is_passive_data():
    crypto = module("evidence")
    with pytest.raises(Exception, match="^content_invalid$"):
        crypto.validate_content("ก" * 12000)
    with pytest.raises(Exception, match="^content_invalid$"):
        crypto.validate_content("not-json", "application/json")
    assert crypto.validate_content('{"synthetic":true}', "application/json")


def test_missing_consent_checker_fails_closed_without_database(monkeypatch):
    storage = module("collections")
    collection = storage.Collection(type("Store", (), {"organization_id": uuid4()})(), None)
    fenced = []
    monkeypatch.setattr(
        collection, "_hold_fence", lambda _tx, _row, _doc, action: fenced.append(action)
    )
    with pytest.raises(Exception, match="^consent_authority_unavailable$"):
        collection.check_consent(None, {"consent_bound": True}, None, "read")
    assert collection.check_consent(None, {"consent_bound": False}, None, "read") is None
    assert fenced == ["read", "read"]


@pytest.mark.parametrize("result", [False, None, 1, "allow", {"allowed": True}])
def test_consent_callback_requires_literal_true(result, monkeypatch):
    storage = module("collections")
    collection = storage.Collection(
        type("Store", (), {"organization_id": uuid4()})(),
        None,
        consent_check=lambda *args, **kwargs: result,
    )
    fenced = []
    monkeypatch.setattr(
        collection, "_hold_fence", lambda _tx, _row, _doc, action: fenced.append(action)
    )
    with pytest.raises(Exception, match="^consent_required$"):
        collection.check_consent(None, {"consent_bound": True}, None, "read")
    assert fenced == ["read"]


def runtime(context):
    from pii_redactor.governance.collections import Collection, CollectionInput
    from pii_redactor.governance.evidence import Evidence, SyntheticKeyProvider
    from pii_redactor.governance.execution import Execution
    from pii_redactor.governance.registry import Registry, ReviewInput
    from tests.test_governance_registry import activity, evidence, published_notice

    registry = Registry(context.store)
    record = registry.create_activity(context.a, uuid4(), activity())
    notice = published_notice(registry, context, record)
    submitted = registry.submit_activity(context.a, uuid4(), record["id"], record["revision"])
    active = registry.review_activity(
        context.b,
        uuid4(),
        record["id"],
        submitted["revision"],
        ReviewInput(
            decision="approve",
            reason="Synthetic review is complete.",
            notice_id=notice["id"],
            evidence=evidence(),
        ),
    )
    provider = SyntheticKeyProvider({(context.store.organization_id, None, "v1"): b"k" * 32})
    collection = Collection(context.store, provider)
    evidence_store = Evidence(context.store, provider, collection=collection)
    execution = Execution(context.store, collection, evidence_store)
    bucket = collection.create(
        context.a,
        uuid4(),
        CollectionInput(activity_id=active["id"], expected_activity_revision=active["revision"]),
    )
    document = collection.put(context.a, uuid4(), bucket["id"], "Synthetic source document")
    return collection, evidence_store, execution, bucket, document


def test_database_encrypted_content_scoped_read_and_restart(context):
    collection, _, _, bucket, document = runtime(context)
    assert (
        collection.read_version(context.a, bucket["id"], document["id"], 1)["content"]
        == "Synthetic source document"
    )
    with pytest.raises(Exception, match="^record_unavailable$"):
        collection.read_version(context.c, bucket["id"], document["id"], 1)
    with context.store.transaction() as tx:
        row = tx.execute(
            "SELECT ciphertext,key_version FROM governance_document_versions"
        ).fetchone()
        assert b"Synthetic source document" not in bytes(row["ciphertext"])
        assert row["key_version"] == "v1"
    from pii_redactor.governance.collections import Collection

    restarted = Collection(context.store, collection.protection.key_provider)
    assert (
        restarted.read_version(context.b, bucket["id"], document["id"], 1)["content"]
        == "Synthetic source document"
    )


def test_database_put_idempotency_and_outbox_failure_are_atomic(context):
    collection, _, _, bucket, _ = runtime(context)
    key = uuid4()
    first = collection.put(context.a, key, bucket["id"], "Synthetic second document")
    assert collection.put(context.a, key, bucket["id"], "Synthetic second document") == first
    with pytest.raises(Exception, match="^idempotency_conflict$"):
        collection.put(context.a, key, bucket["id"], "Synthetic changed content")
    with context.store.transaction() as tx:
        before = tx.execute("SELECT count(*) AS n FROM governance_managed_documents").fetchone()[
            "n"
        ]
        tx.execute("""CREATE FUNCTION refuse_managed_outbox() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic_outbox_failure'; END $$;
            CREATE TRIGGER refuse_managed_outbox BEFORE INSERT ON governance_outbox
            FOR EACH ROW EXECUTE FUNCTION refuse_managed_outbox();""")
    with pytest.raises(Exception, match="^storage_failure$"):
        collection.put(context.a, uuid4(), bucket["id"], "Synthetic rolled back document")
    with context.store.transaction() as tx:
        assert (
            tx.execute("SELECT count(*) AS n FROM governance_managed_documents").fetchone()["n"]
            == before
        )


def test_database_missing_key_and_unauthorized_evidence_reference(context):
    from pii_redactor.governance.collections import Collection
    from pii_redactor.governance.evidence import EvidenceInput

    collection, evidence, _, bucket, document = runtime(context)
    protected = evidence.put(
        context.a,
        uuid4(),
        EvidenceInput(
            collection_id=bucket["id"],
            document_id=document["id"],
            expected_version=1,
            content="Synthetic correction",
        ),
    )
    with pytest.raises(Exception, match="^record_unavailable$"):
        evidence.read(context.c, protected["id"])
    with pytest.raises(Exception, match="^key_service_unavailable$"):
        Collection(context.store, None).read_version(context.a, bucket["id"], document["id"], 1)
    with context.store.transaction() as tx:
        member = tx.execute(
            "SELECT * FROM governance_members WHERE member_id=%s", (context.ids[0],)
        ).fetchone()
        with pytest.raises(Exception, match="^evidence_unavailable$"):
            evidence.resolve(
                tx,
                member,
                protected["id"],
                collection_id=bucket["id"],
                document_id=uuid4(),
                version=1,
            )
