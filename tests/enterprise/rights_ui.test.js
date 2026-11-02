import { afterEach, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { mountRightsStaff, mountRightsSubject } from '../../app/enterprise/static/rights_ui.js';

const id='11111111-1111-4111-8111-111111111111';
const me={roles:['case_manager','privacy_reviewer'],csrf_cookie_name:'rights_csrf'};
const response=(data,status=200)=>({ok:status<300,status,json:async()=>data});
const row={id,revision:4,state:'planned',subject_id:id,link_revision:1,intake:{rights:['access'],original_receipt_ref:id},plan_version:1,plan:{targets:[],manual:[],refusals:[]},manual:[],history:[]};
let mounted;
afterEach(()=>{mounted?.dispose();vi.restoreAllMocks();});
function page(lane){document.body.innerHTML=readFileSync(`app/enterprise/static/rights_${lane}.html`,'utf8');document.cookie='rights_csrf=synthetic; Path=/';}
const tick=async()=>{for(let i=0;i<30;i++)await Promise.resolve();};

it('loads staff scoped cases and a versioned review with no automatic approval',async()=>{
  page('staff');const fetcher=vi.fn(async url=>response(url.endsWith('/me')?me:url.includes('?')?{items:[row],next_cursor:null}:row));
  mounted=mountRightsStaff({fetcher});await mounted.ready;await mounted.select(id);
  expect(document.getElementById('selected').textContent).toContain('ฉบับ 4');
  expect(document.querySelectorAll('#clocks fieldset')).toHaveLength(1);
  expect(document.querySelector('#clocks select[name=applicability]').value).toBe('unknown');
  expect(fetcher.mock.calls.every(([,options])=>options.cache==='no-store')).toBe(true);
});

it('uses textContent for private previews and clears them on lifecycle exit',async()=>{
  page('staff');const fetcher=vi.fn(async url=>response(url.endsWith('/me')?me:url.includes('?')?{items:[],next_cursor:null}:url.endsWith('/preview')?{content:'<img src=x onerror=alert(1)>'}:row));
  mounted=mountRightsStaff({fetcher});await mounted.ready;await mounted.select(id);document.getElementById('preview').click();await tick();
  expect(document.querySelector('#preview-content img')).toBeNull();expect(document.getElementById('preview-content').textContent).toContain('<img');
  window.dispatchEvent(new Event('pagehide'));expect(document.getElementById('preview-content').textContent).toBe('');
});

it('submits explicit right-specific clocks without inventing deadlines',async()=>{
  page('staff');let submitted;
  const fetcher=vi.fn(async(url,options)=>{if(url.endsWith('/verify')){submitted=JSON.parse(options.body);return response({...row,state:'verified'});}return response(url.endsWith('/me')?me:url.includes('?')?{items:[],next_cursor:null}:row);});
  mounted=mountRightsStaff({fetcher});await mounted.ready;await mounted.select(id);
  const form=document.getElementById('verify');form.elements.identity_ref.value=id;form.elements.capacity_ref.value=id;form.elements.completeness_ref.value=id;
  form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await tick();
  expect(submitted.data.clocks[0].due_at).toBeNull();expect(submitted.data.clocks[0].applicability).toBe('unknown');expect(submitted.expected_revision).toBe(4);
  expect(submitted.data).not.toHaveProperty('law_version');expect(submitted.data).not.toHaveProperty('applicability');
});

it('subject download remains unfulfilled until a separate explicit receipt',async()=>{
  page('subject');const fetcher=vi.fn(async(url)=>response(url.endsWith('/me')?me:url.endsWith('/consume')?{id,revision:2,content:'Synthetic private export',receipt_token:id,fulfilled:false}:url.endsWith('/receipt')?{fulfilled:true}:{items:[]}));
  mounted=mountRightsSubject({fetcher});await mounted.ready;await mounted.consume(id);
  expect(document.getElementById('package').hidden).toBe(false);expect(fetcher.mock.calls.some(([u])=>u.endsWith('/receipt'))).toBe(false);
  document.getElementById('acknowledge').click();await tick();expect(fetcher.mock.calls.some(([u])=>u.endsWith('/receipt'))).toBe(true);expect(document.getElementById('export-content').textContent).toBe('');
});

it('blocks a late private response after page exit',async()=>{
  page('subject');let finish;
  const fetcher=vi.fn(async url=>url.endsWith('/consume')?await new Promise(resolve=>{finish=resolve;}):response(url.endsWith('/me')?me:{items:[]}));
  mounted=mountRightsSubject({fetcher});await mounted.ready;const pending=mounted.consume(id);await tick();window.dispatchEvent(new Event('pagehide'));finish(response({id,revision:2,content:'Synthetic late export',receipt_token:id}));await pending;
  expect(document.getElementById('package').hidden).toBe(true);expect(document.getElementById('export-content').textContent).toBe('');
});

it('clears subject content and disables receipt on session failure',async()=>{
  page('subject');const fetcher=vi.fn(async url=>response(url.endsWith('/me')?me:url.endsWith('/consume')?{id,revision:2,content:'Synthetic export',receipt_token:id}:url.endsWith('/receipt')?{error:{code:'authentication_required'}}:{items:[]},url.endsWith('/receipt')?401:200));
  mounted=mountRightsSubject({fetcher});await mounted.ready;await mounted.consume(id);document.getElementById('acknowledge').click();await tick();
  expect(document.getElementById('workspace').hidden).toBe(true);expect(document.getElementById('export-content').textContent).toBe('');expect(document.getElementById('acknowledge').disabled).toBe(true);
});

it('retains one command key for an uncertain network retry',async()=>{
  page('subject');let attempts=0;const bodies=[];
  const fetcher=vi.fn(async(url,options)=>{if(url.endsWith('/consume')){bodies.push(JSON.parse(options.body));if(!attempts++)throw new Error('synthetic network');return response({id,revision:2,content:'Synthetic export',receipt_token:id});}return response(url.endsWith('/me')?me:{items:[]});});
  mounted=mountRightsSubject({fetcher});await mounted.ready;await mounted.consume(id);await mounted.consume(id);expect(bodies[0].command_key).toBe(bodies[1].command_key);
});
