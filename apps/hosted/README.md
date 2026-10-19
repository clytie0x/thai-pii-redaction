# AI Guard — local-first Thai PII protection for AI

AI Guard is Desktop-first.  Desktop 0.1.0 keeps detection,
masking/pseudonymization, the reversible vault/mapping, restoration, and
deterministic PDPA report generation on the user's device, and does not expose
a provider command.  No Desktop or Extension build is published under the
restarted 0.x version line yet.

The secondary Hosted Web App is at source version 0.1.0 for team08 on the AI
for Thai platform. Deployed production still runs Hosted 3.0.2 (see `STATE.md`) until this
source is redeployed through the protected release and public acceptance gates:

<https://team08.aiforthai.in.th>

Hosted helps a user inspect Thai text for personal data, replace recognized
values before an approved downstream AI request, validate the protected
response, and restore context inside one request. Standard access is available
per signed browser session; an issued Priority Invite receives a higher service
class without administrative access. It has three task groups:

1. **Privacy Scan** — show counts, types, and spans returned by the detector.
2. **Safe AI** — show the protected provider-bound input and reveal a restored
   answer only after the outbound-safety and restoration gates pass.
3. **PDF → Protected Markdown / PDPA Report** — transform bounded text-layer PDF
   into protected structured text, or show the automated score/grade before an
   explicit download. PDF redaction and OCR remain unsupported.

The home page first recommends Desktop, then offers Hosted as a separate trust
boundary.  Quick Start, advanced evidence, and Presenter/fullscreen remain
optional tools; competition narrative and Sprint evidence live in `docs/`, not
as the primary user journey.

## Product availability

- **Desktop:** no installer is available to download yet.  The earlier 3.0.0
  release is archived and is not distributed from here; see
  [install from source](https://github.com/clytie0x/thai-pii-redaction/blob/main/docs/install-from-source.md).
- **Web App:** the Hosted 0.1.0 candidate provides Standard access per signed browser session
  and Priority access per issued invite. Original text reaches the AI for Thai
  edge and team service for detection. Only the exact reviewed, policy-checked
  protected text may be admitted through the bounded queue to the single
  approved Tokenmind/Pathumma `thaillm-8b` provider. There is no account or user
  database and no provider fallback.
- **Browser Extension:** no ZIP is available to download yet, and the Chrome
  Web Store item is still a draft preparing for review and is not published,
  so no Store link is claimed.  The Extension needs AI Guard Desktop for Native
  Messaging.  In-page Mask starts only after raw text enters the
  provider-controlled page DOM, where page code may already observe or transmit
  it; the Side Panel is the stronger raw-entry boundary.
- **Hosted text-layer PDF:** the Hosted 0.1.0 candidate accepts bounded text-layer PDF to
  produce Protected Markdown after exact-payload review. The source PDF remains
  unchanged and never reaches Pathumma. PDF redaction/rebuilding, scanned or
  image-only PDF, and OCR remain unsupported; `/redact-pdf` and
  `/v1/redact-pdf` stay fixed proxy-level 404.

Product documentation is served from `/privacy`, `/terms`, `/help`, and
`/downloads`.  Those pages describe data flow, cookies, retention, acceptable
use, limitations, support, and release availability without legal or security
overclaim. The current deployment, same-origin application API, acceptance,
rollback, and operations guide is
[`docs/HOSTED-3-DEPLOY-API-GUIDE.md`](docs/HOSTED-3-DEPLOY-API-GUIDE.md).

## Privacy and security boundary

- Desktop source text, findings, vault/mapping, restoration, and deterministic
  report stay local.  Desktop 0.1.0 has no provider command and contains no
  shared NECTEC credential.
- Hosted source text reaches the AI for Thai edge, reverse proxy, and AI Guard
  server before detection.  Hosted is not on-device-only processing.
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

The public pages and liveness endpoint are readable without a session. Every
text-processing route requires either a signed Standard browser session or a
signed session created from an issued Priority Invite. Cookies are `Secure`,
`HttpOnly`, `SameSite=Strict`, `Path=/`, and have a maximum 30-minute lifetime.
Authority creation and ending enforce same-origin browser context.

Only SHA-256 token fingerprints and expiry times are retained in separate
bounded process-memory pools: maximum 256 Priority sessions and 512 Standard
sessions. Logout revokes the current token; a core restart invalidates all prior
sessions. No token, invite code, identity, or user record is persisted.

Nginx enforces server-side lanes independent of client code:

- public control-plane: 30 requests/second globally;
- login: hard global ceiling 2 requests/second with burst 10; the 16+-byte
  invite secret makes online guessing infeasible, while the higher ceiling
  avoids turning one unauthenticated source into a sustained global lockout;
- ordinary processing: 20 requests/second globally and 30/minute per presented
  session key, with global and per-caller connection caps;
- legacy `/roundtrip`: 6 requests/minute globally and 2/minute per presented
  session key;
- Hosted 3 preview, document, queue and execute controls: route- and
  service-class-specific limits documented in the current deploy/API guide;
- shared provider scheduler: maximum two concurrent provider operations
  globally and one unresolved provider operation per authority.

The core caps text at 20,000 characters; nginx caps the entire request body at
128 KiB (8 KiB on login).  Fixed value-free JSON is used for 413, 429, 502 and
504.  `/roundtrip` has a 200-second proxy boundary around the existing bounded
same-provider policy (at most three 60-second attempts with 1/2-second backoff).
The browser permits one unresolved provider-bound request at a time.

## Deployment architecture

| Component | Boundary |
|---|---|
| `web/` | Read-only static nginx on loopback host port 20070. Concept C Home is isolated from the `/app` runtime; exact routes also serve Developers, Downloads, Privacy, Help, Terms, a branded human 404, local fonts/logos, security headers, and minimized logs. |
| `api/` | Read-only nginx on loopback host port 20071.  Re-adds the stripped `/api` prefix, exact allowlist, holds the inner service key, applies limits and fixed errors. |
| `core/` | Non-root/read-only FastAPI container, internal network only.  Port-owned auth/report policy wraps a vendored upstream slice. |
| `pdf-parser/` | Secretless, networkless, non-root parser on a Unix socket. It accepts one bounded text-layer PDF job, returns strict extracted segments/metadata, and cleans its volatile work directory before readmission. |
| `sync/` | Pins 75 upstream provenance entries from `3c2997835dbdc9842e38b38fb89f09642a713817` with per-file hashes; Hosted keeps its release-owned VERSION. |
| `evaluation/thai_pii/` | Sprint 3 deterministic synthetic/adversarial evidence; outside all runtime build contexts and provider-free. |

The hosted image omits disabled Paddle OCR dependencies.  Its PyThaiNLP
`thainer` asset tree is checked during build against the Sprint 3 SHA-256
`bc36ef28c16dbca39911add53e9b9a96ebb23edf6c8b00555d5647ba8629c315`, then
runs offline.  The four containers are read-only, no-new-privileges, PID/memory
/CPU bounded, use volatile tmpfs, and have a three-failure health watchdog that
exits the service so Docker's bounded restart policy can recover it.  Graceful
stop allows up to 210 seconds for a long provider operation.

## Same-origin application API

The public edge exposes exactly **40 routes** for same-origin application use
by the official Web App: 20 canonical paths and one exact `/v1` alias for each.
This is not an arbitrary third-party API, developer-key product, or broad CORS
surface. Browser requests use `/api/...`; the organizer strips that prefix and
the API proxy restores it for Core. The HTTP contract remains version 2 for
Hosted 0.1.0.

| Method/path | Purpose |
|---|---|
| `GET /health` | Liveness and VERSION only; not provider readiness. |
| `POST /auth/login` | Exchange invite code for the bounded cookie. |
| `POST /auth/logout` | Revoke the current process-local session and clear cookie. |
| `GET /auth/session` | Report authenticated/expiry state plus service-class and timing headers without returning credential, subject, or token. |
| `POST /detect` | Strict PII counts/types/spans. |
| `POST /guard` | Heuristic prompt-risk warning; it does not block by itself. |
| `POST /roundtrip` | Detect → protect → policy-check → approved AI → validate → restore. |
| `POST /analyze-report` | Automated PDPA risk report PDF; no source text in report summary. |
| `POST /auth/guest`, `/auth/guest/end` | Start/end a bounded Standard browser authority. |
| `POST /guest/preview`, `/guest/execute` | Preview/execute a server-owned synthetic scenario. |
| `POST /protection-preview`, `/protection-execute` | Preview and execute approved custom protected text. |
| `POST /document-preview`, `/document-execute` | Parse bounded text-layer PDF and produce protected artifacts. |
| `POST /provider-queue/join`, `GET /provider-queue/status`, `POST /provider-queue/claim`, `POST /provider-queue/cancel` | Content-free bounded provider scheduler control plane. |

Internal `/sanitize`, `/reidentify`, `/analyze`, docs/OpenAPI, and public PDF
redaction/OCR are denied by exact-match routing. The allowlist contract is 40
exact routes; prefixes, near matches, implicit versions, and unknown methods fail
closed.

## Local development and checks

Use synthetic values only:

```bash
export APP_AIGUARD_API_KEY='synthetic-distinct-core-key'
export APP_AIFT_ACCESS_CODE='synthetic-distinct-invite-code'
export APP_AIFT_COOKIE_SIGNING_KEY='synthetic-distinct-cookie-signing-key-long'
export APP_AIFT_PRIORITY_INVITES_JSON='[{"subject_id":"sub_AAAAAAAAAAAAAAAAAAAAAA","role":"priority_invite","enabled":true,"code_sha256":"bd589d9bfd76f29c18d8541750287a480badb3c2272b4f98af6c4439792c2687"}]'
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
rechecks before mutation, health-gates all four services, and retains one exact
prior image/Compose set.  A failed post-mutation gate restores that prior stack.
Acceptance then verifies the same exact SHA, synthetic auth/business/provider
flows, route denial, logs, and the real public edge.  This rollback is repository
hardening, not an official Participant Guide requirement.

The Hosted 0.1.0 release source requires exactly five protected,
environment-scoped variables:

- `APP_AIGUARD_API_KEY`
- `APP_AIFT_ACCESS_CODE`
- `APP_AIFT_COOKIE_SIGNING_KEY`
- `APP_AIFT_PRIORITY_INVITES_JSON`
- `APP_TOKENMIND_API_KEY`

The fifth value is the bounded Priority Invite registry. Release checks consume
all five only from inherited protected, environment-scoped CI variables and do
not print or retrieve their values.

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
