# AI Guard Production Web Redesign

Last updated: 2026-08-15 (Asia/Bangkok)

## Purpose

This is the durable source of truth for converting the approved Concept C art
direction into the production AI Guard website. Update this document whenever a
decision, implementation detail, limitation, or verification result changes.

The goal is a memorable, polished, production-quality Thai-first website. A
working page is not sufficient. The result must have deliberate typography,
color, geometry, motion, product truth, responsive behavior, accessibility, and
an end-to-end production serving path.

## Current state

- Production remains `web/index.html` plus its current supporting files.
- `web/home-concept-c.html` is the selected visual prototype. It is not deployed
  by `web/Dockerfile` and has not replaced production.
- `web/logo-preview.html` is a comparison surface for logo exploration only.
- `web/assets/ai-guard-mark.svg` and `web/assets/ai-guard-favicon.svg` are the
  latest preserved candidates, but the user rejected their symmetry and line
  construction. They are not approved brand assets.
- The canonical historical logo source is in the sibling project at
  `C:/Users/teera/dev/thai-pii-redaction/assets/logo.svg`, with PNG and source
  image variants beside it.
- The mock declares Anuphan but does not yet ship Anuphan font files. The visible
  result may therefore fall back to Leelawadee UI, Noto Sans Thai, or Tahoma.
  Font licensing, authoritative source, subset strategy, and self-hosted routes
  remain open production work.

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

## Open work for the next production session

1. Rebuild the logo and favicon using the construction requirements above.
2. Obtain and self-host the approved Thai font from an authoritative source,
   document its license, and add production routes and tests.
3. Convert Concept C into the production architecture rather than copying the
   standalone mock wholesale.
4. Reconcile the landing-page narrative with the existing authenticated product
   surface and all Desktop/Web privacy boundaries.
5. Replace placeholder links and synthetic visual controls with the correct
   production routes and behaviors.
6. Add or update Docker, Nginx, CSP, route, mixed-content, accessibility, and
   browser tests for every new static asset and page behavior.
7. Run real-browser responsive and interaction QA at all required viewports.
8. Run independent adversarial art-direction, frontend/product, and
   UX/accessibility reviews. Resolve material disagreement and repeat review.
9. Update this document with exact commands, screenshots, tests, commit IDs, and
   remaining limitations.

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

### 2026-08-15

- Selected Concept C from multiple landing-page explorations.
- Set the central brand hue to approximately `#3266A8` and retained the warm
  editorial paper/ink contrast.
- Added prototype motion, responsive behavior, short-laptop adjustments, and a
  visual raw-to-protected product narrative.
- Checked Concept C at 1440 x 729, 1366 x 768, and 1440 x 900.
- Located the canonical logo in `thai-pii-redaction/assets/logo.svg`.
- Created a website-colored SVG mark and a simplified favicon candidate.
- Rejected the current candidates because their symmetry and line construction
  do not look planned. Logo redesign remains the first open visual task.
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
