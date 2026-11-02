"""Real PostgreSQL flows through the exact enterprise production composition."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("authlib", reason="optional enterprise identity dependency")
pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from app.enterprise.capabilities import ConfiguredKeyProvider, managed_services
from pii_redactor.governance.collections import CollectionInput
from pii_redactor.governance.consent import ConsentScope, NoticeProof, PropagationScope
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.execution import InstructionInput
from pii_redactor.governance.registry import Registry, ReviewInput
from tests import governance_helpers as fixtures
from tests import test_governance_consent as consent_fixtures
from tests.test_governance_registry import activity, evidence, published_notice

database = fixtures.database
context = fixtures.context
subject_context = consent_fixtures.subject_context
consent_context = consent_fixtures.consent_context


@pytest.fixture
def integrated(consent_context, tmp_path):
    c = consent_context
    key_file = tmp_path / "synthetic-integration.key"
    key_file.write_text(
        json.dumps(
            {
                "organization_id": str(c.store.organization_id),
                "active_version": "v1",
                "keys": [{"version": "v1", "key_hex": "53" * 32}],
            }
        ),
        encoding="utf-8",
    )
    provider = ConfiguredKeyProvider(key_file, c.store.organization_id)
    c.collection, c.evidence, c.execution, c.worker = managed_services(c.store, provider)
    with c.store.transaction() as tx:
        c.activity = tx.execute(
            "SELECT * FROM governance_activities WHERE activity_id=%s",
            (c.notice["data"]["activity_id"],),
        ).fetchone()
    return c


def create_collection(c, *, source=None, subject_id=None, purpose_version=None):
    source = c.activity if source is None else source
    return c.collection.create(
        c.a,
        uuid4(),
        CollectionInput(
            activity_id=source["activity_id"],
            expected_activity_revision=source["revision"],
            subject_id=subject_id or c.subject["subject_id"],
            purpose_version=purpose_version or c.notice["id"],
        ),
    )


def primary(c, document_id):
    with c.store.transaction() as tx:
        return tx.execute(
            """SELECT state,revision,current_version,last_instruction_id
                          FROM governance_managed_documents WHERE document_id=%s""",
            (document_id,),
        ).fetchone()


def independently_approved(c, bucket, document):
    proposal = c.execution.propose(
        c.a,
        uuid4(),
        InstructionInput(
            collection_id=bucket["id"],
            document_id=document["id"],
            expected_revision=document["revision"],
            expected_version=document["version"],
            action="suppress",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        ),
    )
    approved = c.execution.approve(c.b, uuid4(), proposal["id"], proposal["revision"])
    assert approved["state"] == "pending"
    return approved


def queued_state(c, instruction_id):
    with c.store.transaction() as tx:
        return tx.execute(
            """SELECT i.state,i.revision,t.state AS task_state,t.last_error,
                          t.lease_token IS NULL AND t.worker_id IS NULL AND t.lease_until IS NULL AS lease_cleared
                          FROM governance_execution_instructions i LEFT JOIN governance_execution_tasks t USING(instruction_id)
                          WHERE i.instruction_id=%s""",
            (instruction_id,),
        ).fetchone()


def queued_document(c):
    bucket = create_collection(c)
    document = c.collection.put(c.a, uuid4(), bucket["id"], "Synthetic queued authority document.")
    return bucket, document, independently_approved(c, bucket, document)


def verify_withdrawal_propagation(c):
    for task in c.consent.status(c.actor, c.notice["id"])["propagation"]:
        if task["state"] == "verified":
            continue
        c.consent.review_propagation(
            c.b,
            uuid4(),
            task["id"],
            "verified",
            uuid4(),
            evidence_scope=PropagationScope(
                consent_event_id=task["consent_event_id"],
                event_revision=task["event_revision"],
                recipient_ordinal=task["recipient"],
                expected_state=task["state"],
            ),
        )


def reviewed_activity(c, *, basis="consent", categories=None):
    registry = Registry(c.store)
    draft = registry.create_activity(
        c.a,
        uuid4(),
        activity(
            purpose="Synthetic independent processing purpose",
            general_basis=basis,
            categories=categories or ["CONTACT"],
        ),
    )
    notice = published_notice(registry, c, draft)
    submitted = registry.submit_activity(c.a, uuid4(), draft["id"], draft["revision"])
    active = registry.review_activity(
        c.b,
        uuid4(),
        draft["id"],
        submitted["revision"],
        ReviewInput(
            decision="approve",
            reason="Synthetic separate purpose has independent evidence.",
            notice_id=notice["id"],
            evidence=evidence(),
        ),
    )
    return {"activity_id": draft["id"], "revision": active["revision"]}, notice


def test_production_composition_valid_consent_allows_collection_put(integrated):
    c = integrated
    consent_fixtures.command(c, "grant")
    bucket = create_collection(c)
    document = c.collection.put(c.a, uuid4(), bucket["id"], "Synthetic integration document.")
    assert bucket["consent_bound"] is True
    assert primary(c, document["id"])["state"] == "active"
    assert (
        c.collection.read_version(c.a, bucket["id"], document["id"], 1)["content"]
        == "Synthetic integration document."
    )


def test_production_worker_rechecks_withdrawal_after_independent_approval(integrated):
    c = integrated
    consent_fixtures.command(c, "grant")
    bucket = create_collection(c)
    document = c.collection.put(c.a, uuid4(), bucket["id"], "Synthetic queued document.")
    approved = independently_approved(c, bucket, document)
    before = primary(c, document["id"])
    consent_fixtures.command(c, "withdraw", expected=1)
    denied = c.worker.run_once("synthetic-integration-worker")
    assert denied["state"] == "idle"
    cancelled = queued_state(c, approved["id"])
    assert cancelled["state"] == cancelled["task_state"] == "failed"
    assert cancelled["last_error"] == "consent_authority_changed"
    assert denied["primary_verified"] is False
    assert primary(c, document["id"]) == before
    with c.store.transaction() as tx:
        assert (
            tx.execute(
                "SELECT count(*) AS n FROM governance_execution_outcomes WHERE instruction_id=%s",
                (approved["id"],),
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize("wrong", ["purpose", "activity"])
def test_production_collection_cannot_borrow_other_purpose_grant(integrated, wrong):
    c = integrated
    consent_fixtures.command(c, "grant")
    other, other_notice = reviewed_activity(c)
    c.consent.present(c.actor, other_notice["id"])
    with pytest.raises(GovernanceError, match="^consent_scope_required$"):
        if wrong == "purpose":
            create_collection(c, purpose_version=other_notice["id"])
        else:
            create_collection(c, source=other)
    with c.store.transaction() as tx:
        assert tx.execute("SELECT count(*) AS n FROM governance_collections").fetchone()["n"] == 0


def test_exact_production_gate_rejects_stale_bound_activity_revision(integrated):
    c = integrated
    consent_fixtures.command(c, "grant")
    bucket = create_collection(c)
    with c.store.transaction() as tx:
        row = tx.execute(
            "SELECT * FROM governance_collections WHERE collection_id=%s", (bucket["id"],)
        ).fetchone()
        # Probe the real composed gate against real authority rows, with a stale binding.
        with pytest.raises(GovernanceError, match="^consent_scope_required$"):
            c.collection.consent_check(
                tx,
                collection={**row, "activity_revision": row["activity_revision"] - 1},
                document=None,
                action="put",
            )


def test_production_composition_cannot_widen_granted_categories(integrated):
    c = integrated
    broader, notice = reviewed_activity(c, categories=["CONTACT", "IDENTITY"])
    proof = NoticeProof.model_validate(c.consent.present(c.actor, notice["id"])["notice_proof"])
    c.consent.record_subject_event(
        c.actor,
        uuid4(),
        proof,
        ConsentScope(purpose_version=notice["id"], categories=["CONTACT"], expected_revision=0),
        "grant",
        affirmative=True,
    )
    with pytest.raises(GovernanceError, match="^consent_required$"):
        create_collection(c, source=broader, purpose_version=notice["id"])


def test_separately_reviewed_nonconsent_activity_remains_usable_after_withdrawal(integrated):
    c = integrated
    consent_fixtures.command(c, "grant")
    consent_bucket = create_collection(c)
    consent_fixtures.command(c, "withdraw", expected=1)
    with pytest.raises(GovernanceError, match="^consent_required$"):
        c.collection.put(c.a, uuid4(), consent_bucket["id"], "Synthetic denied document.")
    separate, _notice = reviewed_activity(c, basis="contract")
    bucket = c.collection.create(
        c.a,
        uuid4(),
        CollectionInput(
            activity_id=separate["activity_id"],
            expected_activity_revision=separate["revision"],
        ),
    )
    document = c.collection.put(
        c.a, uuid4(), bucket["id"], "Synthetic separately reviewed document."
    )
    assert bucket["consent_bound"] is False and primary(c, document["id"])["state"] == "active"


def test_genuine_regrant_does_not_reactivate_prewithdrawal_queued_approval(integrated):
    c = integrated
    grant_key = uuid4()
    original_proof = NoticeProof.model_validate(
        c.consent.present(c.actor, c.notice["id"])["notice_proof"]
    )
    consent_fixtures.command(c, "grant", key=grant_key, proof=original_proof)
    bucket = create_collection(c)
    document = c.collection.put(c.a, uuid4(), bucket["id"], "Synthetic old-authority document.")
    independently_approved(c, bucket, document)
    consent_fixtures.command(c, "withdraw", expected=1)
    replay = consent_fixtures.command(c, "grant", key=grant_key, proof=original_proof)
    assert replay["replayed"] is True and replay["effective"]["allowed"] is False
    consent_fixtures.command(c, "grant", expected=2)
    # Remove the separate pending-propagation blocker with genuine scoped evidence review.
    for task in c.consent.status(c.actor, c.notice["id"])["propagation"]:
        c.consent.review_propagation(
            c.b,
            uuid4(),
            task["id"],
            "verified",
            uuid4(),
            evidence_scope=PropagationScope(
                consent_event_id=task["consent_event_id"],
                event_revision=task["event_revision"],
                recipient_ordinal=task["recipient"],
                expected_state=task["state"],
            ),
        )
    state = c.consent.status(c.actor, c.notice["id"])
    assert state["allowed"] is True and state["revision"] == 3
    assert [row["action"] for row in c.consent.history(c.actor, c.notice["id"])] == [
        "grant",
        "withdraw",
        "grant",
    ]
    result = c.worker.run_once("synthetic-integration-worker")
    current = primary(c, document["id"])
    assert (result["primary_verified"], current["state"], current["revision"]) == (
        False,
        "active",
        1,
    )


@pytest.mark.parametrize("stage", ["proposed", "pending", "running", "retry", "unknown"])
def test_real_authority_change_terminally_invalidates_unexecuted_states(integrated, stage):
    c = integrated
    consent_fixtures.command(c, "grant")
    if stage == "proposed":
        bucket = create_collection(c)
        document = c.collection.put(
            c.a, uuid4(), bucket["id"], "Synthetic draft instruction document."
        )
        instruction = c.execution.propose(
            c.a,
            uuid4(),
            InstructionInput(
                collection_id=bucket["id"],
                document_id=document["id"],
                expected_revision=1,
                expected_version=1,
                action="restrict",
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            ),
        )
    else:
        bucket, document, instruction = queued_document(c)
    task = None
    if stage in {"running", "retry", "unknown"}:
        task = c.worker.outbox.claim("synthetic-old-worker")
        if stage in {"retry", "unknown"}:
            c.worker.outbox.record_failure(
                "synthetic-old-worker",
                task,
                "key_service_unavailable" if stage == "retry" else "outcome_unknown",
            )
    consent_fixtures.command(c, "grant", expected=1)
    state = queued_state(c, instruction["id"])
    assert state["state"] == "failed"
    if stage == "proposed":
        assert state["task_state"] is None
    else:
        assert (
            state["task_state"] == "failed"
            and state["last_error"] == "consent_authority_changed"
            and state["lease_cleared"]
        )
    assert primary(c, document["id"])["revision"] == 1
    if stage == "unknown":
        with pytest.raises(GovernanceError, match="^invalid_transition$"):
            c.execution.reconcile(c.b, uuid4(), instruction["id"], state["revision"])
    if stage == "running":
        with pytest.raises(GovernanceError, match="^lease_lost$"):
            c.execution.execute("synthetic-old-worker", task)
        with pytest.raises(GovernanceError, match="^lease_lost$"):
            c.worker.outbox.record_failure("synthetic-old-worker", task, "storage_failure")
        assert queued_state(c, instruction["id"])["state"] == "failed"


@pytest.mark.parametrize("action", ["grant", "refuse", "withdraw"])
def test_portal_authority_events_atomically_cancel_prior_approval(integrated, action):
    c = integrated
    consent_fixtures.command(c, "grant")
    _bucket, document, instruction = queued_document(c)
    consent_fixtures.command(c, action, expected=1)
    assert queued_state(c, instruction["id"])["state"] == "failed"
    assert primary(c, document["id"])["state"] == "active"


@pytest.mark.parametrize(
    "mode,action", [("offline_withdrawal", "withdraw"), ("representative", "grant")]
)
def test_reviewed_offline_events_use_same_atomic_authority_invalidation(integrated, mode, action):
    from pii_redactor.governance.consent import OfflineConsentInput

    c = integrated
    consent_fixtures.command(c, "grant")
    _bucket, _document, instruction = queued_document(c)
    case = c.consent.propose_offline(
        c.a,
        uuid4(),
        OfflineConsentInput(
            subject_id=c.subject["subject_id"],
            scope=ConsentScope(
                purpose_version=c.notice["id"], categories=["CONTACT"], expected_revision=1
            ),
            action=action,
            mode=mode,
            source_evidence_ref=uuid4(),
            source_received_at=datetime.now(UTC) - timedelta(minutes=1),
            capacity_evidence_ref=uuid4() if mode == "representative" else None,
            representative_authority_ref=uuid4() if mode == "representative" else None,
        ),
    )
    assert queued_state(c, instruction["id"])["state"] == "pending"
    reviewed = c.consent.review_offline(c.b, uuid4(), case["id"], 1, "approve", uuid4())
    assert reviewed["portal_act"] is False
    assert queued_state(c, instruction["id"])["state"] == "failed"


def test_corrected_link_and_fresh_grant_do_not_reactivate_old_queue(integrated):
    from app.enterprise.subject_auth import SubjectIdentity
    from pii_redactor.governance.subjects import SubjectLinks
    from tests.test_governance_subjects import link_request

    c = integrated
    consent_fixtures.command(c, "grant")
    _bucket, document, instruction = queued_document(c)
    links = SubjectLinks(c.store)
    correction = links.propose(
        c.a,
        uuid4(),
        link_request(source_version="v2"),
        subject_id=c.subject["subject_id"],
        expected_revision=1,
    )
    links.review(c.b, uuid4(), correction["id"], 1, "approve", uuid4())
    c.actor = c.sessions.resolve(
        c.sessions.issue(
            SubjectIdentity(c.a.issuer, "synthetic-customer", "aiguard-subject")
        ).cookie
    )
    consent_fixtures.command(c, "grant", expected=1)
    assert c.consent.status(c.actor, c.notice["id"])["allowed"] is True
    assert queued_state(c, instruction["id"])["state"] == "failed"
    assert c.worker.run_once("synthetic-integration-worker")["primary_verified"] is False
    assert primary(c, document["id"])["revision"] == 1


def test_changed_category_scope_cancels_old_approval_even_after_full_regrant(integrated):
    c = integrated
    source, notice = reviewed_activity(c, categories=["CONTACT", "IDENTITY"])

    def grant(categories, revision):
        proof = NoticeProof.model_validate(c.consent.present(c.actor, notice["id"])["notice_proof"])
        return c.consent.record_subject_event(
            c.actor,
            uuid4(),
            proof,
            ConsentScope(
                purpose_version=notice["id"], categories=categories, expected_revision=revision
            ),
            "grant",
            affirmative=True,
        )

    grant(["CONTACT", "IDENTITY"], 0)
    bucket = create_collection(c, source=source, purpose_version=notice["id"])
    document = c.collection.put(c.a, uuid4(), bucket["id"], "Synthetic changed-scope document.")
    instruction = independently_approved(c, bucket, document)
    grant(["CONTACT"], 1)
    grant(["CONTACT", "IDENTITY"], 2)
    assert queued_state(c, instruction["id"])["state"] == "failed"
    assert c.worker.run_once("synthetic-integration-worker")["primary_verified"] is False
    assert primary(c, document["id"])["revision"] == 1


def test_same_command_replay_does_not_invalidate_or_duplicate_current_approval(integrated):
    c = integrated
    key = uuid4()
    proof = NoticeProof.model_validate(c.consent.present(c.actor, c.notice["id"])["notice_proof"])
    consent_fixtures.command(c, "grant", key=key, proof=proof)
    _bucket, document, instruction = queued_document(c)
    before = queued_state(c, instruction["id"])
    consent_fixtures.command(c, "grant", key=key, proof=proof)
    assert queued_state(c, instruction["id"]) == before
    assert len(c.consent.history(c.actor, c.notice["id"])) == 1
    assert c.worker.run_once("synthetic-integration-worker")["primary_verified"] is True
    assert primary(c, document["id"])["state"] == "suppressed"


@pytest.mark.parametrize("ack_state", ["verified", "unknown"])
def test_consent_change_never_relabels_immutable_primary_outcome_as_failed(integrated, ack_state):
    c = integrated
    consent_fixtures.command(c, "grant")
    _bucket, document, instruction = queued_document(c)
    assert c.worker.run_once("synthetic-integration-worker")["primary_verified"] is True
    with c.store.transaction() as tx:
        proof = tx.execute(
            "SELECT * FROM governance_execution_outcomes WHERE instruction_id=%s",
            (instruction["id"],),
        ).fetchone()
        if ack_state == "unknown":
            tx.execute(
                "UPDATE governance_execution_instructions SET state='unknown',revision=revision+1 WHERE instruction_id=%s",
                (instruction["id"],),
            )
            tx.execute(
                "UPDATE governance_execution_tasks SET state='unknown',last_error='outcome_unknown' WHERE instruction_id=%s",
                (instruction["id"],),
            )
    before = queued_state(c, instruction["id"])
    consent_fixtures.command(c, "withdraw", expected=1)
    assert queued_state(c, instruction["id"]) == before
    assert primary(c, document["id"])["state"] == "suppressed"
    with c.store.transaction() as tx:
        assert (
            tx.execute(
                "SELECT * FROM governance_execution_outcomes WHERE instruction_id=%s",
                (instruction["id"],),
            ).fetchone()
            == proof
        )


def test_authority_invalidation_is_exact_purpose_and_preserves_nonconsent_queue(integrated):
    c = integrated
    consent_fixtures.command(c, "grant")
    _bucket, _document, affected = queued_document(c)
    other, notice = reviewed_activity(c)
    proof = NoticeProof.model_validate(c.consent.present(c.actor, notice["id"])["notice_proof"])
    c.consent.record_subject_event(
        c.actor,
        uuid4(),
        proof,
        ConsentScope(purpose_version=notice["id"], categories=["CONTACT"], expected_revision=0),
        "grant",
        affirmative=True,
    )
    other_bucket = create_collection(c, source=other, purpose_version=notice["id"])
    other_document = c.collection.put(
        c.a, uuid4(), other_bucket["id"], "Synthetic other-purpose document."
    )
    unaffected = independently_approved(c, other_bucket, other_document)
    separate, _notice = reviewed_activity(c, basis="contract")
    plain_bucket = c.collection.create(
        c.a,
        uuid4(),
        CollectionInput(
            activity_id=separate["activity_id"], expected_activity_revision=separate["revision"]
        ),
    )
    plain_document = c.collection.put(
        c.a, uuid4(), plain_bucket["id"], "Synthetic independently reviewed document."
    )
    plain = independently_approved(c, plain_bucket, plain_document)
    consent_fixtures.command(c, "withdraw", expected=1)
    assert queued_state(c, affected["id"])["state"] == "failed"
    assert queued_state(c, unaffected["id"])["state"] == "pending"
    assert queued_state(c, plain["id"])["state"] == "pending"
    assert c.worker.run_once("synthetic-integration-worker")["primary_verified"] is True
    assert c.worker.run_once("synthetic-integration-worker")["primary_verified"] is True


def test_consent_audit_failure_rolls_back_authority_and_queue_invalidation(integrated):
    c = integrated
    consent_fixtures.command(c, "grant")
    _bucket, document, instruction = queued_document(c)
    before = queued_state(c, instruction["id"])
    proof = NoticeProof.model_validate(c.consent.present(c.actor, c.notice["id"])["notice_proof"])
    with c.store.transaction() as tx:
        tx.execute("""CREATE FUNCTION refuse_authority_change() RETURNS trigger LANGUAGE plpgsql AS $$
                   BEGIN IF NEW.event_code='consent.withdraw' THEN RAISE EXCEPTION 'synthetic failure'; END IF; RETURN NEW; END $$;
                   CREATE TRIGGER refuse_authority_change BEFORE INSERT ON governance_audit
                   FOR EACH ROW EXECUTE FUNCTION refuse_authority_change();""")
    with pytest.raises(GovernanceError, match="^storage_failure$"):
        consent_fixtures.command(c, "withdraw", expected=1, proof=proof)
    assert queued_state(c, instruction["id"]) == before
    assert c.consent.status(c.actor, c.notice["id"])["revision"] == 1
    assert primary(c, document["id"])["state"] == "active"
    with c.store.transaction() as tx:
        assert (
            tx.execute(
                "SELECT count(*) AS n FROM governance_audit WHERE event_code='execution.consent_invalidated'"
            ).fetchone()["n"]
            == 0
        )


def test_fresh_regrant_requires_new_instruction_and_distinct_review(integrated):
    c = integrated
    key = uuid4()
    proof = NoticeProof.model_validate(c.consent.present(c.actor, c.notice["id"])["notice_proof"])
    consent_fixtures.command(c, "grant", key=key, proof=proof)
    bucket, document, old = queued_document(c)
    consent_fixtures.command(c, "withdraw", expected=1)
    consent_fixtures.command(c, "grant", expected=2)
    verify_withdrawal_propagation(c)
    fresh = c.execution.propose(
        c.a,
        uuid4(),
        InstructionInput(
            collection_id=bucket["id"],
            document_id=document["id"],
            expected_revision=1,
            expected_version=1,
            action="restrict",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        ),
    )
    assert c.worker.run_once("synthetic-integration-worker")["state"] == "idle"
    with pytest.raises(GovernanceError, match="forbidden|separation_required"):
        c.execution.approve(c.a, uuid4(), fresh["id"], 1)
    c.execution.approve(c.b, uuid4(), fresh["id"], 1)
    consent_fixtures.command(c, "grant", key=key, proof=proof)
    assert queued_state(c, fresh["id"])["state"] == "pending"
    assert c.worker.run_once("synthetic-integration-worker")["primary_verified"] is True
    assert primary(c, document["id"])["state"] == "restricted"
    with c.store.transaction() as tx:
        assert (
            tx.execute(
                "SELECT count(*) AS n FROM governance_audit WHERE event_code='execution.consent_invalidated' AND target_id=%s",
                (old["id"],),
            ).fetchone()["n"]
            == 1
        )


def test_authority_change_does_not_cancel_another_verified_subject_queue(integrated):
    from app.enterprise.subject_auth import SubjectIdentity
    from pii_redactor.governance.subjects import SubjectLinks
    from tests.test_governance_subjects import link_request

    c = integrated
    consent_fixtures.command(c, "grant")
    _bucket, _document, affected = queued_document(c)
    links = SubjectLinks(c.store)
    proposal = links.propose(c.a, uuid4(), link_request(oidc_subject="synthetic-other-customer"))
    other = links.review(c.b, uuid4(), proposal["id"], 1, "approve", uuid4())
    other_actor = c.sessions.resolve(
        c.sessions.issue(
            SubjectIdentity(c.a.issuer, "synthetic-other-customer", "aiguard-subject")
        ).cookie
    )
    proof = NoticeProof.model_validate(
        c.consent.present(other_actor, c.notice["id"])["notice_proof"]
    )
    c.consent.record_subject_event(
        other_actor,
        uuid4(),
        proof,
        ConsentScope(purpose_version=c.notice["id"], categories=["CONTACT"], expected_revision=0),
        "grant",
        affirmative=True,
    )
    bucket = create_collection(c, subject_id=other["subject_id"])
    document = c.collection.put(c.a, uuid4(), bucket["id"], "Synthetic other-subject document.")
    unaffected = independently_approved(c, bucket, document)
    consent_fixtures.command(c, "withdraw", expected=1)
    assert queued_state(c, affected["id"])["state"] == "failed"
    assert queued_state(c, unaffected["id"])["state"] == "pending"
    assert c.worker.run_once("synthetic-integration-worker")["primary_verified"] is True
    assert primary(c, document["id"])["state"] == "suppressed"
