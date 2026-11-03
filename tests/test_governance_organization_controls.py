"""Synthetic organization records against an owned PostgreSQL database."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from pii_redactor.governance.errors import GovernanceError
from pii_redactor.governance.policy_register import LegalControls, Policies
from pii_redactor.governance.processors import Processors
from tests import governance_helpers as fixtures

database = fixtures.database
context = fixtures.context


def common(**changes):
    return {
        "department_id": "operations",
        "owner_ref": str(uuid4()),
        "evidence_ref": str(uuid4()),
        "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        "links": [],
        "dependencies": [],
        **changes,
    }


def policy(**changes):
    return common(**{"policy_kind": "security", "version_ref": str(uuid4()), **changes})


def processor(**changes):
    return common(
        **{
            "agreement_ref": str(uuid4()),
            "instruction_ref": str(uuid4()),
            "purpose_ref": str(uuid4()),
            "recipient_ref": str(uuid4()),
            "subprocessors": [],
            "destination_ref": str(uuid4()),
            "access_evidence_ref": str(uuid4()),
            **changes,
        }
    )


def activate(register, c, data):
    row = register.create(c.a, uuid4(), data)
    row = register.submit(c.a, uuid4(), row["id"], row["revision"])
    row = register.review(c.b, uuid4(), row["id"], row["revision"], "approve", uuid4())
    assert row["state"] == "reviewed"
    return register.activate(c.b, uuid4(), row["id"], row["revision"])


def test_exact_revision_independent_review_and_current_authority(context):
    c = context
    reg = Processors(c.store)
    row = reg.create(c.a, uuid4(), processor())
    with pytest.raises(GovernanceError, match="revision_conflict"):
        reg.submit(c.a, uuid4(), row["id"], 2)
    row = reg.submit(c.a, uuid4(), row["id"], 1)
    with pytest.raises(GovernanceError, match="separation_required"):
        reg.review(c.a, uuid4(), row["id"], 2, "approve", uuid4())
    row = reg.review(c.b, uuid4(), row["id"], 2, "approve", uuid4())
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET revision=revision+1 WHERE member_id=%s", (c.ids[1],)
        )
    with pytest.raises(GovernanceError, match="authority_changed"):
        reg.activate(c.b, uuid4(), row["id"], row["revision"])


def test_department_admin_and_organization_boundaries(context):
    from pii_redactor.governance.models import Principal
    from pii_redactor.governance.store import Store

    c = context
    reg = Processors(c.store)
    row = reg.create(c.a, uuid4(), processor())
    with pytest.raises(GovernanceError):
        reg.get(c.c, row["id"])
    row = reg.submit(c.a, uuid4(), row["id"], 1)
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_members SET roles='[\"system_administrator\"]'::jsonb WHERE member_id=%s",
            (c.ids[0],),
        )
    with pytest.raises(GovernanceError, match="forbidden"):
        reg.review(c.a, uuid4(), row["id"], 2, "approve", uuid4())
    with pytest.raises(GovernanceError, match="organization_mismatch"):
        Processors(Store(c.store._dsn, uuid4())).get(c.b, row["id"])
    with pytest.raises(GovernanceError):
        reg.get(Principal(issuer=c.a.issuer, subject="unknown"), row["id"])


def test_policy_revision_invalidates_affected_approval(context):
    c = context
    pol = Policies(c.store)
    current = activate(pol, c, policy())
    reg = Processors(c.store)
    bound = activate(
        reg, c, processor(dependencies=[{"id": current["id"], "revision": current["revision"]}])
    )
    assert reg.require_active(c.b, bound["id"], bound["revision"])["usable"]
    pol.replace(c.a, uuid4(), current["id"], current["revision"], policy())
    with pytest.raises(GovernanceError, match="control_stale"):
        reg.require_active(c.b, bound["id"], bound["revision"])
    assert not reg.get(c.b, bound["id"])["usable"]


def test_supersession_and_audit_rollback(context, monkeypatch):
    c = context
    reg = Policies(c.store)
    old = activate(reg, c, policy())
    new = activate(reg, c, policy(supersedes={"id": old["id"], "revision": old["revision"]}))
    assert reg.get(c.b, old["id"])["state"] == "superseded"
    before = c.store.verify_audit()["events"]

    def refuse(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(c.store, "append_event", refuse)
    with pytest.raises(RuntimeError):
        reg.replace(c.a, uuid4(), new["id"], new["revision"], policy())
    assert reg.get(c.b, new["id"])["revision"] == new["revision"]
    assert c.store.verify_audit()["events"] == before


def test_release_register_rejects_unknown_required_applicability(context):
    c = context
    legal = LegalControls(c.store)
    findings = legal.release_findings(c.b, {"department_id": "operations"})
    assert findings["blocked"] and len(findings["items"]) >= 8
    assert all(r["decision"] == "unresolved" for r in findings["items"])
    assert "compliance_score" not in findings


def test_stale_destination_and_replay_do_not_reactivate(context):
    c = context
    reg = Processors(c.store)
    active = activate(reg, c, processor())
    key = uuid4()
    changed = processor()
    draft = reg.replace(c.a, key, active["id"], active["revision"], changed)
    assert draft["state"] == "draft" and not draft["usable"]
    assert reg.replace(c.a, key, active["id"], active["revision"], changed) == draft
    with pytest.raises(GovernanceError, match="idempotency_conflict"):
        reg.replace(c.a, key, active["id"], active["revision"], processor())
