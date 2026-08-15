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

- The working tree now implements the approved split production architecture:
  Concept C's six-scene editorial Home is `web/index.html`, while the complete
  authenticated Hosted workspace is isolated in `web/app.html`, `web/app.css`,
  and `web/app.js`. Home contains no invite input, application runtime, or API
  initialization. The exact built-image checks and required real-browser matrix
  now pass locally and independent full-page reviews report no material blocker.
  The first exact production attempt, Pipeline #36391 at `9995532a`, deployed
  cleanly but was automatically rolled back because the public acceptance test
  incorrectly expected an unauthenticated `GET /api/auth/session` to return
  `404`; the live API's intentional contract is `401 authentication_required`.
  The rollback to `75aaa7e6` completed healthy. A corrected exact-revision
  protected deployment and public browser check remain open.
- `web/home-concept-c.html` is the selected visual prototype. It is not deployed
  by `web/Dockerfile`; it remains the visual quality baseline for the next
  production pass rather than merely a provenance artifact.
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
  HTML, Docker, exact Nginx routes, CSP, and tests; public deployment remains
  pending the complete browser/review gate.
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
- Global footer: label each channel separately as `Desktop 3.0.0`,
  `Hosted 2.5.0 · Private Beta`, and `Extension 3.0.0 · Manual`; then link Home,
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
   Hosted invite-only, Extension Manual/Store unpublished, and PDF/OCR
   unsupported, plus one sentence that pseudonymization is not anonymization or
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
8. Limits and exclusions: 20,000 characters, public PDF/OCR fixed 404,
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
6. FAQ for storage/logging, PDF/OCR, Extension Store status, detection accuracy,
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
6. Separate Desktop/Extension distribution status, unsupported public PDF/OCR,
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

## Open work for this production session

1. Update `STATE.md`, deployment evidence, and this document with the exact
   committed revision, protected-pipeline result, and public caller-facing
   verification.
2. Commit and push the reviewed tree, deploy it through the protected-main UI
   pipeline, and run public route/API/asset/browser acceptance before calling
   the redesign production-ready.

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

- Protected-main production Pipeline #36391 checked and deployed exact revision
  `9995532a2a27a4e49e74ee9d9a46795e9ac1bb1a`; its internal platform acceptance
  passed auth, the API allowlist, live provider roundtrip, report generation,
  and log checks. Public acceptance then exposed a stale assertion: it expected
  unauthenticated `GET /api/auth/session` to be an unknown route (`404`), while
  the intentionally exposed session endpoint returns JSON
  `401 authentication_required`. The mandatory trap restored the exact healthy
  rollback baseline `75aaa7e61b529204b5cf1294aae37d3e99d389ae`. The acceptance
  contract now verifies the truthful `401` status, JSON MIME type and exact safe
  error code while continuing to reject HTML fallback; this correction requires
  a new protected deployment before the redesign can be called live.
- The user approved the six-page static Nginx architecture plus the internal
  branded 404 and explicitly prioritized finishing and deploying the production
  web redesign before the event. Deployment Checklist completion, final slides,
  and the timed pitch script are intentionally deferred to Monday.
- The verified rollback baseline is Hosted 2.5.0 at exact commit
  `75aaa7e61b529204b5cf1294aae37d3e99d389ae`, whose protected production
  Pipeline #36309 passed check, deploy, acceptance, logs, process/resource, and
  restart/recovery jobs. The redesign must preserve that runtime as the rollback
  target until its own exact-revision pipeline and public acceptance pass.
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
  caller path. The protected deployment and public acceptance must prove that
  the edge serves those two API paths successfully before release completion.
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
  public browser check remain responsible for the joined edge/API path.
- `product.css` and `sitemap.xml` are now explicit caller-facing acceptance
  targets. Runtime Nginx tests also deny all five private `.html` source names
  and top-level script/style near-matches, closing the route-allowlist gap.
- Final repeated independent review reports no remaining material disagreement:
  art direction verified the branded 404 and all six fragment landings;
  frontend/product verified the exact-route boundary, legacy handoffs,
  caller-asset coverage, and browser session restoration; UX/accessibility
  independently reproduced the no-JavaScript fail-closed state, click and
  `hashchange` gate behavior, keyboard mobile menu, and overflow results. These
  are pre-commit candidate approvals. Exact-commit and public deployment gates
  remain mandatory.

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
- Compared the current production integration directly with the original
  Concept C at `1440×729`. The user found the original materially stronger, so
  the current production composition is rejected and must be redesigned while
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
  matrix and interaction checks remain open.
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
