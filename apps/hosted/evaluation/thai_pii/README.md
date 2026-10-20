# Thai PII adversarial evaluation v1

This package measures the exact hosted detector and local protection primitives without starting
the HTTP service or calling an AI provider. It is deliberately outside `core/`, `api/`, and `web/`:
the detector remains the manifest-pinned vendored implementation and the evaluation files are not
copied into any runtime image.

The corpus is constructed locally from templates. It contains no sourced user, log, production,
provider, or real-person record. Shape-valid strings are synthetic-context test values; because no
allocation lookup is performed, the suite does not claim that every arbitrary string is impossible
to collide with a real allocation. Nothing in the suite is contacted.

## Contents

- `capabilities.json` — revision-bound executable capability inventory.
- `generate_corpus.py` — deterministic standard-library generator with fixed seed `20260810`.
- `corpus.schema.json` / `section26.schema.json` — strict, closed JSON schemas.
- `corpus.v1.json` — 138 direct-PII cases with code-point spans.
- `section26.v1.json` — 32 separate heuristic-signal cases.
- `manifest.v1.json` — generator/schema/corpus hashes, template counts, source exclusions, and
  annotation state.
- `evaluate.py` — provider-free detector, protection, restoration, metrics, diagnostics, and local
  performance runner.
- `baseline.72e18bbe.json` — untouched production-detector baseline.

The result artifact never contains corpus text, generated replacements, reidentification pairs,
request/provider bodies, cookies, or credentials. Diagnostics contain only case IDs/hashes,
code-point offsets, types, and bounded error categories.

## Reproduce the corpus

```powershell
python evaluation/thai_pii/generate_corpus.py
python tests/thai_pii_evaluation_contract.py
```

Regeneration must be byte-identical. The contract also checks schema closure, corpus hashes,
synthetic-source boundaries, expected spans, negative controls, ambiguous-case exclusion, metric
math, offline/provider-free structure, artifact privacy, runtime-image isolation, and the recorded
three-pass prediction hash.

## Reproduce the detector baseline

Use the revision-labelled production core image. The command passes no application credential and
disables container networking:

```powershell
$repo = (Resolve-Path '.').Path
$imageId = docker image inspect team08-core:latest --format '{{.Id}}'
docker run --rm --network none --entrypoint python `
  -v "${repo}:/workspace" -w /workspace `
  -e PYTHONPATH=/workspace/core `
  team08-core:latest evaluation/thai_pii/evaluate.py `
  --repository-sha 72e18bbe723adaf54c847e4b17c2177dfa60dd68 `
  --runtime-image "team08-core:latest@$imageId" `
  --runtime-revision 72e18bbe723adaf54c847e4b17c2177dfa60dd68 `
  --performance-repeats 3 `
  --output evaluation/thai_pii/baseline.72e18bbe.json
```

The evaluator removes credential-like environment variables, forces PyThaiNLP offline mode,
installs a fail-closed socket tripwire before importing the detector, and records zero network and
provider attempts. It uses the hosted product-equivalent path:

`clean_length_preserving → detect_all → sanitize_stateless → restore_stateless`

Protection uses internal reidentification material only in process to perform the controlled echo
restoration check. That material is cleared by the core and never serialized by the evaluator.

## Scoring policy

- Headline population: `mask_required` and `do_not_mask` cases only.
- Primary: one-to-one exact boundary + exact type micro precision/recall/F1.
- Secondary: typed IoU ≥ 0.5, protective-character recall/precision, over-mask characters,
  document-macro F1, per-type/per-scenario results, and clean-negative false-positive rate.
- `ambiguous` cases are reported but excluded from headline scores.
- Section 26 is scored separately as a keyword review signal. It is not PII NER and not PDPA legal
  accuracy.
- Every per-type stratum currently has support below 25 and is therefore labelled descriptive only.
- Performance is a local WSL2/container observation, excludes Tokenmind, and is not a hosted SLA.

## Annotation and review boundary

Spans are generated from template-bound annotations before detector output is viewed. They are
half-open Python Unicode code-point intervals. The v1 corpus has automated security and methodology
review, but independent Thai human adjudication is still pending. Therefore this suite is suitable
for reproducible competition evidence and error discovery, not a population-wide accuracy claim.

Any gold correction requires a new corpus version and changelog. The committed v1 files must not be
edited in place to improve a metric.
