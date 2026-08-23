# Independent facade review — 2026-08-21

An independent read-only reviewer (running the repository's `aiguard_reviewer`
persona from the original repo's `.codex/agents/`) audited the extracted
package and the pending product decisions. Findings and dispositions:

## Fixed in this repo (same day)

| Finding | Severity | Fix |
|---|---|---|
| `anonymize`/`Session.anonymize` skipped `detection_text` normalization, so a Thai-numeral phone number passed through unmasked with no error — silent fail-open | P0 | Both paths now pass `detection_text=clean_length_preserving(text)`; regression tests use Thai numerals across detect/anonymize/Session/analyze |
| Facade `restore` dropped `generated_pii_count`/`foreign_replacement_count` | P1 | Fields added to `RestoreResult` (both stateless and Session paths) plus derived warnings |
| `analyze` ran on raw text, undercounting risk | P1 | Facade cleans first (`clean().text`) — analyze carries no spans, so full clean is safe |
| Installed wheel reported version "3.0.0" via `app.server` fallback literal | P1 | Fallback now asks `importlib.metadata`, then an honest `0.0.0`; pinned by `tests/test_server_pip_profile.py` |
| Broker-era `private_backend_bootstrap` in `app.server` had zero test coverage after the extraction | P1 | Interim pin: `tests/test_server_pip_profile.py` asserts the bootstrap is inert without broker env and the server boots with `private_backend` off. Full removal is the 0.2.x item below |
| `Session` raised internal exception types the facade does not export | P2 | `OutboundLeakError` mapped to `LeakBlockedError`; `SessionExpiredError` exported |
| `Session` docstring claimed timed expiry that lazy TTL does not provide | P2 | Docstring now states access-time enforcement and advises `close()` |
| `detect()` returned normalized `original_text` instead of the caller's slice | P2 | Facade re-slices `original_text` from the caller's text (spans are length-preserving) |
| `pytest` sat in runtime requirements | P2 | Moved to CI install |

## Accepted design change (applies to the future MCP adapter)

**Never return the pseudonym→original mapping as plaintext in an MCP tool
result.** Tool results always enter the model's context, so a returned mapping
would place every raw PII value into the very LLM conversation the product
exists to protect — and agent frameworks log tool results. The MCP `sanitize`
tool must return masked text plus an opaque session handle (server-side vault,
TTL-bounded) or a sealed (guard-encrypted) mapping blob; `reidentify` accepts
the handle/blob, never a plaintext mapping. The plaintext-mapping form remains
available only in the in-process Python facade, where the caller is code, not
a model context.

## Deferred with owner visibility

| Item | Target | Note |
|---|---|---|
| Trim untested `app/worker` submodules from the wheel, or restore their tests | 0.2.x | Only `handler` is exercised today |
| Freeze paper gold as file+checksum instead of a git-history reference | when research resumes | The old repo's history carries the frozen commit; this one cannot |

## Resolved (2026-08-22)

| Item | Resolution |
|---|---|
| Remove `native_broker_context` hooks from `leak_guard`/`session_service`/`stateless`/`aggregate` | Module deleted outright; every call site (all confirmed no-ops — nothing ever activated a broker context) removed from the four hot modules |
| Cut `private_backend_bootstrap` + `session_control_auth` branches out of `app/server.py` | `private_backend_bootstrap.py` deleted along with its `app.state.private_backend` gating and every `NativeBroker*` handler in `server.py`. **`session_control_auth.py` was kept**, deliberately deviating from this table's literal wording: it is a signed, replay-resistant, target-bound HMAC session-disposal scheme whose `control_secret` can come from either the broker *or* the plain `AMPRANG_TOKEN` env var — it was never broker-only, and it carries ~20 real security regression tests. Removing it would have deleted working, tested access control for no reason tied to the broker's absence. |
| Rename installed top-level packages (`app`, `ai_guard`, `pii_redactor`) under `amprang.*` | `app` → `amprang.server`, `pii_redactor` → `amprang.engine`, `ai_guard.py` → `amprang.cli`. Only the top-level `amprang` module surface (facade, CLI entry point) keeps a semver contract; `amprang.engine.*` and `amprang.server.*` are internal. See the rename commit for the three classes of sed-collateral-damage found and fixed (indented imports, string-literal module paths, mangled quoted path segments). |
| Per-caller API keys with fail-closed default for any agent-facing deployment | `amprang-mcp --transport http` now refuses to start without `AMPRANG_MCP_KEYS="caller_id:key[,...]"` — no absent-key-open fallback. A hand-rolled constant-time bearer-key ASGI middleware gates the streamable-http app rather than the mcp SDK's OAuth-shaped `AuthSettings`/`token_verifier`, which needs a real issuer and stands up authorization-server discovery routes that don't apply to a static shared secret. stdio needs no key (process-local, not network-reachable). The local FastAPI server's single-env, absent-key-open `AMPRANG_API_KEY` is unchanged — it is loopback-only by default (`check_binding`) and opting into a remote bind already requires `--allow-remote` *and* a key, so its risk profile differs from a bare shared MCP endpoint. |
