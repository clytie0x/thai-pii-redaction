# Shared-core and proxy error migration

State: development candidate, not a published release. The owner's
[accepted decision](../../../../docs/decisions/2026-11-02-shared-core-compatibility.md)
selects root warn/report, a direct first-party `thai-pii-redaction-core`
dependency, fixed proxy errors and privacy-qualified rollback artifacts.

## Versioned transition

Current `VERSION` remains `0.1.0` during development and acceptance. The planned
migration release is a new minor version, `0.2.0` or another separately approved
new version. Do not overwrite or republish an earlier artifact with changed
contracts. The release process must synchronize core/SDK versions, the exact
dependency pin and the SDK lock, then qualify both supplied distributions.
This plan does not authorize a release, registry publication or deployment.

The following changes have different implementation states:

| Change | Current candidate state |
| --- | --- |
| Fixed upstream proxy errors | Implemented; synthetic ASGI and packaged-path checks are recorded separately |
| Proxy AnyIO dependency | Explicit `anyio>=4.4.0`; the required public task API is checked before app startup |
| Canonical root compatibility prerequisites | Eight additional structured types, immutable configuration and failure containment implemented in the root |
| SDK facade/HTTP/MCP canonical imports and direct dependency | Not implemented by this prerequisite checkpoint |
| SDK sensitive warn/report behavior and all ten report categories | Approved; integration and matched migration tests remain open |
| Hosted canonical build and exact-image acceptance | Open; no deployment is implied |

## Fixed proxy errors

Earlier source restored tokens recursively inside upstream error bodies and
returned those values. The new error body is always:

```json
{"error":{"message":"upstream request failed","type":"upstream_error"}}
```

For HTTP errors in the 400-599 range, retain the numeric status with this fixed
JSON body. No upstream error body is read or restored, and upstream headers are
not copied. Transport errors, HTTP 200 error envelopes, non-JSON or unsupported
success shapes use status 502 with the same body. Clients must classify by the
status and fixed type, not parse provider messages or nested provider JSON.

Only the supported OpenAI text-completion schema is restored. Tool/function
output, non-text content, a nonempty refusal field, invalid Unicode, malformed
choices and unknown envelope fields are outside that success schema. Supported
metadata and numeric usage/logprob structures are validated before projection.
This is a text proxy, not a generic passthrough for every provider response.

## Streaming and cancellation

The supported event profile uses `data` fields and optional `event: message`.
It joins multiline data before JSON validation and drops comments. Unsupported
control fields, malformed/in-band errors, EOF without `[DONE]` and transport
failures terminate through fixed metadata; provider diagnostics never pass
through as arbitrary SSE lines. This uses
[SSE message framing](https://html.spec.whatwg.org/multipage/server-sent-events.html#event-stream-interpretation).

Once response headers are committed, a failure uses a fixed error data event
and omits `[DONE]`. Held token fragments are discarded. Successful text already
emitted may contain intentionally restored values and cannot be retracted; the
error event itself contains only fixed metadata. Clients must handle an error
event or incomplete stream as failure, not as a completed answer.

Response/client cleanup is joined before return, including cancellation during
cleanup. Request mappings and held restorer state are dropped in `finally`.
Cancellation is re-raised after sensitive handler frames return; ASGI 2.3 and
2.4 after-header cases are covered. Dropping references does not guarantee
zeroization of Python immutable strings. No live-provider, network transport,
Trio or production qualification follows from the synthetic tests alone.

The task-state API used to preserve cancellation across the legacy task group
is present in the [AnyIO 4.4 source](https://github.com/agronholm/anyio/blob/4.4.0/src/anyio/_core/_testing.py).
Both the locked 4.14.2 environment and an isolated 4.4.0 environment passed the
focused proxy contract checks. That evidence does not cover every dependency
combination admitted by broad version ranges.

## Upcoming policy and installation changes

The earlier SDK engine automatically masks some person-linked Section 26 spans.
The approved canonical target reports/warns on those categories instead. It must
still mask separately detected identifiers and fail closed on residual PII.
For example, an identity/phone in a health sentence remains protected; a health
finding alone is a report signal rather than a reason to block or mask text.
Do not assume the target behavior is active until the facade, Session, batch,
HTTP, MCP and proxy paths all pass matched tests against the same core.

The direct core dependency intentionally adds `pii_redactor`/`app` namespaces,
PDF dependencies and assets. Use the first-party `thai-pii-redaction-core`
distribution, never the unrelated public `aiguard`. Clean wheel/sdist installation,
model/configuration isolation and index-free container qualification remain
required. Root configuration must not enable remote TNER in an SDK operation.

## Operational enablement and rollback

Keep the operational proxy path disabled until the exact replacement and a safe
rollback artifact satisfy the approved privacy/error contract. A retained old
wheel establishes provenance, not rollback eligibility. Verify hashes, first-party
identity, installed code origins, positive/failure behavior and every required
CI job before routing production traffic. If no qualified rollback artifact
exists, keep the affected path disabled. No release or deployed route was changed
by preparing or testing this candidate.
