"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const base = "/api/enterprise/v1";
  const state = { me: null, issuer: null, canReadSubjects: false, pending: null, busy: false, loadedLink: null, loadedOffline: null, loadedTasks: [] };
  const list = value => value.split(",").map(s => s.trim()).filter(Boolean);
  const fields = form => Object.fromEntries(new FormData(form));
  const csrf = () => { const name = state.me?.csrf_cookie_name; return document.cookie.split(";").map(s => s.trim()).find(s => s.startsWith(name + "="))?.slice(name.length + 1) || ""; };
  function message(text, error = false) { $("message").textContent = text; $("message").classList.toggle("error", error); }
  async function api(path, body) {
    let response;
    try { response = await fetch(base + path, { method: body ? "POST" : "GET", credentials: "same-origin", cache: "no-store", headers: body ? { "Content-Type": "application/json", "X-CSRF-Token": csrf() } : {}, body: body ? JSON.stringify(body) : undefined }); }
    catch { throw { code: "network_error" }; }
    const result = await response.json(); if (!response.ok) throw { status: response.status, code: result.error?.code }; return result;
  }
  const errors = { separation_required: "ผู้เสนอและผู้ทบทวนต้องเป็นคนละคน", revision_conflict: "ข้อมูลเปลี่ยน กรุณาโหลดฉบับล่าสุดและทบทวนใหม่", identity_conflict: "ข้อมูลการเชื่อมโยงขัดแย้ง ต้องตรวจสอบก่อนดำเนินการ", proposal_authority_expired: "สิทธิ์ของผู้เสนอเปลี่ยน ต้องรับข้อเสนอใหม่", invalid_request: "กรุณาตรวจรหัส ฉบับ เวลา และหลักฐานที่จำเป็น", forbidden: "บัญชีนี้ไม่มีสิทธิ์หรืออยู่นอกขอบเขตงาน", record_unavailable: "ไม่พบระเบียนในขอบเขตที่ได้รับอนุญาต", identity_unresolved: "ตัวตนยังไม่ยืนยัน คำสั่งนี้ยังดำเนินการไม่ได้", network_error: "ยังตรวจผลไม่ได้ กรุณาลองคำสั่งเดิมอีกครั้ง" };
  function failure(e) { if (e.status === 401) { $("workspace").hidden = true; return "เซสชันหมดอายุ กรุณาเข้าสู่ระบบเจ้าหน้าที่"; } return errors[e.code] || "บันทึกไม่ได้ กรุณาตรวจข้อมูลและหลักฐานแล้วลองใหม่"; }
  function busy(value) { state.busy = value; document.querySelectorAll("form button,#retry").forEach(b => { b.disabled = value; }); }
  async function send() {
    if (!state.pending || state.busy) return;
    busy(true); message("กำลังบันทึก…");
    try { const result = await api(state.pending.path, state.pending.body); $("receipt").textContent = "รหัส " + result.id + " · สถานะ " + result.state + " · ฉบับ " + result.revision + (result.subject_id ? " · รหัสเจ้าของข้อมูล " + result.subject_id + " · ฉบับตัวตน " + result.link_revision : "") + (result.portal_act === false ? " · คำขอนอกระบบ ไม่ใช่การคลิกพอร์ทัล" : ""); state.pending = null; $("retry").hidden = true; message("บันทึกแล้ว โปรดใช้รหัสและฉบับนี้ในการทบทวนขั้นต่อไป"); $("message").focus(); }
    catch (e) { message(failure(e), true); if (e.code === "network_error") $("retry").hidden = false; else { state.pending = null; $("retry").hidden = true; } }
    finally { busy(false); }
  }
  function submit(path, body) { if (state.pending || state.busy) { message("กรุณาตรวจผลคำสั่งที่รออยู่ก่อนส่งคำสั่งใหม่", true); return; } state.pending = { path, body: { command_key: crypto.randomUUID(), ...body } }; send(); }
  $("link-form").addEventListener("submit", event => { event.preventDefault(); const f = fields(event.target); const { subject_id, expected_revision, ...data } = f; data.issuer = state.issuer; data.departments = list(data.departments); submit("/subjects/links", { data, subject_id: subject_id || null, expected_revision: expected_revision ? Number(expected_revision) : null }); });
  $("load-link").addEventListener("click", async () => {
    try { const form = $("link-review-form"); const id = form.elements.record_id.value; const row = await api("/subjects/links/" + encodeURIComponent(id)); state.loadedLink = row; form.elements.expected_revision.value = row.revision; $("link-details").replaceChildren(); const names = { issuer: "ผู้ออกบัญชี", oidc_subject: "รหัสบัญชีเจ้าของข้อมูล", source_system: "ระบบต้นทาง", source_record_id: "รหัสต้นทาง", source_version: "ฉบับต้นทาง", departments: "แผนก", identity_evidence_ref: "หลักฐานตัวตน", capacity_evidence_ref: "หลักฐานความสามารถ", state: "สถานะ" }; for (const [key, name] of Object.entries(names)) { const term = document.createElement("dt"); const value = document.createElement("dd"); term.textContent = name; value.textContent = Array.isArray(row[key]) ? row[key].join(", ") : row[key]; $("link-details").append(term, value); } message("โหลดรายละเอียดสำหรับทบทวนแล้ว"); }
    catch (e) { state.loadedLink = null; message(failure(e), true); }
  });
  $("link-review-form").addEventListener("submit", event => { event.preventDefault(); const f = fields(event.target); if (!state.loadedLink || state.loadedLink.id !== f.record_id || state.loadedLink.revision !== Number(f.expected_revision)) { message("กรุณาโหลดรายละเอียดฉบับที่ต้องการทบทวนก่อน", true); return; } submit("/subjects/links/" + encodeURIComponent(f.record_id) + (f.privacy === "true" ? "/privacy-review" : "/review"), { expected_revision: Number(f.expected_revision), decision: f.decision, evidence_ref: f.evidence_ref }); });
  $("offline-form").addEventListener("submit", event => { event.preventDefault(); const f = fields(event.target); const { purpose_version, categories, expected_revision, ...data } = f; data.capacity_evidence_ref ||= null; data.representative_authority_ref ||= null; data.scope = { purpose_version, categories: list(categories), expected_revision: Number(expected_revision) }; submit("/consent/offline", { data }); });
  $("load-offline").addEventListener("click", async () => {
    try { const form = $("offline-review-form"); const row = await api("/consent/offline/" + encodeURIComponent(form.elements.record_id.value)); state.loadedOffline = row; form.elements.expected_revision.value = row.revision; $("offline-details").replaceChildren(); const names = { subject_id: "รหัสเจ้าของข้อมูล", purpose_version: "ฉบับวัตถุประสงค์", mode: "ช่องทาง", action: "การตัดสินใจ", categories: "หมวดข้อมูล", link_revision: "ฉบับตัวตน", expected_consent_revision: "ฉบับความยินยอม", source_received_at: "เวลารับจากต้นทาง", source_evidence_ref: "หลักฐานต้นฉบับ", capacity_evidence_ref: "หลักฐานความสามารถ", representative_authority_ref: "หลักฐานอำนาจผู้แทน", state: "สถานะ" }; for (const [key, name] of Object.entries(names)) { const term = document.createElement("dt"); const value = document.createElement("dd"); term.textContent = name; value.textContent = Array.isArray(row[key]) ? row[key].join(", ") : row[key] ?? "ไม่มี"; $("offline-details").append(term, value); } message("โหลดคำขอแล้ว ต้องตรวจหลักฐานต้นฉบับก่อนอนุมัติ"); }
    catch (e) { state.loadedOffline = null; message(failure(e), true); }
  });
  $("offline-review-form").addEventListener("submit", event => { event.preventDefault(); const f = fields(event.target); if (!state.loadedOffline || state.loadedOffline.id !== f.record_id || state.loadedOffline.revision !== Number(f.expected_revision)) { message("กรุณาโหลดคำขอฉบับที่ต้องการทบทวนก่อน", true); return; } submit("/consent/offline/" + encodeURIComponent(f.record_id) + "/review", { expected_revision: Number(f.expected_revision), decision: f.decision, evidence_ref: f.evidence_ref }); });
  $("status-form").addEventListener("submit", async event => {
    event.preventDefault(); const f = fields(event.target);
    const record = encodeURIComponent(f.subject_id) + "/purposes/" + encodeURIComponent(f.purpose_version);
    const path = state.canReadSubjects ? "/subjects/" + record : "/consent/subjects/" + record + "/propagation";
    try { const row = await api(path); state.loadedTasks = row.propagation; $("current-status").textContent = (state.canReadSubjects ? "ฉบับการตัดสินใจ " + row.revision + " · อำนาจจากความยินยอม " + (row.allowed ? "มีผลในขอบเขตที่เลือก" : "ไม่มีผล") + " · " : "") + "การแจ้งผู้รับ " + (row.propagation_complete ? "หลักฐานงานที่มีอยู่ครบ" : "ยังไม่ครบ"); $("pending-propagation").replaceChildren(); for (const task of row.propagation) { const item = document.createElement("li"); item.textContent = "การตัดสินใจฉบับ " + task.event_revision + " · ผู้รับลำดับ " + task.recipient + " · รหัสงาน " + task.id + " · " + ({ pending: "รอดำเนินการ", failed: "ยังไม่สำเร็จ", verified: "ยืนยันหลักฐานแล้ว" }[task.state] || "รอตรวจสอบ"); $("pending-propagation").append(item); } message("โหลดสถานะแล้ว"); }
    catch (e) { state.loadedTasks = []; message(failure(e), true); }
  });
  $("propagation-form").addEventListener("submit", event => { event.preventDefault(); const f = fields(event.target); const task = state.loadedTasks.find(row => row.id === f.record_id); if (!task || task.state === "verified") { message("กรุณาโหลดสถานะและเลือกงานฉบับที่ยังไม่ยืนยันก่อนทบทวนหลักฐาน", true); return; } submit("/consent/propagation/" + encodeURIComponent(f.record_id) + "/review", { state: f.state, evidence_ref: f.evidence_ref, evidence_scope: { consent_event_id: task.consent_event_id, event_revision: task.event_revision, recipient_ordinal: task.recipient, expected_state: task.state } }); });
  $("retry").addEventListener("click", send);
  (async () => {
    message("กำลังตรวจสิทธิ์เจ้าหน้าที่…");
    try { state.me = await api("/me"); const setup = await api("/subjects/setup"); state.issuer = setup.issuer; state.canReadSubjects = setup.can_read_subjects; const roles = new Set(state.me.roles); $("workspace").hidden = false; $("scope").textContent = "แผนกที่ได้รับอนุญาต: " + state.me.departments.join(", "); $("link-panel").hidden = !roles.has("case_manager") && !roles.has("identity_steward"); $("review-link-panel").hidden = !roles.has("identity_steward") && !roles.has("privacy_reviewer"); $("offline-panel").hidden = !roles.has("case_manager"); $("offline-review-panel").hidden = !roles.has("privacy_reviewer"); $("propagation-panel").hidden = !roles.has("custodian") && !roles.has("privacy_reviewer"); message(""); }
    catch (e) { message(failure(e), true); }
  })();
})();
