/* Evidence references only. Processing authority is checked again on the server. */
const base = "/api/enterprise/v1/processing";
const keys = {
  scope_roles:"ขอบเขตและบทบาท", consent_notice:"ความยินยอมและประกาศ",
  processing_conditions:"เงื่อนไขการประมวลผล", international_transfers:"การส่งต่อระหว่างประเทศ",
  rights:"สิทธิของเจ้าของข้อมูล", security_retention_incidents:"ความปลอดภัย การเก็บรักษา และเหตุละเมิด",
  responsibility_records_processors:"ผู้รับผิดชอบ ทะเบียน และผู้ประมวลผล", dpo:"หน้าที่ด้าน DPO",
};
const states = {draft:"ร่าง",submitted:"รอผู้ทบทวน",reviewed:"ทบทวนแล้ว รอเปิดใช้",active:"เปิดใช้",
  rejected:"ไม่เห็นชอบ",superseded:"มีฉบับใหม่แทน",required:"ต้องดำเนินการ",
  reviewed_not_applicable:"ทบทวนว่าไม่ใช้บังคับ",unknown:"ยังไม่ทราบ"};
const kinds = {legal:"ผลทบทวนการใช้บังคับ",policy:"นโยบายและแหล่งหลักฐาน",processor:"ผู้ประมวลผล",
  transfer:"การส่งต่อ",incident:"เหตุละเมิด",assessment:"การประเมิน",responsibility:"ผู้รับผิดชอบ"};
const labels = {id:"รหัสอ้างอิง",revision:"ฉบับ",state:"สถานะ",activity_id:"กิจกรรม",
  activity_revision:"ฉบับกิจกรรม",department_id:"ฝ่ายงาน",data:"ขอบเขตที่เสนอ",controls:"หลักฐานที่เลือก",
  dependencies:"หลักฐานฉบับที่พึ่งพา",control_versions:"ฉบับหลักฐานทั้งหมด",evidence_ref:"หลักฐานเหตุผล",
  expires_at:"ใช้ได้ถึง",digest:"รหัสตรวจขอบเขต",data_digest:"รหัสตรวจข้อเสนอ",proposed_by:"ผู้เสนอ",
  proposer_revision:"ฉบับอำนาจผู้เสนอ",reviewed_by:"ผู้ทบทวน",reviewer_revision:"ฉบับอำนาจผู้ทบทวน",
  review_evidence_ref:"หลักฐานผลทบทวน",review_digest:"ขอบเขตที่ผู้ทบทวนตรวจ",usable:"ใช้ต่อได้ในขณะตรวจ",
  unresolved_reason:"เหตุที่ต้องทบทวนใหม่",kind:"ประเภท",legal_clearance:"การรับรองกฎหมาย",
  control_key:"ด้านที่ทบทวน",applicability:"ผลการใช้บังคับ",source:"ฉบับแหล่งกฎหมาย",
  rationale_ref:"หลักฐานเหตุผล",implementation_ref:"หลักฐานการทำงาน",operational_ref:"หลักฐานปฏิบัติจริง",
  url:"ต้นฉบับราชการ",sha256:"SHA-256 ของต้นฉบับ",version:"ฉบับต้นฉบับ",byte_count:"จำนวนไบต์ต้นฉบับ",
  fetched_at:"เวลาที่ดึงต้นฉบับ",effective_on:"วันที่มีผล",qualified_review_ref:"หลักฐานผู้มีคุณสมบัติทบทวน",
  owner_ref:"ผู้รับผิดชอบอ้างอิง",links:"งานที่เกี่ยวข้อง",supersedes:"แทนที่ฉบับ",reviewed_at:"เวลาทบทวน",
  activated_at:"เวลาเปิดใช้",evidence_mode:"รูปแบบหลักฐาน",amendment_review:"ผลตรวจฉบับแก้ไข",
  instrument:"ต้นฉบับราชการ",policy_kind:"ประเภทนโยบาย",version_ref:"รหัสฉบับนโยบาย",
  notification_closed:"มีหลักฐานแจ้งครบแล้ว",outstanding_tasks:"กลุ่มการแจ้งที่ยังต้องทบทวน",
};
Object.assign(states,{reviewer_attested:"ผู้มีคุณสมบัติยืนยันการทบทวนแล้ว",organization_reviewer_attestation:"คำยืนยันของผู้ทบทวนองค์กร",
  processing_controls_stale:"หลักฐานหรือขอบเขตเปลี่ยน ต้องทบทวนใหม่",control_stale:"ฉบับหลักฐานหรืออำนาจเปลี่ยน",
  authority_changed:"อำนาจผู้เสนอหรือผู้ทบทวนเปลี่ยน",source_unverified:"ต้นฉบับยังไม่ผ่านการทบทวน",
  linked_case_unverified:"ยังยืนยันงานสิทธิ์ที่อ้างอิงไม่ได้",processing_controls_expired:"ขอบเขตหมดอายุแล้ว",
  processing_controls_integrity:"ขอบเขตไม่ตรงกับหลักฐานฉบับที่เก็บไว้"});

export function mountProcessing({root=document,fetcher=globalThis.fetch.bind(globalThis)}={}) {
  const $ = id => root.getElementById("pc-"+id);
  const state = {me:null,row:null,preview:null,epoch:0,busy:false,pending:new Map(),
    controls:new Map(),activities:new Map(),cursor:null,controlCursor:null,activityCursor:null,
    historyCursor:null,historyRows:[],authority:null};
  const listeners=[]; let disposed=false,turn=0;
  const on=(target,event,handler)=>{target.addEventListener(event,handler);listeners.push(()=>target.removeEventListener(event,handler));};
  const el=(tag,text)=>{const node=root.createElement(tag);if(text!==undefined)node.textContent=String(text);return node;};
  const text=value=>states[value]||kinds[value]||keys[value]||String(value??"ยังไม่มี");
  const has=role=>state.me?.roles?.includes(role);
  const message=(value,error=false)=>{$("message").textContent=value;$("message").classList.toggle("error",error);};
  function draw(container,value) {
    container.replaceChildren();
    function walk(node,value) {
      if(value&&typeof value==="object") {
        const dl=el("dl");
        for(const [name,item] of Object.entries(value)) {
          if(name==="control_versions"||name==="triage_tool")continue;
          const dt=el("dt",labels[name]||keys[name]||(/^\d+$/.test(name)?"รายการ "+(Number(name)+1):name)),dd=el("dd");
          if(item&&typeof item==="object")walk(dd,item);else dd.textContent=typeof item==="boolean"?(item?"ใช่":"ไม่"):text(item);
          dl.append(dt,dd);
        }
        node.append(dl);
      } else node.textContent=text(value);
    }
    walk(container,value);
  }
  function controls() {
    const row=state.row,own=row?.proposed_by===state.me?.id,reviewer=has("privacy_reviewer"),writer=has("data_steward");
    $("save").disabled=state.busy||!writer;
    $("submit").disabled=state.busy||!writer||!own||row?.state!=="draft";
    $("preview").disabled=state.busy||!reviewer||own||row?.state!=="submitted";
    $("approve").disabled=state.busy||!reviewer||own||row?.state!=="submitted"||!state.preview;
    $("reject").disabled=state.busy||!reviewer||own||row?.state!=="submitted";
    $("activate").disabled=state.busy||!reviewer||own||row?.state!=="reviewed";
    $("history").disabled=state.busy||!row;
  }
  function clearRecord() {
    state.row=null;state.preview=null;
    state.historyCursor=null;state.historyRows=[];$("more-history").hidden=true;
    for(const name of ["detail","preview-detail","history-detail"])$(name).replaceChildren();
    $("selected").textContent="เลือกรายการเพื่อทบทวน";$("review-evidence").value="";controls();
  }
  function clearScope(resetCommands=true) {
    state.epoch++;if(resetCommands)state.pending.clear();clearRecord();state.controls.clear();state.activities.clear();
    state.cursor=state.controlCursor=state.activityCursor=null;
    for(const name of ["records","legal","optional"])$(name).replaceChildren();
    $("activity").replaceChildren(el("option","เลือกกิจกรรมก่อน"));$("activity").firstChild.value="";
    for(const name of ["more","more-controls","more-activities"])$(name).hidden=true;
    $("editor").reset();
  }
  function fail(error) {
    if(error.code==="context_changed")return;
    if(error.status===401||error.status===403) {clearScope();state.me=null;$("workspace").hidden=true;}
    else if(["revision_conflict","processing_controls_stale","control_stale","authority_changed","processing_controls_integrity","processing_controls_expired","activity_authority_changed"].includes(error.code))clearScope();
    const messages={network_unknown:"ยังยืนยันผลไม่ได้ ลองคำขอเดิมอีกครั้งเพื่อรับผลเดิม",revision_conflict:"ฉบับเปลี่ยนแล้ว โหลดข้อมูลล่าสุดและทบทวนใหม่",
      processing_preview_required:"ตรวจหลักฐานฉบับที่ผูกไว้ก่อนเห็นชอบ",processing_controls_incomplete:"ยังไม่มีผลทบทวนครบทั้งแปดด้าน",
      processing_controls_stale:"ขอบเขตหรือหลักฐานเปลี่ยน ต้องเสนอและทบทวนฉบับใหม่",processing_controls_expired:"ขอบเขตหมดอายุแล้ว ต้องทบทวนใหม่",
      separation_required:"ผู้เสนอและผู้ทบทวนต้องเป็นคนละคน",authentication_required:"เซสชันหมดอายุ กลับหน้าหลักเพื่อเข้าสู่ระบบ",forbidden:"บัญชีนี้ไม่มีสิทธิ์ตามขอบเขตที่ร้องขอ"};
    message(messages[error.code]||"ยังใช้ขอบเขตนี้ไม่ได้ ตรวจสิทธิ์ ฝ่ายงาน ฉบับ และหลักฐานแล้วโหลดข้อมูลล่าสุด",true);
  }
  async function api(path,body,{command=true}={}) {
    const epoch=state.epoch,options={credentials:"same-origin",cache:"no-store",headers:{Accept:"application/json"}};
    let signature;
    if(body) {
      if(command) {
        signature=path+JSON.stringify(body);
        if(!state.pending.has(signature))state.pending.set(signature,crypto.randomUUID());
        body={...body,command_key:state.pending.get(signature)};
      }
      const name=state.me?.csrf_cookie_name,csrf=name?(root.cookie.split(";").map(v=>v.trim()).find(v=>v.startsWith(name+"="))||"").slice(name.length+1):"";
      options.method="POST";options.headers["Content-Type"]="application/json";options.headers["X-CSRF-Token"]=csrf;options.body=JSON.stringify(body);
    }
    let response;
    try{response=await fetcher(path,options);}catch{throw {code:"network_unknown"};}
    if(disposed||epoch!==state.epoch)throw {code:"context_changed"};
    let result;try{result=await response.json();}catch{throw {code:"response_invalid"};}
    if(disposed||epoch!==state.epoch)throw {code:"context_changed"};
    if(!response.ok) {if(response.status<500&&signature)state.pending.delete(signature);throw {status:response.status,code:result?.error?.code};}
    if(signature)state.pending.delete(signature);return result;
  }
  async function guarded(action,replace=false) {
    if(disposed||(state.busy&&!replace))return;
    const current=++turn;state.busy=true;controls();
    try{await action();}catch(error){if(current===turn)fail(error);}finally{if(current===turn){state.busy=false;controls();}}
  }
  const scope=()=>"department_id="+encodeURIComponent($("department").value)+"&limit=50";
  function choice(view,container) {
    const label=el("label"),input=el("input"),description=el("span");label.className="choice";input.type="checkbox";input.value=view.id;input.disabled=!view.usable;
    const chosen=state.row?.data?.controls?.find(item=>item.id===view.id&&item.revision===view.revision);input.checked=!!chosen;
    description.append(el("span",(keys[view.data?.control_key]||kinds[view.kind]||"หลักฐาน")+" · ฉบับ "+view.revision));
    description.append(el("small",view.id+" · "+(states[view.data?.applicability]||states[view.state]||"ต้องทบทวน")+(view.usable?"":" · ยังใช้ต่อไม่ได้")));
    label.append(input,description);container.append(label);state.controls.set(view.id,view);
  }
  async function loadCatalog(append=false) {
    const page=await api(base+"/controls?"+scope()+(append&&state.controlCursor?"&cursor="+encodeURIComponent(state.controlCursor):""));
    if(!append){$("legal").replaceChildren();$("optional").replaceChildren();state.controls.clear();}
    if(!append)for(const key of page.required_keys||[]) {
      const view=page.legal.find(row=>row.data?.control_key===key);
      if(view)choice(view,$("legal"));else $("legal").append(el("p",(keys[key]||key)+" · ยังไม่มีผลทบทวนที่เปิดใช้"));
    }
    for(const view of page.items)if(!state.controls.has(view.id))choice(view,$("optional"));
    state.controlCursor=page.next_cursor;$("more-controls").hidden=!state.controlCursor;
  }
  async function loadActivities(append=false) {
    const page=await api(base+"/activities?"+scope()+(append&&state.activityCursor?"&cursor="+encodeURIComponent(state.activityCursor):""));
    if(!append){state.activities.clear();$("activity").replaceChildren(el("option","เลือกกิจกรรมก่อน"));$("activity").firstChild.value="";}
    for(const activity of page.items) {state.activities.set(activity.id,activity);const option=el("option",activity.purpose+" · ฉบับ "+activity.revision+" · "+activity.id);option.value=activity.id;$("activity").append(option);}
    state.activityCursor=page.next_cursor;$("more-activities").hidden=!state.activityCursor;
  }
  async function loadBindings(append=false) {
    const page=await api(base+"?"+scope()+(append&&state.cursor?"&cursor="+encodeURIComponent(state.cursor):""));
    if(!append)$("records").replaceChildren();
    if(!append&&!page.items.length)$("records").append(el("p","ยังไม่มีขอบเขตที่เสนอในฝ่ายงานนี้"));
    for(const row of page.items) {
      const article=el("article"),button=el("button","ดูฉบับนี้");article.className="record";button.type="button";
      article.append(el("p",row.id+" · ฉบับ "+row.revision+" · "+text(row.state)+(row.state==="active"&&!row.usable?" · ต้องทบทวนใหม่":"")),button);
      button.addEventListener("click",()=>guarded(()=>select(row.id)));$("records").append(article);
    }
    state.cursor=page.next_cursor;$("more").hidden=!state.cursor;
  }
  async function select(id) {
    clearRecord();state.pending.clear();const row=await api(base+"/"+encodeURIComponent(id));state.row=row;
    $("selected").textContent="ขอบเขต "+row.id+" · ฉบับ "+row.revision+" · "+text(row.state);draw($("detail"),row);
    $("activity").value=row.activity_id;$("evidence").value=row.data.evidence_ref;
    const date=new Date(row.data.expires_at);$("expiry").value=new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);
    for(const input of root.querySelectorAll('#pc-legal input,#pc-optional input')) {
      const view=state.controls.get(input.value);input.checked=!!row.data.controls.find(item=>item.id===view?.id&&item.revision===view.revision);
    }
    controls();
  }
  async function loadScope() {await loadCatalog();if(has("data_steward")||has("privacy_reviewer"))await loadActivities();await loadBindings();message("โหลดฉบับปัจจุบันแล้ว เลือกหลักฐานที่เกี่ยวข้องอย่างชัดแจ้ง");}
  async function refresh() {
    const department=$("department").value;
    clearScope(false);state.me=null;$("workspace").hidden=true;
    const me=await api("/api/enterprise/v1/me");state.me=me;$("departments").replaceChildren();
    const authority=JSON.stringify([me.id,me.member_revision??me.revision,[...(me.roles||[])].sort(),[...(me.departments||[])].sort(),me.csrf_cookie_name]);
    if(state.authority!==authority)state.pending.clear();state.authority=authority;
    for(const department of me.departments||[])if(department!=="*"){const option=el("option");option.value=department;$("departments").append(option);}
    $("department").value=(me.departments||[]).some(value=>value===department||value==="*")?department:(me.departments||[]).find(value=>value!=="*")||"";
    if(department!==$("department").value)state.pending.clear();$("workspace").hidden=false;controls();
    if($("department").value)await loadScope();else message("ระบุฝ่ายงานก่อนโหลดหลักฐาน");
  }
  async function transition(action,data={}) {
    const row=state.row;if(!row)throw {code:"invalid_request"};
    const result=await api(base+"/"+row.id+"/"+action,{expected_revision:row.revision,...data});
    await select(result.id);await loadBindings();
  }
  on($("refresh"),"click",()=>guarded(refresh,true));
  on($("load"),"click",()=>guarded(async()=>{clearScope();await loadScope();},true));
  on($("department"),"change",()=>{clearScope();message("ฝ่ายงานเปลี่ยนแล้ว โหลดข้อมูลฉบับปัจจุบันก่อนดำเนินการ");});
  on($("more"),"click",()=>guarded(()=>loadBindings(true)));
  on($("more-controls"),"click",()=>guarded(()=>loadCatalog(true)));
  on($("more-activities"),"click",()=>guarded(()=>loadActivities(true)));
  on($("new"),"click",()=>{state.epoch++;clearRecord();state.pending.clear();$("editor").reset();for(const input of root.querySelectorAll('#pc-legal input,#pc-optional input'))input.checked=false;});
  on($("editor"),"submit",event=>{event.preventDefault();guarded(async()=>{
    const activity=state.activities.get($("activity").value);if(!activity)throw {code:"invalid_request"};
    const selected=Array.from(root.querySelectorAll('#pc-legal input:checked,#pc-optional input:checked'),input=>state.controls.get(input.value));
    const data={activity_id:activity.id,activity_revision:activity.revision,controls:selected.map(row=>({id:row.id,revision:row.revision})),evidence_ref:$("evidence").value,expires_at:new Date($("expiry").value).toISOString()};
    const row=state.row,result=await api(base+(row?"/"+row.id+"/replace":""),{...(row?{expected_revision:row.revision}:{}),data});
    await select(result.id);await loadBindings();message("บันทึกข้อเสนอแล้ว ต้องให้ผู้ทบทวนอีกคนตรวจฉบับนี้");
  });});
  on($("submit"),"click",()=>guarded(()=>transition("submit")));
  on($("preview"),"click",()=>guarded(async()=>{const row=state.row;const result=await api(base+"/"+row.id+"/preview",{expected_revision:row.revision},{command:false});state.preview=result;draw($("preview-detail"),result);message("ตรวจขอบเขตและหลักฐานฉบับนี้ก่อนเห็นชอบ");}));
  for(const action of ["approve","reject"])on($(action),"click",()=>guarded(()=>transition("review",{decision:action,evidence_ref:$("review-evidence").value})));
  on($("activate"),"click",()=>guarded(()=>transition("activate")));
  async function history(append=false) {const page=await api(base+"/"+state.row.id+"/history"+(append&&state.historyCursor?"?after="+state.historyCursor:""));state.historyRows=append?[...state.historyRows,...page.items]:page.items;state.historyCursor=page.next_cursor;draw($("history-detail"),state.historyRows);$("more-history").hidden=!state.historyCursor;message("ประวัติฉบับเป็นหลักฐานอดีต ไม่ใช่อำนาจประมวลผลปัจจุบัน");}
  on($("history"),"click",()=>guarded(()=>history()));on($("more-history"),"click",()=>guarded(()=>history(true)));
  const hide=()=>{clearScope(false);state.me=null;$("workspace").hidden=true;message("ตรวจบัญชีและสิทธิ์ปัจจุบันก่อนใช้งานต่อ");};
  on(root.defaultView,"pagehide",hide);on(root,"visibilitychange",hide);
  const ready=guarded(refresh);
  return {ready,dispose(){disposed=true;clearScope();state.me=null;for(const remove of listeners)remove();}};
}

if(typeof document!=="undefined"&&document.getElementById("pc-workspace"))mountProcessing();
