#!/usr/bin/env node
/* Stage 6 caller-source contract. Browser integration exercises the rendered surface. */
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const read = name => fs.readFileSync(path.join(root, "web", name), "utf8");
const app = read("app.html");
const source = read("hosted3-app.js");
const css = read("app.css");
const nginx = read("nginx.conf");
const developers = read("developers.html");
const home = read("index.html");
const privacy = read("privacy.html");
const help = read("help.html");
const terms = read("terms.html");
const localEdge = read("nginx.stage6-edge.conf");

assert.match(app, /<div id="appControls" inert>/, "no-JS app controls must fail closed");
assert.match(app, /id="appBootstrapNotice"/, "recovery notice must be authored outside inert controls");
assert.match(app, /src="\/hosted3-app\.js" defer/, "Stage 6 runtime is not exact local asset");
assert.doesNotMatch(app, /<script>([\s\S]*?)<\/script>/, "inline executable script bypasses CSP review");
assert.doesNotMatch(app, /legacy-stage6-retained|id="accessCode"|id="presenterModeBtn"|id="providerEvidenceCard"/, "hidden legacy workflow markup remains in the production App");
assert.match(app, /<details class="app-mobile-nav">[\s\S]*href="\/privacy"[\s\S]*href="\/help"/, "App lacks a no-JavaScript mobile navigation");
assert.match(app, /<details class="app-mobile-nav">[\s\S]*href="\/terms"[\s\S]*href="\/developers"/, "App no-JavaScript mobile navigation omits public routes");
assert.equal((app.match(/<h1\b/g) || []).length, 1, "App must retain one stable page H1 across authority states");
assert.doesNotMatch(app, /id="h3InspectResult"[^>]*aria-live|id="h3AuthorityStatus"[^>]*role="status"/, "App duplicates global live announcements");
for (const id of ["h3StartStandard", "h3ShowPriority", "h3PdfTask", "h3TextTask", "h3InspectTask", "h3Preview", "h3Queue", "h3Result", "h3Recovery"]) assert.ok(app.includes(`id="${id}"`), `missing Stage 6 surface: ${id}`);
assert.match(app, /id="h3ChooserTitle" tabindex="-1"/, "Hosted chooser heading is not programmatically focusable");
assert.match(app, /Start Standard access/, "Standard entry is not primary");
assert.match(app, /Use Priority Invite/, "Priority entry is absent");
assert.match(app, /PDF → Protected Markdown/, "featured PDF journey is absent");
assert.match(app, /เลือกข้อความได้/, "PDF text-layer limit is absent");
assert.match(app, /ไม่ถูกส่งให้ Pathumma/, "raw-PDF boundary is absent");
assert.match(app, /id="synthetic-demo"/, "developer synthetic deep link has no inert destination");

for (const forbidden of ["localStorage", "sessionStorage", "indexedDB", "caches.", "serviceWorker", "history.pushState", "Date.now("]) assert.ok(!source.includes(forbidden), `forbidden browser persistence/time source: ${forbidden}`);
assert.ok(source.includes("performance.now()"), "timing is not performance.now anchored");
assert.ok(source.includes("X-AIGuard-Server-Time-Ms") && source.includes("X-AIGuard-Session-Expires-At-Ms"), "timing headers are not consumed");
assert.ok(source.includes("timingUnavailable") && source.includes("timing_unavailable"), "timing failure does not fail closed");
assert.ok(source.includes("state.generation += 1") && source.includes("isCurrent(generation)"), "stale response generation ownership is absent");
assert.ok(source.includes("state.claimAbort.abort()") && source.includes("beforeunload"), "pending queue authority is not invalidated");
assert.ok(source.includes("document.visibilityState === \"visible\"") && source.includes("navigator.onLine"), "foreground/offline queue guard missing");
assert.ok(source.includes("state.providerRunning"), "provider operation ownership missing");

const order = value => source.indexOf(value);
for (const endpoint of ["/api/auth/guest", "/api/auth/login", "/api/protection-preview", "/api/document-preview", "/api/provider-queue/join", "/api/provider-queue/claim", "/api/protection-execute", "/api/document-execute"]) assert.ok(source.includes(endpoint), `caller misses approved endpoint ${endpoint}`);
assert.ok(order("/api/provider-queue/join") < order("/api/provider-queue/claim") && order("/api/provider-queue/claim") < order("/api/protection-execute"), "provider execution is not ordered after queue claim");
assert.ok(app.includes("Approve and join queue") && source.includes("claim_ready") && source.includes("executeClaim"), "explicit approval and automatic matching claim path missing");
assert.ok(source.includes("protected_text: state.preview.protected_text") && source.includes("PII was not restored"), "PDF execution/artifact restoration boundary missing");
assert.ok(source.includes("document.createElement(\"pre\")") && !source.includes("innerHTML ="), "result rendering is not semantic escaped DOM creation");
assert.ok(source.includes("provenanceHeader") && source.includes("ai-guard-protected.md") && source.includes("ai-guard-receipt.json"), "portable artifact provenance paths missing");

for (const marker of ["location = /developers", "location = /hosted3-app.js", "try_files /developers.html =404", "try_files /hosted3-app.js =404"]) assert.ok(nginx.includes(marker), `exact web allowlist missing ${marker}`);
assert.ok(read("Dockerfile").includes("hosted3-app.js") && read("Dockerfile").includes("developers.html"), "Docker does not copy Stage 6 assets");
assert.ok(css.includes(".hosted3-workspace") && css.includes("@media(max-width:760px)"), "Stage 6 responsive workspace styles missing");
assert.ok(Buffer.byteLength(css, "utf8") < 30000, "App stylesheet retains the legacy dashboard payload");
assert.doesNotMatch(css, /presentation-stage|body\.presenter-mode|safe-hero|guided-shell|scenario-gallery/, "legacy dashboard selectors remain in production CSS");
assert.match(css, /data-presenter-private="true"[^}]*#h3ResultBody/, "Presenter does not hide custom restored content");
assert.match(css, /#h3PresenterPrivateNotice/, "Presenter has no private-content replacement notice");
assert.match(developers, /same-origin application contract/, "developers page overclaims public API access");
assert.match(developers, /40 exact same-origin locations/, "developers page lacks route truth");
assert.match(developers, /liveness only/, "developers page overclaims health/provider readiness");
for (const rateTruth of ["30/minute global, burst 10", "12/minute global burst 4", "48/minute global burst 12", "4/minute global with one global connection"]) assert.ok(developers.includes(rateTruth), `developers page rate truth missing: ${rateTruth}`);
assert.match(developers, /Fixed error and recovery groups/, "developers page lacks deterministic error recovery");
assert.doesNotMatch(developers, /<script/i, "developers page must be static-first");
assert.match(home, /Hosted 3\.0\.0/, "Home lacks the Hosted release version");
assert.doesNotMatch(home, /Quick Start หลังผ่านรหัสเชิญ/, "Home incorrectly invite-gates Standard access");
assert.doesNotMatch(help, /Hosted Web เป็น Private Beta ที่ใช้รหัสเชิญ/, "Help contradicts Standard access");
assert.match(help, /Hosted 3\.0\.0 รับเฉพาะ text-layer PDF เพื่อสร้าง Protected Markdown เท่านั้น/, "Help lacks the Hosted PDF boundary");
assert.match(terms, /Hosted รับเฉพาะ text-layer PDF → Protected Markdown ไม่ใช่ redacted PDF หรือ OCR/, "Terms lacks the Hosted PDF distinction");
assert.match(terms, /Hosted 3\.0\.0 ให้ Standard access และ Priority Invite/, "Terms hero lacks current access truth");
assert.match(privacy, /Standard access และ Priority Invite ใช้ workspace เดียว/, "Privacy lacks the two-service-class boundary");
assert.match(localEdge, /log_format stage6_private 'surface=edge status=\$status bytes=\$body_bytes_sent method=\$request_method rt=\$request_time'/, "local TLS evidence edge lacks value-free logging");
assert.doesNotMatch(localEdge, /\$request_uri|\$args|combined/, "local TLS evidence edge can log a request target");
console.log("frontend Stage 6 contract ok: fail-closed app, memory-only state, approval/claim gate, provenance, and exact static path");
