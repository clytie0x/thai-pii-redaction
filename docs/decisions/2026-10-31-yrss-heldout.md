# YRSS accuracy campaign held-out pre-registration

Date: 2026-10-31. Authorized scope: owner's accuracy/evidence goal.
This record precedes new corpus authoring and every detector change.
Version: `yrss-holdout-v1`. This does not rotate, reopen, or spend blind-v2.

## Question and estimand

Does the final mechanism-fix candidate improve over root baseline
`19fe9f0c209c587c7662ee5302edc752f0fd32c8` on independently authored synthetic
Thai documents, without losing protective character coverage? These results
estimate performance on this constructed corpus, not real-world prevalence.

Primary endpoint: paired difference in unrestricted entity F2, candidate minus
baseline, with 95% percentile document-bootstrap CI (1,000 shared resamples,
seed 0). Reuse the unchanged `benchmark/scorer.py` matching convention. Report
both arms' F2 intervals. Secondary endpoints: shared-11 F2, type-agnostic
character coverage/precision, exact typed boundaries, completely/partly
uncovered gold entities, negative-slice clean-document rate in both views,
per-type descriptive counts, and local timing/memory. Do not interpret an
interval including zero as a demonstrated improvement.

## Composition and isolation

185 documents: address_varied 12, bank_phone 11, education 11, finance 11,
gov_form 11, id_docs 19, long_form 12, medical 11, messy 12,
name_no_cue 12, negative 52, student_id_varied 11. Use the existing 11-type
annotation guidelines and `benchmark.blind.TYPE_MINIMUMS` unchanged.

An author in a fresh context gets only the annotation guidelines, slice/count
requirements, and independently generated valid checksum pools. It must not
read detector code, gold, any earlier blind corpus, benchmark results, or
development error lists. A second fresh context reviews semantics, missing
labels, boundaries, uniqueness and negative purity, under fix-only rules.
There is no detector-disagreement pass. Same-family agent authoring/review
is an explicit limitation; neither human agreement nor cross-family bias
reduction is claimed.

Plaintext and generated blinding key stay at the intentional external path
`C:/Users/teera/aiguard-yrss-holdout-v1/`. Never read this directory in the
development context or run a recursive search over it. Only the isolated
author/reviewer may inspect its text. Existing authenticated blinding and
lock-file validation are reused, with ciphertext and aggregate metadata in
`benchmark/data/`. Do not force-refreeze. Preserve external originals.

## Evaluation and stopping

One paired disclosure, baseline plus one final candidate, after candidate
identity and development-only selection are fixed. Ciphertext is frozen
before tuning. Scoring happens in an isolated evaluator context and returns
aggregate metrics only. A paired audit artifact binds both source manifests,
model hashes, scorer hash, corpus hashes, and the paired CI procedure.
No intermediate candidate, ablation, per-document held-out result, or text
may be disclosed. This corpus has a budget of two scored arms, not two rounds
of feedback. Preserve the old blind audit chain; append the new campaign's
auditable arms or dedicated paired record without rewriting history.

After disclosure, do not tune further and reuse this set as fresh evidence.
Report negative/null results. A failed integrity check is a failed evaluation,
not permission to repair the corpus using detector output. A new hypothesis
after disclosure requires a new protocol and fresh held-out corpus.
