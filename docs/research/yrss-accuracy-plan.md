# YRSS accuracy campaign implementation plan

Goal: reproduce the existing result, inventory errors before changes, fix
confirmed mechanisms, isolate component contributions, and measure a frozen
candidate on independent synthetic held-out documents.

Authorization: the owner requested this complete sequence on 2026-10-31.
Execution is inline, with isolated author/reviewer contexts for held-out data
and one independent final review. No deployment, provider calls, version bump,
or changes to the submitted abstract are part of this campaign.

## Design and invariants

- Baseline: `19fe9f0c209c587c7662ee5302edc752f0fd32c8`, CRF/thainer.
- Reuse `benchmark.scorer.score` unchanged for historical comparability.
- Preserve gold-v4 and all old blind artifacts byte-for-byte.
- Use synthetic data only. Diagnostic artifacts contain IDs, offsets, types,
  and counts, never source values or documents.
- New held-out protocol: [pre-registration](../decisions/2026-10-31-yrss-heldout.md).
- Freeze the new corpus before detector edits. Reveal baseline and the final
  candidate together, after candidate selection. No tuning after the reveal.
- Keep detection, label correctness, complete character coverage, and outbound
  release behavior separate. A wrong type is not automatically a leak.
- Do not change masking policy for generic dates or quasi-identifiers to
  improve the benchmark. Do not broaden STUDENT_ID scope for exam candidates.
- The imported Hosted core is a separate pinned implementation. This campaign
  changes root core only; Hosted parity/deployment remains separate.

## Tasks and verification

1. Reproduce and identify the baseline. Add `benchmark/campaign.py` with
   source/corpus/dependency/model manifests, deterministic prediction digests,
   inventory, and component experiments. Test integrity failures and
   value-free diagnostics in `tests/test_yrss_campaign.py` before implementation.
   Repeat gold predictions offline and compare metrics and digests.
2. Freeze held-out data outside the development context. An isolated author
   and a separate reviewer receive guidelines and checksum pools, never gold,
   detector source, or outputs. Keep only ciphertext, lock, and aggregate QA
   in the repository. Record author/reviewer limitations honestly.
3. Build the baseline error inventory, then reproduce each proposed mechanism
   on new synthetic positive/negative controls. Add focused failing tests,
   implement the smallest fix, rerun the focused tests and gold differential.
   Keep policy/model limitations explicit instead of forcing them green.
4. Run format-only, raw CRF-only, full-system-without-name-context,
   full-system-without-FN-recovery, and full-system experiments using the same
   scorer/corpus. These are interventions, not independent additive gains.
5. Freeze candidate identity, review the code, then run the registered paired
   held-out evaluation aggregate-only. Report document-bootstrap paired F2
   differences and intervals, coverage, boundaries, and negative controls.
6. Run the Python lane, lint/format, version consistency, and diff checks.
   For core changes run `scripts/measure_perf.py` and a same-environment
   baseline control. Distinguish benchmark evidence from deployment proof.

## Review focus

- Incorrect labels whose text is already protected must not be counted as
  completely unmasked entities.
- Partial overlaps must not hide exposed suffixes; union coverage is required.
- Component ablations must restore process-global functions and NER state on
  exceptions and fail on skipped NER chunks.
- Reproduction must reject model/corpus/config/source drift, and must not
  overwrite a previous run directory.
- Held-out content must never enter a developer report, traceback, or diff;
  baseline and candidate must use identical scorer/model/data bytes.

## Evidence ledger

- 2026-10-31: clean clone on the baseline above; isolated feature branch
  `research/yrss-reproducible-detection`; locked Python 3.13 environment.
- Baseline gold: 252 documents, 648 entities, F2 0.9469240048250904;
  313/313 NER chunks succeeded. Historical headline reproduced.
- Baseline benchmark/protocol tests: 60 passed, 2 optional-engine skips.
- Ruling: use the existing clean canonical checkout and feature branch rather
  than another physical copy. There was no pre-existing local work to isolate.
- Ruling: use same-family fresh author/reviewer contexts for new held-out
  authoring. This prevents direct source leakage, but does not claim different
  model-family independence or human annotation.

Tasks 1-6 remain open until their evidence is recorded here and in generated
reports. All historical scores retain their original corpus and commit labels.

## Progress and expanded owner scope

- Tasks 1-2 complete: baseline reproduced with offline repeats and hashes;
  `yrss-holdout-v1` frozen at 185 documents/714 annotations before detector edits.
  Isolated author/reviewer QA is preserved at `research/yrss2026/heldout-qa.json`.
- Task 3 format checkpoint: card lengths, checksum-collision span retention,
  and Thai-digit phone prefixes have focused mechanism and mask/restore tests.
  Corrected full Python suite: 2,749 passed, 34 skipped; old corpora unchanged.
- Review corrections: preserve card detections beside numeric fields; prefer
  complete card coverage to a shorter Thai-ID prefix; bind runner/parser/loader
  and paired driver, not only scorer/model/source. Each was RED then GREEN.
- Ruling: short cards require explicit card context, because an existing OCR
  retry regression proved checksum alone promotes corrupted IDs. Existing
  16-digit compatibility is preserved, including its known overmasking limit.
- Ruling: reachable historical gold-v3 bytes were verified by the original
  SHA-256 before repairing its obsolete commit reference. No old score rebound.
- Ruling: freeze validation now rejects maximal exactly13-digit negative tokens,
  matching the written guideline; allowed longer reference codes were retained.
- 2026-10-31: the owner expanded the goal to research and implement difficult,
  high-value improvements. Research current alternatives before choosing the
  next contribution. Preserve this plan and the untouched held-out boundary.
  Tasks 4-6 remain open; no held-out disclosure or accuracy improvement claimed.
