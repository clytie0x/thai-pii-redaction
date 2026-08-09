#!/usr/bin/env node
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import {fileURLToPath} from "node:url";

const repo = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const page = fs.readFileSync(path.join(repo, "web", "index.html"), "utf8");
for (const forbidden of ["redact-pdf", "pdfFile", "pdfPick", "pdfDownload", "after_png_b64"]) {
  assert.ok(!page.includes(forbidden), `public PDF execution path remains: ${forbidden}`);
}
for (const workflow of ['id="privacy-scan"', 'id="safe-ai"', 'id="pdpa-report"']) {
  assert.ok(page.includes(workflow), `public workflow is missing: ${workflow}`);
}
for (const guidedMarker of [
  'id="guided-demo"',
  'id="guidedStart"',
  'id="guidedReset"',
  'id="guidedStepScan"',
  'id="guidedStepSafe"',
  'id="guidedStepReport"',
  'id="guidedProofLink"',
  'id="protectionEvidence"',
  'id="proofStatus"',
  'id="systemEvidence"',
]) {
  assert.ok(page.includes(guidedMarker), `Guided Demo contract missing: ${guidedMarker}`);
}
assert.ok(page.includes("ข้อความที่ AI Guard ส่งต่อหลังปกป้องและตรวจซ้ำ"), "Safe AI does not label sanitized provider input");
assert.ok(page.includes("ข้อความที่ส่งให้ AI จริง"), "Safe AI proof card is not judge-readable");
assert.ok(page.includes('href="#providerEvidenceCard"'), "Guided proof jump does not target the complete evidence card");
assert.ok(page.includes("scroll-margin-top:140px"), "sticky navigation can obscure the Safe AI proof target");
assert.ok(page.includes('<main id="main-content" tabindex="-1">'), "skip-link target is not programmatically focusable");
assert.ok(page.includes("body.sanitized_text"), "Safe AI does not render the sanitized text");
assert.equal((page.match(/data-sample=/g) || []).length, 5, "demo does not expose exactly five synthetic presets");
assert.equal((page.match(/data-scenario=/g) || []).length, 5, "scenario gallery does not expose exactly five scenarios");
for (const match of page.matchAll(/data-sample="([^"]+)"/g)) {
  assert.match(match[1], /กรุณา/, "synthetic scenario lacks a deterministic AI task");
}
for (const scenario of ["HR", "Healthcare", "Education", "Customer Service", "Government"]) {
  assert.ok(page.includes(scenario), `scenario context missing: ${scenario}`);
}
assert.ok(page.includes("เวลารวมที่วัดในเบราว์เซอร์"), "browser-total timing is not labelled honestly");
assert.ok(page.includes("ไม่ใช่เวลารายขั้นจากเซิร์ฟเวอร์"), "approximate progress is not distinguished from telemetry");
assert.ok(page.includes("ไม่มีการ fallback ไป provider อื่น"), "fail-closed provider trust claim is missing");
assert.ok(page.includes("การลบ PII ใน PDF/OCR แบบสาธารณะ: ปิด"), "system evidence does not show the PDF quarantine");
assert.ok(page.includes("monotonicNow()"), "browser timing does not use the monotonic clock helper");
assert.ok(!page.includes('index < current ? "done"'), "approximate stages falsely claim server-side completion");
assert.ok(!page.includes("Leftover mappings"), "leftover tokens are mislabelled as mappings");
assert.ok(!page.includes("โทเคนทึบ"), "type-labelled token placeholders are described as opaque");
for (const ownershipGuard of [
  "if (generation === detectGeneration) scanBtn.disabled",
  "if (generation === roundtripGeneration)",
  "if (generation === reportGeneration) btn.disabled",
]) {
  assert.ok(page.includes(ownershipGuard), `stale request finalizer lacks ownership guard: ${ownershipGuard}`);
}
for (const marker of [
  'id="scanBtn"',
  'id="resetDemo"',
  'id="safeDemoBtn"',
  'id="reportDownloadBtn"',
  "ข้อความแสดงลำดับโดยประมาณ",
  "prefers-reduced-motion",
  "--canvas:#f4f7fb",
]) {
  assert.ok(page.includes(marker), `competition UX contract missing: ${marker}`);
}
assert.ok(
  page.indexOf("preparedReport = report.report_pdf_b64") < page.indexOf('downloadB64(preparedReport'),
  "PDPA report is not reviewed before explicit download",
);
assert.ok(!page.includes("body.ai_response_masked"), "masked provider response leaked into the frontend");
assert.ok(!/localStorage|sessionStorage/.test(page), "frontend persists sensitive state in browser storage");
assert.ok(!/<script[^>]+src=|<link[^>]+href=["']https?:/i.test(page), "third-party frontend dependency was added");
const scripts = [...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match => match[1]);
const source = scripts.find(script => script.includes("same-origin caller authentication"));
assert.ok(source, "frontend application script is missing");

class FakeElement {
  constructor(id) {
    this.id = id;
    this.hidden = false;
    this.disabled = false;
    this.value = "";
    this.files = [];
    this.dataset = {};
    this.src = "";
    this.scrollTop = 0;
    this.scrollLeft = 0;
    this.listeners = new Map();
    this._textContent = "";
    this._innerHTML = "";
  }

  get textContent() {
    return this._textContent;
  }

  set textContent(value) {
    this._textContent = String(value);
    this._innerHTML = String(value);
  }

  get innerHTML() {
    return this._innerHTML;
  }

  set innerHTML(value) {
    this._innerHTML = String(value);
    this._textContent = String(value).replace(/<[^>]*>/g, "");
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  async emit(type, event = {}) {
    const results = (this.listeners.get(type) || []).map(listener =>
      listener({target: this, ...event})
    );
    await Promise.all(results);
  }

  click() {
    return this.emit("click");
  }

  removeAttribute(name) {
    if (name === "src") this.src = "";
  }

  setAttribute(name, value) {
    if (name === "aria-pressed") this.ariaPressed = String(value);
  }

  focus() {
    this.focused = true;
  }
}

const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, new FakeElement(id));
  return elements.get(id);
};
element("mode").value = "token";
const scenarioButtons = [...page.matchAll(/<button class="scenario-card"[^>]*data-scenario="([^"]+)"[^>]*data-sample="([^"]+)"/g)]
  .map(match => {
    const button = element(`scenario-${match[1]}`);
    button.dataset.scenario = match[1];
    button.dataset.sample = match[2];
    return button;
  });
const downloads = [];
const document = {
  getElementById: element,
  querySelectorAll: selector => selector.includes("data-scenario") ? scenarioButtons : [],
  createElement: tag => {
    assert.equal(tag, "a");
    return {
      href: "",
      download: "",
      click() {
        downloads.push({href: this.href, name: this.download});
      },
    };
  },
};

const response = (status, body = {}) => ({
  status,
  ok: status >= 200 && status < 300,
  async json() {
    return body;
  },
});
const deferred = () => {
  let resolve;
  const promise = new Promise(done => {
    resolve = done;
  });
  return {promise, resolve};
};

let roundtripMode = "deferred";
let slowRoundtrip = deferred();
let roundtripBody = null;
let roundtripCalls = 0;
const roundtripRequests = [];
let slowDetect = deferred();
let detectMode = "deferred";
let detectBody = null;
let detectCalls = 0;
let guardCalls = 0;
let guardMode = "success";
let guardBody = {flagged: false, guard_findings: []};
let analyzeReportCalls = 0;
let reportMode = "success";
let slowReport = deferred();
let abortedRoundtripCalls = 0;
const requestOrder = [];
const initialSession = deferred();
let sessionCalls = 0;
let loginCalls = 0;
let logoutMode = "success";
let slowLogout = null;
const abortable = (promise, signal, onAbort = () => {}) => {
  if (!signal) return promise;
  if (signal.aborted) {
    onAbort();
    const error = new Error("aborted");
    error.name = "AbortError";
    return Promise.reject(error);
  }
  return new Promise((resolve, reject) => {
    const abort = () => {
      onAbort();
      const error = new Error("aborted");
      error.name = "AbortError";
      reject(error);
    };
    signal.addEventListener("abort", abort, {once: true});
    promise.then(
      value => {
        signal.removeEventListener("abort", abort);
        resolve(value);
      },
      error => {
        signal.removeEventListener("abort", abort);
        reject(error);
      },
    );
  });
};
const fetch = (url, _options = {}) => {
  if (url === "/api/health") {
    return Promise.resolve(response(200, {status: "ok", version: "2.5.0", contract_version: 2}));
  }
  if (url === "/api/auth/session") {
    sessionCalls += 1;
    if (sessionCalls === 1) return initialSession.promise;
    return Promise.resolve(response(200, {authenticated: true, expires_in: 1800}));
  }
  if (url === "/api/auth/login") {
    loginCalls += 1;
    return Promise.resolve(response(204));
  }
  if (url === "/api/auth/logout") {
    if (logoutMode === "slow") return slowLogout.promise;
    if (logoutMode === "http-error") return Promise.resolve(response(500));
    if (logoutMode === "network-error") return Promise.reject(new Error("network down"));
    return Promise.resolve(response(204));
  }
  if (url === "/api/roundtrip") {
    roundtripCalls += 1;
    requestOrder.push(url);
    roundtripRequests.push(JSON.parse(_options.body));
    if (roundtripMode === "deferred") {
      return abortable(slowRoundtrip.promise, _options.signal, () => { abortedRoundtripCalls += 1; });
    }
    if (roundtripMode === "body") return Promise.resolve(response(200, roundtripBody));
    if (roundtripMode === "unauthorized") {
      return Promise.resolve(response(401, {error: {code: "authentication_required"}}));
    }
  }
  if (url === "/api/detect") {
    detectCalls += 1;
    requestOrder.push(url);
    if (detectMode === "body") return Promise.resolve(response(200, detectBody));
    if (detectMode === "error") return Promise.resolve(response(503, {error: {code: "service_unavailable"}}));
    return slowDetect.promise;
  }
  if (url === "/api/guard") {
    guardCalls += 1;
    requestOrder.push(url);
    if (guardMode === "error") return Promise.resolve(response(503, {error: {code: "service_unavailable"}}));
    if (guardMode === "network-error") return Promise.reject(new Error("guard network down"));
    return Promise.resolve(response(200, guardBody));
  }
  if (url === "/api/analyze-report") {
    analyzeReportCalls += 1;
    requestOrder.push(url);
    if (reportMode === "error") return Promise.resolve(response(503, {error: {code: "service_unavailable"}}));
    if (reportMode === "malformed") return Promise.resolve(response(200, {}));
    if (reportMode === "deferred") return abortable(slowReport.promise, _options.signal);
    return Promise.resolve(response(200, {
      report_pdf_b64: "JVBERi0xLjQ=",
      overall_score: 68,
      overall_grade: "D",
    }));
  }
  throw new Error(`unexpected fetch: ${url}`);
};

const context = vm.createContext({
  AbortController,
  Array,
  Blob,
  JSON,
  Math,
  Number,
  Object,
  Promise,
  String,
  Uint8Array,
  URL,
  atob,
  clearTimeout,
  console,
  document,
  fetch,
  setTimeout,
});
vm.runInContext(source, context, {filename: "web/index.html"});

const flush = () => new Promise(resolve => setImmediate(resolve));
await flush();
assert.equal(sessionCalls, 1, "initial session check did not start");
assert.equal(element("send").disabled, true, "business controls enabled before auth completed");
assert.equal(element("scanBtn").disabled, true, "Privacy Scan enabled before auth completed");
assert.equal(element("guidedStart").disabled, true, "Guided Demo enabled before auth completed");
assert.equal(element("serviceStatus").textContent, "ออนไลน์ · บริการตอบสนอง", "public health was not normalized into system evidence");
assert.equal(element("serviceVersion").textContent, "2.5.0", "health version was not shown safely");

element("accessCode").value = "synthetic-access-code";
await element("loginBtn").emit("click");
assert.equal(sessionCalls, 2, "login did not start a fresh session check");
assert.equal(element("send").disabled, false, "successful login did not enable business controls");
assert.equal(element("scanBtn").disabled, false, "successful login did not enable Privacy Scan");
assert.equal(element("guidedStart").disabled, false, "successful login did not enable Guided Demo");

initialSession.resolve(response(401, {authenticated: false}));
await flush();
await flush();
assert.equal(
  element("send").disabled,
  false,
  "stale initial session response cleared a newer successful login",
);
await element("safeDemoBtn").emit("click");
assert.match(element("editor").value, /ใบสมัครงานสังเคราะห์/, "Safe AI quick start did not supply synthetic input");
assert.match(element("safeElapsed").textContent, /เรียก API จริง/, "Safe AI quick start did not explain the next real call");
await element("resetDemo").emit("click");
assert.equal(element("editor").value, "", "one-click reset did not clear the Safe AI example");
vm.runInContext(
  'renderHighlight("😀 โทร 081-234-5678", [{start: 6, end: 18, data_type: "PHONE"}])',
  context,
);
assert.match(
  element("highlight").innerHTML,
  />081-234-5678<\/mark>/,
  "astral Unicode offset did not highlight the exact phone substring",
);
vm.runInContext(
  'renderHighlight("<img src=x onerror=alert(1)>", [{start: 0, end: 28, data_type: "NAME"}])',
  context,
);
assert.ok(!element("highlight").innerHTML.includes("<img"), "highlighting rendered source text as HTML");
assert.match(element("highlight").innerHTML, /&lt;img/, "highlighting did not preserve escaped source text");
vm.runInContext(
  'renderLegend({NAME: "<img src=x onerror=alert(1)>"})',
  context,
);
assert.ok(!element("legend").innerHTML.includes("<img"), "legend rendered a count as HTML");
assert.match(element("legend").innerHTML, /&lt;img/, "legend did not preserve an escaped count");
vm.runInContext(
  'fillEvidence({sanitized_text: "synthetic", warnings: [{code: "<img src=x onerror=alert(1)>", count: "<svg onload=alert(2)>"}]})',
  context,
);
assert.ok(!element("evidenceWarnings").innerHTML.includes("<img"), "warning code rendered as HTML");
assert.ok(!element("evidenceWarnings").innerHTML.includes("<svg"), "warning count rendered as HTML");
assert.match(element("evidenceWarnings").innerHTML, /&lt;img/, "warning evidence did not preserve escaped text");
assert.equal(
  vm.runInContext('errorMessage(500, "RAW_EXCEPTION_DETAIL", "text")', context),
  "ไม่สามารถดำเนินการได้ในขณะนี้ กรุณาตรวจข้อมูลแล้วลองใหม่",
  "raw backend detail reached the user-facing error",
);
assert.match(
  vm.runInContext('errorMessage(429, "rate_limited", "text")', context),
  /รอสักครู่แล้วลองใหม่/,
  "rate-limit recovery copy is missing",
);
const seedSensitiveState = () => {
  element("accessCode").value = "SENSITIVE_ACCESS_CODE";
  element("editor").value = "SENSITIVE_EDITOR";
  element("highlight").innerHTML = "SENSITIVE_HIGHLIGHT";
  element("masked").textContent = "SENSITIVE_MASKED";
  element("restored").textContent = "SENSITIVE_RESTORED";
  element("evidenceSanitized").textContent = "SENSITIVE_EVIDENCE";
  element("evidenceWarnings").textContent = "SENSITIVE_WARNING";
  element("guardBar").textContent = "SENSITIVE_GUARD";
  element("safeOriginal").textContent = "SENSITIVE_ORIGINAL";
  element("safeElapsed").textContent = "SENSITIVE_ELAPSED";
  element("safeAnnouncement").textContent = "SENSITIVE_ANNOUNCEMENT";
  element("proofStatus").textContent = "SENSITIVE_PROOF";
  element("safeDuration").textContent = "SENSITIVE_DURATION";
  element("piiTypes").textContent = "SENSITIVE_TYPES";
  element("piiCount").textContent = "99";
  element("reportMeta").textContent = "SENSITIVE_REPORT";
  element("reportScore").textContent = "99";
  element("reportGrade").textContent = "F";
  element("reportScope").textContent = "SENSITIVE_SCOPE";
  element("reportCategories").textContent = "SENSITIVE_CATEGORIES";
  element("guidedStatus").textContent = "SENSITIVE_GUIDED";
  element("guidedPii").textContent = "99";
};
const assertSensitiveStateCleared = (label, {sessionExpired = false} = {}) => {
  assert.equal(element("accessCode").value, "", `${label}: access code retained`);
  assert.equal(element("editor").value, "", `${label}: editor retained source text`);
  assert.equal(element("highlight").textContent, "", `${label}: highlight retained source text`);
  assert.equal(element("masked").textContent, "ยังไม่ได้ส่ง", `${label}: masked text retained`);
  assert.equal(element("restored").textContent, "ยังไม่ได้ส่ง", `${label}: restored text retained`);
  assert.equal(element("evidenceSanitized").textContent, "ยังไม่มีข้อมูล", `${label}: evidence retained`);
  assert.equal(element("guardBar").textContent, "", `${label}: guard result retained`);
  assert.equal(element("safeOriginal").textContent, "กด “ใช้ตัวอย่างสังเคราะห์” เพื่อเริ่มได้ทันที", `${label}: Safe AI original retained`);
  if (sessionExpired) {
    assert.match(element("safeElapsed").textContent, /เซสชันหมดอายุ/, `${label}: local recovery guidance missing`);
  } else {
    assert.equal(element("safeElapsed").textContent, "", `${label}: elapsed state retained`);
  }
  assert.equal(element("safeAnnouncement").textContent, "", `${label}: screen-reader Safe AI state retained`);
  assert.equal(element("proofStatus").textContent, "รอผล Safe AI", `${label}: proof state retained`);
  assert.equal(element("safeDuration").textContent, "—", `${label}: Safe AI timing retained`);
  assert.equal(element("piiTypes").textContent, "ยังไม่มีข้อมูลให้วิเคราะห์", `${label}: PII type summary retained`);
  assert.equal(element("reportMeta").textContent, "", `${label}: report result retained`);
  assert.equal(element("reportScore").textContent, "—", `${label}: report score retained`);
  assert.match(element("reportCategories").textContent, /ประเภทข้อมูลจะแสดงจาก Privacy Scan/, `${label}: report category context retained`);
  assert.equal(element("guidedPii").textContent, "—", `${label}: Guided result retained`);
  assert.equal(element("guidedStepScan").dataset.state, "idle", `${label}: Guided progress retained`);
};

seedSensitiveState();
const pendingSend = element("send").emit("click");
await flush();
assert.equal(roundtripCalls, 1, "slow business request did not start");

await element("logoutBtn").emit("click");
assertSensitiveStateCleared("logout");

slowRoundtrip.resolve(response(200, {
  sanitized_text: "STALE_SANITIZED_RESULT",
  restored_text: "STALE_RESTORED_RESULT",
  provider_used: "STALE_PROVIDER_RESULT",
  detected_entity_count: 1,
  warnings: [],
  safety: {status: "pass"},
  restoration: {status: "complete", leftover_count: 0},
}));
await pendingSend;
assertSensitiveStateCleared("stale response after logout");
assert.equal(downloads.length, 0, "stale response triggered a download");
for (const node of elements.values()) {
  assert.doesNotMatch(
    `${node.value}\n${node.textContent}\n${node.innerHTML}\n${node.src}`,
    /STALE_/,
    `stale response rendered into #${node.id}`,
  );
}

element("accessCode").value = "synthetic-access-code";
await element("loginBtn").emit("click");
assert.equal(element("send").disabled, false, "re-login did not restore business controls");

element("editor").value = "OLD_EDITOR";
await element("editor").emit("input");
const pendingDetect = vm.runInContext("clearTimeout(debounceTimer); detectNow()", context);
await flush();
assert.equal(detectCalls, 1, "slow detect request did not start");
element("editor").value = "NEW_EDITOR";
await element("editor").emit("input");
vm.runInContext("clearTimeout(debounceTimer)", context);
slowDetect.resolve(response(200, {
  highlights: [{start: 0, end: 3, data_type: "NAME"}],
  entity_type_counts: {NAME: 1},
  detected_entity_count: 1,
}));
await pendingDetect;
assert.equal(
  element("highlight").textContent,
  "กดสแกนเพื่อดูตำแหน่ง PII",
  "stale detect response overwrote the newer editor text",
);
assert.equal(guardCalls, 0, "stale detect response started a guard request");

roundtripMode = "deferred";
slowRoundtrip = deferred();
element("editor").value = "OLD_ROUNDTRIP_SOURCE";
await element("editor").emit("input");
vm.runInContext("clearTimeout(debounceTimer)", context);
const staleInputRoundtrip = element("send").emit("click");
await flush();
element("editor").value = "NEW_ROUNDTRIP_SOURCE";
await element("editor").emit("input");
vm.runInContext("clearTimeout(debounceTimer)", context);
slowRoundtrip.resolve(response(200, {
  sanitized_text: "STALE_INPUT_SANITIZED",
  restored_text: "STALE_INPUT_RESTORED",
  provider_used: "tokenmind",
  detected_entity_count: 1,
  warnings: [],
  safety: {status: "pass"},
  restoration: {status: "complete", leftover_count: 0},
}));
await staleInputRoundtrip;
assert.doesNotMatch(element("masked").textContent, /STALE_INPUT_/);
assert.doesNotMatch(element("restored").textContent, /STALE_INPUT_/);

const guidedSource = "นายทดสอบ ตัวอย่าง โทร 081-000-0000";
const guidedPhone = "081-000-0000";
const guidedPhoneStart = Array.from(guidedSource.slice(0, guidedSource.indexOf(guidedPhone))).length;
const guidedDetectBody = {
  highlights: [{
    start: guidedPhoneStart,
    end: guidedPhoneStart + Array.from(guidedPhone).length,
    data_type: "PHONE",
  }],
  entity_type_counts: {PHONE: 1},
  detected_entity_count: 1,
};
const guidedSafeBody = restoredText => ({
  sanitized_text: "นายทดสอบ ตัวอย่าง โทร [PHONE_SYNTHETIC]",
  restored_text: restoredText,
  provider_used: "tokenmind",
  detected_entity_count: 1,
  entity_type_counts: {PHONE: 1},
  section26_categories: [],
  guard_findings: [],
  warnings: [],
  safety: {status: "pass", residual_count: 0},
  restoration: {status: "complete", replaced_count: 1, leftover_count: 0},
});

const callsBeforeScenario = requestOrder.length;
await scenarioButtons[1].emit("click");
assert.match(element("editor").value, /เวชระเบียนสังเคราะห์/, "scenario selection did not populate its synthetic input");
assert.equal(requestOrder.length, callsBeforeScenario, "scenario selection submitted an API request");
assert.equal(scenarioButtons[1].ariaPressed, "true", "selected scenario is not exposed accessibly");

detectMode = "body";
detectBody = guidedDetectBody;
roundtripMode = "body";
roundtripBody = guidedSafeBody("คำตอบที่กู้คืนแล้ว");
reportMode = "success";
element("editor").value = guidedSource;
await element("editor").emit("input");
const guidedOrderStart = requestOrder.length;
const guidedRoundtripStart = roundtripCalls;
const guidedReportStart = analyzeReportCalls;
await element("guidedStart").emit("click");
assert.deepEqual(
  requestOrder.slice(guidedOrderStart),
  ["/api/detect", "/api/guard", "/api/roundtrip", "/api/analyze-report"],
  "Guided Demo did not execute the intended endpoint sequence",
);
assert.equal(roundtripCalls, guidedRoundtripStart + 1, "Guided Demo made more than one Safe AI API invocation");
assert.equal(analyzeReportCalls, guidedReportStart + 1, "Guided Demo did not make exactly one report request");
assert.equal(roundtripRequests.at(-1).mode, "token", "Guided Demo did not send the selected allowlisted mode exactly");
assert.equal(roundtripRequests.at(-1).provider, "tokenmind", "Guided Demo changed the fixed hosted provider");
assert.equal(element("guidedStepScan").dataset.state, "done");
assert.equal(element("guidedStepSafe").dataset.state, "done");
assert.equal(element("guidedStepReport").dataset.state, "done");
assert.equal(element("masked").textContent, roundtripBody.sanitized_text, "exact sanitized provider input was not rendered");
assert.match(element("proofStatus").textContent, /ไม่พบค่าที่ Privacy Scan ตรวจจับ 1 รายการ/);
assert.doesNotMatch(element("proofStatus").textContent, new RegExp(guidedPhone), "proof exposed a detected raw value");
assert.notEqual(element("guidedTiming").textContent, "—", "Guided Demo total timing was not recorded");
assert.equal(element("guidedProofLink").hidden, false, "Guided completion did not reveal the proof jump");

await element("guidedReset").emit("click");
assert.equal(element("editor").value, "", "Guided reset retained source text");
assert.equal(element("guidedStepScan").dataset.state, "idle", "Guided reset retained completed progress");
assert.equal(element("masked").textContent, "ยังไม่ได้ส่ง", "Guided reset retained protected text");
assert.equal(element("reportScore").textContent, "—", "Guided reset retained report metadata");
assert.equal(element("guidedProofLink").hidden, true, "Guided reset retained the stale proof jump");

// Starting Guided Demo must abort an older direct provider-bound request, and
// that stale request must not re-enable controls while Guided owns the lane.
roundtripMode = "deferred";
slowRoundtrip = deferred();
element("editor").value = guidedSource;
await element("editor").emit("input");
const directBeforeGuided = vm.runInContext("runSafeAI()", context);
await flush();
const abortsBeforeGuided = abortedRoundtripCalls;
const guidedOverlapRoundtrip = deferred();
slowRoundtrip = guidedOverlapRoundtrip;
detectMode = "body";
detectBody = guidedDetectBody;
reportMode = "success";
const pendingOverlapGuided = element("guidedStart").emit("click");
await flush();
await flush();
await directBeforeGuided;
assert.equal(abortedRoundtripCalls, abortsBeforeGuided + 1, "Guided Demo did not abort an older Safe AI request");
assert.equal(element("send").disabled, true, "stale Safe AI finalizer re-enabled send during Guided Demo");
assert.equal(element("mode").disabled, true, "stale Safe AI finalizer unfroze mode during Guided Demo");
guidedOverlapRoundtrip.resolve(response(200, guidedSafeBody("คำตอบจาก Guided ที่ไม่ซ้อนคำขอ")));
await pendingOverlapGuided;
assert.equal(element("guidedStepReport").dataset.state, "done", "Guided Demo did not recover after aborting prior work");
await element("guidedReset").emit("click");

// Unsupported DOM values are normalized back to the strict allowlist; both
// supported modes are sent exactly as selected.
roundtripMode = "body";
roundtripBody = guidedSafeBody("คำตอบจากโหมดที่ตรวจสอบแล้ว");
element("editor").value = guidedSource;
await element("editor").emit("input");
element("mode").value = "__proto__";
await element("send").emit("click");
assert.equal(element("mode").value, "token", "unsupported mode was not normalized in the control");
assert.equal(roundtripRequests.at(-1).mode, "token", "unsupported mode escaped the frontend allowlist");
element("mode").value = "surrogate";
await element("mode").emit("change");
await element("send").emit("click");
assert.equal(roundtripRequests.at(-1).mode, "surrogate", "supported surrogate mode was not sent exactly");
element("mode").value = "token";
await element("mode").emit("change");

detectMode = "error";
element("editor").value = guidedSource;
await element("editor").emit("input");
const detectFailureRoundtrips = roundtripCalls;
const detectFailureReports = analyzeReportCalls;
await element("guidedStart").emit("click");
assert.equal(roundtripCalls, detectFailureRoundtrips, "Guided Demo called Safe AI after detect failure");
assert.equal(analyzeReportCalls, detectFailureReports, "Guided Demo called report after detect failure");
assert.equal(element("guidedStepScan").dataset.state, "error");
assert.equal(element("guidedStepSafe").dataset.state, "idle");
assert.equal(element("guidedStepReport").dataset.state, "idle");

guardMode = "error";
detectMode = "body";
element("editor").value = guidedSource;
await element("editor").emit("input");
const guardFailureRoundtrips = roundtripCalls;
const guardFailureReports = analyzeReportCalls;
await element("guidedStart").emit("click");
assert.equal(roundtripCalls, guardFailureRoundtrips, "Guided Demo called Safe AI after guard failure");
assert.equal(analyzeReportCalls, guardFailureReports, "Guided Demo called report after guard failure");
assert.equal(element("guidedStepScan").dataset.state, "error");
assert.match(element("guardBar").textContent, /ตรวจเตือนคำสั่งไม่พร้อม/);
guardMode = "success";

detectMode = "body";
roundtripMode = "body";
roundtripBody = guidedSafeBody("UNSAFE_GUIDED_RESULT");
roundtripBody.safety = {status: "fail", residual_count: 1};
element("editor").value = guidedSource;
await element("editor").emit("input");
const unsafeGuidedReports = analyzeReportCalls;
await element("guidedStart").emit("click");
assert.equal(analyzeReportCalls, unsafeGuidedReports, "Guided Demo called report after unsafe Safe AI result");
assert.equal(element("guidedStepScan").dataset.state, "done");
assert.equal(element("guidedStepSafe").dataset.state, "error");
assert.equal(element("guidedStepReport").dataset.state, "idle");
assert.doesNotMatch(element("restored").textContent, /UNSAFE_GUIDED_RESULT/);

roundtripBody = guidedSafeBody("คำตอบที่ปลอดภัย");
reportMode = "error";
element("editor").value = guidedSource;
await element("editor").emit("input");
await element("guidedStart").emit("click");
assert.equal(element("guidedStepScan").dataset.state, "done");
assert.equal(element("guidedStepSafe").dataset.state, "done");
assert.equal(element("guidedStepReport").dataset.state, "error");
assert.notEqual(element("guidedStatus").dataset.tone, "safe", "report failure was presented as Guided success");

reportMode = "malformed";
element("editor").value = guidedSource;
await element("editor").emit("input");
await element("guidedStart").emit("click");
assert.equal(element("guidedStepScan").dataset.state, "done");
assert.equal(element("guidedStepSafe").dataset.state, "done");
assert.equal(element("guidedStepReport").dataset.state, "error", "malformed report was presented as complete");
assert.equal(element("reportDownloadBtn").hidden, true, "malformed report exposed a download");
assert.notEqual(element("guidedStatus").dataset.tone, "safe", "malformed report produced Guided success");

reportMode = "success";
roundtripMode = "deferred";
slowRoundtrip = deferred();
element("editor").value = guidedSource;
await element("editor").emit("input");
const pendingGuided = element("guidedStart").emit("click");
await flush();
await flush();
await element("guidedReset").emit("click");
slowRoundtrip.resolve(response(200, guidedSafeBody("STALE_GUIDED_RESTORED")));
await pendingGuided;
assert.equal(element("editor").value, "", "reset during Guided request retained source text");
assert.doesNotMatch(element("restored").textContent, /STALE_GUIDED/);
assert.equal(element("guidedStepScan").dataset.state, "idle", "stale Guided completion repopulated progress");
assert.equal(element("reportScore").textContent, "—", "stale Guided completion repopulated report state");

roundtripMode = "body";
roundtripBody = guidedSafeBody("คำตอบหลังทดสอบ Guided");
detectMode = "body";
reportMode = "success";

element("editor").value = "synthetic health report source";
const downloadsBeforeReport = downloads.length;
const directReportCallsBefore = analyzeReportCalls;
await element("reportBtn").emit("click");
assert.equal(analyzeReportCalls, directReportCallsBefore + 1, "PDPA report PDF request did not run");
assert.equal(element("reportScore").textContent, "68");
assert.equal(element("reportGrade").textContent, "D");
assert.equal(element("reportScope").textContent, "พร้อม");
assert.match(element("reportMeta").textContent, /คะแนน 68 · เกรด D/);
assert.equal(downloads.length, downloadsBeforeReport, "report downloaded before the user reviewed its summary");
assert.equal(element("reportDownloadBtn").hidden, false, "validated report did not enable download");
await element("reportDownloadBtn").emit("click");
assert.equal(downloads.length, downloadsBeforeReport + 1, "validated PDPA report was not downloaded on request");
reportMode = "error";
await element("reportBtn").emit("click");
assert.equal(element("reportScore").textContent, "—", "failed report retry retained a stale score");
assert.equal(element("reportGrade").textContent, "—", "failed report retry retained a stale grade");
assert.equal(element("reportDownloadBtn").hidden, true, "failed report retry retained stale PDF bytes");
assert.match(element("reportMeta").textContent, /ยังไม่พร้อม|ไม่สามารถ|ลองใหม่/);
reportMode = "success";
const downloadsAfterReport = downloads.length;
await element("editor").emit("input");
assert.equal(element("reportDownloadBtn").hidden, true, "changing input retained a stale report download");
await element("reportDownloadBtn").emit("click");
assert.equal(downloads.length, downloadsAfterReport, "stale report bytes remained downloadable");

detectMode = "body";
detectBody = guidedDetectBody;
element("editor").value = guidedSource;
await element("editor").emit("input");
await element("scanBtn").emit("click");
assert.equal(element("piiCount").textContent, "1", "scan setup did not render its result");
guardBody = {
  flagged: true,
  guard_findings: [{category: "<img src=x onerror=alert(1)>", severity: "<svg onload=alert(2)>"}],
};
await element("scanBtn").emit("click");
assert.ok(!element("guardBar").innerHTML.includes("<img"), "guard category rendered as HTML");
assert.ok(!element("guardBar").innerHTML.includes("<svg"), "guard severity rendered as HTML");
assert.match(element("guardBar").innerHTML, /&lt;img/, "guard finding did not preserve escaped text");
guardBody = {flagged: false, guard_findings: []};
detectMode = "deferred";
slowDetect = deferred();
const pendingFailedRescan = element("scanBtn").emit("click");
await flush();
assert.equal(element("piiCount").textContent, "—", "rescan retained the prior count while loading");
assert.equal(element("legend").textContent, "", "rescan retained the prior legend while loading");
slowDetect.resolve(response(503, {error: {code: "service_unavailable"}}));
await pendingFailedRescan;
assert.equal(element("piiCount").textContent, "0", "failed rescan retained the prior count");
detectMode = "body";

roundtripMode = "body";
roundtripBody = guidedSafeBody("คำตอบก่อน retry");
await element("send").emit("click");
assert.equal(element("evidenceSanitized").textContent, roundtripBody.sanitized_text);
roundtripMode = "deferred";
slowRoundtrip = deferred();
const pendingFailedSafeRetry = element("send").emit("click");
await flush();
assert.equal(element("evidenceSanitized").textContent, "ยังไม่มีข้อมูล", "Safe AI retry retained stale sanitized evidence");
assert.doesNotMatch(element("evidenceWarnings").textContent, /ไม่พบคำเตือน/, "Safe AI retry retained stale warning state");
slowRoundtrip.resolve(response(503, {error: {code: "provider_unavailable"}}));
await pendingFailedSafeRetry;
assert.equal(element("evidenceSanitized").textContent, "ยังไม่มีข้อมูล", "failed Safe AI retry repopulated stale evidence");

const assertRoundtripSuppressed = async (label, body) => {
  roundtripMode = "body";
  roundtripBody = body;
  element("editor").value = "synthetic source";
  await element("send").emit("click");
  assert.doesNotMatch(
    element("restored").textContent,
    new RegExp(body.restored_text),
    `${label}: unsafe restored_text was rendered`,
  );
  assert.match(
    element("restored").textContent,
    /ระบบระงับคำตอบ/,
    `${label}: suppression warning was not shown`,
  );
};
const guardedBody = restoredText => ({
  sanitized_text: "synthetic sanitized",
  restored_text: restoredText,
  provider_used: "tokenmind",
  detected_entity_count: 1,
  warnings: [],
  safety: {status: "pass"},
  restoration: {status: "complete", leftover_count: 0},
});
const unsafeBody = guardedBody("UNSAFE_RESTORED");
unsafeBody.safety = {status: "fail"};
await assertRoundtripSuppressed("unsafe response", unsafeBody);
const incompleteBody = guardedBody("INCOMPLETE_RESTORED");
incompleteBody.restoration = {status: "incomplete", leftover_count: 1};
await assertRoundtripSuppressed("incomplete restoration", incompleteBody);
const warningBody = guardedBody("WARNING_RESTORED");
warningBody.warnings = [{code: "foreign_replacement", count: 1}];
warningBody.restoration = {status: "unsafe", leftover_count: 0};
await assertRoundtripSuppressed("warning-bearing response", warningBody);

roundtripMode = "unauthorized";
seedSensitiveState();
const downloadsBeforeUnauthorized = downloads.length;
await element("send").emit("click");
assertSensitiveStateCleared("401 response", {sessionExpired: true});
assert.equal(element("send").disabled, true, "401 did not disable business controls");
assert.equal(downloads.length, downloadsBeforeUnauthorized, "401 response triggered a download");
assert.match(element("safeElapsed").textContent, /เซสชันหมดอายุ.*เข้าสู่ระบบด้านบน/, "401 left Safe AI without local recovery guidance");
assert.equal(element("safeElapsed").dataset.tone, "caution", "401 recovery was not presented calmly");
assert.equal(element("accessCode").focused, true, "401 did not return focus to the login field");

element("accessCode").value = "synthetic-access-code";
await element("loginBtn").emit("click");
logoutMode = "slow";
slowLogout = deferred();
seedSensitiveState();
const loginCallsBeforeSlowSuccess = loginCalls;
const pendingSlowLogoutSuccess = element("logoutBtn").emit("click");
await flush();
assert.equal(element("loginBtn").disabled, true, "slow logout left login enabled");
assert.equal(element("accessCode").disabled, true, "slow logout left access code enabled");
element("accessCode").value = "reordered-login-attempt";
await element("loginBtn").emit("click");
assert.equal(
  loginCalls,
  loginCallsBeforeSlowSuccess,
  "login request started before slow logout completed",
);
slowLogout.resolve(response(204));
await pendingSlowLogoutSuccess;
assertSensitiveStateCleared("slow successful logout");
assert.equal(vm.runInContext("authenticated", context), false);
assert.equal(element("authStatus").textContent, "ออกจากระบบแล้ว");
assert.equal(element("loginBtn").disabled, false, "login stayed disabled after logout");

element("accessCode").value = "synthetic-access-code";
await element("loginBtn").emit("click");
logoutMode = "slow";
slowLogout = deferred();
seedSensitiveState();
const loginCallsBeforeSlowFailure = loginCalls;
const pendingSlowLogoutFailure = element("logoutBtn").emit("click");
await flush();
element("accessCode").value = "reordered-login-attempt";
await element("loginBtn").emit("click");
assert.equal(
  loginCalls,
  loginCallsBeforeSlowFailure,
  "login request started before slow failed logout completed",
);
slowLogout.resolve(response(500));
await pendingSlowLogoutFailure;
assertSensitiveStateCleared("failed logout response");
assert.equal(vm.runInContext("authenticated", context), false);
assert.match(element("authStatus").textContent, /session บนเซิร์ฟเวอร์อาจยังอยู่/);
assert.equal(element("logoutBtn").hidden, false, "failed logout did not offer a retry");
assert.equal(element("logoutBtn").textContent, "ลองออกจากระบบอีกครั้ง");
assert.equal(element("loginBtn").disabled, false, "login stayed disabled after failed logout");

logoutMode = "network-error";
seedSensitiveState();
await element("logoutBtn").emit("click");
assertSensitiveStateCleared("failed logout network");
assert.match(element("authStatus").textContent, /session บนเซิร์ฟเวอร์อาจยังอยู่/);
assert.equal(element("logoutBtn").hidden, false, "network failure did not offer a retry");

logoutMode = "success";
await element("logoutBtn").emit("click");
assert.equal(element("authStatus").textContent, "ออกจากระบบแล้ว");
assert.equal(element("logoutBtn").hidden, true);

console.log("frontend session contract ok: auth/logout and stale responses are safe");
