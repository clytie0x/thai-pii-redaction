# AI Guard hosted production-readiness ledger

Status date: 2026-08-15

Starting source: `c02ec1c82e22d0e200fbfad68556c169eba68007`

Starting deployed runtime: `72e18bbe723adaf54c847e4b17c2177dfa60dd68`

Target: private-beta public web product at `https://team08.aiforthai.in.th`

This ledger records launch findings against executable source and the real AI
for Thai route.  Historical Sprint 1–3 findings are not reopened when their
current contracts already pass.  A status of `external evidence` is not a
claim about organizer infrastructure that this repository cannot inspect.
An `external accepted risk` is a scoped owner decision, not a claim that the
underlying transport is secure or that the limitation has been fixed.

## Launch-blocking findings

| ID | Priority | Finding | Owner | Candidate disposition |
|---|---|---|---|---|
| WEB-002 | P1 | A shared invite code alone does not bound provider cost or concurrent long requests. | repository | Keep a clearly labelled private-beta invite gate.  Apply global and signed-session request/concurrency lanes, with a stricter `/roundtrip` lane and fixed 429 projection. |
| WEB-003 | P1 | Stateless logout leaves a copied signed cookie usable until expiry. | repository | Maintain only SHA-256 token fingerprints in bounded process memory, revoke on logout, and fail closed across restart.  No user database or raw session token is persisted. |
| WEB-004 | P1 | Application access logs retain client IP addresses. | repository | Keep fixed operation/surface, method, status, response bytes and request duration logs, disable Uvicorn's client-address access stream at the hosted launcher, and make both local and production acceptance reject its access-record shape.  Rate keys remain in nginx shared memory and are not logged. |
| WEB-005 | P1 | The landing path is framed as a judge demo and lacks product privacy, acceptable-use, help, and Desktop/Extension status surfaces. | repository | Desktop-first CTA/navigation/copy; Hosted is explicitly secondary and not local-only; Desktop local processing and Hosted/Pathumma boundaries are stated before input; dedicated Privacy, Terms, Help and Downloads pages; Quick Start, advanced evidence, and presentation controls remain secondary. |
| WEB-006 | P1 | Health checks report unhealthy state but `restart: unless-stopped` does not restart a live unhealthy process. | repository + platform | Candidate health watchdog exits after repeated local failure so Docker restart policy can recover the process.  Host/daemon/edge failure monitoring remains organizer evidence. |
| WEB-007 | P1 | In-place deployment has no automatic recovery when the candidate becomes unhealthy after container mutation. | repository | Deployment helper snapshots exact prior image IDs/Compose source, health-gates the candidate, and restores the prior stack on a failed post-mutation gate. |
| WEB-008 | P1 | The hosted image downloads the Thai NER asset during build without content verification and includes disabled OCR runtime weight. | repository | Verify the baked model-tree digest; omit OCR-only dependencies/prewarm from the hosted image while keeping all public PDF/OCR aliases denied. |
| WEB-009 | P1 | Legal-sounding Section 26 recommendation text can be projected as a mandatory legal conclusion. | repository hosted adapter | Apply an explicit hosted report projection that labels Section 26 as a heuristic review signal and requires contextual legal review; do not change the vendored detector. |
| WEB-018 | P1 | The first rate-key implementation did not match the real `v1` cookie grammar and allowed shadow/duplicate cookie names to decouple the limiter from the authenticated authority. | repository | Anchor the nonce extractor to a complete cookie pair, reject duplicate session authorities before proxying, and exercise real cookie grammar, shadowing, duplicate order, and independent callers in the nginx contract. |
| WEB-019 | P1 | Public health saturation could also consume the container liveness lane and cause an attacker-induced restart loop. | repository | Keep bounded public health, but move the Docker probe to an unexported loopback listener with a two-second/one-attempt bound; prove it remains healthy after public saturation. |
| WEB-020 | P1 | A red or stale post-deploy acceptance could leave the unaccepted candidate live; early failures were outside rollback coverage. | repository | Retain the previous exact image/Compose set, refuse mutation without it, install the acceptance error trap before the stale-main gate, and automatically restore the exact previous release on every acceptance failure. |
| WEB-021 | P1 | Production acceptance briefly used full `docker inspect`, which would retrieve secret-bearing `Config.Env`. | repository | Use only narrow value-blind inspect projections for revision, resource, isolation, tmpfs, ports, grace, restart and log policy; pin this in the acceptance contract. |
| WEB-022 | P1 | A 10/minute constant-key login lane let any unauthenticated source sustain a global private-beta lockout. | repository | Keep a hard global ceiling but raise it to 2 requests/second with burst 10. The minimum 16-byte invite secret makes online guessing infeasible, while bounded session capacity and provider lanes remain the cost controls. |
| WEB-023 | P1 | Pipeline #36033 deployed the reviewed candidate, but acceptance tried to `docker cp` its report probe into the deliberately read-only core root and then rolled back. | repository | Stream the fixed tracked probe to `python -` over `docker exec -i`; no writable container path, credential retrieval, or command-line value is required. Pin the stdin transport in the acceptance contract and reproduce it against the read-only exact local image. |
| WEB-024 | P1 | Pipeline #36306 passed internal acceptance but the public mixed-content check treated the standards-required SVG XML namespace inside a percent-encoded favicon data URI as an active HTTP subresource, then correctly rolled back exact `8c99dfd...` to healthy `72e18bbe...`. | repository acceptance | Parse network-bearing HTML attributes and reject active plain-HTTP/WS references in attributes, `srcset`, CSS and network API calls. Keep the inline SVG namespace non-networking, pin both safe and unsafe cases in the release-source contract, and retain browser console/mixed-content acceptance. |

## Release-relevant improvements and bounded deferrals

| ID | Priority | Finding | Disposition |
|---|---|---|---|
| WEB-001 | external accepted risk | The organizer public edge currently serves the Team 08 app/API over plain HTTP instead of redirecting to HTTPS. Plain HTTP is not secure. | Pipeline #36253 deployed exact `6ce57356540c5f3b47b8ea12a601039f9e8582e3`, passed internal auth/16-route/live Pathumma/report/log gates, then observed HTTP 200 and automatically restored exact `72e18bbe...`; that rollback history remains valid. On 2026-08-15 the owner accepted only the missing public redirect for the competition deployment after an owner-provided public survey found no HTTP-to-HTTPS redirect on 14 other team hosts: available hosts returned HTTP 200 except Team 15, which redirected to another HTTP application path. The Participant Guide documents the HTTPS public URL but does not explicitly require a team-level HTTP 308. Keep the fixed-host 308 implementation so it activates if the organizer later forwards the original scheme. Emit a structured external warning for a non-308 status; that warning alone is not rollback-eligible. A present 308 with the wrong fixed HTTPS location remains fatal. HTTPS availability, PKI-valid TLS, exact HSTS, authentication/Secure cookies, route policy, live provider, report, privacy, resource, exact-SHA and recovery failures remain fatal. |
| WEB-010 | P2 | Health is liveness, not provider readiness. | Keep the response and UI wording as liveness only; the protected production acceptance performs the minimum synthetic live-provider check. |
| WEB-011 | P2 | Single-worker/single-replica deployment has no zero-downtime redundancy. | Document the platform envelope; add graceful stop windows and rollback.  Multi-replica routing is outside the assigned platform. |
| WEB-012 | P2 | CSP still permits the self-hosted inline application script/style. | Deferred: no third-party script, CDN, tracker, dynamic HTML sink, or public source map is introduced; existing XSS contracts remain mandatory.  Nonce/hash extraction is backlog, not a reason to weaken CSP. |
| WEB-013 | P2 | Platform certificate renewal, Docker-daemon isolation, disk cleanup, central alerting, and edge retention are not observable from project source. | Organizer confirmation remains desirable operational evidence.  Do not claim these controls. |
| WEB-014 | P2 | Runtime has no anonymous public quota ledger or user accounts. | Intentional.  Launch remains an invite-only private beta with bounded in-process sessions and server-side request lanes. |
| WEB-015 | unsupported | Public PDF redaction/OCR exceeds this deployment envelope. | Keep `/redact-pdf` and `/v1/redact-pdf` at 404, remove OCR weight from the hosted runtime, and state the limitation in product documentation.  PDPA text-report generation remains separate. |
| WEB-016 | external | Desktop and Browser Extension releases are owned by another repository; v3.0.0 GitHub assets now exist, while the Chrome Web Store Dashboard shows the item as Draft with submission disabled and no published listing. The GitHub Release is mutable and in-page Mask begins only after raw text reaches provider-controlled DOM. | Link the exact v3.0.0 assets with pinned SHA-256, size, release-asset identity, SHA256SUMS and Desktop provenance; disclose the Side Panel as the stronger raw-entry boundary. Label the ZIP Manual / Developer installation, require Desktop 3.0.0 for Native Messaging, and show “preparing for review / not published” without inventing a Store link. |
| WEB-017 | P2 | The vendored dependency graph pins `cryptography 49.0.0`, reported as `PYSEC-2026-3552`. | Supersede it at image build time with a hash-locked hosted-only `50.0.0` overlay. Keep the shared detector lock byte-identical to its recorded upstream source. |

## Non-negotiable release invariants

- Exact public API allowlist remains 16 paths; all PDF/OCR redaction aliases stay
  denied.
- Only masked, policy-checked text may reach the single approved Tokenmind /
  `thaillm-8b` provider; there is no fallback provider.
- No mapping, request body, prompt, response, cookie, access code, credential,
  or client IP is written to application logs.
- Browser content is not placed in persistent browser storage, analytics, or
  trackers.
- Authentication remains Secure, HttpOnly, SameSite=Strict, origin/fetch-site
  checked, bounded, and fail closed.
- Feature/MR pipelines are check-only; production remains protected-main,
  explicitly started, serialized, exact-revision checked, deployed, then
  accepted.
- VERSION remains `2.5.0`; no tag, release, force push, API widening, public
  OCR/PDF redaction, account system, database, analytics, or new provider is
  part of this launch.

## Evidence still required on the exact candidate

1. All affected source, auth, proxy, Compose, route, secret and browser
   contracts pass locally and in feature-branch CI.
2. Three independent read-only reviews find no open P0/P1 on the exact tree.
3. Protected-main `check → deploy → acceptance` is green for one exact SHA.
4. HTTPS is reachable with PKI-valid TLS and emits exact HSTS plus all expected
   headers.  Each public HTTP probe records the observed status: an exact 308
   must target the fixed query-free HTTPS path; absence of 308 is a structured
   organizer-edge warning and is not rollback-eligible under the 2026-08-15
   owner decision.  This exception does not make plain HTTP secure.
5. Synthetic browser acceptance proves login, scan, Safe AI, report, refresh,
   logout/expiry, fixed failures, rate limits, mobile/desktop pages, and no
   console/mixed-content errors.
6. Production logs contain no synthetic sentinel, credential, cookie, body,
   provider body, mapping, or client IP field.
7. Exact image revision, health, resource limits, restart/recovery and rollback
   readiness are verified without exposing application variables.
