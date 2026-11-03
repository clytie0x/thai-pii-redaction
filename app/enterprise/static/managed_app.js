const base="/api/enterprise/v1/managed";
export const outcomeLabels=Object.freeze({proposed:"รอผู้ทบทวน",pending:"รอเริ่มงาน",running:"กำลังดำเนินการ",verified:"ตรวจยืนยันคลังหลักแล้ว",failed:"ดำเนินการไม่สำเร็จ",unknown:"ไม่ทราบผล ต้องตรวจสอบก่อนเริ่มอีกครั้ง"});
const actions={restrict:"จำกัดการเข้าถึง",suppress:"ระงับการใช้งาน",correct:"แก้ไขเป็นรุ่นใหม่"};
const docStates={active:"อ่านได้ตามสิทธิ์",restricted:"จำกัดการเข้าถึง",suppressed:"ระงับการใช้งาน",quarantined:"อยู่ในเขตกักกัน"};
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function mountManaged({root=document,fetcher=globalThis.fetch.bind(globalThis)}={}){
  const $=id=>root.querySelector("#managed-"+id), state={me:null,authority:null,collections:[],activities:[],target:null,commands:new Map(),proposal:null,epoch:0,busy:false};
  const handlers=[];let sessionTimer,disposed=false,guardTurn=0;
  function on(target,event,fn){target.addEventListener(event,fn);handlers.push(()=>target.removeEventListener(event,fn));}
  function el(tag,text){const node=root.createElement(tag);if(text!==undefined)node.textContent=String(text);return node;}
  function status(text){$("status").textContent=text;}
  function has(...roles){return state.me?.roles.some(role=>roles.includes(role));}
  function canRead(){return has("data_steward","privacy_reviewer","custodian");}
  function clearContent(){$("content").textContent="";$("content").hidden=true;$("clear-content").hidden=true;}
  function clearProtected(){state.epoch++;state.commands.clear();state.proposal=null;state.target=null;state.collections=[];state.activities=[];clearContent();for(const form of root.querySelectorAll("form"))form.reset();for(const input of root.querySelectorAll("textarea"))input.value="";for(const id of ["documents","instructions","collection"])$(id).replaceChildren();$("create").elements.activity_id.replaceChildren();$("target").textContent="เลือกเอกสารจากรายการก่อน";$("snapshot-info").textContent="";for(const id of ["create-panel","upload","proposal-panel","recovery-panel"])$(id).hidden=true;}
  function clearSession(){clearTimeout(sessionTimer);clearProtected();state.me=null;state.authority=null;status("เซสชันหมดอายุ กลับหน้าหลักเพื่อเข้าสู่ระบบ");}
  function csrfFor(me){const name=me?.csrf_cookie_name;return name?(root.cookie.split(";").map(x=>x.trim()).find(x=>x.startsWith(name+"="))||"").slice(name.length+1):"";}
  function csrf(){return csrfFor(state.me);}
  function authorityKey(me){return JSON.stringify([me.id,[...me.roles].sort(),[...me.departments].sort(),me.member_revision??me.revision??null,me.csrf_cookie_name,csrfFor(me)]);}
  async function request(path,body){
    const generation=state.epoch,options={credentials:"same-origin",headers:{Accept:"application/json"}};
    if(body){options.method="POST";options.headers["Content-Type"]="application/json";options.headers["X-CSRF-Token"]=decodeURIComponent(csrf());options.body=JSON.stringify(body);}
    let response;try{response=await fetcher(path,options);}catch{throw new Error("network_unknown");}
    const data=await response.json();
    if(disposed||generation!==state.epoch)throw new Error("context_changed");
    if(!response.ok){if(response.status===401)clearSession();throw new Error(data?.error?.code||"request_failed");}
    return data;
  }
  async function mutate(path,data){
    const signature=path+JSON.stringify(data);let key=state.commands.get(signature);if(!key){key=crypto.randomUUID();state.commands.set(signature,key);}
    const result=await request(path,{command_key:key,...data});state.commands.delete(signature);return result;
  }
  async function guarded(fn,supersede=false){
    if(disposed||(state.busy&&!supersede))return;const turn=++guardTurn;state.busy=true;$("status").setAttribute("aria-busy","true");
    try{await fn();}catch(error){if(turn!==guardTurn||error.message==="context_changed")return;const codes={revision_conflict:"ข้อมูลเปลี่ยนแล้ว กรุณารีเฟรชและตรวจรุ่นใหม่",separation_required:"ต้องใช้ผู้ทบทวนอีกคน",approval_expired:"คำอนุมัติหมดอายุแล้ว",restore_quarantined:"คลังอยู่ในเขตกักกัน ยังเปิดอ่านไม่ได้",restore_reconciliation_required:"ต้องตรวจสอบคำสั่งที่ยังไม่ทราบผลให้เสร็จก่อนกู้คืน",consent_required:"ไม่มีความยินยอมที่มีผลสำหรับขอบเขตนี้",authentication_required:"เซสชันหมดอายุ กลับหน้าหลักเพื่อเข้าสู่ระบบ",network_unknown:"ยังยืนยันผลคำขอไม่ได้ ตรวจสถานะก่อนลองอีกครั้ง"};status(codes[error.message]||"ทำรายการไม่ได้ กรุณาตรวจสิทธิ์และสถานะล่าสุด");}
    finally{if(turn===guardTurn){state.busy=false;$("status").removeAttribute("aria-busy");}}
  }
  function button(label,fn){const node=el("button",label);node.type="button";node.addEventListener("click",()=>{if(!disposed)guarded(fn);});return node;}
  function items(data){if(!data||!Array.isArray(data.items)||data.items.length>100)throw new Error("invalid_response");return data.items;}
  async function loadDocuments(){
    clearContent();state.target=null;$("target").textContent="เลือกเอกสารจากรายการก่อน";
    const id=$("collection").value,selected=state.collections.find(c=>c.id===id);$("documents").replaceChildren();
    if(!selected){$("documents").append(el("p","ยังไม่มีคลังเอกสารในขอบเขตของคุณ"));return;}
    $("collection-state").textContent=selected.state==="ready"?"คลังพร้อมใช้งานตามสิทธิ์":"คลังอยู่ในเขตกักกัน";
    if(!canRead()){$("documents").append(el("p","สิทธิ์กู้คืนแสดงเฉพาะข้อมูลคลัง ไม่เปิดสิทธิ์อ่านเนื้อหา"));return;}
    if(selected.state!=="ready"){$("documents").append(el("p","ต้องทบทวนการกู้คืนและข้อจำกัดก่อนเปิดอ่าน"));return;}
    const docs=items(await request(base+"/collections/"+id+"/documents"));
    if(!docs.length)$("documents").append(el("p","ยังไม่มีเอกสารในคลังนี้"));
    for(const doc of docs){
      if(!uuid.test(doc.id)||!Number.isInteger(doc.version)||!Number.isInteger(doc.revision)||!(doc.state in docStates))throw new Error("invalid_response");
      const card=el("article");card.className="managed-record";card.append(el("code",doc.id),el("p","รุ่นเนื้อหา "+doc.version+" · รุ่นระเบียน "+doc.revision),el("p",docStates[doc.state]));
      const controls=el("div");controls.className="actions";
      if(doc.state==="active")controls.append(button("อ่านรุ่นปัจจุบัน",async()=>{const epoch=state.epoch,result=await request(base+"/collections/"+id+"/documents/"+doc.id+"/versions/"+doc.version);if(disposed||epoch!==state.epoch||!state.me)return;if(result.id!==doc.id||typeof result.content!=="string"||result.content.length>32768)throw new Error("invalid_response");$("content").textContent=result.content;$("content").hidden=false;$("clear-content").hidden=false;status("เปิดเนื้อหาตามสิทธิ์แล้ว");}));
      if(has("data_steward","custodian"))controls.append(button("เลือกเพื่อเสนอคำสั่ง",()=>{state.target=doc;$("target").textContent=doc.id+" · รุ่น "+doc.version+" · ระเบียน "+doc.revision;$("propose").querySelector("select").focus();}));
      card.append(controls);$("documents").append(card);
    }
  }
  async function loadInstructions(){
    if(!canRead()){$("instructions").replaceChildren(el("p","บัญชีนี้ใช้เฉพาะงานกู้คืน ไม่เปิดสิทธิ์อ่านคำสั่งหรือเนื้อหา"));return;}
    const rows=items(await request(base+"/instructions"));$("instructions").replaceChildren();
    if(!rows.length)$("instructions").append(el("p","ยังไม่มีคำสั่งในขอบเขตนี้"));
    for(const row of rows){
      if(!uuid.test(row.id)||!(row.state in outcomeLabels)||!(row.action in actions)||row.primary_verified!==(row.state==="verified"))throw new Error("invalid_response");
      const card=el("article");card.className="managed-record";const badge=el("p",outcomeLabels[row.state]);badge.className="managed-state";
      card.append(el("h3",actions[row.action]),badge,el("p","เอกสาร "+row.document_id),el("p","รุ่นเป้าหมาย "+row.target_version+" · ระเบียน "+row.target_revision),el("p","หมดอายุ "+new Date(row.expires_at).toLocaleString("th-TH")));
      if(row.processing_controls){const snapshot=row.processing_controls,details=el("details"),summary=el("summary","ขอบเขตและหลักฐานที่ผูกกับคำสั่งนี้");details.append(summary,el("p","ขอบเขต "+snapshot.id+" · ฉบับ "+snapshot.revision),el("p","ผู้ทบทวน "+snapshot.reviewed_by+" · หลักฐาน "+snapshot.review_evidence_ref),el("p","รหัสตรวจขอบเขต "+snapshot.digest));for(const control of snapshot.controls||[])details.append(el("p",control.id+" · ฉบับ "+control.revision+" · "+(control.data?.applicability==="reviewed_not_applicable"?"ทบทวนว่าไม่ใช้บังคับ":control.data?.applicability==="required"?"ต้องดำเนินการ":"หลักฐานที่เกี่ยวข้อง")));for(const dependency of snapshot.dependencies||[]){const instrument=dependency.data?.instrument;if(instrument)details.append(el("p","ต้นฉบับ "+instrument.version+" · SHA-256 "+instrument.sha256));}card.append(details);}else card.append(el("p","คำสั่งนี้ยังไม่มีขอบเขตองค์กรที่ทบทวนผูกไว้ ใช้ดำเนินงานองค์กรไม่ได้"));
      const controls=el("div");controls.className="actions";
      if(has("privacy_reviewer")&&row.proposed_by!==state.me.id&&row.action==="correct"&&row.state==="proposed"&&uuid.test(row.evidence_id))controls.append(button("ตรวจข้อความที่เสนอแก้ไข",async()=>{const epoch=state.epoch,result=await request(base+"/instructions/"+row.id+"/evidence?expected_revision="+row.revision);if(disposed||epoch!==state.epoch||!state.me)return;if(result.id!==row.evidence_id||result.instruction_id!==row.id||typeof result.content!=="string"||result.content.length>32768)throw new Error("invalid_response");$("content").textContent=result.content;$("content").hidden=false;$("clear-content").hidden=false;status("ข้อความที่เสนอสำหรับเอกสาร "+row.document_id+" รุ่น "+row.target_version);$("content").scrollIntoView({block:"nearest"});}));
      if(has("privacy_reviewer")&&row.proposed_by!==state.me.id&&["proposed","unknown"].includes(row.state)){const operation=row.state==="proposed"?"approve":"reconcile";controls.append(button(row.state==="proposed"?"ตรวจทบทวนและอนุมัติ":"ตรวจผลและกระทบยอด",async()=>{const result=await mutate(base+"/instructions/"+row.id+"/"+operation,{expected_revision:row.revision});status(outcomeLabels[result.state]);await loadInstructions();await loadDocuments();}));}
      card.append(controls);$("instructions").append(card);
    }
  }
  async function refresh(){
    let epoch=++state.epoch;clearContent();status("กำลังตรวจสถานะล่าสุด…");
    const me=await request("/api/enterprise/v1/me");if(disposed||epoch!==state.epoch)return;const authority=authorityKey(me);if(state.authority!==null&&state.authority!==authority){clearProtected();epoch=state.epoch;}state.me=me;state.authority=authority;clearTimeout(sessionTimer);const deadline=Math.min(state.me.session?.idle_seconds||0,state.me.session?.absolute_remaining_seconds||0);if(deadline<=0){clearSession();return;}sessionTimer=setTimeout(clearSession,deadline*1000);state.collections=items(await request(base+(canRead()?"/collections":"/recovery/collections")));if(epoch!==state.epoch)return;
    const select=$("collection"),previous=select.value;select.replaceChildren();for(const row of state.collections){if(!uuid.test(row.id))throw new Error("invalid_response");const option=el("option",row.id+" · "+row.department_id);option.value=row.id;select.append(option);}if(state.collections.some(row=>row.id===previous))select.value=previous;
    $("create-panel").hidden=!has("data_steward");$("upload").hidden=!has("data_steward","custodian");$("proposal-panel").hidden=!has("data_steward","custodian");$("recovery-panel").hidden=!has("system_administrator","privacy_reviewer");$("snapshot").hidden=!has("system_administrator");
    $("recovery").querySelector('[value="quarantine"]').hidden=!has("system_administrator");$("recovery").querySelector('[value="reconcile"]').hidden=!has("privacy_reviewer");
    if(has("data_steward")){state.activities=(await request("/api/enterprise/v1/activities")).filter(row=>row.state==="active");const options=$("create").elements.activity_id;options.replaceChildren();for(const activity of state.activities){const option=el("option",activity.data.title);option.value=activity.id;options.append(option);}}
    await loadDocuments();await loadInstructions();status("แสดงสถานะล่าสุดแล้ว การส่งคิวยังไม่ใช่ผลสำเร็จ");
  }
  on($("refresh"),"click",()=>guarded(refresh,true));on($("collection"),"change",()=>guarded(loadDocuments));on($("clear-content"),"click",clearContent);
  on($("create"),"submit",event=>{event.preventDefault();guarded(async()=>{const form=event.target,e=form.elements,activity=state.activities.find(row=>row.id===e.activity_id.value);if(!activity)throw new Error("invalid_request");const data={activity_id:activity.id,expected_activity_revision:activity.revision};if(e.subject_id.value)data.subject_id=e.subject_id.value;if(e.purpose_version.value)data.purpose_version=e.purpose_version.value;await mutate(base+"/collections",{data});form.reset();await refresh();});});
  on($("upload"),"submit",event=>{event.preventDefault();guarded(async()=>{await mutate(base+"/collections/"+$("collection").value+"/documents",{content:event.target.elements.content.value,content_type:"text/plain"});event.target.reset();await loadDocuments();status("เพิ่มเอกสารที่เข้ารหัสแล้ว");});});
  on($("propose").elements.action,"change",event=>{$("correction-label").hidden=event.target.value!=="correct";$("propose").elements.correction.required=event.target.value==="correct";});
  on($("propose"),"submit",event=>{event.preventDefault();guarded(async()=>{const target=state.target;if(!target)throw new Error("invalid_request");const fields=event.target.elements,signature=JSON.stringify([target,fields.action.value,fields.minutes.value,fields.correction.value]);if(state.proposal?.signature!==signature)state.proposal={signature,data:{collection_id:target.collection_id,document_id:target.id,expected_version:target.version,expected_revision:target.revision,action:fields.action.value,expires_at:new Date(Date.now()+Number(fields.minutes.value)*60000).toISOString()}};const data=state.proposal.data;if(data.action==="correct"&&!data.evidence_id){const proof=await mutate(base+"/evidence",{data:{collection_id:target.collection_id,document_id:target.id,expected_version:target.version,content_type:"text/plain",content:fields.correction.value}});data.evidence_id=proof.id;}const result=await mutate(base+"/instructions",{data});state.proposal=null;fields.correction.value="";status(outcomeLabels[result.state]);await loadInstructions();});});
  on($("snapshot"),"click",()=>guarded(async()=>{const result=await mutate(base+"/collections/"+$("collection").value+"/snapshots",{});$("snapshot-info").textContent="จุดทดสอบ "+result.id+" · รุ่น "+result.revision;$("recovery").elements.snapshot_id.value=result.id;$("recovery").elements.expected_revision.value=result.revision;status("บันทึกจุดทดสอบแล้ว ยังไม่ใช่การกู้คืนที่รับรอง");}));
  on($("recovery"),"submit",event=>{event.preventDefault();guarded(async()=>{const e=event.target.elements,id=e.snapshot_id.value;if(!uuid.test(id))throw new Error("invalid_request");const operation=event.submitter?.value;if(!["quarantine","reconcile"].includes(operation))throw new Error("invalid_request");const result=await mutate(base+"/snapshots/"+id+"/"+operation,{expected_revision:Number(e.expected_revision.value)});e.expected_revision.value=result.revision;await refresh();status(result.state==="quarantined"?"กู้คืนเข้ากักกันแล้ว ยังเปิดอ่านไม่ได้":"นำข้อจำกัดกลับมาใช้แล้ว ขอบเขตระบบจริงยังรอการรับรอง");});});
  const ready=guarded(refresh);
  return {ready,dispose(){disposed=true;clearTimeout(sessionTimer);clearSession();for(const remove of handlers)remove();}};
}
if(typeof document!=="undefined"&&document.querySelector("[data-managed-root]"))mountManaged();
