"""Synthetic reviewed due policies and honest copy obligations."""

from uuid import uuid4

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

from pii_redactor.governance.retention import CopyRule, PolicyInput
from tests import governance_helpers as fixtures

database = fixtures.database
context = fixtures.context


def policy_input(**changes):
    return PolicyInput(
        **{
            "collection_id": uuid4(),
            "purpose_version": uuid4(),
            "trigger_kind": "record_closed",
            "delay_days": 30,
            "action": "suppress",
            "policy_evidence_ref": uuid4(),
            "restriction_evidence_ref": uuid4(),
            "copies": [
                CopyRule(kind=kind, recipient_ref=uuid4(), applicability="required")
                for kind in ["derived", "processor", "replica_wal", "backup", "physical_storage"]
            ],
            **changes,
        }
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"trigger_kind": ""},
        {"policy_evidence_ref": None},
        {"action": "physical_erase"},
        {"copies": []},
        {"delay_days": -1},
    ],
)
def test_incomplete_or_destructive_policy_is_rejected_without_database(changes):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        policy_input(**changes)


@pytest.fixture
def retention_context(context):
    from pii_redactor.governance.retention import Retention
    from tests.test_governance_collection import runtime

    c = context
    c.collection, c.evidence, c.execution, c.bucket, c.document = runtime(c)
    with c.store.transaction() as tx:
        c.purpose = tx.execute("SELECT review FROM governance_activities LIMIT 1").fetchone()[
            "review"
        ]["notice_id"]
    c.retention = Retention(c.store, execution=c.execution)
    return c


def prepared_due(c, *, action="suppress"):
    from datetime import UTC, datetime, timedelta

    from pii_redactor.governance.retention import TriggerInput

    policy = c.retention.propose_policy(
        c.a,
        uuid4(),
        policy_input(
            collection_id=c.bucket["id"], purpose_version=c.purpose, delay_days=0, action=action
        ),
    )
    policy = c.retention.review_policy(c.b, uuid4(), policy["id"], 1, "approve", uuid4())
    trigger = c.retention.record_trigger(
        c.a,
        uuid4(),
        TriggerInput(
            policy_id=policy["id"],
            document_id=c.document["id"],
            expected_revision=1,
            expected_version=1,
            occurred_at=datetime.now(UTC) - timedelta(days=1),
            evidence_ref=uuid4(),
        ),
    )
    c.retention.review_trigger(c.b, uuid4(), trigger["id"], 1, uuid4())
    due = c.retention.propose_due(datetime.now(UTC))[0]
    return policy, due


def test_database_policy_trigger_and_due_need_distinct_review(retention_context):
    from datetime import UTC, datetime

    from pii_redactor.governance.errors import GovernanceError

    c = retention_context
    draft = c.retention.propose_policy(
        c.a, uuid4(), policy_input(collection_id=c.bucket["id"], purpose_version=c.purpose)
    )
    with pytest.raises(GovernanceError, match="^separation_required$"):
        c.retention.review_policy(c.a, uuid4(), draft["id"], 1, "approve", uuid4())
    assert c.retention.propose_due(datetime.now(UTC)) == []
    _policy, due = prepared_due(c)
    with pytest.raises(GovernanceError, match="^separation_required$"):
        c.retention.approve_due(c.a, uuid4(), due["id"], 1, uuid4())
    approved = c.retention.approve_due(c.b, uuid4(), due["id"], 1, uuid4())
    assert approved["state"] == "approved"
    with c.store.transaction() as tx:
        assert (
            tx.execute(
                "SELECT state FROM governance_managed_documents WHERE document_id=%s",
                (c.document["id"],),
            ).fetchone()["state"]
            == "active"
        )


def test_database_due_suppression_is_primary_logical_and_copies_remain_open(retention_context):
    from pii_redactor.governance.outbox import Outbox

    c = retention_context
    _policy, due = prepared_due(c)
    c.retention.approve_due(c.b, uuid4(), due["id"], 1, uuid4())
    issued = c.retention.issue_instruction(c.a, uuid4(), due["id"], 2)
    assert issued["state"] == "pending"
    task = Outbox(c.store).claim("synthetic-m6-worker")
    assert c.execution.execute("synthetic-m6-worker", task)["state"] == "verified"
    disposition = c.retention.disposition(c.b, due["id"])
    assert disposition["primary"]["state"] == "suppressed"
    assert disposition["primary"]["physical_erasure"] is False
    assert disposition["all_copies_erased"] is False and disposition["immutable_versions_retained"]
    assert {r["kind"] for r in disposition["copies"]} == {
        "derived",
        "processor",
        "replica_wal",
        "backup",
        "physical_storage",
    }
    assert all(r["state"] == "pending" for r in disposition["copies"])
    backup = next(r for r in disposition["copies"] if r["kind"] == "backup")
    c.retention.review_copy(c.b, uuid4(), backup["id"], 1, "failed", uuid4())
    assert (
        next(r for r in c.retention.disposition(c.b, due["id"])["copies"] if r["kind"] == "backup")[
            "state"
        ]
        == "failed"
    )


def test_database_changed_policy_and_target_invalidate_due_approval(retention_context):
    from pii_redactor.governance.errors import GovernanceError

    c = retention_context
    _policy, due = prepared_due(c)
    c.retention.approve_due(c.b, uuid4(), due["id"], 1, uuid4())
    newer = c.retention.propose_policy(
        c.a,
        uuid4(),
        policy_input(collection_id=c.bucket["id"], purpose_version=c.purpose, delay_days=60),
    )
    c.retention.review_policy(c.b, uuid4(), newer["id"], 1, "approve", uuid4())
    with pytest.raises(GovernanceError, match="^retention_authority_changed$"):
        c.retention.issue_instruction(c.a, uuid4(), due["id"], 2)


def test_database_due_schedule_is_bounded_and_does_not_widen_department(retention_context):
    from datetime import UTC, datetime, timedelta

    from pii_redactor.governance.errors import GovernanceError

    c = retention_context
    prepared_due(c)
    with pytest.raises(GovernanceError, match="^invalid_request$"):
        c.retention.propose_due(datetime.now(UTC) + timedelta(days=1))
    with pytest.raises(GovernanceError, match="forbidden|record_unavailable"):
        c.retention.list_due(c.c, c.bucket["id"])


def test_database_policy_change_after_dispatch_blocks_stale_worker_instruction(retention_context):
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.outbox import Outbox

    c = retention_context
    _policy, due = prepared_due(c)
    c.retention.approve_due(c.b, uuid4(), due["id"], 1, uuid4())
    c.retention.issue_instruction(c.a, uuid4(), due["id"], 2)
    replacement = c.retention.propose_policy(
        c.a,
        uuid4(),
        policy_input(collection_id=c.bucket["id"], purpose_version=c.purpose, delay_days=60),
    )
    c.retention.review_policy(c.b, uuid4(), replacement["id"], 1, "approve", uuid4())
    task = Outbox(c.store).claim("synthetic-m6-worker")
    with pytest.raises(GovernanceError, match="^retention_authority_changed$"):
        c.execution.execute("synthetic-m6-worker", task)
    with c.store.transaction() as tx:
        assert (
            tx.execute(
                "SELECT state FROM governance_managed_documents WHERE document_id=%s",
                (c.document["id"],),
            ).fetchone()["state"]
            == "active"
        )


def test_database_unreviewed_or_stale_trigger_never_becomes_due(retention_context):
    from datetime import UTC, datetime, timedelta

    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.retention import TriggerInput

    c = retention_context
    policy = c.retention.propose_policy(
        c.a,
        uuid4(),
        policy_input(collection_id=c.bucket["id"], purpose_version=c.purpose, delay_days=0),
    )
    c.retention.review_policy(c.b, uuid4(), policy["id"], 1, "approve", uuid4())
    trigger = c.retention.record_trigger(
        c.a,
        uuid4(),
        TriggerInput(
            policy_id=policy["id"],
            document_id=c.document["id"],
            expected_revision=1,
            expected_version=1,
            occurred_at=datetime.now(UTC) - timedelta(days=1),
            evidence_ref=uuid4(),
        ),
    )
    assert c.retention.propose_due(datetime.now(UTC)) == []
    with pytest.raises(GovernanceError, match="^separation_required$"):
        c.retention.review_trigger(c.a, uuid4(), trigger["id"], 1, uuid4())
    with c.store.transaction() as tx:
        tx.execute(
            "UPDATE governance_managed_documents SET revision=revision+1 WHERE document_id=%s",
            (c.document["id"],),
        )
    with pytest.raises(GovernanceError, match="^revision_conflict$"):
        c.retention.review_trigger(c.b, uuid4(), trigger["id"], 1, uuid4())


def test_ui_preserves_primary_vs_copy_uncertainty_without_database():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = r"""
      const fs=require('node:fs'),assert=require('node:assert/strict');
      const {JSDOM}=require('jsdom'),{randomUUID}=require('node:crypto');
      const dom=new JSDOM(fs.readFileSync('app/enterprise/static/retention_index.html','utf8'),{url:'https://guard.example.test',runScripts:'outside-only'});
      const w=dom.window,doc=randomUUID(),due=randomUUID();w.crypto.randomUUID=randomUUID;
      w.fetch=async(path)=>{let data;if(path.endsWith('/me'))data={roles:['custodian'],csrf_cookie_name:'synthetic_csrf'};
        else if(path.endsWith('/due/'+due))data={id:due,document_id:doc,target_revision:1,target_version:1,revision:3,state:'issued',action:'suppress',purpose:'Synthetic purpose',purpose_version:randomUUID(),activity_id:randomUUID(),activity_revision:3,policy:{id:randomUUID(),bound_revision:2,current_revision:2,source_evidence_ref:randomUUID(),review_evidence_ref:randomUUID(),restriction_evidence_ref:randomUUID()},trigger:{id:randomUUID(),bound_revision:2,current_revision:2,source_evidence_ref:randomUUID(),review_evidence_ref:randomUUID(),occurred_at:'2026-11-01T00:00:00Z',kind:'record_closed'},due_at:'2026-11-02T00:00:00Z',approval_expires_at:null,approval_window_hours:24,can_approve:false,can_issue:false,blocked_reason:null};
        else if(path.endsWith('/disposition'))data={primary:{state:'suppressed',physical_erasure:false},copies:[{id:randomUUID(),kind:'backup',recipient_ref:randomUUID(),revision:1,state:'pending'},{id:randomUUID(),kind:'processor',recipient_ref:randomUUID(),revision:2,state:'failed'}]};
        else if(path.includes('/due?'))data={items:[{id:due,document_id:doc,target_revision:1,target_version:1,revision:3,state:'issued'}],next_cursor:null};
        else data={items:[],next_cursor:null};return {ok:true,status:200,json:async()=>data};};
      w.eval(fs.readFileSync('app/enterprise/static/retention_app.js','utf8'));
      const tick=async()=>{for(let i=0;i<20;i++)await Promise.resolve();};
      (async()=>{await tick();assert.equal(w.document.getElementById('policy-create-panel').hidden,true);
        const form=w.document.getElementById('scope-form');form.elements.collection_id.value=randomUUID();
        form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await tick();
        w.document.querySelector('#due button').click();await tick();
        assert(w.document.getElementById('primary-state').textContent.includes('ยังไม่ใช่การลบทางกายภาพ'));
        assert(w.document.getElementById('copy-status').textContent.includes('ข้อมูลสำรอง'));
        assert(w.document.getElementById('copy-status').textContent.includes('รอดำเนินการ'));
        assert(w.document.getElementById('copy-status').textContent.includes('ยังไม่สำเร็จ'));
        assert.equal(w.document.querySelector('#due-form button[value="approve"]').hidden,true);
        dom.window.close();})().catch(e=>{process.stderr.write(String(e));process.exitCode=1;});
    """
    result = subprocess.run(
        ["node", "-e", script], cwd=root, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr


def test_old_outcome_cannot_claim_current_disposition_after_target_change_without_database(
    monkeypatch,
):
    from contextlib import contextmanager
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from pii_redactor.governance import retention as module

    due_id, document_id, instruction_id = uuid4(), uuid4(), uuid4()
    due = {
        "due_id": due_id,
        "policy_id": uuid4(),
        "policy_revision": 2,
        "collection_id": uuid4(),
        "document_id": document_id,
        "target_revision": 1,
        "target_version": 1,
        "revision": 3,
        "state": "issued",
        "due_at": datetime.now(UTC),
        "instruction_id": instruction_id,
    }

    def execute(sql, *_args):
        if "governance_execution_outcomes" in sql:
            return SimpleNamespace(
                fetchone=lambda: {
                    "result_state": "suppressed",
                    "result_revision": 2,
                    "result_version": 1,
                    "verified_at": datetime.now(UTC),
                }
            )
        if "governance_managed_documents" in sql:
            return SimpleNamespace(
                fetchone=lambda: {
                    "state": "active",
                    "revision": 3,
                    "current_version": 2,
                    "last_instruction_id": uuid4(),
                }
            )
        return SimpleNamespace(fetchall=lambda: [])

    tx = SimpleNamespace(execute=execute)

    @contextmanager
    def transaction():
        yield tx

    store = SimpleNamespace(organization_id=uuid4(), lock=lambda _tx: None, transaction=transaction)
    retention = module.Retention(store)
    retention._due = lambda *_args: (due, {}, {})
    monkeypatch.setattr(module, "require_member", lambda *_args: {})
    result = retention.disposition(None, due_id)
    assert result["primary"]["state"] == "changed_after_action"
    assert result["primary"]["verification"] == "unverified_after_target_change"


@pytest.mark.parametrize("action", ["restrict", "suppress"])
@pytest.mark.parametrize("mode", ["approve", "issue"])
def test_due_ui_renders_exact_action_and_evidence_before_enabling_without_database(action, mode):
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = r"""
      const fs=require('node:fs'),assert=require('node:assert/strict');
      const {JSDOM}=require('jsdom'),{randomUUID}=require('node:crypto');
      const action=process.argv[1],mode=process.argv[2],id=randomUUID(),doc=randomUUID(),policy=randomUUID(),trigger=randomUUID(),evidence=randomUUID();
      const dom=new JSDOM(fs.readFileSync('app/enterprise/static/retention_index.html','utf8'),{url:'https://guard.example.test',runScripts:'outside-only'});
      const w=dom.window;w.crypto.randomUUID=randomUUID;let releaseDetail,detailCalls=0;
      const row={id,document_id:doc,target_revision:1,target_version:1,revision:mode==='approve'?1:2,state:mode==='approve'?'proposed':'approved'};
      const dto={...row,action,purpose:'Synthetic <img src=x> purpose',purpose_version:randomUUID(),activity_id:randomUUID(),activity_revision:3,
        policy:{id:policy,bound_revision:2,current_revision:2,state:'active',source_evidence_ref:evidence,review_evidence_ref:evidence,restriction_evidence_ref:evidence},
        trigger:{id:trigger,bound_revision:2,current_revision:2,state:'active',kind:'record_closed',occurred_at:'2026-11-01T00:00:00Z',source_evidence_ref:evidence,review_evidence_ref:evidence},
        due_at:'2026-11-02T00:00:00Z',approval_expires_at:mode==='issue'?new Date(Date.now()+3600000).toISOString():null,
        approval_window_hours:24,can_approve:mode==='approve',can_issue:mode==='issue',blocked_reason:null};
      w.fetch=async(path)=>{let data;
        if(path.endsWith('/me'))data={roles:[mode==='approve'?'privacy_reviewer':'data_steward'],csrf_cookie_name:'synthetic_csrf'};
        else if(path.endsWith('/due/'+id)){detailCalls++;await new Promise(resolve=>{releaseDetail=resolve});data=dto;}
        else if(path.endsWith('/disposition'))data={primary:{state:'pending'},copies:[]};
        else if(path.includes('/due?'))data={items:[row],next_cursor:null};
        else data={items:[],next_cursor:null};
        return {ok:true,status:200,json:async()=>data};};
      w.eval(fs.readFileSync('app/enterprise/static/retention_app.js','utf8'));
      const tick=async()=>{for(let i=0;i<20;i++)await Promise.resolve();};
      (async()=>{await tick();const approve=w.document.querySelector('#due-form button[value="approve"]'),issue=w.document.querySelector('#due-form button[value="issue"]');
        assert.equal(approve.disabled,true);assert.equal(issue.disabled,true);
        const form=w.document.getElementById('scope-form');form.elements.collection_id.value=randomUUID();
        form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await tick();
        w.document.querySelector('#due button').click();await tick();
        assert.equal(detailCalls,1);assert.equal(approve.disabled,true);assert.equal(issue.disabled,true);
        releaseDetail();await tick();
        const detail=w.document.getElementById('due-detail');assert(detail);
        assert(detail.textContent.includes(action==='restrict'?'จำกัดการเข้าถึงเชิงตรรกะ':'ระงับการเข้าถึงเชิงตรรกะ'));
        assert(!detail.textContent.includes(action==='restrict'?'ระงับการเข้าถึงเชิงตรรกะ':'จำกัดการเข้าถึงเชิงตรรกะ'));
        for(const value of [policy,trigger,evidence,dto.purpose_version,'2026-11-02T00:00:00Z'])assert(detail.textContent.includes(value));
        assert(detail.textContent.includes(mode==='issue'?dto.approval_expires_at:'24 ชั่วโมงหลังอนุมัติ'));
        assert(detail.textContent.includes('ฉบับ 2'));assert(detail.textContent.includes('Synthetic <img src=x> purpose'));
        assert.equal(detail.querySelector('img'),null);
        assert.equal(approve.disabled,mode!=='approve');assert.equal(issue.disabled,mode!=='issue');
        dom.window.close();})().catch(e=>{process.stderr.write(String(e));process.exitCode=1;});
    """
    result = subprocess.run(
        ["node", "-e", script, action, mode], cwd=root, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("action", ["restrict", "suppress"])
def test_database_exact_due_detail_authorizes_scope_and_distinguishes_action(
    retention_context, action
):
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient

    from app.enterprise.retention_routes import build_retention_router
    from pii_redactor.governance.errors import GovernanceError
    from pii_redactor.governance.holds import Holds

    c = retention_context
    policy, due = prepared_due(c, action=action)
    app = FastAPI()
    actor = {"principal": c.b}

    @app.exception_handler(GovernanceError)
    async def rejected(_request, error):
        return JSONResponse(
            {"error": {"code": error.code}},
            status_code=404 if error.code == "record_unavailable" else 403,
        )

    app.include_router(
        build_retention_router(
            c.retention, Holds(c.store), lambda _request, **_kwargs: actor["principal"]
        )
    )
    with TestClient(app) as client:
        path = "/api/enterprise/v1/retention/due/" + due["id"]
        response = client.get(path)
        assert response.status_code == 200
        detail = response.json()
        assert detail["action"] == action and detail["purpose_version"] == c.purpose
        assert (
            detail["policy"]["id"] == policy["id"]
            and detail["policy"]["bound_revision"] == policy["revision"]
        )
        assert detail["trigger"]["bound_revision"] == 2 and detail["trigger"]["review_evidence_ref"]
        assert detail["trigger"]["source_evidence_ref"] and detail["due_at"] == due["due_at"]
        assert detail["approval_expires_at"] is None and detail["can_approve"] is True
        c.retention.approve_due(c.b, uuid4(), due["id"], 1, uuid4())
        actor["principal"] = c.a
        detail = client.get(path).json()
        assert (
            detail["approval_expires_at"]
            and detail["can_issue"] is True
            and detail["can_approve"] is False
        )
        actor["principal"] = c.c
        denied = client.get(path)
        assert denied.status_code == 404
        assert policy["id"] not in denied.text and c.purpose not in denied.text
