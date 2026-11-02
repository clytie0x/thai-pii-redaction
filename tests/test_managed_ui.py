"""Synthetic DOM regressions using the already locked optional jsdom toolchain."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("psycopg", reason="optional enterprise PostgreSQL dependency")

ROOT = Path(__file__).resolve().parents[1]
NODE_MODULES = ROOT / "node_modules"

HARNESS = r"""
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),{JSDOM}=require('jsdom');
const {mountManaged}=await import('./app/enterprise/static/managed_app.js');
const dom=new JSDOM(readFileSync('./app/enterprise/static/managed_index.html','utf8'),{url:'https://local.example.test/managed'});
dom.window.HTMLElement.prototype.scrollIntoView=function(){};
const root=dom.window.document,$=id=>root.querySelector('#managed-'+id);
root.cookie='csrf=synthetic-csrf';
const ids={a:'10000000-0000-4000-8000-000000000001',b:'10000000-0000-4000-8000-000000000002',c:'10000000-0000-4000-8000-000000000003',d:'10000000-0000-4000-8000-000000000004'};
let me={id:ids.a,roles:['data_steward','custodian'],departments:['operations'],csrf_cookie_name:'csrf',session:{idle_seconds:600,absolute_remaining_seconds:600}};
const bucket={id:ids.c,department_id:'operations',revision:1,state:'ready',consent_bound:false},doc={id:ids.d,collection_id:ids.c,version:1,revision:1,state:'active'};
const calls=[],posts=[];let lateRead=null,deferRead=false;
const response=(data,status=200)=>({ok:status<400,status,json:async()=>data});
const fetcher=async(path,options={})=>{
  calls.push(path);
  if(options.method==='POST'){posts.push(JSON.parse(options.body));throw new Error('synthetic transport ambiguity');}
  if(path==='/api/enterprise/v1/me')return response(structuredClone(me));
  if(path.endsWith('/recovery/collections'))return response({items:[bucket]});
  if(path.endsWith('/collections'))return me.roles.includes('system_administrator')&&me.roles.length===1?response({error:{code:'forbidden'}},403):response({items:[bucket]});
  if(path.includes('/versions/')){if(deferRead)return await new Promise(resolve=>{lateRead=resolve;});return response({...doc,content_type:'text/plain',content:'Synthetic source'});}
  if(path.endsWith('/documents'))return response({items:[doc]});
  if(path.endsWith('/instructions'))return response({items:[]});
  if(path.endsWith('/activities'))return response([]);
  throw new Error('unexpected synthetic route');
};
const settle=async()=>{for(let i=0;i<15;i++)await new Promise(resolve=>setImmediate(resolve));};
const submitUpload=async()=>{$('upload').elements.content.value='Synthetic ambiguous draft';$('upload').dispatchEvent(new dom.window.Event('submit',{bubbles:true,cancelable:true}));await settle();};
let app;
try{
  if(process.env.MANAGED_UI_CASE==='admin')me={...me,roles:['system_administrator']};
  app=mountManaged({root,fetcher});await app.ready;
  if(process.env.MANAGED_UI_CASE==='admin'){
    assert(calls.some(path=>path.endsWith('/recovery/collections')),'plain admin must use scoped recovery metadata');
    assert(!calls.some(path=>path.endsWith('/documents')||path.endsWith('/instructions')),'plain admin must not request protected readers');
    assert.equal($('recovery-panel').hidden,false);assert.equal($('snapshot').hidden,false);
    assert.equal($('upload').hidden,true);assert.equal($('proposal-panel').hidden,true);
  }else if(process.env.MANAGED_UI_CASE==='principal'){
    await submitUpload();const first=posts[0].command_key;
    $('propose').elements.correction.value='Synthetic private correction';
    me={...me,id:ids.b};$('refresh').click();await settle();
    assert.equal($('upload').elements.content.value,'','principal change must clear old raw draft');
    assert.equal($('propose').elements.correction.value,'','principal change must clear old correction');
    await submitUpload();assert.notEqual(posts[1].command_key,first,'new principal must not reuse prior command key');
  }else if(process.env.MANAGED_UI_CASE==='authority'){
    await submitUpload();const first=posts[0].command_key;
    me={...me,departments:['operations','finance']};$('refresh').click();await settle();
    assert.equal($('upload').elements.content.value,'','authority scope change must clear raw draft');
    await submitUpload();assert.notEqual(posts[1].command_key,first,'changed authority must not reuse command key');
  }else if(process.env.MANAGED_UI_CASE==='same'){
    await submitUpload();const first=posts[0].command_key;
    $('refresh').click();await settle();await submitUpload();
    assert.equal(posts[1].command_key,first,'same authority must preserve ambiguous retry key');
  }else if(process.env.MANAGED_UI_CASE==='pending'){
    deferRead=true;const button=[...$('documents').querySelectorAll('button')].find(node=>node.textContent==='อ่านรุ่นปัจจุบัน');button.click();await settle();assert(lateRead);
    me={...me,id:ids.b};$('refresh').click();await settle();
    lateRead(response({...doc,content_type:'text/plain',content:'Synthetic prior principal content'}));await settle();
    assert.equal($('content').textContent,'','prior principal pending response must be discarded');
    assert.equal($('content').hidden,true);
  }
}finally{app?.dispose();dom.window.close();}
"""


@pytest.mark.parametrize("case", ["admin", "principal", "authority", "same", "pending"])
def test_managed_ui_recovery_and_authority_context(case):
    node = shutil.which("node")
    module_path = os.environ.get("NODE_PATH", str(NODE_MODULES))
    if not node or not any(
        (Path(path) / "jsdom").is_dir() for path in module_path.split(os.pathsep)
    ):
        pytest.skip("optional locked Node/jsdom toolchain unavailable")
    environment = {**os.environ, "NODE_PATH": module_path, "MANAGED_UI_CASE": case}
    result = subprocess.run(
        [node, "--input-type=module"],
        input=HARNESS,
        text=True,
        encoding="utf-8",
        capture_output=True,
        cwd=ROOT,
        env=environment,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
