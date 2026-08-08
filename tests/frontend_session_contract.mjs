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
}

const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, new FakeElement(id));
  return elements.get(id);
};
const downloads = [];
const document = {
  getElementById: element,
  querySelectorAll: () => [],
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
let slowDetect = deferred();
let detectCalls = 0;
let guardCalls = 0;
const initialSession = deferred();
let sessionCalls = 0;
let loginCalls = 0;
let logoutMode = "success";
let slowLogout = null;
const fetch = (url, _options = {}) => {
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
    if (roundtripMode === "deferred") return slowRoundtrip.promise;
    if (roundtripMode === "body") return Promise.resolve(response(200, roundtripBody));
    if (roundtripMode === "unauthorized") {
      return Promise.resolve(response(401, {error: {code: "authentication_required"}}));
    }
  }
  if (url === "/api/detect") {
    detectCalls += 1;
    return slowDetect.promise;
  }
  if (url === "/api/guard") {
    guardCalls += 1;
    return Promise.resolve(response(200, {flagged: false, guard_findings: []}));
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

element("accessCode").value = "synthetic-access-code";
await element("loginBtn").emit("click");
assert.equal(sessionCalls, 2, "login did not start a fresh session check");
assert.equal(element("send").disabled, false, "successful login did not enable business controls");

initialSession.resolve(response(401, {authenticated: false}));
await flush();
await flush();
assert.equal(
  element("send").disabled,
  false,
  "stale initial session response cleared a newer successful login",
);
vm.runInContext(
  'renderHighlight("😀 โทร 081-234-5678", [{start: 6, end: 18, data_type: "PHONE"}])',
  context,
);
assert.match(
  element("highlight").innerHTML,
  />081-234-5678<\/mark>/,
  "astral Unicode offset did not highlight the exact phone substring",
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
  element("reportMeta").textContent = "SENSITIVE_REPORT";
};
const assertSensitiveStateCleared = label => {
  assert.equal(element("accessCode").value, "", `${label}: access code retained`);
  assert.equal(element("editor").value, "", `${label}: editor retained source text`);
  assert.equal(element("highlight").textContent, "", `${label}: highlight retained source text`);
  assert.equal(element("masked").textContent, "ยังไม่ได้ส่ง", `${label}: masked text retained`);
  assert.equal(element("restored").textContent, "ยังไม่ได้ส่ง", `${label}: restored text retained`);
  assert.equal(element("evidenceSanitized").textContent, "ยังไม่มีข้อมูล", `${label}: evidence retained`);
  assert.equal(element("guardBar").textContent, "", `${label}: guard result retained`);
  assert.equal(element("reportMeta").textContent, "", `${label}: report result retained`);
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
  "NEW_EDITOR",
  "stale detect response overwrote the newer editor text",
);
assert.equal(guardCalls, 0, "stale detect response started a guard request");

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
await element("send").emit("click");
assertSensitiveStateCleared("401 response");
assert.equal(element("send").disabled, true, "401 did not disable business controls");
assert.equal(downloads.length, 0, "401 response triggered a download");

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
