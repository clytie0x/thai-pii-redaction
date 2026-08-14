# AI Guard Hosted — Thai PII protection for AI

AI Guard Hosted is the private-beta web product deployed for team08 on the AI
for Thai platform:

<https://team08.aiforthai.in.th>

It helps a user inspect Thai text for personal data, replace recognized values
before an approved downstream AI request, validate the protected response, and
restore context inside one request.  The product has three workflows:

1. **Privacy Scan** — show counts, types, and spans returned by the detector.
2. **Safe AI** — show the protected provider-bound input and reveal a restored
   answer only after the outbound-safety and restoration gates pass.
3. **PDPA Report** — show the automated score/grade before an explicit download.

The home page is the user product.  Quick Start and Presenter/fullscreen remain
optional tools; competition narrative and Sprint evidence live in `docs/`, not
as the primary user journey.

## Product availability

- **Web App:** invite-only private beta.  A shared invite gate is retained to
  bound abuse and downstream-provider cost without introducing accounts or a
  user database.
- **Desktop:** [AI Guard 3.0.0 is published on GitHub Releases](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/releases/tag/v3.0.0), with verified links for
  [Windows x64](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/releases/download/v3.0.0/AI.Guard_3.0.0_x64-setup.exe),
  [Linux Debian x64](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/releases/download/v3.0.0/AI.Guard_3.0.0_amd64.deb),
  [Linux AppImage x64](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/releases/download/v3.0.0/AI.Guard_3.0.0_amd64.AppImage), and
  [macOS Apple silicon](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/releases/download/v3.0.0/AI.Guard_3.0.0_aarch64.dmg).
  OS trust warnings may appear because code signing is deferred; users should
  compare the pinned hashes against
  [SHA256SUMS](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/releases/download/v3.0.0/SHA256SUMS)
  and verify GitHub provenance before proceeding.  The release is mutable, so
  a filename or tag alone is not an integrity check.
- **Browser Extension:** the Chrome Web Store item is still a draft preparing
  for review and is not published, so no Store link is claimed.  The
  [3.0.0 ZIP](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/releases/download/v3.0.0/aiguard-extension-3.0.0.zip)
  is labelled Manual / Developer installation; it requires AI Guard Desktop
  3.0.0 for Native Messaging, followed by extract + Load unpacked.  In-page
  Mask starts only after raw text enters the provider-controlled page DOM,
  where page code may already observe or transmit it; the Side Panel is the
  stronger raw-entry boundary.  The separately certified ZIP SHA-256 is
  `feb048775ec3d2a2c57ade08b37000fc4fa035a72ffb77db201e5eb838357670`.
- **Public PDF redaction/OCR:** intentionally unsupported.  Both
  `/redact-pdf` and `/v1/redact-pdf` return a fixed proxy-level 404 and there is
  no upload UI.  This is not a blocker for the production-ready text Web App;
  enabling it later requires separate correctness, provenance, timeout, and
  resource acceptance.

Product documentation is served from `/privacy`, `/terms`, `/help`, and
`/downloads`.  Those pages describe data flow, cookies, retention, acceptable
use, limitations, support, and release availability without legal or security
overclaim.

## Privacy and security boundary

- Source text reaches the AI for Thai edge, reverse proxy, and AI Guard server
  before detection.  This is not on-device-only processing.
- Only the masked text that passes the fresh outbound policy check is sent to
  the single approved Tokenmind/Pathumma `thaillm-8b` integration.  There is no
  provider fallback.
- The reversible mapping is function-local, transient, absent from the provider
  payload and public response, and not intentionally persisted.  The product
  does not claim secure memory zeroization.
- Pseudonymized data can remain personal data.  Token and Surrogate are
  reversible pseudonymization modes, not anonymization.
- Detection can produce false positives and false negatives.  Section 26 output
  is a heuristic review signal, not a legal determination or compliance
  certificate.
- The browser stores no user content in `localStorage` or `sessionStorage` and
  uses no analytics, tracker, CDN, or third-party frontend library.
- Application access rows contain only fixed operation/surface, method, status,
  response bytes, and duration.  They do not contain client IP, request target,
  query, body, prompt, response, mapping, cookie, invite code, or credential.
  Docker rotation is bounded at 50 MiB × 3 files per service.  The organizer
  edge may retain connection metadata under its own policy.

## Access and abuse controls

The public pages and liveness endpoint are readable without a session.  Every
text-processing route requires a signed session cookie minted from the invite
code.  The cookie is `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/`, and has a
maximum 30-minute lifetime.  Login/logout enforce same-origin browser context.

Only SHA-256 token fingerprints and expiry times are retained in bounded
process memory (maximum 256 active sessions).  Logout revokes the current token;
a core restart invalidates all prior sessions.  No token, invite code, identity,
or user record is persisted.

Nginx enforces server-side lanes independent of client code:

- public control-plane: 30 requests/second globally;
- login: hard global ceiling 2 requests/second with burst 10; the 16+-byte
  invite secret makes online guessing infeasible, while the higher ceiling
  avoids turning one unauthenticated source into a sustained global lockout;
- ordinary processing: 20 requests/second globally and 30/minute per presented
  session key, with global and per-caller connection caps;
- Safe AI: 6 requests/minute globally, 2/minute per presented session key,
  maximum two concurrent provider operations globally and one per caller.

The core caps text at 20,000 characters; nginx caps the entire request body at
128 KiB (8 KiB on login).  Fixed value-free JSON is used for 413, 429, 502 and
504.  `/roundtrip` has a 200-second proxy boundary around the existing bounded
same-provider policy (at most three 60-second attempts with 1/2-second backoff).
The browser permits one unresolved provider-bound request at a time.

## Deployment architecture

| Component | Boundary |
|---|---|
| `web/` | Read-only static nginx on loopback host port 20070.  Product pages, fixed 404 routing, security headers, minimized logs. |
| `api/` | Read-only nginx on loopback host port 20071.  Re-adds the stripped `/api` prefix, exact allowlist, holds the inner service key, applies limits and fixed errors. |
| `core/` | Non-root/read-only FastAPI container, internal network only.  Port-owned auth/report policy wraps a vendored upstream slice. |
| `sync/` | Pins 75 upstream files from `44ef30b0e8ea2021fc4ceec9d3b12dc9f64c750f` with per-file hashes. |
| `evaluation/thai_pii/` | Sprint 3 deterministic synthetic/adversarial evidence; outside all runtime build contexts and provider-free. |

The hosted image omits disabled Paddle OCR dependencies.  Its PyThaiNLP
`thainer` asset tree is checked during build against the Sprint 3 SHA-256
`bc36ef28c16dbca39911add53e9b9a96ebb23edf6c8b00555d5647ba8629c315`, then
runs offline.  The three containers are read-only, no-new-privileges, PID/memory
/CPU bounded, use volatile tmpfs, and have a three-failure health watchdog that
exits the service so Docker's bounded restart policy can recover it.  Graceful
stop allows up to 210 seconds for a long provider operation.

## Public API

The API proxy exposes exactly **16 routes**: the eight paths below and one
`/v1` alias for each.  External callers use `/api/...`; the organizer strips
that prefix and the API proxy restores it for core.

| Method/path | Purpose |
|---|---|
| `GET /health` | Liveness and VERSION only; not provider readiness. |
| `POST /auth/login` | Exchange invite code for the bounded cookie. |
| `POST /auth/logout` | Revoke the current process-local session and clear cookie. |
| `GET /auth/session` | Report authenticated/expiry state without returning authority. |
| `POST /detect` | Strict PII counts/types/spans. |
| `POST /guard` | Heuristic prompt-risk warning; it does not block by itself. |
| `POST /roundtrip` | Detect → protect → policy-check → approved AI → validate → restore. |
| `POST /analyze-report` | Automated PDPA risk report PDF; no source text in report summary. |

Internal `/sanitize`, `/reidentify`, `/analyze`, docs/OpenAPI, and public PDF
redaction/OCR are denied by exact-match routing.  The allowlist contract must
remain 16 routes unless a separately reviewed product requirement changes it.

## Local development and checks

Use synthetic values only:

```bash
export APP_AIGUARD_API_KEY='synthetic-distinct-core-key'
export APP_AIFT_ACCESS_CODE='synthetic-distinct-invite-code'
export APP_AIFT_COOKIE_SIGNING_KEY='synthetic-distinct-cookie-signing-key-long'
export APP_TOKENMIND_API_KEY='synthetic-provider-key-or-fake-override'
docker compose -p team08 up -d --build
curl -fsS http://127.0.0.1:20071/health
```

The complete check surface is executable from `.gitlab-ci.yml`.  Useful local
entry points include:

```bash
python tests/auth_contract.py
node tests/frontend_session_contract.mjs
python tests/public_surface_contract.py
python tests/hosted_core_contract.py
python tests/nginx_contract.py
python tests/compose_contract.py
python tests/run_ci_local.py --job check --gitlab-network
```

`tests/local_release_acceptance.py` uses the deterministic fake provider and
must never be presented as live Tokenmind evidence.  The protected production
acceptance performs the minimum synthetic live-provider call, verifies exact
image labels and log privacy, and now runs `tests/public_web_acceptance.py`
against the real HTTP/HTTPS edge.

## GitLab release policy

All jobs are pinned to runner tag `team-08`.  Feature branches, merge requests,
and every ordinary push—including protected `main`—are check-only.  Production
requires an explicitly created web pipeline on protected `main`; deploy and
acceptance are non-interruptible and serialized by
`resource_group: team08-production`.

Deployment validates the latest remote main, builds exact-revision images,
rechecks before mutation, health-gates all three services, and retains one exact
prior image/Compose set.  A failed post-mutation gate restores that prior stack.
Acceptance then verifies the same exact SHA, synthetic auth/business/provider
flows, route denial, logs, and the real public edge.  This rollback is repository
hardening, not an official Participant Guide requirement.

The four environment-scoped project variables are exactly:

- `APP_AIGUARD_API_KEY`
- `APP_AIFT_ACCESS_CODE`
- `APP_AIFT_COOKIE_SIGNING_KEY`
- `APP_TOKENMIND_API_KEY`

Values must never be printed, retrieved, compared outside the existing
value-free deploy checks, placed in command arguments, or copied into evidence.

## Evidence and honest limits

Known-good runtime before this productionization branch:
`72e18bbe723adaf54c847e4b17c2177dfa60dd68` (Pipeline #35744).  Sprint 3 main
`c02ec1c82e22d0e200fbfad68556c169eba68007` changed only evaluation evidence,
not deployed runtime.  Preserve both as historical rollback/audit evidence.

The committed Sprint 3 suite contains 138 constructed Thai PII cases plus 32
separate Section 26 heuristic cases.  It is deterministic synthetic/adversarial
evidence, not a population-representative benchmark and not proof of perfect
detection.  See `docs/evaluation/thai-pii-competition-evaluation.md`.

The official Participant Guide establishes the namespace, ports, main deploy,
team runner, Masked secret variables, limits, log rotation, `/api` stripping,
and `/health` shape.  Protected-main UI release, protected/scoped variables,
strict runner tags, stale-SHA checks, session revocation, exact model hash,
automatic stack recovery and public-edge acceptance are AI Guard hardening.
Protected runner/environment flags are not claimed as guide requirements.

Operational facts that still require organizer evidence are edge certificate
renewal, runner/Docker-daemon isolation, host disk management, external
watchdog/alerting, and organizer-edge metadata retention.  Repository controls
must not be described as proof of those platform properties.
