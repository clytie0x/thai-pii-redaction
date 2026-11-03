# Assess PDPA coverage before automating lifecycle

**AI Guard should represent every statutory data family, assess personal attribution separately, and produce reviewable lifecycle plans without claiming complete detection or legal compliance.** Section 6 is an open identifiability test; Section 26 names sensitive families but does not turn keyword matches into facts about people. The inspected implementation has eight sensitive-topic categories and useful receipt, breach-assessment and DSAR-location helpers, but lacks a consent ledger or complete retention and rights workflow. The smallest justified extension is a shared assessment core with an additive CLI, preserving existing HTTP v2/native contracts and warn-only sensitive findings. Compare three real methods on fresh synthetic data before choosing a default: frozen keywords, contextual rules with existing NER, and those rules augmented by pinned local MiniLM embeddings. This report specifies that experiment and the governance design; **no accuracy, latency, deletion or workflow-fulfilment results exist yet**. Sources were reviewed on 31 October 2026; Thai legal text controls.

## Full category representation requires honest capability states

Section 6 concerns information enabling direct or indirect identification and excludes information specifically about deceased persons. Ordinary personal information therefore includes identifiers and linked financial, employment, education, relationship, location, device and behavioural records; it has no exhaustive statutory identifier dictionary. Applicability exceptions and territorial scope require separate review. The following catalog represents the named Section 26 families individually, including concepts currently grouped together. It is a **proposed assessment inventory**, not evidence that a detector supports every row. ([PDPA, sections 4–6 and 26](https://ratchakitcha.soc.go.th/documents/17082307.pdf))

| Legal family | Required assessment boundary |
|---|---|
| Direct identifiers, Section 6 | Names, IDs, contact/account details and identifiable images; invalid formatting does not establish anonymity. |
| Indirect identifiers and linked attributes, Section 6 | Assess combinations, context and linkage; missing NAME spans do not prove absence. |
| Race | Require origin evidence; surname, appearance or nationality alone is insufficient. |
| Ethnic origin | Represent separately from race and nationality. |
| Political opinions | Attribute an opinion; party names or election topics alone are weaker evidence. |
| Cult/doctrinal beliefs | Preserve this named scope beyond a religion dictionary. |
| Religious beliefs | Distinguish personal belief from places, institutions and general discussion. |
| Philosophical beliefs | Separate personal belief from quotations and academic topics. |
| Sexual behaviour | Use the statutory scope; do not equate all gender/sex vocabulary with behaviour. |
| Criminal records | Preserve allegation, prosecution, judgment, acquittal and no-record distinctions. |
| Health | Include attributable negative results and historical conditions. |
| Disability | Retain separate coverage, including overlap with health. |
| Trade-union information | Require personal relation; a union name alone does not establish membership. |
| Genetic data | Separate attributed genetic information from general DNA discussion. |
| Biometric data | Require identification-related technical context; ordinary photo/audio is not automatically biometric data. |
| Additional Committee-prescribed categories | Versioned extension point; applicable additional notification remains unverified. |

The biometric definition concerns technology-derived physical or behavioural characteristics capable of distinguishing a person. A facial photograph can identify someone under Section 6 without satisfying that Section 26 definition. A text engine can assess statements about genetic tests or biometric templates; it cannot inspect raw sequences, templates, images, audio or video without separately validated extractors. Mark those modalities `unsupported` or `metadata_only`. Keep capability (`supported_text`, `metadata_only`, `unsupported`, `not_run`, `unavailable`) separate from observation counts. Zero findings must never imply complete absence. The catchall requires an applicable Committee notification; this review did not establish one, so neither invent additional statutory categories nor claim the list is definitively exhaustive today. ([PDPA, sections 6 and 26](https://ratchakitcha.soc.go.th/documents/17082307.pdf))

Internally preserve evidence spans, subject linkage, polarity, quotation, temporality, provenance and uncertainty. Return `person_attributed`, `topic_only`, `uncertain` or `not_assessed` independently of the topic label. “Somchai tested negative for HIV” remains an attributable health assertion; a general explanation of HIV does not. Quotation and negation modify assertions rather than automatically excluding them. Pseudonyms can retain linkage and re-identification risk; replacing a name does not establish anonymity. These are design interpretations requiring labelled evaluation, grounded in the Act's identifiability test. ([PDPA, section 6](https://ratchakitcha.soc.go.th/documents/17082307.pdf))

## Three actual methods can test the remaining attribution gap

Presidio offers reusable recognizers and context enhancement, while GLiNER offers label-conditioned span extraction. Neither cited interface establishes person-to-sensitive-attribute relations or Thai PDPA accuracy. PII Engineer advertises Thai support, but its author benchmarks are unreplicated here. Reusing existing identity detection and adding a bounded attribution layer is therefore better supported than replacing the core. Fides provides governance concepts but its repository is archived; Klaro addresses website consent and OPA separates decisions from enforcement, rather than supplying a complete Thai lifecycle system. ([Presidio](https://presidio.dataprivacystack.org/analyzer/), [GLiNER](https://github.com/urchade/GLiNER), [PII Engineer](https://github.com/gantz-ai/pii.engineer), [Fides](https://github.com/ethyca/fides), [Klaro](https://github.com/kiprotect/klaro), [OPA](https://www.openpolicyagent.org/docs))

| Experiment | Actual computation | Main comparison |
|---|---|---|
| A: frozen baseline | Existing eight keyword categories with semantic processing explicitly disabled; unchanged identity detector. | Topic recall, false personal attribution and unsupported families. |
| B: contextual assessment | Expanded versioned cues plus existing NER, field labels, pronouns and bounded subject relations; preserve uncertainty. | Attribution improvement without new weights. |
| C: actual MiniLM augmentation | Real local embeddings propose multiple category candidates from positive/hard-negative examples, then B resolves attribution. | Added paraphrase recall versus review burden, latency and memory. |

C uses `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, pinned to revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`. Its model card documents 384-dimensional vectors and a 128-token limit; similarity is a ranking score, not calibrated legal confidence. Fingerprint local weights, tokenizer/configuration, package versions, backend, pooling, thresholds, prototypes and dataset splits. Load a declared local path offline with remote code disabled. If dependencies, verified artifacts or successful loading are missing, return `unavailable/not_run` or fail an explicit selection; never substitute keyword vectors or relabel B as C. No weights were downloaded or inference measured for this report. ([Model card](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2), [upstream revision metadata](https://huggingface.co/api/models/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2))

Create an independently authored Thai/English/mixed synthetic corpus covering every family, exact-keyword negatives, keyword-free paraphrases, first-person disclosures, multiple subjects, indirect linkage, quotes, negation, historical records, fictional/ambiguous context, OCR noise and unsupported media. Group related templates, paraphrases and value families into one split. Freeze development/final-test manifests before tuning; keep old closed held-out corpora unopened. Use independent annotation and adjudication for a final subset. Compare common eight-label results and full-taxonomy results separately: an unsupported positive is a miss, not a true negative.

Report per-category topic precision/recall/F1/F2, span exact/overlap metrics, attribution precision/recall, joint category-attribution correctness, topic-only false alerts, review rates and unresolved positives, with counts and uncertainty intervals. Preserve identity-output regression checks independently. Measure cold load, warm CPU p50/p95 latency, throughput, peak RSS, truncation and availability failures on identical documents/settings. Token-aware windows must preserve global offsets. Report incremental benefit and cost before promoting B or C; external API charges are unnecessary, while annotation, memory and maintenance still cost resources. Governance simulations separately score missing-evidence detection, abstention and unauthorized-action count. Weak “consent only” or “send everything to manual review” baselines belong only in that benchmark, never production decision rules.

## Consent and retention need purpose-specific evidence

Consent is one route, not a universal prerequisite. A processing record needs purpose/version, necessity, Section 24 route and, where relevant, the separate Section 26 explicit-consent or exception review, safeguards and approval. Missing consent evidence alone does not prove unlawful processing; a contract basis alone does not settle sensitive processing. Link notices, recipients/transfers and Section 39 records. Consent evidence requires a clear affirmative act, scoped purpose, notice/text version, time/channel, representative authority and append-only withdrawal history. Withdrawal should be as easy as granting consent; identify affected jobs/recipients and remaining lawful purposes without silently switching bases. ([PDPA, sections 19–27 and 39](https://ratchakitcha.soc.go.th/documents/17082307.pdf))

Capacity requires explicit review, not inference from age or disability. Thai Section 20 specifies parental-authority consent for age **not exceeding ten**; other minor cases depend on capacity under the incorporated civil-law rules. Custodian and curator authority are separate conditions. Do not encode “under twenty always requires guardian consent.” Store minimal protected evidence references rather than identity documents in ordinary exports. ([Thai PDPA, section 20](https://ratchakitcha.soc.go.th/documents/17082307.pdf))

Retention policies need purpose, owner, start event, duration/decision rule, legal source, review date, hold authority and disposal evidence for originals, extracted text, mappings, caches, logs, outputs, processor copies and backups. Unknown policy stays unknown. Holds require grounds and review dates. Backup delay requires suppression of access/use and completion when technically possible; restoration must reapply deletion, withdrawal, correction and restriction decisions. Masking or dropping an in-memory reference does not prove erasure. Processor instructions, agreements and acknowledgments matter; transfers need separate destination/safeguard review. ([PDPA, sections 23, 28–29 and 33–40](https://ratchakitcha.soc.go.th/documents/17082307.pdf), [2024 erasure notification, clauses 3–9](https://infocenter.oic.go.th/upload/cms/1744195455_4477.pdf))

## Rights clocks and prototype boundaries must stay explicit

Access design must track original receipt, identity/authority checking, deficiencies and complete receipt separately. The 2026 notification requires checking without delay and within **15 days of receipt**; correction opportunities must allow at least **10 days**, and a corrected complete request is received when complete. Fulfil without delay and within **30 days**, with at most a further **30 days** for specified necessity and notified reasons. Do not reset a clock for every identity check. Required channels include in-person/post, and request/fulfilment/refusal evidence must be retained at least two years. ([2026 access notification, clauses 5–12](https://ratchakitcha.soc.go.th/documents/121423.pdf))

The 2024 erasure notification requires qualifying requests to be addressed without delay and within **90 days from request receipt**, with statutory exceptions, copies/backups and technical safeguards assessed. Do not borrow the access completeness-reset rule for erasure. The planner must record receipt and the legal qualification decision, and return `deadline_requires_review` when either is unresolved. For qualifying unlawful-processing requests under Section 33(4), clause 7 requires deletion/destruction rather than substituting anonymization. Scheduled retention expiry is a different duty, with no universal 90-day grace period. Portability, objection, restriction and correction require their own scope/exceptions; this review established no universal numeric deadline for them. Objection can require immediate segregation rather than waiting in a 30-day queue. Identity verification, third-party protection, partial disclosure, refusal reasons and secure delivery precede closure. ([PDPA, sections 30–37](https://ratchakitcha.soc.go.th/documents/17082307.pdf), [2024 notification, clauses 3–9](https://infocenter.oic.go.th/upload/cms/1744195455_4477.pdf))

Implement an additive `pdpa assess` caller over a shared core, detecting identity spans once. Preserve HTTP v2/native fixed vocabularies and recommendations pending separate coordinated review. Existing receipt proves per-run evidence, DSAR locates, and breach assessment summarizes signals; none proves consent, identity verification, notification or rights fulfilment. Current semantic errors can collapse to empty findings, and legacy grades predate semantic augmentation, so expose engine status independently and do not reuse those grades as comprehensive assessment. These are static source observations. ([Report](../../../pii_redactor/report.py), [semantic detector](../../../pii_redactor/sensitive_detector.py), [HTTP contract](../../../app/http_v2.py), [integration inspection](../research_notes/PDPA%20coverage%20and%20lifecycle%20integration.md))

The prototype accepts a closed context schema and emits fixed-code, non-executing plans. Caller declarations remain `simulation_only` until an authoritative system verifies them. Keep detailed evidence transient/protected; exported JSON and errors must exclude raw text, values, filenames, subject hashes, reversible tokens and arbitrary exception messages. This illustrative sketch uses enums and bounded fields, not executable instructions:

```json
{
  "schema": "aiguard.pdpa-assessment/1-proposed",
  "context": {
    "purpose": "review_required",
    "basis_evidence": "declared_unverified",
    "capacity": "undetermined",
    "retention": "unknown",
    "rights_request": "access",
    "receipt_state": "needs_verification"
  },
  "engine": {"requested": "context_rules", "semantic": "not_run"},
  "plan": {
    "state": "simulation_only",
    "actions": ["verify_authority", "review_basis", "review_deadline"],
    "execution": "none"
  }
}
```

The workflow is intake, verify evidence, assess purpose/conditions, review exceptions, locate, propose action, obtain controller approval, then record independently evidenced outcomes. Until executors exist, the prototype stops at proposal. Accepted invariants are no implicit network/model fetch, no silent optional-engine fallback, sensitive findings remaining warn/report only, no automatic consent/deletion/rights action, and no fabricated evidence or schedule. Later implementation must test privacy/error paths, real CLI dispatch, unsupported families, explicit engine failure, no-overwrite/output-alias protection and unchanged contracts, then run the affected repository gates. This research changes no acceptance state.

## Conclusion

The useful deliverable is a traceable inventory of assessed evidence, unsupported scope and decisions still owed by the controller. Choose an implementation default only after the fresh three-way comparison shows its attribution benefit and operating cost. Operational consent, retention and rights require authoritative evidence and execution adapters beyond this bounded planner; extending those boundaries deserves a separate reviewed decision.
