# AI Guard Thai PII competition evaluation

Status: deterministic baseline complete on 2026-08-10. Detector/runtime source:
`72e18bbe723adaf54c847e4b17c2177dfa60dd68` (production pipeline `#35744`, VERSION `2.5.0`).

> This is a deterministic synthetic/adversarial evaluation suite, not a
> population-representative benchmark.

No provider, Tokenmind, production credential, production request, or sourced real-person record
was used. Public runtime behavior was not changed: the surface remains 16 routes and public PDF/OCR
redaction remains disabled.

## Evidence identity

- Corpus: `aiguard-thai-pii-adversarial-v1`
- Corpus SHA-256: `050f3310cad8f06f14a682a76ff7ea5da12eb40f707aed4938d0233aa664cfc3`
- Manifest SHA-256: `8c10872f8e5d1a0ae913d439f9e2a10b561cc5866b4a99e48631cb274f300a7a`
- Vendored upstream: `44ef30b0e8ea2021fc4ceec9d3b12dc9f64c750f`
- Local image ID: `sha256:06edf0bbcb51d12500004d6356fb381cabac194d4610e4bbacfd752b7f9d4764`
- Image revision label: `72e18bbe723adaf54c847e4b17c2177dfa60dd68`
- Offline thainer asset-tree SHA-256:
  `bc36ef28c16dbca39911add53e9b9a96ebb23edf6c8b00555d5647ba8629c315`
- Canonical three-pass prediction SHA-256:
  `21486e458ce6e031748bcb2566c11e54cf08a524d22f89c8ec35a0d985ab06ce`
- NER diagnostics: 414 chunks attempted, 414 succeeded, 0 skipped
- Network attempts: 0
- Provider calls: 0

The full machine-readable evidence is
`evaluation/thai_pii/baseline.72e18bbe.json`. It contains aggregate metrics and value-free
case/offset/type diagnostics, not corpus text or reidentification pairs.

## Corpus design

The direct-PII corpus has 138 cases from 87 base templates:

- 102 `mask_required` positive/mixed cases
- 24 `do_not_mask` clean/hard-negative controls
- 12 genuinely context-dependent cases excluded from headline scores
- 120 exact ground-truth entities
- two deterministic context presentations for every positive base template

It covers all 18 entity types the hosted revision emits: `ADDRESS`, `BANK_ACCOUNT`, `CREDIT_CARD`,
`DATE`, `DATE_OF_BIRTH`, `EMAIL`, `IBAN`, `ID_NUMBER`, `LOCATION`, `MEDICAL_ID`, `NAME`,
`ORGANIZATION`, `PASSPORT`, `PHONE`, `POSTAL_CODE`, `STUDENT_ID`, `THAI_ID`, and
`VEHICLE_PLATE`.

Contexts include HR/CV, healthcare, school, finance, addresses, documents, commerce, technical
text, chat, Markdown, JSON-like text, Thai/English adjacency, Thai digits, punctuation, line breaks,
unusual spacing, parentheses, and zero-width formatting. Negative controls include monetary values,
product/ticket/order numbers, course codes, documentation-reserved IP addresses, versions,
timestamps, dates used as release metadata, invoice numbers, postcode lists, headings, generic
organization/location terms, malformed email near-misses, and ordinary Thai words that resemble
names.

The separate Section 26 suite has 32 cases: two positive keyword cases and two contextual/negated
hard negatives for each of the eight supported signal categories.

## Detection results

| Measure | Result | Denominator / meaning |
|---|---:|---|
| Exact typed precision | 76.86% | 93 / 121 predicted entities |
| Exact typed recall | 77.50% | 93 / 120 expected entities |
| Exact typed F1 | 77.18% | micro, exact type and boundary |
| Typed IoU ≥ 0.5 precision | 83.47% | relaxed, one-to-one |
| Typed IoU ≥ 0.5 recall | 84.17% | relaxed, one-to-one |
| Typed IoU ≥ 0.5 F1 | 83.82% | relaxed, one-to-one |
| Exact boundary rate among relaxed typed matches | 92.08% | 93 / 101 |
| Protective-character recall | 91.57% | expected mask characters covered |
| Character precision | 88.51% | predicted mask characters justified by gold |
| Document-macro F1 | 62.96% | equal weight per scored document |
| Over-mask characters | 42.83 / 1,000 | across scored corpus text |

Exact entity errors were 28 false positives and 27 false negatives. The 24 clean/hard-negative
documents produced six false-positive entities across six documents: a 25.00% document-level false
positive rate and 8.28 false-positive entities per 1,000 negative-control characters. This is not
hidden or averaged away.

### Per-type descriptive results

Every stratum is below 25 gold entities, so all rows are descriptive and must not be generalized.

| Type | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| ADDRESS | 16 | 30.77% | 25.00% | 27.59% |
| BANK_ACCOUNT | 2 | 100.00% | 100.00% | 100.00% |
| CREDIT_CARD | 2 | 100.00% | 100.00% | 100.00% |
| DATE | 2 | 50.00% | 100.00% | 66.67% |
| DATE_OF_BIRTH | 4 | 100.00% | 100.00% | 100.00% |
| EMAIL | 14 | 100.00% | 100.00% | 100.00% |
| IBAN | 2 | 100.00% | 100.00% | 100.00% |
| ID_NUMBER | 2 | 33.33% | 100.00% | 50.00% |
| LOCATION | 2 | 33.33% | 100.00% | 50.00% |
| MEDICAL_ID | 4 | 100.00% | 100.00% | 100.00% |
| NAME | 22 | 65.22% | 68.18% | 66.67% |
| ORGANIZATION | 8 | 100.00% | 50.00% | 66.67% |
| PASSPORT | 2 | 100.00% | 100.00% | 100.00% |
| PHONE | 20 | 100.00% | 80.00% | 88.89% |
| POSTAL_CODE | 2 | 100.00% | 100.00% | 100.00% |
| STUDENT_ID | 4 | 100.00% | 100.00% | 100.00% |
| THAI_ID | 10 | 100.00% | 100.00% | 100.00% |
| VEHICLE_PLATE | 2 | 66.67% | 100.00% | 80.00% |

## Error taxonomy and known limitations

The value-free ledger classifies 42 diagnosis records:

- 14 complete missed entities
- 10 overextended spans
- 2 other boundary mismatches
- 1 wrong type
- 15 remaining false-positive entities

The main observed limitations are:

- Address component/coalescing boundaries are much weaker than structured identifiers. Exact span
  scoring is deliberately strict; protective-character recall is reported alongside it.
- Thai name coverage varies by title, explicit label, line structure, JSON-like context, and NER
  boundary behavior.
- Parenthesized and zero-width-obfuscated phone formats produced genuine misses in this corpus.
- Organization recall was incomplete, and one synthetic hospital organization was typed as a
  location.
- Context-free generic IDs, dates, locations, and NER guesses produced hard-negative false
  positives, including a ticket, course code, timestamp, invoice, release date, and generic
  province term.
- Internal entity scores are not calibrated confidence and are not exposed by the hosted API.

No detector code was changed after seeing these errors. The core is a manifest-pinned vendored
slice; fixture-specific tuning here would fork detector ownership and invalidate the baseline.
Bounded remediation belongs in upstream detector work with broader negative controls and a new
corpus version.

## Protection and restoration

Protection ran locally over all 102 positive cases in both modes with no provider:

| Measure | Token | Surrogate |
|---|---:|---:|
| Recognized source values removed | 100.00% (115/115) | 100.00% (113/113) |
| All expected gold values removed | 94.17% | 94.07% |
| Sanitized successfully | 100.00% (102/102) | 98.04% (100/102) |
| Fail-closed rejections | 0 | 2 structured PHONE residuals |
| Safe disposition (sanitized or rejected) | 100.00% | 100.00% |
| Exact restoration after controlled echo | 100.00% | 100.00% |
| Zero leftovers after successful restore | 100.00% | 100.00% |
| Restoration warnings | 0 | 0 |

The gap between recognized-value removal and expected-gold removal is the honest effect of detector
misses; masking cannot protect what was not recognized. The two Surrogate failures returned no
unsafe text and demonstrate fail-closed residual handling, not successful sanitization. No mapping
or generated replacement is present in the artifact.

## Section 26 heuristic signal evaluation

This is **HEURISTIC SIGNAL EVALUATION**, not PDPA compliance accuracy.

- Recall: 100.00% (16/16 keyword-positive categories)
- Precision: 50.00% (16 false signals on 16 contextual/negated negatives)
- F1: 66.67%
- Exact document category-set accuracy: 50.00% (16/32)

The result exposes the bounded truth: the current implementation finds its keywords but does not
understand negation, quotation, policy, news, or generic context. A flag is a review prompt, not a
legal decision, consent determination, or automatic redaction rule.

## Local performance observation

Measured in the revision-labelled Linux core image on local WSL2, with three warm corpus passes:

- 414 detection samples; median 0.79 ms, p95 1.50 ms, max 2.64 ms
- First detection after imports: 804.15 ms
- Mixed HR document: median 1.93 ms, p95 1.95 ms (5 samples)
- Corpus pass: median 117.71 ms, p95 118.59 ms
- Throughput: 1,171.43 documents/s and 46,271.59 characters/s
- Sanitize: median 2.25 ms, p95 3.72 ms (202 successful samples)
- Restore: median 1.06 ms, p95 1.73 ms (202 samples)
- Peak process RSS: 144,072 KiB

These are local detector/protection measurements, exclude Tokenmind latency, and are not an AI for
Thai hosted SLA or capacity guarantee.

## Competition-safe claims

- “AI Guard was tested on a committed 138-case Thai synthetic/adversarial direct-PII suite plus 32
  separate Section 26 signal cases.”
- “On this exact corpus and revision, exact typed precision was 76.86%, recall 77.50%, F1 77.18%,
  and protective-character recall 91.57%.”
- “Every entity the detector recognized was removed in both protection modes in this run; successful
  controlled echoes restored exactly, while two Surrogate cases failed closed.”
- “The evidence is reproducible, provider-free, value-minimized, and bound to corpus, model asset,
  image, upstream, and prediction hashes.”
- “We publish the misses and false positives instead of claiming perfect Thai detection.”

Claims that must not be made:

- population-wide or real-world accuracy
- perfect detection, zero false positives, or zero false negatives
- Thai-language coverage beyond the committed strata
- calibrated confidence
- that a green outbound rescan proves unrecognized PII cannot exist
- that Section 26 keyword flags are legal classification or PDPA certification
- that all shape-valid synthetic strings are guaranteed unallocated
- hosted latency/SLA or Tokenmind performance from these local numbers

## 60-second judge explanation

“เราไม่ได้อ้างว่าตรวจจับได้สมบูรณ์แบบ เราสร้างชุดทดสอบภาษาไทยแบบ synthetic/adversarial ที่ commit
ไว้ 138 กรณี ครบ 18 ประเภทที่ระบบรุ่นนี้ปล่อยออกมา และแยก hard negatives กับกรณีกำกวมออกชัดเจน
บนชุดนี้ exact precision 76.86%, recall 77.50%, F1 77.18% และครอบคลุมอักขระที่ควรปกป้อง 91.57%
ทุกค่าที่ระบบตรวจพบถูกนำออกก่อนส่งต่อ 100% ในทั้ง Token และ Surrogate; การ restore ที่สำเร็จกลับมา
ตรงทั้งหมด และสองกรณี Surrogate ที่ตรวจความเสี่ยงซ้ำไม่ผ่านถูกหยุดแบบ fail closed เราเผยทั้ง miss,
false positive และข้อจำกัดของ Section 26 ซึ่งเป็นเพียง heuristic review signal ไม่ใช่คำตัดสินทางกฎหมาย”

## Next research steps

1. Have at least two independent Thai reviewers adjudicate complete v1 documents without detector
   output, then version any corrections as v2.
2. Expand support to at least 25 gold entities per claimed type and add cluster-aware uncertainty.
3. Add paired base/perturbed robustness deltas rather than treating wrappers as independent natural
   samples.
4. Send bounded address/name/phone error classes upstream with negative controls; do not patch the
   hosted vendored core locally.
5. Re-run the exact locked suite only after a reviewed upstream detector sync.
