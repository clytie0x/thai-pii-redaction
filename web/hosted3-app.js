(() => {
  "use strict";

  const $ = id => document.getElementById(id);
  const TIMING_UNAVAILABLE = "timing_unavailable";
  const controls = $("appControls");
  const state = { generation: 0, previewRequest: 0, inspectRequest: 0, inspectReport: null, authorityMutation: false, joinPending: false, claimInFlight: false, authority: null, task: null, anchor: null, preview: null, source: "", file: null, result: null, queue: null, claimAbort: null, queueStartedAt: 0, providerRunning: false, returnFocus: null, queuePaused: false };
  const taskPanels = { pdf: $("h3PdfTask"), text: $("h3TextTask"), inspect: $("h3InspectTask") };
  const sensitivePanels = [$("h3Preview"), $("h3Queue"), $("h3Result"), $("h3Recovery")];
  let recoveryAction = null;
  let presenterReturnFocus = null;
  const destinations = Object.freeze({
    "privacy-scan": Object.freeze({ task: "inspect", focus: "h3Detect" }),
    "pdpa-report": Object.freeze({ task: "inspect", focus: "h3Report" }),
    "safe-ai": Object.freeze({ task: "text", focus: "h3Text" }),
    "guided-demo": Object.freeze({ task: "inspect", disclosure: "h3SyntheticEvidence" }),
    "how-it-works": Object.freeze({ task: "text", focus: "h3TextTitle" }),
    "providerEvidenceCard": Object.freeze({ task: "text", focus: "h3TextTitle", afterResult: true }),
    "synthetic-demo": Object.freeze({ task: "inspect", disclosure: "h3SyntheticEvidence" })
  });
  const syntheticSamples = Object.freeze({
    hr: "ข้อมูลสังเคราะห์ HR: คุณตัวอย่าง สมัครงาน โทร 081-000-1020 อีเมล hr@example.invalid",
    healthcare: "ข้อมูลสังเคราะห์ healthcare: ผู้ป่วยตัวอย่าง เลขบัตร 1-1017-00230-70-8 โทร 082-000-2040",
    education: "ข้อมูลสังเคราะห์ education: นักเรียนตัวอย่าง รหัส 65001234 ผู้ปกครอง โทร 083-000-3060",
    customer: "ข้อมูลสังเคราะห์ customer service: ลูกค้าตัวอย่าง โทร 084-000-4080 อีเมล service@example.invalid",
    government: "ข้อมูลสังเคราะห์ government: นายประชาชน ตัวอย่าง ที่อยู่ 99/12 ถนนสาธิต โทร 074-000-505"
  });
  const errorCopy = Object.freeze({
    authentication_required: "Session สิ้นสุดแล้ว AI Guard ล้างข้อมูลและสิทธิ์ในหน้านี้ กรุณาเริ่ม Standard access หรือใช้ Priority Invite ใหม่",
    control_forbidden: "สิทธิ์หรือ browser context นี้ใช้ action ดังกล่าวไม่ได้ ไม่มีการส่งให้ provider",
    session_review_window: "เวลาของ session ไม่พอสำหรับการตรวจทานและเข้าคิว เริ่ม access ใหม่ก่อน",
    approval_invalid: "Approval ใช้กับ session หรือ payload นี้ไม่ได้ ต้องสร้าง preview ใหม่",
    approval_consumed: "Approval นี้ถูกใช้แล้ว ต้องสร้าง preview ใหม่",
    approval_expired: "การอนุมัติหมดอายุ ต้อง preview ใหม่",
    payload_too_large: "ข้อมูลมีขนาดเกินขอบเขตที่รองรับ กรุณาลดขนาดก่อนลองใหม่",
    request_schema_invalid: "รูปแบบคำขอไม่ถูกต้อง ไม่มีการส่งให้ provider",
    provider_payload_too_large: "ข้อความหลังปกป้องมีขนาดเกิน provider envelope กรุณาลดข้อความแล้ว preview ใหม่",
    document_unsupported: "PDF นี้มีโครงสร้างที่ไม่รองรับ กรุณาเลือก text-layer PDF อื่น",
    pdf_text_layer_required: "รองรับเฉพาะ PDF ที่มี text layer ไม่รองรับ scan หรือ OCR",
    pdf_visual_content_unsupported: "PDF มี visual content เกินขอบเขตที่ตรวจทานได้ และระบบไม่ใช้ OCR",
    document_too_complex: "PDF หรือ protected extraction ซับซ้อนเกินขอบเขต กรุณาใช้เอกสารที่สั้นกว่า",
    document_busy: "ตัวแยก PDF กำลังใช้งาน ไม่มีการอ่านไฟล์นี้ กรุณาลองใหม่ภายหลัง",
    document_parser_unavailable: "ตัวแยก PDF ไม่พร้อม ไม่มีการส่งให้ provider กรุณาลองใหม่ภายหลัง",
    queue_full: "คิวเต็มชั่วคราว Protected preview ยังอยู่และจะตรวจ deadline ใหม่ก่อน retry",
    queue_rate_limited: "คิวรับคำขอชั่วคราวไม่พร้อม Protected preview ยังอยู่และจะตรวจ deadline ใหม่ก่อน retry",
    approval_registry_full: "ระบบเก็บ approval ชั่วคราวเต็ม ไม่มีการส่งให้ provider กรุณาลองเข้าคิวใหม่ภายหลัง",
    queue_invalid: "Queue authority ใช้ไม่ได้ ต้องสร้าง preview และเข้าคิวใหม่",
    queue_expired: "คิวหมดอายุ ไม่มีข้อความใดถูกส่งให้ provider ต้องสร้าง preview ใหม่",
    claim_missed_expired: "Automatic start ไม่สำเร็จสองครั้ง ไม่มีข้อความใดถูกส่งให้ provider ต้องสร้าง preview ใหม่",
    provider_already_running: "Provider อาจยังทำงานอยู่ การล้างหน้านี้ไม่สามารถรับประกันการยกเลิก upstream ได้",
    residual_pii: "AI Guard ยังพบ residual PII จึงระงับผลและไม่แสดงคำตอบที่กู้คืน",
    document_integrity_failed: "Protected document ไม่ผ่าน integrity gate จึงไม่มี artifact ที่ใช้ได้",
    document_structure_invalid: "Provider result ไม่ผ่าน structured-output gate จึงไม่มี artifact ที่ใช้ได้",
    provider_configuration: "Provider ยังไม่พร้อมจากการตั้งค่าบริการ กรุณาลองภายหลัง",
    provider_unavailable: "Provider ไม่ตอบสำเร็จ คำขอนี้สิ้นสุดแล้ว ต้องสร้าง preview ใหม่ก่อน retry",
    provider_rejected: "Provider ปฏิเสธคำขอ ไม่มีผลลัพธ์ที่ตรวจสอบได้",
    provider_response_invalid: "Provider ส่ง response ที่ไม่ผ่าน validation จึงไม่มีผลลัพธ์ที่แสดงได้",
    provider_timeout: "Provider หมดเวลา คำขออาจไปถึง upstream แล้ว ห้ามส่งซ้ำจนสถานะนี้สิ้นสุด",
    provider_failed: "Provider request ไม่สำเร็จ คำขอนี้สิ้นสุดแล้ว ต้องสร้าง preview ใหม่",
    restore_failed: "การกู้คืนไม่ผ่าน gate จึงระงับคำตอบและไม่แสดงผลที่กู้คืน",
    restoration_incomplete: "Pathumma ตอบกลับแล้ว แต่ AI Guard คืน token ได้ไม่ครบ จึงระงับผลลัพธ์ ต้องสร้าง Preview ใหม่",
    restoration_unsafe: "Pathumma ตอบกลับแล้ว แต่ AI Guard พบสัญญาณ PII ที่ยืนยันที่มาไม่ได้หลัง restoration จึงระงับผลลัพธ์ ต้องสร้าง Preview ใหม่",
    internal_error: "บริการไม่สามารถยืนยันผลลัพธ์ได้ จึงระงับผลและล้าง execute authority"
  });
  let requestedDestination = null;

  function now() { return performance.now(); }
  function hide(...nodes) { nodes.flat().forEach(node => { if (node) node.hidden = true; }); }
  function show(node) { if (node) node.hidden = false; }
  function clearNode(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function announce(message) { $("appAnnouncement").textContent = message; }
  function unlockControls() { controls.removeAttribute("inert"); $("appBootstrapNotice").hidden = true; }
  function syncActionLocks() {
    const workLocked = state.providerRunning || !!state.queue;
    for (const id of ["h3StartStandard", "h3ShowPriority", "h3PrioritySubmit"]) $(id).disabled = state.authorityMutation;
    $("h3EndAuthority").disabled = state.authorityMutation || workLocked;
    const providerLocked = [
      ...document.querySelectorAll("[data-h3-task]"), ...document.querySelectorAll(".h3-back"), ...document.querySelectorAll("[data-h3-sample]"), ...document.querySelectorAll("input[name=h3Mode]"),
      ...["h3Pdf", "h3PdfPreview", "h3Text", "h3TextPreview", "h3InspectText", "h3Detect", "h3Guard", "h3Report", "h3DownloadReport", "h3Approve", "h3DiscardPreview"].map($),
    ];
    providerLocked.forEach(node => { node.disabled = workLocked; });
  }
  function setAuthorityBusy(value) { state.authorityMutation = value; syncActionLocks(); }
  function setProviderRunning(value) { state.providerRunning = value; syncActionLocks(); }
  function setTaskBusy(task, value) {
    const button = task === "pdf" ? $("h3PdfPreview") : $("h3TextPreview"), panel = taskPanels[task];
    button.disabled = value; button.textContent = value ? (task === "pdf" ? "Uploading & extracting…" : "Creating protected preview…") : (task === "pdf" ? "Upload & extract" : "Preview protected text");
    value ? panel.setAttribute("aria-busy", "true") : panel.removeAttribute("aria-busy");
  }
  function errorCode(body) { return body && body.error && typeof body.error.code === "string" ? body.error.code : "request_failed"; }
  function isCurrent(generation) { return generation === state.generation; }
  function isPlainObject(value) { return !!value && typeof value === "object" && !Array.isArray(value); }
  function finiteNonnegative(value) { return typeof value === "number" && Number.isFinite(value) && value >= 0; }
  function joinedLabels(values) { return Array.isArray(values) && values.length ? values.map(String).join(" · ") : "ไม่พบธง"; }

  function renderDataMap(target, text, counts, highlights = []) {
    clearNode(target);
    const entries = isPlainObject(counts)
      ? Object.entries(counts).filter(([type, count]) => typeof type === "string" && Number.isInteger(count) && count > 0)
      : [];
    const intro = document.createElement("p");
    intro.textContent = entries.length
      ? `พบ ${entries.reduce((sum, [, count]) => sum + count, 0)} รายการใน ${entries.length} ประเภท โดยไม่แสดงค่าข้อมูล`
      : "ไม่พบประเภทข้อมูลส่วนบุคคลในผลปัจจุบัน";
    target.append(intro);
    if (!entries.length) return;
    const list = document.createElement("ul"); list.className = "hosted3-map-list";
    for (const [type, count] of entries) {
      const item = document.createElement("li");
      const label = document.createElement("strong"); label.textContent = `${type} · ${count}`; item.append(label);
      const positions = Array.isArray(highlights) ? highlights.filter(value => value?.data_type === type && Number.isInteger(value.start) && value.start >= 0) : [];
      if (positions.length && text) {
        const position = document.createElement("span");
        position.textContent = `ตำแหน่งเชิงสัดส่วน ${positions.map(value => value.start).join(", ")} จาก ${[...text].length} code points`;
        item.append(position);
      }
      list.append(item);
    }
    target.append(list);
  }

  function renderPreviewEvidence(body) {
    renderDataMap($("h3PreviewMap"), "", body.entity_type_counts, []);
    $("h3PreviewSection26").textContent = `Section 26 heuristic: ${joinedLabels(body.section26_categories)} · ต้องประเมินบริบท ไม่ใช่ข้อสรุปทางกฎหมาย`;
    const findings = Array.isArray(body.guard_findings) ? body.guard_findings : [];
    $("h3PreviewGuard").textContent = findings.length
      ? `Guard review signals: ${findings.map(item => `${item.category || item.code || "finding"}${item.severity ? ` (${item.severity})` : ""}`).join(" · ")}`
      : "Guard review signals: ไม่พบตามกฎปัจจุบัน";
  }

  function resetSensitive({ keepInputs = false } = {}) {
    state.generation += 1; state.previewRequest += 1; state.inspectRequest += 1; state.inspectReport = null; state.joinPending = false;
    if (state.claimAbort) state.claimAbort.abort();
    state.claimAbort = null;
    state.preview = null; state.queue = null; state.result = null; state.queuePaused = false; state.anchor = null; setProviderRunning(false);
    hide(sensitivePanels);
    setTaskBusy("text", false); setTaskBusy("pdf", false); $("h3Approve").disabled = false; $("h3Approve").textContent = "Approve and join queue; when admitted, AI Guard will send this exact protected text automatically"; $("h3CancelQueue").hidden = false; $("h3CancelQueue").disabled = false; $("h3ClearRunning").hidden = true;
    $("h3Protected").textContent = ""; $("h3Receipt").textContent = ""; $("h3RawWorking").textContent = ""; $("h3ProviderBound").textContent = ""; $("h3EvidenceFacts").textContent = ""; $("h3ExecutiveCopy").textContent = "ยังไม่มีผลที่ผ่าน gate"; for (const id of ["h3EvidencePii", "h3EvidenceSection26", "h3EvidenceResidual", "h3EvidenceRestoration", "h3EvidenceAttempts", "h3EvidenceDuration"]) $(id).textContent = "—"; clearNode($("h3ResultBody")); clearNode($("h3PreviewMap")); $("h3PreviewSection26").textContent = ""; $("h3PreviewGuard").textContent = ""; $("h3Result").classList.remove("presenter-fallback"); delete $("h3Result").dataset.presenterPrivate;
    clearNode($("h3InspectResult")); clearNode($("h3InspectMap")); const emptyMap = document.createElement("p"); emptyMap.textContent = "ยังไม่มีผล Detect สำหรับข้อความปัจจุบัน"; $("h3InspectMap").append(emptyMap); $("h3DownloadReport").hidden = true;
    if (!keepInputs) { state.source = ""; state.file = null; $("h3Text").value = ""; $("h3InspectText").value = ""; $("h3TextCount").textContent = "0 / 20,000"; $("h3InspectCount").textContent = "0 / 20,000"; $("h3Pdf").value = ""; $("h3PdfMeta").textContent = "ยังไม่เลือกไฟล์ · การเลือกไฟล์จะไม่อัปโหลดเอง"; }
  }

  function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.json !== undefined) { headers.set("content-type", "application/json"); options.body = JSON.stringify(options.json); }
    delete options.json;
    return fetch(path, { credentials: "same-origin", ...options, headers });
  }

  async function bodyOf(response) {
    const type = response.headers.get("content-type") || "";
    if (!type.includes("application/json")) return null;
    try { return await response.json(); } catch { return null; }
  }

  function readAnchor(response, sentAt, receivedAt, { requireExpiry = false } = {}) {
    const server = response.headers.get("X-AIGuard-Server-Time-Ms");
    const expiry = response.headers.get("X-AIGuard-Session-Expires-At-Ms");
    const serviceClass = response.headers.get("X-AIGuard-Service-Class");
    if (!/^\d+$/.test(server || "") || (requireExpiry && !/^\d+$/.test(expiry || "")) || (serviceClass !== null && !/^(standard|priority)$/.test(serviceClass))) return null;
    return { serverAtReceipt: Number(server) + (receivedAt - sentAt), receivedAt, expiresAt: expiry ? Number(expiry) : null, serviceClass };
  }

  function serverNow() { return state.anchor ? state.anchor.serverAtReceipt + (now() - state.anchor.receivedAt) : NaN; }
  function timingValid(minimumSeconds = 0) { return !!state.anchor && Number.isFinite(serverNow()) && (!state.anchor.expiresAt || state.anchor.expiresAt - serverNow() >= minimumSeconds * 1000); }

  function timingUnavailable(afterUpload = false) {
    resetSensitive({ keepInputs: true });
    $("h3RecoveryCopy").textContent = afterUpload
      ? "ตรวจสอบเวลาของเซสชันไม่ได้ AI Guard จึงยังไม่ส่งข้อความที่ป้องกันแล้วไปยัง Pathumma โปรดลองตรวจสอบเซสชันอีกครั้ง PDF นี้ผ่าน organizer proxy และ AI Guard เพื่อ extraction แล้ว แต่ไม่ได้ส่งให้ Pathumma"
      : "ตรวจสอบเวลาของเซสชันไม่ได้ AI Guard จึงยังไม่ส่งข้อความที่ป้องกันแล้วไปยัง Pathumma โปรดลองตรวจสอบเซสชันอีกครั้ง";
    recoveryAction = () => sampleSession({ focusOnFailure: true });
    show($("h3Recovery")); $("h3RecoveryAction").focus(); announce("ต้องตรวจสอบ session อีกครั้งก่อนส่งข้อความที่ปกป้องแล้ว");
  }

  function setAuthority(serviceClass, { focusEntry = false } = {}) {
    state.authority = serviceClass;
    $("h3ClassChip").textContent = serviceClass === "priority" ? "Priority Invite" : "Standard access";
    $("h3AuthorityStatus").textContent = serviceClass === "priority" ? "Priority Invite พร้อมใช้งาน" : "Standard access พร้อมใช้งาน 30 นาที";
    hide($("h3Access")); show($("h3Chooser")); controls.removeAttribute("inert");
    if (requestedDestination) restoreDestination();
    else if (focusEntry) $("h3ChooserTitle").focus();
  }

  function normalizeFragment() { history.replaceState(null, "", location.pathname); }
  function activeWorkBlocksMutation() {
    if (state.providerRunning) { $("h3ClearRunning").focus(); announce("Provider อาจยังทำงานอยู่ ใช้ Clear this page หากต้องการถอดข้อมูลออกจากหน้าจอ"); return true; }
    if (state.queue) { $("h3CancelQueue").focus(); announce("ต้องยืนยัน Cancel queue ก่อนเปลี่ยนงานหรือจบ access"); return true; }
    return false;
  }
  function requestDestination(fragment) {
    const key = String(fragment || "").replace(/^#/, "");
    if (!Object.hasOwn(destinations, key)) return false;
    if (activeWorkBlocksMutation()) { normalizeFragment(); return true; }
    requestedDestination = key;
    if (!state.authority) { normalizeFragment(); $("h3StartStandard").focus(); announce("เข้าสู่ access gate ก่อนเปิดงานที่เลือก"); return true; }
    restoreDestination(); return true;
  }
  function restoreDestination() {
    const key = requestedDestination; if (!key || !state.authority) return;
    const destination = destinations[key]; requestedDestination = null; normalizeFragment(); chooseTask(destination.task);
    if (destination.disclosure) {
      const details = $(destination.disclosure); details.open = true; const summary = details.querySelector("summary"); summary?.focus();
    } else if (destination.focus) $(destination.focus)?.focus();
    announce(destination.afterResult ? "เปิด Protect text for AI แล้ว หลักฐาน provider จะแสดงหลังผลที่ผ่าน gate" : "เปิดงานที่เลือกแล้ว");
  }

  async function sampleSession({ focusOnFailure = false, recoverQueue = false } = {}) {
    const generation = state.generation, sentAt = now(), hadAuthority = !!state.authority;
    let response;
    try { response = await api("/api/auth/session"); } catch { if (focusOnFailure) timingUnavailable(); return false; }
    const receivedAt = now(), body = await bodyOf(response);
    if (!isCurrent(generation)) return false;
    if (response.status === 401) { resetSensitive({ keepInputs: false }); state.authority = null; state.task = null; hide($("h3Chooser"), ...Object.values(taskPanels)); show($("h3Access")); $("h3AuthorityStatus").textContent = hadAuthority ? "Session สิ้นสุดแล้วและล้างข้อมูลในหน้านี้แล้ว" : "ยังไม่ได้เริ่ม access · เลือก Standard access หรือ Priority Invite"; unlockControls(); if (focusOnFailure || requestedDestination) $("h3StartStandard").focus(); return false; }
    const anchor = readAnchor(response, sentAt, receivedAt, { requireExpiry: true });
    if (!response.ok || !anchor || !anchor.serviceClass || !body || body.authenticated !== true) { if (focusOnFailure) timingUnavailable(); return false; }
    state.anchor = anchor; setAuthority(anchor.serviceClass, { focusEntry: !hadAuthority }); unlockControls();
    if (recoverQueue) await recoverQueueStatus();
    return true;
  }

  async function recoverQueueStatus() {
    try {
      const response = await api("/api/provider-queue/status"); const body = await bodyOf(response);
      if (!response.ok || !body || !["queued", "paused", "claim_ready", "running"].includes(body.state)) return;
      state.queue = {statusOnly: true, revision: Number.isInteger(body.revision) ? body.revision : 0}; setProviderRunning(body.state === "running"); show($("h3Queue")); syncActionLocks();
      $("h3QueueFacts").textContent = `สถานะคิวที่กู้คืนได้: ${body.state}. ข้อมูลส่วนตัว, approval และ execute authority ไม่ถูกเก็บในเบราว์เซอร์; ต้องสร้าง preview ใหม่ก่อนดำเนินการต่อ`;
      $("h3CancelQueue").hidden = body.state === "running"; $("h3ClearRunning").hidden = body.state !== "running";
    } catch { /* recovery remains optional and read-only */ }
  }

  async function reconcileAmbiguousAuthority(expectedClass) {
    const sentAt = now();
    try {
      const response = await api("/api/auth/session"), receivedAt = now(), body = await bodyOf(response);
      if (response.status === 401) { resetSensitive({ keepInputs: false }); state.authority = null; hide($("h3Chooser"), ...Object.values(taskPanels)); show($("h3Access")); return "signed_out"; }
      const anchor = readAnchor(response, sentAt, receivedAt, {requireExpiry: true});
      if (response.ok && body?.authenticated === true && anchor?.serviceClass === expectedClass) { state.anchor = anchor; setAuthority(expectedClass, { focusEntry: true }); unlockControls(); return "authenticated"; }
    } catch { /* unresolved below */ }
    $("h3RecoveryCopy").textContent = "ยืนยันผลการเริ่ม access กับ server ไม่ได้ session อาจถูกสร้างแล้ว ห้ามเริ่ม access อีกแบบจนตรวจ session สำเร็จ";
    $("h3RecoveryAction").textContent = "Retry session check";
    recoveryAction = async () => {
      const result = await reconcileAmbiguousAuthority(expectedClass);
      if (result !== "unknown") { hide($("h3Recovery")); setAuthorityBusy(false); result === "signed_out" ? $("h3StartStandard").focus() : $("h3EndAuthority").focus(); }
      else $("h3RecoveryAction").focus();
    };
    show($("h3Recovery")); $("h3RecoveryAction").focus(); announce("ต้องตรวจสอบ session ก่อนเริ่ม access อีกครั้ง");
    return "unknown";
  }

  async function startStandard() {
    if (state.authorityMutation) return;
    setAuthorityBusy(true);
    resetSensitive({ keepInputs: false }); const sentAt = now();
    let holdForReconciliation = false;
    try {
      const response = await api("/api/auth/guest", { method: "POST", json: {} }), receivedAt = now(), body = await bodyOf(response);
      const anchor = readAnchor(response, sentAt, receivedAt, { requireExpiry: true });
      if (!response.ok) { $("h3AuthorityStatus").textContent = errorCopy[errorCode(body)] || "เริ่ม Standard access ไม่สำเร็จ"; return; }
      if (!body || !anchor || anchor.serviceClass !== "standard") throw new Error("ambiguous");
      state.anchor = anchor; setAuthority("standard", { focusEntry: true }); announce("Standard access started");
    } catch { const result = await reconcileAmbiguousAuthority("standard"); holdForReconciliation = result === "unknown"; if (result === "signed_out") $("h3AuthorityStatus").textContent = "เริ่ม Standard access ไม่สำเร็จและไม่พบ session ที่ใช้งานอยู่"; }
    finally { if (!holdForReconciliation) setAuthorityBusy(false); }
  }

  async function priorityLogin(event) {
    event.preventDefault(); if (state.authorityMutation) return; setAuthorityBusy(true); resetSensitive({ keepInputs: false }); const code = $("h3Invite").value;
    if (!code) { $("h3AuthorityStatus").textContent = "กรอก Priority Invite ที่ออกให้ก่อน"; $("h3Invite").focus(); setAuthorityBusy(false); return; }
    let holdForReconciliation = false;
    try {
      const response = await api("/api/auth/login", { method: "POST", json: { access_code: code } }); const body = await bodyOf(response); $("h3Invite").value = "";
      if (!response.ok) { $("h3AuthorityStatus").textContent = errorCopy[errorCode(body)] || "Priority Invite ใช้ไม่ได้"; return; }
      const result = await reconcileAmbiguousAuthority("priority"); holdForReconciliation = result === "unknown";
      if (result === "authenticated") announce("Priority Invite started");
      else if (result === "signed_out") $("h3AuthorityStatus").textContent = "Priority Invite ไม่ได้สร้าง session";
    } catch { $("h3Invite").value = ""; const result = await reconcileAmbiguousAuthority("priority"); holdForReconciliation = result === "unknown"; if (result === "signed_out") $("h3AuthorityStatus").textContent = "Priority Invite ไม่ได้สร้าง session"; }
    finally { if (!holdForReconciliation) setAuthorityBusy(false); }
  }

  async function endAuthority() {
    if (state.authorityMutation) return;
    if (activeWorkBlocksMutation()) return;
    setAuthorityBusy(true);
    const previousAuthority = state.authority;
    resetSensitive({ keepInputs: false });
    const path = previousAuthority === "standard" ? "/api/auth/guest/end" : "/api/auth/logout";
    let confirmed = false;
    try { const response = await api(path, { method: "POST", json: previousAuthority === "standard" ? {} : undefined }); confirmed = response.status === 204; } catch { /* verify the surviving authority below */ }
    if (!confirmed) {
      await sampleSession({ focusOnFailure: false, recoverQueue: true });
      if (state.authority) {
        hide($("h3Access"), ...Object.values(taskPanels)); show($("h3Chooser"));
        $("h3AuthorityStatus").textContent = "ยืนยันการสิ้นสุด access กับ server ไม่ได้ ข้อมูลในหน้านี้ถูกล้างแล้ว แต่ session เดิมอาจยังใช้งานอยู่ กรุณาลอง End access อีกครั้ง";
        setAuthorityBusy(false); $("h3EndAuthority").focus(); announce("ยังยืนยันการสิ้นสุด access ไม่ได้ session เดิมอาจยังอยู่"); return;
      }
      confirmed = true;
    }
    state.authority = null; hide($("h3Chooser"), ...Object.values(taskPanels)); show($("h3Access")); $("h3AuthorityStatus").textContent = "สิ้นสุด access และล้างข้อมูลในหน้านี้แล้ว"; setAuthorityBusy(false); $("h3StartStandard").focus();
  }

  function chooseTask(task) {
    if (activeWorkBlocksMutation()) return;
    resetSensitive({ keepInputs: false }); state.task = task; hide(...Object.values(taskPanels)); show(taskPanels[task]);
    const heading = taskPanels[task].querySelector("h2"); heading.setAttribute("tabindex", "-1"); heading.focus({ preventScroll: true }); taskPanels[task].scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function freshTiming(minimumSeconds, afterUpload = false) {
    const ok = await sampleSession({ focusOnFailure: true });
    if (!ok) return false;
    if (!timingValid(minimumSeconds)) { timingUnavailable(afterUpload); return false; }
    return true;
  }

  function showError(code, retryTarget) {
    if (["provider_timeout", "provider_already_running"].includes(code)) { showUnresolvedProvider(); return; }
    if (code === "authentication_required") {
      resetSensitive({ keepInputs: false }); state.authority = null; state.task = null; hide($("h3Chooser"), ...Object.values(taskPanels)); show($("h3Access"));
      $("h3AuthorityStatus").textContent = errorCopy.authentication_required; $("h3StartStandard").focus(); announce(errorCopy.authentication_required); return;
    }
    const preservePreview = ["queue_full", "queue_rate_limited", "approval_registry_full"].includes(code) && !!state.preview;
    if (preservePreview) { hide($("h3Queue"), $("h3Result")); state.queue = null; setProviderRunning(false); $("h3Approve").disabled = false; }
    else resetSensitive({ keepInputs: true });
    const copy = errorCopy[code] || "ไม่สามารถดำเนินการได้อย่างปลอดภัย โปรดลองอีกครั้ง";
    const needsNewPreview = ["provider_response_invalid", "restoration_incomplete", "restoration_unsafe"].includes(code);
    $("h3RecoveryCopy").textContent = copy; $("h3RecoveryAction").textContent = code === "session_review_window" ? (state.authority === "standard" ? "Restart Standard access" : "Use Priority Invite again") : preservePreview ? "Retry queue" : needsNewPreview ? "สร้าง Preview ใหม่" : "Retry"; recoveryAction = () => { hide($("h3Recovery")); if (code === "session_review_window") endAuthority(); else (retryTarget || (state.task === "pdf" ? $("h3PdfPreview") : $("h3TextPreview")))?.focus(); };
    show($("h3Recovery")); $("h3Recovery").focus(); announce(copy);
  }

  function displayPreview(body, source) {
    if (!body || typeof body.protected_text !== "string" || body.can_execute !== true || typeof body.ticket !== "string") { showError("request_failed"); return; }
    state.preview = body; state.source = source; $("h3Protected").textContent = body.protected_text;
    $("h3Gate").textContent = `Outbound gate: ${body.outbound_gate?.status || "unknown"} · human review required`;
    const deadline = Number(body.queue_join_before_unix); const minimum = state.task === "pdf" ? 300 : 120;
    if (!Number.isFinite(deadline) || deadline * 1000 - serverNow() < minimum * 1000) return timingUnavailable(state.task === "pdf");
    $("h3PreviewMeta").textContent = `เข้าคิวก่อน ${new Date(deadline * 1000).toLocaleString()} (เวลาจาก server)`;
    const omitted = Array.isArray(body.omitted_visual_page_numbers) && body.omitted_visual_page_numbers.length ? ` หน้า visual ที่ละไว้: ${body.omitted_visual_page_numbers.join(", ")}` : "";
    $("h3PreviewWarning").textContent = `AI Guard แทนที่เฉพาะ PII ที่ตรวจพบ ข้อมูลที่ไม่พบอาจยังอยู่ ต้องตรวจทานโดยมนุษย์${omitted}`;
    renderPreviewEvidence(body);
    hide($("h3Recovery")); show($("h3Preview"));
    $("h3PreviewTitle").setAttribute("tabindex", "-1"); $("h3PreviewTitle").focus();
    announce("Preview protected text พร้อมตรวจทานแล้ว");
  }

  async function previewText() {
    if ($("h3TextPreview").disabled) return;
    const text = $("h3Text").value;
    if (!text) { $("h3Text").focus(); return; }
    if (!await freshTiming(1030)) return;
    const generation = state.generation, request = ++state.previewRequest, mode = document.querySelector("input[name=h3Mode]:checked").value;
    setTaskBusy("text", true); announce("กำลังสร้าง protected preview โดยยังไม่เรียก provider");
    const sentAt = now();
    try { const response = await api("/api/protection-preview", { method: "POST", json: { text, mode } }); const receivedAt = now(), body = await bodyOf(response); if (!isCurrent(generation) || request !== state.previewRequest) return; if (!response.ok) return showError(errorCode(body), $("h3TextPreview")); const anchor = readAnchor(response, sentAt, receivedAt, { requireExpiry: true }); if (!anchor) return timingUnavailable(); state.anchor = anchor; displayPreview(body, text); }
    catch { if (isCurrent(generation)) showError("network", $("h3TextPreview")); }
    finally { if (isCurrent(generation) && request === state.previewRequest) setTaskBusy("text", false); }
  }

  async function previewPdf() {
    if ($("h3PdfPreview").disabled) return;
    const file = state.file;
    if (!file) { $("h3Pdf").focus(); return; }
    if (file.type !== "application/pdf") { showError("document_unsupported", $("h3Pdf")); return; }
    if (!await freshTiming(1230)) return;
    const generation = state.generation, request = ++state.previewRequest, sentAt = now(); setTaskBusy("pdf", true); announce("กำลังอัปโหลดและแยก text layer ใน AI Guard; ยังไม่มีการเรียก provider");
    try { const response = await api("/api/document-preview", { method: "POST", headers: { "content-type": "application/pdf" }, body: file }); const receivedAt = now(), body = await bodyOf(response); if (!isCurrent(generation) || request !== state.previewRequest) return; if (!response.ok) return showError(errorCode(body), $("h3PdfPreview")); const anchor = readAnchor(response, sentAt, receivedAt, { requireExpiry: true }); if (!anchor) return timingUnavailable(true); state.anchor = anchor; displayPreview(body, ""); }
    catch { if (isCurrent(generation)) showError("network", $("h3PdfPreview")); }
    finally { if (isCurrent(generation) && request === state.previewRequest) setTaskBusy("pdf", false); }
  }

  async function approveQueue() {
    if (state.joinPending || $("h3Approve").disabled) return;
    const minimum = state.task === "pdf" ? 300 : 120;
    const deadline = Number(state.preview?.queue_join_before_unix);
    if (!state.preview || !timingValid(minimum) || !Number.isFinite(deadline) || deadline * 1000 - serverNow() < minimum * 1000) return timingUnavailable(state.task === "pdf");
    const generation = state.generation; state.joinPending = true; $("h3Approve").disabled = true; $("h3Approve").textContent = "Approving and joining queue…";
    try { const response = await api("/api/provider-queue/join", { method: "POST", json: { ticket: state.preview.ticket } }); const body = await bodyOf(response); if (!isCurrent(generation)) return; if (!response.ok || typeof body?.queue_capability !== "string") return showError(errorCode(body), $("h3Approve")); state.queue = { capability: body.queue_capability, revision: 0, expires: body.queue_expires_at_unix }; syncActionLocks(); state.queueStartedAt = now(); $("h3Approve").disabled = true; show($("h3Queue")); renderQueue(body); $("h3Queue").focus(); announce("เข้าคิวแล้ว; protected payload ที่อนุมัติยังแสดงอยู่ด้านบน"); claimLoop(generation); }
    catch { if (isCurrent(generation)) showError("network", $("h3Approve")); }
    finally { if (isCurrent(generation)) { state.joinPending = false; $("h3Approve").textContent = state.queue ? "Approved · automatic execution pending" : "Approve and join queue; when admitted, AI Guard will send this exact protected text automatically"; if (!state.queue && state.preview) $("h3Approve").disabled = false; } }
  }

  function renderQueue(queue) {
    const position = queue.position == null ? "กำลังตรวจสถานะ" : `ตำแหน่งโดยประมาณ ${queue.position}`;
    const elapsed = Math.floor((now() - state.queueStartedAt) / 1000); const deadline = queue.queue_expires_at_unix ? new Date(queue.queue_expires_at_unix * 1000).toLocaleString() : "unknown";
    $("h3QueueFacts").textContent = `${state.authority === "priority" ? "Priority Invite" : "Standard access"} · ${position} · รอแล้ว ${elapsed}s · deadline ${deadline}`;
  }

  async function claimLoop(generation) {
    if (!state.queue || state.queue.statusOnly || typeof state.queue.capability !== "string") return;
    if (state.claimInFlight) return;
    state.claimInFlight = true;
    try {
    while (isCurrent(generation) && state.queue && !state.providerRunning && document.visibilityState === "visible" && navigator.onLine) {
      const controller = new AbortController(); state.claimAbort = controller;
      try {
        const response = await api("/api/provider-queue/claim", { method: "POST", json: { queue_capability: state.queue.capability, last_revision: state.queue.revision }, signal: controller.signal }); const body = await bodyOf(response);
        if (!isCurrent(generation) || !state.queue) return;
        if (!response.ok) { if (errorCode(body) === "queue_already_active") return; return showError(errorCode(body), $("h3CancelQueue")); }
        state.queue.revision = Number.isInteger(body.revision) ? body.revision : state.queue.revision; renderQueue(body);
        if (body.reason === "claim_missed_requeued") { $("h3QueueFacts").textContent += " · พลาด claim ครั้งแรก: ย้ายไปท้ายคิวโดยไม่ส่งให้ provider"; announce("Automatic start ไม่สำเร็จครั้งแรก จึงย้ายคำขอไปท้ายคิว"); }
        if (body.state === "claim_ready" && typeof body.claim_token === "string") { announce("สิทธิ์พร้อมแล้ว AI Guard กำลังส่ง protected payload อัตโนมัติ"); return executeClaim(body.claim_token, generation); }
        if (["expired", "failed", "cancelled"].includes(body.state)) return showError(body.reason === "claim_missed_expired" ? "claim_missed_expired" : body.reason || "queue_expired", $("h3CancelQueue"));
      } catch (error) { if (error.name === "AbortError") { if (isCurrent(generation) && document.visibilityState !== "visible") { state.queuePaused = true; $("h3QueueFacts").textContent = "Paused · eligibility ถูกพัก และไม่มีการส่งซ้ำ; กลับมาที่แท็บนี้เพื่ออ่านสถานะแบบปลอดภัย"; announce("คิวถูกพักเพราะหน้านี้ไม่อยู่เบื้องหน้า"); } return; } if (isCurrent(generation)) { $("h3QueueFacts").textContent = "สถานะคิวไม่ทราบ และไม่มีการส่งซ้ำ; เมื่อกลับมาออนไลน์ AI Guard จะอ่านสถานะเท่านั้น"; announce("สถานะคิวไม่ทราบ ยังไม่มีการส่งซ้ำ"); return; } }
    }
    if (isCurrent(generation) && state.queue && document.visibilityState !== "visible") { state.queuePaused = true; $("h3QueueFacts").textContent = "Paused · eligibility ถูกพัก และไม่มีการส่งซ้ำ; กลับมาที่แท็บนี้เพื่อ resume eligibility"; announce("คิวถูกพักเพราะหน้านี้ไม่อยู่เบื้องหน้า"); }
    else if (isCurrent(generation) && state.queue && !navigator.onLine) { state.queuePaused = true; $("h3QueueFacts").textContent = "Offline · สถานะคิวไม่ทราบ ไม่มีการส่งซ้ำ และ deadline ยังคงเดิน; กลับมาออนไลน์เพื่ออ่านสถานะและ resume eligibility"; announce("ออฟไลน์อยู่ สถานะคิวไม่ทราบและไม่มีการส่งซ้ำ"); }
    } finally { state.claimInFlight = false; state.claimAbort = null; }
  }

  async function executeClaim(claimToken, generation) {
    if (!state.queue || !state.preview) return;
    setProviderRunning(true); $("h3CancelQueue").hidden = true; $("h3ClearRunning").hidden = false; $("h3QueueFacts").textContent = "Provider กำลังทำงาน การล้างหน้านี้ไม่สามารถรับประกันการยกเลิก upstream ได้";
    const path = state.task === "pdf" ? "/api/document-execute" : "/api/protection-execute";
    const json = state.task === "pdf" ? { protected_text: state.preview.protected_text, queue_capability: state.queue.capability, claim_token: claimToken } : { text: state.source, queue_capability: state.queue.capability, claim_token: claimToken };
    try { const response = await api(path, { method: "POST", json }); const body = await bodyOf(response); if (!isCurrent(generation)) return; if (!response.ok) return showError(errorCode(body), null); renderResult(body); }
    catch { if (isCurrent(generation)) showUnresolvedProvider(); }
  }

  function showUnresolvedProvider() {
    setProviderRunning(true); hide($("h3Recovery")); show($("h3Queue")); $("h3CancelQueue").hidden = true; $("h3ClearRunning").hidden = false;
    $("h3QueueFacts").textContent = "สถานะ provider ยังไม่แน่ชัดเพราะการเชื่อมต่อขาดหลัง automatic execute คำขออาจยังทำงานอยู่ upstream ห้าม preview, join หรือส่งซ้ำจากหน้านี้";
    $("h3Queue").focus(); announce("สถานะ provider ยังไม่แน่ชัด คำขออาจยังทำงานอยู่และห้ามส่งซ้ำ");
  }

  async function cancelQueue() {
    if (!state.queue || state.providerRunning || !confirm("ยกเลิกคิวและสร้าง preview/upload ใหม่?")) return;
    const statusOnly = state.queue.statusOnly === true, activeTask = state.task;
    $("h3CancelQueue").disabled = true;
    let confirmed = false;
    try { const response = await api("/api/provider-queue/cancel", { method: "POST", json: {} }); confirmed = response.status === 204; } catch { /* status check below */ }
    if (!confirmed) {
      try {
        const response = await api("/api/provider-queue/status"), body = await bodyOf(response);
        if (response.ok && ["absent", "cancelled", "expired", "failed", "complete"].includes(body?.state)) confirmed = true;
        else if (response.ok && body) { renderQueue(body); $("h3QueueFacts").textContent += " · ยืนยันการยกเลิกไม่ได้ คิวยังอาจทำงานอยู่ ไม่มีการสร้างคำขอใหม่"; }
      } catch { $("h3QueueFacts").textContent = "ยืนยันการยกเลิกไม่ได้เพราะการเชื่อมต่อขาด คิวยังอาจอยู่ ห้ามสร้าง preview หรือ join ใหม่จนตรวจสถานะได้"; }
    }
    if (confirmed) {
      resetSensitive({ keepInputs: false });
      if (statusOnly || !activeTask || !taskPanels[activeTask] || taskPanels[activeTask].hidden) { hide(...Object.values(taskPanels)); show($("h3Chooser")); $("h3ChooserTitle").setAttribute("tabindex", "-1"); $("h3ChooserTitle").focus(); }
      else (activeTask === "pdf" ? $("h3PdfPreview") : $("h3TextPreview")).focus();
      announce("ยกเลิกคิวแล้ว ต้องสร้าง preview ใหม่");
    }
    else { $("h3CancelQueue").disabled = false; $("h3CancelQueue").focus(); announce("ยังยืนยันการยกเลิกคิวไม่ได้"); }
  }

  function provenanceHeader(receipt, isPdf) {
    const omitted = Array.isArray(receipt?.omitted_visual_page_numbers) && receipt.omitted_visual_page_numbers.length ? ` Omitted visual page(s): ${receipt.omitted_visual_page_numbers.join(", ")}.` : "";
    return isPdf
      ? ["AI Guard protected/pseudonymized artifact; it is not anonymous.", "The source PDF is unchanged and is not sanitized. PII was not restored into this artifact.", `Text-layer-only extraction; parser ${receipt?.parser_revision || "unavailable"}; extraction ${receipt?.extraction_revision || "unavailable"}.${omitted}`, "Human review is required.", `Hosted channel: AI Guard 3.0.1 · receipt: ${receipt?.source_receipt_id || "unavailable"}`].join("\n")
      : ["AI Guard protected/pseudonymized text artifact; it is not anonymous.", "This portable protected text does not include restored PII. Human review is required.", `Hosted channel: AI Guard 3.0.1 · receipt: ${receipt?.request_id || "unavailable"}`].join("\n");
  }
  function portableReceipt(body, isPdf) {
    const envelope = {
      schema: "aiguard-portable-receipt-v1",
      artifact_kind: isPdf ? "protected_markdown" : "protected_text",
      classification: "protected/pseudonymized, not anonymous",
      restored_text_included: false,
      human_review_required: true,
      warnings: isPdf ? [...body.warnings] : ["Only PII detected by AI Guard was replaced; undetected PII may remain."],
      receipt: {...body.receipt},
    };
    if (isPdf) Object.assign(envelope, {
      source_pdf_unchanged: true, source_pdf_sanitized: false, pii_restored: false,
      text_layer_only: true, ocr_or_visual_layout_interpreted: false,
      omitted_visual_page_numbers: [...body.omitted_visual_page_numbers],
    });
    return envelope;
  }
  function customResultStatus(body, expectedProtected) {
    if (!isPlainObject(body) || typeof body.protected_text !== "string" || body.protected_text !== expectedProtected || typeof body.restored_text !== "string") return null;
    if (!isPlainObject(body.safety) || body.safety.status !== "pass" || body.safety.residual_count !== 0 || !isPlainObject(body.restoration)) return null;
    const status = body.restoration.status, leftover = body.restoration.leftover_count, warnings = body.warnings;
    if (!Number.isInteger(leftover) || leftover < 0 || !Array.isArray(warnings)) return null;
    const warningsValid = warnings.every(warning => isPlainObject(warning)
      && Object.keys(warning).length === 2
      && Object.hasOwn(warning, "code")
      && Object.hasOwn(warning, "count")
      && ["foreign_replacement", "generated_pii"].includes(warning.code)
      && Number.isInteger(warning.count)
      && warning.count > 0);
    if (!warningsValid) return null;
    if (status === "complete" ? leftover !== 0 || warnings.length || !body.restored_text : status === "incomplete" ? leftover <= 0 || warnings.length || body.restored_text !== "" : status === "unsafe" ? !warnings.length || body.restored_text !== "" : true) return null;
    const provider = body.provider, receipt = body.receipt, requestId = body.request_id;
    if (!isPlainObject(provider) || !isPlainObject(receipt) || typeof requestId !== "string" || !requestId) return null;
    if (provider.id !== "tokenmind" || provider.model !== "thaillm-8b" || !Number.isInteger(provider.attempt_count) || provider.attempt_count < 1 || provider.attempt_count > 3) return null;
    if (typeof body.hosted_version !== "string" || !body.hosted_version || body.source_kind !== "custom_standard") return null;
    if (receipt.request_id !== requestId || receipt.hosted_version !== body.hosted_version || receipt.source_kind !== body.source_kind || receipt.restoration_status !== status || receipt.digest_match !== true || receipt.outbound_gate_status !== "no_residual_signal_detected") return null;
    if (receipt.provider_id !== provider.id || receipt.provider_model !== provider.model || !Number.isInteger(receipt.provider_attempt_count) || receipt.provider_attempt_count !== provider.attempt_count) return null;
    return status;
  }
  function validPdfResult(body) {
    return isPlainObject(body)
      && typeof body.protected_markdown === "string"
      && typeof body.protected_plain_text === "string"
      && typeof body.protected_text === "string"
      && isPlainObject(body.receipt)
      && isPlainObject(body.protected_document_ast)
      && Array.isArray(body.protected_document_ast.ordered_sections)
      && Array.isArray(body.warnings)
      && Array.isArray(body.omitted_visual_page_numbers)
      && !Object.hasOwn(body, "restored_text");
  }
  function decodeMarkdownText(value) { return value.replace(/\\([\\`*_{}\[\]()#+\-.!>])/g, "$1"); }
  function renderProtectedMarkdown(target, markdown) {
    const lines = markdown.split("\n");
    if (!lines.length || lines.length > 512 || markdown.includes("\0") || markdown.includes("\r")) return false;
    let rendered = 0;
    for (const line of lines) {
      if (!line) continue;
      if (/^\s*(?:```|~~~|<|!\[|\[[^\]]*\]\(|\|)/.test(line)) return false;
      if (line.startsWith("> ")) continue;
      let tag = "p", text = line;
      if (line.startsWith("## ")) { tag = "h3"; text = line.slice(3); }
      else if (line.startsWith("# ")) { tag = "h2"; text = line.slice(2); }
      if (!text.trim()) return false;
      const node = document.createElement(tag); node.textContent = decodeMarkdownText(text);
      target.append(node); rendered += 1;
    }
    return rendered > 0;
  }
  function renderResult(body) {
    const isPdf = state.task === "pdf";
    if (isPdf && !validPdfResult(body)) return showError("provider_response_invalid", null);
    if (!isPdf) {
      const status = customResultStatus(body, state.preview?.protected_text);
      if (status === null) return showError("provider_response_invalid", null);
      if (status === "incomplete") return showError("restoration_incomplete", null);
      if (status === "unsafe") return showError("restoration_unsafe", null);
    }
    state.queue = null; setProviderRunning(false); hide($("h3Queue")); clearNode($("h3ResultBody")); const bodyNode = $("h3ResultBody");
    const result = isPdf ? body.protected_markdown : body.restored_text;
    $("h3ResultTitle").textContent = isPdf ? "Protected Markdown" : "Restored provider result";
    $("h3TextComparison").hidden = isPdf; $("h3TextEvidence").hidden = isPdf; $("h3ProtectedExtraction").hidden = !isPdf; $("h3TechnicalReceipt").hidden = false;
    const paragraph = document.createElement("p");
    paragraph.textContent = isPdf
      ? `Protected Markdown ผ่าน structured segment validation แล้ว PDF ต้นฉบับไม่เปลี่ยน ไม่มี PII restoration และต้องตรวจทานโดยมนุษย์${body.omitted_visual_page_numbers.length ? ` · visual content ที่ละไว้หน้า ${body.omitted_visual_page_numbers.join(", ")}` : ""}`
      : "ผล provider ผ่าน integrity, residual และ restoration gates แล้ว";
    paragraph.className = "hosted3-result-status"; bodyNode.append(paragraph);
    if (isPdf) {
      if (!renderProtectedMarkdown(bodyNode, result)) return showError("document_structure_invalid", null);
    } else {
      const output = document.createElement("pre"); output.textContent = result; bodyNode.append(output);
    }
    const portable = isPdf ? body.protected_markdown : body.protected_text;
    const artifact = `${provenanceHeader(body.receipt, isPdf)}\n\n${portable}`;
    const receiptEnvelope = portableReceipt(body, isPdf);
    $("h3ResultProtected").textContent = artifact;
    $("h3Receipt").textContent = JSON.stringify(receiptEnvelope, null, 2);
    $("h3RawWorking").textContent = isPdf ? "PDF source is not rendered or exported; review protected extraction only." : state.source;
    $("h3ProviderBound").textContent = state.preview?.protected_text || body.protected_text;
    $("h3EvidenceFacts").textContent = `Provider-bound payload reviewed before queue · mode ${isPdf ? "document protected Markdown" : document.querySelector("input[name=h3Mode]:checked")?.value || "unknown"} · receipt ${body.receipt.request_id || body.receipt.source_receipt_id || "unavailable"}`;
    if (!isPdf) {
      const detected = Number.isInteger(body.detected_entity_count) ? body.detected_entity_count : Object.values(body.entity_type_counts || {}).reduce((sum, count) => sum + (Number.isInteger(count) ? count : 0), 0);
      const typeCount = isPlainObject(body.entity_type_counts) ? Object.keys(body.entity_type_counts).length : 0;
      const attempts = body.provider?.attempt_count ?? body.receipt.provider_attempt_count;
      const duration = body.receipt.duration_ms;
      $("h3ExecutiveCopy").textContent = `AI Guard ตรวจพบ ${detected} รายการใน ${typeCount} ประเภท ส่งเฉพาะ protected payload ที่อนุมัติ และแสดงผลที่กู้คืนหลัง residual และ restoration gates ผ่านครบ`;
      $("h3EvidencePii").textContent = `${detected} รายการ · ${typeCount} ประเภท`;
      $("h3EvidenceSection26").textContent = joinedLabels(body.section26_categories);
      $("h3EvidenceResidual").textContent = `${body.safety.residual_count} สัญญาณ · ${body.safety.status}`;
      $("h3EvidenceRestoration").textContent = `${body.restoration.status} · leftover ${body.restoration.leftover_count}`;
      $("h3EvidenceAttempts").textContent = Number.isInteger(attempts) ? String(attempts) : "ไม่ระบุ";
      $("h3EvidenceDuration").textContent = finiteNonnegative(duration) ? `${duration} ms` : "ไม่ระบุ";
    }
    state.result = { artifact, receipt: receiptEnvelope, text: portable, isPdf };
    $("h3Result").dataset.presenterPrivate = !isPdf && state.source ? "true" : "false";
    show($("h3Result")); $("h3ResultTitle").setAttribute("tabindex", "-1"); $("h3ResultTitle").focus(); announce("ผลลัพธ์พร้อมตรวจทาน");
  }

  function download(name, type, text) { const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([text], { type })); link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 0); }
  function invalidateWork() { resetSensitive({ keepInputs: true }); state.source = ""; }
  function appendFact(target, label, value) { const line = document.createElement("p"); const strong = document.createElement("strong"); strong.textContent = `${label}: `; line.append(strong, document.createTextNode(String(value))); target.append(line); }
  function decodeB64(value) { const binary = atob(value); const bytes = new Uint8Array(binary.length); for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i); return bytes; }
  async function inspect(path, target) {
    const text = $("h3InspectText").value; if (!text) return $("h3InspectText").focus();
    const generation = state.generation, request = ++state.inspectRequest; target.textContent = "กำลังตรวจสอบ…"; $("h3DownloadReport").hidden = true;
    try {
      const response = await api(path, { method: "POST", json: { text } }); const body = await bodyOf(response); if (!isCurrent(generation) || request !== state.inspectRequest) return;
      clearNode(target); if (!response.ok || !body) { const code = errorCode(body); if (code === "authentication_required") return showError(code, null); return appendFact(target, "Error", errorCopy[code] || "ไม่สามารถตรวจสอบได้อย่างปลอดภัย"); }
      if (path === "/api/detect") { appendFact(target, "Detected PII", body.detected_entity_count ?? 0); appendFact(target, "Type counts", Object.entries(body.entity_type_counts || {}).map(([type, count]) => `${type} ${count}`).join(", ") || "none"); appendFact(target, "Spans", (body.highlights || []).map(item => `${item.data_type} ${item.start}–${item.end}`).join("; ") || "none"); renderDataMap($("h3InspectMap"), text, body.entity_type_counts, body.highlights); }
      else if (path === "/api/guard") { appendFact(target, "Guard", body.flagged ? "review required" : "no heuristic finding"); appendFact(target, "Findings", (body.guard_findings || []).map(item => item.message || item.code || "finding").join("; ") || "none"); }
      else { appendFact(target, "PDPA score", body.overall_score); appendFact(target, "Grade", body.overall_grade); appendFact(target, "Scope", "Automated review only; Section 26 context is not returned by this minimized report response"); if (typeof body.report_pdf_b64 === "string") { state.inspectReport = body.report_pdf_b64; $("h3DownloadReport").hidden = false; } }
      announce("ผลการตรวจสอบพร้อมแล้ว");
    } catch { if (isCurrent(generation) && request === state.inspectRequest) { clearNode(target); appendFact(target, "Error", "network"); } }
  }

  async function checkServiceLiveness() {
    const target = $("h3ServiceLiveness");
    try {
      const response = await api("/api/health"), body = await bodyOf(response);
      if (response.ok && body?.status === "ok" && typeof body.version === "string") target.textContent = `Service liveness: ok · Core ${body.version} · liveness only, not provider readiness`;
      else target.textContent = "Service liveness: unavailable · ไม่ใช่หลักฐานว่า provider พร้อมหรือไม่พร้อม";
    } catch { target.textContent = "Service liveness: unknown · การตรวจนี้ไม่เรียก provider"; }
  }

  $("h3StartStandard").addEventListener("click", startStandard); $("h3ShowPriority").addEventListener("click", () => { $("h3PriorityForm").hidden = false; $("h3Invite").focus(); }); $("h3PriorityForm").addEventListener("submit", priorityLogin); $("h3EndAuthority").addEventListener("click", endAuthority);
  document.querySelectorAll("[data-h3-task]").forEach(button => button.addEventListener("click", () => { state.returnFocus = button; chooseTask(button.dataset.h3Task); })); document.querySelectorAll(".h3-back").forEach(button => button.addEventListener("click", () => { if (activeWorkBlocksMutation()) return; resetSensitive({ keepInputs: false }); hide(...Object.values(taskPanels)); show($("h3Chooser")); state.returnFocus?.focus(); }));
  document.addEventListener("click", event => { const anchor = event.target.closest("a[href^='#']"); if (anchor && requestDestination(anchor.getAttribute("href"))) event.preventDefault(); });
  window.addEventListener("hashchange", () => requestDestination(location.hash));
  $("h3Text").addEventListener("input", () => { invalidateWork(); $("h3TextCount").textContent = `${[...$("h3Text").value].length.toLocaleString()} / 20,000`; }); $("h3InspectText").addEventListener("input", () => { invalidateWork(); $("h3InspectCount").textContent = `${[...$("h3InspectText").value].length.toLocaleString()} / 20,000`; }); document.querySelectorAll("input[name=h3Mode]").forEach(input => input.addEventListener("change", invalidateWork));
  $("h3Pdf").addEventListener("change", () => { invalidateWork(); state.file = $("h3Pdf").files[0] || null; const f = state.file; $("h3PdfMeta").textContent = f ? `${f.name} · ${f.type || "unknown"} · ${f.size.toLocaleString()} bytes · ยังไม่อัปโหลด` : "ยังไม่เลือกไฟล์ · การเลือกไฟล์จะไม่อัปโหลดเอง"; });
  $("h3TextPreview").addEventListener("click", previewText); $("h3PdfPreview").addEventListener("click", previewPdf); $("h3Approve").addEventListener("click", approveQueue); $("h3DiscardPreview").addEventListener("click", () => { resetSensitive({ keepInputs: false }); $("h3TextPreview").focus(); }); $("h3CancelQueue").addEventListener("click", cancelQueue); $("h3ClearRunning").addEventListener("click", () => { resetSensitive({ keepInputs: false }); $("h3EndAuthority").focus(); announce("ล้างข้อมูลจากหน้านี้แล้ว แต่ไม่สามารถรับประกันการยกเลิก upstream ได้"); });
  $("h3RecoveryAction").addEventListener("click", () => recoveryAction ? recoveryAction() : sampleSession({ focusOnFailure: true })); $("h3Detect").addEventListener("click", () => inspect("/api/detect", $("h3InspectResult"))); $("h3Guard").addEventListener("click", () => inspect("/api/guard", $("h3InspectResult"))); $("h3Report").addEventListener("click", () => inspect("/api/analyze-report", $("h3InspectResult"))); $("h3DownloadReport").addEventListener("click", () => { if (state.inspectReport) download("ai-guard-pdpa-report.pdf", "application/pdf", decodeB64(state.inspectReport)); });
  $("h3Present").addEventListener("click", async () => {
    presenterReturnFocus = $("h3Present");
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (typeof $("h3Result").requestFullscreen === "function") await $("h3Result").requestFullscreen();
      else {
        const active = $("h3Result").classList.toggle("presenter-fallback");
        announce(active ? "Presenter view is using the in-page fallback because Fullscreen is unavailable" : "Presenter view closed");
        if (!active && presenterReturnFocus) { presenterReturnFocus.focus(); presenterReturnFocus = null; }
      }
    } catch { $("h3Result").classList.add("presenter-fallback"); announce("Presenter view is using the in-page fallback because Fullscreen is unavailable"); }
  });
  document.addEventListener("fullscreenchange", () => { if (!document.fullscreenElement && presenterReturnFocus) { presenterReturnFocus.focus(); presenterReturnFocus = null; } });
  document.querySelectorAll("[data-h3-sample]").forEach(button => button.addEventListener("click", () => { $("h3InspectText").value = syntheticSamples[button.dataset.h3Sample] || ""; $("h3InspectText").dispatchEvent(new Event("input", { bubbles: true })); $("h3InspectText").focus(); announce("ใส่ตัวอย่างสังเคราะห์แล้ว ยังไม่มีการส่งคำขอ"); }));
  $("h3CopyArtifact").addEventListener("click", async () => { if (state.result?.artifact) { await navigator.clipboard.writeText(state.result.artifact); announce("คัดลอก protected artifact พร้อม provenance แล้ว"); } }); $("h3DownloadMd").addEventListener("click", () => state.result && download("ai-guard-protected.md", "text/markdown;charset=utf-8", state.result.artifact)); $("h3DownloadTxt").addEventListener("click", () => state.result && download("ai-guard-protected.txt", "text/plain;charset=utf-8", state.result.artifact)); $("h3DownloadReceipt").addEventListener("click", () => state.result && download("ai-guard-receipt.json", "application/json", JSON.stringify(state.result.receipt, null, 2)));
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && state.queue && !state.queue.statusOnly && !state.providerRunning) { const wasPaused = state.queuePaused; state.queuePaused = false; sampleSession({ focusOnFailure: true }).then(ok => { if (!ok) return; if (wasPaused) announce("กลับมาที่แท็บแล้ว กำลัง resume eligibility"); claimLoop(state.generation); }); } else if (state.claimAbort) state.claimAbort.abort(); }); window.addEventListener("online", () => { if (state.queue && !state.queue.statusOnly && !state.providerRunning) sampleSession({ focusOnFailure: true }).then(ok => ok && claimLoop(state.generation)); }); window.addEventListener("pageshow", event => { if (event.persisted) { resetSensitive({ keepInputs: false }); sampleSession({ focusOnFailure: true, recoverQueue: true }); } }); window.addEventListener("beforeunload", event => { if (state.claimAbort) state.claimAbort.abort(); if (state.preview || state.queue || state.providerRunning || $("h3Text").value || state.file) { event.preventDefault(); event.returnValue = "Leaving clears this page. Provider work that was already sent may still continue."; } });
  if (location.hash) requestDestination(location.hash);
  checkServiceLiveness(); sampleSession({ recoverQueue: true });
})();
