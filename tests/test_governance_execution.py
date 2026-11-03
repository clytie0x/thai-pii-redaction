"""Exact approved instruction contracts; no remote targets or destructive mode."""

import importlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from tests import governance_helpers as fixtures

context = fixtures.context
database = fixtures.database


def execution_module():
    path = "pii_redactor.governance.execution"
    assert importlib.util.find_spec(path) is not None, "execution boundary is not implemented"
    return importlib.import_module(path)


def instruction(**changes):
    return {
        "collection_id": uuid4(),
        "document_id": uuid4(),
        "expected_revision": 1,
        "expected_version": 1,
        "action": "restrict",
        "expires_at": datetime.now(UTC) + timedelta(minutes=10),
        **changes,
    }


@pytest.mark.parametrize("action", ["delete", "erase", "execute_sql", "fetch_url", "restore"])
def test_destructive_and_arbitrary_actions_are_disabled(action):
    from pydantic import ValidationError

    module = execution_module()
    with pytest.raises(ValidationError):
        module.InstructionInput(**instruction(action=action))


def test_correction_requires_exact_protected_evidence_reference():
    from pydantic import ValidationError

    module = execution_module()
    with pytest.raises(ValidationError):
        module.InstructionInput(**instruction(action="correct"))
    assert module.InstructionInput(**instruction(action="correct", evidence_id=uuid4()))
    with pytest.raises(ValidationError):
        module.InstructionInput(**instruction(action="restrict", evidence_id=uuid4()))


def test_naive_or_expired_or_unbounded_expiry_is_rejected():
    from pydantic import ValidationError

    module = execution_module()
    for expiry in (
        datetime.now(),
        datetime.now(UTC) - timedelta(seconds=1),
        datetime.now(UTC) + timedelta(days=2),
    ):
        with pytest.raises(ValidationError):
            module.InstructionInput(**instruction(expires_at=expiry))


def test_target_substitution_fields_are_rejected():
    from pydantic import ValidationError

    module = execution_module()
    for field in ("path", "url", "sql", "connector", "approved_by", "allow_destructive"):
        with pytest.raises(ValidationError):
            module.InstructionInput(**instruction(**{field: "synthetic"}))


def test_fixed_instruction_fingerprint_binds_every_execution_field():
    module = execution_module()
    source = module.InstructionInput(**instruction())
    base = module.instruction_digest(source)
    for change in (
        {"document_id": uuid4()},
        {"expected_version": 2},
        {"expected_revision": 2},
        {"action": "suppress"},
    ):
        assert module.instruction_digest(source.model_copy(update=change)) != base


def test_instruction_fingerprint_is_stable_across_database_round_trip():
    module = execution_module()
    source = module.InstructionInput(**instruction())
    row = {
        "collection_id": source.collection_id,
        "document_id": source.document_id,
        "target_revision": source.expected_revision,
        "target_version": source.expected_version,
        "action": source.action,
        "expires_at": source.expires_at,
        "evidence_id": source.evidence_id,
    }
    assert module.instruction_digest(source) == module.instruction_digest(row)


def test_connector_rejects_target_substitution_before_any_primary_query():
    from pii_redactor.governance.connectors.managed_documents import ManagedDocuments

    collection_id, document_id = uuid4(), uuid4()
    target = {
        "document_id": document_id,
        "collection_id": collection_id,
        "revision": 1,
        "current_version": 1,
    }
    approved = {
        "collection_id": collection_id,
        "document_id": uuid4(),
        "target_revision": 1,
        "target_version": 1,
    }
    with pytest.raises(Exception, match="^target_substitution_denied$"):
        ManagedDocuments(None, None).apply(
            None, {"collection_id": collection_id}, target, approved, None
        )


def test_managed_router_requires_bff_identity_for_reads_and_csrf_for_mutations():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.enterprise.managed_routes import build_managed_router
    from pii_redactor.governance.errors import GovernanceError

    calls = []

    def identity(request, *, mutation=False):
        calls.append(mutation)
        raise GovernanceError("forbidden")

    class Service:
        def list(self, *_args):
            raise AssertionError("unauthorized domain access")

        def propose(self, *_args):
            raise AssertionError("unauthorized domain mutation")

    app = FastAPI()
    app.include_router(build_managed_router(Service(), Service(), Service(), identity))
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/api/enterprise/v1/managed/collections").status_code == 500
    assert calls == [False]
    response = client.post(
        "/api/enterprise/v1/managed/instructions",
        json={
            "command_key": str(uuid4()),
            "data": {
                **instruction(),
                "collection_id": str(uuid4()),
                "document_id": str(uuid4()),
                "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            },
        },
    )
    assert response.status_code == 500
    assert calls == [False, True]


def proposed(context, *, action="restrict", evidence_id=None, expiry=None):
    from tests.test_governance_collection import runtime

    collection, evidence, execution, bucket, document = runtime(context)
    record = execution.propose(
        context.a,
        uuid4(),
        execution_module().InstructionInput(
            **instruction(
                collection_id=bucket["id"],
                document_id=document["id"],
                action=action,
                evidence_id=evidence_id,
                expires_at=expiry or datetime.now(UTC) + timedelta(minutes=5),
            )
        ),
    )
    return collection, evidence, execution, bucket, document, record


def test_database_independent_approval_and_one_primary_outcome(context):
    from app.enterprise.worker import Worker
    from pii_redactor.governance.outbox import Outbox

    collection, _, execution, bucket, document, record = proposed(context)
    with pytest.raises(Exception, match="^separation_required$"):
        execution.approve(context.a, uuid4(), record["id"], 1)
    approved = execution.approve(context.b, uuid4(), record["id"], 1)
    assert approved["state"] == "pending" and not approved["primary_verified"]
    queue = Outbox(context.store)
    task = queue.claim("synthetic-worker")
    result = execution.execute("synthetic-worker", task)
    assert (
        result["state"] == "verified"
        and result["primary_verified"]
        and not result["overall_erasure_verified"]
    )
    with pytest.raises(Exception, match="^lease_lost$"):
        execution.execute("synthetic-worker", task)
    assert Worker(execution, queue).run_once("synthetic-worker")["state"] == "idle"
    with context.store.transaction() as tx:
        assert (
            tx.execute("SELECT count(*) AS n FROM governance_execution_outcomes").fetchone()["n"]
            == 1
        )
    with pytest.raises(Exception, match="^record_restricted$"):
        collection.read_version(context.a, bucket["id"], document["id"], 1)


def test_database_revoked_approver_blocks_mutation(context):
    from app.enterprise.worker import Worker
    from pii_redactor.governance.outbox import Outbox

    collection, _, execution, bucket, document, record = proposed(context)
    execution.approve(context.b, uuid4(), record["id"], 1)
    with context.store.transaction() as tx:
        context.store.lock(tx)
        tx.execute(
            "UPDATE governance_members SET enabled=false,revision=revision+1 WHERE member_id=%s",
            (context.ids[1],),
        )
    result = Worker(execution, Outbox(context.store)).run_once("synthetic-worker")
    assert result["state"] == "failed" and result["error_code"] == "approval_authority_changed"
    assert collection.read_version(context.a, bucket["id"], document["id"], 1)["state"] == "active"


def test_database_expired_approval_cannot_execute(context):
    import time

    from app.enterprise.worker import Worker
    from pii_redactor.governance.outbox import Outbox

    collection, _, execution, bucket, document, record = proposed(
        context, expiry=datetime.now(UTC) + timedelta(seconds=2)
    )
    execution.approve(context.b, uuid4(), record["id"], 1)
    time.sleep(2.05)
    result = Worker(execution, Outbox(context.store)).run_once("synthetic-worker")
    assert result["state"] == "failed" and result["error_code"] == "approval_expired"
    assert collection.read_version(context.a, bucket["id"], document["id"], 1)["state"] == "active"


def test_database_exact_target_and_immutable_instruction(context):
    _, _, execution, _, _, record = proposed(context)
    execution.approve(context.b, uuid4(), record["id"], 1)
    with pytest.raises(Exception, match="^storage_failure$"):
        with context.store.transaction() as tx:
            tx.execute(
                "UPDATE governance_execution_instructions SET document_id=%s WHERE instruction_id=%s",
                (uuid4(), record["id"]),
            )


def test_database_correction_creates_protected_version_and_restore_reapplies_restriction(context):
    from app.enterprise.worker import Worker
    from pii_redactor.governance.evidence import EvidenceInput
    from pii_redactor.governance.outbox import Outbox
    from tests.test_governance_collection import runtime

    collection, evidence, execution, bucket, document = runtime(context)
    snapshot = collection.snapshot(context.a, uuid4(), bucket["id"])
    replacement = evidence.put(
        context.a,
        uuid4(),
        EvidenceInput(
            collection_id=bucket["id"],
            document_id=document["id"],
            expected_version=1,
            content="Synthetic corrected document",
        ),
    )
    record = execution.propose(
        context.a,
        uuid4(),
        execution_module().InstructionInput(
            **instruction(
                collection_id=bucket["id"],
                document_id=document["id"],
                action="correct",
                evidence_id=replacement["id"],
            )
        ),
    )
    execution.approve(context.b, uuid4(), record["id"], 1)
    assert (
        Worker(execution, Outbox(context.store)).run_once("synthetic-worker")["state"] == "verified"
    )
    corrected = collection.read_version(context.a, bucket["id"], document["id"], 2)
    assert corrected["content"] == "Synthetic corrected document"
    with pytest.raises(Exception, match="^version_unavailable$"):
        collection.read_version(context.a, bucket["id"], document["id"], 1)
    restrict = execution.propose(
        context.a,
        uuid4(),
        execution_module().InstructionInput(
            **instruction(
                collection_id=bucket["id"],
                document_id=document["id"],
                expected_revision=corrected["revision"],
                expected_version=2,
            )
        ),
    )
    execution.approve(context.b, uuid4(), restrict["id"], 1)
    assert (
        Worker(execution, Outbox(context.store)).run_once("synthetic-worker")["state"] == "verified"
    )
    restored = collection.restore_quarantine(context.a, uuid4(), snapshot["id"], 1)
    with pytest.raises(Exception, match="^restore_quarantined$"):
        collection.read_version(context.a, bucket["id"], document["id"], 1)
    with pytest.raises(Exception, match="^restore_quarantined$"):
        collection.check_ready()
    with pytest.raises(Exception, match="^separation_required$"):
        collection.reconcile_restore(context.a, uuid4(), snapshot["id"], restored["revision"])
    reconciled = collection.reconcile_restore(
        context.b, uuid4(), snapshot["id"], restored["revision"]
    )
    assert reconciled["state"] == "reconciled"
    with pytest.raises(Exception, match="^record_restricted$"):
        collection.read_version(context.a, bucket["id"], document["id"], 2)


@pytest.mark.parametrize("state", ["restricted", "suppressed"])
def test_database_independent_reviewer_can_preview_only_exact_replacement_for_restricted_target(
    context, state, monkeypatch
):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.evidence import EvidenceInput
    from tests.test_governance_collection import runtime

    collection, evidence, execution, bucket, document = runtime(context)
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_managed_documents SET state=%s WHERE document_id=%s",
            (state, document["id"]),
        )
    replacement = evidence.put(
        context.a,
        uuid4(),
        EvidenceInput(
            collection_id=bucket["id"],
            document_id=document["id"],
            expected_version=1,
            content="Synthetic protected replacement",
        ),
    )
    record = execution.propose(
        context.a,
        uuid4(),
        execution_module().InstructionInput(
            **instruction(
                collection_id=bucket["id"],
                document_id=document["id"],
                action="correct",
                evidence_id=replacement["id"],
            )
        ),
    )
    for principal in (context.a, context.b):
        with pytest.raises(Exception, match="^record_restricted$"):
            evidence.read(principal, replacement["id"])
        with pytest.raises(Exception, match="^record_restricted$"):
            collection.read_version(principal, bucket["id"], document["id"], 1)
    assert callable(getattr(execution, "preview_evidence", None)), (
        "exact reviewer preview is not implemented"
    )
    viewed = execution.preview_evidence(context.b, record["id"], 1)
    assert viewed["content"] == "Synthetic protected replacement"
    assert viewed["instruction_id"] == record["id"] and viewed["id"] == replacement["id"]
    with pytest.raises(Exception, match="^separation_required$"):
        execution.preview_evidence(context.a, record["id"], 1)
    with pytest.raises(Exception, match="^forbidden$"):
        execution.preview_evidence(context.c, record["id"], 1)
    with pytest.raises(Exception, match="^revision_conflict$"):
        execution.preview_evidence(context.b, record["id"], 2)
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET roles='[\"privacy_reviewer\"]'::jsonb,revision=revision+1 WHERE member_id=%s",
            (context.ids[2],),
        )
    with pytest.raises(Exception, match="^record_unavailable$"):
        execution.preview_evidence(context.c, record["id"], 1)
    original_check = collection.check_consent

    def withdrawn(tx, bucket, target, action):
        if action == "preview":
            raise GovernanceError("consent_required")
        return original_check(tx, bucket, target, action)

    with monkeypatch.context() as patch:
        patch.setattr(collection, "check_consent", withdrawn)
        with pytest.raises(Exception, match="^consent_required$"):
            execution.preview_evidence(context.b, record["id"], 1)
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_managed_documents SET revision=revision+1 WHERE document_id=%s",
            (document["id"],),
        )
    with pytest.raises(Exception, match="^revision_conflict$"):
        execution.preview_evidence(context.b, record["id"], 1)


def test_database_expired_correction_preview_does_not_expose_replacement(context):
    import time

    from pii_redactor.governance.evidence import EvidenceInput
    from tests.test_governance_collection import runtime

    _, evidence, execution, bucket, document = runtime(context)
    replacement = evidence.put(
        context.a,
        uuid4(),
        EvidenceInput(
            collection_id=bucket["id"],
            document_id=document["id"],
            expected_version=1,
            content="Synthetic expiring replacement",
        ),
    )
    record = execution.propose(
        context.a,
        uuid4(),
        execution_module().InstructionInput(
            **instruction(
                collection_id=bucket["id"],
                document_id=document["id"],
                action="correct",
                evidence_id=replacement["id"],
                expires_at=datetime.now(UTC) + timedelta(seconds=1),
            )
        ),
    )
    time.sleep(1.05)
    with pytest.raises(Exception, match="^approval_expired$"):
        execution.preview_evidence(context.b, record["id"], 1)


def test_database_admin_recovery_metadata_does_not_grant_document_or_instruction_reads(context):
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient

    from app.enterprise.managed_routes import build_managed_router
    from pii_redactor.governance.errors import GovernanceError
    from tests.test_governance_collection import runtime

    collection, evidence, execution, bucket, document = runtime(context)
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET roles='[\"system_administrator\"]'::jsonb,revision=revision+1 WHERE member_id=%s",
            (context.ids[0],),
        )

    app = FastAPI()

    @app.exception_handler(GovernanceError)
    def fixed_error(_request: Request, error):
        return JSONResponse({"error": {"code": error.code}}, status_code=403)

    app.include_router(
        build_managed_router(
            collection, execution, evidence, lambda request, mutation=False: context.a
        )
    )
    client = TestClient(app)
    response = client.get("/api/enterprise/v1/managed/recovery/collections")
    assert response.status_code == 200, "admin recovery metadata path is missing"
    assert response.json()["items"][0]["id"] == bucket["id"]
    assert "content" not in response.text and "subject_id" not in response.text
    assert client.get("/api/enterprise/v1/managed/collections").status_code == 403
    assert client.get("/api/enterprise/v1/managed/instructions").status_code == 403
    assert (
        client.get(
            f"/api/enterprise/v1/managed/collections/{bucket['id']}/documents/{document['id']}/versions/1"
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/enterprise/v1/managed/collections/{bucket['id']}/snapshots",
            json={"command_key": str(uuid4())},
        ).status_code
        == 200
    )
