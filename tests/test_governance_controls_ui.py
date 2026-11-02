"""Synthetic DOM positive and failure paths, using the locked jsdom cache."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_governance_ui_scoped_review_stale_and_identity_reset():
    if not shutil.which("node") or not any(
        (Path(p) / "jsdom").is_dir()
        for p in os.environ.get(
            "NODE_PATH", str(Path(__file__).resolve().parents[1] / "node_modules")
        ).split(os.pathsep)
    ):
        pytest.skip("optional locked Node/jsdom toolchain unavailable")
    harness = r"""
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{JSDOM}=require('jsdom');
const {mountGovernance}=await import('./app/enterprise/static/governance_app.js');
const dom=new JSDOM(readFileSync('app/enterprise/static/governance_index.html','utf8'),{url:'https://guard.example.test/governance'});
const doc=dom.window.document, $=id=>doc.getElementById(id), settle=()=>new Promise(r=>setTimeout(r,15));
let posts=[], fail=false, me={id:'reviewer',roles:['privacy_reviewer'],departments:['operations'],csrf_cookie_name:'csrf'};
doc.cookie='csrf=synthetic';
const row={id:'10000000-0000-4000-8000-000000000001',revision:2,kind:'policy',state:'submitted',proposed_by:'steward',data:{department_id:'operations'},usable:false};
const schema={type:'object',properties:{department_id:{type:'string'},policy_kind:{enum:['security','source']}}};
async function fetch(url,options={}){
 if(options.method==='POST'){posts.push(JSON.parse(options.body));return {ok:false,status:409,json:async()=>({error:{code:'revision_conflict'}})};}
 const result=url.endsWith('/me')?me:url.endsWith('/schemas')?{policy:schema}:url.includes('/release-findings')?{blocked:true,items:[{control_key:'dpo',decision:'unresolved'}]}:url.includes(row.id)?row:{items:[row]};
 return {ok:true,status:200,json:async()=>result};
}
const app=await mountGovernance(doc,fetch);
$('gov-department').value='operations';$('gov-load').click();await settle();
assert($('gov-list').textContent.includes('10000000'));
$('gov-list').querySelector('button').click();await settle();
assert.equal($('gov-review').disabled,false);
assert.equal($('gov-activate').disabled,true);
$('gov-evidence').value='10000000-0000-4000-8000-000000000002';
$('gov-review').click();await settle();
assert.equal(posts[0].expected_revision,2);
assert.equal($('gov-review').disabled,true,'stale detail must be discarded');
assert($('gov-message').textContent.includes('ฉบับ'));
me={...me,id:'admin',roles:['system_administrator']};$('gov-refresh').click();await settle();
assert.equal($('gov-detail').textContent,'');assert.equal($('gov-review').disabled,true);
app.dispose();dom.window.close();
"""
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module"],
        input=harness,
        text=True,
        encoding="utf-8",
        capture_output=True,
        cwd=Path(__file__).resolve().parents[1],
        env=os.environ,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
