import { afterEach, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { mountProcessing } from "../../app/enterprise/static/processing_controls_app.js";
import { mountManaged } from "../../app/enterprise/static/managed_app.js";

const id="10000000-0000-4000-8000-000000000001",activity="20000000-0000-4000-8000-000000000001";
const keys=["scope_roles","consent_notice","processing_conditions","international_transfers","rights","security_retention_incidents","responsibility_records_processors","dpo"];
const legal=keys.map((key,index)=>({id:`30000000-0000-4000-8000-${String(index+1).padStart(12,"0")}`,revision:4,kind:"legal",usable:true,data:{control_key:key,applicability:"reviewed_not_applicable"}}));
const data={activity_id:activity,activity_revision:3,controls:legal.map(row=>({id:row.id,revision:row.revision})),evidence_ref:id,expires_at:"2099-01-01T00:00:00Z"};
const row={id,revision:2,state:"submitted",proposed_by:"writer",activity_id:activity,activity_revision:3,data};
const writer={id:"writer",roles:["data_steward"],departments:["operations"],csrf_cookie_name:"processing_csrf"};
const reviewer={...writer,id:"reviewer",roles:["privacy_reviewer"]};
const response=(value,status=200)=>({ok:status<300,status,json:async()=>value});
const tick=async()=>{for(let i=0;i<80;i++)await Promise.resolve();};
let app;
afterEach(()=>{app?.dispose();vi.restoreAllMocks();});
function page(){document.body.innerHTML=readFileSync("app/enterprise/static/processing_controls_index.html","utf8");document.cookie="processing_csrf=synthetic; Path=/";}
function get(url,me=reviewer,rows=[row]){
  return url.endsWith("/me")?me:url.includes("/controls?")?{legal,items:[],required_keys:keys,next_cursor:null}:
    url.includes("/activities?")?{items:[{id:activity,revision:3,purpose:"Synthetic reviewed activity"}],next_cursor:null}:
    url.includes("/processing?")?{items:rows,next_cursor:null}:row;
}

it("requires explicit eight-control selection and reuses an uncertain command",async()=>{
  page();const posts=[];let committed;
  const fetcher=vi.fn(async(url,options)=>{
    if(options.method==="POST"){
      posts.push(JSON.parse(options.body));committed={...row,revision:1,state:"draft",data:posts[0].data};
      if(posts.length===1)throw new Error("Synthetic response lost after commit");
      return response(committed);
    }
    return response(url.endsWith("/"+id)&&committed?committed:get(url,writer,committed?[committed]:[]));
  });
  app=mountProcessing({fetcher});await app.ready;
  expect(document.querySelectorAll("#pc-legal input:checked")).toHaveLength(0);
  const fill=()=>{document.getElementById("pc-activity").value=activity;document.getElementById("pc-evidence").value=id;document.getElementById("pc-expiry").value="2099-01-01T00:00";for(const input of document.querySelectorAll("#pc-legal input"))input.checked=true;};
  const submit=()=>document.getElementById("pc-editor").dispatchEvent(new Event("submit",{bubbles:true,cancelable:true}));
  fill();submit();await tick();submit();await tick();
  expect(posts).toHaveLength(2);expect(posts[0]).toEqual(posts[1]);expect(posts[0].data.controls).toHaveLength(8);
  expect(fetcher.mock.calls.filter(([,options])=>options.method==="POST")[0][1].headers["X-CSRF-Token"]).toBe("synthetic");
  document.getElementById("pc-new").click();fill();submit();await tick();
  expect(posts[2].command_key).not.toBe(posts[1].command_key);
});

it("requires a rendered exact preview before independent review and activation",async()=>{
  page();const posts=[];let current=row;
  const fetcher=vi.fn(async(url,options)=>{
    if(options.method==="POST"){
      posts.push([url,JSON.parse(options.body)]);
      if(url.endsWith("/preview"))return response({id,revision:2,controls:legal,dependencies:[{data:{instrument:{version:"<img src=x onerror=alert(1)>",sha256:"0".repeat(64)}}}],digest:"a".repeat(64)});
      current={...row,revision:url.endsWith("/activate")?4:3,state:url.endsWith("/activate")?"active":"reviewed",usable:true};return response(current);
    }
    return response(url.endsWith("/"+id)?current:get(url));
  });
  app=mountProcessing({fetcher});await app.ready;document.querySelector("#pc-records button").click();await tick();
  expect(document.getElementById("pc-approve").disabled).toBe(true);
  document.getElementById("pc-preview").click();await tick();
  expect(document.getElementById("pc-approve").disabled).toBe(false);
  expect(document.querySelector("#pc-preview-detail img")).toBeNull();
  expect(document.getElementById("pc-preview-detail").textContent).toContain("<img");
  document.getElementById("pc-review-evidence").value=id;document.getElementById("pc-approve").click();await tick();
  expect(posts[1][1].expected_revision).toBe(2);expect(posts[1][1].decision).toBe("approve");
  expect(document.getElementById("pc-activate").disabled).toBe(false);
  document.getElementById("pc-activate").click();await tick();expect(posts[2][1].expected_revision).toBe(3);
});

it("drops a pending evidence preview after page exit",async()=>{
  page();let finish;
  const fetcher=vi.fn(async(url)=>url.endsWith("/preview")?await new Promise(resolve=>{finish=resolve;}):response(get(url)));
  app=mountProcessing({fetcher});await app.ready;document.querySelector("#pc-records button").click();await tick();
  document.getElementById("pc-preview").click();await tick();window.dispatchEvent(new Event("pagehide"));
  finish(response({controls:legal,canary:"Synthetic late protected metadata"}));await tick();
  expect(document.getElementById("pc-preview-detail").textContent).toBe("");
  expect(document.getElementById("pc-detail").textContent).toBe("");
  expect(document.getElementById("pc-workspace").hidden).toBe(true);
});

it("clears stale selection and blocks its approval after a conflict",async()=>{
  page();const draft={...row,state:"draft",revision:1};const fetcher=vi.fn(async(url,options)=>options.method==="POST"?response({error:{code:"revision_conflict"}},409):response(url.endsWith("/"+id)?draft:get(url,writer,[draft])));
  app=mountProcessing({fetcher});await app.ready;document.querySelector("#pc-records button").click();await tick();
  document.getElementById("pc-submit").click();await tick();
  expect(document.getElementById("pc-detail").textContent).toBe("");expect(document.getElementById("pc-submit").disabled).toBe(true);
});

it("does not repopulate a new draft when an old create returns late",async()=>{
  page();let finish;
  const fetcher=vi.fn(async(url,options)=>options.method==="POST"?await new Promise(resolve=>{finish=resolve;}):response(get(url,writer,[])));
  app=mountProcessing({fetcher});await app.ready;
  document.getElementById("pc-activity").value=activity;document.getElementById("pc-evidence").value=id;document.getElementById("pc-expiry").value="2099-01-01T00:00";
  for(const input of document.querySelectorAll("#pc-legal input"))input.checked=true;
  document.getElementById("pc-editor").dispatchEvent(new Event("submit",{bubbles:true,cancelable:true}));await tick();
  document.getElementById("pc-new").click();finish(response({...row,state:"draft"}));await tick();
  expect(document.getElementById("pc-detail").textContent).toBe("");
});

it("shows exact control and source evidence to the managed instruction reviewer",async()=>{
  document.body.innerHTML=readFileSync("app/enterprise/static/managed_index.html","utf8");
  document.cookie="processing_csrf=synthetic; Path=/";
  const instruction={id,document_id:activity,action:"restrict",state:"proposed",primary_verified:false,
    proposed_by:"writer",target_version:1,target_revision:1,expires_at:"2099-01-01T00:00:00Z",
    processing_controls:{id:activity,revision:4,digest:"a".repeat(64),reviewed_by:"reviewer",review_evidence_ref:id,
      controls:legal,dependencies:[{data:{instrument:{version:"Synthetic reviewed source",sha256:"b".repeat(64)}}}]}};
  const fetcher=vi.fn(async url=>response(url.endsWith("/me")?{...reviewer,session:{idle_seconds:600,absolute_remaining_seconds:600}}:
    url.endsWith("/instructions")?{items:[instruction]}:{items:[]}));
  app=mountManaged({root:document,fetcher});await app.ready;
  const content=document.getElementById("managed-instructions").textContent;
  expect(content).toContain(activity);expect(content).toContain("ฉบับ 4");expect(content).toContain("Synthetic reviewed source");
  expect(content).toContain("a".repeat(64));expect(content).toContain("b".repeat(64));
});

it("reloads current state instead of displaying a replayed historical receipt as live",async()=>{
  page();let posted=false;const draft={...row,revision:1,state:"draft"};
  const fetcher=vi.fn(async(url,options)=>{
    if(options.method==="POST"){posted=true;return response(row);}
    return response(url.endsWith("/"+id)?posted?{...row,revision:5,state:"superseded"}:draft:get(url,writer,[draft]));
  });
  app=mountProcessing({fetcher});await app.ready;document.querySelector("#pc-records button").click();await tick();
  document.getElementById("pc-submit").click();await tick();
  expect(document.getElementById("pc-selected").textContent).toContain("ฉบับ 5");
  expect(document.getElementById("pc-selected").textContent).toContain("มีฉบับใหม่แทน");
  expect(document.getElementById("pc-activate").disabled).toBe(true);
});
