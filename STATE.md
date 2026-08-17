# Status (2026-08-17 — Hosted 3.0.1 deployed; 3.0.2 output sanitization planned)

## Current release boundary

- Production is Hosted `3.0.1` with exactly 40 public locations at runtime
  revision `514945a42f161a96672ace4545ae8afc9c856338`. HTTP contract remains 2.
  Protected Pipeline #36606 passed check, deploy, and mandatory acceptance with
  no rollback. Manual ops gates logs #143764, exact revision/process/resources
  #143765, and restart/recovery #143766 passed; web, API, Core, and PDF parser
  restarted healthy with the exact runtime label. Public HTTPS health reports
  3.0.1/contract 2, public `hosted3-app.js` exactly matches the reviewed source,
  and credential-free public acceptance passes 40-route/product/TLS/HSTS gates
  with only the two previously accepted organizer plain-HTTP warnings.
- Post-restart public Chrome proved the new fail-closed classification but also
  exposed a remaining availability issue. Two bounded executions of the exact
  synthetic résumé prompt returned `restoration_unsafe` and no restored output.
  The provider created generic résumé-template prose; the detector falsely
  classified the literal placeholder `บริษัท/องค์กร]` twice plus `ได้` and
  `มีประสบการณ์การทำงานในสายงาน` as four generated-PII findings. No unsafe text
  entered the result DOM. The owner approved a separate `3.0.2` plan: preserve
  authoritative restored ranges, replace only newly detected provider-output
  spans with value-free markers, and show the remaining sanitized answer. Token
  integrity, digest, residual, foreign-token, malformed-response, and incomplete
  restoration failures remain full blocks. This opt-in Hosted behavior is not
  implemented or deployed yet and must not silently change Desktop/Extension.
- Hosted `3.0.1` release history: the port manifest pins upstream
  `3c2997835dbdc9842e38b38fb89f09642a713817`, which is the prior 75-file source
  base plus only the reviewed Thai NAME-boundary fix. The exact real-port
  restoration regression and generated-name adversarial control pass inside the
  Core dependency image; the candidate detector-code binding is
  `de2edadb469a753a6b928af45b8e52c9186cf527c96b88e777ad91ab7d03396f`.
  Focused execute is `11/11`, frontend behavior and
  platform policy contracts pass. Non-usable `incomplete|unsafe` execute results
  project an empty `restored_text`, receive distinct recovery copy, and never
  enter the result DOM. Adversarial frontend review then found that the browser
  accepted stale or mixed Hosted-version DTOs while portable provenance was
  labeled `3.0.1`. Current source uses one exact `HOSTED_VERSION = "3.0.1"`
  browser boundary for custom/PDF preview and execute, requires custom receipt
  agreement plus matching PDF receipt/artifact provenance, and has executable
  stale-version custom/PDF negatives. Those corrected frontend contracts pass.
  Exact source commit `2a7aa944e85a36e4c988605b8ebc6afee2a10aed`
  passed GitLab check-only Pipeline #36589. Its healthy exact local images are
  web `sha256:f6505bc982c24debd334e4d5b8c37aac1127730c1374419a8edaeb1262247790`,
  API `sha256:a704cf83d5d50418802076ad7d13b85080c6418ae3a6aed4cf67d905164665ef`,
  Core `sha256:f4124aef4ae5a07340298846a5eb006c63cfb3f903ecb22c3d304cfae862fdb1`,
  and parser `sha256:906ba11ea51c22eb8e175d84a286abba63d6be114c519ee0e681a08c09b2ab44`;
  every image label equals `2a7aa944...`. Source/image parity passes `3/3`,
  exact-image execute passes `11/11`, and local platform acceptance completed
  Priority legacy plus Standard custom/PDF/queue/provider/artifact paths with a
  usable custom result on attempt 1. Real Chrome completed the exact public
  false-positive input through preview, approval, queue, stub Pathumma,
  complete restored result, and a `3.0.1` receipt with zero browser storage.
  Focused art/product and UX/lifecycle re-reviews pass; frontend/security review
  found no remaining runtime blocker after requiring this durable evidence
  correction. A documentation-only release descendant must still receive exact
  label/parity and status rebind before it advanced to protected `main`; that
  rebind and Pipeline #36606 release are now complete.
  Clean source
  commit `1346d9a623e2f5ab8074135459f1037777768bfc` passed GitLab check-only
  Pipeline #36581 and the clean-clone Docker-executor-style check. Its first
  exact local images are web `sha256:b285a2c2212914ed59dc305f2472579f0c5c2383b7a49e9160c09ad790f8e54d`,
  API `sha256:0bf9273bd3fb6043e7d7fbb2daaaf79bde52172431b716b87299372b07a1fc6d`,
  Core `sha256:ae192736fea57313dc597ad602b1d0f4a3d60008ea8991c6064bff2addf9d7ff`,
  and parser `sha256:81cb4fbd394d199bbefe4fdb438e1e34cebd8d8f78a65412e4bdd381d24183bc`.
  All four labels equal that commit; parity passes `3/3`, exact-image execute
  passes `11/11` including the real port regression, the real-detector execute
  probe passes `1/1`, and local platform acceptance completed a usable custom
  result on attempt 1 plus Priority legacy, PDF, queue, artifacts, routes,
  report, and value-free logs. Evidence-only commit
  `b371c2fd516ba0f6821fd6e74ac5be29a2975806` then passed GitLab Pipeline
  #36584 and produced healthy web `sha256:53801a0b886457d74f5edfa104116cf4ca3564ff4b66295df19d4191db454382`,
  API `sha256:0f757861c62684d85157f729a8d5a940ad20e6c92fdf55c4e4cfe987bce92dcd`,
  Core `sha256:32a15d28d13cc28ba953519524b23bf8d1afc3d747cf0d1abd87bb068a690d00`,
  and parser `sha256:ee7097f68c8cbc21b3bbf043c0ce2601ff8e13d09caaa7c3c495cb51ce001c09`.
  That quartet is superseded for release by the `2a7aa944...` browser
  version-binding candidate above; none of the older image IDs is a deployment
  identity.
- Current deployment, same-origin application API, data-flow, acceptance,
  rollback, and operations guidance is centralized in
  `docs/HOSTED-3-DEPLOY-API-GUIDE.md`. Older deployment documents remain
  historical rollout/incident records and do not override that guide.
- Post-deploy UX review of `827e0601…` found ordinary Standard/Priority entry
  lost focus when the access gate hid. Runtime `f0774520…` fixes that boundary:
  direct entry and initial authenticated bootstrap focus the programmatically
  focusable chooser heading, deep-link focus retains precedence, and routine
  BFCache/visibility/online resampling preserves the active task/queue focus.
  Public Chrome after restart verified `document.activeElement.id` equals
  `h3ChooserTitle` with the chooser visible. Stage 9 is complete.
- Desktop remains published at 3.0.0 and Extension remains 3.0.0 Manual. The
  Hosted migration does not change either sibling channel.
- Audio, TTS, images, Vision, scanned/image-only PDF, and OCR remain excluded.
  Hosted text-layer PDF produces Protected Markdown; it does not redact or
  rebuild the source PDF and does not restore PII into the PDF artifact.
- Stage 7 reran the locked 138-case direct-PII corpus and separate 32-case
  Section 26 heuristic corpus in a networkless Core image. It reproduced exact
  typed precision 76.86%, recall 77.50%, F1 77.18%, protective-character recall
  91.57%, zero network/provider calls, detector-code SHA-256
  `01bb7d890aa79cbc4f03a8c8da09c134e7e5074cfca3ef64960bf401c7391c64`,
  and thainer tree SHA-256
  `bc36ef28c16dbca39911add53e9b9a96ebb23edf6c8b00555d5647ba8629c315`.
  These are deterministic synthetic/adversarial results, not a population
  benchmark or legal/compliance accuracy. Stage 8 exact-image acceptance and
  Stage 9 protected deployment are complete.
- Stage 8 candidate `8053c08404824cbc6eb121bdbe74abd6aa77a4fb`
  passed the first exact image/test/browser evidence set but is superseded for
  release because adversarial review found three closeout gaps: re-sync could
  overwrite release-owned Hosted VERSION, public acceptance did not enumerate
  additive routes through the organizer edge, and durable status still said
  Stage 8 had not started. At that review point the tree awaited a replacement
  exact commit/image binding; `f4d8f72d…` below supplied it and closed all three
  findings. At that review point no production mutation had occurred and
  production was still Hosted 2.5.0/16.
- Replacement candidate `f4d8f72dcad37bea267f2ca50b07447c16a2c517`
  passed corrected CI-equivalent `29/29`, parity `3/3`, joined local
  Priority/Standard text/PDF/queue/provider/artifact acceptance, exact image
  identity, and all three focused adversarial re-reviews. That closed Stage 8
  locally with no material disagreement before Stage 9 began.
- Protected production Pipeline #36531 on exact `ac33152a7ed3074858fcbbd712957536c4b39d68`
  passed check and deploy, then failed mandatory acceptance at the live custom
  result classification gate. The trap removed the candidate and restored exact
  healthy revision `dbcfe17b34744dc3e9a88e4099786a754fe903a6`; production was
  therefore still Hosted 2.5.0/16 at that point. The route/provider request returned a
  result. The first correction then conflated a truthfully classified
  `incomplete|unsafe` result with sufficient release usefulness. The final gate
  treats that outcome only as fail-closed safety evidence, retries through at
  most three fresh Standard authorities/approved runs, and still requires one
  `complete`, zero-leftover, warning-free result. Safety, exact protected-payload,
  digest/outbound/receipt/provider agreement remains mandatory on every
  classified attempt; unsafe content is never approved or displayed. That
  failure required a new commit and new web pipeline; the
  failed pipeline must not be retried.
- Replacement Pipeline #36534 on exact
  `54b5524c40b1175d8be1b929332716006e0311e4` proved the bounded live custom
  usefulness policy: attempts classified `unsafe`, `unsafe`, then `complete`,
  and internal Priority/Standard text/PDF/queue/provider/artifact acceptance
  passed. Credential-free public acceptance then failed only because it still
  searched for superseded App boundary copy. Automatic rollback again restored
  healthy `dbcfe17b…`; production remained 2.5.0/16 at that point. The assertion locks the
  current explicit organizer-proxy/Core raw boundary, exact approved Pathumma
  payload boundary, and PDF-not-sent wording. That failure required a new
  descendant and new web pipeline; #36534 must not be retried.
- Pipeline #36537 on exact `827e0601b52f022e97e5be8da84e0ef8e39504cd`
  completed the release. Live custom classifications were `unsafe → unsafe →
  complete`; Priority legacy, Standard text/PDF, queue/claim/provider/artifacts,
  40 public canonical/alias paths, near-match denial, report, resources, and log
  privacy passed. Post-restart public Chrome completed a real Standard custom
  preview→approval→queue→Pathumma→restored-result flow and End access. The
  64-state route/viewport matrix passed with no overflow, status, structure,
  storage, asset/font, or unexpected-console failure. The organizer plain-HTTP
  warning remains; HTTPS/TLS/HSTS is valid.

## Stage 5 status

- Stage 4C is verified locally at Core image
  `sha256:2582ecba14300dd816a7b788f562d6c70325a3098bffd8adaa57a86d6bd6b1eb`,
  revision `stage4c-final-local-contract`; the approved parser is
  `sha256:2e9244ee0eb465313a414274d53418525c1e6d7387e6d9f55b1270345791a91c`,
  revision `stage3-final6-local-contract`.
- Stage 5 is complete for the local-only candidate. The exact four-image
  revision is `stage5-final-local-contract-r3`: web
  `sha256:69b7129b0589df1f190767dd1f8b7247fcf6212dfb065e6c35aea1d14a3749f0`,
  API `sha256:e2a03cf7069b9fc8cb4be5c613df14d7d8e5e3ba9f8606dd0ade2ca43d20f2ab`,
  Core `sha256:2d03c7191b247bbb4c75d2c47728fc0c022881877e9acfc0a1bf6a912ad842a8`,
  and parser `sha256:98f46c99744fa9184fe17c3618944d9a28cf42727b810ac0bff51033b90f3cc2`.
  Creation times are respectively `2026-08-16T18:46:38.195506729Z`,
  `2026-08-16T18:46:36.355848559Z`, `2026-08-16T18:47:33.200293594Z`,
  and `2026-08-16T18:46:52.053046898Z`.
  The approved edit surface was the port-owned Core overlay and authority
  gateway, exact API Nginx proxy, four-service Docker/Compose wiring,
  release-source/rollback scripts, and their tests; manifest-pinned vendored
  upstream files remained out of scope.
- The local candidate may expose the approved 40 exact API locations. Deployed
  production remains Hosted `2.5.0` with exactly 16 public locations; all 24
  Hosted 3 additions remain unexposed in production. No deployment, public
  acceptance, version migration, or Stage 6 UI work has started.
- Evidence is current-source Stage 5/static/authority/rate/queue contracts,
  built-Nginx checks, caller-facing local Compose probe, Core/Parser parity
  `3/3`, legacy image integration `2/2`, parser lifecycle `3/3`, and the
  final 27-command pinned CI-equivalent check (exit 0). The single
  GPT-5.6 Sol/xhigh adversarial reviewer reported no material disagreement.
  Parser and Compose foundations retain network isolation, secretless
  Unix-socket transport, Core read-only socket access, health ordering,
  resource limits, cleanup, and runtime inventory controls.
- Stage 6 is now in progress for the local-only App and reference-page
  integration. Before product edits, the `stage5-final-local-contract-r3`
  images were checked locally under their `aiguardstage5-*` names and matched
  the documented digests; source contracts still prove the 40-location local
  candidate. A read-only public check returned `/api/health` version `2.5.0`
  and fixed `404` for the unexposed Standard-start path. No deployment, public
  acceptance, version migration, or production mutation occurred.
- The active Stage 6 caller probe is `https://127.0.0.1:20270`, a loopback-only
  self-signed TLS edge defined by `web/nginx.stage6-edge.conf` and
  `docker-compose.stage6-local.yml`. It proxies only same-origin candidate API
  calls and is not production TLS evidence. Chromium verified synthetic
  Standard start (201), session confirmation (200 with timing headers), and a
  protected custom-text preview. The current local source slice is
  `web/app.html`, `app.css`, `hosted3-app.js`, and `developers.html`.
- Stage 6 is complete locally. Hidden legacy workflow and cross-page source-copy
  gates are closed; executable behavior, complete failure/queue/browser, exact
  final images/full CI, and all three focused re-reviews pass on final3.
  Production remains Hosted 2.5.0 with exactly 16 public locations; no
  deployment or version migration has occurred.
- During the retained-workflow integration gate, the active result surface now
  owns compact raw-versus-protected working comparison, provider/timing/receipt
  evidence, glossary limits, protected exports, and a presenter/fullscreen
  action. The active Inspect task owns five synthetic scenario entry points.
  The executable zero-dependency behavior contract now proves all seven deep
  links, non-submitting scenarios, Inspect/report ownership, custom/PDF gates,
  presenter focus, provenance, and clearing. The hidden legacy wrapper has been
  deleted from the production App; full queue/error/browser lifecycle evidence
  remains open.
- The latest source-only parity pass adds a value-free Sensitive Data Map from
  current `/detect` fields, shows Section 26 only from Core-returned protected
  preview/result fields, derives an Executive Summary only from a verified
  custom execute result, exposes explicit zero-residual/zero-leftover evidence,
  and reports `/health` as liveness only. Custom restored DOM now requires exact
  pass/zero safety and restoration gates; PDF result validation rejects a
  `restored_text` field. Presenter fallback hides custom raw comparison. These
  changes pass the executable behavior contract and the provider-free secure
  built-caller parity slice. Retained-workflow parity is closed, but Stage 6 is
  still open pending complete PDF/queue/result failure-state evidence, final
  images, browser matrix, and all three re-reviews.
- A Stage 6-only fake Tokenmind service now runs solely in the loopback local
  Compose overlay with no production credential. The secure built caller
  completed synthetic custom and real fixture-PDF preview→queue→claim→execute
  journeys through the local 40-route stack. Browser inspection rejected the
  first PDF result because it displayed raw Markdown as one `<pre>`; the client
  now validates and renders only fixed provenance, heading, and paragraph nodes
  via `textContent`, rejecting HTML/link/image/table/code constructs. This is
  local fake-provider evidence only, not final-image or deployment evidence.
- The static-first `/developers` and six-scene Home/reference copy gates are now
  source-complete: exact starting rate/error groups are documented, and Home,
  Privacy, Help, Terms, and Downloads distinguish deployed Hosted 2.5.0 from
  the Standard/Priority local candidate and text-layer PDF→Protected Markdown
  without weakening the continuing PDF-redaction/OCR denial. Static and built-
  Nginx contracts pass; final viewport and reviewer evidence remains open.
- First-round Stage 6 reviews found and the current source fixes authority/end/
  cancel ambiguity, Inspect 401 clearing, queued/running mutation locks,
  uncertain execute no-retry truth, portable receipt provenance, custom
  Presenter privacy, task-specific result focus/headings, stable H1, complete
  no-JS mobile routes, duplicate live announcements, local-edge request logs,
  mobile PDF overflow, technical-first PDF reading order, and roughly 55 KiB of
  dead legacy App CSS. Real 390×844 browser evidence now reports zero PDF/result
  overflow and semantic protected-document headings/paragraphs. Exact final3
  focused re-reviews pass these fixes. A fresh signed-out App's handled
  `/api/auth/session` 401 remains the one explicit Chromium failed-resource
  exception required by the locked HttpOnly session contract; other console/
  CSP/resource errors remain blockers.
- The first exact Stage 6 candidate is superseded after a status-only reload
  could attempt claim without a capability. Exact final2 revision
  `stage6-final2-local-contract` is web
  `sha256:864ccedf7e3238118fa74437e0277d2c3208231611fce44a8eec68b53c1e6c23`,
  API `sha256:8975bc74107c3b89cae4b4d631bea5f2ec642f3b0afe46d5ba79f49c407ff91f`,
  Core `sha256:9783ac044fbdc887e729022db9cdcd264d32076644d4c080e61c170e5e453a8b`,
  and parser `sha256:a0b533aa9e4316db032189536947c483ae06626a0ec34cf86a2d1484219135b5`.
  Exact parity is `3/3`, legacy integration `2/2`, parser lifecycle `3/3`, and
  the expanded pinned check passes `28/28` in `193.9 s`. The built route/
  viewport matrix passes `64/64`; no-JS, reduced motion, fallback, Presenter,
  custom/PDF semantic result, log, temp cleanup, and zero-persistence evidence
  is recorded in the durable redesign document. Art, frontend/security, and
  UX/accessibility focused re-reviews each bind a final PASS to exact final3
  with no material disagreement. Stage 6 is complete locally; Stage 7 has not
  started and production remains Hosted 2.5.0/16 and unchanged.

# สถานะงาน (16 ส.ค. 2569 — Concept C Production Web Live)

## Current productionization candidate

- Hosted 3.0 implementation is active on branch
  `codex/production-web-redesign`. Production and `core/VERSION` remain Hosted
  `2.5.0`, while local Stage 1 contains an unexposed authority/timing
  foundation under the bounded port-owned overlay. Stage 0 passed the complete
  14-check native implementation/test
  baseline and independent art, frontend/security, and UX/accessibility closeout
  review on 2026-08-16. Stage 1 authority/timing implementation, rebuilt-image
  verification, expanded 15-check baseline, and all three independent reviews
  passed. Stage 2 approval/custom-text-preview implementation is complete:
  the local port-owned overlay contains an encrypted content-stateless approval
  engine, deterministic `pg-v1` protection, and an internal provider-free
  custom-text preview handler. Its sixteen focused tests, including exact
  initial/pre-mint/deadline timing boundaries and blocked/uncertain null timing,
  concurrent one-use consumption, Token-only document tickets, sensitive-fact
  cleanup, and single-worker fail-closed startup, pass. The check job now pins
  exact Alpine `py3-cryptography=42.0.7-r0`, and the focused test passes in the
  digest-pinned GitLab `check` job image; deploy/acceptance/ops do not inherit
  that package. The Core runtime remains separately locked to
  `cryptography==50.0.0`.
  The final expanded 16-check baseline passed. Final local Linux image
  `sha256:8b743aa18fd9f03741b99cc997ac590bb1f881b92277ead7401475e0dd1879a9`
  matched all ten current gateway/auth/Hosted3 Python sources byte-for-byte; its
  real provider-free Standard preview replaced synthetic Thai NAME/EMAIL/PHONE,
  omitted raw input, produced deterministic pg-v1 output, and succeeded without
  a provider credential. The same image rejects `UVICORN_WORKERS=2` before any
  manifest-pinned application import.
  Independent art-direction/scope, frontend/product-security, and UX/lifecycle
  final re-reviews all passed. Stage 3 secretless text-layer PDF implementation/
  test gate has passed locally again after the final transport/semantic
  correction; all three independent closeout reviews passed. Stage 3 is complete
  and Stage 4 queue/scheduler implementation has started. Its
  Stage 3A history began with a hardened, still-unexposed parser candidate:
  hash-locked pikepdf `10.10.0` with bundled qpdf `12.3.2`, pdfplumber `0.11.10`,
  PDFium `5.12.1`, a bounded Unix-socket protocol, a deterministic fictional Thai
  résumé PDF, fixed active-content/text-layer/raster/visible-text gates, and local
  parser image
  `sha256:6e1047529f4e1bda5a0e293d3deaa11ccbec8a2e85dda4537866b33d55b1aac5`.
  The fixture renders cleanly and the parser returns one page, 31 immutable
  segments, and `omitted_visual_page_numbers:[1]`. The first lifecycle review's
  thread-timeout and swallowed-unlink blockers are fixed: each parse runs in a
  killable child that is reaped before capacity is released, framing/body work is
  time-bounded, worker output is reconstructed through a strict allowlist, and a
  private-spool unlink failure stops parser PID 1 with exit `70`. Current source+
  image tests pass `11/11`, container lifecycle tests pass `2/2`, and the real
  parser output passes the final Stage 2 protector in Token mode with 11 detected
  entities across eight types and no residual block. Invisible/clip-only render
  modes `3` through `7`, transparent text, and recursively reachable page/Form clipping paths
  that cannot be visibility-resolved are rejected under bounded depth/cycle
  validation. The official Moby `seccomp/v0.2.3`
  deny-by-default profile does not
  allow `io_uring_setup`, and all Python dependency downloads remain hash-locked.
  Independent art/product, frontend/security, and UX/lifecycle re-reviews all
  passed against that exact image. Stage 3A is closed; Stage 3B Core Unix-socket
  client and provider-free document-preview integration is now in progress.
  Stage 3B found a value-free false `LOCATION` signal formed only across the
  boundary of two joined protected segments. The outbound gate was retained;
  the fictional achievement line was rewritten and the deterministic scenario
  pin advanced to
  `57ffcd9cddfe5abbe3b5b276ad93d22a549d386f01967344315a97cbafc51e6c`.
  The provisional segment-aware Token path now preserves all 31 segments and
  passes the combined gate with 12 detections across nine types and protected
  digest `4e402d73c75b8699706690b7b4cb4a1c2e789d97c32daae1de4eb0999ab5d03f`.
  This is not final Stage 3B image/reviewer evidence.
  Core now also contains the strict streaming Unix-socket client, source-free
  synthetic/uploaded document-preview DTO and approval service, segment-aware
  Token protection, exact protected-size/timing caps, and a source-anchored
  artifact validator that accepts only role/segment IDs and renders fixed Thai
  headings plus escaped Markdown/plain text/semantic HTML with provenance.
  Focused preview `4/4`, artifact `5/5`, real two-image UDS `4/4`, and real
  parser-to-protector scenario tests pass. Compose now includes an internal
  no-network, read-only, non-root, cap-dropped, seccomp/resource-bounded parser
  with private work tmpfs and a socket-only volume mounted read-only by Core. An
  expanded current-source parser corpus passes `16/16` in the pinned dependency
  environment, including modes 3-7, recursive clipping, inert/active structures,
  exact text/segment/page/dimension/raster limits, compressed/inline content,
  cycles and resource bombs. That corpus found and fixed a direct-object wrapper-
  identity reuse defect in the recursive object walker; the valid external-file-
  reference regression now fails closed. This is not yet final rebuilt-image
  evidence. The subsequent Stage 3C local implementation/test gate first passed
  against Compose-built parser image
  `sha256:a656da8b5ea16828f943931fe5bcb9d971ca112bd39b61c21e4f17e6b392c88b`
  and Core image
  `sha256:54df5b2206d8d9ec70480a995e69c856abf44ef6d8d104b5a6c50f2d5461647d`,
  both labelled `stage3-final-local-contract`. Exact image evidence passes parser
  `16/16`, lifecycle `3/3`, Unix-socket `4/4`, real scenario gate `1/1`, and
  source/image parity `3/3`; the complete 19-command native check surface passes.
  The four-service candidate has healthy parser/Core containers, exact no-network/
  read-only/non-root/cap/seccomp/resource/socket controls, 31 segments and 30
  separators through the real Compose socket, and zero fixture/ticket/synthetic-
  secret markers in the bounded logs. That image pair is now superseded
  intermediate evidence: Stage 3D preparation found that document tickets used
  the custom-text prompt binding. That intermediate source selected bindings by
  ticket kind and locked document branches to
  `structure-protected-document-json-v1`; the later Stage 3D classification
  protocol supersedes that document revision;
  focused approval `16/16`, preview `6/6`, artifact `6/6`, and authority `10/10`
  tests pass. Preview warnings now always disclose selectable-text-only/OCR/
  visual-layout limits and add exact omitted pages when present. Their outcome
  wording is status-aware: only success says detected PII was replaced, while
  blocked/uncertain state that no usable protected result was returned and no
  protected text was sent to Pathumma. Replacement image/parity/Compose evidence
  now passes against parser image
  `sha256:2413c8bf2f39163f26152055f1c4405515d2f6f8a3bdafcc6431eb79b571f335`
  and Core image
  `sha256:ab25c1e65c5c65ffdccbabb4c5f0daab03a6106072692b298a6210155eee173c`,
  both labelled `stage3-final2-local-contract`: parser `16/16`, lifecycle `3/3`,
  Unix socket `4/4`, parity `3/3`, scenario gate `1/1`, and the complete current
  native check surface `20/20`. The exact healthy Compose runtime preserves the
  parser isolation/resource controls and read-only Core socket mount; its real
  source-free scenario produces 31 segments/30 separators, 12 detections across
  nine types, the document-specific prompt binding, four truthful warnings, and
  no protected marker in bounded logs. Independent Stage 3C closeout review is
  in progress. The image pair is now superseded by the measured Stage 3D client/
  cap correction described next; a final rebuild is required. This remains local
  evidence.
  An exact opt-in Stage 3D harness now locks the immutable protected-segment
  request. Live Pathumma evidence showed that the proposed 80-segment envelope is
  not usable: the generic 1,024-token client stopped non-finally, and a 4,096-token
  document request still returned a truncated 3,701-byte JSON body. A later test
  at the former 16,000-code-point/48-KiB internal hard stop returned a truncated
  1,621-byte body. The provider-executable cap is therefore 8,000 protected code
  points, 32 segments, and 9,120 encoded request bytes while the parser retains an
  independent 80-segment safety bound. Repeated grouped-ID and role-vector live
  tests exposed truncated, duplicate, missing, or off-by-one model results; AI
  Guard did not repair or accept them. Current source uses
  `structure-protected-document-classifications-v1`: Pathumma returns exact
  `{segment_id,role}` rows in input order and AI Guard validates every position,
  groups deterministically, and renders fixed headings. The real default résumé
  passed at 31 segments/3,962 request bytes/5,827 ms. The 8,000-code-point edge
  passed at 1 segment/8,126 request bytes/1,271 ms. The Thai-plus-Token 32-segment
  edge reaches exactly 9,120 request bytes and passed three consecutive runs at
  6,010/5,878/5,956 ms with exact 1,589-byte validated responses. No provider-
  authored content or credential was emitted. Provider transport runs in a
  killable child, streams the outer response under 32 KiB before parsing, retains
  a separate 32-KiB extracted-response cap, and enforces an absolute parent-owned
  200-second deadline. Focused preview and artifact/transport tests pass `7/7`
  and `7/7`.
  The following final3 image/parity/Compose result is now superseded because it
  predates those request/response/deadline changes. It used parser image
  `sha256:a2455a13f2e214b31f76bdca57950a301d219c4f6711e22102ae639217d2f65e`
  and Core image
  `sha256:05de433e87497cf8a4a42447cb4b58495551724aa6d1600f4230f577a8d29cfc`,
  both labelled `stage3-final3-local-contract`: parser `16/16`, lifecycle `3/3`,
  Unix socket `4/4`, parity `3/3`, real scenario `1/1`, preview `7/7`, artifact
  `6/6`, and the full native check surface `20/20`. The healthy exact Compose
  runtime reported the 32-segment/4,096-token contract, the executable 31-segment
  scenario, unchanged isolation/socket controls, and zero bounded log marker hits.
  A transient final4 rebuild produced parser image
  `sha256:897b35f5e1be3c35bcc93249b8c0f1aa871013e8a7becea8234c93af71b74ef0`
  and Core image
  `sha256:a010149f1a804f26f50de8537b10162c981c03938ca8de800fbd9d5b2d2ebe09`,
  both labelled `stage3-final4-local-contract`; parser `16/16`, lifecycle `3/3`,
  Unix socket `4/4`, scenario `1/1`, parity `3/3`, and native `20/20` passed, but
  those bytes predate the classification protocol and are not closeout evidence.
  Final5 replacement images are parser
  `sha256:afb81cbdd8cf409c8bf7c40401f0495295637df8571e9fe0d5eadd772b9df3c5`
  and Core
  `sha256:83645bfb64269ffde2fca8f30c1821c2e4c02e3a89bfb656edabbcc7a8a31c0b`,
  both labelled `stage3-final5-local-contract`. Exact image evidence passes
  parser `16/16`, lifecycle `3/3`, Unix socket `4/4`, scenario `1/1`, parity
  `3/3`, authority `10/10`, approval `16/16`, preview `7/7`, artifact/transport
  `7/7`, and native `20/20`. Both live boundaries also passed directly from the
  final5 Core image: Thai-plus-Token 32 segments/9,120 bytes in 6,094 ms and the
  8,000-code-point edge in 970 ms. The exact healthy Compose runtime retains the
  parser no-network/read-only/non-root/cap/seccomp/resource/tmpfs controls and a
  read-only Core socket mount; the real scenario preserves 31 segments/30
  separators, 12 detections across nine types, 3,962 request bytes, and the
  classification prompt, with zero bounded log marker hits. Independent review
  then proved final5 could allocate a transparently decompressed HTTP body before
  its wire limit and had no durable semantic-usefulness assertion for the default
  résumé. Current source requests identity encoding, rejects every non-identity
  response before iteration, caps raw wire bytes, and adds a protected opt-in
  gate for the reviewed role distribution, fixed heading order, provenance, and
  exact segment coverage. Final5 is therefore superseded. Final6 images are
  parser
  `sha256:2e9244ee0eb465313a414274d53418525c1e6d7387e6d9f55b1270345791a91c`
  and Core
  `sha256:21792b0e05d161907000e4c5cc8b7e8f655953d8efd62aef8f3fab8e8ea1255b`,
  both labelled `stage3-final6-local-contract`. Exact-image parser `16/16`,
  lifecycle `3/3`, Unix socket `4/4`, scenario `1/1`, parity `3/3`, preview
  `7/7`, artifact/transport `7/7`, and native `20/20` pass. The gzip fixture is
  rejected before raw-body iteration. Live exact-image boundaries pass at
  32 segments/9,120 bytes in 6,040 ms and 8,000 code points in 1,169 ms. The
  default résumé semantic gate passes in 5,702 ms with 31 segments rendered once
  across seven fixed sections: identity 3, contact 6, experience 8, education 3,
  skills 4, achievements 5, and other 2; provenance and fixed heading order pass
  without emitting source/provider content. The exact healthy Compose pair uses
  these digests, keeps parser `/work` and Core `/tmp` empty, returns one page/31
  segments/30 separators, and has zero bounded sensitive-marker log hits. Stage
  3's local implementation/test gate passes; independent art/product,
  frontend/security, and UX/lifecycle reviewers each report a clear pass on
  final6. Stage 3 is complete. No public route, deployed parser image, or
  production evidence exists yet.
  Stage 4A is complete and was limited to a provider-free, content-free
  in-memory scheduler/capability foundation plus focused tests. Its local
  implementation/test gate passes: independently derived AES-GCM
  queue and claim envelopes bind exact authority/session/subject/boot/JTI/slot/
  revision/deadline facts; full approval facts are only transient during strict
  validation, active claim polls retain just the opaque claim-token binding, and
  the running execution object is repr-suppressed with explicit cleanup. A
  single-lock, two-slot scheduler bounds active rows
  at 12 (eight Standard, four Priority), applies the exact global 3:1 claim-grant
  sequence under contention, borrows idle slots, makes status read-only, moves a
  first missed claim to the tail, expires a second miss, invalidates cancelled/
  terminal capabilities. Priority active-row
  ownership is per issued opaque subject, while status/claim/cancel remain bound
  to the exact verified session. Claim dispatch now requires the entire 15-second
  handoff to fit before queue expiry rather than issuing a token with a truncated
  promise. The Stage 4A queue contract passes `15/15`,
  including minimal active-poll memory and bounded terminal-history eviction
  without false active saturation plus exact `15/14`-second handoff boundaries;
  a foreground poll that crosses its deadline returns fixed `queue_expired`
  while read-only status reports `expired` / `deadline_expired`.
  approval remains `16/16`, check-only CI includes the new queue contract, and
  the complete native surface passes `21/21`. At the Stage 4A closeout this was
  local source/test evidence with no queue HTTP handler or provider/legacy
  integration, and no Core image had been rebuilt for Stage 4. The fresh Stage 4A
  native surface passed
  `21/21`; independent art/product, frontend/security, and UX/lifecycle reviewers
  each report a clear pass on the exact current bytes. Stage 4A is complete and
  Stage 4B internal execute/compatibility integration is now in progress. It is
  split into B1 internal queue HTTP/disconnect handling, B2 three queue-bound
  execute services, and B3 legacy `/roundtrip` admission. B1 now has exact
  internal join/status/claim/cancel handlers, value-free HTTP v2 errors, and an
  ASGI-disconnect race that removes claim eligibility before selection. Initial
  reviews found response-after-disconnect, slot leakage, partial-body, immediate-
  error, double-response, and stale-deadline defects; those exact paths are now
  covered by focused fixtures. The final transport review then proved that ASGI
  cannot be used to confirm browser receipt: pinned Uvicorn returns silently from
  `send()` after some peer losses and also emits a normal post-response
  `http.disconnect` after successful responses. Both earlier watcher-based
  confirmation designs are therefore superseded.
  Current source uses execute-as-acknowledgement. A selected HTTP claim has at
  least 20 seconds of server-side validity; its shared record/token/wire integer
  deadline is rounded upward by less than one second, never truncated. At most
  five seconds are budgeted for response transmission, leaving at least 15
  seconds of server-side validity for the official client's immediate execute
  request. This is not a claim about when browser receipt occurs. That
  exact execute request is the only receipt evidence and atomically starts the
  running provider state. No execute means no provider contact and, at expiry,
  the normal first-miss tail demotion or second-miss terminal expiry. Explicit
  send error, timeout, or controller cancellation still abandons the pending
  claim at zero misses and retains fairness; a silent peer loss that ASGI cannot
  distinguish is safely bounded by the less-than-21-second missed-claim rule. The watcher
  is cancelled before the response so Uvicorn's normal completion sentinel cannot
  revoke a valid claim. Connected queued timeout creates no claim. Non-claim
  transport failures remain single-response passthroughs.
  The focused HTTP suite passes `17/17` and the scheduler suite passes `20/20`,
  including `.999` fractional grant and full `5+15` server-side boundary
  fixtures. Prior `22/22` native runs predate these bytes and are historical; a
  fresh exact-current native rerun passes `22/22`. Independent art/product,
  frontend/security, and UX/lifecycle re-reviews each report a clear pass. B1 is
  complete. B2 queue-bound execute-service integration is complete and B3
  legacy `/roundtrip` queue admission is now in progress. The
  current local overlay has an initial strict `ExecuteService` plus internal
  handlers for custom text, pinned synthetic-document, and uploaded protected-
  text execution. A current queue capability/claim must atomically enter running
  before provider contact. Custom execution reproduces source/protected digests,
  rescans before every bounded retry, and restores only through the transient
  mapping. Synthetic execution reparses and revalidates the pinned PDF; uploaded
  document execution accepts only approval-bound protected bytes. Both document
  paths send only protected immutable segments, validate the content-free role
  AST, render fixed Protected Markdown/plain text, and never restore PII. Fixed
  failures release the slot with value-free reasons and clear approval/mapping/
  artifact state. Receipts and document responses exclude source/original-token
  pairs and mappings; custom execution intentionally returns reviewed protected
  text plus a restored answer that may contain the caller's original PII, while
  never returning the transient mapping object. Review then found that the
  synthetic-document provider call blocked the ASGI loop and that an unrelated
  late response failure could be misclassified as `residual_pii`; the old
  `7bf5f768...`/`stage4b2-final2-local-contract` image is therefore superseded.
  Current source offloads the complete synthetic path, locks a slow-provider
  heartbeat, restricts `residual_pii` to the outbound gate, and reports unrelated
  late failures as `internal_error`. The inherited custom provider adapter was
  also post-buffer-only; current source replaces it with a killable child whose
  parent owns a 60-second absolute deadline per attempt, requests identity
  encoding, caps declared/chunked raw response bytes before JSON parsing, and
  enforces 32,000 code points/96 KiB after parsing. Fixed retryable failures keep
  the approved three-attempt maximum within the sub-200-second custom envelope.
  Preview enforces the matching 96-KiB protected-payload cap before ticket mint
  with fixed `422 provider_payload_too_large`; valid approvals cannot be stranded
  by an execution-only byte limit. Malformed operator provider construction maps
  to `provider_configuration`, separately from response-protocol failures.
  The focused B2 source suite passes `9/9`,
  including strict internal
  HTTP routing and zero provider contact for changed source/digest, stale claim,
  schema, and outbound-gate failures. CI has 23 native commands and the fresh
  exact-current native surface passes `23/23`. Historical real-detector evidence
  from the superseded image passed `1/1` with provider input containing no
  original name/email/phone from the synthetic custom-text fixture and exact
  restoration of that custom-text fixture afterward. This validates only the
  custom-text restoration branch; the synthetic-document/PDF branch continues
  to return protected artifacts without PII restoration. This is
  historical local evidence only. The replacement Core image is
  `sha256:cee123fe5ad397079d23ed1d78e9c1c8fcec574e39e2e22043259443db813d4c`
  labelled `stage4b2-final3-local-contract`; the exact Stage-3 parser image is
  `sha256:2e9244ee0eb465313a414274d53418525c1e6d7387e6d9f55b1270345791a91c`
  labelled `stage3-final6-local-contract`. Exact parity passes `3/3`, focused
  execute passes `9/9` inside the read-only/networkless Core image, real-detector
  custom-text flow passes `1/1`, and invalid operator configuration maps to the
  fixed configuration error in-image. The older parser tag failed parity and is
  not counted. Independent art/product, frontend/security, and UX/lifecycle
  reviewers each rechecked the exact replacement image/source/status and report
  a clear pass; B2 has no remaining material disagreement. Nginx
  continues to deny all 24 planned routes, and no public execute route, browser
  UI, version bump, production image, or deployment is claimed. B3 local source
  now wraps the existing vendored `/api/roundtrip` handler without editing
  `core/app/**`: Priority-only calls wait up to five seconds for the same two
  scheduler slots, retain the original FastAPI request/response and fixed
  `429 rate_limited` contract, hold the slot across the complete legacy provider
  call, and release it in `finally`. The internal entry stores no request body,
  approval, or caller capability and participates in the shared 3:1 cursor,
  capacities, owner limit, and pruning. The focused source contract now passes
  `12/12`, and the exact current local Core image passes `2/2` read-only/
  networkless byte-parity and real-FastAPI legacy-route checks, including
  validation precedence, exact five-second `429 rate_limited` denial with zero
  provider contact, headers/CORS behavior, provider error, disconnect,
  cancellation, response-send lifecycle handling, and request-text-free Core
  stdout logs. Independent review reproduced a validation-precedence blocker:
  endpoint-body text/mode/provider checks could wait behind occupied slots. The
  port-owned wrapper now runs those exact legacy checks before admission; focused
  source and image fixtures prove immediate legacy errors, zero provider contact,
  and no scheduler mutation. The rebuilt image resolves to
  `sha256:706051f7d132d3ee18c4d7abc3e1b517ceec002fe8983d8bcf279ab4914fffdc`
  with revision `stage4b3-final2-local-contract`; its image gate passes. The
  prior final1 image/full-native evidence is superseded. The fresh
  Docker-executor-style native surface passes all `24/24` commands, including
  built Nginx/public-surface, secret, log, and Compose-isolation checks. The
  native simulator now honors the check job's AES-GCM-specific `before_script`,
  with a focused GitLab contract regression locking that behavior. The same
  independent GPT-5.6 Sol backend/product/security reviewer reconciled the
  correction and found no material blockers. Stage 4B3 is complete; Stage 4C
  is now in progress as the exact-image, concurrency, lifecycle, integration,
  and review closeout. The owner has authorized one consolidated independent
  GPT-5.6 Sol reviewer at xhigh reasoning effort for this narrow non-UI Stage
  4C closeout only, in place of the usual three reviewers to conserve quota.
  This exception does not alter the three-reviewer requirement for the future
  Stage 6 production UI. None of these local changes has been deployed.
  The distinct Stage 4C Core candidate is
  `sha256:2582ecba14300dd816a7b788f562d6c70325a3098bffd8adaa57a86d6bd6b1eb`
  (`stage4c-final-local-contract`, created `2026-08-16T17:43:44.421095077Z`),
  with the exact Stage 3 parser unchanged at
  `sha256:2e9244ee0eb465313a414274d53418525c1e6d7387e6d9f55b1270345791a91c`
  (`stage3-final6-local-contract`). The deterministic Stage 4C aggregate runs
  59 existing behaviour tests across scheduler, HTTP claim lifecycle, execute,
  and legacy compatibility and passes `4/4` on source and from the exact
  read-only/no-network candidate image. Candidate parity passes `3/3`, legacy
  FastAPI/slot integration `2/2`, the real-detector fake-provider custom
  preview→queue→execute image probe `1/1`, and the full current pinned
  Docker-executor-style check surface `25/25` in 54.6 seconds. It includes the
  built 16-route Nginx boundary, denial of all 24 planned paths, Compose
  isolation, source/build context, and value-free secret/log contracts; `git
  diff --check` passes. This remains synthetic/local candidate evidence pending
  the required one-reviewer consolidated Stage 4C closeout, not a deployment,
  public exposure, UI change, version bump, or Stage 5 start.
  The first consolidated review found a material verification gap rather than
  an observed scheduler failure: cancel and execute were previously tested only
  independently, and a 3:1 selection fixture used a fixed sleep. The corrected
  overlay reports a valid capability invalidated by a winning cancel as
  `queue_not_ready`; generic `queue_invalid` remains for forged or cross-bound
  capability. A 16-round barrier-backed same-entry cancel/execute race now
  proves either cancellation with no slot/provider authority or exactly one
  running execution with `provider_already_running` cancellation. The 3:1 test
  now waits for both contenders at the bounded eligibility seam. Scheduler is
  `21/21`; the rebuilt candidate and every exact-image gate passed, and the
  full final native surface reran `25/25` in 54.6 seconds. The same reviewer is
  now performing the required focused re-review.
  The same independent GPT-5.6 Sol/xhigh reviewer completed that focused
  re-review without edits and issued a final **no material blocker** verdict.
  It independently reproduced the corrected candidate digest, scheduler
  `21/21`, exact-image Stage 4C aggregate `4/4` over 59 behaviours, parity
  `3/3`, valid-cancelled-claim `queue_not_ready` versus tampered-capability
  `queue_invalid`, and `git diff --check`. Stage 4C is complete with local,
  synthetic evidence only. Production remains Hosted `2.5.0` with exactly 16
  public routes; Nginx still denies all 24 planned Hosted 3 paths. No Stage 5
  route exposure, UI work, version bump, production image, deployment, public
  exposure, or live-provider/production validation occurred. Stage 5 is the
  next safe stage and has not started.
  Stage 0 added
  only a machine-readable target fixture, a Hosted 3.0
  contract fence, a bounded port-owned overlay prefix, and their CI requirements.
  The approved ten-stage implementation and per-stage exit gates are authoritative
  in `docs/production-web-redesign.md`. The local Standard/Priority authority and
  timing foundation and provisional parser work exist only on the local branch.
  No browser-accessible Standard entry/document preview, public PDF parser or
  queue route, 40-route proxy, Hosted 3.0 UI, version bump, or deployment has occurred
  yet. Nginx still denies all 24 planned canonical/alias routes.
- Concept C production web is live at exact revision
  `dbcfe17b34744dc3e9a88e4099786a754fe903a6`. Feature Pipeline #36392 and
  protected-main check-only Pipeline #36393 passed, followed by complete
  protected production Pipeline #36394: check #141734, deploy #141735,
  acceptance #141736, logs #141737, exact-revision/process inspection #141738,
  and restart/recovery #141739 all passed. Public Chrome after restart verified
  all six routes, API health/session boundaries, branded versus fail-closed
  404s, all required desktop/tablet/mobile widths, reduced motion, keyboard
  entry, self-hosted font loading, same-origin assets, no broken images, and no
  horizontal overflow.
- The first redesign attempt at `9995532a` in Pipeline #36391 deployed cleanly,
  then safely rolled back to `75aaa7e6` because public acceptance still expected
  `GET /api/auth/session` to return `404`. The joined public contract is the
  intentional JSON `401 authentication_required`; `dbcfe17b` corrected and
  independently reviewed that assertion before the successful redeployment.
- Remaining web content inputs are owner facts, not unimplemented UI: approved
  operator/jurisdiction/policy-date wording, a publishable private privacy and
  security contact, an accessibility-feedback channel, and organizer metadata-
  policy availability. The live pages disclose the limitation rather than
  inventing details. The organizer edge still lacks a plain-HTTP-to-HTTPS
  redirect under the documented 2026-08-15 owner risk decision; HTTPS TLS/HSTS
  passes, but plain HTTP is not represented as secure.
- รอบ deploy เว็บไซต์วันที่ 16 ส.ค. แยก Concept C Home ออกจาก Hosted `/app`
  จริงแล้ว พร้อมหน้า `/downloads`, `/privacy`, `/help`, `/terms`, branded human
  404, ฟอนต์ Anuphan ที่ self-host, revision-B2 logo และ exact Nginx allowlist
  Home ไม่มี invite/API runtime ส่วน `/app` คงสาม workflow, Guided Demo,
  `/guard`, evidence/presenter tools, session/request safety และขอบเขต Hosted
  ตามเดิม
- ก่อนเริ่มรอบนี้ known-good live/rollback baseline คือ exact
  `75aaa7e61b529204b5cf1294aae37d3e99d389ae` จาก protected Pipeline #36309
  ที่ผ่าน check, deploy, public acceptance และ ops recovery แล้ว Candidate เว็บ
  ใหม่ผ่าน local GitLab-equivalent checks ทั้ง 13 รายการ, built-image Chrome
  matrix และ repeated independent art/frontend/UX review โดยไม่มี material
  disagreement ก่อนผ่าน protected-main Pipeline #36394 และ public caller-facing
  acceptance ของ exact revision ตามหลักฐานปัจจุบันด้านบน
- routing ใหม่ปิด source `.html` aliases และ filename/asset near-match แบบ fixed
  unbranded 404; เฉพาะ unknown extensionless human route ได้ branded 404
  Legacy fragments หกตัวไม่ถูก sticky header บัง และ Guided Demo/provider
  evidence มี handoff ไป `/app` ที่ตรง fragment App แบบไม่มี JavaScript จะ inert
  จน bootstrap สำเร็จ ส่วน signed-out workflow hash จะกลับ access gate ก่อนแล้ว
  restore หลัง session ยืนยัน

- เริ่มจาก evaluation/main exact
  `c02ec1c82e22d0e200fbfad68556c169eba68007`; known-good deployed runtime
  ยังเป็น `72e18bbe723adaf54c847e4b17c2177dfa60dd68` จาก Pipeline #35744 จนกว่า
  descendant นี้จะผ่าน feature CI, independent review และ protected-main
  `check → deploy → acceptance` จริง
- production web tree ถูก fast-forward เข้า protected `main` แล้ว; corrective branch
  `codex/aift-production-acceptance-fix` แก้เฉพาะ acceptance transport หลัง
  Pipeline #36033 และ VERSION ยัง `2.5.0`
  และต้องคง 16 routes, public `/redact-pdf` + `/v1/redact-pdf` fixed 404,
  Tokenmind provider เดียว, no mapping และ no browser persistence
- live baseline เมื่อ 13 ส.ค. พบว่า plain HTTP ยังคืน app/API 200 และ HTTPS เดิม
  ไม่มี HSTS Candidate จึงเพิ่ม fixed-host 308 จาก forwarded original scheme +
  HSTS ทั้ง web/api และเพิ่ม public-edge acceptance จริง Fixed-host redirect ยังคง
  อยู่และต้องทำงานแบบ fail-closed หาก organizer ส่ง original scheme ในภายหลัง
- Owner รับความเสี่ยงเฉพาะ competition deployment เมื่อ 15 ส.ค. ว่า organizer
  public edge ที่ไม่ทำ HTTP-to-HTTPS redirect เป็น external platform limitation:
  public survey ที่ Owner ให้มาพบว่า host ของอีก 14 ทีมไม่มีทีมใด redirect ไป
  HTTPS; ทีมที่ตอบได้คืน HTTP 200 ทั้งหมด ยกเว้น Team 15 ที่ redirect ไป path อื่น
  บน HTTP และ Participant Guide ระบุ public HTTPS URL แต่ไม่ได้กำหนด team-level
  HTTP 308 ชัดเจน Acceptance จึงรายงาน status ที่ไม่ใช่ 308 เป็น structured
  `PUBLIC_EDGE_WARNING` ซึ่งอย่างเดียวไม่ทำ rollback ทั้งนี้ plain HTTP ยังไม่
  ปลอดภัยและ limitation นี้ยังไม่ได้ถูกแก้
- product surface ปัจจุบันเป็น Desktop-first: CTA หลักพาไปเลือก Desktop 3.0.0,
  Hosted Web App เป็น Private Beta ลำดับรอง และอธิบายก่อน input ว่า Desktop
  ตรวจจับ/ปกปิด/vault/restoration/report ในเครื่องโดยไม่มี provider command
  ส่วน Web รับ raw text ที่บริการ Team 08 และ Safe AI ส่ง Pathumma เฉพาะข้อความ
  ที่ปกป้อง+ตรวจซ้ำแล้ว Quick Start/หลักฐานขั้นสูงเป็น optional disclosure และมี
  static `/privacy`, `/terms`, `/help`, `/downloads`, robots,
  sitemap หน้า download ชี้ Release v3.0.0 ที่ตรวจ HTTP 200 แล้วสำหรับ Desktop
  Windows/Linux/macOS และ manual Extension ZIP โดยไม่สร้าง Store link ที่ยังไม่มี
  และ pin SHA-256/ขนาด/asset identity, SHA256SUMS กับ GitHub provenance Source
  contract จะ fail หาก redirect ออกจาก release-assets.githubusercontent.com,
  asset ถูกแทนที่ หรือ checksum/size ของ artifact ที่ประกาศเปลี่ยน
- Chrome Web Store Developer Dashboard ที่ตรวจแบบ read-only เมื่อ 14 ส.ค. แสดง
  AI Guard 3.0.0 เป็น Draft, ปุ่มส่งตรวจสอบยัง disabled และยังไม่เผยแพร่ หน้าเว็บจึง
  ระบุว่า “เตรียมส่งตรวจสอบ · ยังไม่เผยแพร่” พร้อมบอกว่า manual ZIP ต้องใช้
  Desktop 3.0.0 สำหรับ Native Messaging, แตกไฟล์แล้ว Load unpacked และคำเตือน
  ความน่าเชื่อถือของ OS อาจปรากฏเพราะเลื่อน code signing โดยไม่ชี้ให้ข้ามคำเตือน
  พร้อมเตือนว่า In-page Mask เริ่มหลัง raw text เข้า provider-controlled DOM แล้ว
  และ Side Panel เป็น raw-entry boundary ที่แข็งแรงกว่า
- invite gate ยังอยู่เพื่อคุม provider cost โดยไม่สร้าง account/database Session
  เก็บเฉพาะ SHA-256 token fingerprint+expiry สูงสุด 256 ค่าใน process, logout
  revoke replay และ restart invalidate session เดิม cookie ยังคง Secure/HttpOnly/
  SameSite=Strict/30 นาที
- nginx แยก global/public/work/provider request+connection lanes, ลด body cap เป็น
  128 KiB (login 8 KiB), ไม่ส่ง client IP เข้า core และ application log เหลือ
  fixed operation/surface, method, status, bytes, duration โดยไม่เก็บ IP/target/
  query/body/cookie
- hosted image ไม่ติดตั้ง/prewarm Paddle OCR ที่ public ใช้ไม่ได้แล้ว และ verify
  offline thainer asset tree กับ Sprint 3 digest ระหว่าง build Container เป็น
  read-only/no-new-privileges/PID bounded; core cap-drop all, tmpfs 128 MiB และ
  memory 2 GiB ต้องผ่าน exact-image resource acceptance ก่อน deploy
- healthcheck ใหม่ exit service หลัง local failure ต่อเนื่อง 3 ครั้งเพื่อให้
  `restart: unless-stopped` ฟื้น process; graceful stop 210 วินาที Deploy helper
  เก็บ previous image IDs + historical Compose และ rollback exact prior revision
  เมื่อ post-mutation health/stale gate ล้ม
- Section 26 report wording ถูก project ผ่าน port-owned hosted adapter เป็น
  heuristic review signal ที่ต้องประเมินบริบท ไม่แก้ vendored detector/core
  75 ไฟล์จาก `44ef30b`
- protected-main Pipeline #36033 ที่ exact `0c10f7ed222a7840cc6af8db2fbd455be7f8c53b`
  ผ่าน check+deploy แต่ acceptance พบว่า route probe เดิมพยายาม copy เข้า
  read-only `/app`; acceptance trap จึงคืน exact runtime
  `72e18bbe723adaf54c847e4b17c2177dfa60dd68` healthy ตามนโยบาย ไม่ปล่อย
  candidate ที่ยังไม่ accepted ค้างอยู่ การแก้ใช้ stdin เข้า `python -` ภายใน
  container และผ่าน local read-only report probe โดยไม่อ่าน secret ออกมา
- protected-main web Pipeline #36253 ที่ exact
  `6ce57356540c5f3b47b8ea12a601039f9e8582e3` ผ่าน check+deploy และ internal
  platform acceptance ผ่าน auth, 16-route allowlist, live Pathumma roundtrip,
  report และ sensitive-value log scan แต่ public edge คืน HTTP 200 แทน 308
  ที่ `/?sentinel=must-not-reflect` Acceptance trap คืน exact `72e18bbe...`
  และ Job #140572 ยืนยัน web/api/core revision ตรง, healthy และอยู่ใน resource
  limit แล้ว ประวัติ rollback นี้ต้องเก็บไว้ หลัง owner decision วันที่ 15 ส.ค.
  เฉพาะ failure นี้ถูกจัดเป็น external warning; ไม่ใช่หลักฐานว่า HTTP ปลอดภัย
- strict log audit หลัง rollback พบว่า Uvicorn access stream ยังมี client IP/port
  metadata แม้ไม่มี body, prompt, cookie, mapping หรือ credential Follow-up
  exact `db5c041132ac2d8527a3ab7e629bb767f7298bf0` จึงปิด Uvicorn access log ที่
  launcher และทำให้ local/production
  acceptance fail หากรูปแบบ client-address access record กลับมา Structured
  web/api/audit logs ที่ไม่เก็บ request target ยังคงอยู่ SHA นี้ผ่าน feature
  Pipeline #36257 และ protected-main check-only Pipeline #36258 แล้ว แต่ไม่ได้
  deploy ซ้ำภายใต้นโยบาย acceptance เดิมเพราะจะ rollback แบบ deterministic
- policy exact `8c99dfd58556887db4a7f9d917a0e4ff1b0ae7d9` ผ่าน feature Pipeline
  #36304 และ protected-main check-only Pipeline #36305 Production Pipeline
  #36306 ผ่าน check/deploy และ internal platform acceptance ทั้ง auth, 16-route
  allowlist, live Pathumma, report และ logs จากนั้น public acceptance รายงาน HTTP
  warnings ตาม owner decision แต่ mixed-content assertion แบบค้น substring จับ
  standards-required `http://www.w3.org/2000/svg` ภายใน percent-encoded inline
  favicon data URI เป็น network request ผิดประเภท Mandatory gate จึง rollback
  กลับ exact `72e18bbe...` healthy ตามนโยบาย Corrective descendant ต้องแยก
  network-bearing attributes/CSS/JS จาก inert inline SVG namespace โดยไม่ลด
  browser mixed-content หรือ HTTPS/TLS/HSTS gate
- รายการ P0/P1/P2 และ platform evidence ที่ไม่ควรอ้างอยู่ที่
  `docs/PRODUCTION-READINESS.md` งานนี้เปลี่ยน runtime จึงต้อง deploy exact SHA;
  HTTPS/valid TLS/HSTS, protected acceptance, live provider, auth/Secure cookie,
  16-route allowlist+legacy denial, log/resource/restart และ browser QA ยังเป็น
  mandatory ทั้งหมด การขาด HTTP 308 เท่านั้นที่เป็น accepted external warning

แผนแม่บท: `C:\Users\teera\.claude\plans\ai-for-thai-expressive-lighthouse.md`
Historical Sprint-2 baseline คือ protected Pipeline #35744 ที่ exact
`72e18bbe723adaf54c847e4b17c2177dfa60dd68` ผ่าน
`check → deploy → acceptance` ครบแล้ว web/api/core ใช้ revision เดียวกัน และ
public acceptance ผ่าน health, auth, Privacy Scan, live Tokenmind Safe AI,
PDPA Report, route denial, log privacy, resource และ restart/recovery SHA นี้เป็น
rollback evidence ก่อนหน้า `9d38c6753aa0242bc35d09ec3332e90fe3f90079`
ยังต้องรักษา ขั้นตอนของวันจริงอยู่ที่ `docs/DEPLOY-DAY.md`

Participant Guide ทางการถูกอ่านครบและยืนยัน `team08`, พอร์ต `20070/20071`,
frontend `/`, backend `/api` ที่ถูก strip prefix, unprefixed `/health`,
non-main `check`, main-only deploy, per-service limits, `50m` × 3 log rotation,
Masked application variables และ no-SSH ops ส่วน protected-main gate,
protected variables, runner tag และ stale-SHA checks เป็น AI Guard hardening
ไม่ใช่ข้อกำหนดที่คู่มือระบุ

candidate ปัจจุบัน sync จาก main commit `44ef30b` ครบ 75 ไฟล์ผ่าน manifest
hash โดยคง `/v1` public aliases แต่ nginx inject contract 2 ให้ strict-v2 core
หน้าเว็บใช้ minimized DTO แล้ว Roundtrip ไม่คืน mapping, token/original pair
หรือ token-bearing entity projection

owner รับ ADR caller-auth เมื่อ 7 ส.ค.: static frontend กับ health เป็น public
ส่วน business API ต้องแลก access code เป็น signed cookie อายุ 30 นาทีแบบ
Secure/HttpOnly/SameSite=Strict internal core key และ provider key แยกกัน

## Hosted production scope หลัง Sprint 2 (10 ส.ค. 2569)

- product สาธารณะมีสาม workflow เท่านั้น: Privacy Scan, Safe AI, PDPA Report
- frontend เป็น light-theme ภาษาไทย-first สำหรับการนำเสนอ: Guided Demo ร้อย
  Privacy Scan → Safe AI → PDPA Report จาก synthetic scenario เดียวกัน โดยเรียก
  `/roundtrip` ฝั่ง frontend หนึ่งครั้งและหยุดเมื่อขั้นใดไม่ผ่าน มี gallery ห้า
  บริบท + reset, Executive Result Summary, Raw-vs-Protected, Sensitive Data Map,
  Prompt Risk, Protection Receipt, Presenter/fullscreen, entity glossary,
  mode `token`/`surrogate`, เวลา total ที่วัดในเบราว์เซอร์ และการ์ด
  “ข้อความที่ส่งให้ AI จริง” ผลทั้งหมด derive จาก response เดิมและไม่สร้าง
  provider call หรือ public route เพิ่ม
- Protection Receipt เป็นหลักฐานบนหน้าจอเฉพาะคำขอ ไม่ใช่หลักฐานเข้ารหัสหรือ
  ใบรับรอง PDPA และไม่แสดง mapping/pair/provider body/raw value ส่วน Prompt Risk
  เป็น heuristic warning-only ที่ไม่บล็อกและไม่รับรองว่าปลอดภัย
- Presenter/fullscreen ไม่ persist state ไม่เรียก network และซ่อน raw/restored
  ของ custom input โดย default; frontend ไม่มี third-party dependency หรือ
  persistent browser storage ของเนื้อหาผู้ใช้
- ทุก CI job ถูก pin ด้วย runner tag `team-08`; feature branch/MR และ push ทุก
  branch รวม protected `main` รัน `check` เท่านั้น ส่วน deploy/acceptance/ops
  ต้องเป็น UI-created pipeline บน protected `main` ตาม executable rules
- exact proxy allowlist มี 16 routes (8 canonical + 8 `/v1` aliases)
- `/redact-pdf` และ `/v1/redact-pdf` คืน proxy-level 404; frontend ไม่มี
  upload/call/preview/download ของ PDF redaction
- implementation PDF/OCR และหลักฐานเก่าคงอยู่ภายใน core/เอกสารประวัติ แต่ OCR
  ยังไม่ production-ready บน AI for Thai การเปิดใหม่ต้องผ่าน correctness,
  provenance, timeout และ resource acceptance แยกต่างหาก
- hosted core sync ถึง `44ef30b` ซึ่งรวม shared provider retries/fresh outbound
  scans, Tokenmind single-attempt และ authoritative PDF intervals โดยหยุดก่อน
  Native Broker; VERSION ยังเป็น 2.5.0
- public 413/429/502/504 เป็น fixed value-free JSON, upstream error body ถูก
  intercept และ roundtrip สอง alias ใช้ timeout 200 วินาทีให้ครอบ shared
  provider envelope; health ยังคงเป็น liveness

## Sprint 3 evaluation scope (10 ส.ค. 2569)

- สร้าง corpus จาก deterministic local templates เท่านั้น 138 direct-PII cases
  (102 positive, 24 hard negative, 12 ambiguous ที่ไม่นับ headline) และ 32
  Section 26 heuristic cases; ไม่มี production/user/log/provider record
- ครบ entity type ที่ hosted revision ปล่อยออกมา 18 ชนิด Ground truth ใช้
  half-open Python Unicode code-point spans และ generated manifest ผูก seed,
  generator/schema/corpus SHA-256
- baseline บังคับวัด detector ที่ exact production SHA `72e18bbe...` ก่อนพิจารณา
  fix ได้ exact typed P/R/F1 = 76.86/77.50/77.18%, protective-character recall
  91.57% และ hard-negative document FP rate 25.00%; per-type ทุกแถวยัง support
  ต่ำกว่า 25 จึงเป็น descriptive only
- recognized value removal = 100% ทั้ง Token/Surrogate; controlled-echo restore
  exact = 100% ในรอบที่ sanitize สำเร็จ Surrogate สอง zero-width PHONE cases
  ถูกหยุด fail closed ไม่มี unsafe text คืน ส่วน expected-gold removal อยู่ราว
  94% เพราะ detector miss ต้องรายงานช่องว่างนี้ตรง ๆ
- Section 26 แยกเป็น HEURISTIC SIGNAL EVALUATION: recall 100%, precision 50%,
  F1 66.67% บน 32 cases แสดงชัดว่าคำ keyword ใน negation/context ยัง flag;
  ไม่ใช่ PDPA compliance/legal classifier
- evaluator รันใน revision-labelled core image ด้วย `--network none` + socket
  tripwire, environment allowlist, offline thainer; provider calls/production
  credentials/real PII = 0 และ artifact ไม่มี corpus text, replacement หรือ
  reidentification pair
- ไม่มีการแก้ `core/`: manifest-pinned vendored ownership ทำให้ address/name/
  parenthesized-or-zero-width phone remediation เป็น upstream task ไม่ใช่การ
  tune fixture ใน hosted shell
- ไม่มี frontend/runtime/API change ไม่เพิ่ม public evidence card เพื่อหลีกเลี่ยง
  demo clutter หลักฐานอยู่ที่ `docs/evaluation/thai-pii-competition-evaluation.md`
  และ machine result `evaluation/thai_pii/baseline.72e18bbe.json`
- independent Thai human adjudication ยัง pending; จึงห้ามอ้าง population-wide
  accuracy หรือ perfect detection

## เสร็จแล้ว (มีหลักฐาน)

- **E0 spike ผ่าน**: paddle cp313 wheel มีจริง, HOME=/opt/ocr-home + chown appuser ใช้ได้,
  offline inference ได้, build เย็น 270s / spike image 2.74GB / RSS 910MB
- **E1-E5 จบ**: สรุป + คำตอบแบบสำรวจอยู่ `docs/evidence/e0-e5-results.md`
  (Text ✓, Vision ✗, GPU ไม่มี, ASR = เจ้าของเลือก — เลขถอดเป็นคำอ่านไทย e4_report.json)
- **Upstream PR #101 merge แล้ว** (`71b7120`) และ PR #102 (ADR tokenmind + port) ตามมา
- **Port repo นี้** ประกอบครบ: sync (SHA-256 manifest + LF normalize), core/Dockerfile
  (OCR baked, UVICORN_WORKERS), api/ (nginx exact allowlist + /v1 + noquery + key inject),
  web/index.html (หน้าเดิมห้าฉาก tokenmind-only ซึ่งถูกแทนด้วยสาม workflow
  ปัจจุบันด้านบนแล้ว), docker-compose.yml, .gitlab-ci.yml, README,
  docs/DEPLOY-DESIGN.md (v2), tests/smoke.py
- **Checklist ก-ฌ + ช + ซ ผ่านครบ** — evidence `docs/evidence/checklist-results.md`
  (soak fake 8 สาย 10 นาที 5465 ok 0 5xx, restart recovery, limit 124×429,
  soak tokenmind 2 สาย 222 ok, log 0 PII)

## เสร็จรอบ 29 ก.ค. เย็น — ปิดช่องว่าง "CI ไม่เคยรันจริง"

หลักฐานเก่าทั้งหมดมาจาก `tests/smoke.py` ที่รันบน Windows ด้วย venv ซึ่งยิงคำสั่ง
**เทียบเท่า** ที่ CI ทำ ไม่ใช่ตัวที่ CI จะรัน ช่องนี้ปิดแล้ว

- **S0 spike** (`tests/out/s0-runner-simulation.json`) socket mount ถึง daemon ของ host ได้
  `--network host` บน Docker Desktop เข้าถึงพอร์ตที่ publish บน 127.0.0.1 ได้
  และ shell ของ job คือ `/bin/busybox` ไม่มี bash
  **ข้อสันนิษฐานในสเปกสองข้อผิด** BusyBox build นี้รองรับ process substitution และ
  `grep -E` รับ `\s` ได้ check stage จึงไม่ต้องเขียนใหม่ (บันทึกไว้แทนที่จะเงียบ)
- **S1 re-sync** หมุดขยับ `46c1f9a` → `00b3ffe` (62 ไฟล์) หมุดเก่าเก่ากว่างานแก้ shaping
  แปลว่า `core/requirements.lock` ไม่มี uharfbuzz และ `/analyze-report` อยู่ใน allowlist
  ถ้า deploy ด้วยหมุดเก่า รายงาน PDPA ที่ผู้ใช้โหลดจะวรรณยุกต์เพี้ยนทั้งฉบับ
- **S2 `tests/nginx_contract.py`** อยู่ใน check stage จริง (ไม่ใช่เครื่องมือ local)
  ยืนยันห้าข้อบน `api/Dockerfile` ตัวจริงกับ stub core ที่สะท้อน path + key กลับมา
  พิสูจน์แล้วว่าจับพังได้ เปลี่ยน `location =` เป็น prefix match แล้ว `/detectx` ทะลุถึง core
  และเทสแดงทั้งสองข้อ
- **S3 `tests/run_ci_local.py`** รัน job จริงในอิมเมจจริง **ผ่านครบสาม job**
  check 12.9s / deploy 167.2s / acceptance 4.7s (ยิง thaillm-8b จริง ด้วย PII สังเคราะห์)
  deploy รอบนี้ยังพิสูจน์ว่า lock ใหม่ build ได้ uharfbuzz ลงในอิมเมจเรียบร้อย

## เสร็จรอบ 3 ส.ค. — re-sync หมุดใหม่ + ถอดสลัก flake ใน acceptance

- **S4 re-sync** หมุด `00b3ffe` → `078e988` (69 ไฟล์ ตาม upstream CI ที่เขียวแล้ว)
  ได้งาน detection ชุด gov-form (gold F2 0.910→0.918), OCR fallback/merge-safe
  retries และฟอนต์ไทย bundled ซึ่งเข้าเส้น detect/redact-pdf/analyze-report
  ที่เปิดบน deployment ทั้งหมด SLICE เพิ่ม `licenses/OFL-1.1.txt` ตามที่ NOTICE ชี้
- **acceptance เลิกเทสอารมณ์ของโมเดล** รอบเต็มรอบแรกจับได้ว่า
  `grep -q` เบอร์โทรบน `restored_text` ผูกอยู่กับว่า thaillm ทวนโทเคนหรือไม่
  (echo 19/25 ที่ temp 0.0 — แดงเงียบทั้งที่บริการตอบ 200) แก้เป็น assert
  หน้าที่ของเราแบบ deterministic (ตรวจเจอครบ / ไม่มีค่าจริงหลุด / ไม่มี token
  residue) + assert โทเคนที่โมเดล**ทวนจริง**ต้องกลับเป็นค่าจริง + curl retry 3
  ครั้งเฉพาะ transport/5xx (เคส key หายยังแดงเพราะ 503 ล้มครบ) ทุกทางล้มมี echo
  พิสูจน์แดงเป็นครบ 6 เคสใต้ busybox ของอิมเมจ CI จริง
- **รันเต็มหลังแก้เขียวครบสาม job** check 70.8s / deploy 77.5s / acceptance
  86.0s (thaillm-8b จริง) และดึง `/analyze-report` จาก stack จริงตรวจด้วยตา
  PDF ฝัง `IBMPlexSansThaiLooped` วรรณยุกต์ซ้อนถูกทุกคำ
  รายละเอียด + ตัวเลขดิบอยู่ `docs/evidence/ci-first-push-readiness.md` (S4)

## เสร็จรอบ 7 ส.ค. — current-core/auth/minimized response

- **S5 sync** `078e988` → `8c6efef` (75 vendored files) รวม strict HTTP v2,
  fail-closed outbound policy, safe errors/logs และ explicit-TNER failure
- **caller auth** unit contract 11/11 ผ่าน ครอบคลุม fail-loud config, public
  health, login, cookie flags, tamper/expiry/secret rotation, cross-site,
  logout และทุก business route; startup ปฏิเสธการใช้ caller/signing/core/provider
  secret ซ้ำกัน
- **frontend session contract** รัน JavaScript จริงผ่าน: stale auth/detect/
  roundtrip/PDF response ไม่เขียนทับ state ใหม่, logout/401 ล้าง PII และ
  PDF bytes, login/logout ไม่แข่งกัน, astral span ตรง และคำตอบ unsafe ไม่ถูกแสดง
- **nginx contract** ผ่าน 12 business/health aliases, 6 auth aliases, 9
  proxy-denied paths, internal key/contract injection, web syntax และ
  api/web query-log regression รวม rate-limit warning path
- **dated local working-tree Docker stack** buildใหม่และ web/api/core healthy ทั้งหมด
  runtime auth/privacy probe ผ่าน 401/403/signed-cookie/strict-v2 minimized
  detect และไม่พบ synthetic honeytoken, PII, cookie หรือ secret ใน log
- **dated live smoke** 8/8 ผ่าน: health, auth, Tokenmind roundtrip, no-query log,
  allowlist, webpage, vendored integrity และ scanned-PDF OCR
- **dated local GitLab approximation** ผ่านครบใน BusyBox runner image:
  check 21.5s / deploy 59.2s (warm cache) / acceptance 8.8s; acceptance
  login จริง, เรียก Tokenmind จริง, ตรวจ minimized response และ scan log
- **release-content commit** `71c20b37b1bf2be8f34b67294bc75137931ad3cb`
  ผ่าน local BusyBox `check` 25.7 วินาที, no-cache build สาม image 230.8
  วินาที, provider-free/fake acceptance + log/rate-limit/restart 28.7 วินาที
  และ BusyBox `deploy` simulation 63.5 วินาที; revision label ตรง commit
  ทั้งสามอิมเมจ
- **exact local profile** detect 100/100 หลัง warmup ได้ p50 6.02 ms,
  p95 7.58 ms, max 12.57 ms; one-page scanned-PDF route ผ่านใน 221.0 วินาที
  แต่ใช้ CPU เฉลี่ยประมาณ 1.93/2 cores และ memory peak ชน 6 GiB
  (`memory.events max=8247`, ไม่มี OOM/restart) จึงเป็น resource gate แดง
- ทุก descendant ที่เปลี่ยน frontend หรือ CI ต้องผ่าน Product/Judge review,
  security review และ exact-revision fake-provider acceptance ใหม่ก่อน
  fast-forward local `main`; หลักฐาน commit เก่าไม่ครอบ descendant โดยอัตโนมัติ

## Production evidence และสิ่งที่ยังเหลือ

1. runner #227 เป็น organizer-provided team-08 group runner, online,
   Docker amd64/Linux, tag `team-08`, accepts untagged และไม่มี Protected flag
   คู่มือไม่กำหนด Protected runner และ flag ที่ขาดไม่ใช่ publication blocker
   เพียงลำพัง แต่ staff ควรยืนยัน project scope/daemon isolation; tag เป็นเพียง
   scheduling control ไม่ใช่ isolation proof
2. first publication `298401552726...` pipeline #35715 และ correction
   `f0359dc7b71f...` pipeline #35716 เป็น historical failed-check evidence;
   ไม่มี production mutation #35718 ที่ exact `5ae77ad25eb...` ผ่าน check-only
   จริงบน runner #227
3. owner ยืนยัน project variables สี่ชื่อครบ โดย metadata เป็น Protected,
   Masked, Hidden และ scope `team08`; repository/Codex ไม่อ่านค่าจริง
4. historical production pipeline #35722 บน `5ae77ad25eb...` ผ่าน check และ build/up
   จน web/api/core healthy แต่ deploy ล้มที่ job-container
   `127.0.0.1:20070/20071`; acceptance และ manual ops ไม่ได้ execute
   stack ที่ยกสำเร็จคงอยู่ แต่ #35722 ไม่ใช่ successful acceptance evidence
5. descendant correction เปลี่ยน deploy เป็น in-container probe, ต่อเฉพาะ
   acceptance job เข้า exact Compose network ชั่วคราว, ปิด ambient proxy,
   รักษา public Host และ cleanup เสมอ ทั้งยังแยก build/recheck/up เพื่อลด
   stale-main race
6. Pipeline #35727 ที่ exact `42476d09a7d80b6920fcf21c0d2ac0d5c6952872`
   พิสูจน์ network correction ครั้งแรกบน runner #227; Pipeline #35736 ที่ exact
   `9d38c6753aa0242bc35d09ec3332e90fe3f90079` คือ rollback ก่อน Sprint 2 และ
   Pipeline #35744 ที่ exact `72e18bbe723adaf54c847e4b17c2177dfa60dd68`
   คือ known-good production ณ รอบนั้น ซึ่งถูกแทนที่ภายหลังด้วย live revision
   `dbcfe17b34744dc3e9a88e4099786a754fe903a6` ตามหลักฐานบนสุด:
   check/deploy/acceptance ผ่านครบ สาม image revision
   ตรงกัน public HTTPS และ `/api` stripping ผ่าน login/session/logout, synthetic
   Privacy Scan, live Tokenmind/thaillm roundtrip, PDPA Report, PDF/forbidden-route
   denial, retained-log scan, resource และ restart/recovery
7. เฉพาะ deploy/acceptance ประกาศ environment `team08` และรับ scoped secrets;
   manual ops ใช้ direct Docker commands โดยไม่ประกาศ environment จึงไม่รับ
   application variables Restart ตรวจ remote SHA + image revision ก่อนทำงาน
   และรอ health ทั้งสาม service
8. competition enhancement ที่เปลี่ยน runtime ต้อง push feature branch ให้ check-only เขียว ผ่าน
   exact fake-provider local acceptance และ independent reviews ก่อน fast-forward
   `main`; จากนั้นสร้าง UI pipeline ใหม่บน protected `main` exact SHA ห้าม retry
   pipeline เก่าหรือใช้ rollback #35736/#35744 เป็นหลักฐานของ runtime descendant
9. successful pipeline ต้องผ่าน `check → deploy → acceptance` ครบ แล้วจึงตรวจ
   public HTTPS, organizer `/api` prefix, real browser cookie flow, rate limit,
   Dozzle/log, resources, restart/recovery และ visual QA แยกจาก internal
   Compose-network acceptance
10. Public PDF redaction/OCR ยัง proxy-level 404 ทั้งสอง alias; PDPA Report PDF
    ยังเปิดตามเดิม และ PDF/OCR ไม่ใช่ capability ของ hosted release นี้
11. คำตอบแบบสำรวจ + การตัดสินใจช่อง ASR ยังรอกรอก/ส่ง
12. Sprint 3 เป็น evaluation/tests/docs-only ถ้า feature check และ reviews ผ่าน
    ให้ integrate ตาม protected-main workflow แต่ไม่สร้าง production deployment
    ที่ไร้ runtime change; deployed SHA ต้องคง `72e18bbe...` และแยกจาก evaluation HEAD

ลำดับเต็มพร้อมกับดักอยู่ที่ `docs/DEPLOY-DAY.md` และใช้ได้เมื่อ preflight
ด้านบนผ่านแล้ว

## กติกาที่ห้ามลืม

- ไม่มี provider จำลองบน deployment / ไม่มีเดโมสำรอง — service จริงเท่านั้น
- pseudonymized-มี-vault ยังเป็นข้อมูลส่วนบุคคล — ห้ามเคลมเกิน
- ห้ามเคลมสาธารณะ "benchmark เดียวของไทย"
- production pipeline ต้องมีคำสั่งเจ้าของชัดเจนและต้องอ้าง exact reviewed SHA;
  ordinary branch/main pushes ยังเป็น check-only ตาม executable rules
- ตัวเลขเวลาจากเครื่องนี้บอกลำดับความใหญ่ ไม่ใช่คำรับประกันบน runner ของผู้จัด
