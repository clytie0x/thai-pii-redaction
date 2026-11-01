from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")
from tests import governance_helpers as fixtures

context = fixtures.context
database = fixtures.database


def activity(**changes):
    from pii_redactor.governance.registry import ActivityInput

    return ActivityInput(
        **{
            "department_id": "operations",
            "title": "Synthetic support processing",
            "purpose": "Resolve service requests",
            "necessity": "Contact the requesting customer",
            "categories": ["CONTACT"],
            "general_basis": "contract",
            "retention_rule": "Thirty days after support case closure",
            "destination": "Organization-controlled Thailand storage",
            "source_refs": ["system:synthetic-support"],
            "subject_groups": ["customers"],
            "recipient_refs": ["processor:synthetic-local"],
            **changes,
        }
    )


def evidence():
    return {
        key: "review:synthetic-" + key for key in ["inventory", "basis", "retention", "destination"]
    }


def published_notice(registry, context, record):
    from pii_redactor.governance.registry import NoticeInput

    notice = registry.create_notice(
        context.a,
        uuid4(),
        NoticeInput(
            activity_id=record["id"],
            title="Synthetic support notice",
            body="We process contact details for support.",
            language="en",
        ),
    )
    return registry.publish_notice(context.b, uuid4(), notice["id"], 1)


def test_notice_creation_cannot_silently_bind_to_a_changed_activity(context):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.registry import NoticeInput, Registry

    registry = Registry(context.store)
    record = registry.create_activity(context.a, uuid4(), activity())
    registry.update_activity(
        context.a,
        uuid4(),
        record["id"],
        record["revision"],
        activity(purpose="A changed synthetic purpose"),
    )
    request = NoticeInput(
        activity_id=record["id"],
        title="Notice for original purpose",
        body="This notice was authored for the original synthetic purpose.",
        language="en",
    )
    with pytest.raises(GovernanceError, match="^revision_conflict$"):
        registry.create_notice(
            context.a, uuid4(), request, expected_activity_revision=record["revision"]
        )
    assert registry.list_notices(context.a, record["id"]) == []


def test_activity_retries_are_idempotent_and_changed_payload_conflicts(context):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.registry import Registry

    registry = Registry(context.store)
    key = uuid4()
    first = registry.create_activity(context.a, key, activity())
    assert registry.create_activity(context.a, key, activity()) == first
    with pytest.raises(GovernanceError, match="idempotency_conflict"):
        registry.create_activity(context.a, key, activity(title="Changed request"))
    assert len(registry.list_activities(context.a)) == 1


def test_other_departments_cannot_read_or_update_activity(context):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.registry import Registry

    registry = Registry(context.store)
    record = registry.create_activity(context.a, uuid4(), activity())
    assert registry.list_activities(context.c) == []
    with pytest.raises(GovernanceError, match="record_unavailable"):
        registry.get_activity(context.c, record["id"])
    with pytest.raises(GovernanceError, match="record_unavailable"):
        registry.update_activity(
            context.c, uuid4(), record["id"], 1, activity(department_id="finance")
        )


def test_stale_revision_cannot_overwrite_a_newer_activity(context):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.registry import Registry

    registry = Registry(context.store)
    record = registry.create_activity(context.a, uuid4(), activity())
    updated = registry.update_activity(
        context.a, uuid4(), record["id"], 1, activity(title="Reviewed title")
    )
    assert updated["revision"] == 2
    with pytest.raises(GovernanceError, match="revision_conflict"):
        registry.update_activity(
            context.a, uuid4(), record["id"], 1, activity(title="Stale overwrite")
        )
    assert registry.get_activity(context.a, record["id"])["data"]["title"] == "Reviewed title"


def test_activity_needs_independent_review_and_a_matching_published_notice(context):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.registry import Registry, ReviewInput

    registry = Registry(context.store)
    record = registry.create_activity(context.a, uuid4(), activity())
    notice = published_notice(registry, context, record)
    submitted = registry.submit_activity(context.a, uuid4(), record["id"], 1)
    review = ReviewInput(
        decision="approve",
        reason="Independently reviewed organization records",
        notice_id=notice["id"],
        evidence=evidence(),
    )
    with pytest.raises(GovernanceError, match="separation_required"):
        registry.review_activity(context.a, uuid4(), record["id"], submitted["revision"], review)
    result = registry.review_activity(
        context.b, uuid4(), record["id"], submitted["revision"], review
    )
    assert result["state"] == "active" and result["legal_clearance"] is False
    assert result["reviewed_by"] == str(context.ids[1])
    assert result["reviewed_at"] is not None


def test_sensitive_activity_cannot_activate_without_separate_condition(context):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.registry import Registry, ReviewInput

    registry = Registry(context.store)
    record = registry.create_activity(context.a, uuid4(), activity(categories=["HEALTH"]))
    notice = published_notice(registry, context, record)
    submitted = registry.submit_activity(context.a, uuid4(), record["id"], 1)
    review = ReviewInput(
        decision="approve",
        reason="General contract basis only is insufficient",
        notice_id=notice["id"],
        evidence=evidence(),
    )
    with pytest.raises(GovernanceError, match="review_incomplete"):
        registry.review_activity(context.b, uuid4(), record["id"], submitted["revision"], review)


def test_audit_failure_rolls_back_registry_and_outbox(context):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.registry import Registry

    registry = Registry(context.store)
    with context.store.transaction() as tx:
        before = tx.execute("SELECT count(*) AS n FROM governance_outbox").fetchone()["n"]
        tx.execute("""CREATE FUNCTION refuse_registry_audit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic audit failure'; END $$;
            CREATE TRIGGER refuse_registry BEFORE INSERT ON governance_audit
            FOR EACH ROW EXECUTE FUNCTION refuse_registry_audit();""")
    with pytest.raises(GovernanceError, match="storage_failure"):
        registry.create_activity(context.a, uuid4(), activity())
    assert registry.list_activities(context.a) == []
    with context.store.transaction() as tx:
        assert tx.execute("SELECT count(*) AS n FROM governance_outbox").fetchone()["n"] == before


def test_idempotent_retry_cannot_return_data_after_scope_revocation(context):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.registry import Registry

    registry = Registry(context.store)
    key = uuid4()
    registry.create_activity(context.a, key, activity())
    with context.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET departments='[\"finance\"]'::jsonb WHERE member_id=%s",
            (context.ids[0],),
        )
    with pytest.raises(GovernanceError, match="forbidden"):
        registry.create_activity(context.a, key, activity())


def test_published_notice_content_cannot_be_modified(context):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.registry import Registry

    registry = Registry(context.store)
    record = registry.create_activity(context.a, uuid4(), activity())
    notice = published_notice(registry, context, record)
    with pytest.raises(GovernanceError, match="storage_failure"):
        with context.store.transaction() as tx:
            tx.execute(
                "UPDATE governance_notices SET data=jsonb_set(data,'{body}','\"Changed after publication\"') WHERE notice_id=%s",
                (notice["id"],),
            )


def test_changed_purpose_cannot_reuse_old_notice_approval(context):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.registry import Registry, ReviewInput

    registry = Registry(context.store)
    record = registry.create_activity(context.a, uuid4(), activity())
    notice = published_notice(registry, context, record)
    updated = registry.update_activity(
        context.a, uuid4(), record["id"], 1, activity(purpose="A different processing purpose")
    )
    submitted = registry.submit_activity(context.a, uuid4(), record["id"], updated["revision"])
    review = ReviewInput(
        decision="approve",
        reason="Old notice does not cover a different purpose",
        notice_id=notice["id"],
        evidence=evidence(),
    )
    with pytest.raises(GovernanceError, match="notice_scope_mismatch"):
        registry.review_activity(context.b, uuid4(), record["id"], submitted["revision"], review)


def test_concurrent_updates_preserve_one_revision_and_one_winner(context):
    from concurrent.futures import ThreadPoolExecutor

    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.registry import Registry

    registry = Registry(context.store)
    record = registry.create_activity(context.a, uuid4(), activity())

    def update(title):
        try:
            return registry.update_activity(
                context.a, uuid4(), record["id"], 1, activity(title=title)
            )["revision"]
        except GovernanceError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(update, ["Concurrent A", "Concurrent B"]))
    assert outcomes.count(2) == 1 and outcomes.count("revision_conflict") == 1


def test_audit_and_outbox_never_contain_processing_text(context):
    import json

    from pii_redactor.governance.registry import Registry

    registry = Registry(context.store)
    registry.create_activity(
        context.a,
        uuid4(),
        activity(title="PRIVATE_SYNTHETIC_TITLE", purpose="PRIVATE_SYNTHETIC_PURPOSE"),
    )
    with context.store.transaction() as tx:
        audit = tx.execute("SELECT details FROM governance_audit").fetchall()
        outbox = tx.execute("SELECT payload FROM governance_outbox").fetchall()
    assert "PRIVATE_SYNTHETIC" not in json.dumps([audit, outbox])


def test_notice_reads_require_the_same_activity_scope(context):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.registry import Registry

    registry = Registry(context.store)
    record = registry.create_activity(context.a, uuid4(), activity())
    notice = published_notice(registry, context, record)
    assert registry.get_notice(context.a, notice["id"])["state"] == "published"
    assert [n["id"] for n in registry.list_notices(context.b, record["id"])] == [notice["id"]]
    with pytest.raises(GovernanceError, match="record_unavailable"):
        registry.get_notice(context.c, notice["id"])


def test_blank_notice_and_evidence_are_not_reviewable_organization_records():
    from pydantic import ValidationError

    from pii_redactor.governance.registry import NoticeInput, ReviewInput

    with pytest.raises(ValidationError):
        NoticeInput(activity_id=uuid4(), title="A notice", body=" " * 30, language="en")
    with pytest.raises(ValidationError):
        ReviewInput(
            decision="approve",
            reason="Reviewed organization evidence",
            evidence={"inventory": "   "},
        )
