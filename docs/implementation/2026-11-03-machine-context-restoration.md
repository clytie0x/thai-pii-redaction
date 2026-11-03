# Machine-context Restoration Implementation Plan

> **For agentic workers:** Use subagent-driven development with disjoint file
> ownership and a fresh independent review before landing each unit.

**Goal:** Enforce the owner-approved machine-context policy in bulk and streamed
restoration while preserving evidenced source rebuilding and existing wire shapes.

**Architecture:** One canonical context policy and incremental restorer under
`pii_redactor/`. Existing session/same-call owners supply only core-created
replacement ranges after exact sanitized-text equality. SDK streaming delegates
to the canonical implementation.

**Tech Stack:** Existing Python 3.11+, core dataclasses/vault/session code,
FastAPI/worker adapters, SDK and current tests. No dependencies or OCR changes.

**Spec:** [Owner-approved decision](../decisions/2026-11-03-machine-context-restoration.md).

## Constraints

- Preserve original spans, longest-first replacement and boundary guards.
- Preserve token namespace/legacy mapping rules and plaintext Sensitive restore.
- Never accept source-proof authority from public HTTP/worker/SDK input fields.
- Keep existing partial output/status and replacement-count contracts.
- Keep the current mixed-occurrence distinction: core/session count one known
  pseudonym if any occurrence restores; stateless/SDK count zero when that same
  pseudonym also remains. Assert both rather than harmonizing them.
- Hold source proof as digest and integer occurrence ranges, not extra raw text.
- Keep stream state bounded independently of response length. Preserve discard
  behavior on failed/cancelled transport; flush only successful completion.
- Preserve old evidence, unchanged baseline/budgets and controlled-performance hold.

## Units and file ownership

### A. Canonical bulk and incremental policy

Own new `pii_redactor/restore_context.py`, `pii_redactor/reverse_mapper.py`,
`tests/test_restore_context.py` and `tests/test_step6_reverse.py`.

- [x] Reproduce restoration into URL, Markdown and tag/attribute contexts.
- [x] Implement one shared context scanner and canonical guarded stream restorer.
      Export `GuardedStreamRestorer(mapping)` with `feed`, `flush`, `discard`;
      preserve token matching and one-token buffering semantics except the
      bounded lookahead needed to classify a possible reference definition.
      Keep incomplete/ambiguous syntax protected at bounds and discard pending
      completed tokens on cancellation before the deciding suffix arrives.
- [x] Make bulk `reverse_map` strict by default. Add private keyword
      `_source_rebuild_ranges`, default empty, for full occurrence matches only.
- [x] Test token/surrogate modes, mixed plain/machine occurrences, quote/nesting
      boundaries, incomplete syntax and bounded worst-case input/state.

### B. Core-owned source occurrence proof and caller integration

Own `pii_redactor/session_service.py`, `pii_redactor/stateless.py`,
`pii_redactor/pipeline.py`, `app/server.py`, relevant `app/worker/` restore callers
and their owning tests. Do not edit unit A's files.

- [x] Bind immutable highlight ranges to the existing successful sanitized
      digest cache after finalize, with existing staging, limit, eviction and
      cleanup behavior. Do not exempt literal old-token occurrences.
      Digest and immutable ranges are one cache entry; never maintain two
      independently mutable collections that can desynchronize.
- [x] Thread private ranges into exact source rebuilding only. Mapping-only
      restore remains strict; public arguments/projections gain no authority.
- [x] Pass same-call evidence only when returned text exactly equals the owned
      sanitized result and ranges come from its highlights.
- [x] Test exact source URLs, changed destinations, copied tokens, seeded/legacy
      mapping reuse, rollback/eviction/lifecycle and no proof on the wire.

### C. SDK streaming and adapters

Own SDK proxy restorer/server, SDK HTTP/roundtrip adapters and owning tests.
Coordinate the private same-call interface with unit B; do not edit core files.

- [x] Delegate `StreamRestorer` to unit A's canonical guarded implementation.
- [x] Test all chunk splits around schemes, tags, Markdown destinations and
      reference definitions, multiple/adjacent/unknown/legacy tokens and EOF.
- [x] Preserve incremental output, bounded buffers, cancellation/disconnect and
      malformed-provider contracts. Confirm no original is transiently emitted
      in a guarded occurrence. No whole-response buffering fallback.
- [x] Keep mappings and proof internals out of API/MCP outputs and logs.

### D. Qualification and integration

- [x] Separate independent adversarial reviews of A/B/C and caller trust flow.
- [x] Complete core/web, SDK and installed proxy/API source gates with exact
      hashes. Unchanged JavaScript evidence remains historical; cross-platform
      execution remains an exact-candidate CI gate.
- [x] New paired wheel/sdist/install/PDF/proxy qualification on Windows/Python
      3.13 after core changes. Other runtime/OS profiles remain CI/host gates.
- [ ] Exact-candidate CI, controlled performance gate and then qualified main
      integration; preserve raw branch/study/worker heads before branch removal.

Review partial-context bypasses, copied-token proof forgery, UTF/code-point
offsets, stream prefix loss, pending-token growth, finalization rollback and
private data in error paths. Local fixtures do not qualify actual hosts/providers.

## Bound local evidence, 2026-11-03

The strict source was qualified as uncommitted changes over `404f2a9`; the later
Desktop-only keepalive commit does not change any of the 256 artifact inputs.
Core/web passes **3,813 tests, 80 skipped, one warning** in 197.74 seconds. SDK
passes **2,205 tests, ten skipped** in 32.89 seconds. Both runs retain identical
before/after hashes for 280 inputs. Skips are explicit PostgreSQL, identity,
optional ML/OCR, platform and live-provider gates, not accepted features.

The source manifest is retained under
`.superpowers/sdd/parallel-s-m/strict-restore-final-source-v3.json`, SHA-256
`6afb97b51d5aae176417d496dd17c526a158e5513e536521a2e61d0cad4caff5`.
The owning scanner/reverse suite passes 324 tests. Final independent MAC review
checks 148 cases, 6,584 two-part splits and character-wise feeds without a
protected original emission. Source-proof/caller and exact-artifact reviews are
CLEAR within their stated scopes; these are not full security audits.

Six fresh paired wheel/sdist/rebuilt artifacts pass byte identity, three fresh
installed profiles, **956 installed tests without skips**, six checker negatives
and 20 identity negatives. Python 3.11/3.12 checks cover identity/cache formats
only, including twelve semantic-cache negatives per interpreter. The immutable
artifact manifest is retained at
`C:/Users/teera/AppData/Local/Temp/aiguard-strict-restore-noizeack/qualification-manifest.json`.

| Binding | SHA-256 |
| --- | --- |
| 256 artifact source inputs | `54340c0705fee0247c19904d6ef80e3ea54b774cd8754d19206b94750cd804d1` |
| Artifact manifest | `b87cb9b54a888f913e781469e14c4a7855dd9cfaab63698b3eb0ff9367fa86af` |
| Phase closure | `2981273363b755b66bf1545955e8bc78e503a57e797116f47a329f13a9195913` |
| Core wheel | `f7477d44ed22a72c6e06dd8c09e0d46eb3edd9ea48b79d9847cfebf0e0cf5a8d` |
| SDK wheel | `5a526663d8801221d28989f7459f262fce106eff03564f1350de83fafe9e1817` |

Installed PDF follow-up passes seven proof groups in each of enterprise and
SDK/server/MCP profiles, including receipt version `0.1.0`, recomputation and
installed-API/source-only-CLI guidance. The parent inspected all ten rendered
PNGs. Command record SHA-256 is
`677c7233936817ec6dfcac606e80c329bf77d7140140b3ea784a437517dcd5df`;
parent visual record SHA-256 is
`01419b9a86593c71324e0e590ac20781d6ee92438e874b7f7b85c2898dcc6f6a`.
Their records are under `.superpowers/sdd/strict-restore-pdf/`.
No external network attempt occurred. Instrumentation permits only Windows
stdlib wakeup socketpairs and is not an OS firewall. OCR inference, external
HTTP, Office/browser hosts and live providers remain unqualified.

The first broad runs and all review negatives remain retained. Root v1 had three
MAC failures; SDK v1 had that MAC failure and 28 stale private-cache assertions.
Root v2 was deliberately stopped after independent review found a valid-URI
prefix bypass. SDK v2's passing result does not qualify that later fix. The
installed harness first reported 954 passes/two caplog failures because its old
blanket logging suppression hid expected sanitized diagnostics. Correcting only
that harness setting produces 956/956; no test selection/assertion or runtime
was weakened. Eight earlier evidence groups (417 files) remain byte-identical.

One five-iteration local performance checkpoint after other workloads completed
measures detect **5.42 ms**, sanitize **14.49 ms**, restore **0.35 ms**, PDF
**68.70 ms**, RSS **151.8 MiB**. It exits **1**: sanitize +44% and restore +25%
exceed the unchanged 20% time budget; RSS stays within 15%. Source and baseline
hashes are unchanged. The guard buys machine-context protection and precise
source-rebuild authority; this shared-host run does not establish the cause of
the older anchor gap or waive it. The protocol, results and exit are retained as
`.superpowers/sdd/parallel-s-m/perf-strict-restoration-v1.*`. M3's owner-selected
controlled-performance hold remains. Do not squash the held branch into main.

`404f2a9` passes all three pre-strict-contract CI workflows, including the real
Hosted image; it does not qualify these later core bytes. The next pushed
strict/keepalive candidate still needs every CI job to execute and pass. Legal,
pilot, actual host and public-purge gates remain open. No production acceptance,
deployment, baseline change or branch deletion follows from this record.
