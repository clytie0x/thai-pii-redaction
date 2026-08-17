# AI Guard Production Web Redesign

Last updated: 2026-08-16 (Asia/Bangkok)

## Purpose

This is the durable source of truth for converting the approved Concept C art
direction into the production AI Guard website. Update this document whenever a
decision, implementation detail, limitation, or verification result changes.

The goal is a memorable, polished, production-quality Thai-first website. A
working page is not sufficient. The result must have deliberate typography,
color, geometry, motion, product truth, responsive behavior, accessibility, and
an end-to-end production serving path.

## Current state

- Audio input, TTS, images, Vision, scanned/image-only PDF, and OCR are excluded
  from the approved Hosted 3.0 release and receive no production teaser or
  control. A later modality release requires a separate owner decision and full
  service/privacy/resource review. Deferred evidence is already local and must
  be checked before generic AI for Thai catalog research: the supplied Pathumma
  credential exposed the current text model plus `ptm-asr-1` and `ptm-tts-1`;
  E0-E5/current runtime record the text identifier as `thaillm-8b`, while one
  LINE observation records `thailm-8b`, so a fresh `/v1/models` response must
  settle the exact identifier before a new contract is locked. Onboarding
  notes record the OpenAI-compatible `/v1/audio/transcriptions` and
  `/v1/audio/speech` operations. It did **not** expose a Vision model. The E4
  synthetic ASR spike completed 30 TTS→ASR→detector cases, but Thai spoken-
  number output caused `PHONE`, `THAI_ID`, and mixed cases to miss the declared
  threshold. The local PaddleOCR spike is a separate self-hosted experiment,
  not organizer-provided Vision entitlement, and its later Hosted profile
  exceeded the accepted resource envelope. If a later release reopens audio it
  needs a fresh live contract test and reviewed spoken-number normalizer; image
  needs separately verified Vision entitlement or a new local-OCR resource
  decision. Evidence:
  `docs/evidence/e0-e5-results.md`, `docs/evidence/e4_report.json`, and the two
  2026-08-16 LINE observation notes.
- On 2026-08-16 the owner paused logo selection and set a new release intent:
  upgrade the Hosted Web/API product itself and issue Hosted `3.0.0` with a
  materially stronger judged experience. This is not authorization for a
  version-label-only change. The B2 production logo stays unchanged while the
  Hosted 3.0 product scope is designed, implemented, verified, and deployed.
- On 2026-08-16, after reviewing the deployed mark at header scale, the user
  requested a genuinely new logo direction with colors aligned to the live web
  system. This is a new exploration, not authorization to replace the deployed
  asset. The next review surface will compare three materially different
  64-unit vector constructions at `16`, `24`, `32`, `42`, `64`, and `128 px` on
  Paper and Deep Blue. Production keeps revision B2 until the user selects
  and approves a replacement through the full asset/deployment gate.
- `web/logo-preview.html` now holds three inline, non-production 64-unit round-3
  studies: Guard Loop (open `G` monogram), Privacy Passage (abstract
  transformation arch), and Signal Veil (refined heritage shield). These are
  deliberately different silhouettes rather than three glyph substitutions in
  one shield. Each includes main, inverse, one-color, and dedicated `16`/`24 px`
  micro constructions. Signal and Safe remain single-purpose accents; gold is
  absent. No production SVG, Docker COPY, Nginx route, CSP, caller, or deployed
  page has changed.
- The working tree now implements the approved split production architecture:
  Concept C's six-scene editorial Home is `web/index.html`, while the complete
  authenticated Hosted workspace is isolated in `web/app.html` and `web/app.css`.
  The deployed `dbcfe17b` caller still uses `/app.js`; the active local Stage 6
  candidate has replaced that runtime with exact `/hosted3-app.js` and no longer
  copies or serves the dead legacy script. Home contains no invite input, application runtime, or API
  initialization. The exact built-image checks and required real-browser matrix
  now pass locally and independent full-page reviews report no material blocker.
  The first exact production attempt, Pipeline #36391 at `9995532a`, deployed
  cleanly but was automatically rolled back because the public acceptance test
  incorrectly expected an unauthenticated `GET /api/auth/session` to return
  `404`; the live API's intentional contract is `401 authentication_required`.
  The rollback to `75aaa7e6` completed healthy. Corrected protected production
  Pipeline #36394 now runs exact revision
  `dbcfe17b34744dc3e9a88e4099786a754fe903a6`; check, deploy, joined public
  acceptance, logs, exact-revision/process inspection, and restart/recovery all
  pass. The Concept C redesign is live at `https://team08.aiforthai.in.th/`.
- `web/home-concept-c.html` is the selected visual prototype. It is not deployed
  by `web/Dockerfile`; it remains the visual quality baseline for the next
  production iteration rather than merely a provenance artifact.
- `web/logo-preview.html` is a comparison surface for logo exploration only.
- Downloads, Privacy, Help, and Terms now use the calm reference-document
  archetype with visible summaries, local contents where useful, non-collapsed
  critical warnings, and channel-specific version labels. An internal branded
  `404.html` is configured only for unknown human-facing routes; `/api/*`, exact
  asset near-matches, unknown methods, and direct `/404.html` access remain
  unbranded fail-closed responses.
- The rejected freehand logo paths have been replaced by revision B2's numeric
  construction plus main, one-color, inverse, and light/dark favicon variants.
  Independent art-direction, frontend/product, and UX/accessibility review now
  reports no material logo blocker. The assets are integrated into production
  HTML, Docker, exact Nginx routes, CSP, and tests, and the joined public route
  serves them successfully at every required browser width.
- The canonical historical logo source is in the sibling project at
  `C:/Users/teera/dev/thai-pii-redaction/assets/logo.svg`, with PNG and source
  image variants beside it.
- Production now self-hosts pinned Anuphan Thai and Latin variable WOFF2 subsets
  plus the full OFL license. All three production stylesheets, Docker, exact Nginx
  routes, `font-src 'self'`, build checks, runtime checks, and caller-facing
  acceptance checks reference the same local assets. All three production
  stylesheets use the unique `AIGuardAnuphan` family name so an installed system
  copy cannot mask a missing self-hosted request.

## Approved direction

The user selected Concept C. Preserve these characteristics unless later visual
feedback overrides them:

- Editorial split-screen architecture with strong Thai display typography.
- Warm paper background, near-black type, and primary blue centered on
  `#3266A8`.
- Clear grid, strong rules, asymmetric editorial composition, and a large live
  product/protection canvas.
- Purposeful motion and interaction. The site must not feel static or generic.
- A product demonstration that makes detection, protection, and human review
  understandable without misrepresenting what the hosted or desktop product
  actually does.
- Desktop-first product positioning with truthful Web App boundaries.

Reference inspiration: the information density, confidence, motion, and visual
craft of `https://nextjs.org/`, without copying its black-and-white palette or
brand language.

## Approved production information architecture

On 2026-08-16 the user approved implementation and deployment of the complete
six-page production architecture plus one branded internal error page, and made
that work the priority before the organizer form, final slides, and seven-minute
rehearsal planned for Monday. The selected Concept C composition remains the
visual quality floor across the system; the rejected production integration is
not a template for any page.

### Route and page inventory

| Route | Production file | Primary job | Navigation status |
| --- | --- | --- | --- |
| `/` | `index.html` | Focused Desktop-first marketing home | Global navigation |
| `/app` | `app.html` | Invite-only Hosted Web application | Global navigation and CTA |
| `/downloads` | `downloads.html` | Verified Desktop/Extension distribution | Global navigation |
| `/privacy` | `privacy.html` | Complete privacy and security boundary | Global navigation |
| `/help` | `help.html` | Onboarding, troubleshooting, FAQ, and support | Global navigation |
| `/terms` | `terms.html` | Acceptable use and service limitations | Footer/legal navigation |
| Internal 404 | `404.html` | Branded recovery from an unknown exact route | Never listed in navigation |

`home-concept-c.html` and `logo-preview.html` remain local review artifacts and
must not enter the production image. There is no separate pricing, blog,
company, or marketing-only product page because no current product truth or
content owner requires one.

### Shared visual and navigation system

- Preserve Concept C's editorial split, warm Paper canvas, Protection Blue
  field, Ink typography, asymmetric grid, large Thai display type, decisive
  rules, generous whitespace, and focused product demonstration. Production
  must match its visual rhythm rather than merely reuse its palette.
- Use the approved revision-B2 logo system and self-hosted Anuphan files. Keep
  the visible `AI Guard` wordmark beside the image so image failure does not
  remove the brand name.
- Global header: logo/home, Desktop, Hosted Web, Privacy, and Help. Terms remains
  in the footer. Desktop links to `/downloads#desktop`; Hosted Web links to
  `/app`.
- Global footer: until the Hosted 3.0 release gate passes, label each channel
  separately as `Desktop 3.0.0`, `Hosted 2.5.0 · Private Beta`, and `Extension
  3.0.0 · Manual`; then link Home,
  Downloads, Privacy, Terms, and Help. Do not use one ambiguous shared version
  label or add social, pricing, customer-logo, certification, or compliance
  claims without verified source material.
- The home page retains `id="web-access"` on its Hosted CTA section so existing
  `/#web-access` fragments land on a useful transition. Functional workflow
  anchors move to `/app#privacy-scan`, `/app#safe-ai`, and
  `/app#pdpa-report`.

### Three related page archetypes

The pages share brand tokens, exact logo use, header/footer structure, focus
style, rules, spacing scale, and color roles, but they do not reuse one layout
indiscriminately.

1. **Editorial marketing, Home only:** Concept C split-screen first fold, display
   type limited to the hero and scene headings, six full-width scenes, strong
   contrast shifts, and deliberate large whitespace. Maximum readable text
   measure is about `62ch`; supporting copy is no more than two short sentences
   per scene topic.
2. **Focused operational workspace, App only:** compact product header, one
   primary task column plus contextual evidence, restrained display type, clear
   state boundaries, and no decorative split screen around active controls. At
   tablet/mobile widths all controls become one ordered column; there is no
   horizontally scrolling workflow or tab strip.
3. **Calm reference documents, Downloads/Privacy/Help/Terms:** editorial intro,
   maximum body measure around `72ch`, optional local anchored contents for long
   pages, steady vertical rhythm, plain-language summaries before technical
   detail, and accessible disclosures only for secondary verification or
   evidence. Critical warnings, current status, and recovery actions are never
   collapsed.

The 404 uses the reference-document shell in a deliberately compact form.

### Page 1: Home `/`

The home page is a focused narrative, not the application container. Lock it to
Concept C's six-scene rhythm; it must not expand into one section per product
fact.

1. **Hero + protection canvas:** compact header, Thai-first headline, one short
   proposition, Desktop 3.0.0 primary CTA, `Use your invite` Hosted CTA, one-line
   channel distinction, and a synthetic `Find → Mask → Review` before/protected
   demonstration. No live form or invented result.
2. **Three workflows:** one headline, one short sentence, and one visual/status
   token each for Privacy Scan, Safe AI, and PDPA Report. Deep-link to the
   matching gated `/app` anchors for full behavior; mention automatic-detection
   limitations once, not on every card.
3. **Choose the boundary:** side-by-side Desktop and Hosted cards limited to one
   status line and two short sentences each. Desktop says processing/vault/report
   stay on-device with no provider command. Hosted says raw reaches the edge/team
   server and only freshly checked protected text reaches the approved provider.
   Lifecycle, session, and log detail belongs on `/privacy`.
4. **Contexts:** HR, healthcare, education, customer service, and government as
   five compact use-context labels around one human-review message. They are not
   customer, certification, or compliance claims.
5. **Availability + trust band:** short status chips for Desktop published,
   Hosted invite-only, Extension Manual/Store unpublished, and the currently
   deployed Hosted 2.5 PDF/OCR exclusion, plus one sentence that pseudonymization
   is not anonymization or
   automatic PDPA certification. Platform files, hashes, and installation facts
   belong only on `/downloads`; complete limitations belong on `/privacy` and
   `/terms`.
6. **Closing channel choice:** one headline, Desktop primary, Hosted invite CTA
   secondary, Privacy tertiary, then the global footer.

The home page must not contain an invite input, application text area, live
health status, workflow result panels, Presenter mode, or advanced evidence.
This keeps Concept C's first-screen composition intact and prevents application
state from overwhelming the marketing narrative.

### Page 2: Hosted Web App `/app`

This page owns all authenticated and interactive behavior currently mixed into
the home page. Existing API routes, payload contracts, fail-closed checks, and
privacy claims do not change.

1. **Application header:** brand/home, Hosted Private Beta 2.5.0 status,
   Privacy, Help, and session/logout state.
2. **Access gate:** invite code, login/logout, same-origin status, no password
   manager overclaim, and a visible statement that the invite code is not stored
   in `localStorage` or `sessionStorage`.
   There is no public signup or waitlist. An unauthenticated `/app#workflow`
   visit keeps controls locked, exposes only the boundary and short workflow
   explanation, focuses the access heading instead of scrolling past the gate,
   and retains the requested anchor in memory only. After successful login it
   scrolls and focuses the requested workflow; Desktop remains the visible
   fallback.
3. **Pre-flight boundary notice:** raw text reaches the Hosted edge and server;
   use Desktop instead when local processing is required. Display the 20,000
   character limit and human-review warning immediately beside the shared input,
   not only at the top of the page. Workflow fragments target the wrapper that
   begins with this notice, never a raw-text control below an off-screen warning.
4. **Synthetic Quick Start:** optional and collapsed by default. It may load only
   synthetic HR, healthcare, education, customer service, or government text.
5. **Shared input:** one text source, character counter, reset action, explicit
   request state, and no automatic submission.
6. **Privacy Scan:** returned counts, types, and spans only; no invented score or
   risk narrative. Include empty, loading, success, partial, error, rate-limit,
   oversized, and expired-session states.
7. **Safe AI:** Token and Surrogate choices described as reversible
   pseudonymization, the exact protected provider-bound text, approved provider
   label, outbound-policy result, restoration gates, and restored answer only
   after every required gate passes. Permit only one unresolved provider-bound
   request in the browser.
8. **Operational evidence:** optional disclosure for provider used, entity
   counts, residual-signal status, restoration status, timing, and value-free
   request evidence. Never expose mapping pairs, provider body, credential, or
   raw value in a shareable evidence card. A user-visible raw-versus-protected
   comparison is an on-screen working view, not shareable value-free evidence.
9. **Retained optional/presentation tools:** preserve all currently supported
   synthetic scenario cards; API-derived `/guard` Prompt Risk warnings;
   Raw-versus-Protected comparison; Sensitive Data Map; Protection Receipt;
   Executive Summary; glossary; and Presenter/fullscreen. Prompt Risk is a
   returned heuristic, not an invented client score. These tools stay collapsed
   or secondary so they do not compete with the three primary workflows.
10. **PDPA Report:** API-returned score and grade, category summary from the same
   Privacy Scan input, explicit download, no source text in the file, and clear
   “automated review, not legal certification” language.
11. **Service status and recovery:** liveness is labelled as liveness only, not
    provider readiness. Cover offline and real `400`, `401`, `403`, `413`,
    `422`, `429`, `500`, `502`, `503`, and `504` outcomes with fixed safe
    messages. Input-validation failures preserve editable input but create no
    result for that revision; auth failures clear sensitive DOM state and return
    focus to the gate; residual-PII/schema and restore failures fail closed and
    reveal no unsafe/restored result; rate limits preserve input and expose the
    allowed retry state; provider/service failures permit retry only after the
    HTTP exchange has definitively settled. Stale completions can never repaint.
12. **Application footer:** Privacy, Terms, Help, Desktop alternative, version,
    and logout guidance.
13. **No-script/bootstrap failure:** a static, always-authored fallback explains
    that Hosted controls require JavaScript and links Desktop, Help, and Privacy.
    Successful bootstrap replaces it; failure never leaves an empty workspace.

Navigation, reload, Back, logout, and expiry follow one sensitive-state rule:
abort local-only work where possible, invalidate completion tokens so stale
responses cannot repaint, clear raw/result/report DOM state, and never persist it
in browser storage. Warn only when meaningful entered or generated work would be
discarded. A provider-bound request that cannot be cancelled remains visibly
unresolved until the HTTP exchange settles; navigation must not imply it was
cancelled. Safe reset and recovery messages receive deterministic focus and a
restrained live-region announcement.

### Page 3: Downloads `/downloads`

1. Desktop-first header and local-processing proposition.
2. Release `v3.0.0`, publication date, exact direct artifacts, sizes, operating
   systems, and architectures: Windows x64 setup, Linux amd64 `.deb`, Linux
   amd64 AppImage, and macOS Apple silicon `.dmg`.
3. Recommended Windows card without implying other platforms are unsupported.
4. System requirements and the fact that packaged models require installation
   space beyond download size.
5. Unsigned/not-notarized warnings stated plainly.
6. Exact SHA-256 values, exact byte sizes, `SHA256SUMS`, GitHub attestation
   command, provenance/security-model link, and warning that tag or filename
   alone is not integrity proof.
7. Extension 3.0.0 status: Store draft/not published, ZIP size/hash, Desktop
   Native Messaging dependency, extract/Developer mode/Load unpacked steps.
8. Extension privacy boundary: in-page masking starts after raw text enters the
   provider-controlled page DOM; Side Panel is the stronger raw-entry boundary.
9. Hosted Private Beta remains a separate channel and download does not change
   its access or data boundary.

### Page 4: Privacy and Security `/privacy`

1. Plain-language summary and an immediate Desktop-versus-Hosted comparison.
2. Four-step Hosted lifecycle: original text at edge/server, freshly protected
   provider payload, request-local transient mapping/restoration, and report
   behavior.
3. Provider truth: one approved Tokenmind/Pathumma `thaillm-8b` integration and
   no provider fallback.
4. Pseudonymization truth: mapping is function-local, absent from provider and
   public response, not intentionally persisted, and not claimed to be securely
   zeroized; pseudonymized data can remain personal data.
5. Browser storage: no user-content `localStorage`/`sessionStorage`, analytics,
   tracker, CDN, or third-party frontend library.
6. Session behavior: Secure, HttpOnly, SameSite=Strict, Path `/`, maximum
   30-minute lifetime, bounded in-process token fingerprints, logout revocation,
   and restart invalidation. No user/account database.
7. Log behavior: fixed operation/surface, method, status, response bytes, and
   duration only; no IP, target/query, body, prompt, response, mapping, cookie,
   invite code, or credential in application access rows. Docker rotation is
   `50 MiB × 3`; organizer infrastructure may retain connection metadata under
   its own policy.
8. Limits and exclusions: 20,000 characters and the currently deployed Hosted
   2.5 public PDF/OCR fixed 404,
   automatic-detection errors, heuristic Section 26 output, no legal
   certification, and no high-risk guarantee.
9. Security-incident guidance: stop sending data and contact support without
   attaching real text, access code, cookie, or credential.
10. Named policy facts: effective date/version, the responsible Hosted operator
    versus AI for Thai edge role, scope/jurisdiction wording approved by the
    owner, organizer metadata-policy link or an explicit statement that no
    public policy link is available, and a private privacy/rights/incident
    contact. These facts are required but are not currently established in the
    repository and must not be invented.

### Page 5: Help and FAQ `/help`

1. Choose Desktop versus Hosted before starting.
2. Desktop installation links and OS warning guidance.
3. Hosted invite/login/session-expiry steps.
4. Synthetic Quick Start, Privacy Scan, Safe AI Token/Surrogate, restoration,
   and PDPA Report walkthroughs.
5. Troubleshooting for invalid invite, rate limit, request in progress, slow
   provider, offline, oversized input, provider timeout/failure, report not
   ready, and session expiry.
6. FAQ for storage/logging, current PDF/OCR status, Extension Store status,
   detection accuracy,
   pseudonymization versus anonymization, Section 26, and report limitations.
7. Safe support process: original invite channel for beta users or upstream
   GitHub for source issues; submit time/timezone, workflow, shown status, HTTP
   status if known, version 2.5.0, and a newly created synthetic reproduction.
   Never submit access code, cookie, credential, or real text.
8. Provide a usable private privacy/security contact and an accessibility
   feedback path for public visitors who have no invite-origin channel. GitHub
   remains suitable only for non-confidential source issues.

### Page 6: Terms `/terms`

1. Invite-only Private Beta scope and capacity limitation.
2. Invite-code authorization, no resale/sharing, and user responsibility for
   input rights and risk.
3. Required human review for medical, legal, employment, education, and other
   high-impact decisions.
4. Prohibited automation, scraping, load testing, rate-limit bypass, attacks,
   illegal content, and attempts to discover another user's credentials,
   mapping, or session.
5. No guarantee of 100% detection, model output, uptime, SLA, legal suitability,
   or automatic PDPA compliance; requests may be limited or suspended for
   safety, cost, and availability.
6. Separate Desktop/Extension distribution status, current Hosted 2.5 public
   PDF/OCR exclusion,
   and links to Privacy, Help, and Downloads.
7. Effective date/version, responsible service role, scope/jurisdiction wording,
   and the same private contact route used by Privacy and Help, after owner
   review. Do not invent a legal entity or jurisdiction.

### Page 7: Internal 404

- Branded, compact, keyboard-accessible recovery page with Home, Hosted App,
  Downloads, and Help links.
- No request target reflection, search box, script, telemetry, or dynamic error
  detail. Preserve the fixed 404 status and security headers.

The branded page applies only to unknown human-facing web routes. `/api/*`
retains the current fixed, unbranded, non-HTML fail-closed 404. `404.html` is an
internal Nginx target; unknown methods, unknown assets, and near-match asset
paths preserve their denial behavior and never fall through to branded HTML.

### Cross-page content and accessibility contract

- Every page starts with a skip link targeting one unique `main`, exposes a
  visible focus indicator, uses `lang="th"`, marks genuine language changes,
  maintains one `h1` and ordered headings/landmarks, and identifies the current
  route independently of color with `aria-current="page"`.
- Mobile navigation is keyboard-operable, retains all routes when JavaScript is
  unavailable, never traps focus, and does not become a horizontal scroller.
  Every page reflows at 200% zoom without two-dimensional reading.
- Every long reference page has one job and one primary action, a short
  plain-language summary, and a local contents list when the body exceeds three
  major sections. Downloads leads with OS choice and defers hashes/attestation;
  Privacy leads with channel choice and lifecycle; Help groups by task/error;
  Terms remains uninterrupted readable legal text.
- Warnings, privacy boundaries, status, and the only recovery action stay
  visible. Disclosures may contain secondary verification or advanced evidence
  but never the sole warning, route, or remedy. Fragment URLs and browser Back
  remain meaningful after a disclosure opens.
- App inputs have programmatic labels and instructions; errors are associated
  with their fields and summarized when needed. Login, loading, success, expiry,
  rate-limit, and failure announcements are concise and non-repetitive. Focus
  moves deterministically after gate success, actionable error, result arrival,
  expiry, and reset. No status relies on color alone.

### Owner-supplied content required before approval-ready implementation

The repository does not establish the responsible public operator/legal role,
approved scope/jurisdiction wording, a private privacy/security contact, an
accessibility-feedback channel, or a public organizer metadata-policy URL.
Those facts are a content blocker, not permission to fabricate placeholders in
production. The owner must supply or explicitly approve them before Privacy,
Help, Terms, and the footer can be considered complete.

### Technical architecture recommendation

Use a static multi-page Nginx web surface plus one client-side application page;
do not migrate to Next.js for this redesign.

- Marketing/docs pages are authored as semantic static HTML with shared local
  CSS and little or no JavaScript.
- `/app` alone loads the existing application logic from an exact local
  JavaScript route. This removes the app payload and state initialization from
  the home page while retaining same-origin `/api/*` calls at the organizer
  edge.
- Suggested local assets: `base.css`, `marketing.css`, `app.css`, and `app.js`,
  plus the approved logo/font files. Every file requires an explicit Docker
  `COPY`, exact Nginx location, CSP compatibility, build-context check, runtime
  route check, and caller-facing acceptance check.
- The web container continues to return 404 for `/api/*`; the organizer routes
  the public `/api` prefix to the separate API surface. No API, auth, provider,
  or core route changes are part of the page split.
- `/app` includes `noindex,nofollow`, is excluded from `sitemap.xml`, and is
  disallowed in `robots.txt`. Home, Downloads, Privacy, Help, and Terms remain
  public sitemap entries. The internal 404 is never indexed.
- `/index.html` remains an exact GET alias for Home with a canonical root URL.
  Legacy `/#web-access`, `/#how-it-works`, `/#privacy-scan`, `/#safe-ai`, and
  `/#pdpa-report` fragments land on the matching Home teaser/CTA. Legacy
  `/#guided-demo` and `/#providerEvidenceCard` expose a compact `:target`-only
  “moved to Hosted App” handoff linking the exact `/app` fragment; this works
  without JavaScript because URL fragments never reach Nginx.
- Header/footer markup may remain duplicated across six fixed HTML files, but a
  single route/link/version contract test must prove the same canonical
  navigation, channel labels, and legal links on every page. Do not introduce a
  client-side header injector that would remove navigation when JavaScript
  fails. A deterministic build-time template is optional, not required.
- Keep no CDN, analytics, tracker, third-party frontend library, hydration, SSR,
  user database, or browser persistence.

Acceptance is route-specific after the split:

- Home must contain no invite input, raw-text editor, application script, or API
  initialization; `/app` must contain the complete gated application and load
  only the exact local `app.js`.
- The executable frontend session contract reads `app.html` plus `app.js`, not
  marketing copy in `index.html`. Local and public acceptance fetch and exercise
  `/app` explicitly.
- Docker/Nginx tests cover exact page/style/script routes, content types, allowed
  methods, near-match denial, and unknown POST/asset behavior.
- Unknown human-facing routes return branded HTML with status 404, while
  `/api/*` continues to return the current non-HTML fail-closed 404. No request
  target is reflected.
- A same-origin link crawl, sitemap/robots assertions, legacy-fragment checks,
  built-image browser tests, and public caller-facing acceptance cover the final
  routes independently.

Next.js would add dependency/build/hydration and CSP review without a current
requirement for SSR, CMS, parameterized content, personalization, or large-scale
localization. Reconsider it only if those requirements become real. Visual
quality is independent of Next.js; the static production page can and must
match Concept C's approved art direction.

### Planned delivery gates after approval

1. Lock this route/content plan with the user before code changes.
2. Establish shared production tokens, header/footer, and exact route skeleton.
3. Rebuild Home against the original Concept C reference and obtain visual
   approval at `1440×729` before extending its system to other pages.
4. Move the intact authenticated application surface to `/app`; do not rewrite
   API behavior during the visual split.
5. Apply the approved visual system to Downloads, Privacy, Help, Terms, and 404
   without removing any required content above.
6. Add Docker, Nginx, CSP, tests, sitemap/robots, and backward-compatible link
   coverage for every route and asset.
7. Verify the built image at all required viewports and interaction/fallback
   modes, then run independent art-direction, frontend/product, and
   UX/accessibility review until no material disagreement remains.
8. Update `STATE.md`, `README.md`, and this document. Keep public deployment and
   public-edge acceptance explicitly unverified unless separately authorized.

## Brand and logo construction requirements

The next logo pass must start from a written construction system before editing
the SVG path data.

1. Build the shield on an explicit geometric grid with a vertical optical axis.
2. Define width, shoulder height, apex, corner radii, stroke weight, and optical
   corrections numerically.
3. Keep the shield optically symmetric. Intentional asymmetry is allowed only in
   the canonical flame/mask motif and must be explained by the construction.
4. Preserve recognizability of the original shield plus split mask/flame mark.
   The flame is the distinctive mnemonic and should not collapse into a generic
   police or sports badge.
5. Plan every cut, join, cap, negative space, and overlap. Avoid incidental
   tangencies and unmatched line endings.
6. Define primary, one-color, inverse, and small-size variants. A favicon may use
   less detail than the main mark but must preserve the same geometry and visual
   weight.
7. Test at 16, 24, 32, 42, 64, and 128 CSS pixels on light and blue fields.
8. Define minimum size and clear space before integration.
9. Keep colors compatible with the website palette. The current exploration
   uses blue `#3266A8`, muted red `#B85868`, paper `#F3F1EB`, and ink `#151515`,
   but the final semantic roles remain subject to visual review.

User's latest verdict: the current candidate looks asymmetrical and its line
cuts look unplanned. Do not polish the existing paths blindly. Reconstruct the
mark from a grid and compare it directly with the canonical source.

### Numeric construction system (revision B2, adversarial review passed)

- Coordinate system: every variant is derived from a `64 × 64` unit mark box.
  The shield's exact vertical axis is `x = 32`; no optical offset is permitted
  on the shield. Clear space is external to this box and is not represented as
  padding inside the SVG view box.
- Outer shield: crown `(32, 8)`, shoulders `(7, 16)` and `(57, 16)`, vertical
  sides to `y = 32`, then matched cubic curves to apex `(32, 61)`. The lower
  curves use reflected control points `(57,45)/(48.5,54)` and
  `(15.5,54)/(7,45)`. The `2`-unit Ink outline uses round joins.
- Inner field: crown `(32, 14)`, shoulders `(13, 20)` and `(51, 20)`, sides to
  `y = 32`, then reflected curves to `(32, 55)`. Its `1.25`-unit outline creates
  a deliberate double-shield reference to the historical mark.
- Canonical motif: the broad left mask and right-rising flame are separate
  numeric paths, not a generic mirrored flame. The mask uses only control points
  inside `x = 12.5…35`, `y = 14.5…50`; the flame uses only control points inside
  `x = 29.25…56`, `y = 2…50.5` and deliberately rises above the shield crown.
  This controlled motif asymmetry, including unequal eyes, is the only
  non-mirrored construction.
- Planned boundary and cuts: both motif fills share one exact irregular contour
  from the upper junction `(31.5, 14.5)` to the lower junction `(30.5, 50)`;
  that contour is rendered once as the Ink seam in the main mark and once as a
  transparent cut in the one-color and inverse variants. The eye apertures are
  unequal canonical shapes. The nearest eye/seam centerlines are `3.094` units
  apart; after the `1.25`-unit eye and `1.75`-unit seam strokes are accounted
  for, `1.594` units of edge-to-edge space remains, approximately `0.797 CSS px`
  at the `32 px` main-mark minimum. No seam ends tangentially against an eye or
  the motif perimeter.
- Stroke hierarchy: `2` units for the shield perimeter, `1.75` for mask/flame
  perimeters, and `1.25` for the inner shield and eyes. All exposed joins and
  caps are round. The main, one-color, and inverse outer footprint includes the
  same `2`-unit shield perimeter.
- Color roles: Protection Blue `#3266A8` is the symmetric shield; Signal Coral
  `#B85868` is the canonical detected/flame side; Review Gold `#E2B95F` is
  restricted to the human mask and opposite eye; Editorial Ink `#151515`
  defines structure; Paper `#F3F1EB` is the inner field and inverse color. Gold
  is a heritage mnemonic, not a general warning or compliance status.
- Variants: `main` uses the five fixed roles above; `one-color` is fixed Ink with
  transparent field, seam, and eye cuts; `inverse` is fixed Paper with the same
  cuts on blue or Ink; `favicon` is a simplified, non-semantic mnemonic for
  light browser chrome; and
  `favicon-inverse` is a Paper one-color small mark for blue/dark fields. Tiny
  favicons do not claim to communicate detected/protected meaning through color.
- Sizing and clear space: the main mark minimum is `32 CSS px`; use a favicon
  variant below that size. Required clear space is `8` units outside the
  `64 × 64` mark box, producing an `80 × 80` minimum usage box. The test matrix
  is `16`, `24`, `32`, `42`, `64`, and `128 CSS px`; both backgrounds must show
  the appropriate main/small variant, and every fixed-color variant receives at
  least one full size-row rather than a single token specimen.

## Production integration constraints

Production is an explicit static Nginx surface, not a general file server.
Adding an asset is incomplete until all of these are updated and verified:

- `web/Dockerfile` copies the exact file.
- `web/nginx.conf` exposes an exact allowlisted route with the intended content
  type and method behavior.
- CSP, security headers, privacy behavior, and no-store policy remain correct.
- Automated route, image-build, mixed-content, accessibility, and acceptance
  tests cover the change.
- The built container serves the asset and production HTML references the same
  exact route.

Read `STATE.md`, `docs/DEPLOY-DESIGN.md`, `docs/DEPLOY-DAY.md`, and
`docs/PRODUCTION-READINESS.md` before altering production behavior. Do not weaken
authentication, privacy boundaries, route allowlists, log privacy, or the
Desktop versus Hosted Web data-location explanation for visual convenience.

### Thai typeface decision

- Family: Anuphan, variable weight `100…700`, normal style. It is used for Thai
  and Latin UI text with `font-display: swap`; the fallback remains
  `"Leelawadee UI", Tahoma, system-ui, sans-serif` so content is never gated on
  font loading.
- Authoritative source: the `google/fonts` first-party Anuphan directory and
  Google Fonts' current `fonts.gstatic.com` v6 WOFF2 distribution. The family
  copyright is “Copyright 2019 The Anuphan Project Authors” and the included
  license is SIL Open Font License 1.1.
- Local subsets: `anuphan-thai.woff2` covers Thai, Thai combining behavior, ZWJ/
  ZWNJ, dotted circle, and the marks declared by Google Fonts; `anuphan-latin.woff2`
  covers the Latin UI and shared punctuation. Vietnamese and Latin Extended are
  intentionally omitted because production copy does not require them.
- Pinned SHA-256: Thai
  `8a03cb45df9decacc349c794b1d626363109d99affb74f698a27d019996c220f`;
  Latin `3a98eb4685d98ab59073f8b2f9995629e23f850f737144025b3ce491f20372d6`;
  license `94da26c98ca8d2ec3555ad30828a4184edfdf5832df92ae8cf4edd490e9ee655`.
- Source URLs are pinned to
  `https://fonts.gstatic.com/s/anuphan/v6/2sDeZGxYgY7LkLT0mX4Dan29.woff2`
  (Thai),
  `https://fonts.gstatic.com/s/anuphan/v6/2sDeZGxYgY7LkLT0mWoDag.woff2`
  (Latin), and
  `https://github.com/google/fonts/blob/main/ofl/anuphan/OFL.txt` (license).
  Production will make no request to any of these origins.

## Required viewport and interaction evidence

The selected prototype has been visually checked at these desktop viewports:

- 1440 x 729
- 1366 x 768
- 1440 x 900

Those checks found no horizontal overflow and kept the hero CTA and product
poster visible. They are prototype evidence only and must be repeated after
production integration.

Before production-ready status, verify at minimum:

- 1440 x 729, 1366 x 768, and 1440 x 900.
- A representative tablet portrait and landscape viewport.
- 390 x 844 and 360 x 800 mobile viewports.
- Keyboard-only navigation, visible focus, skip link, and logical focus order.
- Thai line breaking, font loading, display at 100% and 200% zoom, and fallback
  behavior when font loading fails.
- Default motion, `prefers-reduced-motion: reduce`, and no content hidden behind
  entrance animations when JavaScript fails.
- No horizontal overflow, clipped CTA, obstructed sticky header, or inaccessible
  product-demo controls.
- Performance and layout stability with locally served production assets.

## Implementation status after planning closeout

No implementation, protected-deployment, or caller-verification gate remains for
the deployed six-page redesign at revision `dbcfe17b`. The approved Hosted 3.0
product/queue contract below is a separate staged release. Its local Stage 1
internal Standard/Priority authority and timing foundation now exists and has
built-image import evidence, but Nginx still exposes the 16-route Hosted 2.5
surface and denies all 24 planned additions. No browser-accessible Standard
entry, preview, PDF, queue, Hosted 3.0 UI, `/developers` page, product-version
bump, protected deployment, or public Hosted 3.0 caller evidence exists yet.

The existing content dependency is still owner-supplied operator, jurisdiction,
policy-date, private-contact, accessibility-feedback, and organizer-metadata-
policy facts. The live pages state the current limitation and do not fabricate
those facts. The organizer edge's accepted lack of plain-HTTP redirect also
remains external and is not represented as secure.

## Hosted 3.0 competitive upgrade

### Public benchmark evidence, 2026-08-16

The benchmark is a time-bounded review of public deployment surfaces, not an
audit of competitors' private code or claims. Chrome opened only public pages
and used only a built-in synthetic example or the site's documented Guest
entry. No access control was bypassed, no credentials were guessed, and no real
personal data was submitted.

- Public root availability at the time of the review: Teams 01, 02, 03, 05, 07,
  10, 13, 14, and 15 returned `200`; Teams 04, 06, 09, 11, and 12 returned
  `503`; Team 16 failed the TLS connection. Team 15 exposed a generic Dify
  administrator sign-in, while Team 14 exposed a working but generically titled
  upload workspace. Availability is a snapshot and may change.
- Team 03, TaLaem, set the strongest instant-utility benchmark. Its first page
  offers text, screenshot, and audio paths with no signup, LINE OA continuity,
  readable modes, spoken guidance, safety actions, evaluation claims, and a
  public developer guide/playground. The built-in synthetic AIS example
  completed against the public deployment and returned risk level, reasons,
  detected signals, recommended actions, verified contact numbers, and a
  shareable family summary. Its developer page documents a production base URL,
  text/image/audio endpoints, predictable errors, request IDs, privacy rules,
  rate limits, health/readiness, and a live playground. These are observed page
  behaviors and claims, not independently verified source-code guarantees.
- Team 10, ThaiWorksheet AI, set the strongest end-to-end workflow benchmark:
  a polished Thai-first builder, a 30-item backup library, multiple source types
  (text, PDF, audio/subtitle, web/YouTube), explicit rights/privacy confirmation,
  model choice, draft-first review, PDF/DOCX output, and separate answers. Some
  actions remain access-key gated, but the public page makes the workflow and
  deliverable immediately concrete.
- Team 13, MeeCopilot, set the strongest product-narrative and evidence-first
  benchmark. It presents one killer feature, live questions with confidence and
  transcript evidence, decisions/action items, revision/audit concepts, truthful
  media/browser boundaries, and a one-click Guest workspace. The public Guest
  action successfully created a short-lived workspace and management link; the
  link/token is intentionally not retained in project evidence.
- Team 01 provides a polished, focused authorized-user gate and a concrete
  `49 cases / 5 professions / 20 stations` proposition. Team 05 has strong
  domain specificity, LINE continuity, image analysis, AI assistance, weather,
  and a visually recognizable mascot. Team 02 has ambitious marketplace
  positioning, but the inspected page reported an unconfigured Pathumma path
  using a backup model and rendered many broken images. Teams 07, 14, and 15
  expose narrower login/upload/admin-first surfaces.
- At `390×844`, the three strongest public benchmarks (Teams 03, 10, and 13)
  produced no horizontal document overflow. Team 03 retained the clearest
  mobile first action; Team 13's created Guest session opened a usable mobile
  dashboard. Team 10 remained usable but its display typography and top status
  strip were visually denser.

Durable evidence is in
`output/playwright/competitor-team{NN}-home-1440x729.png` for every public host
that rendered, plus `competitor-team03-home-390x844.png`,
`competitor-team10-home-390x844.png`, and
`competitor-team13-home-390x844.png`. These screenshots are comparative research,
not permission to copy visual identity, text, or proprietary implementation.

### Relative position

AI Guard already leads the inspected public field in explicit privacy-boundary
truth, fail-closed routing, same-origin/no-tracker delivery, browser-state
discipline, deterministic error handling, caller-facing production acceptance,
and the depth of request-scoped protection evidence. The current public weakness
is product proof: an invite wall prevents a judge from immediately exercising
the real Hosted runtime, the public Home preview is illustrative rather than a
completed request, the API contract has no public developer surface, and the
`2.5.0` product label understates the deployed work. The authenticated workspace
also reveals its strongest evidence only after a comparatively long workflow.

<details>
<summary>Superseded single-run Synthetic Guest exploration (historical, non-governing)</summary>

The material in this collapsed block records the reviewed path that led to the
final decision. Its product/authority decisions are not an implementation
contract: the ten-minute synthetic-only Guest, one-execution budget, invite-only
custom upload, 32-route final count, and Guest-versus-invite workspace split are
rejected. The approved contract after this block is authoritative wherever
wording differs.

The approved contract incorporates only these named modality-neutral technical
foundations from the collapsed record: `PDF to Protected Structured Text scope`
(parser isolation, input limits, artifact integrity, renderer, provenance, and
upload behavior); the document field semantics and document-specific error rows
under `Exact route and compatibility contract`; and `Content-stateless approval
capability` (AES-GCM envelope, deterministic `pg-v1` generation, replay
properties, and no-content registry). All old identity labels, cookies, route
counts, authorization matrices, request/response wire tables, scope-specific
ticket branches/TTLs, rates, execution budgets, first-fold copy, and workflow
visibility remain superseded. The authoritative section restates the replacement
route, request/response, approval-timing, and ticket unions so implementation
never has to infer the override.

### Superseded Hosted 3.0 release bar

1. **Instant synthetic preview, then the user decides.** The first Guest action
   never calls the provider. It runs the provider-free protection preview for a
   server-owned allowlisted scenario, shows the exact protected payload and
   outbound-gate result, and then asks for explicit approval with truthful copy:
   “Send this protected synthetic example to Pathumma.” One approval may cause
   up to three bounded attempts to the same provider under the existing retry
   policy; it never means exactly one network attempt.
2. **Preview Before Provider.** The authenticated custom-text path uses the same
   inspect/approve principle. Preview returns protected text, detected types,
   residual-policy result, non-blocking Section-26/Prompt-Risk signals, and an
   opaque expiring approval capability. Execute must send the exact approved
   protected bytes or fail closed. No raw text or mapping is stored in the
   approval registry or browser persistence.
3. **A concise Protection Decision before deep evidence.** Lead with what was
   detected, what changed, the exact **AI Guard outbound-gate result** (`no
   residual signal detected`, `blocked`, or `uncertain`), the persistent human-
   review limitation, and the next action. Never label the payload generally
   “safe” or “allowed.” Keep Raw-vs-Protected, provider-bound text, receipt,
   Prompt Risk, presenter mode, glossary, timing, and digest as evidence rather
   than forcing a judge to decode them before understanding the result.
4. **Public Contract and Evidence surface.** Publish `/developers` as an
   informational, same-origin contract/evidence page, not a claim that arbitrary
   third-party API access is available. It documents product versus HTTP
   contract versions, exact Guest-versus-invite boundaries, new-route examples,
   deterministic errors/retries, privacy path, request IDs on the new 3.0
   operations, liveness semantics, evaluation method, and a synthetic-only
   playground. It explicitly says there is no public developer credential,
   arbitrary unauthenticated processing, third-party CORS contract, or provider
   readiness endpoint. It also states the protocol boundary honestly: an
   authorized client that holds a valid preview ticket can call execute; the
   server proves authority, payload binding, expiry, and one-use consumption,
   not that a human used the official button. Current `/health` remains liveness
   only.
5. **Truthful benchmark proof.** The judged flow gets one plain-language metric
   statement plus corpus revision and a methodology link. Detailed 138-case
   synthetic/adversarial results, 18 evaluated types, exact typed metrics,
   protective-character recall, hard negatives, Section-26 separation, and
   limitations stay on `/developers`. The release must rerun the locked corpus
   and prove that its detector/model hashes equal the deployed Hosted 3.0 hashes;
   “18 evaluated types” must not imply population-complete coverage.
6. **Hosted product `3.0.0`, not a label patch.** `core/VERSION`, health,
   reports/receipts, page metadata, channel labels, README/STATE, release checks,
   public acceptance, and deployed evidence move together only after the new
   experience passes. The product SemVer and HTTP contract version remain
   separate facts: an additive Hosted 3.0 release does not silently change
   `X-AIGuard-Contract-Version: 2`; a contract bump requires its own compatibility
   and migration decision.

### Entry, scenario, and visible product story

- Public copy calls the feature **Synthetic Guest demo**. “Judge Mode” is an
  internal acceptance label only. Home keeps Desktop as its primary boundary
  but replaces the old secondary invite-only CTA with `ลอง Hosted 3.0
  ด้วยตัวอย่างสังเคราะห์`. That action is visible in the `1440×729` and
  `390×844` first fold and opens `/app#synthetic-demo`.
- The `/app` first fold presents two explicit lanes: `ลองเปลี่ยน PDF ตัวอย่างเป็น
  Protected Markdown` and `ใช้รหัสเชิญกับข้อความหรือ PDF ของคุณ`. “ลอง” promises
  immediate access to a provider-free preview, not a fixed end-to-end completion
  time. Guest copy says: `ไฟล์เรซูเม่นี้เป็นข้อมูลสมมติของระบบ ไม่มีการเลือกหรือ
  อัปโหลดไฟล์จากเครื่องคุณ · หนึ่งรอบที่อนุมัติให้ Pathumma ภายใน session 10
  นาที · Preview ไม่ใช้สิทธิ์ · retry ภายในยังนับเป็นรอบเดิม · session ใหม่และ
  ความจุระบบไม่รับประกัน`. A persistent `SYNTHETIC GUEST` badge remains visible.
  The invite lane retains the adjacent raw-data boundary and no-public-signup
  truth.
- The single default scenario is `hr-resume-pdf-structured-v1`: a server-owned,
  hash-pinned text-layer Thai résumé PDF with fictional identity/contact details,
  address, work history, and skills. The first visible promise is: **a fictional
  Thai résumé PDF becomes editable Protected Markdown; Pathumma never receives
  the PDF and receives only the exact protected text you reviewed**. The adjacent
  visible limitation says that AI Guard replaces PII it detects, undetected PII
  may remain, and human review is required. Additional scenarios are out of the
  first release unless they strengthen that exact story.
- Guest uses one three-stage transient canvas, not the full 5,532-pixel
  authenticated page. **1 Prepare & protect** shows one synthetic-PDF identity
  card (name, pages, fictional status), exact protected extraction, and a compact
  Protection Decision. **2 Approve** shows the exact payload and the sentence
  `Pathumma receives this protected text, never the PDF`, followed immediately
  by the single approval control. **3 Protected Markdown** makes the structured
  protected artifact the sole primary result. `Protected extraction` and
  `Technical receipt` are the only two disclosures. Parser limits, hashes,
  metrics, glossary, presenter tools, and contract detail never enter the primary
  canvas. At tablet/mobile only one reading pane is open at a time; comparison is
  a labelled toggle/vertical stack, never a side-by-side diff.
- The post-provider sequence is explicit: `synthetic PDF was read inside AI
  Guard → PII detected by AI Guard was replaced → you approved these exact protected bytes →
  Pathumma received only those bytes → AI Guard validated and rendered Protected
  Markdown`. There is no restoration in the PDF path. The compact live receipt
  contains Hosted version, value-free request ID, provider/model and actual
  attempt count, scenario/registry revision, measured duration, protected digest
  match, outbound-gate result, expected-token integrity, and structured-output
  validation. The two visible human warnings are `รูปภาพในหน้า … ไม่ได้ถูกอ่าน;
  ระบบใช้เฉพาะข้อความที่เลือกได้ กรุณาเทียบกับ PDF ต้นฉบับ` and `PDF ต้นฉบับ
  ไม่ได้ถูกแก้หรือทำให้ปลอดข้อมูล` rather than internal error-code labels.

### PDF to Protected Structured Text scope

The Hosted 3.0 plan now uses the owner's PDF transformation as its single judged
story. This replaces the earlier restored three-point résumé summary. It does not
revive PDF redaction or OCR: the product reads a bounded text-layer PDF, protects
its extracted text, and asks Pathumma only to classify each approved immutable
protected segment. AI Guard validates those classifications, groups them in a
fixed order, and renders reusable protected Markdown with fixed headings and
provenance.

#### Product and privacy boundary

- The feature name is **PDF to Protected Structured Text**. The source PDF is
  unchanged and is never returned as sanitized. The primary output is protected
  Markdown plus plain text; there are no black boxes and no restored PII.
- Guest uses only the hash-pinned fictional PDF shipped with the scenario. It has
  no file input or upload state. Invite users see a native labelled PDF file
  input and optional drag/drop target, but selection is local and triggers no
  request. Before the explicit `Upload & extract` action, an adjacent notice says
  `ไฟล์ PDF ต้นฉบับจะผ่าน organizer proxy และ AI Guard เพื่อแยกข้อความชั่วคราว
  แต่จะไม่ถูกส่งให้ Pathumma · ระบบไม่ทำ secure zeroization · organizer/API อาจมี
  buffering นอกขอบเขตที่ AI Guard ตรวจยืนยันได้`.
- The first release accepts a usable selectable text layer only. Repeated product
  wording everywhere is: `Text-layer PDF → Protected Markdown: supported in
  Hosted 3.0`; `the source PDF is unchanged`; `no redacted/rebuilt PDF`;
  `scanned/image-only PDF and OCR: unsupported`. Home replaces its old PDF/OCR
  trust item inside the existing six-scene budget; it does not add a scene or a
  generic `PDF supported` badge.

#### Secretless parser boundary

- Arbitrary document bytes never enter a PDF library inside the core container.
  A new `pdf-parser` container has no application secrets, no environment beyond
  its fixed runtime, `network_mode: none`, read-only root, non-root UID, all Linux
  capabilities dropped, `no-new-privileges`, a pinned seccomp profile, bounded
  PIDs, one CPU, `512 MiB` memory, and private tmpfs work storage. It receives
  length-prefixed jobs over a Unix-domain socket in a shared socket-only volume;
  core cannot pass user filenames or paths. Parser output is strict length-
  prefixed JSON capped at `128 KiB`.
- The authenticated core acquires document capacity before reading the body,
  then streams and hashes at most `5 MiB` directly into the parser socket without
  joining it in memory. The parser writes fixed random job IDs to its private
  tmpfs, unlinks files and releases references on normal completion, disconnect,
  cancellation, ten-second timeout, parser crash, and shutdown. Documentation
  says `unlinked and references released`, never securely erased. It also states
  that buffering at the organizer edge is outside AI Guard's observable control.
- The parser image contains only hash-locked, license-recorded qpdf/pikepdf and
  the existing permissive pdfplumber/pypdfium2 text stack. QPDF validation and a
  recursive pikepdf object walk inspect decoded object streams. Catalog, page,
  resource, and content dictionaries use an explicit inert-key allowlist. Any
  annotation or action dictionary is rejected regardless of subtype, including
  URI, JavaScript, launch, submit/import, named, rendition, movie/sound, GoToR,
  and GoToE actions. Encryption/passwords, name trees, embedded/associated files,
  AcroForm/XFA, optional-content groups, RichMedia/3D, collections, external
  references, or an incomplete/unknown traversal also fail closed. Page content-
  stream and PDFium object inspection recurse through form XObjects, inline
  images, and drawing operators; adversarial fixtures cover compressed object
  streams, nested forms, inline images, tiny/unrelated text overlays, cycles,
  bombs, malformed cross-references, and parser crashes.
- Parser safety limits are exactly `5 MiB`, `10` pages, `2,000` points on either
  page dimension, `8,000` extracted Unicode code points, and `80` immutable text
  segments. The provider-executable first-release limit is `32` segments; a
  parser result above 32 fails `document_too_complex` before protection or ticket
  minting. Every page must contain at least 80 selectable non-whitespace
  characters across at least five text lines, median glyph height between 6 and
  36 points, line-box union area at least 3% of page area, and line-box convex-
  hull area at least 20% of page area. Raster bounding boxes are unioned after
  clipping; any single raster above 10% or combined raster area above 15% of a
  page fails fixed `pdf_visual_content_unsupported`. These deterministic gates
  reject raster-dominant/scanned pages and tiny-overlay cases but do not claim to
  prove that selectable text corresponds semantically to every visual. Accepted
  pages with any smaller raster or vector drawing are listed in
  `omitted_visual_page_numbers`; the always-visible warning says that images,
  diagrams, icons, lines, and visual layout were not interpreted and the result
  must be compared with the source. Inspection uncertainty fails closed.
  Paddle/OCR is absent from the parser and core images.
- Nginx creates an exact document-preview lane: `4r/m` global, `1r/m` per invite
  throttle key, burst one, and one global/per-caller connection. Core verifies
  invite authority before acquiring a one-job document semaphore. Busy work
  fails fixed `429 document_busy`; parser absence/crash/timeout fails fixed `503
  document_parser_unavailable`. Only the two exact preview aliases override the
  normal body limit to `5m`, disable request buffering, and accept the PDF media
  type. Guest synthetic PDF parsing uses the Guest preview lane but shares the
  same one-job parser semaphore, so it cannot bypass document capacity; a busy
  parser returns the same fixed `document_busy` response before processing.
  Document execute uses the existing authenticated provider lane and shared
  unresolved-request ownership.

#### Exact operations and protected artifact

- `POST /api/document-preview` plus `/api/v1/document-preview` accepts exactly one
  non-empty raw body with one parameter-free `Content-Type: application/pdf`, no
  duplicate content type/length, no content encoding, no query, and a valid PDF
  signature. It rejects multipart, unknown/empty/chunk-over-limit bodies, and
  closes the connection on early capacity/size failure. Success returns page/
  extraction metadata, omitted-visual page numbers, exact Token-mode protected
  text, detected counts/types, outbound-gate result, human-review warnings,
  a fresh request-scoped `source_receipt_id`, protected SHA-256, and a one-use
  approval ticket. The raw source SHA-256 remains inside the encrypted ticket and
  is never returned. The PDF and original↔token mapping are released before the
  response.
- `POST /api/document-execute` plus `/api/v1/document-execute` accepts strict JSON
  `{protected_text,ticket}`. Extracted source is capped at 8,000 code points;
  the general protected-result seam retains defense-in-depth hard stops at 16,000
  code points and 48 KiB UTF-8, but a provider-executable document ticket is
  minted only when the protected text is at most 8,000 code points, contains at
  most 32 immutable segments, and its exact schema-plus-segments provider request
  is at most 9,120 UTF-8 bytes. The exact execute aliases permit at most `96k`
  request bodies. The ticket binds source PDF SHA-256, extraction/parser revision,
  page/character/visual metadata, the fresh 128-bit random source receipt ID,
  protected digest, Token-generation revision,
  fixed provider/model, and `structure-protected-document-classifications-v1`
  prompt.
  Execute verifies the digest, rescans the protected text, and sends those exact
  bytes. The PDF is never uploaded a second time.
- Before provider use, AI Guard deterministically normalizes the extracted
  protected text into at most 32 provider-executable immutable, ordered segments
  with opaque IDs.
  Pathumma receives those exact segments and may return only a source-anchored
  JSON classification array of `classifications[{segment_id,role}]` in the exact
  supplied segment order, where `role` is a fixed server allowlist and no
  provider-authored heading or content string is allowed. Every returned ID must
  match its input position exactly; foreign, duplicate, missing, reordered, or
  extra IDs fail closed. AI Guard, not the provider, deterministically groups the
  classifications by fixed role order and renders the fixed Thai headings. AI
  Guard also verifies exact Token set and multiplicities and scans
  the reconstructed artifact for residual PII. This makes the output a lossless
  reorganization of protected source segments rather than an AI-written summary;
  semantic classification can still be wrong and requires human review.
- The provider call runs in a killable document-only child process. It requests
  identity transfer encoding, rejects any non-identity `Content-Encoding`, and
  consumes `iter_raw()` bytes so transparent HTTP decompression cannot allocate
  an oversized body before the limit. The outer HTTP response is streamed under
  a `32 KiB` total wire-body cap before any JSON parse; invalid or misleading
  `Content-Length`, an over-limit chunk stream, or an extracted provider content
  value over the separate `32 KiB` AST cap fails closed. The parent owns an
  absolute monotonic `200`-second deadline covering
  child startup, connect, write, headers, and every response chunk, then kills and
  reaps the child so a slow-drip response cannot extend the admitted provider job.
  The document-only request uses `max_tokens:4096` after the
  deployed gateway truncated the 80-segment fixture under the generic 1,024-token
  client setting. The token setting is not trusted as a byte limit. URLs, HTML,
  images, code, tables, raw
  attributes, free text, unknown roles/keys, excessive counts, and invalid Unicode
  fail closed. AI Guard deterministically renders semantic HTML and escaped
  canonical Markdown; the browser never injects provider HTML. The protected
  Markdown is primary; `Protected extraction` is an optional comparison disclosure
  and `Technical receipt` is the second and final disclosure. Before release, the
  release envelope must pass two measured Pathumma boundaries without truncation:
  an exact 8,000-code-point protected-text fixture and an exact 32-segment/
  9,120-byte provider request containing representative Thai text plus protection
  Tokens.
  The 32-segment cap is the largest currently locked release fixture; parser
  inspection remains bounded independently at 80 segments.
- Every product-generated copy/download automatically begins with an embedded
  provenance header, and no product action emits a header-free artifact:
  `AI Guard Hosted 3.0 · protected/pseudonymized, not anonymous · source PDF is
  unchanged/not sanitized · PII was not restored · selectable text layer only ·
  OCR/images/diagrams/visual layout were not read · human review required`,
  followed by omitted-visual pages, Guest scenario+registry revision or invite
  request-scoped source receipt ID+parser/extraction revision, and Hosted version.
  The `.md`, `.txt`, and source-bytes-free JSON receipt repeat the same warnings/
  facts and never contain the source PDF, raw source SHA-256, extracted source,
  mapping, original/token pairs, ticket, or access authority. The UI explains
  that the receipt ID correlates artifacts only within that generated request;
  it is random and not a stable document fingerprint across sessions.

#### Upload interaction and route/page impact

- Invite upload uses a native keyboard-reachable file input; drag/drop is an
  optional enhancement. Selected filename, type, and size are announced but not
  uploaded. `Upload & extract` is the only network action. Local selection,
  upload, parser queue, extraction/protection, preview, and reset have restrained
  live-region messages. Replacement/reset invalidates the preview and ticket.
  Wrong type, size/page/text limit, password/active content, malformed file,
  insufficient text layer, parser busy/timeout/unavailable, residual block, and
  provider failure use associated actionable summaries and deterministic focus.
  An invite user's explicit `Upload & extract` transition focuses the completed
  document-preview heading. The first built mobile Stage 6 review found that
  custom-text Preview lost browser focus after its initiating button was
  disabled/re-enabled, so the candidate now focuses the same completed preview
  heading for custom text as well as PDF. Provider completion focuses the
  task-specific result heading.
  No-JavaScript keeps document controls inert and exposes Desktop, Help, and
  Privacy recovery; text paste is offered only after JavaScript is restored.
- The old `/redact-pdf` and `/v1/redact-pdf` stay fixed proxy-level 404. OCR stays
  unsupported because the verified one-page profile took about `221 s`, roughly
  both CPUs, and hit `6 GiB`. The two new document operations and aliases expand
  the exact API allowlist from 28 to 32 routes. They add no eighth page: Home owns
  one compact cue, `/app` owns Guest and invite interaction, `/developers` owns
  contract/parser/evaluation detail, and Privacy/Help/Terms own the repeated
  boundary, artifact, and recovery wording.

### Proposed public information-architecture delta

Hosted 3.0 adds one public route to the deployed six-page architecture. Until
the route passes implementation, exact serving, review, and deployment gates,
the production site remains the existing six pages plus internal 404.

| Proposed route | Production file | Page archetype | Indexing and primary job |
| --- | --- | --- | --- |
| `/developers` | `developers.html` | Calm reference/evidence page using the shared production shell | Public and included in `sitemap.xml`; explains the same-origin contract, synthetic-only playground, evaluation method, and limits without implying public arbitrary-text credentials |

The shared footer adds `Contract & evidence` on every public page. The header
retains its existing primary-route budget rather than crowding the first fold;
Home and the `/app` Guest journey add one contextual evidence link instead of
duplicating developer detail. `/app` remains `noindex,nofollow` and excluded from
the sitemap; `/developers` is readable without JavaScript, authentication, or a
Guest cookie. A direct synthetic playground action hands off to
`/app#synthetic-demo`; it does not execute API requests inside the reference
page.

Hosted 3.0 has an explicit route-impact budget:

- **Home `/`:** change only the Hosted secondary CTA, one compact 3.0 proof
  strip, one availability-band replacement that says `text-layer PDF → Protected
  Markdown` while keeping scanned/OCR unsupported, and channel version label.
  Keep the approved six-scene Concept C rhythm; do not embed the Guest controls,
  contract tables, metrics, or receipt detail.
- **Hosted `/app`:** add the two-lane first fold and three-stage Guest canvas;
  migrate invite Safe AI to preview/approve/execute while retaining the current
  scenarios, `/guard`, report, evidence, presenter, and recovery tools behind
  authentication and optional disclosures. Guest never sees the long advanced
  workspace.
- **Contract & evidence `/developers`:** add the one new calm-reference page and
  own every detailed contract, evaluation, retry, digest, liveness, and
  limitation explanation.
- **Downloads `/downloads`:** do not imply a Hosted binary. Update only the
  separate Hosted `3.0.0` channel status/link; Desktop and Extension version and
  distribution facts remain independent.
- **Privacy `/privacy`:** add the Guest cookie, ten-minute authority, encrypted
  approval ticket, in-memory replay hashes, Pathumma attempt boundary, raw-PDF
  organizer/core/transient-parser boundary, source-file cleanup limitation,
  copied-artifact provenance, and no-browser-persistence lifecycle in plain
  language.
- **Help `/help`:** add task-based Guest/invite switching, PDF selection versus
  explicit upload, expiry, new preview, parser busy/unsupported-file/rate/provider
  failure, consumed-ticket, and protected-artifact recovery.
- **Terms `/terms`:** add concise synthetic-demo, one approved provider run,
  text-layer-PDF limits, source-file and protected-artifact responsibility,
  availability/rate-limit, fictional-data, and human-review terms only after the
  owner approves the wording; do not invent operator/jurisdiction facts.
- **Internal 404:** preserve the approved brand and four primary recovery links.
  `/api/*` and asset/source near-matches remain fixed unbranded failures; no
  request target is reflected.

### Exact route and compatibility contract

Existing canonical and `/v1` aliases for auth, `detect`, `guard`, `roundtrip`,
and `analyze-report` remain byte-for-contract compatible under HTTP contract 2.
`/health` retains its exact schema and liveness semantics; its `version` value is
the intentional product change from `2.5.0` to `3.0.0`. Hosted 3.0 does not
mutate or repurpose `/roundtrip`. The web app migrates to additive operations
after their independent tests pass:

- `POST /api/auth/guest` and `/api/v1/auth/guest`
- `POST /api/auth/guest/end` and `/api/v1/auth/guest/end`
- `POST /api/guest/preview` and `/api/v1/guest/preview`
- `POST /api/guest/execute` and `/api/v1/guest/execute`
- `POST /api/protection-preview` and `/api/v1/protection-preview`
- `POST /api/protection-execute` and `/api/v1/protection-execute`
- `POST /api/document-preview` and `/api/v1/document-preview`
- `POST /api/document-execute` and `/api/v1/document-execute`

The API proxy allowlist therefore grows deliberately from 16 exact locations to
32, not through a prefix route. Tests enumerate all 32 and continue to deny every
unlisted alias.

The Guest start operation is unauthenticated but same-origin and exact-route
only. Guest preview/execute require the separate Guest capability; custom
preview/execute require the existing invite session. Every new data operation
still passes through API Nginx's internal key and HTTP-contract header. Core
middleware, operation maps, protected/public sets, exact allowlists, rate lanes,
fixed value-free error translation, `404` near-match denials, Docker health,
tests, and public acceptance must name the new routes explicitly. Unknown
methods, `/v2`, `/v3`, broad prefixes, and unlisted near-matches remain `404` or
method-denied exactly as specified; no implicit version-prefix routing is added.

The strict request schemas are intentionally narrow:

- Guest start accepts no user content and returns only the short-lived Guest
  authority plus scenario metadata.
- Guest end accepts exact `{}` and idempotently invalidates the server session
  plus every ticket bound to it before clearing the Guest cookie.
- Guest preview accepts exactly `{scenario_id}`; its PDF scenario and Token mode
  are immutable server-side. Guest execute accepts exactly `{ticket}`.
- Invite preview accepts exactly `{text, mode, provider}` under the current
  `20,000`-character and provider allowlists. Invite execute accepts exactly
  `{text, ticket}` so core can verify the source hash and deterministically
  reconstruct the exact approved protected bytes without persisting source or
  mapping. Provider, model, prompt revision, and mode must match the ticket;
  client-supplied overrides are rejected.
- Invite document preview is the exact raw `application/pdf` streaming contract
  defined below; document execute accepts exactly `{protected_text, ticket}`.
- For JSON operations, unknown fields, missing fields, invalid enums, query
  strings, form bodies, oversized JSON, and non-JSON content types fail with
  fixed value-free errors. Invite document preview is the sole non-JSON exception
  and must satisfy its exact raw-PDF media/body contract.
  Scenario IDs are server-allowlisted ASCII identifiers of at most 64 characters;
  tickets are base64url ASCII between 64 and 4,096 characters; modes are exactly
  `token` or `surrogate`; custom text remains 1 to 20,000 Unicode code points.

Every new exact route accepts `POST` only; all other methods, including `GET`,
`PUT`, `DELETE`, `PATCH`, and `OPTIONS`, return fixed JSON `405
method_not_allowed`. Unknown paths and route near-matches return fixed JSON `404
route_not_found`. Canonical and `/v1` aliases have identical statuses and bodies.
Guest auth routes require the existing same-origin/Fetch-Metadata browser check;
business routes still require the internal proxy key and contract header.

The success wire contract is locked before implementation:

| Operation | Exact request | Success | Exact response DTO |
| --- | --- | --- | --- |
| Guest start | JSON object `{}` only; an empty body is invalid | `201` plus `Set-Cookie: __Host-aift_guest=…; Max-Age=600; Secure; HttpOnly; SameSite=Strict; Path=/` with no `Domain` | `scope: "synthetic_guest"`, `expires_at_unix`, `execution_budget: 1`, `scenario_registry_revision`, `default_scenario_id`, and allowlisted `scenarios[{scenario_id,title,purpose,mode:"token"}]`; authority bytes are cookie-only |
| Guest end | JSON object `{}` only | `204` plus `Set-Cookie: __Host-aift_guest=; Max-Age=0; Secure; HttpOnly; SameSite=Strict; Path=/` with no `Domain` | Empty body; repeated same-origin calls remain `204` |
| Guest preview | `{scenario_id}` | `200` | The strict document-preview DTO below, generated by parsing the hash-pinned server-owned synthetic PDF with fixed Token mode |
| Invite preview | `{text, mode, provider}` where provider is the existing allowlisted `tokenmind` identifier | `200` | `source_kind:"custom_invite"`, `scenario:null`, `source_text:null`, `protected_text`, `mode`, `provider{id,model,prompt_revision}`, `detected_entity_count`, `entity_type_counts`, `highlights`, `section26_categories`, `guard_findings`, `outbound_gate{status,residual_count,human_review_required:true}`, `can_execute`, `protected_sha256`, and nullable `ticket`, `ticket_expires_at_unix`, `execute_before_unix`; raw custom text is not echoed back |
| Guest execute | `{ticket}` | `200` | The strict document-execute DTO below with mandatory synthetic scenario/provenance fields and no restored PII |
| Invite execute | `{text, ticket}` | `200` | The text-execute DTO below with `source_kind:"custom_invite"`, `scenario:null`, and no synthetic provenance label |
| Invite document preview | Raw PDF contract below | `200` | Strict document-preview DTO below |
| Invite document execute | `{protected_text, ticket}` | `200` | Strict document-execute DTO below |

The text-execute DTO contains exactly `request_id`, `hosted_version`, `source_kind`,
nullable `scenario`, nullable `synthetic_provenance`, `protected_text`,
`ai_response_masked`, `restored_text`, `mode`, `detected_entity_count`,
`entity_type_counts`, `section26_categories`, `guard_findings`, `warnings`,
`safety`, `restoration`, `provider{id,model,attempt_count}`, and `receipt`. The
source-bytes-free `receipt` contains exactly `receipt_version:1`, `request_id`,
`hosted_version`, `source_kind`, nullable scenario ID/registry revision, mode,
provider/model/prompt revision, detector/model hashes, protected SHA-256,
`digest_match:true`, outbound-gate status, provider attempt count, measured
duration milliseconds, restoration status, and nullable fixed synthetic
provenance. It contains no raw source, mapping, original/token pairs, provider
response body, access authority, or ticket.

The document-preview DTO contains exactly `source_kind`, nullable
`scenario{scenario_id,title,registry_revision}`, `hosted_version`,
`mode:"token"`, `parser_revision`, `extraction_revision`, `page_count`,
`character_count`, `segment_count`, `omitted_visual_page_numbers`, `protected_text`,
`detected_entity_count`, `entity_type_counts`, `outbound_gate{status,
residual_count,human_review_required:true}`, `warnings`, `source_receipt_id`,
`protected_sha256`, `can_execute`, nullable `ticket`, `ticket_expires_at_unix`, and
`execute_before_unix`. `source_receipt_id` is fresh random 128-bit base64url text,
not a raw/stable source digest. The DTO never returns extracted source text, the
PDF, raw source SHA-256, mapping, original/token pairs, or access authority.

The document-execute DTO contains exactly `request_id`, `hosted_version`,
`source_kind`, nullable `scenario`, mandatory `artifact_provenance`,
`protected_text`, `source_receipt_id`, `protected_document_ast`,
`protected_markdown`, `protected_plain_text`, `omitted_visual_page_numbers`, `warnings`,
`provider{id,model,attempt_count}`, and `receipt`. The source-bytes-free receipt contains
the request-scoped source receipt ID, parser/extraction/token/prompt revisions,
protected digest match, outbound-gate result, exact segment coverage, expected-
token integrity result, structured-output validation result, measured duration,
omitted-visual pages, and the same artifact warnings/provenance. “Source-free”
means source-bytes-free, not evidence-free; no raw source digest is exposed. It
contains no source PDF, extracted original text, mapping, original/token pairs,
ticket, authority, or provider response body.

Preview returns `ticket:null` and `can_execute:false` for `blocked` or `uncertain`;
only `no_residual_signal_detected` can carry a ticket. Every response is strict:
unlisted fields are a contract failure, count maps and highlights use the
existing validated DTO rules, timestamps are integer Unix seconds, digests are
lowercase 64-character SHA-256 hex, and request IDs use canonical UUID text.

The new fixed error rows extend HTTP contract 2 without changing existing rows:

| Status | Code | Category | Retryable | Applies when |
| --- | --- | --- | --- | --- |
| `401` | `authentication_required` | `authentication` | `false` | Missing/expired Guest or invite authority; obtain a new Guest or invite session |
| `403` | `control_forbidden` | `authentication` | `false` | Valid authority used outside its Guest/invite scope or cross-site browser context |
| `403` | `approval_invalid` | `session` | `false` | Malformed/tampered ticket or any hidden binding/digest/revision mismatch; the response never identifies which binding failed |
| `409` | `approval_consumed` | `session` | `false` | JTI was already atomically consumed; a new preview is required |
| `409` | `guest_execution_consumed` | `session` | `false` | A different approval already consumed this Guest session's single execution budget; start a new Guest session subject to limits |
| `409` | `approval_expiring` | `session` | `false` | Fewer than `210` seconds remain before execute admission; the same ticket cannot recover and a new preview is required |
| `409` | `session_expiring` | `session` | `false` | An invite session has fewer than 930 seconds remaining before document-preview admission; authenticate again before uploading so the full review window can be minted |
| `410` | `approval_expired` | `session` | `false` | Ticket TTL elapsed; a new preview is required |
| `422` | `document_unsupported` | `document` | `false` | Password/encryption, active content, attachments/forms, malformed structure, unsafe traversal, page/dimension limits, or another fixed unsupported-document condition; no parser detail is reflected |
| `422` | `pdf_text_layer_required` | `document` | `false` | A page fails the exact selectable-character, line-count, glyph-size, line-area, or hull-area text-layer thresholds; OCR is not attempted |
| `422` | `pdf_visual_content_unsupported` | `document` | `false` | A page exceeds the exact per-image or combined raster-area ceiling; OCR/visual interpretation is not attempted |
| `422` | `document_too_complex` | `document` | `false` | Extracted text exceeds 8,000 code points, parser segmentation exceeds 80 segments, or the provider-executable protected result exceeds 8,000 code points, 32 segments, or 9,120 encoded request bytes |
| `422` | `provider_payload_too_large` | `provider` | `false` | Custom source is within the public 20,000-code-point input limit, but deterministic protection expands the exact provider-bound text beyond 96 KiB; Preview returns no approval ticket and the caller must shorten the input before trying again |
| `429` | `document_busy` | `service` | `true` | The bounded parser lane is occupied or its document rate/capacity gate is closed; no body is parsed |
| `503` | `approval_registry_full` | `service` | `true` | The applicable registry contains only unexpired rows at capacity; no row is evicted and no provider call occurs |
| `503` | `document_parser_unavailable` | `dependency` | `true` | Parser absence, crash, protocol failure, or ten-second timeout; no provider call occurs |

New operations also use the existing fixed `400 invalid_request`, `404
route_not_found`, `405 method_not_allowed`, `413 payload_too_large`, `422
request_schema_invalid`, `422 residual_pii`, `429 rate_limited`, `500
restore_failed`, `502 provider_unavailable`, `502 provider_rejected`, `502
provider_response_invalid`, `503 provider_configuration`, `503
service_unavailable`, and proxy-level `504 upstream_timeout` rows exactly as
applicable. Tests lock status, code, category, `count`, and `retryable` values in
`http_v2.py`, Nginx fixed-error translation, both aliases, and `/developers`;
request-derived values are never reflected in an error.

### Content-stateless approval capability

The approval mechanism is content-stateless, not globally stateless: a bounded
memory cache retains only consumed capability hashes and expiry. It is not a
bare digest and does not rely on a fresh random roundtrip reproducing prior
bytes. Preview generates a random salt, performs the real sanitizer, and returns
an opaque base64url ticket encrypted and authenticated with AES-256-GCM from the
already pinned `cryptography 50.0.0` Hosted security overlay. A 32-byte key is
derived by HMAC-SHA-256 from `AIFT_COOKIE_SIGNING_KEY` and the dedicated context
`aiguard-hosted3-approval-v1`; every ticket uses a fresh 96-bit GCM nonce and the
same context as associated data. The authenticated plaintext is a strict tagged
union. Its common envelope contains only ticket schema/kind, random `jti`, process
boot nonce, issued/expiry times, scope, session nonce, mode, fixed provider/model/
prompt revision, HTTP contract version, detector/model hashes, protected digest,
and the random salt. For Token mode it also contains a fresh 32-byte
`protection_generation_seed` and `protection_generation_revision: pg-v1`.

- `custom_text_v1` adds only the custom source SHA-256.
- `guest_document_v1` adds only scenario ID, scenario-registry hash, pinned source-
  PDF hash, parser/extraction/segmentation revisions, page/character/segment/
  visual metadata, source receipt ID, and segment-manifest SHA-256.
- `invite_document_v1` adds only the raw source-PDF SHA-256, parser/extraction/
  segmentation revisions, page/character/segment/visual metadata, source receipt
  ID, and segment-manifest SHA-256.

No branch contains raw text, PDF bytes, original/token pairs, or a mapping.
Preview clears its function-local mapping before returning. Signing-key rotation
intentionally invalidates every outstanding approval and Guest authority.

`pg-v1` is a new internal sanitizer option used only by preview/execute. It
derives the 25-character token namespace and each 20-character token nonce by
domain-separated HMAC-SHA-256 expansion from the encrypted generation seed,
data type, transient original-value bytes, per-type ordinal, and collision-
attempt index. It deliberately does not use detector `entity_id`, because the
current detectors issue random UUIDs on each run. Repeated identical originals
of the same type reuse the same derived token just as the current vault does.
Alphabet encoding uses deterministic rejection sampling rather than modulo bias.
The generation seed exists only inside the ticket's authenticated ciphertext; it
is never exposed as a plaintext response field or stored in a registry or log.
Original values and intermediate keyed digests never enter the ticket, response,
registry, or log. The same source, detector revision, salt, generation seed, and
algorithm revision must therefore produce byte-identical protected text and
mapping in preview and execute even when detector UUIDs differ. Legacy
`/roundtrip` does not pass this seed and retains its current cryptographically
random namespace/nonce behavior byte-for-contract unchanged.

Execute authenticates the caller and tagged ticket and rejects expiry/boot/
session/scope/kind/revision mismatch. Custom text verifies the supplied source
hash and recreates protection from the supplied source. Guest document execution
reloads and rehashes the exact server-owned PDF, reruns the pinned parser and
protection revisions, and compares every bound metadata/digest field. Invite
document execution never requests the PDF again: it verifies the supplied
protected text, deterministic segment manifest, and digests against the encrypted
preview facts. Every branch constant-time compares the protected digest, rescans
the exact protected bytes immediately before **every** provider attempt, and
sends only those bytes. For custom text, the reconstructed mapping exists
function-locally through restoration and is then cleared. PDF/Guest execution
validates the protected document without restoration and does not expose or
persist a mapping. A
bounded value-free replay cache records consumed `jti` hashes before provider
execution; a consumed approval cannot be reused, including after provider
failure. The process boot nonce invalidates unconsumed tickets after restart.
Ticket TTL is five minutes for invite custom-text preview, ten minutes for Guest,
and fifteen minutes for invite document preview. Document-preview admission
requires at least 930 seconds left in the 30-minute invite session; the ticket is
minted only after parsing/protection and expires at the earlier of fifteen minutes
or session expiry. Core
rejects execute with fixed `approval_expiring` before capability consumption
unless at least `210` seconds remain, covering the current `200`-second maximum
provider envelope plus response margin. The official UI disables Send at the
same threshold and offers a new provider-free preview.

### Guest isolation and abuse budget

- Guest authority uses a separate `__Host-aift_guest` Secure/HttpOnly/
  SameSite=Strict cookie and signing context. It is not inserted into the
  invite session registry and can never authorize current or new arbitrary-text
  routes. Guest preview accepts only strict `{scenario_id}` and fixed Token mode;
  provider,
  model, prompt, source text, and scenario registry revision are immutable
  server-side. Guest execute accepts only the opaque approval ticket.
- The organizer edge collapses browser addresses, so the release makes no false
  per-visitor IP-fairness claim. Nginx enforces fixed global Guest limits: start
  `30r/m`, preview `20r/m`, and execute `2r/m`. Cookie text extracted by Nginx is
  only a defense-in-depth throttle key and is never called verified authority.
  After core verifies the Guest cookie, it enforces preview `2r/m` and one
  consumed execution per verified Guest session. Invalid or rotating cookie
  syntax cannot create authority or bypass the global lanes.
- The existing authenticated provider lane remains `6r/m`, two concurrent, and
  `2r/m` per authenticated nonce. Core keeps a shared provider semaphore of two
  and a Guest sub-limit of one, so Guest can hold at most one local provider
  admission slot. This proves local concurrency reservation only. Guest and
  invite requests still share core CPU and the organizer's external Pathumma
  quota; no separate upstream quota or non-starvation SLA is claimed. Guest
  global execute/attempt counters, the receipt's actual attempt count, and
  `AIFT_GUEST_MODE` bound and expose that load without inventing upstream
  isolation.
- Guest cookie TTL is ten minutes. Active Guest sessions and consumed Guest
  approvals are separate registries, each capped at 512; consumed invite
  approvals use a separate 256-entry registry. Under one process-wide lock,
  Guest execute prunes expired rows, atomically checks both the JTI and the
  verified Guest session's remaining execution budget, then consumes both before
  any provider call. Invite execute atomically checks and consumes its JTI.
  Unexpired rows are never evicted. Capacity exhaustion fails
  closed with fixed `approval_registry_full` before minting/consumption or
  provider contact. Concurrent reuse of the same ticket produces one winner and
  fixed `approval_consumed` for every loser; distinct tickets from the same
  Guest produce one winner and fixed `guest_execution_consumed` for every loser.
- The replay design is approved only for the deployed single core process.
  Compose, build, and public acceptance pin and assert `UVICORN_WORKERS=1`; Guest
  startup fails closed if that invariant is not met. Horizontal or multi-worker
  operation requires a separately reviewed shared atomic replay store. No raw,
  protected text, mapping, ticket bytes, or result content enters any registry.
  Guest end invalidates the verified session and its bound tickets, and clears
  the HttpOnly cookie with the exact `204` contract above. Guest→invite switching
  must complete Guest end before login; invite→Guest switching must complete
  invite logout before Guest start. A network failure leaves the user at the
  current gate with truthful recovery instead of silently holding both
  authorities.
  When the Guest budget or switch closes, the UI fails honestly to the invite/
  Desktop choices; it never falls back to arbitrary public processing or a
  second provider.

### Interaction and accessibility state contract

Both Guest and invite flows use `idle → previewing → preview-ready → provider-
pending → complete | error | expired`. Approval binds source/scenario revision,
mode, provider/model/prompt, detector revision, HTTP contract, session, ticket,
and protected digest. Source edits, scenario/mode/provider changes, preview
retry, reset, auth/scope change, expiry, back/reload, or Guest↔invite switching
invalidates the approval and disables Send. Switching authority clears current
results and tickets; warn only when meaningful work would be discarded.

The implemented Stage 6 caller focuses the completed preview heading after both
custom-text Preview and PDF `Upload & extract`; this supersedes the earlier
announcement-only custom-text rule after real 390×844 keyboard review found lost
focus. The approval control immediately
follows the exact payload preview. Provider
completion focuses the restored-result heading for custom text or the Protected
Markdown heading for PDF/Guest, then announces one restrained summary.
Invalidation is announced once; countdowns do not chatter. Expiry or
auth failure returns focus to the correct Guest/invite gate. Text and icons, not
color alone, distinguish preview, blocked, uncertain, pending, complete, and
expired states. During `provider-pending`, navigation retains the existing
truthful warning that a sent provider request may still run and stale completion
can never repaint cleared state. Refresh clears DOM-held text/result/ticket;
duplicate Guest tabs share the one-execution authority, so the first valid
execution consumes it. Reuse of that exact ticket receives `approval_consumed`;
a distinct valid ticket from the same Guest receives
`guest_execution_consumed`.
Once execute is admitted, the UI does not erase its pending state merely because
the original Guest countdown reaches zero. It waits for the bounded request to
settle, may render that request's verified result and receipt, then marks Guest
authority expired and permits no further privileged call. This response window
does not extend the cookie, ticket, arbitrary-text authority, or execution
budget. Navigation/reset still clear the DOM and retain the unresolved-request
warning.

Image/audio and legacy black-box PDF-redaction/OCR breadth are not part of this
competitive promise merely because other teams expose them. The old
`/redact-pdf` aliases and OCR remain fixed `404`. Text-layer PDF to protected
structured text is the selected Hosted 3.0 story, but it is still plan-only and
cannot ship until its separate parser, correctness, provenance, timeout,
resource, privacy, implementation, browser, and independent-review gates pass.
Hosted 3.0 wins on controlled disclosure and verifiable proof before provider
use, not on an unsupported modality checklist.

### Implementation and acceptance sequence

1. Lock the Guest/document threat model, abuse budget, synthetic PDF registry,
   version/compatibility policy, and Preview-Before-Provider request/response
   schemas.
2. Build the secretless, network-denied `pdf-parser` image and Unix-socket
   protocol with qpdf/pikepdf structural rejection, bounded pdfplumber/PDFium
   extraction, strict output framing, cleanup on every exit path, deterministic
   resource caps, and adversarial parser fixtures.
3. Implement core/API behavior with streaming PDF ingress, one-job parser
   admission, value-free logs, fail-closed digest/ticket binding, strict document
   AST validation/rendering, expiry, deterministic errors, and legacy-route
   tests.
4. Author the Synthetic Guest PDF demo, invite upload flow, concise Protection
   Decision, and protected artifact in the real `/app` architecture, plus the
   static developer/evidence surface through exact Docker, Compose, Nginx, CSP,
   link, sitemap/robots, and caller-facing routes.
5. Profile the parser under the production CPU/memory envelope, run unit/
   contract/security tests, complete built-image acceptance, and real
   Chrome verification at every production viewport, keyboard, 200% equivalent
   reflow, Thai marks, motion/reduced motion, failure states, overflow,
   performance, and layout stability.
6. Assign independent adversarial art-direction, frontend/product, security/
   privacy, and UX/accessibility review. Fix material blockers and repeat.
7. Bump and deploy Hosted `3.0.0` only from the reviewed exact revision through
   protected production `check → deploy → acceptance → logs → process/revision →
   restart/recovery`, then verify the public Guest and authenticated journeys.

The defining negative proofs are release blockers, not optional QA:

- zero provider calls from Guest start or either preview operation; execute
  without matching authority and a valid one-use ticket fails before provider
  contact, while the official UI emits execute only from its explicitly labelled
  approval action. Tests do not claim that the server can prove a human click
  against an alternate authorized client or JavaScript bypass;
- zero provider calls during PDF upload, parser admission, extraction,
  protection, document preview, or any document failure; the raw PDF reaches only
  the organizer proxy, core's bounded stream, and the secretless parser over its
  Unix socket, and never Pathumma;
- the core process never opens arbitrary PDF bytes through a PDF library, never
  joins the full upload in memory, and never forwards a filename/path. Streaming
  limit tests, disconnect/cancel/timeout/crash/shutdown tests, and tmpfs inspection
  prove parser job files are unlinked and references released on every exit path
  without making a secure-erasure claim;
- the built parser container has no application secret or network route, runs as
  the pinned non-root/capability-free/read-only/seccomp profile, and fails closed
  if those production controls or the framed-socket protocol are absent;
- qpdf/pikepdf/PDFium adversarial fixtures cover compressed object streams,
  nested forms/XObjects, inline images, tiny text overlays, cycles, bombs,
  malformed cross-references, active content, attachments/forms, and parser
  crashes. Unsupported or uncertain structure returns the fixed document error
  without provider contact;
- Guest synthetic parsing and invite document preview share the one-job parser
  semaphore. Rate/concurrency/saturation tests prove fixed `document_busy` and
  `document_parser_unavailable` behavior without starving the authenticated text
  lane or bypassing the provider semaphore;
- document execute accepts only the exact protected text bound to its one-use
  ticket. Provider output must reference every immutable source segment exactly
  once using only the fixed section-role enum, pass exact expected Token set/
  multiplicity checks and the residual scan, and stay under the streaming `32
  KiB` response cap. Missing/duplicate/foreign segments, free provider prose,
  truncated/oversized JSON, HTML, URLs, images, unknown roles/blocks, and foreign
  or missing tokens fail before the deterministic escaped Markdown/plain-text
  renderer and are never injected as browser HTML;
- every Guest/document copy and `.md`, `.txt`, or JSON receipt embeds the required
  protected-not-anonymous, source-unchanged, no-restoration, text-layer-only,
  raster-page/OCR omission, human-review, revision/hash, and Hosted-version
  provenance; inclusion tests prove that no product copy/download action emits a
  header-free artifact, without claiming that an editable exported file cannot
  later be modified by its recipient;
- arbitrary Guest text, provider/model overrides, query strings, unknown fields,
  invalid scenarios, and Guest attempts against invite-only routes are rejected
  server-side without reflecting input;
- changed source, mode, provider, prompt, detector/model revision, contract,
  session, process boot, expiry, protected digest, or scenario-registry hash makes
  the ticket unusable before provider contact;
- AEAD tagged-union tests reject cross-kind execution, unknown/duplicate fields,
  branch-field smuggling, and custom/Guest/invite document confusion; raw source
  PDF hashes remain encrypted-ticket-only and never appear in DTOs, receipts,
  logs, registries, or browser-readable persistence;
- the approved protected digest equals the bytes scanned before every provider
  attempt and equals the bytes actually sent; a mismatch fails closed;
- both Token and Surrogate preview/execute reproduce byte-identical protected
  text and mapping from the encrypted ticket inputs, while repeated legacy
  `/roundtrip` calls retain their current random token namespace/nonce behavior;
- each approval is one-use, only one Guest provider lane can be unresolved, and
  the actual bounded same-provider attempt count is reported truthfully;
- concurrent reuse of one ticket and concurrent/sequential execution of two
  distinct valid tickets from one Guest session each yield exactly one provider-
  bound winner and the locked consumed error for every loser;
  saturation tests fill Guest and invite replay registries with unexpired rows,
  prove no live row is evicted, and receive `approval_registry_full` before any
  provider call;
- Guest rate, semaphore, registry-capacity, and kill-switch tests prove public
  load cannot take more than one local provider-admission slot or gain the
  authority of the authenticated lane; no test claims isolation from shared CPU
  or external Pathumma quota. The test models the organizer's collapsed client
  address and proves rotating invalid cookie syntax cannot bypass core's
  verified-session quota;
- expiry, Guest↔invite switching, logout, reset, navigation, and reload clear
  sensitive DOM state, tickets, and stale completion authority while retaining
  the truthful warning that an already sent provider request may still run;
- Guest end is idempotent, invalidates every bound approval, emits the exact
  `Max-Age=0` cookie, and a failed authority switch never leaves both Guest and
  invite lanes active;
- execute inside the final `210` seconds is rejected before ticket consumption;
  an already admitted request may render its verified result after cookie expiry
  but cannot extend Guest authority or make another privileged call;
- invite document tickets expose the separate fifteen-minute review window and
  final 210-second admission cutoff without chattering; boundary tests prove the
  official UI allows meaningful keyboard/screen-reader review, disables stale
  approval, and requires a new provider-free upload/preview after expiry;
- deterministic focus, associated errors, restrained live-region announcements,
  non-color status, keyboard order, reduced motion, no-JavaScript failure,
  `720×365` reflow, `390×844`, and `360×800` pass for every defining state;
- native file-input keyboard use, select-without-upload, explicit upload,
  replacement/reset invalidation, parser progress/failure focus, one-pane mobile
  reading order, and no-JavaScript fail-closed recovery pass in real Chrome;
- all existing canonical and `/v1` routes, especially `/roundtrip`, remain
  byte-for-contract compatible, and every new near-match or forbidden method
  returns its locked fixed status/body at both Nginx and core. `/health` alone
  changes its version value intentionally while retaining its schema and
  liveness semantics.
- `/redact-pdf`, `/v1/redact-pdf`, scanned/image-only fixtures, and every OCR
  near-match remain fixed failures; built images contain no OCR model/runtime,
  while all four exact document routes, parser image, socket, MIME/body limits,
  CSP, and Docker/Compose wiring are caller-facing acceptance assertions.
- the exact 8,000-code-point and representative Thai-plus-Token 9,120-byte
  document boundaries, each at 32 segments, plus the 32-KiB streamed provider-
  response cap, absolute 200-second call deadline, and document-only
  `max_tokens:4096` setting pass measured boundary fixtures against the deployed
  Pathumma contract without truncation.

</details>

### Hosted 3.0 approved access and queue contract

Status: owner-approved planning baseline on 2026-08-16. It supersedes the
collapsed block's product/authority decisions, including fixed-scenario-only
authority, single-execution budget, invite-only custom uploads, old route count,
and Guest-versus-invite workspace. It incorporates only the named technical
foundations in that block under the exact precedence rule above. It changes no
current source, version, route, secret, or deployment.

#### Product model: one app, two service classes

The public experience must not present three competing products or a separate
demo-only workspace. A visitor is not an authority tier: public pages remain
readable, and selecting `Use AI Guard` opens one `/app` entry shared with invite
holders.

1. **Standard access** (internal scope `public_guest`) is automatic, requires no
   invite, and exposes every ordinary user-facing workflow: Privacy Scan, Safe
   AI, PDPA Report, custom text, the accepted text-layer PDF path, synthetic
   scenarios, protected artifacts, and normal evidence. It receives lower rate
   and queue priority, but no artificial one-run lifetime cap.
2. **Priority Invite** uses a separately issued high-entropy code and exposes the
   same complete product plus judge/presentation evidence. Its difference is
   service class: higher admission rate and weighted queue priority. It is not an
   administrator role and never exposes
   secrets, raw logs, other sessions, mappings, or operator controls.

Public copy uses `Standard access` and `Priority Invite`, not “Guest demo” versus
“real app.” The signed-out first fold contains one compact start card: one
Thai-first job statement, the two-sentence raw-data boundary, a primary `Start
Standard access` action, and a secondary `Use Priority Invite` action. Starting
Standard creates a fixed 30-minute signed session. After entry, one compact task
chooser features `PDF → Protected Markdown` and gives `Protect text for AI` and
`Inspect & report` one short secondary action each. Synthetic data is an example
inside a task, not a separate lane. Advanced evidence stays inside result
disclosures, so full feature parity does not recreate the rejected long first
screen.

Both classes see the same privacy notice adjacent to raw input, the same inspect-
before-provider decision, and the same correctness/human-review gates. The header
shows at most one short active service-class chip. `Use Priority Invite` belongs
in the access panel, not permanent global chrome. Queue detail is stage-local; an
active queue may add one compact recovery link in the header, which disappears
when no queue exists. At `390×844` and `360×800`, the first fold contains only the
job statement, boundary, and two access actions; task and queue controls stack
below without horizontal tabs. An authority switch warns only when meaningful
work would be cleared and never retains a prior approval, queue capability,
source, result, or provider authority.

All product features have the same safety and correctness limits in both classes.
Priority never bypasses residual-PII blocking, payload caps, parser restrictions,
approval, one-unresolved-request ownership, provider validation, or provenance.
Owner operational access remains outside the public application; a judge invite
must never become an admin credential merely because the owner also uses one.

Hosted 3.0 scope is Text, accepted text-layer PDF to Protected Markdown, the
existing reports/evidence, and server-owned synthetic examples. Audio input,
ASR/TTS product surfaces, images, Vision, scanned/image-only PDF, OCR, image
redaction, and face/voice anonymization are explicitly out of this release even
though separate experiments or organizer models may exist. They require a later
Beta decision, fresh service acceptance, modality-specific raw-data boundaries,
and independent resource/privacy review; no disabled or teaser control is added
to the production UI now.

#### Honest identity and per-user limits

Anonymous traffic cannot be truthfully limited “per person.” The organizer edge
collapses client addresses, while cookies can be cleared or moved. Standard
limits are therefore described and enforced **per verified signed browser
session**, backed by global queue/rate/capacity ceilings. IP or a cookie string at
Nginx is defense in depth only and is never labelled identity or fairness proof.

Priority limits are per issued invite credential, not proof of one human: a code
can still be copied. The owner and each judge therefore receive a different
high-entropy credential so their quotas do not collapse together. A bounded
masked configuration contains only opaque subject IDs, role, enabled state, and
SHA-256 digests of at-least-128-bit random invite codes. Core verifies the
presented code in constant time and keeps raw code bytes only transiently during
verification. Raw codes and human names never enter the masked registry,
session, queue, response, or logs. Revocation disables the credential digest
and invalidates that subject's active sessions without creating an account
database. Public wording says `per issued invite`, never `per person`.

The Stage 1 masked registry wire is the optional secret value
`AIFT_PRIORITY_INVITES_JSON`: a JSON array of at most 32 exact objects
`{subject_id,role,enabled,code_sha256}`. `subject_id` is canonical
`sub_` plus 22 base64url characters derived from random 128-bit owner-managed
identity bytes, `role` is exactly `priority_invite`, `enabled` is Boolean, and
`code_sha256` is unique lowercase 64-character hex. Unknown fields, duplicate
subjects/digests, non-canonical values, and an oversized registry fail startup.
This masked registry contains neither the raw invite nor a human label. During
the migration only, the existing `AIFT_ACCESS_CODE` secret remains accepted as
one implicit opaque legacy subject so the deployed login contract is not broken;
the raw legacy value is confined to secret configuration and transient startup/
verification locals, not retained on the gateway object or in session records.
Stage 5 must provision individually generated registry entries before the final
Priority evidence is claimed. Updating/revoking the secret configuration
restarts the single-worker Core, whose process-local session registry makes all
previous cookies fail closed.

#### Standard authority and route scope

Standard uses the planned `__Host-aift_guest` Secure/HttpOnly/SameSite=Strict/
Path `/` cookie but replaces the earlier Guest wire contract completely.
`POST /api/auth/guest` and `/api/v1/auth/guest` accept exact `{}`. With no valid
Standard cookie they return `201`, set `Max-Age=1800`, and return exactly
`scope:"public_guest"`, `expires_at_unix`, `service_class:"standard"`, and the
exact sorted capability list `["analyze_report","detect","document_execute",
"document_preview","guard","protection_execute","protection_preview",
"synthetic_scenarios"]`; there is no `execution_budget`. With an
already-valid Standard cookie they return the same DTO as `200` without renewal
or reminting. `POST /api/auth/guest/end` plus its `/v1` alias accept exact `{}`,
invalidate the session and every approval/queue record bound to it, clear the
cookie, and remain idempotent `204`. There is no account, renewal token, silent
sliding expiry, or user database. Priority Invite retains the current invite-
login cookie and 30-minute maximum; the two authorities cannot coexist. Standard
start, the existing read-only auth-session response used by either authority,
and all Core-originated new preview success/error responses add the exact
no-store response header `X-AIGuard-Server-Time-Ms`, whose base-10 integer value
is Core UTC Unix milliseconds sampled immediately before ASGI response
serialization. Successful Standard start and authenticated auth-session also add
`X-AIGuard-Session-Expires-At-Ms` as the exact base-10 integer Core session-expiry
epoch in UTC milliseconds. Successful Standard start and authenticated auth-
session also add exact `X-AIGuard-Service-Class: standard|priority`, allowing a
reload to recover the visible class without exposing the HttpOnly cookie,
subject, or credential. These are intentional additive headers only: the
existing auth-session status and `{authenticated:true,expires_in}` body remain
byte-for-contract compatible. None is supplied by Nginx or the client; an
absent/invalid server-time or session-expiry header makes provider-bound controls
fail closed, while an absent/invalid service-class header prevents class-specific
UI or queue action until the same fresh session check succeeds.

Authority transitions are explicit. Successful Priority login while a Standard
cookie is valid invalidates and clears Standard before minting Priority. Starting
Standard while Priority is valid returns fixed `409 authority_conflict` and does
not reduce the caller's authority. If a request presents two independently valid
cookies, Core returns the same fixed conflict, clears both, and forwards no body.
Invalid/stale cookies carry no authority and are cleared when encountered.
Verified business calls receive one immutable internal authority context with
only `scope`, `service_class`, opaque session nonce, nullable opaque subject ID,
and exact expiry; raw cookies, invite values, and invite digests never enter the
downstream scope.

The authoritative authorization matrix is:

- `detect`, `guard`, `analyze-report`, Guest scenario preview, protection preview/
  execute, and document preview/execute accept either verified `public_guest` or
  `priority_invite` authority. They return `source_kind:"custom_standard"` or
  `"custom_invite"` as applicable and otherwise keep the same privacy, parser,
  approval, output, and DTO gates.
- Standard may submit arbitrary text and accepted text-layer PDF under the same
  adjacent raw-edge/core disclosure as Priority. It cannot select a provider,
  model, prompt, safety policy, or parser option.
- Legacy `/roundtrip` remains Priority-invite-only and byte-for-contract
  compatible. The new web app no longer calls it; it uses preview, queue, and
  execute. Standard attempts against `/roundtrip`, auth-control, admin/internal,
  or unknown routes fail before processing.
- Route, middleware, DTO, ticket-kind, Nginx, caller, and negative tests enumerate
  both authorities explicitly. The earlier `Guest arbitrary input must fail`
  assertion is superseded; cross-scope, provider override, and no-authority
  failures remain mandatory.
- The authoritative approval common envelope contains exactly ticket schema and
  kind, random JTI, process boot nonce, issued/expiry times, scope, session nonce,
  mode, fixed provider/model/prompt revision, HTTP contract version, detector/
  model hashes, protected digest, random salt, and Token-mode generation seed/
  revision. `custom_text_v1` adds only custom source SHA-256,
  `source_kind:"custom_standard"|"custom_invite"`, and matching authority.
  `standard_document_v1` and `invite_document_v1` each add only raw source-PDF
  SHA-256, parser/extraction/segmentation revisions, page/character/segment/
  visual metadata, source receipt ID, segment-manifest SHA-256, matching source
  kind, and Standard/Priority authority binding. `synthetic_document_v1` adds
  only scenario ID, scenario-registry hash, pinned source-PDF hash, the same
  parser/metadata/receipt/manifest facts, and the calling Standard/Priority
  authority. No branch contains source bytes, extracted original text, mapping,
  or original/token pairs. Cross-kind or cross-class execution fails before
  queue or provider contact.

#### Approval timing and exact preview/execute wire contract

Provider-bound preview admission guarantees a meaningful, non-timed review
window before the separate `900`-second queue-admission requirement. Custom-text
preview requires at least `1,030` seconds remaining in the verified session:
`900` seconds for queue admission, `120` seconds of guaranteed review, and a
`10`-second initial processing margin. Uploaded or synthetic document preview
requires at least `1,230` seconds remaining: `900` seconds for queue admission,
`300` seconds of guaranteed review, and a `30`-second initial upload/parser
margin. These margins are admission budgets, not assumptions that work always
finishes within that time: the post-processing and client-receipt checks below
enforce the actual review minimum. The
approval TTL is determined only by the tagged branch and is identical across
service classes; Priority changes service rate and queue weight, not how long
approved data remains executable:

| Ticket kind | Standard TTL | Priority TTL | Source |
| --- | --- | --- | --- |
| `custom_text_v1` | `300 s` | `300 s` | Caller-supplied text |
| `standard_document_v1` | `900 s` | Not valid | Standard uploaded text-layer PDF |
| `invite_document_v1` | Not valid | `900 s` | Priority uploaded text-layer PDF |
| `synthetic_document_v1` | `600 s` | `600 s` | Hash-pinned server-owned PDF scenario |

Custom source text remains `1…20,000` Unicode code points. After deterministic
protection and before any ticket mint, Core also requires the exact provider-
bound protected UTF-8 payload to be at most `96 KiB`; token expansion may make
this second bound decisive even when source length passes. Failure is fixed
`422 provider_payload_too_large`, category `provider`, `count:0`,
`retryable:false`; it returns no ticket or timing fields, makes no queue/provider
call, preserves the caller's editable source only in the current page memory,
and focuses a concise recovery that asks the caller to shorten the input. The
execute worker accepts that same 96-KiB boundary exactly and has no stricter
hidden code-point limit on protected text. Tests cover a 20,000 four-byte-code-
point source, token-expanded protected text above 20,000 code points at the
exact 96-KiB boundary, and one-byte-over preview rejection before approval.

`ticket_expires_at_unix` is exactly the earlier of issue time plus the table TTL
or session expiry. `queue_join_before_unix` is exactly the earlier of ticket
expiry or session expiry minus `900` seconds. A preview carries an approval only
when that join deadline is in the future and the outbound gate is
`no_residual_signal_detected`; otherwise it returns `can_execute:false` and null
approval/timing fields. The UI shows the absolute join deadline and requires a
cause-specific recovery after it passes. Fixed `410 approval_expired` applies
only when ticket expiry is **strictly earlier** than session expiry minus `900`
seconds; it focuses Preview and requires a new provider-free preview. Session-
earlier **or equal** deadlines use fixed `409 session_review_window`, focus the
authority restart/reauthentication action, and allow a preview only after that
recovery. Equality is session-derived because only `900` seconds then remain and
the branch's minimum review window can no longer be reminted. The client
determines the visible branch from `ticket_expires_at_unix`,
`queue_join_before_unix`, and the authenticated session expiry, while Core
remains authoritative. Queue join consumes the preview approval and replaces it
with the separately bounded `provider_queue_v1` capability below; it never
silently renews the preview ticket.

The official client takes a fresh same-origin read-only auth-session sample
before it sends a preview request. It records monotonic `performance.now()` at
request dispatch and receipt, reads `X-AIGuard-Server-Time-Ms`, and treats
`server_sample + full measured request duration` as the conservative server time
at receipt. It compares that estimate directly with the authenticated
`X-AIGuard-Session-Expires-At-Ms`; it never reconstructs expiry from the rounded
legacy `expires_in` body. Later checks add only monotonic elapsed time since
receipt; user wall clock and `Date.now()` never decide eligibility. For uploaded documents this
happens after local file selection but before any PDF network request, so an
insufficient conservative session window never causes the official UI to upload
the selected file. Core independently authenticates
and checks the branch threshold before consuming the request stream, acquiring
parser work, or creating a spool reference; a direct request cannot bypass the
initial deadline check. After protection/parsing completes but before minting or
returning a ticket, Core checks again: custom text must still have at least
`1,020` seconds remaining and every document branch at least `1,200` seconds.
Failure returns `409 session_review_window` without minting approval or contacting
the provider. A slow upload may therefore consume the already-disclosed raw PDF
path and still fail this post-processing check, but it never creates a shortened
approval. Organizer-edge or proxy buffering remains outside AI Guard's observable
control and retains the existing explicit disclosure.

On preview receipt, the official client creates a new conservative anchor from
that response's server-time header and the full monotonic preview-request
duration. `queue_join_before_unix` minus this conservative server estimate must
be at least `120` seconds for custom text or `300` seconds for any document. If
network delay has eroded that minimum, it discards the returned approval in page
memory, makes no queue request, presents the same `session_review_window`
authority recovery, and never calls the provider. Countdown and eligibility then
use only the anchored server sample plus monotonic elapsed time. Visibility
resume, BFCache restore, system wake, or a lost timing anchor requires a fresh
read-only auth-session sample before showing an active countdown or allowing
join. The UI may format the absolute server deadline in a labelled timezone, but
the device wall clock never drives the countdown. Thus the guaranteed minimum
applies to the official browser journey; another authorized client remains
responsible for honoring the published absolute deadline.

Missing, malformed, or non-integer timing headers enter the fixed client state
`timing_unavailable`; this is not misreported as an HTTP/provider failure. The
visible summary says `ตรวจสอบเวลาของเซสชันไม่ได้ AI Guard จึงยังไม่ส่งข้อความที่
ป้องกันแล้วไปยัง Pathumma โปรดลองตรวจสอบเซสชันอีกครั้ง`, is announced once, and
receives focus on its `Retry session check` action. If this happens after an
uploaded-document preview response, the adjacent summary also states that the
source PDF already traversed the organizer proxy and AI Guard for extraction but
was not sent to Pathumma. Entry clears every preview approval and timing anchor
but may retain unsent text or a locally selected, not-yet-uploaded file; upload,
queue join, and provider controls remain disabled. Retry performs one fresh
read-only auth-session sample. Success announces restoration once and returns
focus to the task's Preview or `Upload & extract` action; repeated failure retains
focus on Retry without announcement chatter. Nginx `413` and `429` keep their
specific actionable size/rate summaries rather than becoming a timing error, but
any later request retry obtains a fresh timing sample first.

Insufficient session time returns the fixed HTTP-contract-2 envelope
`{"error":{"code":"session_review_window","category":"session","count":0,
"retryable":false,"status":409}}`. No request-derived value is reflected. The UI
announces it once and focuses the relevant `Restart Standard access` or
`Use Priority Invite again` action; it tells the user to renew authority before
re-uploading or re-previewing. By contrast, ticket-only expiry uses fixed `410
approval_expired`, focuses the task's Preview action, and requires a new
provider-free preview (including a fresh explicit PDF upload when the source was
an uploaded document). Neither recovery silently retains an approval, queue
capability, or provider authority.

All JSON request objects reject unknown or missing fields. `scenario_id` is
allowlisted ASCII of at most 64 characters, `mode` is exactly `token` or
`surrogate`, caller text is 1 to 20,000 Unicode code points, and capabilities are
base64url ASCII of 64 to 4,096 characters. The fixed provider, model, prompt,
detector, and parser revisions are server-owned and cannot be supplied or
overridden by either class. The exact preview wire contracts are:

| Operation | Exact request | `200` success DTO |
| --- | --- | --- |
| Guest scenario preview | `{scenario_id}` | The document-preview DTO below with `source_kind:"synthetic_document"`, non-null scenario, and fixed Token mode |
| Protection preview | `{text, mode}` | The text-preview DTO below with `source_kind:"custom_standard"` or `"custom_invite"` from verified authority |
| Document preview | Raw `application/pdf` body under the incorporated parser/body contract; no query or form fields | The document-preview DTO below with `source_kind:"document_standard"` or `"document_invite"` from verified authority and `scenario:null` |

Every success row above and every **Core-originated** fixed preview error carries
`Cache-Control:no-store` and the exact `X-AIGuard-Server-Time-Ms` header. The
header is response metadata, not a JSON DTO field, and canonical plus `/v1`
aliases emit identical body and header semantics. Early fixed edge responses,
including Nginx-generated `413 payload_too_large` and `429 rate_limited`, remain
headerless because Core was not reached; the client treats them as terminal for
that request, creates no timing anchor, and keeps upload/join/provider actions
closed. Nginx never fabricates Core time.

The text-preview DTO contains exactly `source_kind`, `scenario:null`,
`source_text:null`, `protected_text`, `mode`, `hosted_version`,
`provider{id,model,prompt_revision}`, `detected_entity_count`,
`entity_type_counts`, `highlights`, `section26_categories`, `guard_findings`,
`outbound_gate{status,residual_count,human_review_required:true}`, `can_execute`,
`protected_sha256`, nullable `ticket`, nullable `ticket_expires_at_unix`, and
nullable `queue_join_before_unix`. Raw caller text is never echoed.

The document-preview DTO contains exactly `source_kind`, nullable
`scenario{scenario_id,title,registry_revision}`, `hosted_version`, `mode:"token"`,
`parser_revision`, `extraction_revision`, `page_count`, `character_count`,
`segment_count`, `omitted_visual_page_numbers`, `protected_text`,
`detected_entity_count`, `entity_type_counts`,
`outbound_gate{status,residual_count,human_review_required:true}`, `warnings`,
`source_receipt_id`, `protected_sha256`, `can_execute`, nullable `ticket`, nullable
`ticket_expires_at_unix`, and nullable `queue_join_before_unix`.
`source_receipt_id` is fresh random 128-bit base64url text, not a raw or stable
source digest. The response never contains source PDF bytes, extracted original
text, a raw source hash, mapping, original/token pairs, or access authority.

Preview returns `ticket:null`, null timing fields, and `can_execute:false` for
`blocked` or `uncertain`; only `no_residual_signal_detected` may carry a ticket.
Timestamps are integer Unix seconds, digests are lowercase 64-character SHA-256
hex, request IDs are canonical UUID text, and unlisted response fields are a
contract failure.

After queue admission, the exact execute requests are Guest scenario
`{queue_capability,claim_token}`, protection
`{text,queue_capability,claim_token}`, and document
`{protected_text,queue_capability,claim_token}`. The first two bind respectively
to `synthetic_document_v1` and `custom_text_v1`; the document request binds to
the authority-matched uploaded-document branch. Missing source bytes, changed
source/protected bytes, wrong kind/class/session, stale claim, or an extra field
fails before provider contact.

Protection execute returns exactly `request_id`, `hosted_version`, `source_kind`,
`scenario:null`, `synthetic_provenance:null`, `protected_text`,
`ai_response_masked`, `restored_text`, `mode`, `detected_entity_count`,
`entity_type_counts`, `section26_categories`, `guard_findings`, `warnings`,
`safety`, `restoration`, `provider{id,model,attempt_count}`, and `receipt`. Its
source-bytes-free receipt contains exactly `receipt_version:1`, `request_id`,
`hosted_version`, `source_kind`, nullable scenario ID/registry revision, mode,
provider/model/prompt revision, detector/model hashes, protected SHA-256,
`digest_match:true`, outbound-gate status, provider attempt count, measured
duration milliseconds, restoration status, and nullable fixed synthetic
provenance. It contains no raw source, mapping, original/token pairs, provider
response body, access authority, queue capability, or claim token.

Guest scenario and uploaded-document execute return exactly `request_id`,
`hosted_version`, `source_kind`, nullable `scenario`, mandatory
`artifact_provenance`, `protected_text`, `source_receipt_id`,
`protected_document_ast`, `protected_markdown`, `protected_plain_text`,
`omitted_visual_page_numbers`, `warnings`, `provider{id,model,attempt_count}`, and
`receipt`. That source-bytes-free receipt contains the request-scoped source
receipt ID, parser/extraction/token/prompt revisions, protected digest match,
outbound-gate result, exact segment coverage, expected-token integrity,
structured-output validation, measured duration, omitted-visual pages, and the
same artifact warnings/provenance. It contains no source PDF, extracted original
text, raw source digest, mapping, original/token pairs, provider body, authority,
queue capability, or claim token.

The exact allowlist starts with the deployed 16 locations and adds these 12
canonical operations plus exact `/v1` aliases: `/auth/guest`, `/auth/guest/end`,
`/guest/preview`, `/guest/execute`, `/protection-preview`,
`/protection-execute`, `/document-preview`, `/document-execute`,
`/provider-queue/join`, `/provider-queue/status`, `/provider-queue/claim`, and
`/provider-queue/cancel`. The approved total is therefore 40 exact locations;
no prefix, implicit version, or near-match routing is permitted. Scenario routes
are server-owned examples available to either authority, not a separate Guest
product. Execute request bodies use the matching queue capability and claim token
as defined below.

#### Starting fair-use policy

The release begins with a measurable, adjustable server policy rather than a
total-use entitlement:

| Operation class | Standard session | Priority Invite | Global truth |
| --- | --- | --- | --- |
| Provider-free detect/guard/report preview | token bucket `6/min`, burst `2` | `30/min`, burst `5` | Existing global work/body/connection ceilings remain |
| Text-layer PDF parse/protect preview | `1/min`, burst `1`, one parser request unresolved | `4/min`, burst `1`, one unresolved | One shared parser job; busy requests queue/fail by the locked document policy |
| Provider queue join | base `1/min`, burst `1`; one queued/claim-ready/running | `6/min`, burst `2`; one queued/claim-ready/running | Two provider slots, bounded queue, existing same-provider retry envelope |

There is no Standard total-run cap. The base queue-join bucket is `1/min`, but
Core may lend otherwise idle capacity: if both queues are empty, a provider slot
is idle, the same Standard session has no queued/claim-ready/running job, and at least
ten seconds have passed since its prior provider admission, it may join
immediately without a base token. Idle borrowing stops as soon as any other
verified session waits. It is an opportunistic work-conservation rule, not a
throughput promise. This lets a lone user continue while preventing that bypass
under contention. Repeated internal attempts to the same provider remain one
admitted job and the receipt shows the actual attempt count. Starting another
Standard session is not called a right to extra capacity; global admission
remains authoritative.

These are initial release values, not permanent marketing promises. They may be
lowered before deployment if measured provider/parser capacity requires it, but
the UI, `/developers`, errors, tests, and public evidence must publish the same
effective values. Limits cannot be raised past the reviewed resource envelope by
client code or an unreviewed environment change.

Queue/control-plane Nginx and Core ceilings are exact starting contracts:

| Control operation | Global | Verified session/credential | Connection/capacity rule |
| --- | --- | --- | --- |
| Standard start | `30/min`, burst `10` | valid cookie is idempotent, not reminted | `10` connections; `512` active Standard sessions |
| Queue join | `12/min`, burst `4` | Standard `1/min` burst `1`; Priority `6/min` burst `2`; reviewed idle-borrow exception only | one active queue record |
| Read-only status | `60/min`, burst `12` | `6/min`, burst `1` | no fairness/state mutation |
| Authenticated 25-second claim long-poll | `48/min`, burst `12` | `3/min`, burst `1` | `16` global and one per session/credential |
| Cancel | `30/min`, burst `5` | `2/min`, burst `1` | queued/claim-ready only |
| Early/duplicate execute attempts | `30/min`, burst `5` | `4/min`, burst `1` | matching claim still required; one running |

Priority login keeps its existing hard global `2/s`, burst `10`. Fixed overflow
is `429 queue_rate_limited` for queue controls and `429 rate_limited` for auth;
active-session capacity is fixed `429 standard_capacity`. Early Nginx failures and
Core failures use the same value-free status/body and never reflect cookies,
capabilities, positions, or input. Duplicate tabs share the one per-session claim
connection and receive fixed `409 queue_already_active`, not extra polling budget.

#### Work-conserving visible queue

Core remains a single process and owns an in-memory, content-free provider
scheduler in front of the existing maximum of two provider operations. The two
slots are identical rather than permanently reserved. Every provider-bound path
acquires one scheduler admission for its full same-provider retry envelope. The
dispatcher is globally work-conserving:

- while both classes wait, global weighted round-robin grants bounded claim
  opportunities in the exact sequence `Priority, Priority, Priority, Standard`,
  regardless of which physical slot became free. A granted opportunity counts
  even when its client misses the applicable bounded claim-to-execute handoff,
  so a stale client
  cannot distort the class schedule. No preemption occurs. Because two client-
  mediated claims may complete in different network order, the product does not
  promise that observed provider-start timestamps reproduce the grant sequence;
- if either queue is empty, the other class is eligible for both slots. Thus
  Priority receives three of four claim opportunities under sustained eligible
  contention and Standard has a finite selection-opportunity no-starvation
  bound. A slot is never held for a merely queued
  client; the only bounded reservation is the active claim window below;
- each verified session or priority subject may own only one queued, claim-ready, or
  running provider admission; the bounded queue holds at most 12 entries total,
  no more than eight Standard and four Priority;
- queue join requires at least 900 seconds remaining in the verified session and
  a still-valid preview approval. Join consumes that approval and mints a strict
  encrypted `provider_queue_v1` capability valid for 15 minutes. The queue
  deadline is exactly the minimum of `join+600 s`, `session expiry-210 s`, and
  `capability expiry-210 s`; a request that cannot receive the full provider
  envelope never reserves a slot;
- a foreground browser holds its queue capability in memory and maintains one
  authenticated long-poll claim request. A merely observed/status-only entry is
  never eligible and never reserves capacity. When a slot becomes available, the
  scheduler issues one HTTP claim with at least 20 seconds of server-side
  response-and-execute-acknowledgement validity. Because the wire contract uses
  integer epoch seconds, the shared record/token/response deadline is rounded up
  by less than one second rather than truncated; actual server-side validity is
  therefore at least 20 and less than 21 seconds. The controller may spend at
  most the first five seconds sending its small no-store response, leaving at
  least 15 seconds of server-side validity for the official client to submit
  execute. This does not claim 15 seconds after the browser receives the bytes.
  That execute request is the only
  reliable proof that the browser received the claim and atomically performs the
  matching `claim_ready → running` transition; ASGI `send()` completion and a
  post-response `http.disconnect` are not treated as delivery evidence. No user
  action is timed. A claim that receives no matching execute request before its
  rounded deadline contacts no provider, loses its old fairness age on the
  first miss, and terminally expires the queue entry and approval on the second.
  Thus a stale/malicious client can waste at most two bounded grant opportunities
  of less than 21 seconds each and cannot remain oldest. A transport exception, controller
  cancellation, or send timeout that the server observes before response
  completion atomically abandons the pending claim at zero misses and retains its
  original fairness age. If the pinned ASGI server silently returns from a send
  after an actual peer loss, that condition is indistinguishable from a completed
  response; no execute follows, so the same bounded missed-claim rule applies and
  provider contact remains impossible. Queue
  position is approximate because cancellations, claim eligibility, retries, and
  weighted fairness can change order; the product does not invent an ETA.

Queue records contain only random queue ID, hashed session/subject binding,
service class, approval-JTI, queue-capability, and current claim-JTI hashes,
timestamps, fairness age, state, claim-miss count, and attempt counters. They
contain no source, protected payload,
PDF, mapping, provider output, raw invite, or human identity. The encrypted queue
capability and exact source/protected bytes remain only in the page's memory. A
refresh can recover **status only** through the HttpOnly session; it cannot resume
or execute because the capability/content intentionally were not persisted. The
reloaded page says so, offers cancel, and requires a new preview. Restart clears
the queue and process-local sessions; the UI reports the interruption and also
requires a fresh preview.

The queue uses four canonical exact routes plus `/v1` aliases, keeping prefix
routing forbidden:

- `POST /api/provider-queue/join` accepts exact `{ticket}`. Under the one process-
  wide lock it authenticates the tagged preview ticket, rejects any queued/used
  JTI, checks session/rate/deadline/capacity, records only hashes/metadata, consumes
  the original approval, and returns `201` with exact `state:"queued"`, approximate
  nullable `position`, `queue_expires_at_unix`,
  `poll_after_ms:10000`, and opaque `queue_capability`. Responses are `no-store`.
- `GET /api/provider-queue/status` accepts no body or query and returns exact
  `state` (`queued|paused|claim_ready|running|complete|failed|cancelled|expired|
  absent`), approximate nullable `position`, nullable fixed `reason`
  (`claim_missed_requeued|claim_missed_expired|deadline_expired|provider_failed|
  approval_invalid|document_integrity_failed|document_parser_unavailable|
  residual_pii|restore_failed|internal_error|cancelled`), enqueue/deadline
  timestamps, `poll_after_ms:10000`, and
  whether automatic execute remains possible. It never returns a capability,
  claim, or content and
  is strictly read-only: it cannot change fairness age, eligibility, or state.
- `POST /api/provider-queue/claim` accepts exact `{queue_capability,
  last_revision}` and holds one long-poll for at most 25 seconds. It authenticates
  class/session/queue/JTI/deadline, marks the entry foreground-eligible only for
  that request, and returns queued state/revision or one opaque claim when globally
  selected. A connected no-slot timeout returns `200` queued with null token and
  creates no claim acknowledgement. A selected HTTP claim returns
  `claim_token`, an absolute `claim_expires_at_unix` rounded upward from
  grant-time-plus-20-seconds, and nominal `claim_window_seconds:20`. The matching execute request is the
  acknowledgement and must arrive before that exact deadline. One session may
  have only one claim poll; disconnect observed before selection removes
  eligibility immediately. The AEAD token binds queue,
  capability JTI, session/subject, slot, revision, boot nonce, and an outer expiry
  equal to that rounded record deadline, but that ciphertext is never sufficient
  without the matching current server record.
- `POST /api/provider-queue/cancel` accepts exact `{}`, invalidates the queue entry,
  capability, and bound approval, and returns `204` from queued/claim-ready/expired/
  absent states; a new provider-free preview is required before rejoining.

New Guest/custom-text/document execute bodies replace the preview `ticket` with
the matching `queue_capability`, `claim_token`, and their previously required source/protected
fields. The capability is an AEAD tagged union containing the authenticated
preview claims, queue ID, original approval JTI, session/subject, service class,
boot nonce, issue/queue/execute deadlines, and a fresh queue JTI; it contains no
raw source or mapping. Execute validates the capability and atomically transitions
the matching `claim_ready → running` record before provider contact. The official UI's
button says `Approve and join queue; when admitted, AI Guard will send this exact
protected text automatically`, so claim-ready requires no inaccessible second action.

Legacy `/roundtrip` cannot bypass fairness. It retains its exact request/response
DTO and uses an internal Priority-class scheduler entry with a five-second wait
deadline; if not selected, it returns the already-compatible fixed `429
rate_limited` without provider contact. Its internal lease is created and consumed
inside the same request. New execute routes require `queue_capability`; legacy is
the only compatibility adapter and is included in global weighted admissions,
slot ownership, rates, and tests. The exact API allowlist is the 40 locations
enumerated above, never a dynamic path or wildcard.

The atomic state machine is `preview-ready → queued → claim_ready → running → complete`
with terminal `cancelled|expired|failed`. Duplicate join returns fixed `409
queue_already_active`; invalid/cross-session capability `403 queue_invalid`;
queue full or join rate `429 queue_full|queue_rate_limited`; deadline loss `410
queue_expired`; execute without the current claim `409 queue_not_ready`; restart follows the
existing session-invalid `401`; and cancel after `running` returns fixed `409
provider_already_running` because the upstream request may continue. Capability,
status, execute, and cancel are all one-session/one-subject and one-process atomic.

#### Queue UX and acceptance

The main journey remains `prepare → preview exact protected payload → approve and
join → automatic admitted execution → provider result`. Queueing is a transient
state inside the approval stage, not another dashboard. It shows service class,
approximate position, elapsed wait, and cancel while keeping the approved payload
and human-review warning available. A compact header recovery link appears only
while this stage is active; it carries no position/ETA and consumes no permanent
mobile navigation slot.

The queue card persistently says: `Keep this page open and in the foreground. If
you switch tabs/apps, minimize, lock the phone, or go offline, this request will
not start. Your fairness age is retained when you return, but the queue deadline
continues. This applies while paused before selection; if an already-issued
automatic-start claim misses its handoff, the first miss moves the request to the
queue tail and the second expires it.` It shows the absolute local-time deadline
as well as elapsed wait.
Loss of visibility or the authenticated claim long-poll changes the visible state
to `Paused`; returning
sends an immediate authenticated claim long-poll, restores `Queued` with the
current fairness age, and never resets the deadline or silently submits the
provider request. A read-only status check after refresh cannot make the orphan
eligible because it lacks the in-memory queue capability.

Status changes use one restrained live region; countdowns and position polling do
not chatter or steal focus. The paused and resumed transitions are each announced
once. `claim_ready` announces that the already-approved request
is starting automatically, and provider completion focuses the result heading.
`claim_missed_requeued` announces the one-time demotion and updated approximate
position. `claim_missed_expired` focuses an actionable error saying `Automatic
start could not complete twice; nothing was sent to the provider; create a new
preview.` Neither state implies provider contact.
Offline polling says `status unknown; your request was not resubmitted`, resumes
without duplicate join, and never claims cancellation. Queue-full/rate/capability/
expiry/restart errors focus one actionable summary and preserve the provider-free
preview when still valid. Cancel is offered only before running and requires a
confirmation that the approval and any upload/preview work must be recreated.
Once running, the UI replaces Cancel with `Clear this page` and the truthful
warning that clearing cannot promise upstream cancellation. After refresh,
status-only recovery explains that private content was not stored, cancels the
orphan only after confirmation, and returns focus to the relevant text/PDF
preview action.

Release-blocking tests must prove global work conservation outside the bounded
claim handoff and the exact 3:1 claim-grant sequence under contention, including
missed grants counting once without claiming a false provider-start ordering;
both-slot borrowing when one class is empty, no Standard selection-opportunity
starvation, per-session/per-credential ownership, duplicate tabs,
capability-authenticated claim eligibility, read-only status behavior, first-miss
tail demotion, second-miss expiry, deadline pruning before reservation,
cancel/running truth, restart, saturation, idle borrowing, rate refill, retry
accounting, legacy `/roundtrip` scheduler participation, and exact 40-route denial.
Exact-second boundary fixtures cover custom-text admission at `1,030/1,029`
seconds and document admission at `1,230/1,229` seconds remaining, plus both
causes of `queue_join_before_unix`: ticket-derived expiry returns/focuses the
`410 approval_expired` preview recovery, while session-derived expiry returns/
focuses the `409 session_review_window` authority recovery before any PDF body is
sent by the official client or consumed by Core. Equality fixtures for custom,
synthetic, and uploaded-document deadlines prove the mandatory session-derived
`409` branch, authority-action focus, and no-body behavior in both UI and Core.
Delayed-body/processing fixtures cross the initial `10`- and `30`-second budgets
and prove the post-processing `1,020/1,200` checks return fixed `409` without a
ticket or provider call. Delayed-response browser fixtures prove the receipt-time
`120/300` minimum discards the in-memory approval, makes no queue request, and
focuses the same authority recovery rather than showing a shortened countdown.
Clock-skew fixtures set the browser wall clock both ahead and behind while
holding Core time fixed; eligibility, countdown, and focus remain identical.
Slow auth/preview responses subtract the complete monotonic request duration;
visibility resume, BFCache restore, system wake, missing/malformed server-time
headers, and lost anchors all fail closed and require a fresh session-time sample
before upload, countdown, or queue join.
Auth-contract fixtures prove the legacy `expires_in` body stays byte-compatible
while the two exact Core headers bind current time and absolute session expiry.
Core-originated preview errors carry server time; early Nginx `413/429` remain
headerless, no timing anchor is created, and provider-bound controls stay closed.
Missing/malformed fixtures cover each timing header independently and together,
assert the fixed `timing_unavailable` summary, single announcement, Retry focus,
approval disposal, and closed upload/join/provider controls. Repeated-failure
fixtures preserve Retry focus without chatter; successful retry restores focus
to Preview/Upload without restoring an old approval. Edge `413/429` fixtures keep
their size/rate recovery and require a new timing sample before another request.
Pre-request and post-preview fixtures prove the fixed copy never claims that no
data reached AI Guard; the uploaded-preview variant retains the exact PDF-
traversed-AI-Guard / not-sent-to-Pathumma boundary.
They also prove the Standard authority matrix and DTO kinds; 15-minute queue
capability versus session/provider deadlines; status-only refresh behavior;
fixed error/focus/recovery states; content-free records; no source/capability in
browser persistence; public cookie rotation cannot create verified identity;
unique invite credentials receive independent quotas; copied credentials are not
represented as people; and no new execute provider call can occur without the
scheduler's matching claim-ready record, capability, and claim token.
Slow-network, page-visibility race, suspended-background-tab, and main-thread-
delay browser tests must exercise both claim-miss outcomes and their exact live/
focus recovery without duplicate provider contact.

### Hosted 3.0 implementation plan and stage exit gates

Status: implementation started on 2026-08-16. The owner approved execution of
this plan in the current session. Hosted production remains `2.5.0`; a stage may
change local source and tests, but no stage may claim or publish Hosted `3.0.0`
until Stage 8 passes, the owner authorizes the exact reviewed SHA, and the
protected release in Stage 9 passes.
The plan is deliberately dependency-ordered so a visible surface cannot get
ahead of its authority, privacy, scheduler, or caller contract.

#### Stage 0 — Freeze the 2.5 baseline and executable seams

Work:

- inventory the current AuthGateway, FastAPI DTO/routes, provider retry path,
  Nginx exact allowlist/rate lanes, Compose resource/secret boundary, web caller,
  and every CI/local/public acceptance reader that assumes 16 routes or Hosted
  `2.5.0`;
- run the existing fast contract suite before runtime edits and record failures
  that predate Hosted 3.0 separately from new regressions;
- add one Hosted 3.0 contract-test entry point and fixtures without weakening or
  rewriting the existing 2.5 assertions;
- keep user-owned `docs/DEPLOY-DAY.md`, paused `web/logo-preview.html`, LINE
  evidence, and existing browser artifacts outside the implementation diff.

Exit gate:

- current auth, core, frontend-session, public-surface, Nginx, Compose, build-
  context, release-source, secret-hygiene, GitLab, and platform-acceptance
  contract tests pass on the unmodified runtime baseline;
- `core/VERSION` remains exactly `2.5.0`, the public proxy still exposes exactly
  16 routes, and both PDF-redaction/OCR aliases remain fixed 404;
- the durable document records baseline commands/results and names every file
  that Stage 1 is allowed to modify. No runtime claim changes in this stage.

Stage 0 implementation/test evidence on 2026-08-16:

- the complete native check surface passed after Docker Desktop was started:
  upstream sync (75 files), auth (13 tests), executable frontend session,
  public surface, Hosted core (11 tests), the new Hosted 3.0 planning fence,
  Thai PII evaluation, build-context, secret-hygiene, platform-acceptance,
  release-source, GitLab, real built Nginx, and Compose contracts all exited 0;
- `nginx_contract.py` built and exercised the current proxy in Docker and passed
  its exact route, auth isolation, fixed denial, header injection, log, web
  syntax, wording, and no-store checks. The first attempt was blocked before test
  execution because Docker Desktop was stopped; it was rerun successfully and is
  recorded as an environment event, not hidden as a passing first attempt;
- `tests/fixtures/hosted3/contract.json` now provides the machine-readable target
  fence and `tests/hosted3_contract.py` proves Stage 0 still has VERSION `2.5.0`,
  exactly 16 public routes, no premature Hosted 3.0 route, correct 40-route
  arithmetic, the pinned AEAD dependency, queue constants, TTL/review invariants,
  modality exclusion, and the authoritative implementation-stage marker;
- `.gitlab-ci.yml` and `tests/gitlab_contract.py` now run and require that fence.
  Runtime, public routes, web UI, Docker/Compose, secrets, VERSION, and deployment
  were not changed in Stage 0.
- focused adversarial review found that the first Stage 1 file fence would have
  required editing manifest-pinned upstream files and that the first route fence
  enumerated exact locations without rejecting a newly added prefix matcher.
  The corrected architecture keeps all Hosted 3.0 code in the bounded port-owned
  `core/aift_hosted3/` overlay and continues to hash-pin `core/app/**` and
  `core/pii_redactor/**`. The executable route fence now proves canonical route
  uniqueness/disjointness, builds the unique 40-member target set, rejects every
  unapproved non-exact Nginx matcher, and the built-proxy test denies all 24
  planned canonical/alias paths before exposure;
- after those corrections, the complete 14-command native check surface was run
  again on 2026-08-16. Upstream verification, auth, frontend session, public
  surface, Hosted core, Hosted 3.0 fence, evaluation, build context, secret
  hygiene, platform contract, release source, GitLab contract, built Nginx, and
  Compose all exited `0`. Stage 0 remains in independent closeout review; this
  result does not claim that Stage 1 runtime work or any later stage exists.
- final independent art-direction, frontend/product-security, and UX/accessibility
  closeout reviews each returned a clear pass. They independently verified the
  stage order, bounded overlay ownership, manifest-pinned upstream files, unique
  40-route target arithmetic, rejection of non-exact proxy matchers, live denial
  of all 24 planned paths, truthful 2.5/16-route status, and the complete
  14-command rerun. Stage 0 is complete; Stage 1 may start.

Hosted 3.0 runtime code is a port-owned overlay, never a local patch to the
vendored detector application. The bounded package prefix is
`core/aift_hosted3/`; `sync/sync_from_upstream.py` owns only that exact prefix
and continues to reject unrelated extras. `core/app/**` and
`core/pii_redactor/**` remain hash-pinned by `sync/PORT_MANIFEST.json`. New
routes and DTOs compose around the vendored FastAPI application through
`core/aift_gateway.py`; if an upstream behavior itself must change, it requires
an upstream commit and reviewed resync rather than a port-local edit.

Stage 1 may modify only the existing port-owned `core/aift_auth.py` and
`core/aift_gateway.py`, files under `core/aift_hosted3/`, `core/Dockerfile` for
an explicit package copy, the bounded ownership rule in
`sync/sync_from_upstream.py`, and directly corresponding
auth/Hosted3/sync/build-context/secret/Compose tests. It may wire those exact
check-only commands into `.gitlab-ci.yml` and pin them in
`tests/gitlab_contract.py`; deploy, acceptance, and ops jobs remain out of
scope. It may update this durable document and `STATE.md` when verified facts
change. It must not modify
`core/app/**`, `core/pii_redactor/**`, API Nginx routes/rates, web UI/assets,
VERSION, provider/PDF/queue behavior, production Compose service topology, or
deployment jobs in this stage. Any required expansion must be recorded here
before editing.

#### Stage 1 — Service-class authority and timing foundation

Work:

- extend the port-owned auth boundary with automatic 30-minute
  `public_guest`/Standard sessions, idempotent end, and mutually exclusive
  Priority Invite sessions;
- replace the single shared-code assumption with an owner-managed, bounded
  digest-to-opaque-subject registry while preserving constant-time verification,
  revocation, secret separation, process-local sessions, and the current legacy
  invite path during migration;
- carry a typed authority context (`scope`, service class, session/subject
  binding, expiry) to protected core routes without forwarding raw invite or
  cookie values;
- add the exact Core server-time/session-expiry headers, client-neutral error
  metadata, new HTTP-v2 error rows, and strict Standard start/end DTOs while
  keeping the existing auth-session body byte-compatible.

Exit gate:

- auth tests prove Standard start/idempotence/end/capacity, Priority per-issued-
  credential isolation/revocation, no coexistence, tamper/expiry/restart/key-
  rotation behavior, origin/Fetch-Metadata enforcement, and no raw codes/names in
  memory records, responses, arguments, or logs;
- legacy invite login/logout/session bodies and cookie flags remain compatible;
  the additive timing headers have exact provenance and fail closed when absent;
- Core receives only a verified opaque authority context, every unauthorized or
  cross-class call fails before body processing, and no provider call is added;
- focused unit/contract tests and the full Stage-0 suite pass before review.

Stage 1 completed implementation/test evidence on 2026-08-16:

- `core/aift_hosted3/authority.py` implements an immutable opaque authority
  context and a startup-strict masked Priority registry. The registry accepts at
  most 32 exact digest rows, enforces canonical opaque subjects, unique lowercase
  SHA-256 digests, fixed role/Boolean state, canonical 22–128-character
  base64url presented codes for new rows, and retains only a digest-backed opaque
  legacy subject for migration. No raw invite is retained on the gateway or in a
  session record;
- `core/aift_auth.py` now supports fixed 30-minute process-local Standard
  authority at internal `/aift/auth/guest` and `/aift/auth/guest/end`, separately
  signed Priority and Standard cookies, exact Standard capability DTOs,
  idempotent start/end, 512-session fail-closed capacity, per-issued Priority
  subjects, two-authority conflict clearing, the Standard-versus-Priority route
  matrix, and immutable downstream `aiguard_authority` context. Legacy login,
  logout, session JSON/cookie shape, and `v1` cookie syntax remain compatible;
- authenticated session and Standard-start responses add exact no-store Core
  server-time/session-expiry and `standard|priority` class headers without
  changing the legacy authenticated session body or exposing a subject. The
  overlay owns fixed value-free HTTP-contract-2 rows for
  `409 session_review_window` and `410 approval_expired`; no new preview or
  provider call is implemented in this stage;
- `tests/hosted3_authority_contract.py` contains 10 focused tests covering exact
  schema/idempotence/capacity, origin and pre-body rejection, per-credential
  isolation, strict/disabled/weak registry rows, restart revocation, raw-secret
  non-retention, Standard tamper/expiry/restart/key rotation, mutual exclusion,
  route scope, legacy body compatibility, exact timing headers, and fixed v2
  error rows. The existing 13 auth tests still pass unchanged in behavior;
- the Core Dockerfile explicitly copies only `aift_hosted3/`; the build-context
  fence requires that copy. Local image `aiguard-stage1-contract:local` built
  successfully from the final Stage 1 source as local manifest-list digest
  `sha256:b1d2a32f37da9ca7cce8b5671427bffb7c5fb6ff60cdca1e09e04764ad047793`
  and imported the Standard path, typed context, service-class header, and two
  additive error rows from the image. This is built-image evidence, not a public
  route or production deployment;
- the expanded 15-command native check surface, now including the new authority
  contract, passed in full: upstream verification, legacy auth, Stage 1
  authority, frontend session, public surface, Hosted core, Hosted 3.0 fence,
  evaluation, build context, secret hygiene, platform contract, release source,
  GitLab contract, built Nginx, and Compose each exited `0`. The proxy remains at
  16 exact routes and still denies all 24 planned Hosted 3.0 paths.
- independent art-direction/product-scope, frontend/product-security, and UX/
  lifecycle reviewers returned clear passes after fixes. The final frontend
  review matched SHA-256 hashes for the three Stage 1 Python sources inside the
  rebuilt image to the working source, reran all 15 commands, and verified the
  bounded CI file exception. UX review verified reload-safe service-class
  metadata and the exact local-internal versus public-production status. No
  material disagreement remains; Stage 1 is complete.

#### Stage 2 — Content-stateless approval engine and custom-text preview

Stage 2 may modify only `core/aift_gateway.py`, files under the already bounded
`core/aift_hosted3/` overlay, and directly corresponding Hosted3/build/CI tests.
It may wire the exact new check-only test into `.gitlab-ci.yml` and
`tests/gitlab_contract.py`, including the exact check-job-only cryptography
package required to execute that test in the digest-pinned Alpine runner; it
must keep this document and `STATE.md`
current. It must not modify the manifest-pinned `core/app/**` or
`core/pii_redactor/**`, API Nginx routes/rates, web UI/assets, VERSION,
Docker/Compose topology, deployment jobs, the legacy `/roundtrip` path, or any
provider call. The internal canonical `/api/protection-preview` handler may
exist behind `AuthGateway` during this stage, but the API proxy must continue to
deny both public canonical and `/v1` aliases until Stage 5.

Work:

- implement the AES-256-GCM approval envelope, boot nonce, strict tagged union,
  bounded consumed-JTI registry, deterministic `pg-v1` Token regeneration, fixed
  provider/detector/prompt bindings, and zero-content replay state;
- implement provider-free custom-text preview with strict DTOs, residual-policy
  result, protected digest, exact approval TTL/join deadline, Core timing
  headers, and no raw echo;
- implement document ticket codecs and validation service seams against injected,
  deterministic metadata only. Stage 2 does not parse a PDF, expose a document
  route, or claim a working synthetic/uploaded document preview; Stage 3 owns the
  first real hash-pinned and uploaded PDF flows through the secretless parser;
- implement execute validation as an internal service seam only: source
  re-protection, digest/revision/session/kind/class checks and fresh outbound scan
  must pass before it can be connected to provider admission in Stage 4;
- keep legacy `/roundtrip` behavior unchanged and publicly reachable throughout
  this stage.

Stage 2 implementation in progress on 2026-08-16:

- `core/aift_hosted3/approval.py` now implements the dedicated
  HMAC-derived AES-256-GCM key, fresh 96-bit GCM nonces, process boot binding,
  strict custom/document tagged union with Token-only document branches,
  branch TTLs, fixed provider/prompt/
  detector bindings, and a bounded lock-protected replay registry that stores
  only JTI SHA-256 plus expiry. Its externally approved replay/capacity codes
  are exactly `approval_consumed` and `approval_registry_full`;
- `core/aift_hosted3/protection.py` adds the `pg-v1` deterministic Token seed
  plan with domain-separated HMAC expansion and rejection sampling. It derives
  token namespace/nonces from encrypted seed plus transient type/original/
  ordinal/collision facts, seeds the existing manifest-pinned sanitizer, and
  never changes legacy `/roundtrip` randomness;
- `core/aift_hosted3/preview.py` implements exact provider-free custom-text
  preview and a pre-provider execute-validation seam. It enforces the 20,000-
  code-point schema, initial/post-processing timing floors, branch TTL and
  120-second review window, null approvals for blocked/uncertain outcomes, no
  raw echo, deterministic re-protection, constant-time source/protected digest
  comparisons, repr-suppressed decrypted approval facts, and explicit mapping/
  approval cleanup;
- `core/aift_hosted3/overlay.py` owns the internal canonical preview route with
  before-body authority/time/API-key/HTTP-v2 checks, strict duplicate-key JSON,
  bounded body reads, no-store timing/class metadata, and fixed errors.
  The overlay's minimal fixed error rows are dependency-free and do not import
  the vendored FastAPI DTO module during focused CI. `core/aift_gateway.py`
  runs the single-worker guard before any manifest-pinned `app` import, then
  composes the overlay inside the existing `AuthGateway`; startup fails unless
  `UVICORN_WORKERS` is exactly `1`, because replay state remains process-local.
  Nginx is
  unchanged and still denies all 24 planned Hosted 3.0 paths;
- `tests/hosted3_approval_contract.py` contains sixteen fast focused
  tests for the deterministic AEAD vector, nonce/tamper/key/boot/session/class/
  kind/revision/expiry failures, bounded one-use replay state, document codecs,
  pg-v1 mapping, exact preview DTO/timing/limits, blocked/uncertain outcomes,
  execute reconstruction/replay, aggregate protection-code/model source
  bindings, strict internal ASGI admission/metadata, exact initial/pre-mint/
  deadline boundary fixtures, concurrent one-winner consumption, Token-only
  document branches, explicit sensitive-fact cleanup, and the single-worker
  startup invariant. All sixteen pass. The digest-pinned GitLab job installs
  exact Alpine `py3-cryptography=42.0.7-r0` in the `check` job only; executable
  CI assertions prove deploy/acceptance/ops inherit no such package. The Core
  runtime remains separately locked to `cryptography==50.0.0`;
- the complete expanded sixteen-command native check surface passed against the
  final reviewed Stage 2 source: upstream verification, legacy auth, Stage 1 authority,
  Stage 2 approval/preview, frontend session, public surface, Hosted core,
  Hosted3 fence, evaluation, build context, secret hygiene, platform contract,
  release source, GitLab, built Nginx, and Compose each exited `0`. Nginx still
  reports 16 exposed locations and denies all 24 planned additions;
- the final local Linux image `aiguard-stage2-contract:local` was rebuilt as
  manifest-list digest
  `sha256:8b743aa18fd9f03741b99cc997ac590bb1f881b92277ead7401475e0dd1879a9`
  at `2026-08-16T10:15:54Z`, with revision label
  `stage2-final2-local-contract` and pinned Core `cryptography 50.0.0`. SHA-256
  for all ten current Python files across `aift_gateway.py`, `aift_auth.py`, and
  `aift_hosted3/*.py` matched the final source byte-for-byte. A real in-image
  Standard request exercised the internal provider-free preview with synthetic
  Thai résumé/email/phone text: NAME, EMAIL, and PHONE were replaced, raw input
  was absent from the DTO, class/time metadata and the custom ticket were exact,
  and the request succeeded with no provider credential configured. Repeated
  real sanitizer calls with the same source/salt/pg-v1 seed produced byte-
  identical Token output and mapping. A separate final-image import with
  `UVICORN_WORKERS=2` failed closed before application configuration or any
  manifest-pinned `app` import;
- in-review hardening expanded the detector revision binding to
  the complete protection pipeline, tightened document-codec caps, suppressed
  and explicitly cleared sensitive decrypted facts, enforced Token-only
  document branches, normalized error vocabulary, added concurrent replay and
  single-worker invariants, made focused CI dependencies executable, and added
  source/timing-boundary assertions. Independent art-direction/scope, frontend/
  product-security, and UX/lifecycle re-reviews all passed against the corrected
  source and final evidence. Stage 2 is complete.

Exit gate:

- deterministic vectors prove encrypt/decrypt, nonce uniqueness, tamper/wrong-
  key/boot/session/class/kind/revision rejection, one-use atomic consumption,
  registry capacity/pruning, restart invalidation, and no source/mapping in
  tickets or replay rows;
- custom-text preview tests prove exact request/response fields,
  20,000-code-point limits, Token/Surrogate behavior, blocked/uncertain null
  tickets, strict TTL/deadline precedence, 120-second review enforcement, and
  zero provider requests. Document codec tests use injected facts and cannot be
  cited as parser or document-preview evidence;
- execute-seam tests prove changed/replayed/stale/cross-authority payloads fail
  before provider contact and valid deterministic reconstruction matches the
  exact approved protected digest;
- no new route is exposed through Nginx until its end-to-end contract is ready.

#### Stage 3 — Secretless text-layer PDF to Protected Markdown

Stage 3 may modify only the bounded `core/aift_hosted3/` overlay and gateway
composition, a new explicit `pdf-parser/` build context (including dependency
locks, licence/notice material, parser process, healthcheck and seccomp profile),
`docker-compose.yml` for the internal secretless parser topology, directly
corresponding document/Compose/build/secret/CI tests and synthetic fixtures,
check-job-only CI wiring, this document, `STATE.md`, and the Hosted3 stage
fixture. It must not modify manifest-pinned `core/app/**` or
`core/pii_redactor/**`, `api/**`, `web/**`, `core/VERSION`, release/deploy/
acceptance/ops jobs, or production scripts. Nginx must continue denying every
planned document route throughout this stage.

Stage 3 began with only the marker/status transition. The current local branch now
contains a **hardened, unexposed Stage 3A parser candidate**, not a completed
Stage 3 or production feature: hash-locked pikepdf `10.10.0` with bundled qpdf
`12.3.2`, pdfplumber `0.11.10`, PDFium `5.12.1`, a bounded Unix-socket frame,
explicit container controls, a deterministic fictional Thai résumé fixture, and
active-content/text-layer/raster/visible-text gates. The rendered fixture is
visually clean; the image returns one page, 31 immutable segments, and page 1 in
the visual-omission list. Nginx still denies every planned document path and no
Core document-preview, Compose, browser, version, or deployment claim exists.

The first independent lifecycle review found real blockers in the original
candidate: `asyncio.to_thread` timeout did not terminate native parsing, an unlink
error was swallowed, header/body framing could hold the only job indefinitely,
PDF text render modes `3` and `7` were accepted as visible content, the child
result was not strictly reconstructed, the custom seccomp profile expanded the
Docker default syscall surface, and a separate unhashed pip download contradicted
the byte-lock claim. The corrected candidate now runs every parse in a killable
child process that is reaped before cleanup/capacity release; any spool/output
unlink failure terminates parser PID 1 with exit `70`; header, body, process,
connection and one-job admission are bounded; only non-clipping visible text
render modes `0`, `1`, and `2` are accepted; transparent text and recursively
reachable page/Form clipping paths that cannot
be visibility-resolved are rejected under bounded depth/cycle validation; the
supervisor recomputes every result field through an exact schema;
the image uses the official Moby `seccomp/v0.2.3` deny-by-default profile and does
not allow `io_uring_setup`; and Python packages are installed only from the
hash-locked requirements file. The default fixture subtitle was also corrected
after a real whole-document detector interaction caused a residual NAME block.

Current local Stage 3A evidence, all against image
`sha256:6e1047529f4e1bda5a0e293d3deaa11ccbec8a2e85dda4537866b33d55b1aac5`:

- source plus in-image parser contracts pass `11/11`, covering exact dependency/
  licence/protocol/fixture/result boundaries, deterministic extraction, active
  structures, encryption, page/dimension/malformed files, image-only/large-raster
  files, text render modes `3` through `7`, direct and nested page/Form clipping
  paths, and kill/reap behavior;
- container lifecycle tests pass `2/2`: slow partial headers and bodies return
  fixed `document_parser_unavailable`, capacity recovers with no job/result files,
  and an induced private-spool unlink failure stops PID 1 with exit `70` before
  the parser can continue serving;
- the real parser's 31-segment output passes the final Stage 2 image's real
  `ProtectionService` in Token mode, replacing 11 entities across ADDRESS,
  DATE_OF_BIRTH, EMAIL, LOCATION, NAME, ORGANIZATION, PHONE, and POSTAL_CODE with
  protected digest
  `90c0e1d7e2e74ec6c018c5655c80f45311f412cf94abab9ac62e460a49a8f829`
  and no residual block.

This is local parser implementation/test evidence only. Independent Stage 3A
art/product, frontend/security, and UX/lifecycle re-reviews all passed against
the exact `6e104752...` image after the recursive clipping and text-render-mode
fixes. Stage 3A is closed and Stage 3B Core Unix-socket/provider-free document-
preview integration is in progress. Remaining exact-boundary/adversarial
coverage, Compose, final image parity, the complete Stage 3 suite, and all three
final Stage 3 reviews remain mandatory.

Stage 3B found one value-free cross-segment detector interaction in the reviewed
fixture: the boundary between achievement segment 24 and skill segment 25 formed
a new false `LOCATION` span only after the protected segments were joined. The
outbound policy was not weakened. The fictional achievement sentence was
rewritten, the deterministic PDF was regenerated, and all scenario pins were
advanced to source SHA-256
`57ffcd9cddfe5abbe3b5b276ad93d22a549d386f01967344315a97cbafc51e6c`.
The current segment-aware Token path preserves all 31 immutable segments and 30
exact separators and passes the combined outbound gate with 12 detections across
ADDRESS, DATE, DATE_OF_BIRTH, EMAIL, LOCATION, NAME, ORGANIZATION, PHONE, and
POSTAL_CODE; its provisional protected digest is
`4e402d73c75b8699706690b7b4cb4a1c2e789d97c32daae1de4eb0999ab5d03f`.
The prior `6e104752...` image/digest remains Stage 3A historical evidence only;
fresh Stage 3B image, Unix-socket, and reviewer evidence is still required.

Stage 3B/3C implementation is now present but still unexposed and under final
hardening. Core has a strict async Unix-socket client with parser admission
before ASGI-body consumption, an 11-second total ingress deadline, a 1,024-frame
cap, PDF-signature and exact-length hashing, duplicate-free bounded response
parsing, NFC/schema/manifest/source revalidation, and explicit sensitive-result
cleanup. The provider-free document service implements synthetic, Standard, and
Priority document branches, exact source-free DTOs, segment-aware Token
protection, fresh request-scoped receipt IDs, 16,000-code-point/48-KiB internal
protected-output hard stops, the stricter 8,000-code-point/32-segment/9,120-byte
provider-executable gate, 1,230/1,200-second timing floors, and bound approval tickets. A
separate source-anchored artifact validator accepts only a 32-KiB
`classifications[{segment_id,role}]` JSON response, rejects provider-authored text
or unknown structure, requires every immutable segment once in its exact input
position, then groups it deterministically into the server-owned
`ordered_sections` artifact, verifies the
exact Token multiset and outbound policy again, and renders fixed Thai headings,
escaped Markdown/plain text, and semantic HTML with mandatory provenance.

Current focused source tests pass: document preview `4/4`, protected artifact
`5/5`, approval `16/16`, authority `10/10`, and the Hosted 3 stage fence. A real
Linux two-image Unix-socket suite passes `4/4`: an uploaded PDF streams in three
chunks with source/manifest recomputation; a busy parser causes zero ASGI body
reads; invalid signatures and excessive empty frames fail closed; and both the
server-owned scenario and Standard upload produce source-free bound tickets.
The real parser-to-protector scenario gate also passes. Compose now defines a
fourth internal `pdf-parser` service with no network, read-only root, UID/GID
1000, all capabilities dropped, no-new-privileges, the pinned Moby seccomp
profile, `512 MiB`/one CPU/32 PID limits, private `/work` tmpfs, and a socket-only
named volume mounted read-only by Core. An intermediate Compose build proved
both services healthy, `network_mode:none`, no parser application secrets, a
read-only Core socket mount, and a real source-free scenario ticket. Those
intermediate image digests predate the latest output-cap, collision, NFC, and
health-recovery hardening and are intentionally not final evidence. A fresh
image-parity rebuild, full Stage 3 suite, provider-envelope measurement, and all
three closeout reviews are still mandatory. Nginx remains at 16 exact public
routes and denies all planned additions.

The Stage 3C adversarial parser corpus has expanded to `16/16` passing tests
against the pinned parser dependency environment with the current source mounted.
It now covers the exact 5-MiB protocol boundary; attachments, associated files,
XFA, optional-content, collections and external references; compressed object
streams and inline images; exact 10-page, 2,000-point, 8,000-code-point,
80-segment, 10%-single-raster and 15%-combined-raster boundaries; all text render
modes `3` through `7`; page/direct/nested-Form clipping; tiny text; Form cycles,
depth bombs and container-member bombs. This expansion found a real direct-object
walker defect: short-lived pikepdf wrappers could reuse a Python object ID and
make a later direct dictionary look previously visited. The walker now keeps
direct wrappers alive for the full traversal, and a valid external-file-reference
fixture locks the correction. These are current-source results, not final rebuilt-
image or production evidence by themselves; the exact final-image reproduction is
recorded immediately below.

Stage 3C first reached a passing local implementation/test gate against Compose-
built caller images. Parser image
`sha256:a656da8b5ea16828f943931fe5bcb9d971ca112bd39b61c21e4f17e6b392c88b`
and Core image
`sha256:54df5b2206d8d9ec70480a995e69c856abf44ef6d8d104b5a6c50f2d5461647d`
both carry revision label `stage3-final-local-contract`. Image parity passes
`3/3` against every allowlisted current parser/runtime and Core authority/
gateway/Hosted3 source byte. The exact parser image reproduces the complete
`16/16` adversarial corpus; lifecycle passes `3/3`, including slow framing,
kill/reap, unlink-fail exit `70`, and three-strike health restart; the two-image
Unix-socket contract passes `4/4`; and the real scenario-to-protector gate passes
`1/1`. The exact four-service Compose candidate reports parser and Core healthy;
parser is `network_mode:none`, read-only, UID/GID 1000, all capabilities dropped,
no-new-privileges, the deny-default seccomp profile, `512 MiB`, one CPU and 32
PIDs; Core mounts the socket volume read-only. Parser PID 1 exposes only the six
fixed runtime environment keys, a real Compose scenario returns 31 segments/30
separators with the pinned scenario identity, and a bounded log scan finds zero
fixture values, scenario digest prefix, ticket marker, or synthetic secret
markers. The complete current 19-command native check job surface also passes;
Nginx still exposes 16 Hosted 2.5 operations and denies all planned additions.

That image pair became **superseded intermediate evidence** when Stage 3D
preparation found that document tickets inherited the custom-text prompt binding.
At that intermediate point, source selected bindings by ticket kind and locked
document branches to `structure-protected-document-json-v1`; the later Stage 3D
classification protocol supersedes that document revision, while custom-text
tickets retain their existing
prompt revision. Focused approval `16/16`, document preview `6/6`, artifact `6/6`,
and authority `10/10` tests pass the correction, including rejection by a runtime
that expects the wrong document prompt. The document DTO now always carries the
selectable-text/OCR/visual-layout limitation, even when the parser detected no
specific raster/vector page; a fourth warning names exact omitted pages when it
did. Outcome wording is status-aware: only a successful preview says detected PII
was replaced; `blocked` and `uncertain` explicitly say that no usable protected
result was returned and that nothing was sent to Pathumma, while retaining the
source-unchanged and OCR/layout limits. Fresh images, parity, integration,
Compose, and reviewer evidence are mandatory before Stage 3C can close again.

The replacement Stage 3C image pair is parser
`sha256:2413c8bf2f39163f26152055f1c4405515d2f6f8a3bdafcc6431eb79b571f335`
and Core
`sha256:ab25c1e65c5c65ffdccbabb4c5f0daab03a6106072692b298a6210155eee173c`,
both labelled `stage3-final2-local-contract`. Against those exact bytes, parser
adversarial coverage passes `16/16`, lifecycle `3/3`, Unix-socket integration
`4/4`, source/image parity `3/3`, and the real parser-to-protector scenario gate
`1/1`. Focused authority passes `10/10`, approval `16/16`, document preview
`6/6`, and artifact/provider-boundary source validation `6/6`. The complete
current `20/20` native check-job command surface passes; the Pathumma command is
present but reports its intentional protected-environment skip rather than a
network result. The exact four-service Compose runtime reports both parser and
Core healthy, preserves the parser's no-network/read-only/non-root/cap-dropped/
deny-default-seccomp/resource limits and Core's read-only socket mount, and the
real socket scenario produces 31 protected segments with 30 separators, 12
detections across nine types, a source-free DTO, the document-specific prompt
binding, four truthful warnings, and an executable outbound-gate result. A
bounded parser/Core log scan found none of the fictional email/phone, source-
digest prefix, approval-ticket marker, or synthetic test-secret markers. This is
superseded Stage 3C image evidence after the Stage 3D measurement required a
document-only client and a lower provider-executable segment cap. A final rebuild
against those current source changes remains mandatory; nothing here is public or
deployed evidence.

Stage 3D now has an exact, opt-in measurement path rather than an informal manual
prompt. `document_provider.py` defines the fixed source-as-untrusted-data system
instruction and serializes only schema plus the ordered immutable protected
`{segment_id,text}` rows under an exact 9,120-byte provider-request cap. Source
tests separately reach the 8,000-code-point protected-text edge and a 32-segment
representative Thai-plus-Token fixture at the exact 9,120-byte encoded-request
edge; both prove no ID or text is changed.
`tests/hosted3_pathumma_boundary_contract.py` is always syntax/import checked by
the ordinary check job but skips network use unless
`AIGUARD_PATHUMMA_BOUNDARY=1`; in an authorized protected environment it requires
both provider base and key, performs real requests with the document-specific
Tokenmind transport, and emits only counts, byte sizes, timing, and validation
facts. The live development sequence exposed limits without weakening validation:
the generic 1,024-token client returned a non-stop completion at 80 segments; a
document 4,096-token request still returned a truncated 3,701-byte body at 80
segments; and a later attempt at the former 16,000-code-point/48-KiB internal hard
stop returned a truncated 1,621-byte body. Those failures are why the internal
hard stops are not a provider-executable product promise.

The original grouped-ID response happened to pass one 8,000-code-point/
32-segment call in `3,135 ms`, but later identical-size calls produced truncated
JSON or repeated IDs. A role-only vector then passed the real 31-segment résumé
once but produced off-by-one arrays on boundary fixtures. AI Guard did not repair,
guess, or loosen either invalid result. The final unexposed protocol is
`structure-protected-document-classifications-v1`: Pathumma must copy each opaque
segment ID with one allowlisted role in exact input order; AI Guard validates
every position and then performs deterministic grouping. With that protocol, the
real protected default résumé passed at 31 segments, 1,488 protected code points,
3,962 request bytes, 1,497 response bytes, and `5,827 ms`. The exact 8,000-code-
point one-segment edge passed with an 8,126-byte request, 65-byte response, and
`1,271 ms`. The representative Thai-plus-Token 32-segment edge reaches exactly
9,120 request bytes and 5,922 protected code points; it passed three consecutive
runs in `6,010`, `5,878`, and `5,956 ms`, each with an exact 1,589-byte validated
classification response. No provider-authored content or credential was emitted.

Current source rejects preview ticket minting above 8,000 protected code points,
32 immutable segments, or the exact 9,120-byte encoded provider request. It also
replaces the buffered provider call with a killable child process, a pre-parse
32-KiB streamed outer-response cap, a separate 32-KiB extracted-response cap,
and an absolute parent-owned 200-second deadline that kills/reaps slow or
trickling responses. Focused preview and artifact/transport suites pass `7/7`
and `7/7`. This is local protected development evidence, not a deployed Hosted
3.0 claim; fresh final image, full-suite, Compose, and reviewer evidence remain
mandatory after the final protocol/transport changes.

The following final3 pair is now **superseded evidence** because it predates the
strict provider-request gate and streamed/absolute-deadline worker. The former
candidate was parser image
`sha256:a2455a13f2e214b31f76bdca57950a301d219c4f6711e22102ae639217d2f65e`
and Core image
`sha256:05de433e87497cf8a4a42447cb4b58495551724aa6d1600f4230f577a8d29cfc`,
both labelled `stage3-final3-local-contract`. Source/image parity passes `3/3`;
the exact images pass parser `16/16`, lifecycle `3/3`, Unix-socket integration
`4/4`, and real scenario gate `1/1`. Focused authority is `10/10`, approval
`16/16`, preview `7/7`, artifact/provider request `6/6`, and the complete native
check-job command surface passes `20/20`. The live boundary call used the same
source bytes later proven present in the final Core image. The healthy Compose
runtime reported provider segment cap `32`, document output budget `4,096`, a
31-segment/30-separator executable scenario, document-specific prompt binding,
12 detections across nine types, four warnings, a source-free DTO, exact parser
isolation/resource controls, a read-only Core socket mount, and zero bounded log
marker hits. A transient final4 rebuild produced parser image
`sha256:897b35f5e1be3c35bcc93249b8c0f1aa871013e8a7becea8234c93af71b74ef0`
and Core image
`sha256:a010149f1a804f26f50de8537b10162c981c03938ca8de800fbd9d5b2d2ebe09`,
both labelled `stage3-final4-local-contract`; it passed parser `16/16`, lifecycle
`3/3`, Unix-socket integration `4/4`, scenario gate `1/1`, image parity `3/3`,
and the native `20/20` surface, but was intentionally superseded before closeout
when live boundary evidence required the classification protocol above. A fresh
`stage3-final5-local-contract` rebuild and exact evidence replacement were
mandatory before independent closeout; nothing here is public or
deployed Hosted 3.0 evidence.

That final5 replacement is now built: parser image
`sha256:afb81cbdd8cf409c8bf7c40401f0495295637df8571e9fe0d5eadd772b9df3c5`
and Core image
`sha256:83645bfb64269ffde2fca8f30c1821c2e4c02e3a89bfb656edabbcc7a8a31c0b`,
both labelled `stage3-final5-local-contract`. Exact image evidence passes parser
`16/16`, lifecycle `3/3`, Unix-socket integration `4/4`, real parser-to-protector
scenario gate `1/1`, and source/image parity `3/3`; focused authority is `10/10`,
approval `16/16`, document preview `7/7`, and artifact/stream/deadline validation
`7/7`. The complete current native check-job command surface passes `20/20`.
The live boundary suite was then run from the exact final5 Core image bytes, with
only the test file mounted: Thai-plus-Token 32-segment/9,120-byte passed in
`6,094 ms` with a 1,589-byte validated response, and the 8,000-code-point edge
passed in `970 ms` with an 8,126-byte request and 65-byte validated response.

The exact final5 Compose pair is healthy. The parser has network mode `none`, a
read-only root, UID/GID `1000:1000`, all capabilities dropped, no-new-privileges,
32 PIDs, 512 MiB, one CPU, and the private noexec `/work` tmpfs; Core is read-only
and mounts the parser socket read-only. A real socket scenario preserves 31
segments/30 separators, 12 detections across nine types, protected digest
`4e402d73c75b8699706690b7b4cb4a1c2e789d97c32daae1de4eb0999ab5d03f`,
the classification prompt revision, 3,962 request bytes, and all published caps.
A bounded parser/Core log scan found zero fictional email/phone, source-prefix,
ticket, or synthetic-secret markers. Independent review then found that the
transport used HTTPX decoded `iter_bytes()`, so a compressed response could
allocate beyond the wire cap before rejection, and that the default résumé had
no durable semantic-structure gate. Current source now requests identity
encoding, rejects every non-identity response before iteration, caps raw
`iter_raw()` bytes, and adds a protected opt-in default-scenario gate that checks
reviewed role counts, fixed heading order, provenance, and exactly-once segment
coverage without emitting source or provider content. The final5 pair is
therefore superseded evidence.

The final6 replacement is parser image
`sha256:2e9244ee0eb465313a414274d53418525c1e6d7387e6d9f55b1270345791a91c`
and Core image
`sha256:21792b0e05d161907000e4c5cc8b7e8f655953d8efd62aef8f3fab8e8ea1255b`,
both labelled `stage3-final6-local-contract`. Exact image evidence passes parser
`16/16`, lifecycle `3/3`, Unix-socket integration `4/4`, parser-to-protector
scenario `1/1`, parity `3/3`, document preview `7/7`, and artifact/transport
`7/7`; the full native check surface passes `20/20`. The transport test now
proves that a gzip response is rejected before any raw-body iteration and that
the request asks for identity encoding. Live calls from the exact Core image
passed the Thai-plus-Token 32-segment/9,120-byte boundary in `6,040 ms` with a
1,589-byte response and the 8,000-code-point boundary in `1,169 ms` with an
8,126-byte request and 65-byte response. The exact default résumé then passed the
protected semantic gate in `5,702 ms`: all 31 source segments were rendered
exactly once under seven fixed sections in fixed order, with role counts
`identity:3`, `contact:6`, `experience:8`, `education:3`, `skills:4`,
`achievements:5`, and `other:2`; provenance and structural validation were
present. This evidence records only fixed roles/counts and never source text or
provider-authored content. The healthy final6 Compose pair uses those exact
digests, preserves the parser isolation/resource contract and read-only Core
socket mount, returns one page/31 segments/30 separators for the pinned scenario,
leaves parser `/work` and Core `/tmp` empty, and has zero bounded sensitive-marker
log hits. Stage 3's local implementation/test gate is passed again; independent
final art/product, frontend/security, and UX/lifecycle reviews each report a
clear pass on the exact final6 digests. Stage 3 is complete. There is still no
public route, version bump, deployed parser, browser UI, or production Hosted
3.0 evidence.

Work:

- add the isolated `pdf-parser` image/socket protocol and exact qpdf/pikepdf/
  PDFium/pdfplumber dependency locks, license evidence, seccomp/resource/network-
  none/read-only/tmpfs controls, bounded one-job admission, stream limits, parser
  timeout, cleanup, and crash recovery;
- implement deterministic PDF inspection, text-layer/raster/active-content gates,
  extraction/segmentation manifest, protected text and receipt identifiers;
- implement uploaded and synthetic document ticket branches, provider-free
  preview DTO, post-processing timing floor, safe AST/Markdown renderer,
  portable provenance headers, and no-restoration/document-execute validation
  seam;
- retain proxy-level fixed 404 for `/redact-pdf`, `/v1/redact-pdf`, OCR, image,
  Vision, audio, and scanned/image-only routes.

Exit gate:

- adversarial fixtures cover malformed/compressed/nested/action/encrypted/
  attachment/form/XFA/image-overlay/cycle/bomb/password/scanned documents and all
  exact size/page/dimension/text/raster/segment boundaries without parser escape,
  secret access, egress, or unbounded memory/process growth;
- Core checks authority/review time/capacity before consuming bytes, cleans every
  normal/error/disconnect/timeout/crash spool reference, and never logs or
  returns source bytes/hash/text/mapping;
- valid fixtures preserve each immutable segment exactly once through the safe
  structured artifact and carry required warning/provenance fields in UI-ready
  DTO, Markdown, text, and JSON receipt;
- both measured 32-segment provider boundaries fit with exact source coverage and
  no truncation: 8,000 code points at the code-point edge, and a representative
  Thai-plus-Token payload at the exact 9,120-byte encoded-request edge.

#### Stage 4 — Fair provider scheduler and execute integration

Current Stage 4 execution is split into three reviewable gates so queue state
cannot be attached to provider calls before its atomic/privacy properties pass:

1. **Stage 4A — content-free scheduler foundation.** Add the strict AEAD queue
   capability and claim token, bounded 12-record active queue, two identical
   slots, exact `Priority, Priority, Priority, Standard` claim-grant sequence,
   per-authority ownership, deadline pruning, first-miss tail demotion,
   second-miss expiry, read-only status, cancel/running truth, and value-free
   snapshots. This gate is provider-free and has no public route.
2. **Stage 4B — execute and compatibility integration.** Bind queue join to
   atomic approval consumption, attach custom/synthetic/document execute only to
   a matching one-use claim, enforce source/digest reconstruction and existing
   provider retry/integrity behavior, and place legacy Priority `/roundtrip`
   behind the same two slots with its five-second compatibility deadline.
3. **Stage 4C — image/concurrency/reviewer closeout.** Prove the complete state
   machine under threads, slow/disconnected claims, both-slot contention,
   restart, cleanup, retry, and exact source-image parity; rerun the full native
   surface and independent review before Stage 5 may expose routes. **Stage 4C
   began on 2026-08-17 and is complete under the local/synthetic closeout below.** The owner authorized one consolidated,
   independent GPT-5.6 Sol reviewer at xhigh reasoning effort for this narrow,
   non-UI local closeout only, to conserve quota. This exception replaces the
   usual three-reviewer requirement for Stage 4C only; it does not alter the
   required three independent reviews for the future Stage 6 production UI.

Stage 4B is itself executed as three bounded gates. **4B1** adds only the
internal queue HTTP controller and disconnect-safe claim transport; Nginx must
continue to deny every planned route. It passes only when exact methods, query/
body/header schemas, no-store response DTOs, fixed value-free errors, read-only
status, one active poll, and disconnect eligibility removal pass without changing
the 2.5.0/16-route public surface. **4B2** adds custom, synthetic-document, and
uploaded-document execute services. Each must atomically consume a current queue
claim, reproduce and digest-check the exact protected payload, rerun the outbound
gate before every bounded provider attempt, validate/restore or render only the
approved result shape, clear sensitive facts, and prove zero provider contact on
every mismatch. **4B3** adds the internal five-second Priority legacy
`/roundtrip` compatibility adapter to the same slots and proves byte-for-contract
success/error behavior. Each subgate requires its focused tests, the full native
surface, truthful docs/status, and fresh independent art/product,
frontend/security, and UX/lifecycle review before the next begins.

Stage 4A may change only the bounded `core/aift_hosted3/` overlay, its dedicated
`tests/hosted3_provider_queue_contract.py`, check-only CI/test wiring, the Hosted
3 fixture marker, this document, and `STATE.md`. It must not modify manifest-
pinned `core/app/**` or `core/pii_redactor/**`, Nginx, production web assets,
Compose topology, `core/VERSION`, deploy/acceptance/ops jobs, or the public
16-route surface.

Stage 4A local implementation/test status on 2026-08-16: the bounded overlay now
contains an unexposed, provider-free `ProviderQueue` foundation and the approval
engine's strict four-branch inspect/consume seam. Queue capabilities and claim
tokens are independently derived AES-GCM envelopes bound to process boot,
authority, session/subject, queue/capability JTI, deadlines, slot, and revision.
The single-lock state machine holds at most 12 active content-free records (eight
Standard, four Priority), owns two identical slots, applies the exact global
`Priority, Priority, Priority, Standard` claim-grant opportunity sequence while
both classes are eligible, borrows both slots when one class is empty, and keeps
Priority ownership per issued opaque subject while status/claim/cancel remain
bound to the exact verified session. It records only hashes, class, state,
timestamps, fairness age, miss/provider-attempt counts, and slot metadata; the
full approval remains encrypted in the caller-held capability, is decrypted only
transiently during strict join/claim/execute validation, and is cleared from the
claim path before it waits. An active long-poll retains only opaque capability
JTI, scope, session nonce, and nullable subject binding. After the atomic execute
transition, approval facts exist only in the explicit repr-suppressed
`QueueExecution`, whose cleanup clears them. Status is strictly read-only. Join
consumes approval only after owner/deadline/capacity
checks; cancellation and terminal transitions invalidate the old capability;
first claim miss moves to the class queue tail, second miss expires, and one
claim has exactly one atomic executor. Direct internal dispatch declines to issue
a claim unless the complete 15-second handoff fits before the queue deadline;
the HTTP controller instead requires at least 20 seconds of server-side grant-to-
execute validity, conservatively rounding its integer epoch deadline upward by
less than one second. It budgets at most five seconds for its response and at
least 15 seconds of remaining server-side validity for the official client's
immediate execute acknowledgement. A selected response therefore carries one
truthful absolute deadline. An already-active
authenticated long-poll that crosses the deadline returns fixed `queue_expired`;
it does not collapse ordinary expiry into an invalid-capability error.

The focused Stage 4A contract passes `15/15`, including all four approval ticket
branches, cross-authority/boot rejection, per-session/per-issued-subject
ownership, 16-thread duplicate join, 16-thread one-winner execute, exact two-slot
3:1 contention, one-class slot borrowing, read-only status, deadline pruning,
first-miss tail order, second-miss expiry, claim-ready cancellation/slot release,
provider-failure state, bounded attempt count, capability invalidation, and
sensitive-fact cleanup and minimal active-poll memory. Bounded terminal-history
eviction also proves completed
rows cannot create a false active-queue saturation while active rows are never
evicted; exact `15/14`-second deadline fixtures prove a claim receives its full
handoff window or is not issued, and a blocked-slot foreground poll crossing the
deadline returns `queue_expired` while status reports `expired` /
`deadline_expired`. Approval remains `16/16`; the expanded check-only CI
surface includes this test and the complete native command surface passes
`21/21`. At the Stage 4A closeout, `core/VERSION` remained `2.5.0`, Nginx had
exactly 16 public routes and denied all 24 planned additions, and no queue HTTP
handler, provider call, legacy admission change, browser UI, image rebuild,
version bump, or deployment was claimed. The Stage 4A implementation/test gate
and fresh `21/21` native rerun
passed. Independent art/product, frontend/security, and UX/lifecycle reviewers
each report a clear pass on the exact current bytes after the minimal-poll and
deadline fixes. Stage 4A is complete; Stage 4B execute/compatibility integration
is now in progress and remains internally unexposed.

Stage 4B1 internal implementation status on 2026-08-16: the bounded overlay now
owns exact, still-unexposed Core handlers for `POST /api/provider-queue/join`,
`GET /api/provider-queue/status`, `POST /api/provider-queue/claim`, and
`POST /api/provider-queue/cancel`. The preview-only 1,030-second admission fence
does not incorrectly reject queue operations; queue join retains its independent
900-second requirement. Every route requires one verified authority, exact HTTP
contract header and Core key, no query, an exact method and body schema, bounded
declared bytes, duplicate-key rejection, and no-store timing/class metadata.
Status consumes an exact empty request and is read-only. Cancel returns an empty
`204`. Claim runs the synchronous scheduler poll outside the event loop and races
it against the ASGI disconnect signal only while the claim poll is unresolved.
An observed disconnect sets a thread-safe cancellation event, wakes the scheduler
condition, waits for cleanup, removes eligibility, and serializes no response.
Once the poll returns, the watcher is cancelled before response transmission;
pinned Uvicorn emits `http.disconnect` after an ordinary completed response, so
that sentinel cannot be used as proof of peer loss. The response transport is
bounded to five seconds. An explicit send exception, timeout, or controller
cancellation atomically abandons the exact pending claim, invalidates its token,
releases the slot, and retains the original fairness age with zero misses. A
connected no-slot timeout returns ordinary queued state and creates no claim.

A selected HTTP grant carries one absolute integer deadline rounded upward from
grant-time-plus-20-seconds and keeps an execute acknowledgement pending. The
official client's exact queue-bound execute
request is the only delivery acknowledgement and atomically begins provider work.
There is no post-send confirmation method and no user action is timed. If no
execute arrives before expiry, the scheduler makes no provider call and applies
the normal first-miss tail demotion or second-miss expiry. This also bounds a
Uvicorn-style silent transport loss that ASGI cannot distinguish from successful
response completion. Partial-body disconnect, invalid-capability completion,
outer-task cancellation, response-send failure, and non-claim transport failure
remain non-serializing cleanup paths. The zero-miss cleanup path authenticates
the exact capability, claim, authority, JTI, revision, and slot; expired claims
remain invalid for execute. Fixed approval/queue failures use the value-free v2
envelope.

The focused HTTP contract currently passes `17/17` and the scheduler contract
passes `20/20`. Exact fixtures cover direct 15-second claims, fractional `.999`
HTTP grants with at least 20 seconds of aligned record/token/wire validity, the
full five-second response budget leaving at least 15 seconds of server-side
validity for the immediate grant-to-execute acknowledgement, first/second misses
without provider contact,
explicit send failure/timeout cleanup, connected queued timeout, silent transport
loss, and pinned Uvicorn's normal post-response disconnect sentinel without
revoking a valid claim. At the B1 closeout, check-only CI carried the HTTP
contract as the 22nd native
command. The earlier `22/22` native runs predate this execute-as-acknowledgement
and fractional-deadline revision and are historical. The fresh exact-current
native surface passes `22/22`; independent art/product, frontend/security, and
UX/lifecycle re-reviews each report a clear pass. Stage 4B1 is complete. At that
closeout this was local source evidence only: Nginx denied all 24 planned
canonical/alias paths and no execute service existed.

Review history is retained because it materially changed the protocol. Earlier
iterations first cancelled the disconnect watcher too early and could treat a
silent transport loss as delivery, then kept it through response completion and
misread Uvicorn's normal post-response sentinel as failure. Both approaches and
their prior passing mock suites are superseded. Execute-as-acknowledgement avoids
claiming that ASGI proves browser receipt while still guaranteeing zero provider
contact without the exact follow-up request.

Stage 4B2 local implementation status on 2026-08-16: the port-owned overlay now
contains a first internal `ExecuteService` and exact, still-Nginx-denied handlers
for `POST /api/guest/execute`, `POST /api/protection-execute`, and
`POST /api/document-execute`. Each request is strict JSON with one declared
bounded body, duplicate-key rejection, no query, contract/key/authority checks,
and no-store timing/class metadata. An exact queue capability plus current claim
must atomically enter `running` before any provider contact. Custom text is
reconstructed from the approval salt/generation seed, source and protected
digests are compared, the outbound gate runs before every bounded retry, and the
validated provider response is restored only through the transient mapping.
Synthetic documents reparse the pinned scenario and reproduce every parser,
manifest, protection, registry, and digest fact. Uploaded documents accept only
the exact protected text already bound to the consumed approval. Both document
branches send only immutable protected segments to the bounded document provider
transport, validate the content-free classification AST, render fixed escaped
Protected Markdown/plain text, and never restore PII.

Success responses and receipts are explicitly shaped. Receipts and both
document responses exclude source PDF bytes, original extracted text, raw
source digests, mappings, original/token pairs, provider bodies, authorities,
queue capabilities, and claim tokens. The custom-text response intentionally
returns the reviewed protected text, masked provider answer, and restored answer;
that restored answer may contain the caller's original PII. It never returns an
explicit mapping object, and the restoration mapping remains transient only.
Failure completion records only one fixed value-free queue reason; source/digest,
kind/class/session, stale-claim, outbound-gate, parser, structure, provider, and
restoration failures release the slot and retain no decrypted approval. The
first reviewed `7bf5f768...` image and its `7/7` focused evidence are now
superseded: review found that its synthetic-document provider call blocked the
ASGI event loop, and an unrelated late document-response failure could be
misclassified as `residual_pii`. Current source offloads the complete synthetic
parse/provider/artifact path from the ASGI loop, locks responsiveness with a
slow-provider heartbeat fixture, scopes `residual_pii` to the outbound gate,
and reports unrelated late failures as `internal_error`. The focused B2 source
then replaced the inherited post-buffer-only custom provider adapter with a
killable child transport. Each custom attempt has a parent-owned 60-second
absolute deadline; the worker requests identity encoding, rejects any other
content encoding, caps declared and streamed raw response bytes before JSON
parsing, then enforces the 32,000-code-point/96-KiB content cap. Retryable fixed
failures retain the approved maximum of three attempts plus bounded backoff, so
the complete custom envelope remains below 200 seconds. Content-length, chunked
overflow, compression, oversized decoded content, child-timeout/reap, three-
attempt retry, and non-retryable-response fixtures are executable. Preview now
enforces the matching 96-KiB protected-payload cap before minting a ticket and
returns fixed `422 provider_payload_too_large`, so a valid approval is never
consumed by an execution-only size rule; 20,000 four-byte source code points
remain valid when their protected result fits that cap. Provider construction is
separate from response parsing, and malformed operator URL/header configuration
maps to `provider_configuration` rather than `provider_response_invalid`. The focused
B2 source contract now passes `9/9`, covering custom restoration,
provider-attempt rescans, uploaded and synthetic no-restoration artifacts, exact
internal route transport, stale/schema/source/digest failures, fixed provider/
restore/structure/parser failures, and zero provider contact on every mismatch.
Check-only CI now includes this as the 23rd native command. The superseded local
Core image previously resolved to manifest-list digest
`sha256:7bf5f768b5bf948f6cace65934b05241e755b6546c6c7a4d910602c1f988e83f`
with revision label `stage4b2-final2-local-contract`; it predates the current
event-loop and failure-classification fixes and is not closeout evidence. Its
historical exact Core/parser source-image parity passed `3/3`, focused execute
contract `7/7`, and real-detector image probe `1/1`, proving that earlier image's
provider-free preview → queue → execute reproduced the same protected bytes,
sent the fake provider no original name/email/phone, and restored the synthetic
custom-text test fixture exactly. That probe validates
the custom-text restoration branch; it is not evidence of PII restoration in
the synthetic-document/PDF branch, which intentionally never restores PII.

The exact current replacement image `aiguard-stage4b2-core:local` resolves to
manifest-list digest
`sha256:cee123fe5ad397079d23ed1d78e9c1c8fcec574e39e2e22043259443db813d4c`
with revision label `stage4b2-final3-local-contract`. Against the exact Stage-3
parser image `sha256:2e9244ee0eb465313a414274d53418525c1e6d7387e6d9f55b1270345791a91c`
labelled `stage3-final6-local-contract`, source-image parity passes `3/3`.
The focused execute suite passes `9/9` inside the read-only, networkless
replacement Core image, the real-detector custom-text preview → queue → execute
probe passes `1/1`, and an in-image invalid-operator-configuration probe returns
only `provider_configuration`. An initial parity attempt against the older
`aiguard-pdf-parser-stage3:local` tag correctly failed and is not counted; using
the exact Stage-3 closeout image fixed the evidence binding. The fresh exact-
current native surface passes `23/23`. Independent art/product, frontend/
security, and UX/lifecycle reviewers each rechecked the exact replacement image,
source, and durable status and report a clear pass with no material disagreement.
Stage 4B2 is complete. At its closeout, Nginx still denied all 24 planned
paths and there was no public execute route, browser UI, legacy admission
change, version bump, production image, or deployment. Stage 4B3 legacy
`/roundtrip` queue admission is complete; Stage 4C has not started.

Stage 4B3 source now installs a port-owned compatibility wrapper around the
existing vendored FastAPI `/api/roundtrip` handler without editing
`core/app/**`. `AuthGateway` remains the outer authority boundary; the Hosted 3
overlay binds its immutable Priority authority into the framework's copied
thread context, and the existing synchronous endpoint is invoked only after an
internal Priority entry wins one of the same two provider slots. The wrapper
raises the vendored fixed `ContractError("rate_limited")` after a five-second
wait, so FastAPI retains the existing error DTO, contract header, CORS, request
validation, and success response contract. The slot is held for the complete
legacy endpoint call and released in `finally` on success or failure. The
scheduler entry contains only hashed authority bindings, service class,
deadlines, state, revision, and slot; it creates no caller capability, approval,
request-body copy, or new public route. It participates in the same atomic 3:1
grant cursor, total/class capacities, one-active-owner rule, slot borrowing, and
terminal pruning as new execute traffic. The focused source contract now passes
`12/12`, including two-slot timeout, same-subject owner rejection across
distinct sessions, cancellation cleanup, semantic validation before admission,
shared Priority-versus-Standard
selection, content-free records, vendored error-code selection, exact endpoint
result passthrough, and unconditional slot release. The exact current local Core
image `aiguard-stage4b3-core:local` additionally passes `2/2`
read-only/networkless checks: every copied port-owned runtime byte matches
source and the copied FastAPI `/api/roundtrip` route preserves the legacy DTO
and contract header, retains same-origin CORS behavior (no permissive header),
returns fixed `429 rate_limited` only after the five-second slot wait with zero
provider contact, validates malformed input before admission, releases after a
provider error or response-send failure, and retains the running slot through
observed post-body disconnect and outer-request cancellation until synthetic
provider work ends; its stdout assertion also proves the synthetic legacy
request text does not enter the Core audit log. The independent backend/product/
security review then found that endpoint-body semantic validation was behind
admission: with both slots occupied, empty/whitespace/oversized text and invalid
mode/provider could have become delayed `429 rate_limited` responses. The
port-owned adapter now invokes the exact vendored text validator and repeats the
endpoint's mode/provider membership checks in order before a scheduler record is
created. The exact-image probe reproduces every case under occupied slots,
proves the immediate legacy `400 invalid_request` or `413 payload_too_large`,
and asserts no queue mutation or provider contact. The rebuilt local image
resolves to manifest-list digest
`sha256:706051f7d132d3ee18c4d7abc3e1b517ceec002fe8983d8bcf279ab4914fffdc`
with revision label `stage4b3-final2-local-contract`; its `2/2` image/parity
probe passes. The earlier `stage4b3-final1-local-contract` image and native
run are superseded. The fresh Docker-executor-style native rerun passes all
`24/24` commands, including built Nginx/public-surface, static and runtime
secret/log, build-context, route-count, and Compose-isolation checks. The native
simulator now faithfully honors the check job's AES-GCM-specific
`before_script`, with a focused GitLab-contract regression locking that
behavior. The same independent GPT-5.6 Sol backend/product/security reviewer
reconciled the fix,
verified immediate held-slot semantic errors with no scheduler/provider work,
and reports no material Stage 4B3 blockers. Stage 4B3 is complete. This is
local evidence only: production remains Hosted 2.5.0 on the previous deployed
image, Nginx exposes exactly the existing 16 routes, and Stage 4C has not
started.

Stage 4C candidate evidence on 2026-08-17 is local and synthetic, pending the
single owner-authorized consolidated review. The new deterministic
`tests/hosted3_stage4c_closeout_contract.py` runs the four actual Stage 4
behaviour contracts in isolated processes rather than performing source-string
checks: scheduler/authority/replay/deadline/cleanup (`21` tests), HTTP claim
acknowledgement/disconnect/partial-send (`17`), custom/document execution and
provider bounds (`9`), and Priority legacy shared-slot/validation (`12`). Its
aggregate passes `4/4` (59 underlying behaviour tests) on the source tree and
again with the overlay imported from the exact candidate image under read-only,
no-network, cap-dropped execution. The candidate Core is
`sha256:2582ecba14300dd816a7b788f562d6c70325a3098bffd8adaa57a86d6bd6b1eb`,
revision `stage4c-final-local-contract`, created
`2026-08-16T17:43:44.421095077Z`; it is a new tag/digest and does not relabel
the B3 image. It passed complete source-to-image Core overlay/auth/gateway
parity plus the exact approved parser's minimal-source parity (`3/3`), legacy
FastAPI/slot integration (`2/2`), and a real-detector custom preview→queue→
execute fake-provider probe (`1/1`) inside the candidate. The parser remains
the approved Stage 3 image
`sha256:2e9244ee0eb465313a414274d53418525c1e6d7387e6d9f55b1270345791a91c`,
revision `stage3-final6-local-contract`; no parser rebuild was required. An
explicit image file listing found only the Dockerfile's allowlisted runtime
paths under `/app`, with no copied test/evaluation/cache artifact. The complete
current pinned Docker-executor-style check command surface passes `25/25` in
54.6 seconds, including built Nginx/public-route (`16` exposed; all 24 planned
Hosted 3 paths denied), Compose isolation, source/build context, and value-free
secret/log contracts. `git diff --check` passes. This is still in-progress local
evidence: it is not a production image, deployment, Stage 5 route exposure, UI
change, or version bump.

The consolidated reviewer found one material verification gap, corrected before
closeout: the former queue contract had no same-entry simultaneous
cancel-versus-execute race, and its 3:1 contention fixture used a fixed sleep
without proving both classes were eligible at selection. `ProviderQueue` now
reports a valid, correctly bound capability invalidated by cancellation as the
truthful `queue_not_ready` execute state rather than generic `queue_invalid`,
while forged/cross-bound capability behavior remains unchanged. The new
16-round barrier-backed race accepts only cancellation with no slot/provider
authority or exactly one running execution with cancellation rejected as
`provider_already_running`; it clears the winning execution in every case. The
grant fixture now waits on the bounded internal eligibility seam before release.
The focused scheduler contract passes `21/21`, the Stage 4C aggregate covers
59 underlying behaviours, the exact candidate was rebuilt, all exact-image
gates reran, and the final current Docker-executor-style surface reran `25/25`
in 54.6 seconds. The focused re-review by the same independent reviewer is
recorded immediately below.

Stage 4C final closeout: the single owner-authorized independent reviewer was
GPT-5.6 Sol at xhigh reasoning effort and made no file edits. Its consolidated
backend/security/product-integrity, lifecycle/UX-truth, and product/status-truth
review identified the two test-verification issues above, verified their fixes,
then independently reproduced candidate
`sha256:2582ecba14300dd816a7b788f562d6c70325a3098bffd8adaa57a86d6bd6b1eb`,
revision `stage4c-final-local-contract`, the scheduler `21/21`, exact-image
Stage 4C aggregate `4/4` / 59 underlying behaviours, source-image parity
`3/3`, and `git diff --check`. Its final verdict is **no material blocker**.
The final Docker-executor-style CI-equivalent result remains `25/25` in 54.6
seconds; legacy FastAPI integration remains `2/2`; and the in-image real-
detector fake-provider custom execution probe remains `1/1`. Candidate Core
and the unchanged approved parser are local only; all provider evidence for
this closeout uses safe fake fixtures except the in-image detector processing
of synthetic text. Production remains Hosted `2.5.0` with exactly 16 routes,
and Nginx denies every one of the 24 planned Hosted 3 paths. No Stage 5 route
exposure, UI work, version bump, production image, deployment, or public
exposure occurred. **Stage 4C is complete. Stage 5 is the next safe stage and
has not started.**

Work:

- implement the single-process, two-slot, content-free queue state machine,
  bounded Standard/Priority capacities, atomic 3:1 claim-grant sequence, idle
  borrowing, deadlines, foreground claim long-poll, two-miss demotion/expiry,
  cancellation, restart, and status-only recovery;
- bind approval consumption to queue join and AEAD queue/claim capabilities;
  connect custom, synthetic, and uploaded-document execute services only after a
  matching `claim_ready → running` transition;
- admit legacy Priority-only `/roundtrip` through the same scheduler with its
  compatibility-preserving five-second deadline;
- keep provider attempts, fresh outbound scans, response caps, restoration/
  document-integrity validation, log minimization, and one-unresolved-request
  truth exact.

Exit gate:

- concurrency tests prove bounded work conservation, exact grant sequence,
  no Standard selection starvation, both-slot borrowing, no preemption, one
  active entry per authority, deadline pruning, replay rejection, and atomic
  state under duplicate tabs/calls;
- slow/disconnected/background clients can waste at most two HTTP claim-to-
  execute acknowledgement opportunities of less than 21 seconds each,
  never retain oldest age, and never cause provider contact without matching
  approval+queue+claim authority;
- refresh is status-only, records contain no content/capability/raw identity,
  restart and cancellation have truthful terminal states, and legacy roundtrip
  cannot bypass global slots;
- fake-provider tests cover success, up to three same-provider attempts, every
  fixed failure, unresolved-upstream truth, result integrity, and log privacy.

#### Stage 5 — Exact API proxy, Docker, Compose, and security wiring

Stage 5 status: **complete, local only**. `core/VERSION` remains `2.5.0`;
the deployed service remains the reviewed Hosted 2.5.0, 16-location boundary.
The Stage 5 source candidate may expose all 40 approved locations only through
its local API proxy. No caller UI, public copy, version label, production image,
deployment, public acceptance, or Stage 6 work is authorized by this stage.

Stage 5 rate ownership is deliberately split and tested. Nginx owns exact path
selection, request-size ceilings, duplicate-cookie rejection, anonymous/global
transport ceilings, document's `4/min` global plus one-global-connection lane,
and non-authoritative per-cookie transport fences. Core owns every published
verified session/per-issued-Priority-Invite bucket (including the fixed
provider-free, document, status, claim, cancel, and execute values),
active-session capacity, parser admission, one-active-queue-record state,
document busy/unavailable truth, queue capacity, claim lifecycle, and the
Standard idle-borrow exception. Nginx keys are not identity or quota proof;
Core uses only one-way owner digests and shares a Priority Invite subject across
separately minted sessions. No Nginx rule may mint an authority, queue, claim,
timing header, or provider/parser work. New route-level Nginx 413/429 responses
are fixed, value-free, `no-store`, and have no Core timing header. Core-originated
responses retain their Core-authored timing/service-class headers unchanged. The
PDF preview aliases alone use the 5 MiB ceiling and disabled request buffering;
all other new JSON routes are bounded at 8 KiB, 12 KiB, or 96 KiB according to
their exact DTO class.

Work:

- add the 12 canonical operations and exact `/v1` aliases to Core and Nginx,
  growing the public contract from 16 to exactly 40 locations without prefix or
  implicit-version routing;
- add exact Standard/preview/document/queue rate and connection lanes, body and
  timeout policy, Core-key/contract injection, Core-versus-edge error handling,
  no-store/timing-header provenance, and fixed near-match/method denials;
- add the parser image/socket volume/health/resource/security wiring to Docker,
  Compose, CI build/revision checks, rollback capture, and health/restart flow;
- keep CSP same-origin, no tracker/CDN, no client address/target/query/body/cookie
  application logs, and only the approved secret set.

Exit gate:

- static and live Nginx tests enumerate all 40 allowed locations and deny every
  method, query, `/v2`/`/v3`, source/asset/API near-match, PDF-redaction/OCR, and
  internal route; canonical and `/v1` statuses/bodies/headers match;
- rate/capacity tests prove published global and per-authority values including
  headerless early edge errors and no provider/parser work after rejection;
- built images contain only explicit runtime files/dependencies, exact revision
  labels, no secret/test/evaluation artifact, no OCR model/runtime, and all four
  services pass health, resource, read-only, no-new-privileges, network, stop,
  restart, and cleanup assertions;
- Stage 0–4 tests plus GitLab-equivalent check pass from the built images.

Final local Stage 5 evidence: the fresh exact revision is
`stage5-final-local-contract-r3`, with web
`sha256:69b7129b0589df1f190767dd1f8b7247fcf6212dfb065e6c35aea1d14a3749f0`,
API `sha256:e2a03cf7069b9fc8cb4be5c613df14d7d8e5e3ba9f8606dd0ade2ca43d20f2ab`,
Core `sha256:2d03c7191b247bbb4c75d2c47728fc0c022881877e9acfc0a1bf6a912ad842a8`,
and parser `sha256:98f46c99744fa9184fe17c3618944d9a28cf42727b810ac0bff51033b90f3cc2`.
Their creation times are respectively `2026-08-16T18:46:38.195506729Z`,
`2026-08-16T18:46:36.355848559Z`, `2026-08-16T18:47:33.200293594Z`, and
`2026-08-16T18:46:52.053046898Z`.
All four were healthy and revision-aligned in the isolated synthetic stack.
The Stage 5/static, authority, rate, queue, built-Nginx, Compose, release,
secret, and deployed-boundary contracts passed; exact Core/Parser parity was
`3/3`, legacy image integration `2/2`, parser lifecycle `3/3`, and the fresh
pinned Docker-executor-style CI-equivalent check ran all `27` commands with
exit `0`. The
single GPT-5.6 Sol/xhigh adversarial review and focused r3 re-review reported
no material disagreement. This evidence is local and synthetic only: it does
not alter the deployed 16-route Hosted 2.5.0 service or authorize Stage 6.

#### Stage 6 — Production App and reference-page integration

Stage 6 status: **complete, local only**. The Stage 5 image baseline was
rechecked on 2026-08-17: local `aiguardstage5-web`, `aiguardstage5-api`,
`aiguardstage5-core`, and `aiguardstage5-pdf-parser` resolve to the four
documented final-r3 digests. Source contracts still enumerate the candidate's
40 exact API locations, while a read-only public probe found Hosted `2.5.0`
at `/api/health` and fixed `404` for the not-yet-deployed Standard-start path.
This stage is limited to the local caller-facing candidate. It does not change
`core/VERSION`, deploy, expose a public 40-route service, or make a Hosted 3.0
release claim.

Checkpoint, 2026-08-17: the local-only caller now runs through a loopback TLS
edge at `https://127.0.0.1:20270`. `web/nginx.stage6-edge.conf` maps the
same-origin candidate `/api/` prefix to the existing exact API allowlist, while
`docker-compose.stage6-local.yml` keeps that edge and its Core origin local.
In Chromium, synthetic Standard start returned 201, session confirmation
returned 200 with all required timing headers, and protected custom-text preview
completed. Its generated self-signed certificate is ignored evidence only, not
production TLS evidence. The current source slice is `web/app.html`,
`web/app.css`, `web/hosted3-app.js`, `web/developers.html`, plus the exact
Docker/Nginx assets and local edge overlay.

This remains provisional, but the retained-workflow and reference-copy gates
below are now closed: the hidden legacy DOM and served `/app.js` dependency are
removed, the active three-task App owns every required workflow/evidence feature,
and executable behavior tests cover all seven deep links plus custom/PDF request
ordering and clearing. The secure local stack has completed synthetic custom and
real fixture-PDF journeys with a Stage 6-only fake provider. At that checkpoint
the failure/queue/browser matrix, exact images/full CI, and focused re-reviews
were still open; final3 evidence and passes below subsequently close them.
Production remains Hosted 2.5.0 with exactly 16 public routes.

The first exact candidate is superseded by final2 after the frontend reviewer
found that status-only reload recovery could still enter `claimLoop()` without a
capability. Final2 guards claim/resume on a non-status-only queue with a string
capability, keeps recovered mutations locked, and adds a visibility/online
regression with zero claim/execute calls before confirmed Cancel.

Final2 is itself superseded by final3 after UX re-review found that confirmed
status-only Cancel focused a hidden text-preview control. Final3 captures the
status-only/task state before clearing, restores the visible chooser, focuses
`#h3ChooserTitle`, and locks that exact recovery in the executable behavior
contract. No other runtime or visual change follows final3.

Current reviewer-approved exact-candidate evidence:

- revision `stage6-final3-local-contract`; web
  `sha256:f9a3e51d916ebb4ef98a6278315fea0a56c4bbef1ee72d7802b760c3ca504cd8`,
  API `sha256:d688f43abda52fb1f02e1768a0608bb631842a22b40c1d320f28f02752b8ac31`,
  Core `sha256:302a4b6d6777fd19948e6dc9362dc05c90e250ec917275a6e92cd6c35b658790`,
  and parser `sha256:1d6d170a92cab420d8cdb397dfb45be9e1a24416634782c395d7181eb491c3f3`;
- exact Core/parser parity `3/3`, legacy FastAPI image integration `2/2`, and
  parser lifecycle `3/3` pass on those images; source hashes for `app.html`,
  `app.css`, and `hosted3-app.js` equal the running web image byte-for-byte;
- the expanded pinned Docker-executor-style check surface passes `28/28` in
  `218.7 s`; static, zero-dependency behavior, built Nginx, build-context,
  secret, Compose, GitLab, and `git diff --check` gates are green;
- the exact built local caller completed synthetic custom and real fixture PDF
  provider-free preview plus fake-provider queue/claim/execute results. The
  real 390×844 custom Presenter hides the restored result/comparison and restores
  focus on exit. PDF semantic results have zero page/child overflow at 390×844,
  360×800, and 720×365;
- the route/viewport matrix passes `64/64` across Home, App, Developers,
  Privacy, Help, Terms, Downloads, and branded 404 at all eight required
  viewports: no overflow, status, H1, font, image, storage, IndexedDB, Cache API,
  service-worker, or unexpected-console failures. It records exactly eight
  expected signed-out `/api/auth/session` 401 browser resource rows and eight
  deliberate navigation 404 rows under the explicit exception above;
- exact no-JavaScript mobile App retains inert controls, visible recovery, and
  all public routes; reduced motion reports maximum duration `0.00001 s`;
  forced local font/logo failure preserves the visible wordmark and zero
  overflow; local edge logs contain only value-free rows; six-service bounded
  log scan finds zero synthetic/source/capability markers and Core `/tmp` plus
  parser `/work` are empty.

Durable screenshots include
`output/playwright/stage6-final-home-1440x729.png`,
`stage6-final-home-390x844.png`,
`stage6-final-app-signedout-1440x729.png`,
`stage6-final-developers-1440x729.png`,
`stage6-final-developers-390x844.png`,
`stage6-custom-presenter-private-390x844.png`,
`stage6-pdf-result-semantic-390x844.png`,
`stage6-pdf-result-semantic-360x800.png`,
`stage6-final-nojs-menu-390x844.png`, and
`stage6-app-font-logo-fallback-390x844.png`. This is local/self-signed/
fake-provider evidence only, not public or production evidence.

##### Stage 6 retained-workflow parity ledger

| Legacy feature | Required | Active-task owner and fields | Placement / fragment | Behavioral proof | Status |
| --- | --- | --- | --- | --- | --- |
| Guided demo | Yes | Inspect synthetic samples; `/api/detect`, `/api/guard`, `/api/analyze-report` | Inspect secondary disclosure; `#guided-demo` | Scenario selection is non-submitting, then explicit action routes correctly | Complete |
| Five synthetic scenarios | Yes | Inspect `syntheticSamples` | Inspect secondary disclosure; `#synthetic-demo` | Populate only; no request before action | Complete |
| Privacy Scan | Yes | Inspect `/api/detect`: count, type counts, spans | Primary Inspect; `#privacy-scan` | Structured escaped output | Complete |
| Prompt Risk / Guard | Yes | Inspect `/api/guard`: `flagged`, `guard_findings` | Primary Inspect; `#privacy-scan` | Structured escaped output and stale guard | Complete |
| PDPA Report | Yes | Inspect `/api/analyze-report`: score, grade, report base64 | Primary Inspect; `#pdpa-report` | Explicit report download | Complete |
| Sensitive Data Map / Section 26 | Yes | Detect owns a value-free type/count/position map; protected preview/result owns Core-returned `section26_categories` | Inspect and protected-review disclosures | Must render current structured result only and never infer Section 26 client-side | Complete |
| Safe AI provider evidence | Yes | preview protected text, execute receipt | Text result disclosure; `#safe-ai`, `#providerEvidenceCard` | Exact current preview/result only | Complete |
| Raw-versus-protected comparison | Yes | `state.source`, `state.preview.protected_text` | Text result disclosure only | Never portable/exported | Complete |
| Executive summary | Yes | verified custom execute result, safety/restoration gates, and receipt | Text-result evidence disclosure | No unsafe or stale result | Complete |
| Protection Receipt | Yes | execute `receipt` | Text/PDF technical receipt | Reset/logout clears it | Complete |
| Restored-result gate | Yes | execute `restored_text`, integrity/residual gate | Text primary result | No restored DOM on failed gate | Complete |
| Residual / leftover evidence | Yes | execute `safety` and `restoration` objects plus receipt | Text evidence disclosure | Requires exact pass/zero gates before any restored DOM | Complete |
| Token/Surrogate glossary | Yes | selected mode and static definitions | Text evidence disclosure; `#how-it-works` | Mapping opens active task | Complete |
| Timing evidence | Yes | server/session timing anchor | Text evidence disclosure | performance.now-only anchor | Complete |
| PDF extraction / provenance | Yes | protected markdown, omitted pages, parser/extraction receipt | PDF: exactly Protected extraction + Technical receipt | No restoration/export bypass | Complete |
| Service liveness | Yes | `/api/health` liveness only | Inspect evidence disclosure | Never provider-ready claim and never invokes provider | Complete |
| Presenter/fullscreen | Yes | verified synthetic/execute result | Active result action | Private input hidden; focus restored | Complete |

The executable zero-dependency frontend behavior contract now proves every row:
all seven gate-first fragments, five non-submitting scenarios, current Detect/
Guard/report ownership, stale Inspect suppression, preview-before-provider,
queue/claim/execute ordering, custom and PDF output gates, task-aware
disclosures, presenter focus/privacy, artifact provenance, timing failure, and
logout clearing. The hidden legacy wrapper has therefore been deleted from the
production App instead of remaining dead or contradictory runtime weight.

The completed parity source pass adds active, value-free Sensitive Data Map
projection from `/detect`, Core-owned Section 26/Guard projection from protected
preview, a gate-derived custom-text Executive Summary, explicit residual/
leftover/provider-attempt/timing facts, and one liveness-only `/health` check.
The client refuses to render a custom restored result unless safety is `pass`
with zero residuals and restoration is `complete` with zero leftovers; PDF
result validation rejects any `restored_text` field. Presenter fallback also
hides custom raw comparison. The secure built caller independently exercised
Standard access, scenario selection, Detect map, liveness-only evidence, and
protected preview. Full PDF/queue/result lifecycle and the complete viewport/
failure matrix remain separate Stage 6 gates; parity completion does not claim
those later gates passed.

The next lifecycle slice uses a dedicated local-only OpenAI-compatible provider
stub under `tests/stub-tokenmind/`, wired only by
`docker-compose.stage6-local.yml`. It echoes the already-protected custom payload
or returns ordered document segment classifications, has no production
credential, and cannot enter the production Compose or image path. The secure
caller has now completed one synthetic custom preview→queue→claim→execute→
restored-result run and one real fixture PDF upload→parse→preview→queue→claim→
Protected Markdown run through the local 40-route stack. The PDF result initially
rendered raw Markdown in one `<pre>`; browser inspection rejected that as an
insufficient reading surface. The current client instead validates and renders
only a fixed safe subset of provenance quotes, `h2`/`h3` headings, and paragraphs
with `textContent`, rejecting raw HTML, links, images, tables, and code fences.
This remains local/fake-provider lifecycle evidence, not final exact-image or
production evidence.

The first Stage 6 implementation reviews then found material defects that are
now corrected in source and targeted browser/behavior evidence: unconfirmed End
or Cancel no longer claims success or discards the surviving authority/queue;
Inspect `401` clears raw state and returns to the access gate; lost Standard/
Priority mutation responses are reconciled through a fresh session sample;
queued and provider-running work locks task/input/back/end mutations; uncertain
execute transport exposes only truthful may-still-run/Clear-page recovery with
no Retry; portable receipt JSON now wraps the value-free server receipt in the
mandatory artifact/provenance warnings; custom Presenter hides both raw
comparison and restored result; result headings are task-specific and focused;
the page H1 remains visible across authority states; the no-JavaScript mobile
menu includes every public route; duplicated live regions were removed; and the
local TLS edge now emits only value-free surface/status/bytes/method/duration
logs. A real 390×844 PDF result went from 150 px overflow to zero and now renders
32 paragraphs plus nine semantic headings without child overflow. The App CSS
was mechanically reduced from roughly 70 KiB/570 lines of legacy dashboard
rules to about 15 KiB/51 active Stage 6 lines.

One browser-console event is explicitly expected and allowlisted for a fresh
signed-out App load: the byte-compatible, HttpOnly-cookie-aware
`GET /api/auth/session` contract returns `401 authentication_required`, which
Chromium records as a failed resource even though the client handles it and
shows the access gate. This cannot be changed to `200` in Stage 6 without
breaking the locked authentication contract. Final evidence permits exactly
that URL/status once in a signed-out bootstrap (and the deliberate navigation
404 when testing the branded 404); any uncaught JavaScript error, CSP violation,
other failed resource, or authenticated-session 401 remains a blocker.

Implementation map and checklist:

- [x] Audit the existing web caller path: `web/app.html`, `app.css`, `hosted3-app.js`,
  shared reference markup/style, Docker COPY, exact Nginx allowlist/CSP,
  sitemap/robots, and current route/source/build/public contracts.
- [x] Replace the `/app` access and workflow surface with the approved
  Standard/Priority, three-task, memory-only state model. Retained workflows,
  deep links, task-aware evidence, custom/PDF results, and lifecycle states are
  owned by the active App; hidden legacy DOM and served `/app.js` are removed.
- [x] Add the static-first `/developers` route through HTML, Docker, exact
  Nginx, sitemap, navigation/footer, and source/runtime contracts. The page now
  records the exact starting class/global control rates, deterministic error/
  retry truth, liveness-only boundary, and same-origin/no-public-credential
  scope without JavaScript.
- [x] Update the six-scene Home and bounded reference-page copy without a
  version migration, extra modality, or new page class. Source contracts now
  distinguish deployed Hosted 2.5.0/16 routes from the local candidate,
  Standard/Priority access, text-layer PDF→Protected Markdown, and continuing
  PDF-redaction/OCR denial without a seventh Home scene.
- [x] Add executable client contracts for authority, timing, queue, stale
  response, no-persistence, artifact, and safe-rendering behavior. Static and
  zero-dependency behavioral contracts run in the pinned check job and cover
  the defining request/state/failure order.
- [x] Verify the built four-service local caller path and all required browser,
  keyboard, reduced-motion, no-JS, failure, and responsive evidence. Exact
  final3 passes the 64-check matrix plus custom/PDF, Presenter, fallback,
  storage, log, and cleanup evidence above.
- [x] Obtain the required independent art-direction, frontend/security, and
  UX/accessibility reviews; verify and resolve material findings. All three
  focused re-reviews bind clear passes to exact final3 with no material
  disagreement.

Stage 6 final closeout: art direction, frontend/product/security, and UX/
accessibility independently verified all four exact final3 digests and revision
`stage6-final3-local-contract`. Art rechecked the semantic PDF hierarchy,
wrapping, task titles, H1, Terms, and Concept C composition. Frontend/security
rechecked source/image parity, auth/queue/uncertain transport/cancel/status-only
lifecycle, portable receipt, local-edge logs, exact assets/near matches, and
public 2.5/16 truth. UX rechecked status-only Cancel focus, zero claim/execute on
visibility/online, Presenter privacy, custom/PDF focus, no-JS routes, single live
region, and the signed-out 401 exception. Each issued a final **PASS** with no
material disagreement. Stage 6 is complete locally; this does not authorize
Stage 7, a version claim, production deployment, or public acceptance.

Work:

- replace the invite-only first fold with the approved compact Standard/Priority
  entry and one three-task chooser; retain current authenticated workflows and
  optional evidence without rebuilding the rejected long dashboard;
- implement text/PDF prepare→preview→approve/join→automatic execute→result states,
  exact protected-payload inspection, queue card, timing anchors,
  `timing_unavailable`, no-JS fail-closed behavior, state clearing, portable
  artifacts, and all deterministic focus/live-region behavior;
- add static-first `/developers`, update the existing six Home scenes and
  Privacy/Help/Terms/Downloads/channel labels within their content budgets, and
  update navigation/footer/sitemap/robots without introducing a new product or
  multimodal teaser;
- add every new static asset through Docker COPY, exact Nginx allowlist, CSP,
  tests, and caller-facing verification.

Exit gate:

- executable frontend contracts prove no provider request before approval and
  scheduler claim, no arbitrary Standard bypass, timing/skew/delay recovery,
  stale-response suppression, authority switch/logout/expiry/reload clearing,
  queue lifecycle, safe Markdown subset, provenance on every copy/download, and
  zero browser persistence;
- real Chromium verifies 1440×729, 1366×768, 1440×900, tablet, 390×844,
  360×800, and 720×365/200%-equivalent reflow with Thai marks, fallback font,
  keyboard, skip/current navigation, focus, live regions, reduced motion,
  no-JS, offline/error states, image/asset failure, no overflow, and no layout
  instability;
- Home preserves the six-scene Concept C first fold, App remains a focused
  workspace, reference pages remain readable, and no broken image/link/console/
  CSP/network error remains;
- independent art-direction, frontend/product/security, and UX/accessibility
  reviewers report no material disagreement after verified fixes.

#### Stage 7 — Version, evidence, and release-source migration

Work:

- rerun the locked 138-case plus 32-case evaluation against exact candidate
  detector/model hashes and publish only the approved bounded summary/limitations;
- change `core/VERSION`, health, receipts, page metadata, channel labels,
  README/STATE, Docker labels, release-source assertions, and public acceptance
  expectations to Hosted `3.0.0` together; HTTP contract stays 2 unless a
  separately approved incompatibility is discovered;
- update operations/privacy/help/terms/developer documentation and the durable
  evidence log without inventing operator, jurisdiction, contact, platform, or
  provider-readiness facts.

Exit gate:

- version-drift tests find no `Hosted 2.5.0` claim on the candidate surface and
  no false change to Desktop/Extension versions;
- evaluation hashes equal the built candidate and limitations remain visible;
  provider/data/log/session/queue/PDF claims match running code and tests;
- source, built-image, and local caller evidence agree on `3.0.0`; this is still
  a release candidate, not production evidence.

#### Stage 8 — Complete local release-candidate acceptance

Work:

- run the full native and GitLab-runner-equivalent check suite, build exact-
  revision images, deterministic fake-provider acceptance, concurrency/rate/
  restart/log/resource/cleanup tests, and full browser matrix;
- inspect generated PDF/Markdown/text/receipt artifacts and durable screenshots;
- perform final independent adversarial reviews against the actual built caller,
  verify every claim, fix material blockers, and repeat all affected gates.

Exit gate:

- every CI check and local release acceptance is green on one exact clean commit;
  no test is skipped because a route/service is absent;
- images, browser artifacts, logs, resources, revisions, route matrix, queue
  traces, and generated outputs all bind to that exact commit and use only
  synthetic data/fake provider where labelled;
- all three independent reviewers issue a clear pass; the worktree contains no
  unexplained generated cache/artifact and no unrelated user file was modified;
- the owner receives exact SHA and remaining external/production-only limits for
  an explicit release decision.

#### Stage 9 — Protected main release gate

Work:

- after explicit owner authorization, push the reviewed feature branch, require
  check-only CI, fast-forward the exact reviewed commit to protected `main`, and
  create a new protected UI pipeline; never retry or repurpose an older pipeline;
- allow serialized `check → deploy → acceptance → logs → exact revision/process →
  restart/recovery` with existing automatic rollback on any post-mutation gate.

Exit gate:

- every protected job passes on the exact authorized SHA, three public images
  plus parser image carry that revision, and no rollback was triggered;
- public HTTPS/browser/API tests exercise Standard, Priority, text, PDF, queue,
  provider, artifact, 40-route/near-match, rate, log, resource, and restart paths;
- live provider evidence is clearly separated from fake-provider evidence, the
  organizer HTTP-redirect limitation is still reported honestly, and only then
  may Hosted `3.0.0` be called deployed.

Current execution position: **Stages 0 through 7 are complete locally; Stage 8
exact release-candidate acceptance has not started.** The source candidate
now identifies Hosted `3.0.0`, retains HTTP contract version 2, and has exactly
40 API locations. Deployed production remains Hosted `2.5.0` with exactly 16
public API locations until the exact Stage 8 commit passes the protected Stage 9
pipeline. No public deployment is implied by the source-version migration.
`HOSTED3_IMPLEMENTATION_STAGE=stage7_complete`

Machine-checked implementation marker: `HOSTED3_IMPLEMENTATION_STAGE=stage7_complete`.

Stage 7 closeout evidence (local release migration only):

- `core/VERSION`, built health, receipts/artifacts, Home/App/reference labels,
  README/operations guidance, release assertions, and public acceptance now
  agree on Hosted `3.0.0`; HTTP contract remains `2` and the API surface remains
  exactly 40 locations. Desktop and Extension remain 3.0.0 in their existing
  Published/Manual channels.
- A networkless Core evaluation image
  `sha256:40076754e43163641f5e5031917b4ae6a19e4421a8f9d28af35feb764729e367`
  (`stage7-eval-local-contract`) reran 138 constructed direct-PII cases and 32
  separate Section 26 heuristic cases with zero network/provider calls. Exact
  typed precision/recall/F1 remained 76.86/77.50/77.18%; protective-character
  recall remained 91.57%. Detector-code and model-tree hashes match the approval
  bindings recorded in the evaluation document.
- The rebuilt four-service joined local stack reported health version 3.0.0 and
  passed Priority legacy plus Standard custom-text and text-layer-PDF
  preview→queue→claim→fake-provider→verified result/artifact acceptance, exact
  resource/revision checks, and value-free logs. A Playwright CLI browser read
  the built App title/footer as Hosted 3.0.0 at desktop/mobile; the direct web
  image correctly returned fixed 404 for joined API paths, so joined acceptance
  used the local TLS edge and internal API stack.
- This evidence is local and synthetic. Stage 8 must bind the full suite,
  exact images, browser matrix, artifacts, and three independent reviews to one
  clean commit before any protected production pipeline is authorized.

## Production-ready acceptance criteria

- The visual system is approved by the user and no retained prototype is
  presented as production.
- Logo geometry has an explicit construction spec and passes small-size tests.
- Thai typography is self-hosted, licensed, routed, and verified without a CDN.
- Production assets are included in the image and exposed only through intended
  exact routes.
- Product claims and data boundaries match running behavior.
- Required browser, accessibility, responsive, reduced-motion, security, and
  production acceptance evidence passes.
- Independent adversarial reviewers report no unresolved material blocker.
- `STATE.md` and this document accurately describe the deployed commit and
  evidence. A local screenshot or source-only mock is never sufficient.

## Decision and evidence log

### 2026-08-16

- The owner selected PDF-to-protected-structured-text as the proposed Hosted 3.0
  judged story rather than reviving black-box PDF redaction. Local code and
  production
  evidence show that text-layer extraction dependencies are already in the
  Hosted image, while scanned-PDF OCR remains disqualified by the measured
  one-page `221 s`/roughly two-CPU/`6 GiB` resource failure. The recommended scope
  therefore accepts invite-only text-layer PDF uploads,
  uses a server-owned synthetic PDF for Guest, protects in fixed Token mode,
  requires explicit approval of exact protected text, asks Pathumma only to
  classify each immutable protected segment, and lets AI Guard validate, group,
  and render the Protected Markdown; it never returns a modified PDF or restores
  PII. It adds two operations plus aliases to the plan, taking
  the exact allowlist from 28 to 32; old `/redact-pdf` and all OCR paths remain
  fixed 404. This is a product-plan decision only: no PDF source, route, parser
  image, version, or deployment has changed.
- The first PDF-plan adversarial pass rejected absolute `no original PII reaches
  Pathumma` wording, contradictory preview focus, unusable no-JavaScript text-
  paste recovery, immutable-provenance wording for editable files, an exposed
  stable source hash, an unmeasured 20,000-character provider envelope, weak
  tiny-overlay/raster policy, free-form provider content, and a roughly 90-second
  document-review window. The corrected plan says only detected PII is replaced;
  scopes focus by transition; provides real no-JavaScript recovery; automatically
  includes editable provenance with no header-free product path; uses a random
  request-scoped receipt ID; initially proposed 8,000 code points/80 immutable
  segments pending measurement, later reduced to the measured 32-segment provider
  cap and 9,120-byte request cap while retaining the parser's 80-segment safety bound; uses exact text/raster
  geometry and inert-PDF allowlists; permits Pathumma only to return an exact
  source-anchored classification for every segment while AI Guard performs the
  deterministic grouping/reordering; streams provider responses under 32 KiB
  inside an absolute-deadline child; and
  gives invite documents a fifteen-minute review ticket. The final ticket
  contract is a strict AEAD tagged union so custom text, server-owned Guest PDF,
  and invite PDF execution each receive only their required authenticated facts;
  raw source hashes remain ciphertext-only.
- Final focused art-direction, frontend/product/security, and UX/accessibility
  re-reviews report no material PDF-plan disagreement. They verified the single
  artifact-led story and three-stage density budget; source-faithful segment
  reorganization and measured provider bounds; enforceable parser/raster/action
  gates; branch-complete content-stateless ticket behavior; meaningful review
  timing; request-scoped receipt identity; accessible upload/focus/no-JavaScript
  behavior; and editable artifact provenance. This is approval of the plan only.
  No Hosted 3.0 PDF source, parser image, built-image/browser evidence, version
  bump, or deployment exists yet.
- The owner paused logo selection and requested a real Hosted Web/API `3.0.0`
  competitive release rather than another visual-only or version-label update.
  Public Chrome research inspected only openly reachable surfaces and built-in
  synthetic/Guest paths. Team 03 set the strongest instant-utility benchmark,
  Team 10 the strongest complete creation workflow, and Team 13 the strongest
  evidence-led product narrative. AI Guard's chosen answer is not to copy their
  modality breadth: it is an immediate server-owned Synthetic Guest journey
  that proves `parse a server-owned synthetic résumé PDF → preview exact
  protected payload → explicit human approval → send those exact bytes → return
  reusable Protected Markdown without restoring PII → issue value-free proof`.
- The initial Hosted 3.0 proposal failed independent adversarial review because
  it simultaneously implied provider execution on the first click and required
  approval, did not lock a memorable job or first-fold entry, could have made the
  long App denser, treated a bare digest as sufficient despite randomized
  Token/Surrogate mappings, and lacked Guest authority, abuse isolation, exact
  route compatibility, lifecycle, accessibility, and negative acceptance
  contracts. The pre-PDF revision selected `hr-candidate-summary-v1`; that story
  is now superseded by the single `hr-resume-pdf-structured-v1` scenario, a
  three-stage Guest canvas, an additional public `/developers` reference page,
  eight additive canonical+`/v1` operations, a content-stateless AEAD approval
  ticket
  with bounded one-use replay state, separate Guest cookie/capacity/rate lanes,
  exact request schemas, truthful outbound-gate language, deterministic focus
  and invalidation, and release-blocking negative proofs. At that historical
  stage no Hosted 3.0 source, version, or production deployment had changed and
  implementation was pending owner approval; the owner-approved queue-first
  contract recorded below later superseded that status.
- The pre-PDF Hosted 3.0 plan passed focused adversarial review for entry,
  authority, ticket, state, and evidence foundations. Its HR-summary/restoration
  story and 28-route count were superseded by the later PDF plan. At that
  historical stage the PDF revision still required focused review before owner
  approval. Those reviews and the later queue-first approval are now recorded
  below. No source, built-image, browser, version, or public production evidence
  exists for Hosted 3.0 yet.
- The owner then requested a simpler queue-first access model: ordinary visitors
  should use the real product at a low rate, owner/judge invites should receive
  the same complete product at higher priority, and otherwise idle capacity
  should remain usable. The resulting proposal removes the separate demo-only
  workspace and exposes one App with two service classes: automatic 30-minute
  `Standard access` and individually issued `Priority Invite`. Standard is full-
  feature with no lifetime run cap; Priority adds judge/presentation evidence,
  higher rate, and three of every four claim-grant opportunities under sustained
  two-class contention. Either class can borrow both provider slots when the
  other is empty. Public limits are truthfully per signed browser session, while
  Priority limits are per issued credential rather than an unprovable person.
- The owner approved the queue-first planning baseline and explicitly excluded
  audio, TTS, images, Vision, scanned/image-only PDF, and OCR from Hosted 3.0.
  The decision changes no running route, version, secret, image, or deployment.
  It defines exact Standard authority and
  ticket branches, 40 exact Nginx/API locations, control-plane rates, a content-
  free in-memory scheduler, 12-entry capacity, 3:1 weighted claim grants, status-
  only refresh recovery, capability-authenticated foreground claim handoff, and
  deterministic queue/failure/accessibility behavior. Independent adversarial
  art-direction, frontend/product/security, and UX/accessibility re-reviews
  report no remaining material plan disagreement after corrections for first-
  fold density, authority conflicts, ticket/session deadlines, legacy scheduler
  bypass, identity wording, control-plane abuse, claim races, terminal status
  serialization, and claim-miss recovery. The earlier single-run Guest detail is
  retained in a collapsed history whose product/authority decisions are non-
  governing; its explicitly named modality-neutral PDF/DTO/AEAD foundations are
  incorporated by the authoritative contract. Final closeout re-review also
  passed after the authoritative section became self-contained for exact preview/
  execute DTOs and ticket TTLs; added 120/300-second review-window enforcement at
  admission, pre-mint, and browser receipt; defined strict ticket-versus-session
  deadline precedence; anchored browser timing to additive Core server/session-
  expiry headers plus monotonic elapsed time; kept Nginx-originated errors
  truthfully headerless; and added accessible `timing_unavailable` recovery whose
  copy distinguishes data already processed by AI Guard from data not sent to
  Pathumma. Art-direction, frontend/product/security, and UX/accessibility each
  report a clear pass with no material disagreement. At that historical planning
  closeout there was no queue or Standard-access implementation/browser/
  deployment evidence. The later Stage 1 entry above now records a local,
  internal-only Standard/Priority authority/timing foundation; queue, public
  routing, browser UI, version, and deployment evidence remain absent.
- The user reopened the logo direction after seeing the live mark and asked for
  a new design whose palette belongs to the production website. The exploration
  must remove the assumption that the historical face/mask is mandatory, avoid
  an esports or mascot expression, and compare distinct concepts before any
  production integration. The live palette is Paper `#F3F1EB`, Ink `#151515`,
  Protection Blue `#3266A8`, Deep Blue `#173B65`, Safe `#267A61`, and Signal
  `#E06972`; accent colors must have explicit roles rather than compete equally.
- Implemented the three review studies directly in the existing non-production
  `logo-preview.html`, not as deployable assets. The comparison includes the
  current live mark, header-scale wordmark lockups, main-on-Paper and inverse-on-
  Deep-Blue specimens at exact `16`, `24`, `32`, `42`, `64`, and `128 CSS px`,
  and numeric geometry notes. Chrome rendered 42 study instances with no broken
  image or console error and no horizontal overflow at `1440×900`, `720×365`,
  `390×844`, or `360×800`; the size matrix measured the six requested CSS sizes
  exactly. Evidence is
  `output/playwright/logo-redesign-round2-1440.png` and
  `output/playwright/logo-redesign-round2-390.png`. These are exploratory
  comparisons, not approved artwork or production-serving evidence.
- The first adversarial review of that comparison did not approve it as a
  three-way choice. Art direction found that all three candidates reused the
  same generic shield, that Data Fold read as a commodity secure-PDF mark, and
  that Boundary Core read as `[0]`, a switch, or code syntax. Signal Veil was
  the most distinctive candidate but its crown collision and fire/firewall
  reading remained material. Frontend and UX review also found that the sheet
  had not proved a genuine one-color construction, that hue carried critical
  distinctions, and that every candidate needed a dedicated `16`/`24 px`
  micro construction with critical features at least one CSS pixel thick.
  Those findings supersede the round-2 candidate copy; no round-2 mark is
  eligible for production integration.
- Rebuilt the comparison as round 3 with materially different outer systems:
  Guard Loop is an open `G` monogram, Privacy Passage is a transformation arch,
  and Signal Veil is the only retained shield direction. Signal Veil's rounded
  layer now begins below the crown and uses a curved persistent seam rather
  than the former straight bisection or crown-breaking flame. All three expose
  main, inverse, one-color, and optically hinted `16`/`24 px` micro
  constructions; the required matrix now contains 54 exact-size specimens and
  18 of them resolve to dedicated micro symbols. Chrome found one H1, three
  explicitly named hero marks, no console error, no broken image, and no
  horizontal overflow at `1440×900`, `720×365`, `390×844`, or `360×800`.
  Evidence is `output/playwright/logo-redesign-round3-1440.png` and
  `output/playwright/logo-redesign-round3-390.png`. Round 3 remains a prototype
  pending independent adversarial review and user direction; production assets,
  routes, Docker, Nginx, CSP, and the deployed B2 mark remain unchanged.
- Round-3 adversarial art, frontend/product, and UX/accessibility review agree
  that the set is materially distinct and responsible to show as directional
  exploration, never as production-ready artwork. All three rank Guard Loop
  first, Signal Veil second, and Privacy Passage third. Guard Loop owns the
  strongest compact silhouette but its Signal square can resemble a
  notification/plug and needs terminal refinement if selected. Signal Veil is
  the safest continuity option but retains generic shield/leaf associations.
  Privacy Passage is explicitly the weakest abstract experiment because its
  dominant unaided readings are headphones, a horseshoe magnet, a gate, or a
  connector; its one-color output also merges into the right leg. The preview
  copy now discloses those readings and no longer claims that transformation is
  immediately legible. Frontend review independently confirmed all 54 exact CSS
  sizes, all 18 micro-symbol substitutions, geometry inside the viewBox,
  one-color negative space, responsive evidence, and zero production route or
  asset change. This closes the presentation gate only; a selected direction
  still needs redraw, numeric lock, all final variants, production integration,
  and the complete deploy/re-review path.
- Corrected exact revision `dbcfe17b34744dc3e9a88e4099786a754fe903a6`
  passed feature Pipeline #36392 and protected-main check-only Pipeline #36393,
  then passed the complete UI-started protected production Pipeline #36394:
  check Job #141734, deploy #141735, acceptance #141736, logs #141737,
  process/revision inspection #141738, and restart/recovery #141739. Acceptance
  verified authenticated platform behavior, the 16-route allowlist, a live
  provider roundtrip, report generation, log privacy, HTTPS/TLS/HSTS, every
  product/document surface and pinned static asset, health, and exact legacy
  denials. All three production containers survived restart healthy at the same
  exact revision.
- A fresh Chrome 151 caller audit against the public host after restart returned
  `200` for Home, App, Downloads, Privacy, Help, and Terms; every page had one
  truthful H1, the production CSP and HSTS, zero broken images and no horizontal
  overflow. The App correctly bootstrapped out of `inert`, reported the signed-
  out invite state, and kept business controls disabled; DevTools recorded the
  handled `401` session probe as a failed resource, with no uncaught application
  error. `/api/health` returned version `2.5.0`; unauthenticated
  `/api/auth/session` returned exact JSON `401 authentication_required`.
  Branded human 404 and unbranded source, asset-near-match, and API denials all
  preserved their intended `404` boundaries.
- The public Home passed Chrome at `1440×729`, `1366×768`, `1440×900`,
  `1024×768`, `768×1024`, `720×365`, `390×844`, and `360×800`: no overflow,
  no broken image, the self-hosted `AIGuardAnuphan` face loaded, and every
  network resource remained same-origin. Reduced motion capped animation at
  `0.00001 s`; keyboard focus began on the skip link. With JavaScript disabled,
  the native mobile menu exposed all four primary destinations and the App kept
  its operational workspace inert while leaving recovery text available.
  Post-restart screenshots are
  `output/playwright/production-public-home-1440x729.png`,
  `production-public-home-390x844.png`, and
  `production-public-home-360x800.png`.
- Pipeline #36394 repeated the accepted structured warning that the organizer's
  plain-HTTP edge does not redirect to HTTPS. HTTPS itself has valid TLS and
  HSTS; the external HTTP limitation remains explicitly unsafe, owner-accepted
  for this competition deployment on 2026-08-15, and not rollback-eligible.
- Protected-main production Pipeline #36391 checked and deployed exact revision
  `9995532a2a27a4e49e74ee9d9a46795e9ac1bb1a`; its internal platform acceptance
  passed auth, the API allowlist, live provider roundtrip, report generation,
  and log checks. Public acceptance then exposed a stale assertion: it expected
  unauthenticated `GET /api/auth/session` to be an unknown route (`404`), while
  the intentionally exposed session endpoint returns JSON
  `401 authentication_required`. The mandatory trap restored the exact healthy
  rollback baseline `75aaa7e61b529204b5cf1294aae37d3e99d389ae`. The acceptance
  contract now verifies the truthful `401` status, JSON MIME type and exact safe
  error code while continuing to reject HTML fallback. At that point the
  correction required a new protected deployment; Pipeline #36394 subsequently
  supplied it and is the live evidence recorded above.
- The user approved the six-page static Nginx architecture plus the internal
  branded 404 and explicitly prioritized finishing and deploying the production
  web redesign before the event. Deployment Checklist completion, final slides,
  and the timed pitch script are intentionally deferred to Monday.
- The verified rollback baseline is Hosted 2.5.0 at exact commit
  `75aaa7e61b529204b5cf1294aae37d3e99d389ae`, whose protected production
  Pipeline #36309 passed check, deploy, acceptance, logs, process/resource, and
  restart/recovery jobs. It was retained as the rollback target until the
  redesign's exact-revision Pipeline #36394 and public acceptance passed.
- Owner identity, approved jurisdiction wording, and a publishable private
  privacy/security/accessibility contact remain owner-supplied facts. The
  implementation may preserve the existing bounded support wording but must not
  invent or expose personal contact information while those facts are absent.
- Split the production files by route: Home now loads only exact local
  `home.css`/`home.js`; Hosted loads only exact local `app.css`/`app.js` and is
  `noindex,nofollow`. The application retains Privacy Scan, Safe AI, PDPA
  Report, `/guard`, all five synthetic scenarios, evidence/presenter tools, and
  current session/request safety. Deep links are held in memory, return the
  visitor to the access gate first, and restore the requested workflow only
  after authenticated session confirmation.
- Completed the reference-page and branded-404 source integration. Privacy
  explicitly distinguishes Desktop, Hosted, Extension, and disabled Hosted
  PDF/OCR; Help groups recovery by task/status; Downloads remains OS-first with
  hashes and provenance in disclosure; Terms stays one uninterrupted article.
  Because the repository does not establish a legal operator, jurisdiction, or
  approved private public inbox, the pages state that limitation instead of
  inventing facts.
- Extended the explicit Docker and Nginx surface for the new page/style/script
  files, removed CSP `script-src 'unsafe-inline'`, retained only exact local
  scripts, excluded `/app` from robots/sitemap, and separated branded web 404s
  from fixed API/asset failures. `python tests/nginx_contract.py` passes against
  the built web image, including MIME types, CSP, internal 404 behavior,
  near-match denial, no-store headers, log hygiene, and valid Nginx syntax.
- Route-specific source contracts now prove that Home has no access/API
  runtime, Hosted owns the full workflow/session contract, and the old
  root-copy acceptance cannot false-pass. `node
  tests/frontend_session_contract.mjs`, `python
  tests/build_context_contract.py`, `python tests/public_surface_contract.py`,
  `python tests/secret_hygiene_contract.py`, and `python
  tests/release_source_contract.py` pass on the current working tree.
- Built-image Chrome 151 evidence now covers `1440×729`, `1366×768`,
  `1440×900`, `1024×768`, `768×1024`, `720×365` (200%-equivalent reflow),
  `390×844`, and `360×800`. Every Home viewport returned 200 with zero console
  errors, zero horizontal overflow, one H1, working self-hosted Thai/Latin
  faces, no broken visual assets, and maximum measured CLS `0.00035`; maximum
  local load time was `190 ms` with `104,659` transferred bytes. The static App
  workspace measured CLS `0.01833` and no horizontal overflow.
- Keyboard evidence starts at the visible skip link, moves focus to
  `main-content`, and then traverses App navigation, invite input, login, and
  workflow links in source order. Reduced-motion Chrome reports the requested
  preference, reduces the scan animation to `0.00001 s`, leaves no hidden
  reveal content, and introduces no overflow. Home and App remain readable with
  JavaScript disabled; App keeps its authored bootstrap/recovery panel visible.
- Font-failure evidence uses a fresh Chrome process and aborts both exact WOFF2
  requests. `AIGuardAnuphan` then reports unavailable, Leelawadee/fallback
  rendering keeps Thai marks readable, and the `390×844` page has no overflow.
  SVG-failure evidence now leaves a clean visible `AI Guard` wordmark with no
  broken-image glyph because decorative header marks use a CSS background.
- Playwright's `Control++` shortcut did not mutate browser zoom in either
  headless or headed automation. The durable zoom evidence is therefore the
  explicit `720×365` 200%-equivalent CSS viewport, not a claimed literal
  browser-shortcut result. It reflows without horizontal overflow. Exact JSON
  is `output/playwright/production-web-audit.json`; the separate fresh-process
  font result is `output/playwright/production-font-fallback-audit.json`.
- The isolated built web container deliberately returns fixed 404 for
  `/api/health` and `/api/auth/session`, producing two expected console network
  errors on `/app`; production routes these through the organizer edge. This
  artifact proves the web image's fail-closed boundary, not the joined public
  caller path. The joined-edge proof was therefore assigned to protected
  deployment and public acceptance, and Pipeline #36394 plus the post-restart
  browser audit have now satisfied it.
- First full-page adversarial review found four real integration defects: the
  Nginx catch-all exposed source `.html` filenames and branded filename-like
  misses; old Guided Demo/provider-evidence fragments did not expose their
  exact Hosted handoff; the 404 omitted the shared brand and two required
  recovery routes; and App no-JavaScript/same-page deep-link behavior plus the
  mobile Home navigation could bypass the intended access/navigation contract.
  The reviewed fixes now make every non-allowlisted filename a fixed unbranded
  404, keep only extensionless human misses branded, expose exact target-only
  legacy handoffs with header-safe offsets, add the inverse brand and all four
  404 recovery routes, keep App controls `inert` until JavaScript bootstraps,
  intercept signed-out workflow hashes at the gate, and provide a native
  no-JavaScript mobile menu with every primary route.
- Post-fix Chrome 151 evidence in
  `output/playwright/production-fix-audit.json` verifies five representative
  filename/source aliases as fixed unbranded 404, the branded four-link 404,
  all six legacy Home fragments below the sticky header, both exact moved
  handoffs, an open four-route mobile menu with JavaScript disabled, and an
  inert no-JavaScript App whose login control cannot receive focus. A real
  browser integration test uses controlled synthetic API responses to verify
  that a signed-out same-page Safe AI link returns focus to `authCard`, clears
  the visible hash, retains the target only in memory, and after successful
  session confirmation restores `#safe-ai` with focus on that section. This
  proves the client transition; protected-pipeline HTTP acceptance and the
  public browser check subsequently proved the joined edge/API path.
- `product.css` and `sitemap.xml` are now explicit caller-facing acceptance
  targets. Runtime Nginx tests also deny all five private `.html` source names
  and top-level script/style near-matches, closing the route-allowlist gap.
- Final repeated independent review reports no remaining material disagreement:
  art direction verified the branded 404 and all six fragment landings;
  frontend/product verified the exact-route boundary, legacy handoffs,
  caller-asset coverage, and browser session restoration; UX/accessibility
  independently reproduced the no-JavaScript fail-closed state, click and
  `hashchange` gate behavior, keyboard mobile menu, and overflow results. These
  were pre-commit candidate approvals. The exact-commit and public deployment
  gates later passed in Pipeline #36394 and the public Chrome audit above.
- A separate post-deploy adversarial pass inspected the public revision itself.
  Art direction found no live visual/brand regression at desktop or both mobile
  widths; UX/accessibility independently reproduced skip-link, native mobile
  menu, reduced-motion, gate-first, and no-JavaScript fail-closed behavior; and
  frontend/product verified the exact revision, joined API/session contracts,
  resource state, and 404 separation. After correcting stale historical wording
  in this document and `STATE.md`, no material post-deploy disagreement remains.

### 2026-08-15

- Selected Concept C from multiple landing-page explorations.
- Proposed, but did not yet implement, a six-page static production information
  architecture plus an internal branded 404: Home, Hosted App, Downloads,
  Privacy, Help, and Terms. Home is locked to Concept C's six-scene content
  budget; App and reference pages use distinct related archetypes. Next.js is
  not justified for the current fixed semantic pages plus one client app.
- Independent art-direction, frontend/product, and UX/content-architecture
  reviews found material planning gaps in the first draft. The revised plan now
  covers retained application/presentation features, all current error classes,
  state-loss/navigation behavior, gate-first deep links, API-safe branded 404,
  legacy fragments, no-index app policy, route-specific tests, mobile/dynamic
  accessibility, and summary-to-detail rules. Re-review reports no remaining
  material design or architecture disagreement.
- Content completeness still depends on owner-supplied facts that the repository
  does not establish: responsible operator/service roles, approved
  scope/jurisdiction wording, policy effective date/version, a private
  privacy/security contact, an accessibility-feedback channel, and an organizer
  metadata-policy URL or explicit confirmation that none is public. These must
  not be fabricated.
- Compared the then-current production integration directly with the original
  Concept C at `1440×729`. The user found the original materially stronger, so
  that prior production composition was rejected and had to be redesigned while
  retaining the real production architecture and technical asset path.
- Set the central brand hue to approximately `#3266A8` and retained the warm
  editorial paper/ink contrast.
- Added prototype motion, responsive behavior, short-laptop adjustments, and a
  visual raw-to-protected product narrative.
- Checked Concept C at 1440 x 729, 1366 x 768, and 1440 x 900.
- Located the canonical logo in `thai-pii-redaction/assets/logo.svg`.
- Created a website-colored SVG mark and a simplified favicon candidate.
- Rejected the current candidates because their symmetry and line construction
  do not look planned. Logo redesign remains the first open visual task.
- Locked a `64 × 64` numeric construction system, rebuilt the shield as exact
  reflected cubic geometry, confined asymmetry to the canonical flame lobes,
  and generated main, one-color, inverse, and simplified favicon candidates.
- XML parsing and explicit geometry-token checks pass for all four SVGs.
  Playwright rendered the required `16`, `24`, `32`, `42`, `64`, and `128` CSS
  pixel matrix on Paper and Protection Blue with zero browser console errors;
  evidence is `output/playwright/logo-construction-1440.png`. This remains local
  visual evidence, not production-serving evidence. Independent art-direction,
  frontend/product, and UX/accessibility reviews are in progress.
- First adversarial logo review found material blockers: the symmetric flame
  drifted into a generic sports-badge silhouette instead of preserving the
  canonical broad mask/right-rising flame; the normal favicon disappeared on a
  blue field; eye/seam strokes left only `0.175` units of rendered clearance;
  the stated motif extrema and clear-space diagram were inaccurate; fixed-color
  variants were incorrectly described as consumer-configurable `currentColor`;
  and the test matrix did not fully exercise every variant.
- Revision B keeps the verified symmetric shield but reconstructs the canonical
  gold mask, unequal eyes, and coral flame that rises above the crown. It removes
  the free-standing centre seam, guarantees at least `1.5` units edge-to-edge at
  eye cuts, shares the outer footprint across main/one-color/inverse, adds a
  dedicated inverse favicon, labels tiny favicons non-semantic, replaces the
  false padded construction grid with a direct 64-unit grid plus a separate
  `80 × 80` external-clear-space diagram, and adds semantic specimen headings.
  Revision B2 then replaced the overlapping mask/flame outlines with one exact
  shared fill contour rendered once, moved the left-eye endpoint to
  `(27.875, 32)` to preserve a measured `1.594`-unit rendered clearance, and
  retained that seam as a transparent cut in the one-color and inverse marks.
  Final browser evidence is
  `output/playwright/logo-construction-revision-b2-final-1440.png`. Independent
  art-direction, frontend/product, and UX/accessibility reviewers verified the
  exact post-change artifact and reported no material logo disagreement.
- Resolved Anuphan from Google Fonts' first-party repository and current v6
  distribution, retained the full OFL 1.1 license, pinned the Thai and Latin
  WOFF2 hashes above, and confirmed both binaries have a valid `wOF2` signature.
  All three production stylesheets use the local subsets with `font-display: swap`;
  Docker copies them explicitly, Nginx exposes exact allowlisted routes with
  `font-src 'self'`, and build/runtime tests pin their hashes and WOFF2 magic.
- Converted Concept C into the real `web/index.html` architecture while
  preserving the existing workflow controls and application script. The hero is
  Desktop-first; its boundary ledger says that Desktop processing/vault/report
  state remains on-device and that Hosted Web sends raw text to AI Guard's edge
  and server, while only repeatedly protected text reaches Pathumma/thaillm-8b.
- Added the final SVGs, local fonts, and license through `web/Dockerfile`, exact
  `web/nginx.conf` routes, CSP, build-context tests, Nginx runtime tests, source
  DOM contracts, and public acceptance checks. `python tests/nginx_contract.py`
  passed with the exact assets, `font-src 'self'`, no-store policy, route
  isolation, clean API/web logs, and valid Nginx syntax.
- Source-server browser iteration at `1440×729`, `1366×768`, `1440×900`,
  `1024×768`, `768×1024`, `390×844`, and `360×800` found no horizontal overflow;
  the local Anuphan face was ready for a Thai combining-mark sample at every
  size. This is responsive iteration evidence only; the built-image browser
  matrix and interaction checks were still open at that stage and were
  subsequently completed in the 2026-08-16 evidence above.
- Removed superseded Concept B, Concept D, and the initial home mock from the
  retained handoff set. Concept C remains the only selected prototype.
- Consolidated `aiguard-aift` onto local `main`; removed 16 merged local branches
  and seven merged remote branches. No alternate AI Guard branch remains.
- Confirmed `thai-pii-redaction` is clean on local `main`. Three current,
  unmerged Dependabot pull-request branches remain remote because their checks
  are not fully passing; deleting them would discard active update work.
- Confirmed `aift-onboarding` is not a Git repository, so it has no branch to
  consolidate.
- Removed 46.122 GiB of deterministic Rust, Python, JavaScript, and build caches
  from `thai-pii-redaction`. Preserved release-certification evidence, QA
  artifacts, benchmark reports, logs, and normal Git data.
