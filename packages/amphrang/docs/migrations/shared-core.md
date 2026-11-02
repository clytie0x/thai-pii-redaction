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
| SDK facade/HTTP/MCP/proxy canonical imports and exact core dependency | Implemented in source; final combined wheel/sdist and CI qualification remains open |
| SDK sensitive warn/report behavior and all ten report categories | Implemented with matched synthetic Python and adapter tests; historical automatic-mask scores do not qualify this policy |
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

## Policy and installation changes

The earlier SDK engine automatically masks some person-linked Section 26 spans.
The canonical candidate reports/warns on those categories instead. It must
still mask separately detected identifiers and fail closed on residual PII.
For example, an identity/phone in a health sentence remains protected; a health
finding alone is a report signal rather than a reason to block or mask text.
The Python facade, Session, batch, HTTP, MCP and proxy paths consume the canonical
core. Python/MCP expose `section26:<CATEGORY>` in their existing warnings field;
HTTP uses the existing warnings field with fixed codes and counts. The proxy
emits fixed-code Python operator warnings without adding OpenAI fields or headers.

The direct core dependency intentionally adds `pii_redactor`/`app` namespaces,
PDF dependencies and assets. Use the first-party `thai-pii-redaction-core`
distribution, never the unrelated public `aiguard`. Clean wheel/sdist installation,
model/configuration isolation and index-free container qualification remain
required. Root configuration must not enable remote TNER in an SDK operation.

### Supplied artifacts only

The SDK requires `thai-pii-redaction-core==0.1.0`. Its wheel contains only
`amphrang`; the separately supplied core owns `pii_redactor` and `app`, including
PDF dependencies and assets. The development uv source is `../..`, never a
public-index fallback for this core. Frozen CI sync excludes core installation;
an explicit pinned build step builds the core and installs that exact wheel
before the SDK is imported.

Install a qualified pair and its trusted dependency wheelhouse with index access
disabled. Replace the example paths with the reviewed artifacts:

```sh
python -m pip install --no-index --find-links /qualified/wheelhouse \
  /qualified/thai_pii_redaction_core-0.1.0-py3-none-any.whl \
  '/qualified/amphrang-0.1.0-py3-none-any.whl[server]'
```

Use `[proxy]` or `[mcp]` on the supplied SDK wheel for those optional surfaces.
Do not use a bare registry pin, mix public/private indexes, or remove an unrelated
`aiguard` installation. A verified old first-party installation requires explicit
migration: overlapping old/new `app` and `pii_redactor` files are not accepted
as safe coexistence. The installed-artifact checker takes the installation
directory, SDK wheel and core wheel; it checks identity, exact pin, owned files,
namespace collisions and canonical imports before an offline synthetic roundtrip.

At release preparation, run `scripts/bump_version.py` for the approved new version,
then regenerate/check `packages/amphrang/uv.lock` and rebuild/requalify both
distributions. Development does not bump VERSION.

### Container context and internal compatibility

The SDK Dockerfile now consumes an artifact-only context: `wheels/`, a trusted
`wheelhouse/`, pre-provisioned `models/`, and
`qualification/check_sdk_installed.py`. Each artifact directory needs a complete
`SHA256SUMS` inventory. Installation and model qualification run without network
access; missing, extra or modified files fail the build. The root SDK CI job
prepares that context from pinned source/dependencies, then checks no-key refusal,
keyed routes and network-isolated runtime. Actual image acceptance remains open
until the exact image executes in Docker; source checks do not establish it.

Private `amphrang.engine` module paths remain as thin aliases to the identical
canonical module objects, including shared monkeypatches and caches. The SDK's
protection engine no longer contains separately authored detector, vault,
provider or report code.
The obsolete private `detectors.sensitive_span` module was removed rather than
preserving an automatic-mask profile. Historical private imports carry no
cross-release stability guarantee.

Private aliases use canonical function signatures and defaults. Public SDK
adapters retain `AMPHRANG_*` settings and local-only behavior; internal callers
bind the SDK snapshot explicitly instead of rewriting process environment.

Benchmark detector, generator, strategy and blind-runner entrypoints now import
canonical modules. One captured local-only SDK profile governs engine selection;
benchmarks no longer mutate global environment settings or clear canonical
caches. Synthetic generation fingerprints for three seed/size combinations
remained identical. No gold data, labels, scores or held-out files were changed
and no standalone accuracy or live-provider benchmark was run. Routine SDK test
fixtures do not establish a new research score. Research baseline HTTP
callers keep their existing experiment mechanics and use only canonical shared
OpenAI parsing helpers; they are not the product's guarded provider path.

The release profile gate reads canonical identifier names and Section 26 report
categories independently. It does not equate a report category with a maskable
entity or promote historical accuracy measurements to the current candidate.

Two additional private expectations were adapted deliberately: the token label
table now contains 27 masking labels plus ten separately validated reporting
categories, and successful degenerate-chunk retagging uses the canonical
`WARNING` record instead of the older private SDK `INFO` severity. Recovery
invocation, exact record count, label/length metadata and no-text logging remain
tested. Failure-graph inspectors recognize both product namespaces; test fakes
accept the concrete configuration and prove they run on the intended path.

## Operational enablement and rollback

Keep the operational proxy path disabled until the exact replacement and a safe
rollback artifact satisfy the approved privacy/error contract. A retained old
wheel establishes provenance, not rollback eligibility. Verify hashes, first-party
identity, installed code origins, positive/failure behavior and every required
CI job before routing production traffic. If no qualified rollback artifact
exists, keep the affected path disabled. No release or deployed route was changed
by preparing or testing this candidate.

## S5.1 private-test expectation ledger

The prior sensitive-span module had 49 test functions. Five security and
identifier-preservation expectations remain, adapted only to canonical types,
configuration and return shapes. The other 44 were specific to the superseded
automatic-sensitive-mask policy: anchors, lexical vetoes, segment caps, merge
rules, sensitive entity emission and sensitive-only outbound blocking. Their
replacement checks enforce all ten warn/report categories, preserve independent
identifier masking and source spans, and retain synthetic legacy restoration.
The original code and historical decision remain in Git history. No test was
removed to conceal a failure; canonical range-coverage differences were reported
and fixed in the canonical implementation.

All replacement names below are in `tests/test_sensitive_span.py`.

| Previous test function | Disposition | Current check |
| --- | --- | --- |
| `test_person_linked_span_is_detected` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_positives_cover_every_category` | Superseded policy | `test_migration_covers_every_canonical_sensitive_category` |
| `test_bare_name_span_anchors_a_sensitive_span` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_name_span_swallowed_by_the_hit_is_not_its_own_anchor` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_impersonal_near_miss_emits_nothing` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_specificity_marker_promotes_a_vetoed_role_reference` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_register_veto_does_not_apply_to_a_named_person` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_the_specificity_window_is_clamped_at_the_segment_end` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_a_name_span_anchor_is_vetoed_by_the_impersonal_register` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_f4_accepted_cost_a_bare_real_name_in_a_register_segment_no_longer_anchors` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_a_lexical_tier1_anchor_still_beats_the_register_veto_beside_a_name_span` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_health_category_error_is_dropped_not_trimmed` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_health_category_error_veto_does_not_touch_a_real_health_span` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_a_result_cue_yields_its_label_to_genetic` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_a_result_cue_yields_its_label_to_biometric` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_a_result_cue_with_no_specific_keyword_stays_health` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_a_health_keyword_that_is_not_a_result_cue_keeps_its_label` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_a_single_space_never_splits_a_segment` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_two_spaces_split_the_segment` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_a_newline_splits_the_segment` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_span_never_expands_backwards_past_the_keyword` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_span_is_capped_at_max_span_chars` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_blocked_span_clamps_the_forward_end` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_sensitive_spans_never_overlap_each_other` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_merge_two_remainder_fixture_keeps_both_sides` | Superseded policy | `test_identifier_roundtrip_preserves_sensitive_text_and_warns` |
| `test_merge_two_sensitive_spans_inside_one_organization` | Superseded policy | `test_identifier_roundtrip_preserves_sensitive_text_and_warns` |
| `test_merge_sensitive_inside_location_yields_characters` | Superseded policy | `test_identifier_roundtrip_preserves_sensitive_text_and_warns` |
| `test_merge_never_trims_a_structured_fp_hit` | Superseded policy | `test_identifier_roundtrip_preserves_sensitive_text_and_warns` |
| `test_merge_never_trims_a_name` | Superseded policy | `test_identifier_roundtrip_preserves_sensitive_text_and_warns` |
| `test_merge_drops_a_candidate_fully_covered_by_a_blocker` | Superseded policy | `test_identifier_roundtrip_preserves_sensitive_text_and_warns` |
| `test_merge_sensitive_candidates_never_overlap_each_other` | Superseded policy | `test_identifier_roundtrip_preserves_sensitive_text_and_warns` |
| `test_merge_mixed_fixture_holds_the_invariant` | Superseded policy | `test_identifier_roundtrip_preserves_sensitive_text_and_warns` |
| `test_merge_without_sensitive_spans_returns_the_list_unchanged` | Superseded policy | `test_identifier_roundtrip_preserves_sensitive_text_and_warns` |
| `test_detect_all_emits_person_linked_sensitive_spans` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_detect_all_is_untouched_on_an_impersonal_document` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_token_labels_are_registered_exactly` | Superseded policy | `test_synthetic_legacy_sensitive_tokens_restore` |
| `test_every_sensitive_type_is_a_safe_outbound_leak_type` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_two_health_span_round_trip` | Superseded policy | `test_identifier_roundtrip_preserves_sensitive_text_and_warns` |
| `test_surrogate_mode_still_fakes_the_name_realistically` | Preserved | `test_surrogate_mode_still_fakes_the_name_realistically` |
| `test_analyze_counts_the_sensitive_span` | Superseded policy | `test_report_projects_categories_without_direct_sensitive_entities` |
| `test_scan_outbound_leaks_is_clean_on_masked_output` | Superseded policy | `test_identifier_roundtrip_preserves_sensitive_text_and_warns` |
| `test_scan_outbound_leaks_reports_an_unmasked_sensitive_phrase` | Superseded policy | `test_sensitive_only_never_blocks_or_masks` |
| `test_self_labelling_sensitive_token_does_not_fail_the_document_closed` | Superseded policy | `test_synthetic_legacy_sensitive_tokens_restore` |
| `test_the_real_vault_trusts_the_self_labelling_token` | Superseded policy | `test_synthetic_legacy_sensitive_tokens_restore` |
| `test_sanitize_chat_request_survives_the_self_labelling_token` | Superseded policy | `test_proxy_uses_operator_warning_without_sensitive_masking` |
| `test_a_pseudonym_containing_its_own_real_value_is_still_untrusted` | Preserved | `test_a_pseudonym_containing_its_own_real_value_is_still_untrusted` |
| `test_layer1_excuses_a_span_covered_by_two_contiguous_restored_ranges` | Preserved | `test_layer1_excuses_a_span_covered_by_two_contiguous_restored_ranges` |
| `test_layer1_still_halts_when_one_character_was_not_restored` | Preserved | `test_layer1_still_halts_when_one_character_was_not_restored` |
| `test_validate_output_raises_pii_leak_error_on_the_uncovered_character` | Preserved | `test_validate_output_raises_pii_leak_error_on_the_uncovered_character` |
