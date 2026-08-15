#!/usr/bin/env node
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import {fileURLToPath} from "node:url";

const repo = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const home = fs.readFileSync(path.join(repo, "web", "index.html"), "utf8");
const appPage = fs.readFileSync(path.join(repo, "web", "app.html"), "utf8");
const appCss = fs.readFileSync(path.join(repo, "web", "app.css"), "utf8");
const source = fs.readFileSync(path.join(repo, "web", "app.js"), "utf8");
const page = `${appPage}\n${appCss}\n${source}`;

assert.match(home, /<main id="main-content"/, "Home has no semantic main target");
assert.match(home, /<script src="\/home\.js" defer><\/script>/, "Home does not load the exact local deferred script");
assert.doesNotMatch(home, /id="accessCode"|id="authCard"|\/api\//, "Home contains app authentication or API initialization");
assert.doesNotMatch(home, /src="\/app\.js"/, "Home loads the Hosted application runtime");
for (const handoff of ["/app#privacy-scan", "/app#safe-ai", "/app#pdpa-report", "/app#guided-demo", "/app#providerEvidenceCard"]) {
  assert.ok(home.includes(handoff), `Home workflow handoff is missing: ${handoff}`);
}
assert.match(home, /<details class="mobile-nav">[\s\S]*href="\/privacy"[\s\S]*href="\/help"/, "Home has no no-JavaScript mobile navigation");
assert.match(appPage, /<meta name="robots" content="noindex,nofollow">/, "Hosted app is indexable");
assert.match(appPage, /<script src="\/app\.js" defer><\/script>/, "Hosted app does not load the exact local runtime");
assert.doesNotMatch(appPage, /<script>([\s\S]*?)<\/script>/, "Hosted app retains inline executable script");
assert.ok(appPage.includes('id="appBootstrapNotice"'), "Hosted app has no no-script/bootstrap failure panel");
assert.ok(appPage.includes('<div id="appControls" inert>'), "Hosted operational controls do not fail closed before JavaScript bootstrap");
assert.ok(source.includes('document.getElementById("appControls").removeAttribute("inert")'), "Hosted bootstrap never unlocks the inert application controls");
assert.ok(source.includes('event.target.closest(\'a[href^="#"]\')'), "signed-out same-page workflow links are not intercepted");
assert.ok(source.includes("holdWorkflowUntilAuthenticated(location.hash)"), "signed-out hash changes can bypass the access gate");
assert.ok(appPage.includes('id="editorBoundary"'), "Hosted raw input lacks an adjacent privacy boundary");
for (const forbidden of ["redact-pdf", "pdfFile", "pdfPick", "pdfDownload", "after_png_b64"]) {
  assert.ok(!page.includes(forbidden), `public PDF execution path remains: ${forbidden}`);
}
for (const workflow of ['id="privacy-scan"', 'id="safe-ai"', 'id="pdpa-report"']) {
  assert.ok(page.includes(workflow), `public workflow is missing: ${workflow}`);
}
assert.match(home, /href="\/downloads#desktop">ดาวน์โหลด Desktop 3\.0\.0/, "Home is not Desktop-first");
assert.ok(home.includes('class="visual"') && home.includes('class="poster"'), "Home lost the approved protection canvas");
for (const channelBoundary of [
  "การตรวจจับ การแทนที่ vault/mapping การกู้คืน และรายงานอยู่บนอุปกรณ์",
  "Desktop 3.0.0 ไม่มีคำสั่งเรียก provider ภายนอก",
]) {
  assert.ok(home.includes(channelBoundary), `Home channel boundary is missing: ${channelBoundary}`);
}
for (const channelBoundary of [
  "ข้อความต้นฉบับถึง AI for Thai edge และเซิร์ฟเวอร์ Team 08",
  "ส่งให้ Pathumma / thaillm-8b เฉพาะข้อความที่ปกป้องและตรวจซ้ำแล้ว",
  "ไม่ส่ง raw PII, vault/mapping หรือคู่ข้อมูลเดิมกับข้อมูลแทน",
]) {
  assert.ok(appPage.includes(channelBoundary), `Hosted channel boundary is missing: ${channelBoundary}`);
}
assert.match(
  page,
  /<details class="advanced-evidence">[\s\S]*id="protectionEvidence"/,
  "advanced protection evidence is not progressively disclosed",
);
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
for (const sprintTwoMarker of [
  'id="presenterModeBtn"',
  'id="fullscreenBtn"',
  'id="presentationStage"',
  'id="executiveSummary"',
  'id="protectionReceipt"',
  'id="rawProtectedComparison"',
  'id="sensitiveDataMap"',
  'id="guardRiskPanel"',
  'id="entityGlossary"',
  'id="modeTokenCard"',
  'id="modeSurrogateCard"',
  'id="appAnnouncement"',
]) {
  assert.ok(page.includes(sprintTwoMarker), `Sprint 2 presentation contract missing: ${sprintTwoMarker}`);
}
for (const initiallyHiddenResult of [
  "executiveSummary",
  "protectionReceipt",
  "rawProtectedComparison",
  "sensitiveDataMap",
  "guardRiskPanel",
]) {
  assert.match(
    page,
    new RegExp(`<[^>]*id="${initiallyHiddenResult}"[^>]*\\shidden(?:\\s|>|=)`),
    `Sprint 2 result is not initially hidden: ${initiallyHiddenResult}`,
  );
}
assert.match(
  page,
  /id="appAnnouncement"[^>]*role="status"[^>]*aria-live="polite"[^>]*aria-atomic="true"/,
  "the consolidated application announcement is not polite and atomic",
);
for (const noisyLiveRegion of [
  "guided-summary",
  "scan-summary",
  "safe-metrics",
  "evidence-grid",
  "report-summary",
]) {
  assert.doesNotMatch(
    page,
    new RegExp(`class="[^"]*${noisyLiveRegion}[^"]*"[^>]*aria-live=`),
    `result grid remains an overly broad live region: ${noisyLiveRegion}`,
  );
}
assert.ok(
  (page.match(/aria-live=/g) || []).length <= 6,
  "frontend exposes too many competing live regions",
);
assert.ok(page.includes("ข้อความที่ AI Guard ส่งต่อหลังปกป้องและตรวจซ้ำ"), "Safe AI does not label sanitized provider input");
assert.ok(page.includes("ข้อความที่ส่งให้ AI จริง"), "Safe AI proof card is not judge-readable");
assert.ok(page.includes('href="#providerEvidenceCard"'), "Guided proof jump does not target the complete evidence card");
assert.ok(page.includes("scroll-margin-top:140px"), "sticky navigation can obscure the Safe AI proof target");
assert.ok(
  page.includes(".presentation-stage:fullscreen .receipt-item b{font-size:17px}"),
  "fullscreen receipt values remain too small for projector evidence",
);
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
  "--canvas:#f3f1eb",
  "@font-face{font-family:AIGuardAnuphan",
  "url('/assets/fonts/anuphan-thai.woff2')",
  "url('/assets/fonts/anuphan-latin.woff2')",
  'href="/assets/ai-guard-favicon.svg"',
  "url('/assets/ai-guard-mark.svg')",
  "ข้อมูลสังเคราะห์",
]) {
  assert.ok(page.includes(marker), `competition UX contract missing: ${marker}`);
}
assert.ok(
  page.indexOf("preparedReport = report.report_pdf_b64") < page.indexOf('downloadB64(preparedReport'),
  "PDPA report is not reviewed before explicit download",
);
assert.ok(!page.includes("body.ai_response_masked"), "masked provider response leaked into the frontend");
assert.ok(!/localStorage\s*[.\[]|sessionStorage\s*[.\[]/.test(source), "frontend persists sensitive state in browser storage");
assert.ok(
  !/<script[^>]+src=["']https?:|<link[^>]+rel=["']stylesheet["'][^>]+href=["']https?:|<link[^>]+href=["']https?:[^>]+rel=["']stylesheet["']/i.test(page),
  "third-party executable/style dependency was added",
);
assert.ok(source.includes("same-origin caller authentication"), "frontend application script is missing");

class FakeClassList {
  constructor(owner) {
    this.owner = owner;
    this.values = new Set();
  }

  add(...tokens) {
    for (const token of tokens) this.values.add(token);
  }

  remove(...tokens) {
    for (const token of tokens) this.values.delete(token);
  }

  contains(token) {
    return this.values.has(token);
  }

  toggle(token, force) {
    const enabled = force === undefined ? !this.values.has(token) : Boolean(force);
    if (enabled) this.values.add(token);
    else this.values.delete(token);
    return enabled;
  }

  toString() {
    return [...this.values].join(" ");
  }
}

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
    this.attributes = new Map();
    this.classList = new FakeClassList(this);
    this.ariaPressed = "false";
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
      listener({target: this, currentTarget: this, preventDefault() {}, ...event})
    );
    await Promise.all(results);
  }

  click() {
    if (this.disabled) return Promise.resolve();
    return this.emit("click");
  }

  removeAttribute(name) {
    if (name === "src") this.src = "";
    this.attributes.delete(name);
  }

  setAttribute(name, value) {
    if (name === "aria-pressed") this.ariaPressed = String(value);
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    if (name === "aria-pressed") return this.ariaPressed;
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  toggleAttribute(name, force) {
    const enabled = force === undefined ? !this.attributes.has(name) : Boolean(force);
    if (enabled) this.setAttribute(name, "");
    else this.removeAttribute(name);
    return enabled;
  }

  async requestFullscreen() {
    fullscreenRequestCalls += 1;
    if (fullscreenRequestMode === "reject") throw new Error("fullscreen rejected");
    document.fullscreenElement = this;
    await document.emit("fullscreenchange");
  }

  scrollIntoView() {
    this.scrolledIntoView = true;
  }

  focus() {
    for (const node of elements.values()) node.focused = false;
    this.focused = true;
    document.activeElement = this;
  }
}

const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, new FakeElement(id));
  return elements.get(id);
};
const sprintTwoSurfaceChildren = Object.freeze({
  executiveSummary: ["executivePii", "executiveProtection", "executivePromptRisk", "executiveReport", "executiveNarrative"],
  protectionReceipt: ["receiptMode", "receiptProvider", "receiptPii", "receiptSafety", "receiptResidual", "receiptRestoration", "receiptSection26", "receiptDuration", "receiptTypes"],
  rawProtectedComparison: ["comparisonRaw", "comparisonProtected", "comparisonLengths", "comparisonDetectedProof"],
  sensitiveDataMap: ["dataMapList", "dataMapNote", "glossaryDetected"],
  guardRiskPanel: ["guardRiskList"],
});
const surfaceText = id => [id, ...(sprintTwoSurfaceChildren[id] || [])]
  .map(childId => element(childId).textContent)
  .join("\n");
element("mode").value = "token";
const scenarioButtons = [...page.matchAll(/<button class="scenario-card"[^>]*data-scenario="([^"]+)"[^>]*data-sample="([^"]+)"/g)]
  .map(match => {
    const button = element(`scenario-${match[1]}`);
    button.dataset.scenario = match[1];
    button.dataset.sample = match[2];
    return button;
  });
const modeCards = [
  ["modeTokenCard", "token"],
  ["modeSurrogateCard", "surrogate"],
].map(([id, mode]) => {
  const button = element(id);
  button.dataset.mode = mode;
  button.dataset.modeCard = mode;
  return button;
});
for (const id of [
  "executiveSummary",
  "protectionReceipt",
  "rawProtectedComparison",
  "sensitiveDataMap",
  "guardRiskPanel",
]) {
  const openingTag = page.match(new RegExp(`<[^>]*id="${id}"[^>]*>`))?.[0] || "";
  element(id).hidden = /\shidden(?:\s|>|=)/.test(openingTag);
}
const downloads = [];
let fullscreenRequestMode = "success";
let fullscreenRequestCalls = 0;
let fullscreenExitCalls = 0;
const documentListeners = new Map();
const document = {
  body: element("body"),
  documentElement: element("documentElement"),
  activeElement: element("body"),
  fullscreenEnabled: true,
  fullscreenElement: null,
  getElementById: element,
  querySelectorAll: selector => {
    if (selector.includes("data-scenario")) return scenarioButtons;
    if (selector.includes("data-mode") || selector.includes("mode-card")) return modeCards;
    return [];
  },
  addEventListener(type, listener) {
    const listeners = documentListeners.get(type) || [];
    listeners.push(listener);
    documentListeners.set(type, listeners);
  },
  removeEventListener(type, listener) {
    documentListeners.set(type, (documentListeners.get(type) || []).filter(item => item !== listener));
  },
  async emit(type, event = {}) {
    const results = (documentListeners.get(type) || []).map(listener => listener({type, ...event}));
    await Promise.all(results);
  },
  async exitFullscreen() {
    fullscreenExitCalls += 1;
    this.fullscreenElement = null;
    await this.emit("fullscreenchange");
  },
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

const response = (status, body = {}, {invalidJson = false} = {}) => ({
  status,
  ok: status >= 200 && status < 300,
  async json() {
    if (invalidJson) throw new SyntaxError("invalid synthetic JSON");
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
let abortedDetectCalls = 0;
let guardCalls = 0;
let guardMode = "success";
let guardBody = {flagged: false, guard_findings: []};
let slowGuard = deferred();
let abortedGuardCalls = 0;
let analyzeReportCalls = 0;
let reportMode = "success";
let slowReport = deferred();
let abortedRoundtripCalls = 0;
let abortedReportCalls = 0;
const requestOrder = [];
const requestLedger = [];
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
  let parsedBody = null;
  if (typeof _options.body === "string") {
    try { parsedBody = JSON.parse(_options.body); } catch { parsedBody = "invalid-json"; }
  }
  requestLedger.push({url, body: parsedBody, signal: _options.signal || null});
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
    if (roundtripMode === "error") return Promise.resolve(response(503, {error: {code: "provider_unavailable"}}));
    if (roundtripMode === "network-error") return Promise.reject(new Error("roundtrip network down"));
    if (roundtripMode === "invalid-json") return Promise.resolve(response(200, {}, {invalidJson: true}));
    if (roundtripMode === "unauthorized") {
      return Promise.resolve(response(401, {error: {code: "authentication_required"}}));
    }
  }
  if (url === "/api/detect") {
    detectCalls += 1;
    requestOrder.push(url);
    if (detectMode === "body") return Promise.resolve(response(200, detectBody));
    if (detectMode === "error") return Promise.resolve(response(503, {error: {code: "service_unavailable"}}));
    if (detectMode === "network-error") return Promise.reject(new Error("detect network down"));
    if (detectMode === "invalid-json") return Promise.resolve(response(200, {}, {invalidJson: true}));
    return abortable(slowDetect.promise, _options.signal, () => { abortedDetectCalls += 1; });
  }
  if (url === "/api/guard") {
    guardCalls += 1;
    requestOrder.push(url);
    if (guardMode === "error") return Promise.resolve(response(503, {error: {code: "service_unavailable"}}));
    if (guardMode === "network-error") return Promise.reject(new Error("guard network down"));
    if (guardMode === "invalid-json") return Promise.resolve(response(200, {}, {invalidJson: true}));
    if (guardMode === "deferred") {
      return abortable(slowGuard.promise, _options.signal, () => { abortedGuardCalls += 1; });
    }
    return Promise.resolve(response(200, guardBody));
  }
  if (url === "/api/analyze-report") {
    analyzeReportCalls += 1;
    requestOrder.push(url);
    if (reportMode === "error") return Promise.resolve(response(503, {error: {code: "service_unavailable"}}));
    if (reportMode === "malformed") return Promise.resolve(response(200, {}));
    if (reportMode === "invalid-json") return Promise.resolve(response(200, {}, {invalidJson: true}));
    if (reportMode === "network-error") return Promise.reject(new Error("report network down"));
    if (reportMode === "deferred") {
      return abortable(slowReport.promise, _options.signal, () => { abortedReportCalls += 1; });
    }
    return Promise.resolve(response(200, {
      report_pdf_b64: "JVBERi0xLjQ=",
      overall_score: 68,
      overall_grade: "D",
    }));
  }
  throw new Error(`unexpected fetch: ${url}`);
};

let monotonicClock = 1_000;
const windowListeners = new Map();
const windowObject = {
  innerWidth: 1440,
  innerHeight: 900,
  addEventListener(type, listener) {
    const listeners = windowListeners.get(type) || [];
    listeners.push(listener);
    windowListeners.set(type, listeners);
  },
  removeEventListener(type, listener) {
    windowListeners.set(type, (windowListeners.get(type) || []).filter(item => item !== listener));
  },
  matchMedia: query => ({
    matches: query.includes("prefers-reduced-motion"),
    media: query,
    addEventListener() {},
    removeEventListener() {},
  }),
  requestAnimationFrame: callback => {
    callback();
    return 1;
  },
};
const contextObject = {
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
  navigator: {userAgent: "frontend-contract"},
  performance: {now: () => {
    monotonicClock += 100;
    return monotonicClock;
  }},
  setTimeout,
  window: windowObject,
};
const context = vm.createContext(contextObject);
windowObject.document = document;
windowObject.window = windowObject;
vm.runInContext(source, context, {filename: "web/app.js"});

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
assert.equal(element("logoutBtn").focused, true, "successful login did not move focus to the visible session control");

initialSession.resolve(response(401, {authenticated: false}));
await flush();
await flush();
assert.equal(
  element("send").disabled,
  false,
  "stale initial session response cleared a newer successful login",
);

for (const id of [
  "executiveSummary",
  "protectionReceipt",
  "rawProtectedComparison",
  "sensitiveDataMap",
  "guardRiskPanel",
]) {
  assert.equal(element(id).hidden, true, `initial Sprint 2 result is visible: #${id}`);
}

const presentationFetchStart = requestLedger.length;
assert.equal(element("presenterModeBtn").disabled, true, "Presenter Mode is available before evidence exists");
await element("presenterModeBtn").click();
assert.equal(element("presenterModeBtn").ariaPressed, "false", "disabled Presenter Mode entered an empty presentation");
assert.equal(requestLedger.length, presentationFetchStart, "disabled Presenter Mode made an API request");

assert.equal(element("fullscreenBtn").disabled, true, "fullscreen is enabled before evidence exists");
await element("fullscreenBtn").click();
assert.equal(document.fullscreenElement, null, "disabled fullscreen changed browser state");
assert.equal(fullscreenRequestCalls, 0, "disabled fullscreen requested browser state");
assert.equal(requestLedger.length, presentationFetchStart, "fullscreen made an API request");

assert.equal(element("modeTokenCard").ariaPressed, "true", "Token mode card is not initially selected");
assert.equal(element("modeSurrogateCard").ariaPressed, "false", "Surrogate mode card is initially selected");
await element("modeSurrogateCard").click();
assert.equal(element("mode").value, "surrogate", "Surrogate mode card did not select surrogate mode");
assert.equal(element("modeSurrogateCard").ariaPressed, "true", "Surrogate mode card did not expose selection");
assert.equal(element("modeTokenCard").ariaPressed, "false", "Token mode card retained stale selection");
await element("modeTokenCard").click();
assert.equal(element("mode").value, "token", "Token mode card did not select token mode");
assert.equal(element("modeTokenCard").ariaPressed, "true", "Token mode card did not expose selection");
await element("entityGlossary").click();
assert.equal(requestLedger.length, presentationFetchStart, "mode/glossary interaction made an API request");

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
  "บริการไม่สามารถทำคำขอนี้ให้เสร็จได้ ระบบไม่แสดงผลลัพธ์ที่ตรวจสอบไม่ได้",
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
  for (const id of [
    "executiveSummary",
    "protectionReceipt",
    "rawProtectedComparison",
    "sensitiveDataMap",
    "guardRiskPanel",
  ]) {
    element(id).hidden = false;
    for (const target of sprintTwoSurfaceChildren[id] || [id]) {
      element(target).textContent = `SENSITIVE_SPRINT2_${id}_${target}`;
    }
  }
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
  for (const id of [
    "executiveSummary",
    "protectionReceipt",
    "rawProtectedComparison",
    "sensitiveDataMap",
    "guardRiskPanel",
  ]) {
    assert.equal(element(id).hidden, true, `${label}: #${id} remained visible`);
    assert.doesNotMatch(surfaceText(id), /SENSITIVE_SPRINT2_/, `${label}: #${id} retained sensitive state`);
  }
};

seedSensitiveState();
const pendingSend = element("send").emit("click");
await flush();
assert.equal(roundtripCalls, 1, "slow business request did not start");

await element("logoutBtn").emit("click");
assertSensitiveStateCleared("logout");
assert.equal(element("accessCode").focused, true, "successful logout did not return focus to the access-code field");

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
assert.equal(element("send").disabled, false, "re-login did not restore business controls after the prior exchange settled");

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
assert.equal(element("send").disabled, false, "settled stale input request retained the provider lock");

const guidedSource = "นายทดสอบ ตัวอย่าง โทร 081-000-0000";
const guidedPhone = "081-000-0000";
const guidedPhoneStart = Array.from(guidedSource.slice(0, guidedSource.indexOf(guidedPhone))).length;
const guidedDetectBody = {
  highlights: [{
    start: guidedPhoneStart,
    end: guidedPhoneStart + Array.from(guidedPhone).length,
    data_type: "PHONE",
    redact_type: "FP",
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

// A real disabled button ignores a second rapid click. One user gesture lane
// must therefore create exactly one browser request to the provider boundary.
roundtripMode = "deferred";
slowRoundtrip = deferred();
element("editor").value = guidedSource;
await element("editor").emit("input");
const doubleClickRoundtrips = roundtripCalls;
const firstUserClick = element("send").click();
const secondUserClick = element("send").click();
await flush();
assert.equal(roundtripCalls, doubleClickRoundtrips + 1, "rapid double-click created duplicate /roundtrip requests");
assert.equal(element("modeTokenCard").disabled, true, "active Safe AI request did not freeze Token mode card");
assert.equal(element("modeSurrogateCard").disabled, true, "active Safe AI request did not freeze Surrogate mode card");
await element("modeSurrogateCard").click();
assert.equal(element("mode").value, "token", "mode changed after the provider-bound request started");
assert.equal(roundtripCalls, doubleClickRoundtrips + 1, "mode action created a hidden provider request");
const customRestoredResult = `คำตอบจากการคลิกครั้งเดียว ${guidedPhone}`;
slowRoundtrip.resolve(response(200, guidedSafeBody(customRestoredResult)));
await Promise.all([firstUserClick, secondUserClick]);
assert.equal(roundtripCalls, doubleClickRoundtrips + 1, "disabled click escaped provider request discipline");
assert.equal(element("modeTokenCard").disabled, false, "Token mode card remained frozen after Safe AI completed");
assert.equal(element("modeSurrogateCard").disabled, false, "Surrogate mode card remained frozen after Safe AI completed");
for (const id of [
  "executiveSummary",
  "protectionReceipt",
  "rawProtectedComparison",
  "sensitiveDataMap",
  "guardRiskPanel",
]) {
  assert.equal(element(id).hidden, false, `direct Safe AI did not expose #${id}`);
}
for (const id of ["executiveSummary", "protectionReceipt", "sensitiveDataMap", "guardRiskPanel"]) {
  assert.doesNotMatch(surfaceText(id), new RegExp(guidedPhone), `#${id} exposed a detected raw value`);
}
assert.match(surfaceText("rawProtectedComparison"), new RegExp(guidedPhone), "comparison omitted the selected original text");
assert.match(surfaceText("rawProtectedComparison"), /\[PHONE_SYNTHETIC\]/, "comparison omitted the exact protected text");
assert.match(surfaceText("protectionReceipt"), /Token|token|โทเคน/, "receipt is not bound to the requested mode");
assert.match(surfaceText("protectionReceipt"), /Pathumma|thaillm-8b|tokenmind/, "receipt is not bound to the validated provider");
assert.match(element("receiptPii").textContent, /รายการ.*ประเภท/, "receipt count/type value is ambiguous");
vm.runInContext(
  'renderSensitiveDataMap("abcdefghij", {PHONE: 2}, [{start: 1, end: 2, data_type: "PHONE"}, {start: 7, end: 9, data_type: "PHONE"}])',
  context,
);
assert.equal((element("dataMapList").innerHTML.match(/class="data-map-fill"/g) || []).length, 2, "Sensitive Data Map merged separate entities into one overstated span");

const presenterEvidenceFetchStart = requestLedger.length;
assert.equal(element("presenterModeBtn").disabled, false, "validated evidence did not enable Presenter Mode");
await element("presenterModeBtn").click();
await flush();
assert.equal(element("presenterModeBtn").ariaPressed, "true", "Presenter Mode did not expose its active state");
assert.equal(element("presentationStage").focused, true, "Presenter Mode did not focus the executive evidence stage");
assert.equal(element("presentationStage").scrolledIntoView, true, "Presenter Mode preserved a stale mid-page scroll position");
assert.doesNotMatch(element("comparisonRaw").textContent, new RegExp(guidedPhone), "Presenter Mode retained custom raw text in the DOM");
assert.doesNotMatch(element("executiveRestored").textContent, new RegExp(guidedPhone), "Presenter Mode retained custom restored text in the DOM");
assert.equal(requestLedger.length, presenterEvidenceFetchStart, "Presenter Mode made an API request");
await element("presenterModeBtn").click();
assert.equal(element("presenterModeBtn").ariaPressed, "false", "Presenter Mode did not expose its inactive state");
assert.match(element("comparisonRaw").textContent, new RegExp(guidedPhone), "Presenter Mode did not restore custom raw text after exit");
assert.match(element("executiveRestored").textContent, new RegExp(guidedPhone), "Presenter Mode did not restore custom result after exit");

const fullscreenFetchStart = requestLedger.length;
assert.equal(element("fullscreenBtn").disabled, false, "validated evidence did not enable safe fullscreen");
element("fullscreenBtn").focused = false;
await element("fullscreenBtn").click();
assert.equal(document.fullscreenElement, element("presentationStage"), "fullscreen did not target the safe presentation stage");
assert.equal(fullscreenRequestCalls, 1, "fullscreen requested more than once for one click");
assert.equal(requestLedger.length, fullscreenFetchStart, "fullscreen made an API request");
assert.doesNotMatch(element("comparisonRaw").textContent, new RegExp(guidedPhone), "fullscreen retained custom raw text in the DOM");
assert.doesNotMatch(element("executiveRestored").textContent, new RegExp(guidedPhone), "fullscreen retained custom restored text in the DOM");
assert.equal(element("presentationStage").focused, true, "fullscreen entry did not focus the evidence stage");
assert.match(element("appAnnouncement").textContent, /เต็มจอ.*Escape|Escape.*เต็มจอ/, "fullscreen entry was not announced");
await document.exitFullscreen();
assert.equal(document.fullscreenElement, null, "external fullscreen exit did not clear browser state");
assert.equal(element("fullscreenBtn").ariaPressed, "false", "fullscreenchange did not synchronize the button state");
assert.match(element("comparisonRaw").textContent, new RegExp(guidedPhone), "fullscreen exit did not restore custom raw text");
assert.match(element("executiveRestored").textContent, new RegExp(guidedPhone), "fullscreen exit did not restore custom result");
assert.equal(element("fullscreenBtn").focused, true, "fullscreen exit did not restore focus to its trigger");
assert.match(element("appAnnouncement").textContent, /ออกจาก.*เต็มจอ/, "fullscreen exit was not announced");
fullscreenRequestMode = "reject";
await element("fullscreenBtn").click();
assert.equal(document.fullscreenElement, null, "rejected fullscreen was presented as active");
assert.match(element("appAnnouncement").textContent, /เต็มจอ|fullscreen|ไม่สามารถ/i, "fullscreen rejection lacked accessible recovery copy");
fullscreenRequestMode = "success";
assert.equal(requestLedger.length, fullscreenFetchStart, "rejected fullscreen made an API request");

element("editor").value = `${guidedSource} เปลี่ยนข้อความ`;
await element("editor").emit("input");
for (const id of [
  "executiveSummary",
  "protectionReceipt",
  "rawProtectedComparison",
  "sensitiveDataMap",
  "guardRiskPanel",
]) {
  assert.equal(element(id).hidden, true, `input change retained #${id}`);
  assert.doesNotMatch(surfaceText(id), new RegExp(guidedPhone), `input change retained raw data in #${id}`);
}

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
const guidedLedgerStart = requestLedger.length;
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
assert.deepEqual(
  requestLedger.slice(guidedLedgerStart).map(item => item.url),
  ["/api/detect", "/api/guard", "/api/roundtrip", "/api/analyze-report"],
  "Guided Demo hid an extra browser request",
);
for (const request of requestLedger.slice(guidedLedgerStart)) {
  assert.equal(request.body.text, guidedSource, `${request.url} was not bound to the selected source generation`);
}
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
for (const id of [
  "executiveSummary",
  "protectionReceipt",
  "rawProtectedComparison",
  "sensitiveDataMap",
  "guardRiskPanel",
]) {
  assert.equal(element(id).hidden, false, `Guided completion did not expose #${id}`);
}
for (const id of ["executiveSummary", "protectionReceipt", "sensitiveDataMap", "guardRiskPanel"]) {
  assert.doesNotMatch(surfaceText(id), new RegExp(guidedPhone), `#${id} exposed raw PII`);
}
assert.match(surfaceText("executiveSummary"), /ผ่าน|สำเร็จ|พร้อม|ปกป้อง/, "executive summary did not reflect validated success");
assert.match(surfaceText("protectionReceipt"), /Token|token|โทเคน/, "Guided receipt lost the frozen mode");
assert.match(surfaceText("sensitiveDataMap"), /โทรศัพท์|PHONE/, "Sensitive Data Map omitted the detected entity type");
assert.match(surfaceText("guardRiskPanel"), /ไม่พบ|ผ่าน|ปกติ/, "Guard / Prompt Risk did not expose the validated safe result");
assert.match(surfaceText("rawProtectedComparison"), new RegExp(guidedPhone), "Guided comparison omitted original text");
assert.match(surfaceText("rawProtectedComparison"), /\[PHONE_SYNTHETIC\]/, "Guided comparison omitted protected text");

await element("guidedReset").emit("click");
assert.equal(element("editor").value, "", "Guided reset retained source text");
assert.equal(element("guidedStepScan").dataset.state, "idle", "Guided reset retained completed progress");
assert.equal(element("masked").textContent, "ยังไม่ได้ส่ง", "Guided reset retained protected text");
assert.equal(element("reportScore").textContent, "—", "Guided reset retained report metadata");
assert.equal(element("guidedProofLink").hidden, true, "Guided reset retained the stale proof jump");
for (const id of [
  "executiveSummary",
  "protectionReceipt",
  "rawProtectedComparison",
  "sensitiveDataMap",
  "guardRiskPanel",
]) {
  assert.equal(element(id).hidden, true, `Guided reset retained #${id}`);
  assert.doesNotMatch(surfaceText(id), new RegExp(guidedPhone), `Guided reset retained raw data in #${id}`);
}

// A browser abort cannot prove that an upstream provider stopped. Guided must
// not supersede an unresolved provider-bound request with a possible duplicate.
roundtripMode = "deferred";
slowRoundtrip = deferred();
element("editor").value = guidedSource;
await element("editor").emit("input");
const directBeforeGuided = vm.runInContext("runSafeAI()", context);
await flush();
const abortsBeforeGuided = abortedRoundtripCalls;
detectMode = "body";
detectBody = guidedDetectBody;
reportMode = "success";
const overlapRoundtrips = roundtripCalls;
await element("guidedStart").click();
assert.equal(roundtripCalls, overlapRoundtrips, "Guided Demo created a duplicate while Safe AI ownership was unresolved");
assert.equal(abortedRoundtripCalls, abortsBeforeGuided, "Guided Demo aborted an ambiguous provider-bound request");
assert.equal(element("guidedStart").disabled, true, "provider lane did not disable Guided Demo");
slowRoundtrip.resolve(response(200, guidedSafeBody("คำตอบจากคำขอเดิมที่จบแน่นอน")));
await directBeforeGuided;
assert.equal(element("guidedStart").disabled, false, "settled Safe AI request did not release Guided Demo");
roundtripMode = "body";
roundtripBody = guidedSafeBody("คำตอบจาก Guided หลัง ownership ว่าง");
const settledGuidedRoundtrips = roundtripCalls;
await element("guidedStart").click();
assert.equal(roundtripCalls, settledGuidedRoundtrips + 1, "Guided retry did not make exactly one /roundtrip request");
assert.equal(element("guidedStepReport").dataset.state, "done", "Guided Demo did not recover after prior work settled");
await element("guidedReset").emit("click");

// Guided ownership also supersedes older direct detect and report work. Their
// aborted finalizers must not unlock controls or repopulate Sprint 2 results.
detectMode = "deferred";
slowDetect = deferred();
element("editor").value = guidedSource;
await element("editor").emit("input");
const pendingDirectDetect = element("scanBtn").click();
await flush();
const detectAbortsBeforeGuided = abortedDetectCalls;
detectMode = "body";
detectBody = guidedDetectBody;
roundtripMode = "deferred";
slowRoundtrip = deferred();
reportMode = "success";
const detectRaceRoundtrips = roundtripCalls;
const pendingDetectRaceGuided = element("guidedStart").click();
await flush();
await flush();
await pendingDirectDetect;
assert.equal(abortedDetectCalls, detectAbortsBeforeGuided + 1, "Guided Demo did not abort older direct detect work");
assert.equal(element("scanBtn").disabled, true, "stale detect finalizer unlocked controls during Guided Demo");
assert.equal(roundtripCalls, detectRaceRoundtrips + 1, "detect race created duplicate provider-bound requests");
slowRoundtrip.resolve(response(200, guidedSafeBody("คำตอบหลังแย่ง ownership จาก detect")));
await pendingDetectRaceGuided;
assert.equal(element("guidedStepReport").dataset.state, "done", "Guided Demo did not recover from direct detect race");
await element("guidedReset").click();

reportMode = "deferred";
slowReport = deferred();
element("editor").value = guidedSource;
await element("editor").emit("input");
const pendingDirectReport = element("reportBtn").click();
await flush();
const reportAbortsBeforeGuided = abortedReportCalls;
detectMode = "body";
detectBody = guidedDetectBody;
roundtripMode = "deferred";
slowRoundtrip = deferred();
reportMode = "success";
const reportRaceRoundtrips = roundtripCalls;
const pendingReportRaceGuided = element("guidedStart").click();
await flush();
await flush();
await pendingDirectReport;
assert.equal(abortedReportCalls, reportAbortsBeforeGuided + 1, "Guided Demo did not abort older direct report work");
assert.equal(element("reportBtn").disabled, true, "stale report finalizer unlocked controls during Guided Demo");
assert.equal(roundtripCalls, reportRaceRoundtrips + 1, "report race created duplicate provider-bound requests");
slowRoundtrip.resolve(response(200, guidedSafeBody("คำตอบหลังแย่ง ownership จาก report")));
await pendingReportRaceGuided;
assert.equal(element("guidedStepReport").dataset.state, "done", "Guided Demo did not recover from direct report race");
await element("guidedReset").click();

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

detectMode = "invalid-json";
element("editor").value = guidedSource;
await element("editor").emit("input");
const malformedDetectRoundtrips = roundtripCalls;
const malformedDetectReports = analyzeReportCalls;
await element("guidedStart").emit("click");
assert.equal(roundtripCalls, malformedDetectRoundtrips, "Guided Demo called Safe AI after malformed Detect 200");
assert.equal(analyzeReportCalls, malformedDetectReports, "Guided Demo called report after malformed Detect 200");
assert.equal(element("guidedStepScan").dataset.state, "error", "malformed Detect was presented as a valid scan");
assert.equal(element("sensitiveDataMap").hidden, true, "malformed Detect exposed a stale data map");

guardMode = "error";
detectMode = "body";
element("editor").value = guidedSource;
await element("editor").emit("input");
const guardFailureRoundtrips = roundtripCalls;
const guardFailureReports = analyzeReportCalls;
await element("guidedStart").emit("click");
assert.equal(roundtripCalls, guardFailureRoundtrips, "Guided Demo called Safe AI after guard failure");
assert.equal(analyzeReportCalls, guardFailureReports, "Guided Demo called report after guard failure");
assert.equal(element("guidedStepScan").dataset.state, "done", "Guard failure obscured a valid Privacy Scan");
assert.equal(element("guidedStepSafe").dataset.state, "error", "Guard failure was not assigned to the Safe AI gate");
assert.match(element("guardBar").textContent, /ตรวจเตือนคำสั่งไม่พร้อม/);
assert.equal(element("sensitiveDataMap").hidden, false, "guard failure hid a valid PII scan map");
assert.equal(element("guardRiskPanel").hidden, false, "guard failure did not expose Guard availability");
assert.match(surfaceText("guardRiskPanel"), /ไม่พร้อม|ไม่สำเร็จ|เชื่อมต่อ/, "guard failure was not distinguished from scan failure");
for (const id of ["executiveSummary", "protectionReceipt", "rawProtectedComparison"]) {
  assert.equal(element(id).hidden, true, `guard failure exposed stale #${id}`);
}
assert.doesNotMatch(surfaceText("sensitiveDataMap"), new RegExp(guidedPhone), "map exposed raw PII after guard failure");

guardMode = "invalid-json";
detectMode = "body";
element("editor").value = guidedSource;
await element("editor").emit("input");
const malformedGuardRoundtrips = roundtripCalls;
const malformedGuardReports = analyzeReportCalls;
await element("guidedStart").emit("click");
assert.equal(roundtripCalls, malformedGuardRoundtrips, "Guided Demo called Safe AI after malformed Guard 200");
assert.equal(analyzeReportCalls, malformedGuardReports, "Guided Demo called report after malformed Guard 200");
assert.equal(element("guidedStepScan").dataset.state, "done", "malformed Guard obscured the valid Privacy Scan");
assert.equal(element("guidedStepSafe").dataset.state, "error", "malformed Guard was not assigned to the Safe AI gate");
assert.match(surfaceText("guardRiskPanel"), /ไม่พร้อม|ไม่สำเร็จ|เชื่อมต่อ/, "malformed Guard was presented as clean");
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
assert.equal(element("protectionReceipt").hidden, false, "report failure discarded the completed protection receipt");
assert.equal(element("rawProtectedComparison").hidden, false, "report failure discarded the completed comparison");
assert.equal(element("executiveSummary").hidden, false, "report failure discarded the partial executive summary");
assert.match(surfaceText("executiveSummary"), /รายงาน.*(?:ไม่|ยัง)|(?:ไม่|ยัง).*รายงาน|รอ PDPA Report/, "report failure was missing from the executive summary");

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
for (const id of [
  "executiveSummary",
  "protectionReceipt",
  "rawProtectedComparison",
  "sensitiveDataMap",
  "guardRiskPanel",
]) {
  assert.equal(element(id).hidden, true, `stale Guided completion repopulated #${id}`);
  assert.doesNotMatch(surfaceText(id), /STALE_GUIDED/, `stale Guided response reached #${id}`);
}
assert.equal(element("guidedStart").disabled, false, "settled stale Guided request retained the provider lock");

detectMode = "body";
detectBody = guidedDetectBody;
guardMode = "deferred";
slowGuard = deferred();
element("editor").value = guidedSource;
await element("editor").emit("input");
const guardAbortBeforeReset = abortedGuardCalls;
const pendingGuardReset = element("scanBtn").click();
await flush();
await element("resetDemo").click();
await pendingGuardReset;
assert.equal(abortedGuardCalls, guardAbortBeforeReset + 1, "reset did not abort pending Guard work");
assert.equal(element("sensitiveDataMap").hidden, true, "reset during Guard retained the map");
assert.equal(element("guardRiskPanel").hidden, true, "reset during Guard retained prompt-risk state");
guardMode = "success";

reportMode = "deferred";
slowReport = deferred();
element("editor").value = guidedSource;
await element("editor").emit("input");
const reportAbortBeforeReset = abortedReportCalls;
const pendingReportReset = element("reportBtn").click();
await flush();
await element("resetDemo").click();
await pendingReportReset;
assert.equal(abortedReportCalls, reportAbortBeforeReset + 1, "reset did not abort pending report work");
assert.equal(element("executiveSummary").hidden, true, "reset during report retained executive state");
assert.equal(element("protectionReceipt").hidden, true, "reset during report retained receipt state");
reportMode = "success";

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
assert.equal(element("sensitiveDataMap").hidden, false, "direct scan did not expose Sensitive Data Map");
assert.equal(element("guardRiskPanel").hidden, false, "direct scan did not expose Guard / Prompt Risk");
assert.match(surfaceText("sensitiveDataMap"), /โทรศัพท์|PHONE/, "direct scan map omitted its entity type");
assert.doesNotMatch(surfaceText("sensitiveDataMap"), new RegExp(guidedPhone), "direct scan map exposed a detected raw value");
for (const id of ["executiveSummary", "protectionReceipt", "rawProtectedComparison"]) {
  assert.equal(element(id).hidden, true, `direct scan exposed unrelated #${id}`);
}
guardBody = {
  flagged: true,
  guard_findings: [{category: "<img src=x onerror=alert(1)>", severity: "<svg onload=alert(2)>"}],
};
await element("scanBtn").emit("click");
assert.ok(!element("guardBar").innerHTML.includes("<img"), "guard category rendered as HTML");
assert.ok(!element("guardBar").innerHTML.includes("<svg"), "guard severity rendered as HTML");
assert.match(element("guardBar").textContent, /ไม่พร้อม/, "invalid Guard enum was presented as a clean result");
assert.ok(!element("guardRiskList").innerHTML.includes("<img"), "Guard / Prompt Risk rendered category as HTML");
assert.ok(!element("guardRiskList").innerHTML.includes("<svg"), "Guard / Prompt Risk rendered severity as HTML");
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

detectMode = "body";
detectBody = guidedDetectBody;
guardMode = "network-error";
element("editor").value = guidedSource;
await element("editor").emit("input");
const guardNetworkRoundtrips = roundtripCalls;
await element("scanBtn").click();
assert.equal(roundtripCalls, guardNetworkRoundtrips, "guard network failure reached the provider boundary");
assert.equal(element("sensitiveDataMap").hidden, false, "guard network failure hid valid scan evidence");
assert.equal(element("guardRiskPanel").hidden, false, "guard network failure hid Guard availability");
assert.match(surfaceText("guardRiskPanel"), /ไม่พร้อม|ไม่สำเร็จ|เชื่อมต่อ/, "guard network failure was not presented distinctly");

detectMode = "network-error";
guardMode = "success";
element("editor").value = `${guidedSource} network-detect`;
await element("editor").emit("input");
await element("scanBtn").click();
assert.equal(element("sensitiveDataMap").hidden, true, "detect network failure exposed a map without evidence");
assert.equal(element("guardRiskPanel").hidden, true, "detect network failure exposed a Guard result");

roundtripMode = "network-error";
element("editor").value = `${guidedSource} network-roundtrip`;
await element("editor").emit("input");
const uncertainRoundtrips = roundtripCalls;
await element("send").click();
assert.equal(roundtripCalls, uncertainRoundtrips + 1, "network test did not reach /roundtrip exactly once");
assert.equal(element("send").disabled, true, "ambiguous network failure reopened the provider lane early");
for (const id of [
  "executiveSummary",
  "protectionReceipt",
  "rawProtectedComparison",
  "sensitiveDataMap",
  "guardRiskPanel",
]) {
  assert.equal(element(id).hidden, true, `roundtrip network failure exposed #${id}`);
}

roundtripMode = "invalid-json";
await element("send").click();
assert.equal(roundtripCalls, uncertainRoundtrips + 1, "ambiguous network retry created a possible duplicate provider call");
vm.runInContext("settleProviderLane(true)", context);
await element("send").click();
assert.equal(roundtripCalls, uncertainRoundtrips + 2, "provider lane did not reopen after deterministic settlement");
for (const id of ["executiveSummary", "protectionReceipt", "rawProtectedComparison"]) {
  assert.equal(element(id).hidden, true, `malformed roundtrip exposed #${id}`);
}

roundtripMode = "body";
roundtripBody = guidedSafeBody("คำตอบก่อนรายงานเสียหาย");
element("editor").value = guidedSource;
await element("editor").emit("input");
await element("send").click();
assert.equal(element("protectionReceipt").hidden, false, "safe setup did not produce a receipt");
reportMode = "invalid-json";
await element("reportBtn").click();
assert.equal(element("protectionReceipt").hidden, false, "malformed report discarded a valid protection receipt");
assert.equal(element("reportDownloadBtn").hidden, true, "malformed report enabled a stale download");
assert.match(surfaceText("executiveSummary"), /รายงาน.*(?:ไม่|ยัง)|(?:ไม่|ยัง).*รายงาน|รอ PDPA Report/, "malformed report was absent from the executive summary");
reportMode = "success";
detectMode = "body";

const assertRoundtripSuppressed = async (label, body) => {
  roundtripMode = "body";
  roundtripBody = body;
  element("editor").value = "synthetic source";
  await element("editor").emit("input");
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
  for (const id of ["executiveSummary", "protectionReceipt", "rawProtectedComparison"]) {
    assert.equal(element(id).hidden, true, `${label}: invalid response exposed #${id}`);
  }
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
seedSensitiveState();
document.body.classList.add("presenter-mode");
element("presenterModeBtn").setAttribute("aria-pressed", "true");
element("presentationStage").hidden = false;
element("fullscreenBtn").disabled = false;
await element("fullscreenBtn").click();
assert.equal(document.fullscreenElement, element("presentationStage"), "expiry setup did not enter real fullscreen state");
vm.runInContext("scheduleSessionExpiry(0)", context);
await new Promise(resolve => setTimeout(resolve, 5));
await flush();
assertSensitiveStateCleared("local session-expiry timer");
assert.match(element("meta").textContent, /เซสชันหมดอายุ/, "local expiry lacked visible recovery guidance");
assert.match(element("guidedStatus").textContent, /เซสชันหมดอายุ/, "local expiry lacked Guided recovery guidance");
assert.equal(vm.runInContext("authenticated", context), false, "local expiry did not end the authenticated UI state");
assert.equal(document.body.classList.contains("presenter-mode"), false, "local expiry retained Presenter Mode");
assert.equal(document.fullscreenElement, null, "local expiry retained fullscreen evidence");
assert.equal(element("presenterModeBtn").ariaPressed, "false", "local expiry retained Presenter Mode state");
assert.equal(element("accessCode").focused, true, "local expiry did not return focus to login recovery");

element("accessCode").value = "synthetic-access-code";
await element("loginBtn").emit("click");
logoutMode = "slow";
slowLogout = deferred();
seedSensitiveState();
const loginCallsBeforeSlowSuccess = loginCalls;
const pendingSlowLogoutSuccess = element("logoutBtn").emit("click");
await flush();
assert.equal(element("authCard").focused, true, "pending logout retained focus on a hidden control");
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
assert.equal(element("accessCode").focused, true, "slow successful logout did not return focus to access code");

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
assert.equal(element("logoutBtn").focused, true, "failed logout did not focus the visible retry control");

logoutMode = "network-error";
seedSensitiveState();
await element("logoutBtn").emit("click");
assertSensitiveStateCleared("failed logout network");
assert.match(element("authStatus").textContent, /session บนเซิร์ฟเวอร์อาจยังอยู่/);
assert.equal(element("logoutBtn").hidden, false, "network failure did not offer a retry");
assert.equal(element("logoutBtn").focused, true, "network logout failure did not focus the visible retry control");

logoutMode = "success";
await element("logoutBtn").emit("click");
assert.equal(element("authStatus").textContent, "ออกจากระบบแล้ว");
assert.equal(element("logoutBtn").hidden, true);

console.log("frontend contract ok: Sprint 2 presentation, request discipline, races, and session clearing are safe");
