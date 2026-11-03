import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { mountApp } from "../../app/enterprise/static/app.js";

const id = "11111111-1111-4111-8111-111111111111";
const record = (title="Synthetic processing") => ({
  id, state:"draft", revision:1,
  data:{department_id:"operations",title,purpose:"Synthetic support",necessity:"Contact requester",
    categories:["CONTACT"],general_basis:"contract",sensitive_condition:null,retention_rule:"Thirty days",
    destination:"Local storage",source_refs:["source:synthetic"],subject_groups:["customers"],recipient_refs:["local"]},
  review:null,created_by:id,last_editor:id,submitted_by:null,reviewed_by:null,reviewed_at:null,
  review_evidence_mode:null,legal_clearance:false,
});
const me = {id,roles:["data_steward"],departments:["operations"],csrf_cookie_name:"aiguard_dev_csrf",
  session:{idle_seconds:1800,absolute_remaining_seconds:28800}};
const catalog = {categories:[{code:"CONTACT",sensitive:false},{code:"HEALTH",sensitive:true}],
  bases:["contract","consent"],sensitive_conditions:["explicit_consent"],roles:["data_steward","privacy_reviewer"]};
const response = (data,status=200) => ({ok:status>=200&&status<300,status,json:async()=>data});
let app;
beforeEach(()=>{
  document.body.innerHTML = readFileSync("app/enterprise/static/index.html","utf8");
  document.cookie="aiguard_dev_csrf=synthetic-csrf; Path=/";
});
afterEach(()=>{app?.dispose();vi.useRealTimers();vi.restoreAllMocks();});
const tick = async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
const handler = (overrides={}) => vi.fn(async(path,options={})=>{
  const route=path.split("?")[0];
  if(overrides[route])return overrides[route](options);
  if(route.endsWith("/me"))return response(me);
  if(route.endsWith("/catalog"))return response(catalog);
  if(route.endsWith("/activities")||route.endsWith("/notices"))return response([]);
  throw new Error("Unexpected test route");
});

describe("enterprise caller flow",()=>{
  it("shows organization login without a fabricated dashboard",async()=>{
    app=mountApp({fetcher:handler({"/api/enterprise/v1/me":()=>response({error:{code:"authentication_required"}},401)})});
    await app.start();
    expect(document.querySelector("#welcome").hidden).toBe(false);
    expect(document.querySelector("#workspace").hidden).toBe(true);
    expect(document.querySelector('a[href="/auth/login"]')).not.toBeNull();
  });

  it("renders record text without executing HTML",async()=>{
    app=mountApp({fetcher:handler({"/api/enterprise/v1/activities":()=>response([record('<img src=x onerror="evil()">')])})});
    await app.start();
    expect(document.querySelector("#records").textContent).toContain("<img src=x");
    expect(document.querySelector("#records img")).toBeNull();
  });

  it("clears already displayed data when the server revokes the session",async()=>{
    let revoked=false;
    app=mountApp({fetcher:handler({"/api/enterprise/v1/me":()=>revoked?response({error:{code:"authentication_required"}},401):response(me),
      "/api/enterprise/v1/activities":()=>response([record()])})});
    await app.start(); revoked=true; await app.start();
    expect(document.querySelector("#workspace").hidden).toBe(true);
    expect(document.querySelector("#records").textContent).not.toContain("Synthetic processing");
  });

  it("rejects malformed success rather than offering unsafe actions",async()=>{
    app=mountApp({fetcher:handler({"/api/enterprise/v1/activities":()=>response([{id:"wrong",state:"active"}])})});
    await app.start();
    expect(document.querySelector("#status").textContent).toContain("รูปแบบข้อมูล");
    expect(document.querySelector("#records").children.length).toBe(0);
  });

  it("uses the same command key for a retry after uncertain network failure",async()=>{
    const keys=[];
    const fetcher=handler({"/api/enterprise/v1/activities":async(options)=>{
      if(options.method!=="POST")return response([]);
      keys.push(JSON.parse(options.body).command_key);
      if(keys.length===1)throw new Error("network");
      return response(record("New processing"));
    }});
    app=mountApp({fetcher}); await app.start();
    document.querySelector("#new-activity").click();
    const form=document.querySelector("#activity-form");
    form.elements.title.value="New processing";form.elements.purpose.value="Synthetic purpose";
    form.elements.department_id.value="operations";
    form.querySelector('[name="categories"][value="CONTACT"]').checked=true;
    form.dispatchEvent(new Event("submit",{bubbles:true,cancelable:true})); await tick();
    form.dispatchEvent(new Event("submit",{bubbles:true,cancelable:true})); await tick();
    expect(keys).toHaveLength(2);expect(keys[0]).toBe(keys[1]);
  });

  it("clears protected content when the idle deadline passes",async()=>{
    vi.useFakeTimers();
    app=mountApp({fetcher:handler({"/api/enterprise/v1/me":()=>response({...me,session:{idle_seconds:1,absolute_remaining_seconds:5}}),
      "/api/enterprise/v1/activities":()=>response([record()])})});
    await app.start();await vi.advanceTimersByTimeAsync(1100);
    expect(document.querySelector("#workspace").hidden).toBe(true);
    expect(document.querySelector("#records").textContent).toBe("");
  });

  it("never writes staff content or credentials to browser storage",async()=>{
    const stored=vi.spyOn(Storage.prototype,"setItem");
    app=mountApp({fetcher:handler()}); await app.start();
    expect(stored).not.toHaveBeenCalled();
  });

  it("rejects unexpected mapping fields in a success projection",async()=>{
    app=mountApp({fetcher:handler({"/api/enterprise/v1/activities":()=>response([{...record(),mapping:{token:"unexpected-value"}}])})});
    await app.start();
    expect(document.querySelector("#status").textContent).toContain("รูปแบบข้อมูล");
    expect(document.querySelector("#records").children.length).toBe(0);
  });

  it("removes detail text as well as the list when authorization ends",async()=>{
    let revoked=false;
    const privateRecord=record("Private detail marker");
    app=mountApp({fetcher:handler({
      "/api/enterprise/v1/me":()=>revoked?response({error:{code:"authentication_required"}},401):response(me),
      "/api/enterprise/v1/activities":()=>response([privateRecord]),
      ["/api/enterprise/v1/activities/"+id]:()=>response(privateRecord),
    })});
    await app.start();document.querySelector("#records button").click();
    await vi.waitFor(()=>expect(document.querySelector("#detail-title").textContent).toBe("Private detail marker"));
    revoked=true;await app.start();
    expect(document.body.textContent).not.toContain("Private detail marker");
  });

  it("accepts the minimized enrollment receipt and refreshes the real grant view",async()=>{
    let submitted=false;
    const target="22222222-2222-4222-8222-222222222222";
    const grant="33333333-3333-4333-8333-333333333333";
    app=mountApp({fetcher:handler({
      "/api/enterprise/v1/me":()=>response({...me,roles:["system_administrator"]}),
      "/api/enterprise/v1/members":options=>{
        if(options.method==="POST"){submitted=true;return response({id:grant,state:"proposed",revision:1});}
        return response(submitted?[{id:target,issuer:"https://staff.example.test",subject:"new-synthetic-subject",roles:["data_steward"],departments:["operations"],enabled:false,revision:1}]:[]);
      },
      "/api/enterprise/v1/grants":()=>response(submitted?[{id:grant,target_id:target,proposed_by:id,approved_by:null,roles:["data_steward"],departments:["operations"],enabled_change:true,state:"proposed",revision:1,target_revision:1}]:[]),
    })});
    await app.start();
    const form=document.querySelector("#enrollment-form");
    form.elements.subject.value="new-synthetic-subject";
    form.elements.roles.options[0].selected=true;form.elements.departments.value="operations";
    form.dispatchEvent(new Event("submit",{bubbles:true,cancelable:true}));
    await vi.waitFor(()=>expect(document.querySelector("#status").textContent).toContain("ส่งข้อเสนอเพิ่มเจ้าหน้าที่แล้ว"));
    expect(document.querySelector("#members").textContent).toContain("new-synthetic-subject");
    expect(document.querySelector("#status").classList.contains("error")).toBe(false);
  });

  it("invalidates private detail when another tab replaces the principal",async()=>{
    let current=me;
    app=mountApp({fetcher:handler({
      "/api/enterprise/v1/me":()=>response(current),
      "/api/enterprise/v1/activities":()=>response(current.id===id?[record("Old principal private detail")]:[]),
      ["/api/enterprise/v1/activities/"+id]:()=>response(record("Old principal private detail")),
    })});await app.start();document.querySelector("#records button").click();
    await vi.waitFor(()=>expect(document.querySelector("#detail-title").textContent).toContain("Old principal"));
    current={...me,id:"44444444-4444-4444-8444-444444444444",departments:["finance"]};
    window.dispatchEvent(new Event("focus"));
    await vi.waitFor(()=>expect(document.querySelector("#session-scope").textContent).toContain("finance"));
    expect(document.body.textContent).not.toContain("Old principal private detail");
    expect(document.querySelector("#activity-detail").hidden).toBe(true);
  });

  it("does not carry notice and review drafts to a different activity",async()=>{
    const other="22222222-2222-4222-8222-222222222222";
    const a={...record("Record A"),state:"submitted"};const b={...record("Record B"),id:other,state:"submitted"};
    app=mountApp({fetcher:handler({
      "/api/enterprise/v1/me":()=>response({...me,id:"44444444-4444-4444-8444-444444444444",roles:["data_steward","privacy_reviewer"]}),
      "/api/enterprise/v1/activities":()=>response([a,b]),
      ["/api/enterprise/v1/activities/"+id]:()=>response(a),["/api/enterprise/v1/activities/"+other]:()=>response(b),
    })});await app.start();
    const dialog=document.querySelector("#confirmation");dialog.showModal=()=>{dialog.returnValue="confirm";dialog.dispatchEvent(new Event("close"));};
    document.querySelectorAll("#records button")[0].click();await vi.waitFor(()=>expect(document.querySelector("#detail-title").textContent).toBe("Record A"));
    document.querySelector("#notice-form").elements.body.value="Notice written for Record A only";
    document.querySelector("#review-form").elements.reason.value="Review evidence for Record A only";
    document.querySelectorAll("#records button")[1].click();await vi.waitFor(()=>expect(document.querySelector("#detail-title").textContent).toBe("Record B"));
    expect(document.querySelector("#notice-form").elements.body.value).toBe("");
    expect(document.querySelector("#review-form").elements.reason.value).toBe("");
  });

  it("shows sensitive inventory categories to a reviewer without edit access",async()=>{
    const value={...record(),state:"submitted",data:{...record().data,categories:["HEALTH"]}};
    app=mountApp({fetcher:handler({
      "/api/enterprise/v1/me":()=>response({...me,id:"44444444-4444-4444-8444-444444444444",roles:["privacy_reviewer"]}),
      "/api/enterprise/v1/activities":()=>response([value]),["/api/enterprise/v1/activities/"+id]:()=>response(value),
    })});await app.start();document.querySelector("#records button").click();
    await vi.waitFor(()=>expect(document.querySelector("#detail-title").textContent).toBe(value.data.title));
    expect(document.querySelector("#detail-values").textContent).toContain("สุขภาพ");
    expect(document.querySelector("#detail-values").textContent).toContain("อ่อนไหว");
  });

  it("shows whether a grant enables or suspends its target",async()=>{
    let enabled=true;const target="22222222-2222-4222-8222-222222222222";
    app=mountApp({fetcher:handler({
      "/api/enterprise/v1/me":()=>response({...me,id:"44444444-4444-4444-8444-444444444444",roles:["authority_reviewer"]}),
      "/api/enterprise/v1/members":()=>response([{id:target,issuer:"https://staff.example.test",subject:"synthetic-target",roles:["data_steward"],departments:["operations"],enabled:false,revision:1}]),
      "/api/enterprise/v1/grants":()=>response([{id,target_id:target,proposed_by:id,approved_by:null,roles:["data_steward"],departments:["operations"],enabled_change:enabled,state:"proposed",revision:1,target_revision:1}]),
    })});await app.start();
    expect(document.querySelector("#grants").textContent).toContain("หลังอนุมัติ: เปิดใช้งาน");
    enabled=false;await app.start();expect(document.querySelector("#grants").textContent).toContain("หลังอนุมัติ: ระงับ");
  });

  it("keeps the department label free of hidden datalist option text",async()=>{
    app=mountApp({fetcher:handler()});await app.start();
    expect(document.querySelector("#activity-form").elements.department_id.labels[0].textContent.trim()).toBe("รหัสแผนก");
  });
});
