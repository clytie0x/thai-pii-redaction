# Root-core overlap and confidence research gap

Scope: read-only inspection on 2026-10-31, branch `research/yrss-reproducible-detection`, while other working changes were present. No product files changed. Only fabricated in-memory strings/entities were exercised. No provider/network calls, model inference, real documents, or external held-out material were used. Historical decisions describe existing functionality, not current measured accuracy.

## Main finding

The smallest substantive algorithmic gap is **coverage-preserving resolution of conflicting spans under the existing reversible-masking contract**. Adding a broad detector or another name-cue collection would repeat existing work. A replacement resolver must preserve precise structured winners, account for uncovered residual characters, and keep original source positions, unique mapping identities, and restoration valid. The present code proves the need at the interval level; it does not establish how often this occurs in development documents or the size of an accuracy gain.

### Where coverage can disappear

- `pii_redactor/detectors/aggregate.py:19-41`: `dedupe_spans` sorts FP before TB, then start ascending and length descending, and discards an entire candidate on **any** overlap. A later-starting, partially overlapping TB candidate can lose its uncovered tail. A wide TB candidate containing a precise FP candidate can lose both residual sides. Scores do not affect this resolver.
- FP priority is broader than the docstring's checksum explanation: generic ID_NUMBER/address heuristics and FN fallbacks also have `redact_type="FP"`, sometimes with scores 0.6, 0.8, or 0.85 (`fn_scanner.py:15-38,138-188`; `fp_detector.py:814-829,994-1079`). A high-confidence TB candidate can therefore be entirely displaced by a lower-score heuristic FP candidate.
- `tb_detector.py:653-688` already solves a related problem internally: it removes a lower-priority candidate only when its **entire character interval** is covered. Consequently, TB deliberately returns overlaps to retain coverage. The final aggregate resolver does not preserve that general invariant. Its comment about downstream wide-span safety is true for nested same-start spans but not arbitrary crossing spans or FP intersections.
- `fn_scanner.py:145-155,175-177` suppresses a complete fallback candidate on any overlap with raw FP/TB output, before final aggregation. A new final resolver cannot recover evidence never submitted to it. Separately, FP's internal score-first greedy dedupe (`fp_detector.py:78-103`) also discards partial-overlap candidates; raw-pattern coverage and aggregate-input coverage are different populations.

## Existing targeted safeguards and duplication risks

- Address fragments are already coalesced under constrained gap rules (`aggregate.py:123-182`). `_extend_address_chains` (`aggregate.py:185-244`) retrieves raw TB ADDRESS tails lost to FP priority and clamps expansion at neighboring retained entities. This is an ADDRESS-specific repair, not a generic residual resolver.
- Strong record-name context already relabels conflicting TB candidates while refusing to shorten existing coverage (`aggregate.py:46-77`). Student-ID relabeling already overrides the generic ID_NUMBER type on equal spans (`aggregate.py:297-322`).
- Name processing already includes role cues, explicit line/inline labels, kinship, rosters, passport adjacency, Latin cues, and title/intro token passes (`name_context.py:639-835`). Conjunction continuation is implemented (`853-885`), as are repeated NAME/THAI_ID rows and OCR co-applicant evidence (`914-976`).
- Name hygiene already splits at newline/digit boundaries, rejects document/header compounds, trims role/field edges, and retags selected degenerate or isolated lines (`tb_detector.py:237-370,759-848,1040-1115`). The account-number-swallowed-name failure has an explicit regression (`tests/test_name_leak_mechanisms.py:169-198`). Adding those named mechanisms again would duplicate accepted fixes.
- The nested wide-name coverage case is already tested through `detect_tb` and `detect_all` (`tests/test_name_boundary_hygiene.py:218-257`). Existing pipeline overlap testing enforces non-overlap and phone masking, but does not assert coverage of the TB-only prefix (`tests/test_step9_pipeline.py:152-202`).

## Can residual fragments safely enter the present product?

| Consumer | Existing contract | Consequence for a resolver |
|---|---|---|
| Entity/registry | `models.py:34-61`: one immutable entity, one contiguous interval, one ID/type/value; counts are entity counts | Emit a new ID per fragment and set `original_text = source[start:end]`. Fragment counts are not person counts. The dataclass itself does not validate non-overlap. |
| Anonymizer | `anonymizer/anonymizer.py:409-442`: tail-first replacement and lookup by entity ID | Final intervals must be non-overlapping. Reusing a parent ID across residual pieces silently reuses the first fragment's mapping for different source content. |
| Consistency reuse | `anonymizer/anonymizer.py:164-179,228-254,452-501` | A fragment's text can be reused/replaced elsewhere as an independent value, losing the parent context. A short residual can produce wider document effects. |
| Vault | `session_vault.py:112-141,184-214`: ID-indexed records, pseudonym ownership, type-aware original lookup | Separate IDs are mandatory; collision protection does not distinguish two different fragments accidentally sharing one ID before `write`. |
| Reverse mapping | `reverse_mapper.py:119-192`: longest-first claims on untouched response, boundary guard at `15-51` | Bracket-token fragments can round-trip. Adjacent Thai surrogate fragments can leave a middle surrogate glued on both sides and rejected by the existing boundary guard. Natural-language model edits can additionally separate/reorder fragment meanings; identity round-trip does not prove utility. |
| PDF | `redactor.py:54-154`: exact source intervals and matching slices, all non-whitespace characters mapped; whole selected word boxes painted | Exact fragments are accepted, but several fragments inside one source word all select that entire box. PDF coverage is therefore coarser than character-span coverage. Do not promise partial-glyph redaction or normalize text without remapping. |
| Public detect output | `app/server.py:1312-1340`: highlights refer to caller text and must remain ordered/non-overlapping | Retaining overlapping candidates in the final list is not compatible with the caller-facing contract. |

Observed synthetic results from a short direct Python run using the repository virtual environment:

| Geometry/contract probe | Observed result |
|---|---|
| TB `[0,9)` plus FP `[3,6)` | Current aggregate kept only FP; 6 candidate-covered characters disappeared. |
| TB `[0,6)` plus TB `[3,9)` | Current aggregate kept `[0,6)`; 3 candidate-covered characters disappeared. |
| Partition `[0,3)`, `[3,6)`, `[6,9)` with identical ID on the two TB pieces | `anonymize(..., mode="token")` followed by `_do_reverse` failed equality; only 2 vault records existed. |
| Same partition with distinct IDs | Exact identity round-trip; 3 vault records. |
| Same pieces inside a single exact-source PDF WordBbox | Mapper accepted all intervals; the same whole box was selected 3 times. No raster PDF was generated in this probe. |
| Thai surrogate with Thai-letter neighbors on both sides | `_boundary_ok` returned false. This is a boundary-unit observation, not a full surrogate-flow experiment. |

These fabricated interval probes prove present mechanics, not prevalence, model quality, or a new algorithm's accuracy. The first round-trip probe initially used the wrong positional SessionVault constructor argument; it was corrected to `SessionVault()` before the reported successful run.

## Confidence: real opportunity, existing implementation boundary

- Every ordinary CRF/WangchanBERTa/TNER BIO candidate finalized by `tb_detector.py:714-756` receives **0.85**. The product consumes `.tag()` word/tag pairs at `900`, not CRF marginals. Rule scores around 0.87-0.90 function as priority constants. `models.py:51` describes TB score as confidence, which overstates this path's semantics.
- The installed PyThaiNLP code (`.venv/Lib/site-packages/pythainlp/tag/named_entity.py:116-154`, `tag/thainer.py:189-198`) calls its underlying CRF tagger but discards probability information from the public tuple result. Local inspection confirmed `pycrfsuite.Tagger.marginal` exists. No actual marginals were measured, and changing the shared adapter requires engine-specific handling rather than inventing probabilities for all engines.
- A locally fine-tuned engine already exists: `finetuned_engine.py:66-132` uses fast-tokenizer source offsets, 240-token windows with 60-token overlap, per-token maximum-confidence window selection, and mean chosen-label probability over each BIO run. `tb_detector.py:404-466` applies artifact-provided per-label floors, source hygiene, cue upgrades, and model verification of extended name cues. This is not an absent capability.
- `training/generate_data.py`, `training/train.py`, and `training/calibrate_thresholds.py` already supply synthetic generation, training, hard negatives/counterfactuals, dev checkpoint selection, and dev-only per-label threshold calibration. The manifest records 6,828 training and 680 dev documents with hashes. Current external weight availability was not inspected or assumed.
- Existing threshold calibration constrains **overlap entity recall** to within 0.005 of its unthresholded development value, using a fixed grid. It does not calibrate confidence reliability, exact boundaries, character leakage, cross-window disagreement, or downstream reversible fragments. Mean token softmax is not demonstrated to be a probability that the complete span is correct. Historical single-seed limits are explicitly recorded in `docs/decisions/2026-07-28-finetuned-ner-results.md`.
- Adding confidence values alone does not fix aggregation: the final resolver currently ignores them. Using confidence as an eviction threshold can reduce recall, including rare/OCR names, and requires an independently declared coverage constraint.

## Smallest meaningful experiment

1. Instrument stage-specific **candidate coverage lost to resolution**, using only development data and synthetic collision families, before changing behavior. Distinguish raw pattern candidates, TB retained candidates, aggregate input, final entities, and actually replaced output. Do not equate candidate coverage with true-positive coverage.
2. Compare the current greedy resolver with a deterministic, FP-anchor-preserving interval partition that subtracts occupied intervals and retains valid residual source intervals. Preserve parent provenance in internal experiment records; assign each emitted mapping fragment a fresh identity. Explicitly define what a residual's inherited type means and how one-character/whitespace/Thai combining-mark fragments are treated. Do not label a partial NAME as a newly discovered whole person.
3. Gate against structured-winner displacement, source-slice mismatch, any final overlap, leaked gold characters, negative overmasking, exact-boundary/type degradation, identity round-trip failure, and PDF source mapping failure. Report both coverage and typed/exact entity metrics, because fragmenting one entity changes entity counts and can distort overlap scoring.
4. Keep surrogate-mode restoration and repeated-fragment consistency as acceptance requirements, not an assumed consequence of token-mode success. If that requires separate semantic entities and replacement intervals, identify it as a larger representation change and review it independently.
5. Only after prevalence and utility are established, test whether actual CRF evidence or development-calibrated span/boundary evidence improves **which evidence owns each interval** at fixed coverage. Compare against the already-existing fine-tuned adapter; do not describe a new threshold sweep or generic fine-tune as novel.

This is a bounded core research question: can a resolver reduce privacy coverage loss without displacing structured evidence, inflating unsupported labels, corrupting reversal, or overmasking benign context? A synthetic proof is available now; a population effect and research novelty claim still require development measurements and comparison with current primary literature.
