# PDPA category assessment and lifecycle design

This local extension represents 11 named sensitive families, 11 general
navigation families, and two explicitly open/unassessed review slots. It does
not enumerate every possible personal datum, inspect raw media, certify legal
compliance, verify consent/identity or execute retention/rights actions.

- [Legal and alternatives design](reports/PDPA%20coverage%20and%20lifecycle.md)
- [Controller lifecycle records/states](LIFECYCLE-DESIGN.md)
- [Registered implementation/evaluation plan](../../docs/research/pdpa-coverage-plan.md)
- [Independent corpus QA](corpus-qa.json)

## Working caller path

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe ai_guard.py pdpa coverage
.\.venv\Scripts\python.exe ai_guard.py pdpa assess input.txt --context context.json --output assessment.json
.\.venv\Scripts\python.exe ai_guard.py pdpa lifecycle --context context.json
```

The context uses closed enum/boolean/date fields. An example without subject
data is in `context.example.json`. Inputs may be UTF-8 text-like TXT/JSON/CSV or
text-layer PDF. JSON/CSV are assessed as text, not a validated structured-data
parser. Declared image/audio/video/genetic files and image-bearing PDFs are
explicitly not assessed; they require qualified modality review. No implicit
recursive scanning, output overwrite, new HTTP/native routes or action executor.

The catalog distinguishes partial text evidence from unsupported or unassessed
capabilities. `legal_clearance` is always false. Section26 remains warn/review;
masking/direct identifier protection stays in the existing core. Legacy report
grades/keyword notices are not comprehensive legal assessments and have not
been promoted into this mode. Existing Desktop/Extension/Hosted interfaces are
not migrated by this CLI work.

## Actual model experiment

The optional hybrid runs real pinned MiniLM locally in `.venv-pdpa-ml`, with
safetensors/config/tokenizer fingerprints, CPU, no remote code or model fallback,
and source-offset token windows that reject truncation/integrity failures.
The ordinary application environment and dependency lock remain unchanged.
`model-manifest.json` records the public revision and cache path. Similarity is
not probability. Use an explicit `--strategy hybrid --model-dir <snapshot>`;
missing assets fail instead of returning an empty finding list.

## Data and evaluation boundary

280 fictional records were independently authored and reviewed:70 calibration,
210 encrypted evaluation. Templates/families are split-disjoint; 12 records
were corrected before freeze. The exact original guide is preserved in
`annotation-guide-at-freeze.md`; metadata clarification adds primary-category
counts without feeding that label to a detector. No old YRSS or blind set is
reopened. External originals/key stay at
`C:/Users/teera/aiguard-pdpa-context-v1/`.

Corpus limitations are material: AI authors/reviewers, explicit fiction cues,
explicit ambiguity cues, recurring genres and artificial ID/order schedules.
Only text and declared modality enter classifiers, never ID/scope/targets.
General features in sensitive-scoped records are not independently adjudicated.

The initial calibration was retained, including poor attribution performance.
Ordinary third-person references, student-field/generic-discussion separation,
reported possessives and all-catalog semantic prototypes were developed with
synthetic RED/GREEN tests before final evaluation. This is development, not an
independent gain claim. Final calibration will choose the registered operating
point and bind the exact metric/helper/model/source identities. One final batch
of three strategies is reserved; no tuning follows disclosure.

## Lifecycle comparison boundary

`benchmark.pdpa_workflow_study` compares three actual policy functions on20
hand-authored functional scenarios: a deliberately weak uniform-consent gate,
manual-only review, and the basis/lifecycle planner. Scenario satisfaction is
not independent legal accuracy, live approval, deletion or rights fulfilment.
Actual registries, authenticated authority, connectors and verified outcomes
remain the separate organization architecture in LIFECYCLE-DESIGN.md.

## Verification ledger

- Shared core, real CLI, closed context, no-value/errors, no-overwrite, optional
  engine failure, model/chunk integrity, legal-clock and proposal-only tests.
- Independent whole-change review found five blockers: lifecycle sensitivity,
  parser errors, selected threshold drift, embedded personal statements and
  missing metric/decode fingerprints. All were reproduced and fixed.
- Final local Python run:2,840 passed,34 skipped; one existing dependency warning.
  Lint/format/version/diff checks passed. Existing-path sanitizer anchor remains
  red before and after these additive modes; it was not moved. There is no
  claim of remote CI, installed-host, provider, modality or production acceptance.
- Final corpus comparison and method recommendation remain pending.
