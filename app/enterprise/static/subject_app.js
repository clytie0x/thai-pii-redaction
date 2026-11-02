"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const state = { me: null, current: null, pending: null, busy: false, nextCursor: null, paging: false };
  const labels = { granted: "ให้ความยินยอมแล้ว", withdrawn: "ถอนความยินยอมแล้ว", refused: "ไม่ให้ความยินยอม", no_consent: "ยังไม่มีความยินยอม", identity_unresolved: "รอตรวจสอบตัวตน", identity_changed: "ตัวตนเปลี่ยน ต้องยืนยันใหม่", purpose_changed: "วัตถุประสงค์เปลี่ยน ความยินยอมเดิมใช้ไม่ได้", propagation_pending: "บันทึกความยินยอมใหม่แล้ว แต่พักการประมวลผลระหว่างรอหลักฐานแจ้งผู้รับเดิม", propagation_failed: "บันทึกความยินยอมใหม่แล้ว แต่ยังประมวลผลไม่ได้เพราะงานแจ้งผู้รับเดิมไม่สำเร็จ" };
  const actionLabels = { grant: "ให้ความยินยอม", refuse: "ไม่ให้ความยินยอม", withdraw: "ถอนความยินยอม" };
  function message(text, error = false) { $("message").textContent = text; $("message").classList.toggle("error", error); }
  function csrf() { const name = state.me?.csrf_cookie_name; return document.cookie.split(";").map(x => x.trim()).find(x => x.startsWith(name + "="))?.slice(name.length + 1) || ""; }
  async function api(path, body) {
    let response;
    try { response = await fetch("/api/subject/v1" + path, { method: body ? "POST" : "GET", credentials: "same-origin", cache: "no-store", headers: body ? { "Content-Type": "application/json", "X-CSRF-Token": csrf() } : {}, body: body ? JSON.stringify(body) : undefined }); }
    catch { throw { code: "network_error" }; }
    const result = await response.json();
    if (!response.ok) throw { code: result.error?.code || "request_failed", status: response.status };
    return result;
  }
  function errorText(error) {
    if (error.status === 401) { state.me = null; $("workspace").hidden = true; $("login-panel").hidden = false; return "เซสชันหมดอายุหรือบัญชีเปลี่ยน กรุณาเข้าสู่ระบบอีกครั้ง"; }
    if (["revision_conflict", "notice_scope_mismatch", "notice_presentation_required"].includes(error.code)) return "ข้อมูลเปลี่ยนหรือประกาศหมดอายุ กรุณารีเฟรชประกาศแล้วตัดสินใจใหม่ คำขอเดิมไม่ได้เปลี่ยนสถานะล่าสุด";
    if (error.code === "network_error") return "ยังตรวจผลคำขอไม่ได้ กรุณาตรวจการเชื่อมต่อแล้วลองคำขอเดิมอีกครั้ง";
    return "ดำเนินการไม่ได้ กรุณาลองใหม่หรือติดต่อผู้รับผิดชอบ";
  }
  function setBusy(value) { state.busy = value; document.querySelectorAll("#choice-form button,#refresh,#logout,#retry").forEach(b => { b.disabled = value || (b.value && b.value !== "withdraw" && state.current?.grant_allowed === false); }); $("notice-panel").setAttribute("aria-busy", String(value)); }
  async function refresh() {
    message("กำลังโหลดประกาศ…");
    try {
      state.me = await api("/me"); $("login-panel").hidden = true; $("workspace").hidden = false;
      $("notice-list").replaceChildren(); state.nextCursor = null;
      await loadPage();
      message("");
    } catch (e) { message(errorText(e), e.status !== 401); }
  }
  async function loadPage() {
    if (state.paging) return;
    state.paging = true; $("load-more").disabled = true;
    try {
      const page = await api("/notices?limit=50" + (state.nextCursor ? "&cursor=" + encodeURIComponent(state.nextCursor) : ""));
      if (!page.items.length && !$("notice-list").children.length) $("notice-list").textContent = "ยังไม่มีประกาศที่พร้อมให้คุณตัดสินใจ หากรายการไม่ถูกต้อง กรุณาติดต่อองค์กร";
      for (const notice of page.items) {
        const card = document.createElement("article"); card.className = "notice-card";
        const title = document.createElement("h2"); title.textContent = notice.title;
        const button = document.createElement("button"); button.type = "button"; button.textContent = "อ่านประกาศและจัดการความยินยอม";
        button.addEventListener("click", () => openNotice(notice.notice_id)); card.append(title, button); $("notice-list").append(card);
      }
      state.nextCursor = page.next_cursor; $("load-more").hidden = !state.nextCursor;
    } finally { state.paging = false; $("load-more").disabled = false; }
  }
  async function updateStatus(status) {
    $("authority").textContent = "สถานะปัจจุบัน: " + (labels[status.reason] || "รอตรวจสอบ") + " · ฉบับการตัดสินใจ " + status.revision;
    $("propagation").replaceChildren();
    if (!status.propagation.length) $("propagation").textContent = "ไม่มีงานแจ้งผู้รับสำหรับการตัดสินใจล่าสุด";
    for (const row of status.propagation) {
      const item = document.createElement("li"); item.textContent = "การตัดสินใจฉบับ " + row.event_revision + " · ผู้รับลำดับ " + row.recipient + ": " + ({ pending: "รอดำเนินการ", failed: "ยังไม่สำเร็จ", verified: "ผู้ทบทวนยืนยันหลักฐานภายนอกแล้ว" }[row.state] || "รอตรวจสอบ"); $("propagation").append(item);
    }
    const history = await api("/purposes/" + state.current.purpose_version + "/history"); $("history").replaceChildren();
    if (!history.length) $("history").textContent = "ยังไม่มีประวัติการตัดสินใจ";
    for (const row of history) {
      const item = document.createElement("li"); const channel = row.channel === "subject_portal" ? "ผ่านบัญชีเจ้าของข้อมูล" : "คำขอนอกระบบที่ผ่านการทบทวนหลักฐาน";
      item.textContent = (actionLabels[row.action] || "ทบทวน") + " · " + new Date(row.received_at).toLocaleString("th-TH") + " · " + channel; $("history").append(item);
    }
  }
  async function openNotice(id) {
    if (state.busy) return;
    if (state.pending) { message("กรุณาตรวจผลคำขอที่รออยู่ก่อนรีเฟรชประกาศ", true); return; }
    message("กำลังโหลดประกาศฉบับเต็ม…");
    try {
      state.current = await api("/notices/" + id + "/presentation", {}); state.pending = null; $("retry").hidden = true;
      $("notice-title").textContent = state.current.title; $("purpose").textContent = "วัตถุประสงค์: " + state.current.purpose;
      $("notice-body").textContent = state.current.body; $("notice-version").textContent = state.current.notice_proof.notice_revision;
      $("notice-digest").textContent = state.current.notice_proof.notice_digest; $("category-options").replaceChildren();
      for (const category of state.current.categories) {
        const label = document.createElement("label"); const check = document.createElement("input"); check.type = "checkbox"; check.name = "category"; check.value = category;
        label.append(check, document.createTextNode(category)); $("category-options").append(label);
      }
      $("notice-panel").hidden = false; $("notice-list").hidden = true; await updateStatus(state.current.effective);
      $("load-more").hidden = true;
      setBusy(false);
      message(""); $("notice-title").focus();
    } catch (e) { message(errorText(e), true); }
  }
  async function submitPending() {
    if (!state.pending || state.busy) return;
    setBusy(true); message("กำลังบันทึกการตัดสินใจ…");
    try {
      const result = await api("/events", state.pending); state.current.effective = result.effective;
      await updateStatus(result.effective); state.pending = null; $("retry").hidden = true;
      const id = state.current.purpose_version;
      state.current = await api("/notices/" + id + "/presentation", {});
      document.querySelectorAll("#category-options input").forEach(c => { c.checked = false; });
      message("บันทึกการตัดสินใจแล้ว กรุณาดูสถานะและงานแจ้งผู้รับข้อมูลด้านล่าง"); $("message").focus();
    } catch (e) {
      message(errorText(e), true);
      if (e.code === "network_error") $("retry").hidden = false;
      else { state.pending = null; $("retry").hidden = true; }
    } finally { setBusy(false); }
  }
  $("choice-form").addEventListener("submit", event => {
    event.preventDefault(); if (state.busy || !state.current || state.pending) return;
    const action = event.submitter?.value; if (!actionLabels[action]) return;
    let categories = [...document.querySelectorAll("#category-options input:checked")].map(c => c.value);
    if (action === "grant" && !categories.length) { message("กรุณาเลือกหมวดข้อมูลที่ต้องการให้ความยินยอม", true); return; }
    if (action !== "grant") categories = [...state.current.categories];
    state.pending = { command_key: crypto.randomUUID(), notice_version: state.current.notice_proof,
      purpose_scope: { purpose_version: state.current.purpose_version, categories, expected_revision: state.current.effective.revision }, action, affirmative: true };
    submitPending();
  });
  $("retry").addEventListener("click", submitPending);
  $("load-more").addEventListener("click", () => loadPage().catch(e => message(errorText(e), true)));
  $("refresh").addEventListener("click", () => state.current && !$("notice-panel").hidden ? openNotice(state.current.purpose_version) : refresh());
  $("back").addEventListener("click", () => { if (state.busy || state.pending) { message("กรุณาตรวจผลคำขอที่รออยู่ก่อนออกจากประกาศ", true); return; } $("notice-panel").hidden = true; $("notice-list").hidden = false; $("load-more").hidden = !state.nextCursor; });
  $("logout").addEventListener("click", async () => {
    if (state.busy) return;
    try { const response = await fetch("/subject/auth/logout", { method: "POST", credentials: "same-origin", headers: { "X-CSRF-Token": csrf() } }); if (!response.ok) throw {}; state.me = null; state.current = null; state.pending = null; $("workspace").hidden = true; $("login-panel").hidden = false; message("ออกจากระบบแล้ว"); }
    catch { message("ออกจากระบบไม่สำเร็จ กรุณาลองใหม่", true); }
  });
  refresh();
})();
