# Machine-context restoration and streaming

Status: owner-approved policy on 2026-11-03; implemented with bounded local
evidence; exact-candidate CI and controlled-performance gates remain open.

## Context

The owner selected stricter restoration and streaming behavior before branch
consolidation. The older restore-context patch cannot be copied unchanged:
mapping-only APIs cannot prove whether a URL came from the source, current
callers return partial text, and proxy streaming bypasses `reverse_map`.
Whole-text digest equality alone also authorizes too much: source text may
contain a previously known token copied into a new machine context.

## Decision

1. Bulk and streaming restoration keep a known pseudonym unchanged in a URL,
   Markdown link/image destination or reference definition, or HTML/XML tag or
   attribute, including raw script/style content and markup comments, unless a
   trusted source-rebuild occurrence is proven. Human-readable
   text outside those contexts retains ordinary restoration.
2. Mapping-only restoration has no source proof. Its former arbitrary URL
   roundtrip behavior intentionally changes to partial restoration. Plain-text
   legacy Sensitive tokens and `prior_mapping` identity reuse remain supported.
3. A source-rebuild exemption requires both exact sanitized-text equality and
   the exact replacement occurrence range created by the canonical core.
   Session proof is published only after successful finalization, bound to the
   existing bounded digest cache and cleared with its lifecycle. Same-call
   paths use the sanitize result they still own. No wire/client-supplied ranges,
   digests or booleans grant this exemption.
4. Streaming has no whole-message source proof and applies the strict default.
   One canonical core component owns its context policy and incremental token
   restoration. The SDK adapter delegates to it. Arbitrary chunk boundaries,
   incomplete contexts, errors and cancellation must not release a protected
   original. Preserve incremental delivery with bounded state and token/lookahead
   buffering; do not buffer the whole response or disable streaming.
   Ambiguous context remains protected until a safe decision; reaching a buffer
   bound never permits restoration. A completed line-start token must await the
   possible reference-definition colon before exposing an original.
5. Preserve existing public response fields and partial/leftover status handling.
   Do not silently redefine replacement counts for mixed restored/withheld
   occurrences. No mapping, raw source, URL, restored value or provider body is
   added to diagnostics or acceptance records.
6. This is a context-sensitive restoration policy, not an HTML sanitizer,
   network firewall or general prompt-injection verdict. Section 26 and
   prompt-injection warn/report policy remains unchanged.

The owner approved the stricter public policy. The occurrence-proof and shared
incremental implementation are engineering choices to preserve source identity,
bounded memory and one authored protection core.

## Compatibility and acceptance

Exact source URL reconstruction remains available only where core-owned
occurrence evidence exists. Standalone mapping-only and streaming callers may
retain tokens in machine contexts even for an echoed URL. Existing ordinary
reidentify success fields and plain-text restoration remain supported.

Require adversarial review and tests for copied old tokens, altered destinations,
surrogate/token modes, legacy mappings, partial results, every chunk split,
bounded buffering, cancellation, lifecycle/eviction and failed-finalizer rollback.
Rebuild and qualify exact artifacts after core changes. Current performance,
CI, host, legal and pilot gates remain open; this decision grants no waiver or
deployment authorization.

Raw study and pre-integration heads remain preserved separately. Neither
historical research scores nor earlier artifact results qualify this change.
