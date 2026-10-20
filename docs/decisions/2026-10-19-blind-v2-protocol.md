# Blind evaluation set v2 (blind-v2)

- Date: 2026-10-19
- Status: accepted; pre-registration, written before any v2 document exists
- Extends: [2026-07-28 blind set protocol](2026-07-28-blind-set-protocol.md),
  whose storage, validation, aggregate-only scoring and audit-log rules apply
  unchanged unless this record says otherwise

## Problem

`blind-v1` exhausted its reveal budget (6/6) on 2026-08-02 and is now a closed
audit trail. Every accuracy number produced since then comes from gold v4,
which the detector was tuned against, so the YRSS 2026 abstract's figures
(gold v4 F2 0.947, zero shared-11 negative-slice false positives) are
development-set results. The last v1 reveal (CRF, reveal 5) scored F2 0.898
with only 18 of 52 negative documents clean, and the poster due on
2026-11-24 needs a held-out number measured after the latest detector work.

Rotation reason (predeclared in the v1 protocol): reveal-budget exhaustion.

## Decisions

### Authoring

- Human authors were considered and deferred for schedule; v2 is
  agent-authored like v1, with one change aimed at independence: the draft is
  written by a **different model family** (OpenAI Codex, run through the
  Codex MCP) than the one that wrote gold v3/v4, blind-v1 and the detector
  rules. The author works in `C:\Users\teera\aiguard-blind-v2\`, outside every
  repository, and is given only `docs/annotation-guidelines.md`, the slice
  composition below, and pre-generated checksum-valid value pools. It is not
  given gold documents, blind-v1, or detector source.
- An independent reviewer context (a Claude subagent that has not seen the
  draft being written) checks missed PII, wrong labels, span glitches and
  negative-slice purity, under the v1 fix-only rule.
- **No pre-freeze detector disagreement pass.** v1 allowed one; v2 does not,
  so no detector output can shape the corpus.
- Neither agent reports document text or values back to the development
  context; their final replies are counts and error kinds only.

### Composition

Same slices and type minimums as v1 (`TYPE_MINIMUMS` in `benchmark/blind.py`)
so v1 and v2 are comparable: 185 documents —
address_varied 12, bank_phone 11, education 11, finance 11, gov_form 11,
id_docs 19, long_form 12, medical 11, messy 12, name_no_cue 12,
negative 52, student_id_varied 11.

### System under test

- Detector frozen at commit `cb43304d` (`pii_redactor/` unchanged from it).
  The only code change for v2 is benchmark plumbing: `run_blind(version=...)`
  and `python -m benchmark --source blind --blind-version blind-v2`.
- Gold v4 reproduces on this tree at CRF F2 0.947 (CI 0.928-0.964), checked
  2026-10-19 before authoring started.
- No detector change may land between freeze and the reveals below.

### Reveal budget: 2

1. CRF (the default engine) — the primary result.
2. The fine-tuned opt-in engine on the same commit, only if its weights
   (`AIGUARD_FINETUNED_MODEL_DIR`, kept outside the repo) are available;
   otherwise the reveal stays unused.

Primary metric: overall entity F2 with document-bootstrap 95% CI. Secondary:
negative-slice clean-document rate (unrestricted and shared-11), character
coverage recall, exact-boundary recall, family macros. Reveals append to the
existing `benchmark/data/blind-scores.jsonl` chain; reveal indices are
counted per version.

## Known limitations

- Still synthetic and agent-authored. A different model family reduces, but
  does not remove, shared-style bias; results must not be described as
  real-document accuracy.
- The development context chose the composition and wrote the guidelines the
  author follows.
- The draft and its authoring transcripts exist on the local disk outside
  the repository (accepted, as in v1).
