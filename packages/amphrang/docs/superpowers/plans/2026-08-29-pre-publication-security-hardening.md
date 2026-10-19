# Pre-publication Security Hardening Plan

- **Status:** Complete locally; not committed, pushed, tagged, or published
- **Scope:** Close the two verified P0 privacy defects before any public repository or package release.
- **Baseline:** `main` at `ad60551`; preserve the user-owned untracked `.claude/` tree and `AGENTS.md`.
- **Timer origin:** 2026-08-29T16:36:18.586Z (first task tool action)

## Findings

1. Shared MCP HTTP authenticates a `caller_id`, but session operations authorize only the
   opaque handle. A caller who obtains another caller's handle can continue, restore, or close
   that session.
2. The chat proxy sanitizes `message.content` but forwards the rest of the copied request.
   Unknown or string-bearing fields can therefore carry raw PII to the upstream.

## Required design

### MCP caller binding

- Bind every HTTP-created session to the authenticated caller.
- Make a foreign handle behave exactly like an expired or unknown handle.
- Cover `sanitize` continuation, `reidentify`, and `close_session`.
- Preserve local stdio behavior, TTL cleanup, capacity bounds, and value-free errors.

### Proxy request schema

- Forward only an explicit v1 allowlist of top-level and message fields.
- Bind the client-supplied model exactly to the required `AMPHRANG_PROXY_MODELS`
  configuration; never infer trust from version-like syntax.
- Sanitize every supported text content value with one request-scoped mapping.
- Validate forwarded identifiers/enums and numeric/boolean controls; reject unknown,
  unsupported, or uninspected fields before contacting the upstream.
- Preserve input immutability and reject tool/function/non-text paths fail closed.

## Execution and gates

1. Add adversarial tests that fail on the current code.
2. Implement the smallest caller-facing fixes.
3. Run targeted MCP/proxy tests, Ruff, the complete pytest suite, release consistency,
   pre-commit hygiene, and `git diff --check`.
4. Assign an independent reviewer; verify and fix every material finding, then re-run affected
   gates.
5. Record measured wall-clock durations below. Do not commit, push, or tag.

## Timing log

| Phase | Start (UTC) | End (UTC) | Duration | Status/evidence |
|---|---|---|---:|---|
| Baseline and plan | 2026-08-29T16:36:18.586Z | 2026-08-29T16:37:10.030Z | 51.4 s | Complete |
| Environment sync | 2026-08-29T16:37:34.440Z | 2026-08-29T16:37:57.685Z | 23.2 s | `uv --no-cache sync --extra server --extra mcp` passed |
| MCP caller binding | 2026-08-29T16:37:34.814Z | 2026-08-29T16:47:59.652Z | 10 m 24.8 s | 3 red baseline probes; 22 targeted tests passed |
| Proxy strict schema | 2026-08-29T16:37:36.031Z | 2026-08-29T16:55:19.884Z | 17 m 43.9 s | 29 red baseline failures; 129 proxy tests passed |
| Proxy fix round 2 | 2026-08-29T17:00:38.851Z | 2026-08-29T17:09:41.757Z | 9 m 02.9 s | Exact model binding + error-value restore; 149 targeted tests passed |
| Adversarial fix round 3 | 2026-08-29T17:21:34.438Z | 2026-08-29T17:35:04.773Z | 13 m 30.3 s | Scalar outbound policy + whole-history guard + MCP forgery matrix |
| Verification | 2026-08-29T16:55:07.228Z | 2026-08-29T17:41:29.773Z | 46 m 22.5 s | Final full/static/pre-commit gates passed; overlaps fix/review work |
| Independent review and fixes | 2026-08-29T17:14:43.301Z | 2026-08-29T17:41:29.773Z | 26 m 46.5 s | Three rounds; final verdict: no material disagreement |

Verification history is evidence, not a hidden retry: the first full run spent
93.8 s and failed because the default Windows pytest temp root was unreadable;
the isolated-basetemp run spent 64.7 s and found two real missing-model
regressions; after fix round 2, the full suite passed 1,976 tests with 9 skips
in 61.14 s (71.8 s wall time including process/tool overhead).

Round 3 added the outbound policy for every forwarded scalar, a sanitized
whole-history boundary guard, and direct forged-header/raw-handle MCP probes.
The final targeted suite passed 184 tests in 2.99 s; the final full suite
passed 1,989 tests with 9 skips in 56.86 s (63.5 s wall time). Ruff, Ruff
format, `scripts/check_release.py`, `uv lock --check`, `git diff --check`, and
all configured pre-commit hooks passed. Pre-commit's first successful hook-
environment bootstrap cost 72.3 s; the final warm run cost 38.1 s.

The total observed wall time from the first task tool action through the final
static gates was 65 m 11.2 s. Rows overlap because MCP, proxy, tests, and review
ran in parallel; their durations must not be summed as elapsed time.

## Accepted v1 response limitation

For parsed upstream JSON errors, string values are restored recursively but
object keys remain unchanged. Restoring keys can create collisions and silently
change the upstream schema. A token used as a key may therefore remain masked;
this does not send plaintext upstream and is recorded for a later response-
contract decision.
