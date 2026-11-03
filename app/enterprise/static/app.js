/* Staff UI calls the shared API. It never stores bearer cookies or provider tokens. */
const BASE = "/api/enterprise/v1";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ROLES = {
  system_administrator:"ผู้ดูแลระบบ",authority_reviewer:"ผู้ทบทวนสิทธิ์",data_steward:"ผู้จัดทำทะเบียน",
  privacy_reviewer:"ผู้ทบทวนความเป็นส่วนตัว",case_manager:"ผู้จัดการคำขอ",identity_steward:"ผู้ทบทวนตัวตน",
  custodian:"ผู้ดูแลแหล่งข้อมูล",auditor:"ผู้ตรวจสอบ",
};
const CATEGORIES = {IDENTITY:"ข้อมูลระบุตัวตน",CONTACT:"ข้อมูลติดต่อ",LOCATION:"ที่อยู่และตำแหน่ง",FINANCIAL:"การเงิน",
  EDUCATION:"การศึกษา",EMPLOYMENT:"การทำงาน",ONLINE:"ตัวตนออนไลน์",ACTIVITY:"กิจกรรม",RELATIONSHIPS:"ความสัมพันธ์",
  MEDIA:"สื่อ",QUASI_IDENTIFIERS:"ข้อมูลที่อาจระบุตัวบุคคลร่วมกัน",RACE:"เชื้อชาติ",ETHNICITY:"ชาติพันธุ์",
  POLITICAL_OPINION:"ความคิดเห็นทางการเมือง",BELIEF:"ความเชื่อ",SEXUAL_BEHAVIOR:"พฤติกรรมทางเพศ",
  CRIMINAL_RECORD:"ประวัติอาชญากรรม",HEALTH:"สุขภาพ",DISABILITY:"ความพิการ",LABOR_UNION:"สหภาพแรงงาน",
  GENETIC_DATA:"พันธุกรรม",BIOMETRIC_IDENTITY:"ชีวภาพเพื่อระบุตัวบุคคล",OTHER_PERSONAL:"ข้อมูลส่วนบุคคลอื่น (รอทบทวน)",
  OTHER_DECLARED_SENSITIVE:"ข้อมูลอ่อนไหวอื่น (รอทบทวน)"};
const OPTIONS = {consent:"ความยินยอม",contract:"สัญญา",legal_obligation:"หน้าที่ตามกฎหมาย",vital_interests:"ป้องกันอันตรายต่อชีวิต",
  public_task:"ภารกิจเพื่อประโยชน์สาธารณะ",legitimate_interests:"ประโยชน์โดยชอบด้วยกฎหมาย",research_archiving:"วิจัย / สถิติ / จดหมายเหตุ",
  explicit_consent:"ความยินยอมโดยชัดแจ้ง",nonprofit_internal:"กิจกรรมภายในองค์กรไม่แสวงกำไร",manifestly_public:"ข้อมูลที่เปิดเผยโดยชัดแจ้ง",
  legal_claims:"สิทธิเรียกร้องตามกฎหมาย",medical:"การแพทย์ตามเงื่อนไข",public_health:"สาธารณสุขตามเงื่อนไข",
  employment_social_protection:"การจ้างงาน / คุ้มครองทางสังคม",research_statistics:"วิจัย / สถิติตามเงื่อนไข",
  substantial_public_interest:"ประโยชน์สาธารณะที่สำคัญ"};
const STATES = {draft:"ร่าง",submitted:"รอทบทวน",active:"ผ่านการทบทวน",rejected:"ส่งกลับแก้ไข",published:"เผยแพร่แล้ว",
  proposed:"รอทบทวนสิทธิ์",applied:"ดำเนินการแล้ว"};
const ERRORS = {invalid_request:"ตรวจข้อมูลที่จำเป็นและรูปแบบข้อมูลอีกครั้ง",forbidden:"บัญชีนี้ไม่มีสิทธิ์ดำเนินการในขอบเขตนี้",
  separation_required:"ต้องให้ผู้ทบทวนอีกคนพิจารณารายการนี้",independent_review_required:"ต้องให้ผู้ทบทวนอีกคนพิจารณารายการนี้",
  revision_conflict:"ข้อมูลเปลี่ยนแล้ว โปรดโหลดข้อมูลล่าสุดและทบทวนก่อนส่งอีกครั้ง",idempotency_conflict:"รายการส่งซ้ำมีข้อมูลไม่ตรงกัน โปรดตรวจทานก่อนส่งใหม่",
  review_incomplete:"ข้อมูลกิจกรรมหรือหลักฐานทบทวนยังไม่ครบ",notice_scope_mismatch:"ประกาศไม่ตรงกับกิจกรรมรุ่นที่กำลังทบทวน",
  record_unavailable:"ไม่พบรายการในขอบเขตสิทธิ์ปัจจุบัน",invalid_transition:"สถานะรายการเปลี่ยนแล้ว โปรดโหลดข้อมูลล่าสุด",
  proposal_stale:"สิทธิ์หรือข้อมูลเจ้าหน้าที่เปลี่ยนแล้ว ต้องตรวจทานข้อเสนอใหม่",storage_failure:"ยังยืนยันการบันทึกไม่ได้ โปรดลองส่งซ้ำในหน้านี้",
  identity_unavailable:"ระบบยืนยันตัวตนยังไม่พร้อม โปรดลองอีกครั้ง",invalid_response:"รูปแบบข้อมูลจากระบบไม่ถูกต้อง จึงยังไม่เปิดให้ดำเนินการ",
  network:"ติดต่อระบบไม่ได้ ข้อมูลอาจบันทึกแล้ว คุณส่งซ้ำในหน้านี้ได้โดยไม่สร้างรายการซ้ำ",internal_error:"ระบบยังดำเนินการไม่สำเร็จ โปรดลองอีกครั้ง"};
ERRORS.busy="กำลังบันทึกข้อมูล โปรดรอผลก่อนเปลี่ยนรายการ";
class UIError extends Error {constructor(code, correlation=""){super(code);this.code=code;this.correlation=correlation;}}
const object = value => value && typeof value === "object" && !Array.isArray(value);
const strings = (value,max=64) => Array.isArray(value) && value.length<=max && value.every(x=>typeof x==="string");
const exact = (value,names) => object(value)&&Object.keys(value).length===names.length&&names.every(k=>Object.hasOwn(value,k));
const recordKeys=["id","state","revision","data","review","created_by","last_editor","submitted_by","reviewed_by","reviewed_at","review_evidence_mode","legal_clearance"];
const dataKeys=["department_id","title","purpose","necessity","categories","general_basis","sensitive_condition","retention_rule","destination","source_refs","subject_groups","recipient_refs"];
function validRecord(value){
  if(!exact(value,recordKeys)||!UUID.test(value.id)||!Number.isInteger(value.revision)||value.revision<1||
    !["draft","submitted","active","rejected"].includes(value.state)||!exact(value.data,dataKeys)||
    typeof value.data.title!=="string"||typeof value.data.purpose!=="string"||!strings(value.data.categories,24)||
    value.legal_clearance!==false)throw new UIError("invalid_response");
  return value;
}
function validNotice(value){
  if(!exact(value,["id","state","revision","data","content_digest","created_by","published_by","published_at","created_at"])||!UUID.test(value.id)||!Number.isInteger(value.revision)||value.revision<1||
    !["draft","published"].includes(value.state)||!object(value.data)||typeof value.data.title!=="string"||
    typeof value.data.body!=="string")throw new UIError("invalid_response");
  return value;
}
function validGrant(value){
  if(!exact(value,["id","target_id","proposed_by","approved_by","roles","departments","enabled_change","state","revision","target_revision"])||!UUID.test(value.id)||!UUID.test(value.target_id)||!Number.isInteger(value.revision)||
    !strings(value.roles,8)||!strings(value.departments,32)||!["proposed","applied"].includes(value.state)||
    ![true,false,null].includes(value.enabled_change))throw new UIError("invalid_response");
  return value;
}
function receipt(value,state,id=null){
  if(!exact(value,["id","state","revision"])||!UUID.test(value.id)||value.state!==state||
    !Number.isInteger(value.revision)||value.revision<1||(id!==null&&value.id!==id))throw new UIError("invalid_response");
  return value;
}
function array(value, validator=x=>x){
  if(!Array.isArray(value)||value.length>100)throw new UIError("invalid_response");
  return value.map(validator);
}
const refs = value => value.split(/[\n,]/).map(x=>x.trim()).filter(Boolean);

export function mountApp({root=document, fetcher=globalThis.fetch.bind(globalThis)}={}){
  const $ = id => root.querySelector("#"+id);
  const state={me:null,catalog:null,selected:null,editing:null,view:"activities",offset:0,epoch:0,selection:0,blocked:false,commands:new Map(),busy:new Set(),mutations:new Set()};
  const requests=new Set(), handlers=[], dynamic=new Map();
  let idleTimer,absoluteTimer,disposed=false;
  function node(tag,text,cls){const n=root.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n;}
  function listen(target,event,fn){target.addEventListener(event,fn);handlers.push(()=>target.removeEventListener(event,fn));}
  function bind(container,target,event,fn){target.addEventListener(event,fn);if(!dynamic.has(container))dynamic.set(container,[]);dynamic.get(container).push(()=>target.removeEventListener(event,fn));}
  function resetList(id){for(const remove of dynamic.get(id)||[])remove();dynamic.delete(id);$(id).replaceChildren();}
  function status(text,error=false){$("status").textContent=text;$("status").classList.toggle("error",error);}
  function clearProtected(){
    for(const id of ["records","notices","members","grants","audit-entries","detail-values"])resetList(id);
    for(const form of root.querySelectorAll("#workspace form")){form.reset();delete form.dataset.recordId;delete form.dataset.recordRevision;}
    for(const id of ["detail-title","detail-state","session-scope","confirmation-text","page-info"])$(id).textContent="";
    $("grant-form").elements.member_id.replaceChildren();$("review-form").elements.notice_id.replaceChildren();
    if($("confirmation").open&&typeof $("confirmation").close==="function")$("confirmation").close("cancel");
    $("activity-editor").hidden=true;$("activity-detail").hidden=true;
    state.selected=null;state.editing=null;state.offset=0;state.selection++;state.commands.clear();state.mutations.clear();
  }
  function expire(message="เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง"){
    state.epoch++;for(const controller of requests)controller.abort();requests.clear();
    clearTimeout(idleTimer);clearTimeout(absoluteTimer);state.me=null;state.catalog=null;
    clearProtected();$("workspace").hidden=true;$("welcome").hidden=false;
    root.querySelector("#main").setAttribute("aria-busy","false");status(message);
  }
  function resetIdle(){if(state.me){clearTimeout(idleTimer);idleTimer=setTimeout(()=>expire(),state.me.session.idle_seconds*1000);}}
  function acceptMe(value){
    if(!exact(value,["id","roles","departments","csrf_cookie_name","session"])||!UUID.test(value.id)||!strings(value.roles,8)||!value.roles.every(x=>Object.hasOwn(ROLES,x))||
      !strings(value.departments,32)||!exact(value.session,["idle_seconds","absolute_remaining_seconds"])||!Number.isInteger(value.session.idle_seconds)||
      value.session.idle_seconds<1||value.session.idle_seconds>86400||!Number.isInteger(value.session.absolute_remaining_seconds)||
      value.session.absolute_remaining_seconds<0||value.session.absolute_remaining_seconds>604800||
      !["__Host-aiguard_csrf","aiguard_dev_csrf"].includes(value.csrf_cookie_name))throw new UIError("invalid_response");
    const fingerprint=m=>JSON.stringify([m.id,[...m.roles].sort(),[...m.departments].sort(),m.csrf_cookie_name]);
    const changed=state.me&&fingerprint(state.me)!==fingerprint(value);
    if(changed){state.epoch++;for(const c of requests)c.abort();requests.clear();clearProtected();state.catalog=null;}
    state.me=value;resetIdle();clearTimeout(absoluteTimer);
    absoluteTimer=setTimeout(()=>expire(),value.session.absolute_remaining_seconds*1000);
    $("session-scope").textContent=value.roles.map(x=>ROLES[x]).join(" · ")+" | แผนก: "+value.departments.join(", ");
    return changed;
  }
  function csrf(){
    const name=state.me?.csrf_cookie_name;
    const value=root.cookie.split(";").map(x=>x.trim()).find(x=>x.startsWith(name+"="));
    try{return value?decodeURIComponent(value.slice(name.length+1)):"";}catch{return "";}
  }
  async function request(path,options={},optional=false){
    const epoch=state.epoch,controller=new AbortController();requests.add(controller);
    try{
      const response=await fetcher(path,{credentials:"same-origin",cache:"no-store",...options,signal:controller.signal});
      if(epoch!==state.epoch||disposed)throw new UIError("session_changed");
      if(response.status===401){const failed=new URLSearchParams(root.defaultView?.location.search||"").get("login")==="failed";
        expire(optional?(failed?"เข้าสู่ระบบยังไม่สำเร็จหรือบัญชียังไม่มีสิทธิ์ โปรดลองอีกครั้งหรือติดต่อผู้ดูแล":"พร้อมเข้าสู่ระบบองค์กร"):"เซสชันสิ้นสุดหรือสิทธิ์เปลี่ยน กรุณาเข้าสู่ระบบอีกครั้ง");if(optional)return null;throw new UIError("session_changed");}
      const value=response.status===204?null:await response.json();
      if(epoch!==state.epoch||disposed)throw new UIError("session_changed");
      if(!response.ok){const code=typeof value?.error?.code==="string"?value.error.code:"internal_error";
        throw new UIError(code,UUID.test(value?.error?.correlation_id)?value.error.correlation_id:"");}
      resetIdle();return value;
    }catch(error){
      if(error instanceof UIError)throw error;
      if(error?.name==="AbortError"||epoch!==state.epoch)throw new UIError("session_changed");
      throw new UIError("network");
    }finally{requests.delete(controller);}
  }
  function showError(error){
    if(error.code==="invalid_response"){state.blocked=true;clearProtected();$("new-activity").hidden=true;$("enrollment-form").hidden=true;$("grant-form").hidden=true;}
    if(error.code!=="session_changed")status((ERRORS[error.code]||"ยังดำเนินการไม่ได้ โปรดตรวจทานหรือรีเฟรช")+(error.correlation?" รหัสอ้างอิง: "+error.correlation:""),true);
  }
  async function task(button,action){
    if(state.busy.has(button))return;state.busy.add(button);button.disabled=true;
    try{await action();}catch(error){showError(error);}finally{state.busy.delete(button);button.disabled=false;}
  }
  async function command(path,payload,method="POST",validate=x=>x){
    if(state.blocked)throw new UIError("invalid_response");
    const operation=Symbol();state.mutations.add(operation);
    try{
    const fingerprint=method+path+JSON.stringify(payload);
    if(!state.commands.has(fingerprint)){if(state.commands.size>32)state.commands.clear();state.commands.set(fingerprint,crypto.randomUUID());}
    const value=await request(path,{method,headers:{"Content-Type":"application/json","X-CSRF-Token":csrf()},
      body:JSON.stringify({command_key:state.commands.get(fingerprint),...payload})});
    const result=validate(value);state.commands.delete(fingerprint);return result;
    }finally{state.mutations.delete(operation);}
  }
  function can(role){return !!state.me?.roles.includes(role);}
  function empty(container,text){container.replaceChildren(node("p",text,"empty"));}
  function option(select,value,label){const o=node("option",label);o.value=value;select.append(o);}
  function configureForms(){
    const catalog=state.catalog;
    if(!exact(catalog,["categories","bases","sensitive_conditions","roles"])||!Array.isArray(catalog.categories)||catalog.categories.length>32||
      !strings(catalog.bases,32)||!strings(catalog.sensitive_conditions,32)||!strings(catalog.roles,8))throw new UIError("invalid_response");
    $("category-options").replaceChildren();
    for(const entry of catalog.categories){if(!object(entry)||typeof entry.code!=="string"||typeof entry.sensitive!=="boolean")throw new UIError("invalid_response");
      const label=node("label");const check=node("input");check.type="checkbox";check.name="categories";check.value=entry.code;
      label.append(check,node("span",(CATEGORIES[entry.code]||entry.code)+(entry.sensitive?" · อ่อนไหว":"")));$("category-options").append(label);}
    const form=$("activity-form");
    for(const [name,values] of [["general_basis",catalog.bases],["sensitive_condition",catalog.sensitive_conditions]]){
      const select=form.elements[name];select.replaceChildren();option(select,"","ยังไม่ระบุในร่าง");
      for(const value of values)option(select,value,OPTIONS[value]||value);
    }
    $("department-options").replaceChildren();for(const code of state.me.departments.filter(x=>x!=="*"))option($("department-options"),code,code);
    for(const select of root.querySelectorAll(".role-options")){select.replaceChildren();for(const role of catalog.roles)option(select,role,ROLES[role]||role);}
    $("new-activity").hidden=!can("data_steward");
    for(const id of ["enrollment-form","grant-form"])$(id).hidden=!can("system_administrator");
  }
  function allowedViews(){return {activities:state.me?.roles.some(x=>["data_steward","privacy_reviewer","case_manager","custodian"].includes(x)),
    grants:can("system_administrator")||can("authority_reviewer"),audit:can("auditor")};}
  async function loadRecords(){
    const records=array(await request(BASE+"/activities?limit=100&offset="+state.offset),validRecord);
    resetList("records");
    if(!records.length)empty($("records"),"ยังไม่มีกิจกรรมในหน้านี้ สร้างร่างใหม่หรือเลือกหน้าก่อนเพื่อเริ่มงาน");
    for(const value of records){const card=node("article",undefined,"record"),button=node("button",value.data.title,"row-link");button.type="button";
      bind("records",button,"click",()=>task(button,()=>openRecord(value.id)));card.append(button,node("p",STATES[value.state]+" · "+value.data.department_id,"muted"));$("records").append(card);}
    return records.length;
  }
  function detail(value,preserveSelection=false){
    validRecord(value);
    if(!preserveSelection)state.selection++;
    if(state.selected?.id!==value.id||state.selected?.revision!==value.revision){
      for(const id of ["notice-form","review-form"]){$(id).reset();$(id).dataset.recordId=value.id;$(id).dataset.recordRevision=String(value.revision);}
    }
    state.selected=value;$("activity-detail").hidden=false;$("detail-title").textContent=value.data.title;
    $("detail-state").textContent=STATES[value.state]+" · รุ่น "+value.revision;$("detail-values").replaceChildren();
    const fields={purpose:"วัตถุประสงค์",necessity:"ความจำเป็น",department_id:"แผนก",general_basis:"ฐานการประมวลผล",
      sensitive_condition:"เงื่อนไขอ่อนไหว",retention_rule:"ระยะเวลาเก็บ",destination:"ปลายทาง",source_refs:"แหล่งอ้างอิง",
      subject_groups:"กลุ่มเจ้าของข้อมูล",recipient_refs:"ผู้รับข้อมูล"};
    for(const [key,label]of Object.entries(fields)){const raw=value.data[key];const text=Array.isArray(raw)?raw.join("\n"):OPTIONS[raw]||raw||"ยังไม่ระบุ";
      $("detail-values").append(node("dt",label),node("dd",text));}
    $("detail-values").append(node("dt","หมวดข้อมูล"),node("dd",value.data.categories.map(code=>(CATEGORIES[code]||code)+(state.catalog.categories.find(c=>c.code===code)?.sensitive?" · อ่อนไหว":"")).join("\n")));
    const editable=can("data_steward")&&["draft","rejected"].includes(value.state);
    $("edit-activity").hidden=!editable;$("submit-activity").hidden=!editable;$("notice-form").hidden=!can("data_steward");
    $("review-form").hidden=!can("privacy_reviewer")||value.state!=="submitted";
    const self=[value.created_by,value.last_editor,value.submitted_by].includes(state.me.id);
    $("review-form").querySelector('[type="submit"]').disabled=self;
    $("review-separation").textContent=self?"คุณเป็นผู้จัดทำหรือส่งรายการนี้ ต้องให้ผู้ทบทวนอีกคนพิจารณา":"ตรวจหลักฐานและขอบเขตประกาศก่อนบันทึกผล การทบทวนนี้ไม่ใช่ใบรับรองกฎหมาย";
  }
  async function notices(){
    const selected=state.selected?.id,ticket=state.selection;if(!selected)return;
    const rows=array(await request(BASE+"/activities/"+selected+"/notices"),validNotice);
    if(state.selected?.id!==selected||state.selection!==ticket)return;
    resetList("notices");const select=$("review-form").elements.notice_id;select.replaceChildren();option(select,"","เลือกประกาศ");
    if(!rows.length)empty($("notices"),"ยังไม่มีประกาศของกิจกรรมรุ่นนี้");
    for(const value of rows){const card=node("article",undefined,"record");card.append(node("h3",value.data.title),node("p",STATES[value.state],"badge"),node("p",value.data.body));
      if(value.state==="published")option(select,value.id,value.data.title);
      if(value.state==="draft"&&can("privacy_reviewer")&&value.created_by!==state.me.id){const b=node("button","เผยแพร่ประกาศ");b.type="button";
        bind("notices",b,"click",()=>task(b,async()=>{await command(BASE+"/notices/"+value.id+"/publish",{expected_revision:value.revision},"POST",validNotice);await notices();status("เผยแพร่ประกาศแล้ว");}));card.append(b);}
      $("notices").append(card);}
  }
  async function openRecord(id){
    if(state.mutations.size)throw new UIError("busy");
    const dirty=$("notice-form").elements.title.value||$("notice-form").elements.body.value||
      $("review-form").elements.reason.value||["inventory","basis","retention","destination","sensitive"].some(k=>$("review-form").elements[k].value);
    if(state.selected?.id!==id&&dirty&&!(await confirmAction("เปลี่ยนกิจกรรมและล้างร่างประกาศ/หลักฐานที่ยังไม่บันทึก?")))return;
    const ticket=++state.selection;
    const value=await request(BASE+"/activities/"+encodeURIComponent(id));if(ticket!==state.selection)return;
    detail(value,true);await notices();if(ticket===state.selection)$("detail-title").focus();
  }
  function edit(value=null){
    state.editing=value;const form=$("activity-form");form.reset();$("activity-editor").hidden=false;
    $("editor-title").textContent=value?"แก้ไขร่างกิจกรรม":"ร่างกิจกรรมใหม่";
    if(value){for(const [key,raw]of Object.entries(value.data)){if(key==="categories"){for(const c of form.querySelectorAll('[name="categories"]'))c.checked=raw.includes(c.value);}
      else if(form.elements[key])form.elements[key].value=Array.isArray(raw)?raw.join("\n"):raw??"";}}
    else form.elements.department_id.value=state.me.departments.find(x=>x!=="*")||"";
    form.elements.title.focus();
  }
  async function confirmAction(message){
    const dialog=$("confirmation");$("confirmation-text").textContent=message;
    return new Promise(resolve=>{dialog.addEventListener("close",()=>resolve(dialog.returnValue==="confirm"),{once:true});dialog.showModal();});
  }
  async function loadGrants(){
    const suffix="?limit=100&offset="+state.offset;
    const members=array(await request(BASE+"/members"+suffix),value=>{
      if(!object(value)||!UUID.test(value.id)||typeof value.subject!=="string"||!strings(value.roles,8)||!strings(value.departments,32)||typeof value.enabled!=="boolean"||!Number.isInteger(value.revision))throw new UIError("invalid_response");return value;});
    const grants=array(await request(BASE+"/grants"+suffix),validGrant);
    resetList("members");resetList("grants");const targets=$("grant-form").elements.member_id;targets.replaceChildren();option(targets,"","เลือกเจ้าหน้าที่");
    if(!members.length)empty($("members"),"ไม่พบเจ้าหน้าที่ในหน้านี้");
    for(const m of members){option(targets,m.id,m.subject);const card=node("article",undefined,"record");card.append(node("h3",m.subject),node("p",m.roles.map(x=>ROLES[x]||x).join(" · ")),
      node("p",m.departments.join(", ")+" · "+(m.enabled?"เปิดใช้งาน":"ยังไม่เปิดใช้งาน"),"muted"));
      if(m.enabled&&can("system_administrator")){const b=node("button","ระงับสิทธิ์");b.type="button";bind("members",b,"click",()=>task(b,async()=>{
        if(await confirmAction("ระงับสิทธิ์ของ "+m.subject+" ทันที? การเปิดใช้งานอีกครั้งต้องผ่านการทบทวนสิทธิ์")){
          await command(BASE+"/members/"+m.id+"/suspend",{expected_revision:m.revision},"POST",v=>receipt(v,"suspended",m.id));await loadGrants();status("บันทึกการระงับสิทธิ์แล้ว");}}));card.append(b);}
      $("members").append(card);}
    if(!grants.length)empty($("grants"),"ยังไม่มีข้อเสนอสิทธิ์ในหน้านี้");
    for(const g of grants){const card=node("article",undefined,"record");card.append(node("p",STATES[g.state],"badge"),node("p","เป้าหมาย: "+(members.find(x=>x.id===g.target_id)?.subject||g.target_id)),
      node("p",g.roles.map(x=>ROLES[x]||x).join(" · ")+" | "+g.departments.join(", ")));
      const current=members.find(x=>x.id===g.target_id),desired=g.enabled_change===null?"คงสถานะเดิม":g.enabled_change?"เปิดใช้งาน":"ระงับ";
      card.append(node("p","สถานะปัจจุบัน: "+(current?(current.enabled?"เปิดใช้งาน":"ระงับ / ยังไม่เปิดใช้งาน"):"ต้องตรวจจากรายการเจ้าหน้าที่")+" · หลังอนุมัติ: "+desired));
      if(g.state==="proposed"&&can("authority_reviewer")&&![g.target_id,g.proposed_by].includes(state.me.id)){const b=node("button","อนุมัติข้อเสนอสิทธิ์");b.type="button";
        bind("grants",b,"click",()=>task(b,async()=>{
          const fresh=await request(BASE+"/members/"+g.target_id);
          if(!exact(fresh,["id","issuer","subject","roles","departments","enabled","revision"])||fresh.id!==g.target_id||typeof fresh.subject!=="string"||typeof fresh.enabled!=="boolean")throw new UIError("invalid_response");
          if(fresh.revision!==g.target_revision)throw new UIError("revision_conflict");
          if(await confirmAction("ทบทวนสิทธิ์ของ "+fresh.subject+" · ปัจจุบัน: "+(fresh.enabled?"เปิดใช้งาน":"ระงับ / ยังไม่เปิดใช้งาน")+" · หลังอนุมัติ: "+desired+" · บทบาท: "+g.roles.map(x=>ROLES[x]||x).join(", ")+" · แผนก: "+g.departments.join(", ")+" ยืนยันว่าตรวจข้อมูลครบแล้ว?")){
          await command(BASE+"/grants/"+g.id+"/approve",{expected_revision:g.revision},"POST",v=>receipt(v,"applied",g.id));await loadGrants();status("ดำเนินการตามข้อเสนอสิทธิ์แล้ว");}}));card.append(b);}
      $("grants").append(card);}
    return Math.max(members.length,grants.length);
  }
  async function loadAudit(){
    const rows=array(await request(BASE+"/audit?limit=100&offset="+state.offset),value=>{
      if(!object(value)||!Number.isInteger(value.sequence)||typeof value.event_code!=="string"||typeof value.occurred_at!=="string"||!/^[a-f0-9]{64}$/.test(value.event_hash))throw new UIError("invalid_response");return value;});
    resetList("audit-entries");if(!rows.length)empty($("audit-entries"),"ยังไม่มีเหตุการณ์ในขอบเขตของคุณในหน้านี้");
    for(const row of rows){const card=node("article",undefined,"record");card.append(node("h3",row.sequence+" · "+row.event_code),node("p",row.occurred_at,"muted"),node("p","รายการ: "+(row.target_id||"—")),node("p","Hash: "+row.event_hash,"muted"));$("audit-entries").append(card);}
    return rows.length;
  }
  async function loadView(view=state.view){
    if(!allowedViews()[view])return;state.view=view;
    for(const name of ["activities","grants","audit"])$("view-"+name).hidden=name!==view;
    for(const b of root.querySelectorAll("[data-view]"))b.setAttribute("aria-pressed",String(b.dataset.view===view));
    $("page-title").textContent={activities:"ทะเบียนกิจกรรม",grants:"เจ้าหน้าที่และสิทธิ์",audit:"บันทึกเหตุการณ์"}[view];
    status("กำลังโหลดรายการ…");$("main").setAttribute("aria-busy","true");
    try{const count=await({activities:loadRecords,grants:loadGrants,audit:loadAudit}[view]());
      $("previous").disabled=state.offset===0;$("next").disabled=count<100;
      $("page-info").textContent="หน้า "+(state.offset/100+1)+" · ไม่เกิน 100 รายการต่อชุด";status("โหลดข้อมูลแล้ว");
    }finally{$("main").setAttribute("aria-busy","false");}
  }
  async function start(){
    state.epoch++;for(const controller of requests)controller.abort();requests.clear();
    status("กำลังตรวจสอบเซสชัน…");$("main").setAttribute("aria-busy","true");
    try{const value=await request(BASE+"/me",{},true);if(!value)return;
      acceptMe(value);state.catalog=await request(BASE+"/catalog");configureForms();state.blocked=false;
      $("welcome").hidden=true;$("workspace").hidden=false;const allowed=allowedViews();
      for(const b of root.querySelectorAll("[data-view]"))b.hidden=!allowed[b.dataset.view];
      $("no-permissions").hidden=Object.values(allowed).some(Boolean);
      if(!allowed[state.view])state.view=Object.keys(allowed).find(x=>allowed[x]);
      if(state.view)await loadView(state.view);
      else for(const v of ["activities","grants","audit"])$("view-"+v).hidden=true;
    }catch(error){showError(error);}finally{$("main").setAttribute("aria-busy","false");}
  }
  function submit(form,action){listen(form,"submit",event=>{event.preventDefault();if(form.reportValidity())task(form.querySelector('[type="submit"]'),action);});}
  listen($("new-activity"),"click",()=>{if(state.mutations.size)status(ERRORS.busy,true);else edit();});listen($("close-editor"),"click",()=>{$("activity-editor").hidden=true;});
  listen($("edit-activity"),"click",()=>edit(state.selected));
  listen($("reload-detail"),"click",()=>task($("reload-detail"),async()=>{if(await confirmAction("โหลดรุ่นล่าสุดและแทนข้อความร่างที่ยังไม่บันทึกในฟอร์ม?")){await openRecord(state.selected.id);edit(state.selected);}}));
  listen($("submit-activity"),"click",()=>task($("submit-activity"),async()=>{const r=state.selected;
    detail(await command(BASE+"/activities/"+r.id+"/submit",{expected_revision:r.revision},"POST",validRecord));await loadRecords();status("ส่งให้ผู้ทบทวนแล้ว");}));
  submit($("activity-form"),async()=>{
    const f=$("activity-form"),data={};for(const name of ["department_id","title","purpose","necessity","retention_rule","destination"])data[name]=f.elements[name].value;
    data.categories=Array.from(f.querySelectorAll('[name="categories"]:checked')).map(x=>x.value);if(!data.categories.length)throw new UIError("invalid_request");
    for(const name of ["general_basis","sensitive_condition"])data[name]=f.elements[name].value||null;
    for(const name of ["source_refs","subject_groups","recipient_refs"])data[name]=refs(f.elements[name].value);
    const r=state.editing;const value=await command(BASE+"/activities"+(r?"/"+r.id:""),{data,...(r?{expected_revision:r.revision}:{})},r?"PUT":"POST",validRecord);
    $("activity-editor").hidden=true;f.reset();state.editing=null;detail(value);await loadRecords();await notices();status("บันทึกร่างแล้ว");
  });
  submit($("notice-form"),async()=>{const f=$("notice-form");if(f.dataset.recordId!==state.selected?.id||Number(f.dataset.recordRevision)!==state.selected?.revision)throw new UIError("revision_conflict");
    await command(BASE+"/notices",{expected_activity_revision:Number(f.dataset.recordRevision),data:{activity_id:f.dataset.recordId,title:f.elements.title.value,body:f.elements.body.value,language:f.elements.language.value}},"POST",validNotice);f.reset();await notices();status("สร้างร่างประกาศแล้ว");});
  listen($("review-form").elements.decision,"change",()=>{const f=$("review-form"),approve=f.elements.decision.value==="approve";
    for(const name of ["notice_id","inventory","basis","retention","destination"])f.elements[name].required=approve;
    f.elements.sensitive.required=approve&&state.catalog.categories.some(c=>c.sensitive&&state.selected?.data.categories.includes(c.code));});
  submit($("review-form"),async()=>{const f=$("review-form"),r=state.selected,evidence={};if(f.dataset.recordId!==r?.id||Number(f.dataset.recordRevision)!==r?.revision)throw new UIError("revision_conflict");for(const key of ["inventory","basis","retention","destination","sensitive"])if(f.elements[key].value)evidence[key]=f.elements[key].value;
    const value=await command(BASE+"/activities/"+r.id+"/review",{expected_revision:r.revision,data:{decision:f.elements.decision.value,reason:f.elements.reason.value,notice_id:f.elements.notice_id.value||null,evidence}},"POST",validRecord);
    f.reset();detail(value);await loadRecords();status("บันทึกผลการทบทวนแล้ว");});
  submit($("enrollment-form"),async()=>{const f=$("enrollment-form");await command(BASE+"/members",{data:{subject:f.elements.subject.value,roles:Array.from(f.elements.roles.selectedOptions).map(x=>x.value),departments:refs(f.elements.departments.value)}},"POST",v=>receipt(v,"proposed"));f.reset();await loadGrants();status("ส่งข้อเสนอเพิ่มเจ้าหน้าที่แล้ว ยังไม่เปิดใช้งานจนกว่าอีกคนจะอนุมัติ");});
  submit($("grant-form"),async()=>{const f=$("grant-form");await command(BASE+"/members/"+f.elements.member_id.value+"/grants",{roles:Array.from(f.elements.roles.selectedOptions).map(x=>x.value),departments:refs(f.elements.departments.value),enabled:f.elements.enabled.value===""?null:f.elements.enabled.value==="true"},"POST",v=>receipt(v,"proposed"));await loadGrants();status("ส่งข้อเสนอสิทธิ์แล้ว");});
  for(const b of root.querySelectorAll("[data-view]"))listen(b,"click",()=>task(b,async()=>{if(state.mutations.size)throw new UIError("busy");if(!$("activity-editor").hidden&&!(await confirmAction("เปลี่ยนพื้นที่งานและปิดร่างที่ยังไม่บันทึก?")))return;
    $("activity-editor").hidden=true;$("activity-detail").hidden=true;state.offset=0;await loadView(b.dataset.view);$("page-title").focus();}));
  listen($("refresh"),"click",()=>task($("refresh"),start));
  for(const [id,delta]of [["previous",-100],["next",100]])listen($(id),"click",()=>task($(id),async()=>{state.offset=Math.max(0,Math.min(10000,state.offset+delta));await loadView();}));
  listen($("logout"),"click",()=>task($("logout"),async()=>{await request("/auth/logout",{method:"POST",headers:{"X-CSRF-Token":csrf()}});expire("ออกจากระบบแล้ว");}));
  const focus=async()=>{if(state.me){try{const value=await request(BASE+"/me");if(acceptMe(value))await start();}catch(error){showError(error);}}};
  if(root.defaultView)listen(root.defaultView,"focus",focus);
  return {start,dispose(){disposed=true;expire("");for(const remove of handlers)remove();handlers.length=0;}};
}

if(typeof document!=="undefined"&&document.querySelector("[data-enterprise-root]"))mountApp().start();
