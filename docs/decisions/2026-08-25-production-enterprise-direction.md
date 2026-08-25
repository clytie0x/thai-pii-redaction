# Production and enterprise direction: staged open-core, "PDPA firewall for LLM usage"

- **Date:** 2026-08-25
- **Status:** Proposed (approved in discussion, pending implementation plan)
- **Deciders:** Teerapat Vatpitak

## Context

amphrang 0.1.0 is a working Thai PII detection/anonymization library with a CLI,
an optional FastAPI server, an MCP server, PDF redaction, and PDPA document
tooling. Its differentiators are Thai-specific detection with checksum
validation, fully offline operation, a fail-closed leak guard, and a disciplined
benchmark protocol (open gold set + encrypted blind set).

What it lacks for production use: published performance numbers, published
accuracy numbers, an API stability commitment, and any adoption path that does
not require writing Python. It is maintained by one person. There are no
reference deployments.

Market context: Thai organizations (banks, hospitals, government, BPO) want to
use external LLMs but PDPA blocks sending personal data outside. Microsoft
Presidio has weak Thai support; commercial DLP does not understand Thai
government-document context. That gap is the wedge.

## Decision

Adopt a **staged open-core model** positioned as a **PDPA firewall for LLM
usage**:

1. Keep the core library, CLI, MCP server, and single-instance server open
   source. Open source is load-bearing here: a product whose whole claim is
   "your data never leaves your machine" must be inspectable.
2. Build a **sanitizing proxy** (OpenAI-compatible) as the primary adoption
   surface — organizations point `base_url` at amphrang and change nothing else.
3. Sell an **enterprise layer** later (on-prem licensed: SSO, RBAC, audit,
   HA packaging, support), only after the open core has real users.

Explicitly rejected alternatives:

- **Enterprise product first.** No reference customers to sell with, and the
  multi-tenant/SSO/support burden exceeds a solo maintainer's capacity.
- **Library-only forever.** The buyers with budget want a deployable appliance,
  not a pip package. Thai developers who can embed a library themselves are a
  small population.
- **Hosted SaaS.** Contradicts the core promise ("data never leaves your
  organization") and adds permanent operational burden. Non-goal.

## Target users and usage surfaces

| Surface | User | Status |
|---|---|---|
| Sanitizing proxy (`/v1/chat/completions`) | Platform/infra engineer who wants existing apps protected with zero code change | **New — Phase 2** |
| Python SDK (`amphrang.detect/anonymize/restore/Session`) | Developer embedding PII handling in an app | Exists; needs 1.0 stability promise |
| MCP server (`amphrang-mcp`) | Teams running AI agents (Claude Code, agent frameworks) | Exists; needs setup recipes |
| CLI + PDF redaction + PDPA documents | DPO / compliance officer, batch workflows | Exists; needs packaging polish |

## Phase 1 — Prove production readiness (before any new feature)

Goal: turn "it works on my machine" into published, reproducible numbers and a
stability contract. Everything here is a precondition for anyone deploying this
in production.

1. **Performance harness.** A repeatable benchmark (same discipline as the
   accuracy benchmark) measuring: cold start (NER model load), p50/p95 latency
   per input size class, throughput (docs/sec) single-process and multi-worker,
   peak memory. Published in `docs/benchmarks/`. CI regression guard on the
   cheap subset.
2. **Published accuracy.** Per-entity precision/recall from the gold set (and
   aggregate blind-set scores within the existing reveal budget) in the README.
   Honest-labeling policy already exists; this makes it visible.
3. **Async + batch API.** Detection is CPU-bound, so async means threadpool
   offload, not asyncio rewrites: `detect_batch`/`anonymize_batch` and
   documented multi-worker guidance for the server. No API redesign.
4. **1.0 release.** Semver policy, deprecation policy (one minor version
   warning), documented public surface = `amphrang/__init__.py` exactly as
   today. `check_release.py` gate extended to block accidental surface changes.

Exit criteria: benchmark docs exist with real numbers from this machine + CI
runners; 1.0.0 tagged; a stranger can read the README and know latency,
throughput, and accuracy before installing.

## Phase 2 — Sanitizing proxy (the adoption product)

Goal: an OpenAI-compatible reverse proxy. An existing app sets
`base_url=http://amphrang-proxy:8400/v1` and its traffic is masked outbound and
restored inbound, with the mapping never leaving the proxy process.

### Scope (v1)

- `POST /v1/chat/completions` only, streaming and non-streaming. No
  embeddings, images, audio, or tools-with-PII passthrough in v1.
- One configured upstream (base URL + API key from env). Works with any
  OpenAI-compatible upstream (OpenAI, Anthropic via compat endpoint, local
  vLLM/Ollama).
- New optional extra `amphrang[proxy]`, code under `amphrang/proxy/`, reusing
  `stateless.py` and the leak guard unchanged.

### Data flow

1. Request arrives with full message history (OpenAI chat format).
2. All message contents are sanitized **in one pass with one session
   namespace/nonce**, so the same PII value maps to the same bracket token
   across the whole history. Mapping lives in request-scoped memory only.
3. Leak guard runs on the sanitized payload. If it trips → 422 with a
   value-free error; nothing is forwarded. Fail-closed, same promise as the
   library.
4. Sanitized request goes upstream. Response (or stream) comes back containing
   bracket tokens; proxy restores them and returns plaintext to the client.
5. Mapping is dropped when the request ends. Multi-turn works because the
   client always resends full history (which contains restored plaintext) and
   step 2 re-sanitizes it consistently within each request.

### Streaming restore

Bracket tokens have a fixed shape `[<label>_<namespace>_<nonce>_<ordinal>]`
with an enforced maximum length (`_TOKEN_MAX_LENGTH` in
`amphrang/engine/anonymizer/token_generator.py`). The stream restorer:

- passes text through until it sees `[`,
- holds back at most `_TOKEN_MAX_LENGTH` characters from the last unmatched
  `[`,
- on a complete token match, emits the restored value; on overflow or `]`
  without a match, flushes the held text verbatim.

Worst-case added latency is one token-length of buffering; no full-response
buffering. This is the hardest component and gets its own test suite
(token split across arbitrary chunk boundaries, malformed tokens, token at
stream end, upstream error mid-stream).

### Error semantics

- Upstream errors pass through with upstream status; body is restored if it
  contains tokens, otherwise forwarded as-is.
- Proxy-side failures never emit the mapping or raw PII in errors (reuse
  `safe_errors` conventions).

Exit criteria: a stock `openai` Python client and a stock chat UI work through
the proxy unmodified against a real upstream; streaming demo shows Thai PII
masked in upstream logs and restored on screen; leak-guard trip demonstrably
blocks forwarding.

## Phase 3 — Enterprise layer (licensed, on-prem)

Built only after Phase 2 has external users. Ships as a separate distribution
wrapping the open core; the open core never regresses to require it.

- **AuthN/AuthZ:** OIDC (works behind corporate SSO), API-key issuance per
  client app, roles: admin / operator / auditor.
- **Audit:** value-free structured event log (who sanitized what entity types,
  counts, timestamps — never values), hash-chained like
  `benchmark/data/blind-scores.jsonl`, exportable for ISO/PDPA audits.
- **Observability:** Prometheus `/metrics` (latency, entity counts by type,
  leak-guard trips), structured JSON logs, health/readiness probes.
- **Deployment:** Helm chart; HA guidance (proxy and stateless API scale
  horizontally; `Session`-based API needs sticky routing or stays
  single-instance — documented, not engineered around, in v1); offline/air-gapped
  install bundle with pre-warmed NER model (extends the Docker pre-warm).
- **Supply chain:** SBOM (CycloneDX) in releases, sigstore-signed artifacts,
  hash-pinned dependency lockfile for the enterprise bundle.
- **Assurance:** third-party pentest before enterprise GA; expand
  `docs/standards-mapping.md` toward ISO/IEC 27001 control mapping and a DPA
  template customers can hand to their DPO.

## Non-goals

- Hosted multi-tenant SaaS.
- Supporting non-Thai locales beyond what falls out of the existing detectors.
- Real-time restore of upstream *tool calls* containing PII (v1 proxies chat
  content only).
- Building enterprise features speculatively before Phase 2 adoption exists.

## Risks

- **Solo maintainer.** Mitigation: phases are strictly sequential, each phase
  ships something usable alone; no phase depends on future revenue.
- **Accuracy in the wild ≠ benchmark accuracy.** Mitigation: proxy logs
  value-free detection stats so early adopters can report gaps; benchmark
  contribution guide already exists for turning gaps into gold-set entries.
- **Streaming restore correctness.** Mitigation: exhaustive chunk-boundary test
  suite before the proxy is advertised; non-streaming mode ships first.
- **Open-core boundary drift.** Mitigation: this document is the boundary
  record; anything security-relevant to the core promise (detection, leak
  guard, restore) stays open source permanently.

## Testing

- Phase 1: performance harness is itself CI-run (subset); release gate blocks
  1.0 surface drift.
- Phase 2: contract tests against the OpenAI API schema; chunk-boundary fuzz
  tests for the stream restorer; end-to-end test with a fake upstream asserting
  no raw PII ever appears in forwarded requests (assert on the fake upstream's
  received bytes).
- Phase 3: auth/RBAC contract tests; audit-log chain verification test; Helm
  chart smoke test in CI.
