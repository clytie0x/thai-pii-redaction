#!/usr/bin/env node
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import {fileURLToPath} from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const html = fs.readFileSync(path.join(root, "web", "app.html"), "utf8");
const source = fs.readFileSync(path.join(root, "web", "hosted3-app.js"), "utf8");

class FakeClassList {
  constructor() { this.values = new Set(); }
  add(...values) { values.forEach(value => this.values.add(value)); }
  remove(...values) { values.forEach(value => this.values.delete(value)); }
  contains(value) { return this.values.has(value); }
  toggle(value) { const active = !this.values.has(value); active ? this.values.add(value) : this.values.delete(value); return active; }
}

class FakeElement {
  constructor(id = "", tag = "div") {
    this.id = id; this.tagName = tag.toUpperCase(); this.hidden = false; this.disabled = false; this.value = ""; this.files = [];
    this.dataset = {}; this.attributes = new Map(); this.listeners = new Map(); this.children = []; this.classList = new FakeClassList();
    this.checked = false; this.open = false; this.focused = false; this.download = ""; this.href = ""; this._text = "";
  }
  get textContent() { return this.children.map(child => child.textContent || "").join(""); }
  set textContent(value) { this._text = ""; const text = String(value); this.children = text ? [new FakeText(text)] : []; }
  get firstChild() { return this.children[0] || null; }
  append(...nodes) { for (const node of nodes) this.children.push(typeof node === "string" ? new FakeText(node) : node); }
  removeChild(node) { const index = this.children.indexOf(node); if (index >= 0) this.children.splice(index, 1); }
  addEventListener(type, listener) { const values = this.listeners.get(type) || []; values.push(listener); this.listeners.set(type, values); }
  async emit(type, event = {}) { for (const listener of this.listeners.get(type) || []) await listener({target: this, currentTarget: this, preventDefault() {}, ...event}); }
  dispatchEvent(event) { void this.emit(event.type, event); return true; }
  async click() { if (!this.disabled) await this.emit("click"); }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  removeAttribute(name) { this.attributes.delete(name); }
  getAttribute(name) { return this.attributes.has(name) ? this.attributes.get(name) : null; }
  focus() { elements.forEach(node => { node.focused = false; }); this.focused = true; document.activeElement = this; }
  scrollIntoView() { this.scrolled = true; }
  querySelector(selector) { return queryChildren.get(`${this.id}:${selector}`) || null; }
  async requestFullscreen() { document.fullscreenElement = this; await document.emit("fullscreenchange"); }
  async requestSubmit() { await this.emit("submit"); }
  clickDownload() { downloads.push({name: this.download, href: this.href}); }
}
class FakeText { constructor(value) { this.textContent = String(value); } }

const elements = new Map();
for (const match of html.matchAll(/\bid="([^"]+)"/g)) elements.set(match[1], new FakeElement(match[1]));
const get = id => {
  if (!elements.has(id)) elements.set(id, new FakeElement(id));
  return elements.get(id);
};
get("appControls").setAttribute("inert", "");
get("h3Access").hidden = false;
for (const id of ["h3Chooser", "h3PdfTask", "h3TextTask", "h3InspectTask", "h3Preview", "h3Queue", "h3Result", "h3Recovery", "h3PriorityForm"]) get(id).hidden = true;
get("h3TextComparison").hidden = true; get("h3TextEvidence").hidden = true; get("h3ProtectedExtraction").hidden = true; get("h3TechnicalReceipt").hidden = false;

const taskButtons = ["pdf", "text", "inspect"].map(task => { const node = new FakeElement(`task-${task}`, "button"); node.dataset.h3Task = task; return node; });
const backButtons = ["pdf", "text", "inspect"].map(task => new FakeElement(`back-${task}`, "button"));
const token = new FakeElement("mode-token", "input"); token.value = "token"; token.checked = true;
const surrogate = new FakeElement("mode-surrogate", "input"); surrogate.value = "surrogate";
const samples = ["hr", "healthcare", "education", "customer", "government"].map(name => { const node = new FakeElement(`sample-${name}`, "button"); node.dataset.h3Sample = name; return node; });
const queryChildren = new Map([
  ["h3PdfTask:h2", get("h3PdfTitle")], ["h3TextTask:h2", get("h3TextTitle")], ["h3InspectTask:h2", get("h3InspectTitle")],
  ["h3SyntheticEvidence:summary", new FakeElement("synthetic-summary", "summary")],
]);

const documentListeners = new Map();
const downloads = [];
const document = {
  activeElement: get("body"), fullscreenElement: null, visibilityState: "visible",
  getElementById: get,
  querySelector(selector) { if (selector === "input[name=h3Mode]:checked") return token.checked ? token : surrogate; return null; },
  querySelectorAll(selector) {
    if (selector === "[data-h3-task]") return taskButtons;
    if (selector === ".h3-back") return backButtons;
    if (selector === "input[name=h3Mode]") return [token, surrogate];
    if (selector === "[data-h3-sample]") return samples;
    return [];
  },
  createElement(tag) {
    const node = new FakeElement("", tag);
    if (tag === "a") node.click = () => node.clickDownload();
    return node;
  },
  createTextNode: value => new FakeText(value),
  addEventListener(type, listener) { const values = documentListeners.get(type) || []; values.push(listener); documentListeners.set(type, values); },
  async emit(type, event = {}) { for (const listener of documentListeners.get(type) || []) await listener({type, ...event}); },
  async exitFullscreen() { this.fullscreenElement = null; await this.emit("fullscreenchange"); },
};

const windowListeners = new Map();
const location = {pathname: "/app", hash: "#guided-demo"};
const history = {replaceState(_state, _title, value) { location.pathname = value; location.hash = ""; }};
const navigator = {onLine: true, clipboard: {writes: [], async writeText(value) { this.writes.push(value); }}};
const windowObject = {
  addEventListener(type, listener) { const values = windowListeners.get(type) || []; values.push(listener); windowListeners.set(type, values); },
  async emit(type, event = {}) { for (const listener of windowListeners.get(type) || []) await listener({type, ...event}); },
};

const SERVER_MS = 1_800_000_000_000;
const SESSION_EXPIRY_MS = SERVER_MS + 1_800_000;
let timingHeadersValid = true;
const timedHeaders = serviceClass => new Headers(timingHeadersValid ? {
  "content-type": "application/json", "X-AIGuard-Server-Time-Ms": String(SERVER_MS),
  "X-AIGuard-Session-Expires-At-Ms": String(SESSION_EXPIRY_MS), "X-AIGuard-Service-Class": serviceClass,
} : {"content-type": "application/json", "X-AIGuard-Service-Class": serviceClass});
const jsonResponse = (status, body, headers = new Headers({"content-type": "application/json"})) => ({status, ok: status >= 200 && status < 300, headers, async json() { return body; }});
const requestLog = [];
let authenticated = false;
let activeClass = "standard";
let inspectDeferred = null;
let customExecuteValid = true;
let joinMode = "success";
let claimResponses = [];
let endMode = "success";
let startMode = "lost_success";
let loginMode = "success";
let inspectAuthFailure = false;
let executeMode = "success";
let cancelMode = "success";
let queueStatusState = "absent";
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return {promise, resolve}; };
const fetch = async (url, options = {}) => {
  const body = typeof options.body === "string" ? JSON.parse(options.body) : options.body;
  requestLog.push({url, method: options.method || "GET", body});
  if (url === "/api/health") return jsonResponse(200, {status: "ok", version: "3.0.0"});
  if (url === "/api/auth/session") return authenticated
    ? jsonResponse(200, {authenticated: true, expires_in: 1800}, timedHeaders(activeClass))
    : jsonResponse(401, {error: {code: "authentication_required"}});
  if (url === "/api/auth/guest") { authenticated = true; activeClass = "standard"; if (startMode === "lost_success") { startMode = "success"; throw new Error("synthetic lost response"); } return jsonResponse(201, {scope: "public_guest"}, timedHeaders("standard")); }
  if (url === "/api/auth/guest/end") { if (endMode === "network") throw new Error("synthetic disconnect"); authenticated = false; return jsonResponse(204, null); }
  if (url === "/api/auth/login") { authenticated = true; activeClass = "priority"; if (loginMode === "lost_success") { loginMode = "success"; throw new Error("synthetic lost response"); } return jsonResponse(204, null); }
  if (url === "/api/auth/logout") { if (endMode === "network") throw new Error("synthetic disconnect"); authenticated = false; return jsonResponse(204, null); }
  if (url === "/api/detect") {
    if (inspectAuthFailure) { authenticated = false; return jsonResponse(401, {error: {code: "authentication_required"}}); }
    if (inspectDeferred) return inspectDeferred.promise;
    return jsonResponse(200, {detected_entity_count: 2, entity_type_counts: {PHONE: 1, EMAIL: 1}, highlights: [{start: 5, end: 17, data_type: "PHONE"}, {start: 24, end: 44, data_type: "EMAIL"}]});
  }
  if (url === "/api/guard") return jsonResponse(200, {flagged: false, guard_findings: []});
  if (url === "/api/analyze-report") return jsonResponse(200, {overall_score: 20, overall_grade: "A", report_pdf_b64: "JVBERg=="});
  if (url === "/api/protection-preview") return jsonResponse(200, {
    source_kind: "custom_standard", protected_text: "[NAME_1] โทร [PHONE_1]", detected_entity_count: 2,
    entity_type_counts: {NAME: 1, PHONE: 1}, highlights: [{start: 0, end: 8, data_type: "NAME"}],
    section26_categories: ["HEALTH"], guard_findings: [], outbound_gate: {status: "no_residual_signal_detected", residual_count: 0, human_review_required: true},
    can_execute: true, ticket: "preview-ticket", queue_join_before_unix: Math.floor((SERVER_MS + 600_000) / 1000),
  }, timedHeaders("standard"));
  if (url === "/api/document-preview") return jsonResponse(200, {
    source_kind: "standard_document", protected_text: "ประวัติย่อ [NAME_1]", protected_markdown: "# Protected resume",
    detected_entity_count: 1, entity_type_counts: {NAME: 1}, highlights: [], section26_categories: [], guard_findings: [],
    omitted_visual_page_numbers: [1], outbound_gate: {status: "no_residual_signal_detected", residual_count: 0, human_review_required: true},
    can_execute: true, ticket: "document-ticket", queue_join_before_unix: Math.floor((SERVER_MS + 600_000) / 1000),
  }, timedHeaders("standard"));
  if (url === "/api/provider-queue/join") return joinMode === "queue_full"
    ? jsonResponse(429, {error: {code: "queue_full"}})
    : jsonResponse(201, {state: "queued", queue_capability: "queue-capability", position: 1, queue_expires_at_unix: Math.floor((SERVER_MS + 500_000) / 1000)});
  if (url === "/api/provider-queue/claim") return jsonResponse(200, claimResponses.shift() || {state: "claim_ready", revision: 1, claim_token: "claim-token", claim_expires_at_unix: Math.floor((SERVER_MS + 20_000) / 1000)});
  if (url === "/api/protection-execute") {
    if (executeMode === "network") throw new Error("synthetic lost execute response");
    return jsonResponse(200, customExecuteValid ? {
    protected_text: "[NAME_1] โทร [PHONE_1]", restored_text: "ผลสังเคราะห์ที่กู้คืนแล้ว", detected_entity_count: 2,
    entity_type_counts: {NAME: 1, PHONE: 1}, section26_categories: ["HEALTH"], guard_findings: [], warnings: [],
    safety: {status: "pass", residual_count: 0}, restoration: {status: "complete", replaced_count: 2, leftover_count: 0},
    provider: {id: "tokenmind", model: "thaillm-8b", attempt_count: 1},
    receipt: {request_id: "req_synthetic", provider_attempt_count: 1, duration_ms: 1250},
  } : {
    protected_text: "[NAME_1]", restored_text: "UNSAFE RESTORED", detected_entity_count: 1, entity_type_counts: {NAME: 1},
    section26_categories: [], guard_findings: [], warnings: [], safety: {status: "pass", residual_count: 0},
    restoration: {status: "incomplete", replaced_count: 0, leftover_count: 1}, provider: {attempt_count: 1}, receipt: {request_id: "req_invalid"},
    });
  }
  if (url === "/api/document-execute") return jsonResponse(200, {
    protected_markdown: "> Protected/pseudonymized, not anonymous.\n\n# Protected resume\n\n## Identity\n\n[NAME_1]\n", protected_plain_text: "Protected resume\n\nIdentity\n[NAME_1]\n", protected_text: "ประวัติย่อ [NAME_1]",
    protected_document_ast: {ordered_sections: [{role: "identity", segment_ids: ["seg_001"]}]}, warnings: ["Human review is required."], omitted_visual_page_numbers: [1],
    receipt: {source_receipt_id: "src_synthetic", parser_revision: "parser-v1", extraction_revision: "extract-v1", omitted_visual_page_numbers: [1], duration_ms: 900},
  });
  if (url === "/api/provider-queue/cancel") { if (cancelMode === "network") throw new Error("synthetic lost cancel response"); return jsonResponse(204, null); }
  if (url === "/api/provider-queue/status") return jsonResponse(200, {state: queueStatusState, position: queueStatusState === "queued" ? 2 : null, queue_expires_at_unix: Math.floor((SERVER_MS + 500_000) / 1000)});
  throw new Error(`unexpected request ${url}`);
};

let monotonic = 10_000;
const context = vm.createContext({
  AbortController, Array, Blob, Event: class { constructor(type, init = {}) { this.type = type; Object.assign(this, init); } }, Headers, JSON, Math, Number, Object, Promise, String, Uint8Array, URL,
  atob, clearTimeout, confirm: () => true, console, document, fetch, history, location, navigator,
  performance: {now: () => { monotonic += 5; return monotonic; }}, setTimeout, window: windowObject,
});
windowObject.document = document; windowObject.location = location; windowObject.window = windowObject;
vm.runInContext(source, context, {filename: "web/hosted3-app.js"});
const flush = async (rounds = 6) => { for (let index = 0; index < rounds; index += 1) await new Promise(resolve => setImmediate(resolve)); };

await flush();
assert.equal(get("appControls").getAttribute("inert"), null, "bootstrap did not release inert controls after the signed-out session response");
assert.equal(location.hash, "", "gate-first deep link was not normalized");
assert.equal(get("h3StartStandard").focused, true, "signed-out deep link did not focus the access gate");
assert.equal(requestLog.filter(item => item.url.includes("preview") || item.url.includes("execute")).length, 0, "startup made protected/provider work");

await get("h3StartStandard").click(); await flush();
assert.equal(get("h3Chooser").hidden, false, "Standard start did not reveal the task chooser");
assert.equal(get("h3InspectTask").hidden, false, "guided-demo did not restore the active Inspect task");
assert.equal(queryChildren.get("h3SyntheticEvidence:summary").focused, true, "guided-demo did not focus its visible disclosure");

queueStatusState = "queued";
await windowObject.emit("pageshow", {persisted: true}); await flush();
assert.equal(get("h3Queue").hidden, false, "BFCache/status recovery did not expose the orphan queue");
const claimsBeforeStatusOnlyLifecycle = requestLog.filter(item => item.url === "/api/provider-queue/claim").length;
document.visibilityState = "hidden"; await document.emit("visibilitychange"); document.visibilityState = "visible"; await document.emit("visibilitychange"); await windowObject.emit("online"); await flush();
assert.equal(requestLog.filter(item => item.url === "/api/provider-queue/claim").length, claimsBeforeStatusOnlyLifecycle, "status-only recovery attempted a claim without capability");
assert.equal(requestLog.filter(item => item.url.includes("execute")).length, 0, "status-only recovery attempted execute");
queueStatusState = "absent"; await get("h3CancelQueue").click(); await flush();
assert.equal(get("h3Chooser").hidden, false, "status-only cancel did not return to the visible chooser");
assert.equal(get("h3ChooserTitle").focused, true, "status-only cancel focused a hidden task control");

const requestsBeforeSample = requestLog.length;
await samples[0].click();
assert.match(get("h3InspectText").value, /ข้อมูลสังเคราะห์ HR/, "synthetic sample did not populate Inspect");
assert.equal(requestLog.length, requestsBeforeSample, "synthetic selection submitted automatically");

await get("h3Detect").click(); await flush();
assert.match(get("h3InspectResult").textContent, /Detected PII: 2/, "Detect result did not render structurally");
assert.match(get("h3InspectMap").textContent, /PHONE · 1/, "Sensitive Data Map did not project current counts");
assert.ok(!get("h3InspectMap").textContent.includes("081-"), "Sensitive Data Map exposed a detected value");
assert.match(get("h3ServiceLiveness").textContent, /liveness only, not provider readiness/, "health overclaimed readiness");

inspectDeferred = deferred();
const slowDetectClick = get("h3Detect").click();
await flush(1);
await get("h3Guard").click(); await flush();
assert.match(get("h3InspectResult").textContent, /Guard: no heuristic finding/, "Guard did not render its non-blocking current result");
inspectDeferred.resolve(jsonResponse(200, {detected_entity_count: 99, entity_type_counts: {STALE: 99}, highlights: []}));
await slowDetectClick; await flush(); inspectDeferred = null;
assert.ok(!get("h3InspectResult").textContent.includes("99"), "stale Inspect completion repainted a newer action");
await get("h3Report").click(); await flush();
assert.match(get("h3InspectResult").textContent, /PDPA score: 20/, "PDPA report summary did not render");
assert.equal(get("h3DownloadReport").hidden, false, "explicit report download was not enabled after a current report");
await get("h3DownloadReport").click();
assert.equal(downloads.at(-1)?.name, "ai-guard-pdpa-report.pdf", "PDPA report download did not use the reviewed bytes");

await backButtons[2].click(); await taskButtons[1].click();
get("h3Text").value = "ข้อมูลสังเคราะห์ นายทดสอบ โทร 081-000-1020";
await get("h3Text").emit("input");
const beforePreview = requestLog.length;
await get("h3TextPreview").click(); await flush();
assert.equal(requestLog.slice(beforePreview).some(item => item.url.includes("execute")), false, "preview contacted execute/provider");
assert.equal(get("h3Preview").hidden, false, "protected preview did not render");
assert.equal(get("h3PreviewTitle").focused, true, "custom preview did not focus the completed preview heading");
assert.match(get("h3PreviewSection26").textContent, /HEALTH/, "Core-returned Section 26 evidence was not projected");
assert.ok(!get("h3PreviewMap").textContent.includes("จาก 46 code points"), "protected-output offsets were misrepresented as raw-source positions");

joinMode = "queue_full";
await get("h3Approve").click(); await flush();
assert.equal(get("h3Preview").hidden, false, "queue saturation discarded a still-valid protected preview");
assert.equal(get("h3Approve").disabled, false, "queue saturation left approval disabled");
assert.match(get("h3RecoveryCopy").textContent, /Protected preview ยังอยู่/, "queue saturation lost retry truth");
await get("h3RecoveryAction").click(); joinMode = "success";
claimResponses = [
  {state: "queued", revision: 1, reason: "claim_missed_requeued", position: 5, queue_expires_at_unix: Math.floor((SERVER_MS + 500_000) / 1000)},
  {state: "claim_ready", revision: 2, claim_token: "claim-token", claim_expires_at_unix: Math.floor((SERVER_MS + 20_000) / 1000)},
];
const claimsBeforeOfflineJoin = requestLog.filter(item => item.url === "/api/provider-queue/claim").length;
navigator.onLine = false;
await get("h3Approve").click(); await flush(12);
assert.equal(requestLog.filter(item => item.url === "/api/provider-queue/claim").length, claimsBeforeOfflineJoin, "offline queue attempted a claim");
assert.match(get("h3QueueFacts").textContent, /Offline.*ไม่มีการส่งซ้ำ/s, "offline queue did not expose status-unknown truth");
assert.equal(get("h3Text").disabled, true, "queued text remained editable");
assert.equal(taskButtons[0].disabled, true, "queued task navigation remained enabled");
assert.equal(backButtons[1].disabled, true, "queued Back remained enabled");
assert.equal(get("h3EndAuthority").disabled, true, "queued End access remained enabled");
cancelMode = "network"; queueStatusState = "queued"; await get("h3CancelQueue").click(); await flush();
assert.equal(get("h3Queue").hidden, false, "unconfirmed cancel discarded queue state");
assert.match(get("h3QueueFacts").textContent, /ยืนยันการยกเลิกไม่ได้/, "unconfirmed cancel claimed success");
assert.equal(get("h3CancelQueue").focused, true, "unconfirmed cancel did not focus retry");
cancelMode = "success"; queueStatusState = "absent";
navigator.onLine = true; await windowObject.emit("online"); await flush(12);
const ordered = requestLog.map(item => item.url);
const previewAt = ordered.lastIndexOf("/api/protection-preview");
const joinAt = ordered.lastIndexOf("/api/provider-queue/join");
const claimAt = ordered.lastIndexOf("/api/provider-queue/claim");
const executeAt = ordered.lastIndexOf("/api/protection-execute");
assert.ok(previewAt >= 0 && previewAt < joinAt && joinAt < claimAt && claimAt < executeAt, "provider ordering is not preview → join → claim → execute");
assert.ok(ordered.filter(value => value === "/api/provider-queue/claim").length >= 2, "first claim miss did not requeue before automatic execute");
assert.equal(get("h3Result").hidden, false, "verified custom result did not render");
assert.equal(get("h3ResultTitle").textContent, "Restored provider result", "custom result heading is not explicit");
assert.equal(get("h3ResultTitle").focused, true, "custom completion did not focus its result heading");
assert.match(get("h3ExecutiveCopy").textContent, /residual และ restoration gates ผ่านครบ/, "Executive Summary is not gate-derived");
assert.equal(get("h3EvidenceResidual").textContent, "0 สัญญาณ · pass", "residual evidence is missing");
assert.equal(get("h3EvidenceRestoration").textContent, "complete · leftover 0", "leftover evidence is missing");
assert.match(get("h3Receipt").textContent, /aiguard-portable-receipt-v1.*restored_text_included/s, "custom receipt download surface lacks provenance envelope");
assert.match(get("h3ResultBody").textContent, /ผลสังเคราะห์ที่กู้คืนแล้ว/, "restored result is absent after exact gates");
assert.equal(get("h3ProtectedExtraction").hidden, true, "custom result exposed the PDF-only extraction disclosure");
assert.equal(get("h3TextComparison").hidden, false, "custom result omitted working comparison");

await get("h3CopyArtifact").click();
assert.match(navigator.clipboard.writes[0], /protected\/pseudonymized text artifact/, "copy omitted automatic provenance");
assert.ok(!navigator.clipboard.writes[0].includes("ผลสังเคราะห์ที่กู้คืนแล้ว"), "portable protected artifact included restored PII context");
await get("h3Present").click();
assert.equal(document.fullscreenElement, get("h3Result"), "Presenter did not enter fullscreen for a verified result");
assert.equal(get("h3Result").dataset.presenterPrivate, "true", "custom result did not mark raw comparison private for Presenter");
await document.exitFullscreen();
assert.equal(get("h3Present").focused, true, "Presenter exit did not restore focus");

endMode = "network";
await get("h3EndAuthority").click(); await flush();
assert.equal(get("h3Chooser").hidden, false, "failed End access presented a false signed-out gate");
assert.match(get("h3AuthorityStatus").textContent, /session เดิมอาจยังใช้งานอยู่/, "failed End access did not retain truthful authority state");
assert.equal(get("h3EndAuthority").focused, true, "failed End access did not focus its retry action");
assert.equal(get("h3Result").hidden, true, "failed End access retained result content");
assert.equal(get("h3InspectResult").textContent, "", "failed End access retained Inspect result content");
endMode = "success";
await get("h3EndAuthority").click(); await flush();
assert.equal(get("h3Result").hidden, true, "logout retained a result surface");
assert.equal(get("h3Text").value, "", "logout retained custom source text");
assert.equal(get("h3Receipt").textContent, "", "logout retained receipt evidence");

loginMode = "lost_success";
await get("h3ShowPriority").click(); get("h3Invite").value = "synthetic-priority-code"; await get("h3PriorityForm").emit("submit"); await flush();
assert.equal(get("h3ClassChip").textContent, "Priority Invite", "Priority login did not recover its service class");
assert.equal(get("h3Invite").value, "", "Priority credential remained in the DOM");
await get("h3EndAuthority").click(); await flush();
await get("h3StartStandard").click(); await flush();
const deepLinks = [
  ["#privacy-scan", "h3InspectTask", "h3Detect"], ["#pdpa-report", "h3InspectTask", "h3Report"],
  ["#safe-ai", "h3TextTask", "h3Text"], ["#how-it-works", "h3TextTask", "h3TextTitle"],
  ["#providerEvidenceCard", "h3TextTask", "h3TextTitle"],
];
for (const [hash, panel, focus] of deepLinks) {
  location.hash = hash; await windowObject.emit("hashchange");
  assert.equal(get(panel).hidden, false, `${hash} did not reveal its active task`);
  assert.equal(get(focus).focused, true, `${hash} did not focus its visible owner`);
  assert.equal(location.hash, "", `${hash} was not normalized after restoration`);
}
for (const hash of ["#guided-demo", "#synthetic-demo"]) {
  location.hash = hash; await windowObject.emit("hashchange");
  assert.equal(get("h3InspectTask").hidden, false, `${hash} did not reveal Inspect`);
  assert.equal(get("h3SyntheticEvidence").open, true, `${hash} did not open its active disclosure`);
  assert.equal(queryChildren.get("h3SyntheticEvidence:summary").focused, true, `${hash} did not focus the disclosure summary`);
}

get("h3InspectText").value = "ข้อมูลที่ต้องล้างเมื่อ session หมด"; await get("h3InspectText").emit("input");
inspectAuthFailure = true; await get("h3Detect").click(); await flush(); inspectAuthFailure = false;
assert.equal(get("h3Access").hidden, false, "Inspect 401 did not return to access gate");
assert.equal(get("h3InspectText").value, "", "Inspect 401 retained raw input");
assert.equal(get("h3StartStandard").focused, true, "Inspect 401 did not focus access recovery");
await get("h3StartStandard").click(); await flush();

await taskButtons[1].click();
get("h3Text").value = "ข้อมูลสังเคราะห์สำหรับ claim miss"; await get("h3Text").emit("input");
await get("h3TextPreview").click(); await flush();
const executesBeforeSecondMiss = requestLog.filter(item => item.url === "/api/protection-execute").length;
claimResponses = [{state: "expired", revision: 2, reason: "claim_missed_expired", position: null}];
await get("h3Approve").click(); await flush();
assert.match(get("h3RecoveryCopy").textContent, /Automatic start ไม่สำเร็จสองครั้ง/, "second claim miss lost its terminal recovery truth");
assert.equal(requestLog.filter(item => item.url === "/api/protection-execute").length, executesBeforeSecondMiss, "second claim miss contacted provider");

await backButtons[1].click(); await taskButtons[0].click();
const selectedPdf = {name: "synthetic-resume.pdf", type: "application/pdf", size: 2048};
const beforeSelection = requestLog.length;
get("h3Pdf").files = [selectedPdf]; await get("h3Pdf").emit("change");
assert.equal(requestLog.length, beforeSelection, "PDF selection uploaded automatically");
assert.match(get("h3PdfMeta").textContent, /ยังไม่อัปโหลด/, "selected PDF state did not disclose no-upload truth");
await get("h3PdfPreview").click(); await flush();
assert.equal(requestLog.at(-1).url, "/api/document-preview", "explicit PDF upload did not use document preview");
assert.match(get("h3PreviewWarning").textContent, /หน้า visual ที่ละไว้: 1/, "PDF preview omitted the affected visual page warning");
await get("h3Approve").click(); await flush(12);
assert.equal(requestLog.some(item => item.url === "/api/document-execute"), true, "PDF claim did not execute the document path");
assert.match(get("h3ResultBody").textContent, /Protected resume.*Identity/s, "PDF primary result did not render the semantic Markdown subset");
assert.ok(!get("h3ResultBody").textContent.includes("\\[NAME\\_1\\]"), "safe Markdown escapes remained visible in the reading surface");
assert.match(get("h3ResultBody").textContent, /\[NAME_1\]/, "safe Markdown escape decoding lost protected text");
assert.equal(get("h3TextComparison").hidden, true, "PDF exposed raw-versus-protected source comparison");
assert.equal(get("h3ResultTitle").textContent, "Protected Markdown", "PDF result heading is not task-specific");
assert.equal(get("h3ResultTitle").focused, true, "PDF completion did not focus its result heading");
assert.equal(get("h3TextEvidence").hidden, true, "PDF exposed custom restoration evidence");
assert.equal(get("h3ProtectedExtraction").hidden, false, "PDF omitted Protected extraction disclosure");
assert.equal(get("h3TechnicalReceipt").hidden, false, "PDF omitted Technical receipt disclosure");
assert.ok(!get("h3ResultBody").textContent.includes("restored"), "PDF result implied PII restoration");
await get("h3CopyArtifact").click();
assert.match(navigator.clipboard.writes.at(-1), /PII was not restored/, "PDF artifact omitted no-restoration provenance");
assert.match(get("h3Receipt").textContent, /source_pdf_unchanged.*text_layer_only.*ocr_or_visual_layout_interpreted/s, "PDF receipt JSON lacks mandatory portable provenance");

await backButtons[0].click(); await taskButtons[1].click();
executeMode = "network"; customExecuteValid = true;
get("h3Text").value = "ข้อมูลสังเคราะห์สำหรับ uncertain execute"; await get("h3Text").emit("input");
await get("h3TextPreview").click(); await flush(); await get("h3Approve").click(); await flush(12);
assert.match(get("h3QueueFacts").textContent, /สถานะ provider ยังไม่แน่ชัด.*ห้าม preview, join หรือส่งซ้ำ/s, "lost execute response invited an unsafe retry");
assert.equal(get("h3Recovery").hidden, true, "lost execute response exposed generic Retry recovery");
assert.equal(get("h3Text").disabled, true, "uncertain provider state left source editable");
assert.equal(taskButtons[2].disabled, true, "uncertain provider state left task switching enabled");
assert.equal(get("h3ClearRunning").hidden, false, "uncertain provider state omitted truthful Clear action");
await get("h3ClearRunning").click(); executeMode = "success";

await backButtons[1].click(); await taskButtons[1].click();
customExecuteValid = false;
get("h3Text").value = "ข้อมูลสังเคราะห์ นายทดสอบ"; await get("h3Text").emit("input");
await get("h3TextPreview").click(); await flush(); await get("h3Approve").click(); await flush(12);
assert.equal(get("h3Result").hidden, true, "incomplete restoration rendered a result");
assert.equal(get("h3Recovery").hidden, false, "incomplete restoration did not fail closed into recovery");
assert.ok(!get("h3ResultBody").textContent.includes("UNSAFE RESTORED"), "unsafe restored text reached the DOM");

timingHeadersValid = false;
get("h3Text").value = "ข้อมูลสังเคราะห์สำหรับ timing"; await get("h3Text").emit("input");
const beforeTimingFailure = requestLog.filter(item => item.url === "/api/protection-preview").length;
await get("h3TextPreview").click(); await flush();
assert.equal(requestLog.filter(item => item.url === "/api/protection-preview").length, beforeTimingFailure, "missing timing headers allowed preview work");
assert.match(get("h3RecoveryCopy").textContent, /ยังไม่ส่งข้อความที่ป้องกันแล้วไปยัง Pathumma/, "timing failure copy lost the provider boundary");
assert.equal(get("h3RecoveryAction").focused, true, "timing failure did not focus its Retry action");

console.log("Stage 6 frontend behavior contract ok: all deep links, non-submitting scenarios, Inspect/report parity, preview/queue/claim ordering, custom/PDF gates, presenter focus, provenance, and clearing");
