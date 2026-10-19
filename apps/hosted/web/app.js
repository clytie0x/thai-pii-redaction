"use strict";

/* ── shared: colors, labels, escaping ── */
const COLORS = {
  NAME: "var(--c-name)", THAI_ID: "var(--c-id)", PHONE: "var(--c-phone)",
  EMAIL: "var(--c-email)", ADDRESS: "var(--c-addr)", LOCATION: "var(--c-addr)",
  DATE: "var(--c-date)", DATE_OF_BIRTH: "var(--c-date)", ORGANIZATION: "var(--c-org)",
};
const SAFE_AI_DEMO_TEXT = "ใบสมัครงานสังเคราะห์: นางสาวอรุณี ตัวอย่าง สมัครตำแหน่งนักวิเคราะห์ ติดต่อ 081-000-1020 หรือ arunee@example.invalid ที่อยู่ 88/8 ถนนตัวอย่าง เขตบางรัก กรุงเทพมหานคร กรุณาสรุปผู้สมัคร 2 ประโยค โดยระบุชื่อ ตำแหน่ง เบอร์โทรศัพท์ และอีเมล";
const SCENARIO_LABELS = Object.freeze({
  hr: "สมัครงาน / HR · ข้อมูลสังเคราะห์",
  healthcare: "โรงพยาบาล / Healthcare · ข้อมูลสังเคราะห์",
  education: "โรงเรียน / Education · ข้อมูลสังเคราะห์",
  "customer-service": "บริการลูกค้า / Customer Service · ข้อมูลสังเคราะห์",
  government: "เอกสารราชการ / Government · ข้อมูลสังเคราะห์",
  custom: "ข้อความที่ผู้ใช้กรอกเอง",
});
const MODE_DETAILS = Object.freeze({
  token: {
    label: "Token",
    description: "ใช้ placeholder แบบวงเล็บที่บอกประเภทและสุ่ม namespace ต่อคำขอ ตรวจสอบง่ายโดยไม่เปิดเผยค่าจริง และกู้คืนได้ภายในคำขอเดียว",
  },
  surrogate: {
    label: "Surrogate",
    description: "ใช้ข้อมูลสมมุติที่รักษารูปแบบภาษาให้เป็นธรรมชาติมากขึ้น กู้คืนได้ภายในคำขอเดียว และไม่ได้หมายความว่าปลอดภัยกว่า Token",
  },
});
function normalizeProtectionMode(value) {
  return Object.prototype.hasOwnProperty.call(MODE_DETAILS, value) ? value : "token";
}
function selectedProtectionMode() {
  const select = document.getElementById("mode");
  const mode = normalizeProtectionMode(select.value);
  if (select.value !== mode) select.value = mode;
  return mode;
}
const THAI_LABELS = {
  NAME: "ชื่อบุคคล", THAI_ID: "เลขบัตรประชาชน", PHONE: "เบอร์โทรศัพท์",
  EMAIL: "อีเมล", ADDRESS: "ที่อยู่", LOCATION: "สถานที่", DATE: "วันที่",
  DATE_OF_BIRTH: "วันเกิด", ORGANIZATION: "องค์กร", BANK_ACCOUNT: "เลขบัญชี",
  CREDIT_CARD: "บัตรเครดิต", PASSPORT: "หนังสือเดินทาง", ID_NUMBER: "เลขอ้างอิง",
  STUDENT_ID: "รหัสนักศึกษา", VEHICLE_PLATE: "ทะเบียนรถ", IBAN: "IBAN",
  RACE_ETHNICITY: "เชื้อชาติ/ชาติพันธุ์", POLITICAL_OPINION: "ความคิดเห็นทางการเมือง",
  RELIGION: "ศาสนา", HEALTH: "สุขภาพ", SEXUAL_BEHAVIOR: "พฤติกรรมทางเพศ",
  CRIMINAL_RECORD: "ประวัติอาชญากรรม", DISABILITY: "ความพิการ", LABOR_UNION: "สหภาพแรงงาน",
};
const colorFor = t => COLORS[t] || "var(--c-other)";
const labelFor = t => THAI_LABELS[t] || t;
const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escAttr = s => esc(s).replace(/"/g, "&quot;").replace(/'/g, "&#39;");

function errorMessage(status, detail, kind) {
  if (status === 401) return kind === "auth" ? "รหัสเข้าใช้งานไม่ถูกต้อง กรุณาลองอีกครั้ง" : "เซสชันหมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง";
  if (status === 403) return "ไม่สามารถยืนยันคำขอจากหน้านี้ได้ กรุณาเปิดเว็บไซต์ใหม่แล้วลองอีกครั้ง";
  if (status === 429) return "ระบบกำลังมีผู้ใช้งานหนาแน่น กรุณารอสักครู่แล้วลองใหม่";
  if (status === 413) return "ข้อความยาวเกินขีดจำกัด 20,000 ตัวอักษร";
  const codes = {
    residual_pii: "ยังพบสัญญาณข้อมูลส่วนบุคคลหลังปกปิด ระบบจึงหยุดก่อนเรียกโมเดล",
    provider_configuration: "บริการ LLM ยังไม่พร้อม กรุณาลองใหม่ภายหลัง",
    provider_unavailable: "โมเดลปลายทางไม่พร้อมให้บริการ กรุณาลองใหม่ภายหลัง",
    upstream_unavailable: "แพลตฟอร์มหรือโมเดลปลายทางยังไม่พร้อม กรุณาลองใหม่ภายหลัง",
    upstream_timeout: "โมเดลใช้เวลาตอบนานเกินไป กรุณาลองใหม่อีกครั้ง",
    provider_rejected: "โมเดลปลายทางไม่สามารถรับคำขอนี้ได้",
    provider_response_invalid: "ระบบระงับคำตอบที่ตรวจสอบความปลอดภัยไม่ได้",
    restore_failed: "ระบบระงับผลลัพธ์เนื่องจากกู้คืนบริบทไม่สมบูรณ์",
    ner_unavailable: "ระบบตรวจชื่อยังไม่พร้อม",
    dependency_unavailable: "ส่วนประกอบประมวลผลยังไม่พร้อม",
    service_unavailable: "บริการยังไม่พร้อม ลองใหม่ภายหลัง",
    request_schema_invalid: "ข้อความหรือรูปแบบคำขอไม่ถูกต้อง กรุณาตรวจแล้วลองใหม่",
    invalid_request: "ข้อความหรือรูปแบบคำขอไม่ถูกต้อง กรุณาตรวจแล้วลองใหม่",
    request_too_large: "ข้อความยาวเกินขีดจำกัด 20,000 ตัวอักษร",
    payload_too_large: "ข้อความยาวเกินขีดจำกัด 20,000 ตัวอักษร",
    rate_limited: "ระบบกำลังมีผู้ใช้งานหนาแน่น กรุณารอสักครู่แล้วลองใหม่",
  };
  if (codes[detail]) return codes[detail];
  if (status === 504) return "โมเดลใช้เวลาตอบนานเกินไป กรุณาลองใหม่อีกครั้ง";
  if (status === 502 || status === 503) return "บริการส่วนหนึ่งยังไม่พร้อม กรุณาลองใหม่ภายหลัง";
  if (status === 400 || status === 422) return "ข้อความหรือรูปแบบคำขอไม่ถูกต้อง กรุณาตรวจแล้วลองใหม่";
  if (status === 500) return "บริการไม่สามารถทำคำขอนี้ให้เสร็จได้ ระบบไม่แสดงผลลัพธ์ที่ตรวจสอบไม่ได้";
  return "ไม่สามารถดำเนินการได้ในขณะนี้ กรุณาตรวจข้อมูลแล้วลองใหม่";
}

async function safeJson(r) {
  try { return await r.json(); } catch { return {}; }
}
function detailText(body) {
  if (body && body.error && typeof body.error.code === "string") return body.error.code;
  if (typeof body.detail === "string") return body.detail;
  return "";
}

/* ── same-origin caller authentication ── */
let authenticated = false;
let authGeneration = 0;
let detectGeneration = 0;
let roundtripGeneration = 0;
let reportGeneration = 0;
let guidedGeneration = 0;
let authCheckGeneration = 0;
let authCheckController = null;
let authMutationInFlight = false;
let safeProgressTimer = null;
let preparedReport = null;
let guidedRunning = false;
let selectedScenario = "hr";
let lastDetection = null;
let lastGuard = null;
let lastRoundtrip = null;
let lastReport = null;
let presentationRawText = "";
let presentationRestoredText = "";
let providerLaneActive = false;
let providerLaneReleaseTimer = null;
let sessionExpiryTimer = null;
let sessionExpiresAt = 0;
let fullscreenReturnFocus = null;
const businessControllers = new Set();
const accessCodeInput = document.getElementById("accessCode");
const loginBtn = document.getElementById("loginBtn");
const logoutBtn = document.getElementById("logoutBtn");
const authStatus = document.getElementById("authStatus");
const WORKFLOW_ANCHORS = new Set(["#privacy-scan", "#safe-ai", "#pdpa-report", "#guided-demo", "#providerEvidenceCard"]);
let pendingWorkflowAnchor = typeof location !== "undefined" && WORKFLOW_ANCHORS.has(location.hash)
  ? location.hash
  : "";
let lastAuthRestoredWorkflow = false;

function focusAccessGate() {
  const gate = document.getElementById("authCard");
  if (gate && typeof gate.scrollIntoView === "function") gate.scrollIntoView({block: "start"});
  if (gate && typeof gate.focus === "function") gate.focus({preventScroll: true});
  announce("เวิร์กโฟลว์นี้ต้องใช้รหัสเชิญ โปรดตรวจขอบเขตข้อมูลและเข้าสู่ระบบก่อน");
}

function holdWorkflowUntilAuthenticated(anchor) {
  if (!WORKFLOW_ANCHORS.has(anchor)) return false;
  pendingWorkflowAnchor = anchor;
  if (typeof history !== "undefined" && typeof history.replaceState === "function") {
    history.replaceState(null, "", "/app");
  }
  if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
    window.requestAnimationFrame(focusAccessGate);
  } else {
    focusAccessGate();
  }
  return true;
}

function restoreRequestedWorkflow() {
  if (!pendingWorkflowAnchor) return false;
  const anchor = pendingWorkflowAnchor;
  pendingWorkflowAnchor = "";
  const target = document.getElementById(anchor.slice(1));
  if (typeof history !== "undefined" && typeof history.replaceState === "function") {
    history.replaceState(null, "", `/app${anchor}`);
  }
  if (target) {
    target.setAttribute("tabindex", "-1");
    target.scrollIntoView({block: "start"});
    target.focus({preventScroll: true});
  }
  announce(`เข้าสู่ระบบแล้ว เปิด ${anchor.slice(1)} ตามลิงก์ที่ขอ`);
  return true;
}

document.addEventListener("click", (event) => {
  const link = event.target && event.target.closest ? event.target.closest('a[href^="#"]') : null;
  if (!link || authenticated) return;
  const anchor = link.getAttribute("href");
  if (!WORKFLOW_ANCHORS.has(anchor)) return;
  event.preventDefault();
  holdWorkflowUntilAuthenticated(anchor);
});

if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
  window.addEventListener("hashchange", () => {
    if (!authenticated && WORKFLOW_ANCHORS.has(location.hash)) {
      holdWorkflowUntilAuthenticated(location.hash);
    }
  });
}

class StaleBusinessRequest extends Error {}

function isStaleBusinessError(error) {
  return error instanceof StaleBusinessRequest || (error && error.name === "AbortError");
}

function invalidateBusinessRequests() {
  authGeneration += 1;
  // A browser abort cannot prove that an already-dispatched provider request
  // stopped on the server. Keep that request alive and its single-flight lane
  // locked until the HTTP exchange settles; only local-only requests are aborted.
  for (const record of businessControllers) {
    if (!record.providerBound) {
      record.controller.abort();
      businessControllers.delete(record);
    }
  }
}

function invalidateAuthCheck() {
  authCheckGeneration += 1;
  if (authCheckController) authCheckController.abort();
  authCheckController = null;
}

function setAuthMutationState(value) {
  authMutationInFlight = value;
  accessCodeInput.disabled = value;
  loginBtn.disabled = value;
  logoutBtn.disabled = value;
}

function clearSafeProgress() {
  clearTimeout(safeProgressTimer);
  safeProgressTimer = null;
  document.getElementById("safeProgress").hidden = true;
  for (let index = 0; index < 5; index += 1) {
    document.getElementById("safeStage" + index).dataset.state = "idle";
  }
}

function clearPreparedReport() {
  preparedReport = null;
  document.getElementById("reportDownloadBtn").hidden = true;
}

function monotonicNow() {
  return typeof performance !== "undefined" && typeof performance.now === "function"
    ? performance.now()
    : Date.now();
}

function formatElapsed(startedAt) {
  return `${((monotonicNow() - startedAt) / 1000).toFixed(1)} วินาที`;
}

const GUARD_LABELS = Object.freeze({
  instruction_override: "พยายามเปลี่ยนคำสั่งหลัก",
  role_hijack: "พยายามสวมบทบาทหรือเปลี่ยนบทบาท",
  exfiltration: "ขอเปิดเผยข้อมูลหรือคำสั่งภายใน",
  hidden_chars: "พบอักขระซ่อนหรือรูปแบบผิดปกติ",
  suspicious_payload: "พบ payload ที่ควรให้มนุษย์ตรวจทาน",
});
const SEVERITY_LABELS = Object.freeze({low: "ต่ำ", medium: "ปานกลาง", high: "สูง"});

function validDetectPayload(body, text) {
  if (!body || typeof body !== "object"
      || !Number.isInteger(body.detected_entity_count) || body.detected_entity_count < 0
      || !body.entity_type_counts || typeof body.entity_type_counts !== "object" || Array.isArray(body.entity_type_counts)
      || !Array.isArray(body.highlights)) return false;
  const counts = Object.entries(body.entity_type_counts);
  if (counts.some(([type, count]) => !/^[A-Z][A-Z0-9_]*$/.test(type) || !Number.isInteger(count) || count <= 0)
      || counts.reduce((sum, [, count]) => sum + count, 0) !== body.detected_entity_count
      || body.highlights.length !== body.detected_entity_count) return false;
  const textLength = Array.from(text).length;
  const seen = Object.fromEntries(counts.map(([type]) => [type, 0]));
  let previousEnd = 0;
  for (const item of body.highlights) {
    if (!item || typeof item !== "object"
        || !Number.isInteger(item.start) || !Number.isInteger(item.end)
        || item.start < previousEnd || item.end <= item.start || item.end > textLength
        || typeof item.data_type !== "string" || !Object.prototype.hasOwnProperty.call(seen, item.data_type)
        || (item.redact_type !== "FP" && item.redact_type !== "TB")) return false;
    seen[item.data_type] += 1;
    previousEnd = item.end;
  }
  return counts.every(([type, count]) => seen[type] === count);
}

function validGuardPayload(body) {
  if (!body || typeof body !== "object" || typeof body.flagged !== "boolean"
      || !Array.isArray(body.guard_findings)) return false;
  if (body.flagged !== Boolean(body.guard_findings.length)) return false;
  return body.guard_findings.every(item => item && typeof item === "object"
    && Object.prototype.hasOwnProperty.call(GUARD_LABELS, item.category)
    && Object.prototype.hasOwnProperty.call(SEVERITY_LABELS, item.severity));
}

function announce(message) {
  document.getElementById("appAnnouncement").textContent = message;
}

function syncModeCards(mode = selectedProtectionMode()) {
  for (const card of document.querySelectorAll("[data-mode-card]")) {
    const cardMode = card.dataset.modeCard || card.dataset.mode;
    card.setAttribute("aria-pressed", cardMode === mode ? "true" : "false");
  }
}

function anyPresentationEvidenceVisible() {
  return ["executiveSummary", "rawProtectedComparison", "sensitiveDataMap", "guardRiskPanel", "protectionReceipt"]
    .some(id => !document.getElementById(id).hidden);
}

function syncPresentationVisibility() {
  const stage = document.getElementById("presentationStage");
  stage.hidden = !anyPresentationEvidenceVisible();
  document.getElementById("presenterModeBtn").disabled = stage.hidden;
  document.getElementById("fullscreenBtn").disabled = stage.hidden;
  document.getElementById("presentationScenario").textContent = selectedScenario === "custom"
    ? "ข้อความที่ผู้ใช้กรอกเอง"
    : `${SCENARIO_LABELS[selectedScenario] || "ข้อมูลสังเคราะห์"}`;
  if (stage.hidden) {
    // Reset/logout/session-expiry owns recovery focus. Do not let a delayed
    // fullscreenchange return focus to the now-disabled presentation trigger.
    fullscreenReturnFocus = null;
    if (document.fullscreenElement === stage && typeof document.exitFullscreen === "function") {
      Promise.resolve(document.exitFullscreen()).catch(() => {});
    }
  }
  if (stage.hidden && document.body.classList.contains("presenter-mode")) leavePresenterMode();
}

function resetExecutiveEvidence() {
  lastRoundtrip = null;
  presentationRawText = "";
  presentationRestoredText = "";
  document.getElementById("executiveSummary").hidden = true;
  document.getElementById("rawProtectedComparison").hidden = true;
  document.getElementById("protectionReceipt").hidden = true;
  document.getElementById("executiveRestoredCard").hidden = true;
  document.getElementById("executiveRestored").textContent = "";
  for (const id of ["comparisonRaw", "comparisonProtected"]) document.getElementById(id).textContent = "";
  document.getElementById("comparisonRawCard").dataset.private = "false";
  document.getElementById("executivePii").textContent = "—";
  document.getElementById("executiveProtection").textContent = "—";
  document.getElementById("executivePromptRisk").textContent = "—";
  document.getElementById("executiveReport").textContent = "รอรายงาน";
  document.getElementById("executiveNarrative").textContent = "รอผลที่ตรวจสอบครบ";
  document.getElementById("comparisonLengths").textContent = "รอผลการเปรียบเทียบ";
  document.getElementById("comparisonDetectedProof").textContent = "รอผลตรวจเทียบค่าที่ตรวจพบ";
  for (const id of ["receiptMode", "receiptProvider", "receiptPii", "receiptSafety", "receiptResidual", "receiptRestoration", "receiptSection26", "receiptDuration"]) {
    document.getElementById(id).textContent = "—";
  }
  document.getElementById("receiptTypes").textContent = "ยังไม่มีประเภทข้อมูล";
  syncPresentationVisibility();
}

function resetScanEvidence() {
  lastGuard = null;
  document.getElementById("sensitiveDataMap").hidden = true;
  document.getElementById("guardRiskPanel").hidden = true;
  document.getElementById("dataMapList").textContent = "";
  document.getElementById("guardRiskList").textContent = "";
  document.getElementById("dataMapNote").textContent = "แผนที่แสดงประเภทและตำแหน่งเชิงสัดส่วนเท่านั้น ไม่แสดงค่าข้อมูล";
  document.getElementById("glossaryDetected").textContent = "ประเภทที่พบในคำขอปัจจุบัน: ยังไม่มีผล";
  syncPresentationVisibility();
  if (lastRoundtrip && lastRoundtrip.text === editor.value) updateExecutiveSummary();
}

function resetReportEvidence() {
  lastReport = null;
  if (lastRoundtrip && lastRoundtrip.text === editor.value) updateExecutiveSummary();
}

function renderSensitiveDataMap(text, counts, highlights = []) {
  const entries = Object.entries(counts || {}).filter(([, count]) => Number.isInteger(count) && count > 0);
  const list = document.getElementById("dataMapList");
  const panel = document.getElementById("sensitiveDataMap");
  const textLength = Math.max(1, Array.from(text || "").length);
  if (!entries.length) {
    list.innerHTML = '<p class="risk-clear">ไม่พบประเภทข้อมูลส่วนบุคคลในผลปัจจุบัน</p>';
  } else {
    list.innerHTML = entries.map(([type, count]) => {
      const matching = highlights.filter(item => item.data_type === type
        && Number.isInteger(item.start) && Number.isInteger(item.end)
        && item.start >= 0 && item.end > item.start && item.end <= textLength);
      const fills = matching.map(item => {
        const left = Math.max(0, Math.min(99, (item.start / textLength) * 100));
        const width = Math.max(1, Math.min(100 - left, ((item.end - item.start) / textLength) * 100));
        return `<i class="data-map-fill" style="left:${left.toFixed(1)}%;width:${width.toFixed(1)}%"></i>`;
      }).join("");
      const unavailable = matching.length ? "" : " unavailable";
      return `<div class="data-map-row"><b>${esc(labelFor(type))}</b><span class="data-map-track${unavailable}" aria-hidden="true">${fills}</span><span>${count}</span></div>`;
    }).join("");
  }
  document.getElementById("dataMapNote").textContent = highlights.length
    ? "แสดงประเภท จำนวน และตำแหน่งเชิงสัดส่วนจาก Privacy Scan โดยไม่แสดงค่าข้อมูล"
    : "แสดงประเภทและจำนวนจาก Safe AI; รัน Privacy Scan เพื่อเพิ่มตำแหน่งเชิงสัดส่วน";
  document.getElementById("glossaryDetected").textContent = entries.length
    ? `ประเภทที่พบในคำขอปัจจุบัน: ${entries.map(([type]) => labelFor(type)).join(" · ")}`
    : "ประเภทที่พบในคำขอปัจจุบัน: ไม่พบ";
  panel.hidden = false;
  syncPresentationVisibility();
}

function renderGuardRisk(findings, available = true) {
  const safeFindings = Array.isArray(findings) ? findings : [];
  const list = document.getElementById("guardRiskList");
  if (!available) {
    list.innerHTML = '<p class="warn">การตรวจ Guard ไม่พร้อม · ผล Privacy Scan ยังใช้ได้ แต่ไม่ควรตีความว่าไม่มีความเสี่ยง</p>';
  } else if (!safeFindings.length) {
    list.innerHTML = '<p class="risk-clear">ไม่พบสัญญาณตามกฎ Guard ที่มีขอบเขตจำกัด</p>';
  } else {
    list.innerHTML = safeFindings.map(item => {
      const category = GUARD_LABELS[item.category] || item.category;
      const severity = SEVERITY_LABELS[item.severity] || item.severity;
      return `<div class="risk-row"><strong>${esc(category)}</strong><span class="risk-severity">ระดับ ${esc(severity)}</span></div>`;
    }).join("");
  }
  document.getElementById("guardRiskPanel").hidden = false;
  syncPresentationVisibility();
  if (lastRoundtrip && lastRoundtrip.text === editor.value) updateExecutiveSummary();
}

function currentGuardSummary() {
  if (!lastGuard || lastGuard.text !== editor.value) return "ยังไม่ตรวจ";
  if (!lastGuard.available) return "ตรวจไม่ได้";
  return lastGuard.findings.length ? `พบ ${lastGuard.findings.length} สัญญาณ` : "ไม่พบตามกฎ";
}

function updateExecutiveSummary() {
  if (!lastRoundtrip || lastRoundtrip.text !== editor.value) {
    document.getElementById("executiveSummary").hidden = true;
    syncPresentationVisibility();
    return;
  }
  const typeLabels = Object.keys(lastRoundtrip.entityTypeCounts).map(labelFor);
  document.getElementById("executivePii").textContent = `${lastRoundtrip.detectedEntityCount} รายการ · ${typeLabels.length} ประเภท`;
  document.getElementById("executiveProtection").textContent = `${MODE_DETAILS[lastRoundtrip.mode].label} · thaillm-8b`;
  document.getElementById("executivePromptRisk").textContent = currentGuardSummary();
  const reportBound = lastReport && lastReport.text === editor.value;
  document.getElementById("executiveReport").textContent = reportBound
    ? `${lastReport.score}/100 · เกรด ${lastReport.grade}`
    : "รอ PDPA Report";
  const reportSentence = reportBound
    ? ` PDPA Report ของข้อความเดียวกันให้คะแนน ${lastReport.score} และเกรด ${lastReport.grade}.`
    : " ยังไม่ได้สร้าง PDPA Report สำหรับข้อความชุดนี้";
  document.getElementById("executiveNarrative").textContent =
    `AI Guard ตรวจพบ ${lastRoundtrip.detectedEntityCount} รายการ ปกป้องก่อนส่งไปยัง thaillm-8b และกู้คืนผลครบตาม gate ของคำขอนี้.${reportSentence}`;
  document.getElementById("executiveSummary").hidden = false;
  syncPresentationVisibility();
}

function renderRawProtectedComparison(text, sanitizedText, proof) {
  presentationRawText = text;
  document.getElementById("comparisonProtected").textContent = sanitizedText;
  syncRawPresentationPrivacy();
  document.getElementById("comparisonLengths").textContent =
    `ก่อนปกป้อง ${Array.from(text).length} ตัวอักษร · หลังปกป้อง ${Array.from(sanitizedText).length} ตัวอักษร`;
  document.getElementById("comparisonDetectedProof").textContent = proof.status === "pass"
    ? `ตรวจเทียบค่าที่ Privacy Scan พบ ${proof.checked} รายการ · ไม่พบค่าตรงกันในข้อความที่ส่งต่อ`
    : proof.status === "unknown"
      ? "ยังไม่มีตำแหน่งจาก Privacy Scan สำหรับตรวจเทียบค่าตรงกัน"
      : "การตรวจเทียบไม่ผ่าน · ผลไม่ได้รับสถานะสำเร็จ";
  document.getElementById("rawProtectedComparison").hidden = false;
  syncPresentationVisibility();
}

function renderProtectionReceipt(snapshot) {
  const types = Object.keys(snapshot.entityTypeCounts).map(labelFor);
  document.getElementById("receiptMode").textContent = MODE_DETAILS[snapshot.mode].label;
  document.getElementById("receiptProvider").textContent = "Pathumma · thaillm-8b";
  document.getElementById("receiptPii").textContent = `${snapshot.detectedEntityCount} รายการ / ${types.length} ประเภท`;
  document.getElementById("receiptSafety").textContent = "ผ่าน · residual 0";
  document.getElementById("receiptResidual").textContent = `${snapshot.residualCount} สัญญาณ`;
  document.getElementById("receiptRestoration").textContent = `สมบูรณ์ · ตกค้าง ${snapshot.leftoverCount}`;
  document.getElementById("receiptSection26").textContent = snapshot.section26Categories.length
    ? snapshot.section26Categories.map(labelFor).join(" · ")
    : "ไม่พบธง";
  document.getElementById("receiptDuration").textContent = snapshot.duration;
  document.getElementById("receiptTypes").textContent = types.length
    ? `ประเภทที่ระบบตรวจพบ: ${types.join(" · ")}`
    : "ประเภทที่ระบบตรวจพบ: ไม่พบข้อมูลส่วนบุคคล";
  document.getElementById("protectionReceipt").hidden = false;
  syncPresentationVisibility();
}

function clearSessionExpiry() {
  clearTimeout(sessionExpiryTimer);
  sessionExpiryTimer = null;
  sessionExpiresAt = 0;
}

function expireLocalSession() {
  if (!authenticated) return;
  setAuthState(false, "session หมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง");
  showSessionExpiredRecovery("/api/session");
}

function scheduleSessionExpiry(expiresIn) {
  clearSessionExpiry();
  const boundedSeconds = Math.max(0, Math.min(1800, Number(expiresIn) || 0));
  sessionExpiresAt = Date.now() + boundedSeconds * 1000;
  sessionExpiryTimer = setTimeout(expireLocalSession, boundedSeconds * 1000);
  if (sessionExpiryTimer && typeof sessionExpiryTimer.unref === "function") sessionExpiryTimer.unref();
}

function enforceSessionDeadline() {
  if (authenticated && sessionExpiresAt && Date.now() >= sessionExpiresAt) expireLocalSession();
}

const PROVIDER_UNCERTAIN_LOCK_MS = 205000;

function acquireProviderLane() {
  if (providerLaneActive) return false;
  clearTimeout(providerLaneReleaseTimer);
  providerLaneReleaseTimer = null;
  providerLaneActive = true;
  syncBusinessControls();
  return true;
}

function settleProviderLane(responseReceived) {
  clearTimeout(providerLaneReleaseTimer);
  providerLaneReleaseTimer = null;
  if (responseReceived) {
    providerLaneActive = false;
    syncBusinessControls();
    return;
  }
  // With no HTTP response the browser cannot know whether the server/provider
  // is still running. Hold the lane through the configured 200s proxy window.
  providerLaneActive = true;
  providerLaneReleaseTimer = setTimeout(() => {
    providerLaneActive = false;
    providerLaneReleaseTimer = null;
    syncBusinessControls();
    announce("พร้อมลอง Safe AI ใหม่หลังช่วงป้องกันคำขอซ้ำ");
  }, PROVIDER_UNCERTAIN_LOCK_MS);
  if (providerLaneReleaseTimer && typeof providerLaneReleaseTimer.unref === "function") {
    providerLaneReleaseTimer.unref();
  }
  syncBusinessControls();
}

function leavePresenterMode() {
  document.body.classList.remove("presenter-mode");
  const button = document.getElementById("presenterModeBtn");
  button.setAttribute("aria-pressed", "false");
  button.textContent = "โหมดนำเสนอ";
  syncRawPresentationPrivacy();
  const stage = document.getElementById("presentationStage");
  if (document.fullscreenElement === stage && typeof document.exitFullscreen === "function") {
    Promise.resolve(document.exitFullscreen()).catch(() => {});
  }
}

function syncRawPresentationPrivacy(forcePrivate = false) {
  const presenting = document.body.classList.contains("presenter-mode")
    || document.fullscreenElement === document.getElementById("presentationStage")
    || forcePrivate;
  const privateActive = presenting && selectedScenario === "custom";
  document.getElementById("comparisonRawCard").dataset.private = privateActive ? "true" : "false";
  document.getElementById("executiveRestoredCard").dataset.private = privateActive ? "true" : "false";
  document.getElementById("comparisonRaw").textContent = privateActive
    ? "ซ่อนข้อความที่ผู้ใช้กรอกเองระหว่างการนำเสนอ"
    : presentationRawText;
  document.getElementById("executiveRestored").textContent = privateActive
    ? "ซ่อนผลลัพธ์ของข้อความที่ผู้ใช้กรอกเองระหว่างการนำเสนอ"
    : presentationRestoredText;
}

function syncFullscreenState() {
  const stage = document.getElementById("presentationStage");
  const active = document.fullscreenElement === stage;
  const button = document.getElementById("fullscreenBtn");
  button.setAttribute("aria-pressed", active ? "true" : "false");
  button.textContent = active ? "ออกจากเต็มจอ" : "แสดงหลักฐานเต็มจอ";
  syncRawPresentationPrivacy();
  if (active) {
    stage.focus({preventScroll: true});
    announce("แสดงหลักฐานเต็มจอแล้ว กด Escape หรือปุ่มออกจากเต็มจอเพื่อกลับ");
  } else if (fullscreenReturnFocus) {
    const returnTarget = button.disabled ? document.getElementById("safe-ai") : fullscreenReturnFocus;
    fullscreenReturnFocus = null;
    returnTarget.focus({preventScroll: true});
    announce("ออกจากการแสดงหลักฐานเต็มจอแล้ว");
  }
}

function setGuidedStep(name, state, label) {
  const suffix = name === "scan" ? "Scan" : name === "safe" ? "Safe" : "Report";
  document.getElementById("guidedStep" + suffix).dataset.state = state;
  document.getElementById("guidedState" + suffix).textContent = label;
}

function resetGuidedPresentation(message = "เข้าสู่ระบบ แล้วกดเริ่มเพื่อเรียก API จริง") {
  guidedRunning = false;
  for (const name of ["scan", "safe", "report"]) setGuidedStep(name, "idle", "รอเริ่ม");
  document.getElementById("guidedStatus").textContent = message;
  document.getElementById("guidedStatus").dataset.tone = "";
  document.getElementById("guidedPii").textContent = "—";
  document.getElementById("guidedMode").textContent = MODE_DETAILS[selectedProtectionMode()].label;
  document.getElementById("guidedSafety").textContent = "รอผล";
  document.getElementById("guidedTiming").textContent = "—";
  document.getElementById("guidedProofLink").hidden = true;
}

function resetScanPresentation(message = "เลือกตัวอย่างหรือพิมพ์ข้อความเพื่อเริ่มต้น") {
  lastDetection = null;
  resetScanEvidence();
  highlight.textContent = editor.value.trim() ? "กดสแกนเพื่อดูตำแหน่ง PII" : "ผลการไฮไลต์จะแสดงที่นี่หลังสแกน";
  renderLegend({});
  document.getElementById("piiCount").textContent = "0";
  document.getElementById("piiTypeCount").textContent = "0";
  document.getElementById("piiTypes").textContent = "ยังไม่มีข้อมูลให้วิเคราะห์";
  document.getElementById("guardBar").textContent = "";
  document.getElementById("scanTiming").textContent = "ยังไม่มีเวลาคำขอ";
  meta.textContent = message;
  meta.dataset.tone = "";
}

function resetSafePresentation(message) {
  clearSafeProgress();
  resetExecutiveEvidence();
  document.getElementById("safeOriginal").textContent = editor.value || "กด “ใช้ตัวอย่างสังเคราะห์” เพื่อเริ่มได้ทันที";
  document.getElementById("masked").textContent = editor.value.trim() ? "รอกดส่งข้อความชุดนี้" : "ยังไม่ได้ส่ง";
  document.getElementById("restored").textContent = editor.value.trim() ? "ยังไม่มีผลสำหรับข้อความชุดนี้" : "ยังไม่ได้ส่ง";
  document.getElementById("safeOriginal").dataset.filled = editor.value.trim() ? "true" : "false";
  for (const id of ["masked", "restored"]) {
    document.getElementById(id).dataset.filled = "false";
    document.getElementById(id).dataset.tone = "";
  }
  document.getElementById("safeElapsed").textContent = message === undefined
    ? (editor.value.trim() ? "พร้อมเริ่มเส้นทาง Safe AI" : "กด “ใช้ตัวอย่างสังเคราะห์” หรือเลือกข้อความจาก Privacy Scan")
    : message;
  document.getElementById("safeElapsed").dataset.tone = "";
  document.getElementById("safeAnnouncement").textContent = "";
  document.getElementById("safeCount").textContent = "—";
  document.getElementById("safeTypes").textContent = "—";
  document.getElementById("safeTypeLabels").textContent = "ประเภทข้อมูลที่ตรวจพบ";
  document.getElementById("safeProtection").textContent = "รอผล";
  document.getElementById("safeRestoration").textContent = "รอผล";
  document.getElementById("safeMode").textContent = MODE_DETAILS[selectedProtectionMode()].label;
  document.getElementById("safeProvider").textContent = "รอผล";
  document.getElementById("safeResidual").textContent = "รอผล";
  document.getElementById("safeLeftover").textContent = "รอผล";
  document.getElementById("safeEvidenceSafety").textContent = "รอผล";
  document.getElementById("safeEvidenceRestoration").textContent = "รอผล";
  document.getElementById("safeSection26").textContent = "รอผล";
  document.getElementById("safeDuration").textContent = "—";
  document.getElementById("providerTag").hidden = true;
  document.getElementById("providerTag").textContent = "";
  document.getElementById("evidenceSanitized").textContent = "ยังไม่มีข้อมูล";
  document.getElementById("evidenceWarnings").textContent = "ยังไม่มีข้อมูลความปลอดภัย";
  document.getElementById("proofStatus").textContent = "รอผล Safe AI";
  document.getElementById("proofMethod").textContent = "เมื่อ Privacy Scan และ Safe AI ใช้ข้อความเดียวกัน เบราว์เซอร์จะเปรียบเทียบค่าที่ตรวจพบกับข้อความที่ส่งให้ AI โดยไม่แสดงข้อมูลจับคู่";
  document.getElementById("proofCallout").dataset.tone = "";
}

function resetReportPresentation() {
  clearPreparedReport();
  resetReportEvidence();
  document.getElementById("reportMeta").textContent = "";
  document.getElementById("reportMeta").dataset.tone = "";
  document.getElementById("reportScore").textContent = "—";
  document.getElementById("reportGrade").textContent = "—";
  document.getElementById("reportScope").textContent = "ยังไม่ได้สร้างรายงาน";
  document.getElementById("reportCategories").textContent = "ประเภทข้อมูลจะแสดงจาก Privacy Scan ของข้อความเดียวกัน โดยไม่ใส่ข้อความต้นฉบับในสรุปนี้";
  document.getElementById("reportTiming").textContent = "ยังไม่มีเวลาคำขอ";
}

function syncBusinessControls() {
  const blocked = !authenticated || guidedRunning;
  for (const id of ["scanBtn", "reportBtn"]) {
    document.getElementById(id).disabled = blocked;
  }
  document.getElementById("send").disabled = blocked || providerLaneActive;
  document.getElementById("guidedStart").disabled = blocked || providerLaneActive;
  document.getElementById("reportDownloadBtn").disabled = !authenticated || guidedRunning;
  document.getElementById("mode").disabled = guidedRunning || providerLaneActive;
  document.getElementById("safeDemoBtn").disabled = guidedRunning || providerLaneActive;
  for (const button of document.querySelectorAll("[data-mode-card]")) button.disabled = guidedRunning || providerLaneActive;
  for (const button of document.querySelectorAll("[data-scenario]")) button.disabled = guidedRunning || providerLaneActive;
}

function clearSensitiveState() {
  clearTimeout(debounceTimer);
  detectGeneration += 1;
  roundtripGeneration += 1;
  reportGeneration += 1;
  guidedGeneration += 1;
  guidedRunning = false;
  accessCodeInput.value = "";
  editor.value = "";
  document.getElementById("characterCount").textContent = "0 / 20,000 ตัวอักษร";
  resetScanPresentation("เข้าสู่ระบบก่อนส่งข้อความไปประมวลผล");
  highlight.textContent = "";
  resetSafePresentation("");
  resetReportPresentation();
  resetGuidedPresentation("เข้าสู่ระบบ แล้วกดเริ่มเพื่อเรียก API จริง");
  leavePresenterMode();
  selectedScenario = "hr";
  document.body.dataset.privateInput = "false";
  document.getElementById("guidedScenario").textContent = SCENARIO_LABELS.hr;
  document.getElementById("scenarioStatus").textContent = "ยังไม่ใส่ข้อความ · Quick Start จะใช้ตัวอย่างสมัครงานสังเคราะห์เป็นค่าเริ่มต้น";
  for (const button of document.querySelectorAll("[data-scenario]")) {
    button.setAttribute("aria-pressed", "false");
  }
}

function setAuthState(value, message) {
  authenticated = value;
  document.getElementById("authCard").dataset.state = value ? "authenticated" : "signed-out";
  accessCodeInput.hidden = value;
  loginBtn.hidden = value;
  logoutBtn.hidden = !value;
  if (value) logoutBtn.textContent = "ออกจากระบบและล้างข้อมูล";
  authStatus.textContent = message;
  const neutralAuthMessage = message.includes("กำลัง") || message.includes("กรุณาใส่");
  authStatus.dataset.tone = value ? "safe" : neutralAuthMessage ? "" : "error";
  if (!value) {
    clearSessionExpiry();
    invalidateAuthCheck();
    invalidateBusinessRequests();
    clearSensitiveState();
  } else if (!editor.value) {
    meta.textContent = "เลือกตัวอย่างสังเคราะห์หรือพิมพ์ข้อความเพื่อเริ่มต้น";
    highlight.textContent = "ผลการไฮไลต์จะแสดงที่นี่หลังสแกน";
    document.getElementById("safeElapsed").textContent = "กด “ใช้ตัวอย่างสังเคราะห์” หรือเลือกข้อความจาก Privacy Scan";
    document.getElementById("guidedStatus").textContent = "พร้อมเริ่ม Quick Start ด้วยข้อมูลสังเคราะห์";
  }
  syncBusinessControls();
}

function showSessionExpiredRecovery(url) {
  const message = "เซสชันหมดอายุ · กรุณากลับไปเข้าสู่ระบบด้านบน";
  if (url === "/api/roundtrip") {
    document.getElementById("safeElapsed").textContent = message;
    document.getElementById("safeElapsed").dataset.tone = "caution";
  } else if (url === "/api/analyze-report") {
    document.getElementById("reportMeta").textContent = message;
    document.getElementById("reportMeta").dataset.tone = "caution";
  } else {
    meta.textContent = message;
    meta.dataset.tone = "caution";
  }
  document.getElementById("guidedStatus").textContent = message;
  document.getElementById("guidedStatus").dataset.tone = "caution";
  if (typeof accessCodeInput.focus === "function") accessCodeInput.focus();
}

async function checkAuthSession() {
  const generation = authCheckGeneration + 1;
  authCheckGeneration = generation;
  if (authCheckController) authCheckController.abort();
  const controller = new AbortController();
  authCheckController = controller;
  try {
    const r = await fetch("/api/auth/session", {
      credentials: "same-origin",
      signal: controller.signal,
    });
    const body = await safeJson(r);
    if (generation !== authCheckGeneration) return;
    const valid = r.ok
      && body.authenticated === true
      && Number.isInteger(body.expires_in)
      && body.expires_in >= 0
      && body.expires_in <= 1800;
    setAuthState(valid, valid ? "เข้าสู่ระบบแล้ว — session อายุไม่เกิน 30 นาที" : "กรุณาใส่รหัสเชิญ");
    lastAuthRestoredWorkflow = valid && restoreRequestedWorkflow();
    if (valid) scheduleSessionExpiry(body.expires_in);
  } catch (err) {
    if (generation !== authCheckGeneration || (err && err.name === "AbortError")) return;
    setAuthState(false, "ตรวจสอบสิทธิ์ไม่ได้");
  } finally {
    if (authCheckController === controller) authCheckController = null;
  }
}

async function apiJson(url, options = {}) {
  if (!authenticated) throw new StaleBusinessRequest();
  const generation = authGeneration;
  const controller = new AbortController();
  const providerBound = url === "/api/roundtrip";
  const record = {controller, providerBound};
  let responseReceived = false;
  businessControllers.add(record);
  try {
    const r = await fetch(url, {
      ...options,
      credentials: "same-origin",
      signal: controller.signal,
    });
    responseReceived = true;
    if (r.status === 401) {
      setAuthState(false, "session หมดอายุ กรุณาเข้าสู่ระบบอีกครั้ง");
      showSessionExpiredRecovery(url);
      throw new StaleBusinessRequest();
    }
    const body = await safeJson(r);
    if (!authenticated || generation !== authGeneration) {
      throw new StaleBusinessRequest();
    }
    return {r, body};
  } finally {
    businessControllers.delete(record);
    if (providerBound) settleProviderLane(responseReceived);
  }
}

loginBtn.addEventListener("click", async () => {
  if (authMutationInFlight) return;
  let code = accessCodeInput.value;
  let loginSucceeded = false;
  if (!code) return;
  setAuthMutationState(true);
  logoutBtn.hidden = true;
  invalidateAuthCheck();
  authStatus.textContent = "กำลังยืนยัน...";
  try {
    const r = await fetch("/api/auth/login", {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({access_code: code}),
    });
    if (r.status === 204) {
      await checkAuthSession();
      loginSucceeded = authenticated;
    } else {
      const body = await safeJson(r);
      setAuthState(false, errorMessage(r.status, detailText(body), "auth"));
    }
  } catch {
    setAuthState(false, "เชื่อมต่อระบบยืนยันสิทธิ์ไม่ได้");
  } finally {
    code = "";
    accessCodeInput.value = "";
    setAuthMutationState(false);
    if (loginSucceeded && !lastAuthRestoredWorkflow) logoutBtn.focus({preventScroll: true});
    lastAuthRestoredWorkflow = false;
  }
});

accessCodeInput.addEventListener("keydown", event => {
  if (event.key === "Enter") loginBtn.click();
});

logoutBtn.addEventListener("click", async () => {
  if (authMutationInFlight) return;
  setAuthMutationState(true);
  setAuthState(false, "กำลังออกจากระบบ...");
  document.getElementById("authCard").focus({preventScroll: true});
  let complete = false;
  try {
    const r = await fetch("/api/auth/logout", {method: "POST", credentials: "same-origin"});
    complete = r.status === 204;
  } catch {
    /* local state is already invalidated */
  }
  accessCodeInput.value = "";
  setAuthMutationState(false);
  if (complete) {
    logoutBtn.hidden = true;
    logoutBtn.textContent = "ออกจากระบบ";
    authStatus.textContent = "ออกจากระบบแล้ว";
    accessCodeInput.focus({preventScroll: true});
  } else {
    logoutBtn.hidden = false;
    logoutBtn.textContent = "ลองออกจากระบบอีกครั้ง";
    authStatus.textContent =
      "ล้างข้อมูลในหน้านี้แล้ว แต่ session บนเซิร์ฟเวอร์อาจยังอยู่ กรุณาลองออกจากระบบอีกครั้ง";
    authStatus.dataset.tone = "error";
    logoutBtn.focus({preventScroll: true});
  }
});

function downloadB64(b64, name, mime) {
  const bytes = Uint8Array.from(atob(b64), ch => ch.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], {type: mime}));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

/* ── demo: shared input + explicit Privacy Scan ── */
const editor = document.getElementById("editor");
const highlight = document.getElementById("highlight");
const meta = document.getElementById("meta");
let debounceTimer = null;

function hasMeaningfulWork() {
  return Boolean(editor.value.trim() || preparedReport || lastDetection || lastRoundtrip || lastReport || providerLaneActive);
}

window.addEventListener("beforeunload", event => {
  if (!hasMeaningfulWork()) return;
  event.preventDefault();
  event.returnValue = "";
});

document.addEventListener("click", event => {
  const link = event.target && typeof event.target.closest === "function"
    ? event.target.closest("a[href]")
    : null;
  if (!link || !hasMeaningfulWork() || typeof location === "undefined") return;
  const destination = new URL(link.href, location.href);
  if (destination.origin !== location.origin || destination.pathname === location.pathname) return;
  const warning = providerLaneActive
    ? "คำขอ Safe AI อาจยังทำงานบนเซิร์ฟเวอร์ แม้ออกจากหน้านี้ ข้อมูลและผลในหน้านี้จะถูกล้าง ต้องการออกหรือไม่"
    : "ข้อมูลหรือผลที่อยู่ในหน้านี้จะถูกล้างและไม่สามารถกู้คืน ต้องการออกหรือไม่";
  if (typeof window.confirm === "function" && !window.confirm(warning)) {
    event.preventDefault();
    return;
  }
  clearSensitiveState();
});

function codePointRangeToUtf16(text, start, end) {
  const points = Array.from(text);
  if (
    !Number.isInteger(start) || !Number.isInteger(end)
    || start < 0 || end < start || end > points.length
  ) throw new Error("invalid code-point range");
  return [
    points.slice(0, start).join("").length,
    points.slice(0, end).join("").length,
  ];
}

function renderHighlight(text, entities) {
  const sorted = [...entities].sort((a, b) => b.start - a.start);
  const parts = [];
  let cursor = text.length;
  for (const e of sorted) {
    const [start, end] = codePointRangeToUtf16(text, e.start, e.end);
    if (end > cursor) continue; // กัน span ซ้อน (server dedupe แล้ว แต่กันไว้)
    parts.unshift({text: text.slice(end, cursor)});
    parts.unshift({text: text.slice(start, end), type: e.data_type});
    cursor = start;
  }
  parts.unshift({text: text.slice(0, cursor)});
  const html = parts.map(p => p.type
    ? `<mark style="background:${colorFor(p.type)}" title="${escAttr(labelFor(p.type))}">${esc(p.text)}</mark>`
    : esc(p.text)).join("");
  highlight.innerHTML = html + "\n";
}

function renderLegend(counts) {
  const legend = document.getElementById("legend");
  legend.innerHTML = Object.entries(counts).map(([t, n]) =>
    `<span><i class="dot" style="background:${colorFor(t)}"></i>${esc(labelFor(t))} (${esc(n)})</span>`
  ).join("");
}

async function detectNow() {
  const text = editor.value;
  const generation = ++detectGeneration;
  const startedAt = monotonicNow();
  const scanBtn = document.getElementById("scanBtn");
  if (!text.trim()) {
    highlight.textContent = "กรุณาใส่ข้อความหรือเลือกตัวอย่างก่อนสแกน";
    renderLegend({});
    meta.textContent = "กรุณาใส่ข้อความหรือเลือกตัวอย่างก่อนสแกน";
    meta.dataset.tone = "caution";
    document.getElementById("guardBar").innerHTML = "";
    document.getElementById("piiCount").textContent = "0";
    document.getElementById("piiTypeCount").textContent = "0";
    document.getElementById("piiTypes").textContent = "ยังไม่มีข้อมูลให้วิเคราะห์";
    document.getElementById("scanTiming").textContent = "ยังไม่มีเวลาคำขอ";
    return false;
  }
  if (!authenticated) {
    meta.textContent = "กรุณาเข้าสู่ระบบก่อนสแกนข้อมูล";
    meta.dataset.tone = "caution";
    return false;
  }
  scanBtn.disabled = true;
  lastDetection = null;
  resetScanEvidence();
  highlight.textContent = "กำลังวิเคราะห์ข้อความ...";
  renderLegend({});
  document.getElementById("piiCount").textContent = "—";
  document.getElementById("piiTypeCount").textContent = "—";
  document.getElementById("piiTypes").textContent = "กำลังสรุปผลใหม่";
  document.getElementById("guardBar").textContent = "";
  document.getElementById("scanTiming").textContent = "กำลังวัดเวลาคำขอ /detect ในเบราว์เซอร์";
  meta.textContent = "กำลังสแกนข้อมูลส่วนบุคคลภาษาไทย";
  meta.dataset.tone = "";
  try {
    const {r, body} = await apiJson("/api/detect", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text}),
    });
    if (!r.ok) {
      if (generation !== detectGeneration || text !== editor.value) return;
      highlight.textContent = "ยังไม่มีผลการสแกน";
      renderLegend({});
      document.getElementById("piiCount").textContent = "0";
      document.getElementById("piiTypeCount").textContent = "0";
      document.getElementById("piiTypes").textContent = "ไม่มีผลใหม่ให้แสดง";
      document.getElementById("scanTiming").textContent = `คำขอไม่สำเร็จหลัง ${formatElapsed(startedAt)}`;
      meta.textContent = errorMessage(r.status, detailText(body), "text");
      meta.dataset.tone = "error";
      return false;
    }
    if (generation !== detectGeneration || text !== editor.value) return false;
    if (!validDetectPayload(body, text)) {
      highlight.textContent = "ยังไม่มีผลการสแกนที่ตรวจสอบได้";
      renderLegend({});
      document.getElementById("piiCount").textContent = "0";
      document.getElementById("piiTypeCount").textContent = "0";
      document.getElementById("piiTypes").textContent = "ผลตอบกลับไม่ครบตามสัญญา API";
      document.getElementById("scanTiming").textContent = `คำขอหยุดอย่างปลอดภัยหลัง ${formatElapsed(startedAt)}`;
      meta.textContent = "ผล Privacy Scan ไม่สมบูรณ์ กรุณาลองใหม่";
      meta.dataset.tone = "error";
      return false;
    }
    renderHighlight(text, body.highlights);
    renderLegend(body.entity_type_counts);
    const typeEntries = Object.entries(body.entity_type_counts);
    lastDetection = {
      text,
      highlights: body.highlights.map(item => ({start: item.start, end: item.end, data_type: item.data_type})),
      entityTypeCounts: {...body.entity_type_counts},
      detectedEntityCount: body.detected_entity_count,
    };
    renderSensitiveDataMap(text, body.entity_type_counts, lastDetection.highlights);
    document.getElementById("piiCount").textContent = String(body.detected_entity_count);
    document.getElementById("piiTypeCount").textContent = String(typeEntries.length);
    document.getElementById("piiTypes").textContent = typeEntries.length
      ? typeEntries.map(([type, count]) => `${labelFor(type)} ${count}`).join(" · ")
      : "ไม่พบข้อมูลส่วนบุคคลในข้อความนี้";
    meta.textContent = body.detected_entity_count
      ? `พบข้อมูลส่วนบุคคล ${body.detected_entity_count} รายการ จาก ${typeEntries.length} ประเภท`
      : "ไม่พบข้อมูลส่วนบุคคลในข้อความนี้";
    meta.dataset.tone = body.detected_entity_count ? "caution" : "safe";
    document.getElementById("scanTiming").textContent = `Privacy Scan /detect · เวลารวมที่วัดในเบราว์เซอร์ ${formatElapsed(startedAt)}`;
    try {
      const {r: gr, body: gb} = await apiJson("/api/guard", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text}),
      });
      if (generation !== detectGeneration || text !== editor.value) return false;
      const bar = document.getElementById("guardBar");
      if (!gr.ok || !validGuardPayload(gb)) {
        lastGuard = {text, available: false, findings: []};
        renderGuardRisk([], false);
        bar.textContent = "การตรวจเตือนคำสั่งไม่พร้อม · Privacy Scan ผ่าน แต่ Quick Start จะหยุดก่อนเรียก Safe AI";
        return false;
      }
      const findings = Array.isArray(gb.guard_findings) ? gb.guard_findings : [];
      lastGuard = {text, available: true, findings: findings.map(item => ({category: item.category, severity: item.severity}))};
      renderGuardRisk(lastGuard.findings, true);
      bar.innerHTML = findings.length
        ? '<span class="guard-ok">พบสัญญาณคำสั่งที่ควรตรวจสอบ · ดู Prompt Risk ด้านล่าง</span> '
          + findings.map(g => `<span class="chip guard-chip">${esc(GUARD_LABELS[g.category] || g.category)} · ${esc(SEVERITY_LABELS[g.severity] || g.severity)}</span>`).join("")
        : '<span class="guard-ok">ไม่พบสัญญาณตามกฎ Guard ที่มีขอบเขตจำกัด · Guard เป็นคำเตือนและไม่บล็อก</span>';
    } catch (err) {
      if (isStaleBusinessError(err)) return false;
      if (generation !== detectGeneration || text !== editor.value) return false;
      lastGuard = {text, available: false, findings: []};
      renderGuardRisk([], false);
      document.getElementById("guardBar").textContent = "เชื่อมต่อการตรวจเตือนคำสั่งไม่ได้ · Privacy Scan ผ่าน แต่ Quick Start จะหยุดก่อนเรียก Safe AI";
      return false;
    }
    return true;
  } catch (err) {
    if (isStaleBusinessError(err)) return false;
    if (generation !== detectGeneration || text !== editor.value) return false;
    lastDetection = null;
    highlight.textContent = "ยังไม่มีผลการสแกน";
    renderLegend({});
    document.getElementById("piiCount").textContent = "0";
    document.getElementById("piiTypeCount").textContent = "0";
    document.getElementById("piiTypes").textContent = "ไม่มีผลใหม่ให้แสดง";
    meta.textContent = "เชื่อมต่อบริการไม่ได้ กรุณาลองใหม่";
    meta.dataset.tone = "error";
    document.getElementById("scanTiming").textContent = `เชื่อมต่อไม่สำเร็จหลัง ${formatElapsed(startedAt)}`;
    return false;
  } finally {
    if (generation === detectGeneration) scanBtn.disabled = !authenticated || guidedRunning;
  }
}

function handleInputChange({preserveScenario = false} = {}) {
  if (guidedRunning) invalidateBusinessRequests();
  detectGeneration += 1;
  roundtripGeneration += 1;
  reportGeneration += 1;
  guidedGeneration += 1;
  guidedRunning = false;
  document.getElementById("characterCount").textContent = `${Array.from(editor.value).length.toLocaleString()} / 20,000 ตัวอักษร`;
  resetScanPresentation(editor.value.trim() ? "พร้อมสแกนข้อความชุดนี้" : "เลือกตัวอย่างหรือพิมพ์ข้อความเพื่อเริ่มต้น");
  resetSafePresentation();
  resetReportPresentation();
  if (!preserveScenario) selectedScenario = editor.value.trim() ? "custom" : "hr";
  document.body.dataset.privateInput = selectedScenario === "custom" ? "true" : "false";
  syncRawPresentationPrivacy();
  const scenarioLabel = SCENARIO_LABELS[selectedScenario];
  document.getElementById("guidedScenario").textContent = scenarioLabel;
  document.getElementById("scenarioStatus").textContent = selectedScenario === "custom"
    ? "ข้อความที่ผู้ใช้กรอกเอง · ตรวจสอบว่าไม่มีข้อมูลจริงที่มีความเสี่ยงสูง"
    : `เลือกแล้ว: ${scenarioLabel}`;
  for (const button of document.querySelectorAll("[data-scenario]")) {
    button.setAttribute("aria-pressed", editor.value.trim() && button.dataset.scenario === selectedScenario ? "true" : "false");
  }
  resetGuidedPresentation(authenticated ? "พร้อมเริ่ม Quick Start ด้วยข้อมูลชุดนี้" : "เข้าสู่ระบบ แล้วกดเริ่มเพื่อเรียก API จริง");
  clearTimeout(debounceTimer);
  syncBusinessControls();
}

editor.addEventListener("input", handleInputChange);
document.getElementById("scanBtn").addEventListener("click", detectNow);

document.querySelectorAll("[data-scenario][data-sample]").forEach(btn => {
  btn.addEventListener("click", () => {
    selectedScenario = btn.dataset.scenario;
    editor.value = btn.dataset.sample;
    handleInputChange({preserveScenario: true});
    if (typeof editor.focus === "function") editor.focus();
  });
});

document.getElementById("safeDemoBtn").addEventListener("click", () => {
  selectedScenario = "hr";
  document.body.dataset.privateInput = "false";
  editor.value = SAFE_AI_DEMO_TEXT;
  handleInputChange({preserveScenario: true});
  document.getElementById("safeElapsed").textContent = "ตัวอย่างสังเคราะห์พร้อมแล้ว กดปกป้องและส่งให้ Safe AI เพื่อเรียก API จริง";
  if (typeof document.getElementById("send").focus === "function") document.getElementById("send").focus();
});

function resetAllDemoState() {
  invalidateBusinessRequests();
  guidedGeneration += 1;
  guidedRunning = false;
  selectedScenario = "hr";
  editor.value = "";
  handleInputChange({preserveScenario: true});
  document.getElementById("guidedScenario").textContent = SCENARIO_LABELS.hr;
  document.getElementById("scenarioStatus").textContent = "ยังไม่ใส่ข้อความ · Quick Start จะใช้ตัวอย่างสมัครงานสังเคราะห์เป็นค่าเริ่มต้น";
  resetGuidedPresentation(authenticated ? "ล้างผลทั้งหมดแล้ว พร้อมเริ่ม Quick Start ใหม่" : "เข้าสู่ระบบ แล้วกดเริ่มเพื่อเรียก API จริง");
  syncBusinessControls();
  if (typeof editor.focus === "function") editor.focus();
}

document.getElementById("resetDemo").addEventListener("click", resetAllDemoState);
document.getElementById("guidedReset").addEventListener("click", resetAllDemoState);

function applyProtectionMode(value) {
  const mode = normalizeProtectionMode(value);
  document.getElementById("mode").value = mode;
  const detail = MODE_DETAILS[mode];
  document.getElementById("modeDescription").textContent = `${detail.label}${mode === "token" ? " — แนะนำ" : ""}: ${detail.description}`;
  document.getElementById("safeMode").textContent = detail.label;
  document.getElementById("guidedMode").textContent = detail.label;
  document.getElementById("systemMode").textContent = detail.label;
  syncModeCards(mode);
  roundtripGeneration += 1;
  guidedGeneration += 1;
  resetSafePresentation("เปลี่ยนรูปแบบการปกป้องแล้ว พร้อมเริ่มคำขอใหม่");
  resetGuidedPresentation(authenticated ? "เลือกรูปแบบแล้ว พร้อมเริ่ม Quick Start" : "เข้าสู่ระบบ แล้วกดเริ่มเพื่อเรียก API จริง");
  syncBusinessControls();
}

document.getElementById("mode").addEventListener("change", event => {
  applyProtectionMode(event.target.value);
});

for (const card of document.querySelectorAll("[data-mode-card]")) {
  card.addEventListener("click", () => applyProtectionMode(card.dataset.modeCard || card.dataset.mode));
}

document.getElementById("presenterModeBtn").addEventListener("click", () => {
  const stage = document.getElementById("presentationStage");
  if (stage.hidden) return;
  const active = document.body.classList.toggle("presenter-mode");
  const button = document.getElementById("presenterModeBtn");
  button.setAttribute("aria-pressed", active ? "true" : "false");
  button.textContent = active ? "ออกจากโหมดนำเสนอ" : "โหมดนำเสนอ";
  syncRawPresentationPrivacy();
  announce(active ? "เปิดโหมดนำเสนอแล้ว" : "ออกจากโหมดนำเสนอแล้ว");
  if (active) {
    const focusEvidence = () => {
      stage.focus({preventScroll: true});
      stage.scrollIntoView({block: "start", behavior: "auto"});
    };
    if (typeof window.requestAnimationFrame === "function") window.requestAnimationFrame(focusEvidence);
    else setTimeout(focusEvidence, 0);
  }
});

document.getElementById("fullscreenBtn").addEventListener("click", async () => {
  const stage = document.getElementById("presentationStage");
  const button = document.getElementById("fullscreenBtn");
  if (stage.hidden) return;
  try {
    if (document.fullscreenElement === stage) {
      await document.exitFullscreen();
    } else if (document.fullscreenEnabled !== false && typeof stage.requestFullscreen === "function") {
      // Remove custom raw/restored values from the DOM before the browser
      // begins its fullscreen transition; a CSS cover alone is not sufficient.
      syncRawPresentationPrivacy(true);
      fullscreenReturnFocus = button;
      await stage.requestFullscreen();
    } else {
      throw new Error("fullscreen unavailable");
    }
  } catch {
    fullscreenReturnFocus = null;
    syncRawPresentationPrivacy();
    announce("เบราว์เซอร์ไม่อนุญาตให้แสดงเต็มจอ ใช้โหมดนำเสนอแทนได้");
    button.focus();
  }
});

document.getElementById("fullscreenExitBtn").addEventListener("click", async () => {
  if (document.fullscreenElement && typeof document.exitFullscreen === "function") {
    try { await document.exitFullscreen(); } catch { announce("ออกจากเต็มจอไม่สำเร็จ กรุณากด Escape"); }
  }
});

document.getElementById("presenterLogoutBtn").addEventListener("click", () => logoutBtn.click());

document.addEventListener("fullscreenchange", syncFullscreenState);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) enforceSessionDeadline();
});
if (typeof window.addEventListener === "function") window.addEventListener("focus", enforceSessionDeadline);

/* ── demo: send roundtrip (provider hard-coded to tokenmind) ── */
function warningLabel(w) {
  if (w && typeof w === "object") return `${w.code} (${w.count})`;
  const m = /^foreign_tokens:(\d+)$/.exec(w);
  if (m) return `โทเคนแปลกปลอม ${m[1]} จุด`;
  return w;
}

function fillEvidence(body) {
  document.getElementById("evidenceSanitized").textContent = body.sanitized_text;
  const wrap = document.getElementById("evidenceWarnings");
  wrap.innerHTML = (body.warnings && body.warnings.length)
    ? body.warnings.map(w => `<span class="chip warn-chip">${esc(warningLabel(w))}</span>`).join("")
    : '<span class="chip ok-chip">ไม่พบคำเตือน</span>';
}

function roundtripIsSafe(body) {
  return Boolean(
    body
    && typeof body.sanitized_text === "string"
    && typeof body.restored_text === "string"
    && body.provider_used === "tokenmind"
    && Number.isInteger(body.detected_entity_count)
    && body.detected_entity_count >= 0
    && body.entity_type_counts
    && typeof body.entity_type_counts === "object"
    && Array.isArray(body.section26_categories)
    && Array.isArray(body.guard_findings)
    && body.safety
    && body.safety.status === "pass"
    && body.safety.residual_count === 0
    && body.restoration
    && body.restoration.status === "complete"
    && body.restoration.leftover_count === 0
    && Array.isArray(body.warnings)
    && body.warnings.length === 0
  );
}

function compareDetectedValues(text, sanitizedText) {
  if (!lastDetection || lastDetection.text !== text || !lastDetection.highlights.length) {
    return {status: "unknown", checked: 0, remaining: 0};
  }
  const values = lastDetection.highlights.map(item => {
    const [start, end] = codePointRangeToUtf16(text, item.start, item.end);
    return text.slice(start, end);
  }).filter(Boolean);
  const remaining = values.filter(value => sanitizedText.includes(value)).length;
  return {status: remaining === 0 ? "pass" : "fail", checked: values.length, remaining};
}

function renderProtectionEvidence(body, text, startedAt, requestedMode) {
  const mode = MODE_DETAILS[normalizeProtectionMode(requestedMode)];
  const proof = compareDetectedValues(text, body.sanitized_text);
  const section26 = body.section26_categories || [];
  document.getElementById("safeMode").textContent = mode.label;
  document.getElementById("safeProvider").textContent = body.provider_used === "tokenmind" ? "Pathumma · thaillm-8b" : body.provider_used;
  document.getElementById("safeResidual").textContent = String(body.safety.residual_count);
  document.getElementById("safeLeftover").textContent = String(body.restoration.leftover_count);
  document.getElementById("safeEvidenceSafety").textContent = body.safety.status === "pass" ? "ผ่าน" : "ระงับ";
  document.getElementById("safeEvidenceRestoration").textContent = body.restoration.status === "complete" ? "สมบูรณ์" : "ระงับ";
  document.getElementById("safeSection26").textContent = section26.length ? section26.map(labelFor).join(" · ") : "ไม่พบธง";
  document.getElementById("safeDuration").textContent = formatElapsed(startedAt);
  if (proof.status === "pass") {
    document.getElementById("proofStatus").textContent = `ตรวจเทียบแล้ว: ไม่พบค่าที่ Privacy Scan ตรวจจับ ${proof.checked} รายการในข้อความที่ส่งให้ AI`;
    document.getElementById("proofMethod").textContent = "เป็นการเปรียบเทียบค่าตรงกันในเบราว์เซอร์กับข้อความปกป้องที่ API คืนมา โดยไม่แสดงข้อมูลจับคู่หรือค่าคู่แทนที่";
    document.getElementById("proofCallout").dataset.tone = "safe";
  } else if (proof.status === "fail") {
    document.getElementById("proofStatus").textContent = "การตรวจเทียบในเบราว์เซอร์ไม่ผ่าน ระบบจึงไม่แสดงผลลัพธ์เป็นความสำเร็จ";
    document.getElementById("proofMethod").textContent = `ยังพบค่าที่ตรวจจับ ${proof.remaining} รายการใน sanitized_text`;
    document.getElementById("proofCallout").dataset.tone = "error";
  } else {
    document.getElementById("proofStatus").textContent = "แสดงข้อความปกป้องที่ API ส่งต่อให้ provider แล้ว";
    document.getElementById("proofMethod").textContent = "รัน Privacy Scan ก่อน Safe AI หรือใช้ Quick Start เพื่อเพิ่มการตรวจเทียบค่าที่ตรวจจับในเบราว์เซอร์";
    document.getElementById("proofCallout").dataset.tone = "safe";
  }
  return proof;
}

function beginSafeProgress(startedAt, generation) {
  const messages = [
    "ตรวจหาข้อมูลส่วนบุคคล",
    "ปกป้องข้อมูลสำคัญ",
    "ส่งเฉพาะข้อความที่ปกป้องแล้ว",
    "ตรวจคำตอบจากโมเดล",
    "กู้คืนบริบทที่ผ่านการตรวจ",
  ];
  const panel = document.getElementById("safeProgress");
  const status = document.getElementById("safeElapsed");
  panel.hidden = false;
  let current = 0;
  const advance = () => {
    if (generation !== roundtripGeneration) return;
    for (let index = 0; index < messages.length; index += 1) {
      document.getElementById("safeStage" + index).dataset.state = index === current ? "active" : "idle";
    }
    const elapsed = ((monotonicNow() - startedAt) / 1000).toFixed(1);
    status.textContent = `กำลังดำเนินการ ${elapsed} วินาที · ลำดับโดยประมาณ: ${messages[current]}`;
    status.dataset.tone = "";
    current = Math.min(current + 1, messages.length - 1);
    safeProgressTimer = setTimeout(advance, 1400);
  };
  advance();
}

function finishSafeProgress(success) {
  clearTimeout(safeProgressTimer);
  safeProgressTimer = null;
  const panel = document.getElementById("safeProgress");
  panel.hidden = !success;
  for (let index = 0; index < 5; index += 1) {
    document.getElementById("safeStage" + index).dataset.state = success ? "done" : "idle";
  }
}

async function runSafeAI() {
  const text = editor.value;
  const safeElapsed = document.getElementById("safeElapsed");
  if (!text.trim()) {
    safeElapsed.textContent = "กรุณาใส่ข้อความหรือเลือกตัวอย่างก่อนเริ่ม Safe AI";
    safeElapsed.dataset.tone = "caution";
    return false;
  }
  if (!authenticated) return false;
  if (providerLaneActive) {
    safeElapsed.textContent = "Safe AI มีคำขอก่อนหน้าที่ยังไม่ยืนยันว่าจบแล้ว กรุณารอเพื่อป้องกันการส่งซ้ำ";
    safeElapsed.dataset.tone = "caution";
    announce("ยังเริ่ม Safe AI ซ้ำไม่ได้ กรุณารอคำขอก่อนหน้า");
    return false;
  }
  if (!acquireProviderLane()) return false;
  const generation = ++roundtripGeneration;
  const startedAt = monotonicNow();
  const requestedMode = selectedProtectionMode();
  const btn = document.getElementById("send");
  const masked = document.getElementById("masked");
  const restored = document.getElementById("restored");
  const tag = document.getElementById("providerTag");
  resetSafePresentation();
  btn.disabled = true;
  document.getElementById("mode").disabled = true;
  tag.hidden = true;
  tag.textContent = "";
  masked.textContent = "กำลังเตรียมข้อความที่ปกป้องแล้ว...";
  restored.textContent = "ระบบจะแสดงผลเมื่อผ่านการตรวจครบ";
  masked.dataset.filled = "false";
  restored.dataset.filled = "false";
  masked.dataset.tone = "";
  restored.dataset.tone = "";
  document.getElementById("safeCount").textContent = "…";
  document.getElementById("safeTypes").textContent = "…";
  document.getElementById("safeTypeLabels").textContent = "กำลังสรุปประเภท";
  document.getElementById("safeProtection").textContent = "กำลังตรวจ";
  document.getElementById("safeRestoration").textContent = "รอผล";
  document.getElementById("safeMode").textContent = MODE_DETAILS[requestedMode].label;
  document.getElementById("safeDuration").textContent = "กำลังวัด";
  document.getElementById("safeAnnouncement").textContent = "เริ่ม Safe AI แล้ว ระบบกำลังปกป้องและประมวลผลข้อความ";
  beginSafeProgress(startedAt, generation);
  try {
    const {r, body} = await apiJson("/api/roundtrip", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text, mode: requestedMode, provider: "tokenmind"}),
    });
    if (generation !== roundtripGeneration || text !== editor.value) return false;
    if (!r.ok) {
      finishSafeProgress(false);
      masked.textContent = "ไม่มีข้อความถูกส่งสำเร็จในคำขอนี้";
      restored.textContent = "ไม่มีผลลัพธ์ให้แสดง";
      masked.dataset.tone = "error";
      restored.dataset.tone = "error";
      document.getElementById("safeCount").textContent = "—";
      document.getElementById("safeTypes").textContent = "—";
      document.getElementById("safeTypeLabels").textContent = "ยังไม่มีข้อมูล";
      document.getElementById("safeProtection").textContent = "ไม่สำเร็จ";
      document.getElementById("safeRestoration").textContent = "ไม่เริ่ม";
      document.getElementById("safeProvider").textContent = "ไม่ส่งสำเร็จ";
      document.getElementById("safeResidual").textContent = "—";
      document.getElementById("safeLeftover").textContent = "—";
      document.getElementById("safeEvidenceSafety").textContent = "ไม่สำเร็จ";
      document.getElementById("safeEvidenceRestoration").textContent = "ไม่เริ่ม";
      document.getElementById("safeSection26").textContent = "—";
      document.getElementById("safeDuration").textContent = formatElapsed(startedAt);
      document.getElementById("proofStatus").textContent = "ไม่มีหลักฐานใหม่จากคำขอนี้";
      document.getElementById("proofMethod").textContent = "ผลเดิมถูกล้างก่อนเริ่ม และระบบไม่แสดง response ภายในเมื่อคำขอไม่สำเร็จ";
      document.getElementById("proofCallout").dataset.tone = "error";
      safeElapsed.textContent = `${errorMessage(r.status, detailText(body), "text")} · ${formatElapsed(startedAt)}`;
      safeElapsed.dataset.tone = "error";
      document.getElementById("safeAnnouncement").textContent = "Safe AI ไม่สำเร็จ ระบบไม่แสดงผลลัพธ์";
      document.getElementById("evidenceWarnings").textContent = "คำขอหยุดโดยไม่แสดงข้อมูลภายในหรือคำตอบดิบ";
      return false;
    }
    masked.textContent = body.sanitized_text;
    masked.dataset.filled = "true";
    tag.textContent = body.provider_used === "tokenmind" ? "Pathumma · thaillm-8b" : (body.provider_used || "Pathumma · thaillm-8b");
    tag.hidden = false;
    const typeEntries = Object.entries(body.entity_type_counts || {});
    document.getElementById("safeCount").textContent = String(body.detected_entity_count);
    document.getElementById("safeTypes").textContent = String(typeEntries.length);
    document.getElementById("safeTypeLabels").textContent = typeEntries.length
      ? typeEntries.map(([type]) => labelFor(type)).join(" · ")
      : "ไม่พบข้อมูลส่วนบุคคล";
    document.getElementById("safeProtection").textContent = body.safety && body.safety.status === "pass" ? "ผ่าน" : "ระงับ";
    const browserProof = renderProtectionEvidence(body, text, startedAt, requestedMode);
    if (!roundtripIsSafe(body) || browserProof.status === "fail") {
      finishSafeProgress(false);
      restored.textContent = "ระบบระงับคำตอบที่กู้คืนไม่สมบูรณ์หรือมีคำเตือน";
      restored.dataset.filled = "false";
      restored.dataset.tone = "error";
      document.getElementById("safeRestoration").textContent = "ระงับ";
      fillEvidence(body);
      const section26 = (body.section26_categories || []).length
        ? ` · หมวดข้อมูลอ่อนไหวตามมาตรา 26: ${body.section26_categories.map(labelFor).join(", ")}`
        : "";
      safeElapsed.textContent = `ระงับผลหลัง ${formatElapsed(startedAt)} · ไม่แสดงคำตอบจนกว่าสถานะความปลอดภัยและการกู้คืนจะผ่านครบ${section26}`;
      safeElapsed.dataset.tone = "error";
      document.getElementById("safeAnnouncement").textContent = "Safe AI ระงับผลลัพธ์ที่ไม่ผ่านการตรวจความปลอดภัย";
      return false;
    }
    finishSafeProgress(true);
    restored.textContent = body.restored_text;
    restored.dataset.filled = "true";
    restored.dataset.tone = "";
    document.getElementById("safeRestoration").textContent = "สมบูรณ์";
    fillEvidence(body);
    const duration = formatElapsed(startedAt);
    const guardFindings = Array.isArray(body.guard_findings)
      ? body.guard_findings.map(item => ({category: item.category, severity: item.severity}))
      : [];
    lastRoundtrip = {
      text,
      mode: requestedMode,
      providerUsed: body.provider_used,
      section26Categories: [...(body.section26_categories || [])],
      detectedEntityCount: body.detected_entity_count,
      entityTypeCounts: {...(body.entity_type_counts || {})},
      residualCount: body.safety.residual_count,
      leftoverCount: body.restoration.leftover_count,
      sanitizedText: body.sanitized_text,
      duration,
      guardFindings,
    };
    lastGuard = {text, available: true, findings: guardFindings};
    renderSensitiveDataMap(
      text,
      lastRoundtrip.entityTypeCounts,
      lastDetection && lastDetection.text === text ? lastDetection.highlights : [],
    );
    renderGuardRisk(guardFindings, true);
    renderRawProtectedComparison(text, body.sanitized_text, browserProof);
    renderProtectionReceipt(lastRoundtrip);
    presentationRestoredText = body.restored_text;
    document.getElementById("executiveRestored").textContent = presentationRestoredText;
    document.getElementById("executiveRestoredCard").hidden = false;
    syncRawPresentationPrivacy();
    updateExecutiveSummary();
    const section26 = (body.section26_categories || []).length
      ? ` · หมวดข้อมูลอ่อนไหวตามมาตรา 26: ${body.section26_categories.map(labelFor).join(", ")}`
      : " · ไม่พบหมวดข้อมูลอ่อนไหวตามมาตรา 26";
    safeElapsed.textContent = `ปกป้องสำเร็จใน ${formatElapsed(startedAt)} · การปกป้องและการกู้คืนผ่านครบ${section26}`;
    safeElapsed.dataset.tone = "safe";
    document.getElementById("safeAnnouncement").textContent = "Safe AI สำเร็จ การปกป้องและการกู้คืนผ่านครบ";
    return true;
  } catch (err) {
    if (isStaleBusinessError(err)) return false;
    if (generation !== roundtripGeneration || text !== editor.value) return false;
    finishSafeProgress(false);
    masked.textContent = "ไม่มีข้อความถูกส่งสำเร็จในคำขอนี้";
    restored.textContent = "ไม่มีผลลัพธ์ให้แสดง";
    masked.dataset.filled = "false";
    restored.dataset.filled = "false";
    masked.dataset.tone = "error";
    restored.dataset.tone = "error";
    document.getElementById("safeCount").textContent = "—";
    document.getElementById("safeTypes").textContent = "—";
    document.getElementById("safeTypeLabels").textContent = "ยังไม่มีข้อมูล";
    document.getElementById("safeProtection").textContent = "ไม่สำเร็จ";
    document.getElementById("safeRestoration").textContent = "ไม่เริ่ม";
    document.getElementById("safeProvider").textContent = "เชื่อมต่อไม่ได้";
    document.getElementById("safeResidual").textContent = "—";
    document.getElementById("safeLeftover").textContent = "—";
    document.getElementById("safeEvidenceSafety").textContent = "ไม่สำเร็จ";
    document.getElementById("safeEvidenceRestoration").textContent = "ไม่เริ่ม";
    document.getElementById("safeSection26").textContent = "—";
    document.getElementById("safeDuration").textContent = formatElapsed(startedAt);
    document.getElementById("proofStatus").textContent = "ไม่มีหลักฐานใหม่จากคำขอนี้";
    document.getElementById("proofMethod").textContent = "เชื่อมต่อแพลตฟอร์มไม่ได้ และผลเดิมถูกล้างแล้ว";
    document.getElementById("proofCallout").dataset.tone = "error";
    document.getElementById("evidenceSanitized").textContent = "ยังไม่มีข้อมูล";
    document.getElementById("evidenceWarnings").textContent = "คำขอไม่สำเร็จโดยไม่แสดงข้อมูลภายใน";
    safeElapsed.textContent = providerLaneActive
      ? `การเชื่อมต่อขาดหายและคำขอก่อนหน้าอาจยังทำงานอยู่ · ระบบพักการส่งซ้ำชั่วคราว · ${formatElapsed(startedAt)}`
      : `เชื่อมต่อแพลตฟอร์มไม่ได้ กรุณาลองใหม่ · ${formatElapsed(startedAt)}`;
    safeElapsed.dataset.tone = "error";
    document.getElementById("safeAnnouncement").textContent = "Safe AI เชื่อมต่อแพลตฟอร์มไม่สำเร็จ";
    return false;
  } finally {
    if (generation === roundtripGeneration) {
      syncBusinessControls();
    }
  }
}

document.getElementById("send").addEventListener("click", runSafeAI);

async function runGuidedDemo() {
  if (!authenticated || guidedRunning) return false;
  if (providerLaneActive) {
    document.getElementById("guidedStatus").textContent = "ยังเริ่ม Quick Start ไม่ได้ เพราะ Safe AI คำขอก่อนหน้ายังไม่ยืนยันว่าจบแล้ว";
    document.getElementById("guidedStatus").dataset.tone = "caution";
    return false;
  }
  // Guided owns local-only request state. A provider-bound request is never
  // aborted-and-replaced because browser cancellation cannot prove server stop.
  invalidateBusinessRequests();
  if (!editor.value.trim()) {
    selectedScenario = "hr";
    editor.value = SAFE_AI_DEMO_TEXT;
    handleInputChange({preserveScenario: true});
  } else {
    handleInputChange({preserveScenario: true});
  }

  const generation = ++guidedGeneration;
  const startedAt = monotonicNow();
  guidedRunning = true;
  syncBusinessControls();
  document.getElementById("guidedStatus").textContent = "กำลังเริ่ม Privacy Scan ด้วยข้อความสังเคราะห์ที่เลือก";
  document.getElementById("guidedStatus").dataset.tone = "";
  document.getElementById("guidedMode").textContent = MODE_DETAILS[selectedProtectionMode()].label;
  document.getElementById("guidedTiming").textContent = "กำลังวัด";
  setGuidedStep("scan", "active", "กำลังสแกน");

  let completed = false;
  try {
    const scanPassed = await detectNow();
    if (generation !== guidedGeneration || !guidedRunning) return false;
    if (!scanPassed) {
      const scanActuallyPassed = lastDetection && lastDetection.text === editor.value;
      setGuidedStep("scan", scanActuallyPassed ? "done" : "error", scanActuallyPassed ? "สแกนผ่าน" : "ไม่สำเร็จ");
      if (scanActuallyPassed && lastGuard && !lastGuard.available) {
        setGuidedStep("safe", "error", "Guard ไม่พร้อม");
      }
      document.getElementById("guidedSafety").textContent = "หยุดอย่างปลอดภัย";
      document.getElementById("guidedStatus").textContent = scanActuallyPassed
        ? "Privacy Scan ผ่าน แต่ Guard ไม่พร้อม · หยุดก่อนเรียก Safe AI โดยไม่สร้างผลสำเร็จจำลอง"
        : "Quick Start หยุดที่ Privacy Scan · แก้ไขตามข้อความแจ้งเตือนแล้วกดลองใหม่";
      document.getElementById("guidedStatus").dataset.tone = "error";
      return false;
    }

    setGuidedStep("scan", "done", "ผ่าน");
    document.getElementById("guidedPii").textContent = String(lastDetection.detectedEntityCount);
    setGuidedStep("safe", "active", "กำลังปกป้อง");
    document.getElementById("guidedStatus").textContent = "Privacy Scan ผ่าน · กำลังเรียก Safe AI หนึ่งครั้ง";
    const safePassed = await runSafeAI();
    if (generation !== guidedGeneration || !guidedRunning) return false;
    if (!safePassed) {
      setGuidedStep("safe", "error", "ถูกระงับ");
      document.getElementById("guidedSafety").textContent = "หยุดอย่างปลอดภัย";
      document.getElementById("guidedStatus").textContent = "Quick Start หยุดที่ Safe AI · ระบบไม่แสดงขั้นรายงานเป็นความสำเร็จ";
      document.getElementById("guidedStatus").dataset.tone = "error";
      return false;
    }

    setGuidedStep("safe", "done", "ผ่าน");
    document.getElementById("guidedSafety").textContent = "ผ่านครบ";
    document.getElementById("guidedMode").textContent = MODE_DETAILS[lastRoundtrip.mode].label;
    setGuidedStep("report", "active", "กำลังสร้าง");
    document.getElementById("guidedStatus").textContent = "Safe AI ผ่าน · กำลังสร้าง PDPA Report จากข้อความเดียวกัน";
    const reportPassed = await generateReport();
    if (generation !== guidedGeneration || !guidedRunning) return false;
    if (!reportPassed) {
      setGuidedStep("report", "error", "ไม่สำเร็จ");
      document.getElementById("guidedStatus").textContent = "Safe AI ผ่าน แต่ PDPA Report ไม่สำเร็จ · ผลก่อนหน้ายังคงแยกสถานะอย่างชัดเจน";
      document.getElementById("guidedStatus").dataset.tone = "error";
      return false;
    }

    setGuidedStep("report", "done", "พร้อม");
    document.getElementById("guidedTiming").textContent = formatElapsed(startedAt);
    document.getElementById("guidedStatus").textContent = "Quick Start สำเร็จครบ 3 เวิร์กโฟลว์ · เลื่อนดูข้อความที่ส่งให้ AI จริงและสรุปรายงานได้เลย";
    document.getElementById("guidedStatus").dataset.tone = "safe";
    document.getElementById("guidedProofLink").hidden = false;
    completed = true;
    return true;
  } catch {
    if (generation !== guidedGeneration) return false;
    document.getElementById("guidedStatus").textContent = "Quick Start หยุดอย่างปลอดภัยจากปัญหาการเชื่อมต่อ กรุณาลองใหม่";
    document.getElementById("guidedStatus").dataset.tone = "error";
    return false;
  } finally {
    if (generation === guidedGeneration) {
      guidedRunning = false;
      document.getElementById("guidedTiming").textContent = formatElapsed(startedAt);
      if (!completed && document.getElementById("guidedSafety").textContent === "รอผล") {
        document.getElementById("guidedSafety").textContent = "ไม่สำเร็จ";
      }
      syncBusinessControls();
    }
  }
}

document.getElementById("guidedStart").addEventListener("click", runGuidedDemo);

/* ── PDPA report: inspect server summary before volatile download ── */
function validReportPayload(report) {
  if (
    !report
    || typeof report.overall_score !== "number"
    || !Number.isFinite(report.overall_score)
    || report.overall_score < 0
    || report.overall_score > 100
    || !["A", "B", "C", "D", "F"].includes(report.overall_grade)
    || typeof report.report_pdf_b64 !== "string"
    || !report.report_pdf_b64
  ) return false;
  try {
    return atob(report.report_pdf_b64).slice(0, 5) === "%PDF-";
  } catch {
    return false;
  }
}

async function generateReport() {
  const text = editor.value;
  const reportMeta = document.getElementById("reportMeta");
  if (!text.trim()) {
    reportMeta.textContent = "กรุณาใส่ข้อความใน Privacy Scan ก่อน";
    reportMeta.dataset.tone = "caution";
    return false;
  }
  if (!authenticated) return false;
  const generation = ++reportGeneration;
  const startedAt = monotonicNow();
  const btn = document.getElementById("reportBtn");
  resetReportPresentation();
  btn.disabled = true;
  document.getElementById("reportScope").textContent = "กำลังสร้างรายงาน";
  reportMeta.textContent = "กำลังวิเคราะห์คะแนนและสร้างรายงานภาษาไทย...";
  reportMeta.dataset.tone = "";
  document.getElementById("reportTiming").textContent = "กำลังวัดเวลาคำขอ /analyze-report ในเบราว์เซอร์";
  try {
    const {r: reportResponse, body: report} = await apiJson("/api/analyze-report", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text}),
    });
    if (generation !== reportGeneration || text !== editor.value) return false;
    if (!reportResponse.ok) {
      document.getElementById("reportScope").textContent = "ยังไม่มีรายงาน";
      reportMeta.textContent = errorMessage(reportResponse.status, detailText(report), "text");
      reportMeta.dataset.tone = "error";
      document.getElementById("reportTiming").textContent = `คำขอไม่สำเร็จหลัง ${formatElapsed(startedAt)}`;
      return false;
    }
    if (!validReportPayload(report)) {
      document.getElementById("reportScope").textContent = "รายงานถูกระงับ";
      reportMeta.textContent = "ระบบระงับรายงานที่ตรวจสอบรูปแบบไม่ได้ กรุณาลองใหม่";
      reportMeta.dataset.tone = "error";
      document.getElementById("reportTiming").textContent = `ระงับผลหลัง ${formatElapsed(startedAt)}`;
      return false;
    }
    document.getElementById("reportScore").textContent = String(report.overall_score);
    document.getElementById("reportGrade").textContent = String(report.overall_grade);
    document.getElementById("reportScope").textContent = "พร้อม";
    preparedReport = report.report_pdf_b64;
    lastReport = {text, score: report.overall_score, grade: report.overall_grade};
    document.getElementById("reportDownloadBtn").hidden = false;
    if (lastDetection && lastDetection.text === text) {
      const labels = Object.keys(lastDetection.entityTypeCounts).map(labelFor);
      document.getElementById("reportCategories").textContent = labels.length
        ? `บริบทจาก Privacy Scan ของข้อความเดียวกัน: ${lastDetection.detectedEntityCount} รายการ · ${labels.join(" · ")}`
        : "Privacy Scan ของข้อความเดียวกันไม่พบข้อมูลส่วนบุคคล";
    } else {
      document.getElementById("reportCategories").textContent = "รายงาน endpoint ส่งกลับเฉพาะคะแนนและเกรด · รัน Privacy Scan เพื่อดูประเภทของข้อความเดียวกัน";
    }
    reportMeta.textContent = `รายงานพร้อมดาวน์โหลด · คะแนน ${report.overall_score} · เกรด ${report.overall_grade}`;
    reportMeta.dataset.tone = "safe";
    document.getElementById("reportTiming").textContent = `PDPA Report /analyze-report · เวลารวมที่วัดในเบราว์เซอร์ ${formatElapsed(startedAt)}`;
    updateExecutiveSummary();
    return true;
  } catch (err) {
    if (isStaleBusinessError(err)) return false;
    if (generation !== reportGeneration || text !== editor.value) return false;
    document.getElementById("reportScope").textContent = "ยังไม่มีรายงาน";
    reportMeta.textContent = "เชื่อมต่อแพลตฟอร์มไม่ได้ กรุณาลองใหม่";
    reportMeta.dataset.tone = "error";
    document.getElementById("reportTiming").textContent = `เชื่อมต่อไม่สำเร็จหลัง ${formatElapsed(startedAt)}`;
    return false;
  } finally {
    if (generation === reportGeneration) btn.disabled = !authenticated || guidedRunning;
  }
}

document.getElementById("reportBtn").addEventListener("click", generateReport);

document.getElementById("reportDownloadBtn").addEventListener("click", () => {
  if (!authenticated || !preparedReport) return;
  downloadB64(preparedReport, "ai-guard-pdpa-report.pdf", "application/pdf");
  document.getElementById("reportMeta").textContent = "ดาวน์โหลดรายงานแล้ว · ไฟล์ยังพร้อมให้ดาวน์โหลดซ้ำจนกว่าจะเปลี่ยนข้อความหรือออกจากระบบ";
});

async function checkServiceHealth() {
  const status = document.getElementById("serviceStatus");
  const version = document.getElementById("serviceVersion");
  try {
    const response = await fetch("/api/health", {credentials: "same-origin"});
    const body = await safeJson(response);
    if (response.ok && body.status === "ok" && typeof body.version === "string" && body.version) {
      status.textContent = "ออนไลน์ · บริการตอบสนอง";
      status.dataset.tone = "safe";
      version.textContent = body.version;
      return;
    }
  } catch {
    /* fixed state below; never render a raw response or exception */
  }
  status.textContent = "ตรวจสถานะบริการไม่สำเร็จ";
  status.dataset.tone = "error";
  version.textContent = "—";
}

syncModeCards("token");
syncFullscreenState();
document.getElementById("appControls").inert = false;
document.getElementById("appControls").removeAttribute("inert");
document.getElementById("appBootstrapNotice").hidden = true;
if (pendingWorkflowAnchor && typeof history !== "undefined" && typeof history.replaceState === "function") {
  holdWorkflowUntilAuthenticated(pendingWorkflowAnchor);
}
setAuthState(false, "กำลังตรวจสอบสิทธิ์...");
checkAuthSession();
checkServiceHealth();
