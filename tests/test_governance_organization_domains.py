"""Processor, transfer, incident, responsibility and source failure paths."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from pii_redactor.governance.assessments import Assessments
from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.incidents import Incidents
from pii_redactor.governance.policy_register import CONTROL_KEYS, LegalControls, Policies
from pii_redactor.governance.processors import Processors
from pii_redactor.governance.responsibilities import Responsibilities
from pii_redactor.governance.transfers import Transfers
from tests import governance_helpers as fixtures
from tests.test_governance_organization_controls import (
    activate,
    common,
    policy,
    processor,
)

context = fixtures.context
database = fixtures.database


def source(**changes):
    return policy(
        policy_kind="source",
        instrument={
            "url": "https://ratchakitcha.soc.go.th/documents/synthetic.pdf",
            "sha256": "0" * 64,
            "byte_count": 100,
            "fetched_at": datetime.now(UTC).isoformat(),
            "version": "synthetic-test-only",
            "effective_on": "2020-01-01",
            "amendment_review": "reviewer_attested",
            "qualified_review_ref": str(uuid4()),
            **changes,
        },
    )


def binding(row):
    return {"id": row["id"], "revision": row["revision"]}


def test_transfer_exact_destination_source_and_safeguard_expiry(context):
    c = context
    proc = activate(Processors(c.store), c, processor())
    law = activate(Policies(c.store), c, source())
    data = common(
        processor=binding(proc),
        source=binding(law),
        destination_ref=proc["data"]["destination_ref"],
        recipient_ref=proc["data"]["recipient_ref"],
        access_evidence_ref=str(uuid4()),
        classification="international",
        route="section29_safeguard",
        safeguard_ref=str(uuid4()),
        dependencies=[binding(proc), binding(law)],
    )
    reg = Transfers(c.store)
    current = activate(reg, c, data)
    assert current["usable"]
    changed = activate(Processors(c.store), c, processor(supersedes=binding(proc)))
    with pytest.raises(GovernanceError, match="control_stale"):
        reg.require_active(c.b, current["id"], current["revision"])
    wrong = {
        **data,
        "processor": binding(changed),
        "dependencies": [binding(changed), binding(law)],
    }
    row = reg.create(c.a, uuid4(), wrong)
    reg.submit(c.a, uuid4(), row["id"], 1)
    with pytest.raises(GovernanceError, match="destination_changed"):
        reg.review(c.b, uuid4(), row["id"], 2, "approve", uuid4())
    expired = {
        **wrong,
        "destination_ref": changed["data"]["destination_ref"],
        "recipient_ref": changed["data"]["recipient_ref"],
        "expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    }
    row = reg.create(c.a, uuid4(), expired)
    reg.submit(c.a, uuid4(), row["id"], 1)
    with pytest.raises(GovernanceError, match="control_stale"):
        reg.review(c.b, uuid4(), row["id"], 2, "approve", uuid4())


@pytest.mark.parametrize(
    "change", [{"agreement_ref": None}, {"destination_ref": "foreign-cloud"}, {"sme": True}]
)
def test_incomplete_processor_or_blanket_sme_exemption_rejected(context, change):
    with pytest.raises(GovernanceError, match="invalid_request"):
        Processors(context.store).create(context.a, uuid4(), processor(**change))


def test_incident_draft_cannot_close_notification_and_unknown_clock(context):
    c = context
    reg = Incidents(c.store)
    data = common(
        awareness_at=None,
        awareness_evidence_ref=str(uuid4()),
        uncertainty_ref=str(uuid4()),
        risk="unknown",
        risk_review_ref=str(uuid4()),
        escalation_ref=str(uuid4()),
        tasks=[
            {
                "audience": "authority",
                "applicability": "unknown",
                "state": "draft",
                "rationale_ref": str(uuid4()),
            }
        ],
    )
    row = activate(reg, c, data)
    assert row["conditional_authority_target_at"] is None
    assert not row["notification_closed"]
    assert row["outstanding_tasks"] == ["authority", "subjects", "controller"]
    data["awareness_at"] = datetime.now(UTC).isoformat()
    data["risk"] = "high"
    data["tasks"][0].update(applicability="required", state="external_evidence_recorded")
    with pytest.raises(GovernanceError, match="invalid_request"):
        reg.replace(c.a, uuid4(), row["id"], row["revision"], data)


def test_responsibility_requires_applicability_conflict_and_independent_review(context):
    c = context
    reg = Responsibilities(c.store)
    data = common(
        responsibility="dpo",
        applicability="unknown",
        rationale_ref=str(uuid4()),
        designation_ref=str(uuid4()),
        independence_ref=str(uuid4()),
        conflict_review_ref=str(uuid4()),
        escalation_ref=str(uuid4()),
        backup_ref=str(uuid4()),
    )
    row = reg.create(c.a, uuid4(), data)
    reg.submit(c.a, uuid4(), row["id"], 1)
    with pytest.raises(GovernanceError, match="applicability_unresolved"):
        reg.review(c.b, uuid4(), row["id"], 2, "approve", uuid4())
    reg.review(c.b, uuid4(), row["id"], 2, "reject", uuid4())
    with pytest.raises(GovernanceError, match="invalid_transition"):
        reg.activate(c.b, uuid4(), row["id"], 3)
    data["applicability"] = "reviewed_not_applicable"
    assert activate(reg, c, data)["usable"]


@pytest.mark.parametrize("kind", ["risk", "complaint", "training", "periodic_review"])
def test_assessments_cover_risk_complaints_training_and_review(context, kind):
    row = activate(
        Assessments(context.store),
        context,
        common(
            assessment_kind=kind,
            subject_ref=str(uuid4()),
            findings_ref=str(uuid4()),
            mitigation_ref=str(uuid4()),
            followup_ref=str(uuid4()),
            outcome="evidence_recorded",
        ),
    )
    assert row["state"] == "active" and row["legal_clearance"] is False


def test_source_pending_and_unknown_legal_applicability_stay_pending(context):
    c = context
    reg = Policies(c.store)
    row = reg.create(c.a, uuid4(), source(amendment_review="pending"))
    reg.submit(c.a, uuid4(), row["id"], 1)
    with pytest.raises(GovernanceError, match="source_unverified"):
        reg.review(c.b, uuid4(), row["id"], 2, "approve", uuid4())
    law = activate(reg, c, source())
    legal = LegalControls(c.store)
    data = common(
        control_key="dpo",
        applicability="unknown",
        rationale_ref=str(uuid4()),
        source=binding(law),
        dependencies=[binding(law)],
    )
    row = legal.create(c.a, uuid4(), data)
    legal.submit(c.a, uuid4(), row["id"], 1)
    with pytest.raises(GovernanceError, match="applicability_unresolved"):
        legal.review(c.b, uuid4(), row["id"], 2, "approve", uuid4())


def test_reviewed_not_applicable_retains_source_reviewer_evidence_and_invalidates(context):
    c = context
    policies = Policies(c.store)
    law = activate(policies, c, source())
    legal = LegalControls(c.store)
    for key in CONTROL_KEYS:
        activate(
            legal,
            c,
            common(
                control_key=key,
                applicability="reviewed_not_applicable",
                rationale_ref=str(uuid4()),
                source=binding(law),
                dependencies=[binding(law)],
            ),
        )
    report = legal.release_findings(c.b, {"department_id": "operations"})
    assert not report["blocked"] and not report["legal_clearance"]
    assert all(
        i["decision"] == "reviewed_not_applicable"
        and i["source"]["version"] == "synthetic-test-only"
        and i["reviewer"]
        and i["evidence"]
        for i in report["items"]
    )
    policies.replace(
        c.a, uuid4(), law["id"], law["revision"], source(version="changed-synthetic-version")
    )
    stale = legal.release_findings(c.b, {"department_id": "operations"})["items"]
    assert all(
        i["decision"] == "unresolved" and i["source"]["version"] == "synthetic-test-only"
        for i in stale
    )


def test_workflow_activity_revision_and_opaque_m7_reference(context):
    from pii_redactor.governance.registry import Registry
    from tests.test_governance_registry import activity

    c = context
    registry = Registry(c.store)
    draft = registry.create_activity(c.a, uuid4(), activity())
    data = policy(links=[{"kind": "activity", "id": draft["id"], "revision": draft["revision"]}])
    reg = Policies(c.store)
    row = reg.create(c.a, uuid4(), data)
    reg.submit(c.a, uuid4(), row["id"], 1)
    with pytest.raises(GovernanceError, match="control_stale"):
        reg.review(c.b, uuid4(), row["id"], 2, "approve", uuid4())
    data = policy(links=[{"kind": "case", "id": str(uuid4()), "revision": 1}])
    row = reg.create(c.a, uuid4(), data)
    reg.submit(c.a, uuid4(), row["id"], 1)
    with pytest.raises(GovernanceError, match="linked_case_unverified"):
        reg.review(c.b, uuid4(), row["id"], 2, "approve", uuid4())


def test_missing_notification_audience_decisions_block_an_otherwise_reviewed_release(context):
    c = context
    law = activate(Policies(c.store), c, source())
    legal = LegalControls(c.store)
    for key in CONTROL_KEYS:
        activate(
            legal,
            c,
            common(
                control_key=key,
                applicability="reviewed_not_applicable",
                rationale_ref=str(uuid4()),
                source=binding(law),
                dependencies=[binding(law)],
            ),
        )
    assert not legal.release_findings(c.b, {"department_id": "operations"})["blocked"]
    incidents = Incidents(c.store)
    data = common(
        awareness_at=datetime.now(UTC).isoformat(),
        awareness_evidence_ref=str(uuid4()),
        uncertainty_ref=str(uuid4()),
        risk="low",
        risk_review_ref=str(uuid4()),
        escalation_ref=str(uuid4()),
        tasks=[
            {
                "audience": "controller",
                "applicability": "reviewed_not_applicable",
                "state": "pending",
                "rationale_ref": str(uuid4()),
            }
        ],
    )
    row = activate(incidents, c, data)
    assert set(row["outstanding_tasks"]) == {"authority", "subjects"}
    assert legal.release_findings(c.b, {"department_id": "operations"})["blocked"]
    data["tasks"] = [
        {
            "audience": audience,
            "applicability": "reviewed_not_applicable",
            "state": "pending",
            "rationale_ref": str(uuid4()),
        }
        for audience in ("authority", "subjects", "controller")
    ]
    row = incidents.replace(c.a, uuid4(), row["id"], row["revision"], data)
    row = incidents.submit(c.a, uuid4(), row["id"], row["revision"])
    row = incidents.review(c.b, uuid4(), row["id"], row["revision"], "approve", uuid4())
    incidents.activate(c.b, uuid4(), row["id"], row["revision"])
    assert not legal.release_findings(c.b, {"department_id": "operations"})["blocked"]


def test_required_release_evidence_and_incident_draft_remain_unresolved(context):
    c = context
    law = activate(Policies(c.store), c, source())
    incidents = Incidents(c.store)
    incident = activate(
        incidents,
        c,
        common(
            awareness_at=datetime.now(UTC).isoformat(),
            awareness_evidence_ref=str(uuid4()),
            uncertainty_ref=str(uuid4()),
            risk="high",
            risk_review_ref=str(uuid4()),
            escalation_ref=str(uuid4()),
            tasks=[
                {
                    "audience": "authority",
                    "applicability": "required",
                    "state": "draft",
                    "rationale_ref": str(uuid4()),
                }
            ],
        ),
    )
    legal = LegalControls(c.store)
    data = common(
        control_key="security_retention_incidents",
        applicability="required",
        rationale_ref=str(uuid4()),
        source=binding(law),
        dependencies=[binding(law), binding(incident)],
    )
    row = legal.create(c.a, uuid4(), data)
    legal.submit(c.a, uuid4(), row["id"], 1)
    with pytest.raises(GovernanceError, match="evidence_required"):
        legal.review(c.b, uuid4(), row["id"], 2, "approve", uuid4())
    data.update(implementation_ref=str(uuid4()), operational_ref=str(uuid4()))
    with pytest.raises(GovernanceError, match="operational_obligations_unresolved"):
        activate(legal, c, data)
    report = legal.release_findings(c.b, {"department_id": "operations"})
    finding = next(i for i in report["items"] if i["control_key"] == "security_retention_incidents")
    assert finding["decision"] == "unresolved"
    assert any(
        i["control_key"] == "incident_tasks" and i["decision"] == "unresolved"
        for i in report["items"]
    )


def test_owned_history_and_receipt_are_value_free_and_append_only(context):
    from psycopg import Error

    c = context
    reg = Policies(c.store)
    row = activate(reg, c, policy())
    page = reg.history(c.b, row["id"], limit=2)
    assert page["historical_only"] and page["next_cursor"] == 2
    assert reg.history(c.b, row["id"], after=2)["items"][-1]["activated_at"]
    with pytest.raises(GovernanceError):
        reg.history(c.c, row["id"])
    with c.store.transaction() as tx:
        history = tx.execute(
            "SELECT * FROM governance_control_history WHERE control_id=%s ORDER BY revision",
            (row["id"],),
        ).fetchall()
        assert len(history) == 4 and [h["snapshot"]["state"] for h in history] == [
            "draft",
            "submitted",
            "reviewed",
            "active",
        ]
    with pytest.raises(GovernanceError, match="storage_failure"):
        with c.store.transaction() as tx:
            tx.execute("DELETE FROM governance_control_history WHERE control_id=%s", (row["id"],))
    with c.store.transaction() as tx:
        assert all(
            event["details"] == {}
            for event in tx.execute(
                "SELECT details FROM governance_audit WHERE event_code LIKE 'control.%'"
            )
        )


def test_supersession_is_exact_and_concurrent_revision_has_one_winner(context):
    from concurrent.futures import ThreadPoolExecutor

    c = context
    reg = Policies(c.store)
    old = activate(reg, c, policy())
    new = reg.create(c.a, uuid4(), policy(supersedes=binding(old)))
    reg.replace(c.a, uuid4(), old["id"], old["revision"], policy())
    reg.submit(c.a, uuid4(), new["id"], 1)
    reg.review(c.b, uuid4(), new["id"], 2, "approve", uuid4())
    with pytest.raises(GovernanceError, match="revision_conflict"):
        reg.activate(c.b, uuid4(), new["id"], 3)
    row = reg.create(c.a, uuid4(), policy())

    def submit():
        try:
            return reg.submit(c.a, uuid4(), row["id"], 1)["state"]
        except GovernanceError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: submit(), range(2))) == ["revision_conflict", "submitted"]


def test_expired_unlinked_incident_review_still_blocks_release(context, monkeypatch):
    from pii_redactor.governance import control_register

    c = context
    law = activate(Policies(c.store), c, source())
    legal = LegalControls(c.store)
    for key in CONTROL_KEYS:
        activate(
            legal,
            c,
            common(
                control_key=key,
                applicability="reviewed_not_applicable",
                rationale_ref=str(uuid4()),
                source=binding(law),
                dependencies=[binding(law)],
            ),
        )
    activate(
        Incidents(c.store),
        c,
        common(
            expires_at=(datetime.now(UTC) + timedelta(hours=12)).isoformat(),
            awareness_at=datetime.now(UTC).isoformat(),
            awareness_evidence_ref=str(uuid4()),
            uncertainty_ref=str(uuid4()),
            risk="low",
            risk_review_ref=str(uuid4()),
            escalation_ref=str(uuid4()),
            tasks=[
                {
                    "audience": audience,
                    "applicability": "reviewed_not_applicable",
                    "state": "pending",
                    "rationale_ref": str(uuid4()),
                }
                for audience in ("authority", "subjects", "controller")
            ],
        ),
    )
    assert not legal.release_findings(c.b, {"department_id": "operations"})["blocked"]

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + timedelta(days=1)

    monkeypatch.setattr(control_register, "datetime", Later)
    assert legal.release_findings(c.b, {"department_id": "operations"})["blocked"]
