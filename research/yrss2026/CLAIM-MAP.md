# YRSS 2026 claim map

Citation rules for the headline detection numbers. Thai glosses are in
parentheses. This page does not add a measurement. A rounded headline is the
Python format `.3f` of the stored float, and the stored float is the value
that may be checked.

Matching for gold-v4 and yrss-holdout-v1 is the scorer behind
`research/yrss2026/heldout-paired.json` and `baseline.json`. Matching for the
synthetic locks is type-aware overlap in `benchmark/blind_v2/score.py`.
Those two matchers are not the same experiment.

Measurement commits recorded inside the gold, holdout, and sealed-reveal
artifacts are **absent** from this clone (`git cat-file` does not resolve
them). The numbers below are still in files this clone contains. Absence of
the old commit is not a license to recompute the number on current `main`.

`gemma3:1b` on the original synthetic freeze is **VERIFIED** as the mean
of five seeded local samples. Counts are in
`docs/benchmark/runs/gemma-freeze-seeds.json`. F2 0.009 is an unreproduced
historical print. Sampling details are below.

## Summary

| Claim | P | R | F1 | F2 | Dataset / split | Held-out? |
|---|---:|---:|---:|---:|---|---|
| gold-v4 full, dev only | 0.8674033149171271 | 0.9691358024691358 | 0.9154518950437317 | 0.9469240048250904 | gold-v4, 252 documents, 648 entities | No. Development set (ชุดพัฒนา) |
| sealed blind-v2 reveal 1 | 0.5775962660443408 | 0.8839285714285714 | 0.6986591390261117 | 0.7991604778818212 | blind-v2, 185 documents, CRF, reveal 1 | Yes. True held-out, old freeze (ชุดปิด) |
| yrss-holdout-v1 baseline | 0.78748370273794 | 0.84593837535014 | 0.8156650911546253 | 0.8335633452939553 | yrss-holdout-v1, 185 documents, 714 entities | Yes. One paired disclosure, now closed |
| yrss-holdout-v1 candidate | 0.7989949748743719 | 0.8907563025210085 | 0.8423841059602649 | 0.8707557502738226 | same split, candidate arm | Yes. Same closed disclosure |
| synthetic hard-test | 0.9803921568627451 | 0.9615384615384616 | 0.970873786407767 | 0.9652509652509652 | hard-test-v1, seed 20261103, 60 documents | No. Not a held-out substitute |

Rounded with `.3f`: gold F2 0.947; sealed F2 0.799; holdout F2 0.834 to 0.871;
hard-test F1 0.971 and F2 0.965.

## gold-v4 F2 0.947, dev only

| Field | Record |
|---|---|
| Value | F2 0.9469240048250904; F1 0.9154518950437317; P 0.8674033149171271; R 0.9691358024691358; tp 628; fp 96; fn 20 |
| Metric | Unrestricted entity precision, recall, F1, and F2 |
| Dataset / split | `gold-v4`. 252 documents, 648 gold entities. Arm `full` |
| Held-out? | No. Dev only. The detector was tuned against this set |
| Source file | `research/yrss2026/baseline.json` `arms.full.metrics.overall`. Same F2 in `research/yrss2026/RESULTS.md` and `research/yrss2026/candidate-development.json` arm `full` |
| Commit SHA | File last changed in `52bd94a7b7dfac5bde8fe8a1cf5c2532051baec7`. Manifest `git.head` is `19fe9f0c209c587c7662ee5302edc752f0fd32c8` with `git.dirty` true. That object is absent from this clone |
| Lock hash | No gold lock file in this repo. Manifest `requirements_sha256` is `283cb10a3838b72cab3dbc3b10e54c6de437f211e2ddbbc73dd789a337911d1c`. Model `thainer-1.4` is `8c4f5b73434843d683442b42ddfaf2999a51d7c37579b27bac82c816c8a11e38` |
| Plaintext hash | Manifest `corpus_sha256` `01f86b012c438c074b86942e21021cf39b6df54e2bf950cb2301688b1c1b935b` |
| Reproducing command | Recorded in `research/yrss2026/README.md`: `python -m benchmark.campaign --out <new-dir> --ablations` after `scripts/prewarm_ner.py`, Python 3.13.12. Not re-run this session |
| MAY | Cite as a development-set result, with P, R, F1, and F2 together, and with the dirty-tree note |
| MAY NOT | Cite as held-out, as real-document accuracy, or as the score of current `main`. The shared-11 negative slice in the same arm has 0 false positives on 45 documents; the unrestricted negative slice has 15 false positives and 31/45 clean documents. Do not drop the view name |

Document-bootstrap 95% CI for that F2, stored in the same object: 0.9282772820864789 to 0.9639889196675901 (1,000 resamples, seed 0).

## sealed blind-v2 F2 0.799, true held-out, old freeze

| Field | Record |
|---|---|
| Value | F2 0.7991604778818212; F1 0.6986591390261117; P 0.5775962660443408; R 0.8839285714285714; tp 495; fp 362; fn 65 |
| Metric | Unrestricted entity precision, recall, F1, and F2. Primary pre-registered metric is F2 |
| Dataset / split | `blind-v2`, reveal index 1, engine `crf`, 2026-10-19T13:01:16+00:00. Not the later synthetic `blind-v2-repro` freeze |
| Held-out? | Yes. True held-out, old freeze. `over_budget` is false. Budget is 2; this entry spends reveal 1 |
| Source file | `benchmark/data/blind-scores.jsonl` line whose `version` is `blind-v2`. `entry_sha256` `84b7212555c8b623281cc00370c92c3284ea4921ef5a56cfb0dc901f34ecce5f` |
| Commit SHA | The jsonl file was last changed in `856db15bbd1451630b22b505be090468002536ff`. The entry's own `git.head` is `4cc5eb17aa16f2df7d5e65576cd5ba61f0737540`. That object is absent from this clone. The protocol names detector freeze `cb43304d`; that object is also absent |
| Lock hash | `benchmark/data/blind-v2.lock.json` ciphertext `d6fdd3713d7d72e456f19903f11533d3728c79b382048e693d357ab79aa529fe` (matches the reveal). Lock file sha256 `b152949920fb8c998fa20e6bdca9674c1abd7c48f6884f0e363201989c669eb5` |
| Plaintext hash | `a4503b4e3596dd56af19aef137ec25d2429ee8c09a9e4c94eb43d411ec6e56a5` in both the lock and the reveal |
| Reproducing command | Protocol command `python -m benchmark --source blind --blind-version blind-v2`. Not run this session. The ciphertext was not opened |
| MAY | Cite as the sealed blind-v2 CRF reveal at that freeze, with the CI below, and as a true held-out result for that old tree |
| MAY NOT | Cite as the score after the November 2026 detector fixes. The sealed corpus was not reopened. Do not cite the synthetic hard-test or `blind-v2-repro` number in its place |

Stored 95% document-bootstrap CI: 0.7671418873048201 to 0.8285105086810843. Negative slice in the same entry: 9/52 clean, 112 false positives.

## Sealed per-type recall, same reveal

Counts are true positives over gold `n` (`tp`/`n`) for the 11 types in
`benchmark.types.SHARED_ENTITY_TYPES`. In this entry `tp + fn` equals `n` on
every one of those types. Payment card is `CREDIT_CARD`. This is the stored
line, not a rescore, and the ciphertext stays closed. Citation limits are the
same as the sealed F2 section above.

Source file for every row in this section: `benchmark/data/blind-scores.jsonl`
line 7 (`splitlines()[6]`), `version` `blind-v2`, same `entry_sha256` as the
F2 section.

Recomputing command, from the repo root. It prints the eleven `tp`/`n` rows,
then `242 of 362`, then `metrics.shared_11.excluded_predictions`, then the
negative count. It reads the stored line and does not score a corpus:

`python -c "import json, pathlib; row=json.loads(pathlib.Path('benchmark/data/blind-scores.jsonl').read_text(encoding='utf-8').splitlines()[6]); types=('THAI_ID','PHONE','EMAIL','BANK_ACCOUNT','CREDIT_CARD','PASSPORT','VEHICLE_PLATE','STUDENT_ID','DATE_OF_BIRTH','NAME','ADDRESS'); by=row['metrics']['by_type']; print('\n'.join(t+' '+str(by[t]['tp'])+'/'+str(by[t]['n']) for t in types)); print(str(by['OUT_OF_SCHEME']['fp'])+' of '+str(row['metrics']['overall']['fp'])); print(str(row['metrics']['shared_11']['excluded_predictions'])); neg=row['metrics']['negative']; print(str(neg['clean_docs'])+'/'+str(neg['documents']))"`

| Stored count | JSON path |
|---|---|
| THAI_ID 39/39 | `metrics.by_type.THAI_ID.tp` / `metrics.by_type.THAI_ID.n` |
| PHONE 43/62 | `metrics.by_type.PHONE.tp` / `metrics.by_type.PHONE.n` |
| EMAIL 51/51 | `metrics.by_type.EMAIL.tp` / `metrics.by_type.EMAIL.n` |
| BANK_ACCOUNT 34/39 | `metrics.by_type.BANK_ACCOUNT.tp` / `metrics.by_type.BANK_ACCOUNT.n` |
| CREDIT_CARD 17/26 | `metrics.by_type.CREDIT_CARD.tp` / `metrics.by_type.CREDIT_CARD.n` |
| PASSPORT 26/27 | `metrics.by_type.PASSPORT.tp` / `metrics.by_type.PASSPORT.n` |
| VEHICLE_PLATE 27/27 | `metrics.by_type.VEHICLE_PLATE.tp` / `metrics.by_type.VEHICLE_PLATE.n` |
| STUDENT_ID 10/28 | `metrics.by_type.STUDENT_ID.tp` / `metrics.by_type.STUDENT_ID.n` |
| DATE_OF_BIRTH 33/38 | `metrics.by_type.DATE_OF_BIRTH.tp` / `metrics.by_type.DATE_OF_BIRTH.n` |
| NAME 151/158 | `metrics.by_type.NAME.tp` / `metrics.by_type.NAME.n` |
| ADDRESS 64/65 | `metrics.by_type.ADDRESS.tp` / `metrics.by_type.ADDRESS.n` |
| 242 of 362 | `metrics.by_type.OUT_OF_SCHEME.fp` of `metrics.overall.fp`. `metrics.shared_11.excluded_predictions` is the same outside-label count. The other 120 false positives are inside the 11 types |
| 9/52, untouched stored negative slice | `metrics.negative.clean_docs` / `metrics.negative.documents`. The sealed corpus was not reopened |

## yrss-holdout-v1 0.834 to 0.871

| Field | Record |
|---|---|
| Value | Baseline F2 0.8335633452939553, F1 0.8156650911546253, P 0.78748370273794, R 0.84593837535014 (tp 604, fp 163, fn 110). Candidate F2 0.8707557502738226, F1 0.8423841059602649, P 0.7989949748743719, R 0.8907563025210085 (tp 636, fp 160, fn 78) |
| Metric | Unrestricted entity precision, recall, F1, and F2. Pre-registered primary endpoint is the paired F2 difference |
| Dataset / split | `yrss-holdout-v1`. 185 documents, 714 entities. Two scored arms |
| Held-out? | Yes for this pair. Closed after the one disclosure. Not a new blind set for later commits |
| Source file | `research/yrss2026/heldout-paired.json` `baseline.metrics.overall` and `candidate.metrics.overall`. Rounded story also in `research/yrss2026/RESULTS.md` |
| Commit SHA | File last changed in `52bd94a7b7dfac5bde8fe8a1cf5c2532051baec7`. Recorded `baseline_commit` `19fe9f0c209c587c7662ee5302edc752f0fd32c8` and `candidate_commit` `ed01027f2e782b6f83d88520c7fe9d2547a84ba1` are absent from this clone. Candidate `candidate_git_dirty` is false |
| Lock hash | Ciphertext `1e5456db9d4df092fa3cbd0b29b599a3a0953441e07c148db50d9fcb23344cae`. Lock file sha256 `db9e0ba05fb220df5af760517464600f9449caceb669883a03b2b3f92bebeb2b`. Driver sha256 stored on the result: `b9e9a780d834ac2f286eeeb2ae0cc47f6e76c7465a60af246a7ebc0a67c787db` |
| Plaintext hash | `eab1d171c0960f1ad75deb33345b6d307bb97f2126c1ec20c9acd2675db9f299` |
| Reproducing command | `python scripts/yrss_paired_eval.py` with `--baseline`, `--candidate`, `--data-dir`, `--key-file`, and `--out`. The exact argv of the stored run is not in the JSON. Not run this session. Plaintext and key stay outside the repo |
| MAY | Cite the paired move 0.834 to 0.871 as three-decimal rounding of the two stored F2 values, with both F1 values, on this closed synthetic set |
| MAY NOT | Cite as a fresh held-out win for any commit after `ed01027`, or as real-document accuracy. Negative controls are unchanged and are not a precision win: 23/52 clean and 36 false positives in both arms; shared-11 view 42/52 clean and 10 false positives in both arms |

Paired F2 difference stored in `paired_f2`: +0.03719240497986731, 95% CI 0.026076086386718322 to 0.04825962883307955, 1,000 shared resamples, seed 0.

## yrss-holdout-v1 per-type counts, same closed pair

Counts are `tp` over `corpus.by_type`. In both arms `tp + fn` equals that gold
count for payment card (`CREDIT_CARD`), `PHONE`, and `STUDENT_ID`. This is the
stored pair, not a new measurement. Citation limits are the same as the
holdout F2 section above.

Source file for every row in this section: `research/yrss2026/heldout-paired.json`.

Recomputing command, from the repo root. It prints the three before/after
counts, then the negative clean-document counts for the baseline arm and the
candidate arm. It reads the stored JSON and does not score a corpus:

`python -c "import json, pathlib; d=json.loads(pathlib.Path('research/yrss2026/heldout-paired.json').read_text(encoding='utf-8')); types=('CREDIT_CARD','PHONE','STUDENT_ID'); b=d['baseline']['metrics']; c=d['candidate']['metrics']; print('\n'.join(t+' '+str(b['by_type'][t]['tp'])+'/'+str(b['corpus']['by_type'][t])+' to '+str(c['by_type'][t]['tp'])+'/'+str(c['corpus']['by_type'][t]) for t in types)); n=b['by_slice']['negative']; m=c['by_slice']['negative']; print(str(n['clean_docs'])+'/'+str(n['documents'])+' and '+str(m['clean_docs'])+'/'+str(m['documents']))"`

| Stored count | JSON path |
|---|---|
| CREDIT_CARD 6/27 to 27/27 | `baseline.metrics.by_type.CREDIT_CARD.tp` / `baseline.metrics.corpus.by_type.CREDIT_CARD` to `candidate.metrics.by_type.CREDIT_CARD.tp` / `candidate.metrics.corpus.by_type.CREDIT_CARD` |
| PHONE 72/95 to 83/95 | `baseline.metrics.by_type.PHONE.tp` / `baseline.metrics.corpus.by_type.PHONE` to `candidate.metrics.by_type.PHONE.tp` / `candidate.metrics.corpus.by_type.PHONE` |
| STUDENT_ID 23/35 to 23/35 in both arms | `baseline.metrics.by_type.STUDENT_ID.tp` / `baseline.metrics.corpus.by_type.STUDENT_ID` to `candidate.metrics.by_type.STUDENT_ID.tp` / `candidate.metrics.corpus.by_type.STUDENT_ID` |
| 23/52 and 23/52 | `baseline.metrics.by_slice.negative.clean_docs` / `baseline.metrics.by_slice.negative.documents` and `candidate.metrics.by_slice.negative.clean_docs` / `candidate.metrics.by_slice.negative.documents` |

## synthetic hard-test F1 0.971 / F2 0.965

| Field | Record |
|---|---|
| Value | AI Guard micro F1 0.970873786407767; F2 0.9652509652509652; P 0.9803921568627451; R 0.9615384615384616; tp 100; fp 2; fn 4 |
| Metric | Micro precision, recall, F1, and F2 over the twelve redaction types. Predictions outside that list count as false positives |
| Dataset / split | `hard-test-v1`, seed `20261103`, 60 documents, `official` true. Comparative synthetic prose (ชุดสังเคราะห์เปรียบเทียบ) |
| Held-out? | No. Not a held-out substitute. The dev half of the same generator was readable while detectors changed. This split is not `blind-v2.enc` |
| Source file | `docs/benchmark/runs/hard-test.json` system `aiguard` `micro`. Rendered with `.3f` in `docs/benchmark/per-entity-results.md`. File sha256 `2f03e327ae97493f5d4d7fb06e7acfbb415d0e8e8601c582ee9159ed4c8f8127` |
| Commit SHA | Measured in `bd18441ca3ed742382b393acc42cc8896ae81c3f`. That blob is on this branch via the cherry-pick. A later re-run on current detectors is a different tree; see WORKLOG |
| Lock hash | `benchmark/data/hard-test.lock.json` sha256 `21eda81a3b19e19531775a20b312a5b94405ccba5dbbe27f603f8c55bd5b36cd`, also stored in `docs/benchmark/runs/environment.json` |
| Plaintext hash | `90749a8891d42b924bbfbbb690f9637ab599867013f27c4a3ed459e8f3aaca11` |
| Reproducing command | `python -m benchmark.blind_v2 --split hard-test --systems aiguard,regex,presidio,pythainlp-ner,wangchanberta-ner --no-utility --json <path>`, from `docs/benchmark/per-entity-results.md`. Re-run 2026-11-05; see below. The sealed corpus is not an input |
| MAY | Cite as a comparative score against regex, Presidio, PyThaiNLP NER, and WangchanBERTa NER on this locked synthetic split, with the layer ablation from the `bd18441` JSON |
| MAY NOT | Cite as held-out, as a replacement for sealed blind-v2 0.799, or as real-document accuracy |

## Reproduction on 2026-11-05

Command log: self-check hashes matched the three lock plaintext hashes above.
Python 3.12.3. Packages matched the recovered environment except
`sentencepiece` 0.2.3 here versus 0.2.2 recorded in
`docs/benchmark/runs/environment.json`. No API key was set. Those commands
did not score `gemma` (`ollama` was not installed for them). A separate
`llm` run on the same freeze is in the gemma section. Field compare is
`docs/benchmark/runs/repro-2026-11-05.json`.

Hard-test and hard-dev AI Guard full micro, and every baseline micro on all
three splits, matched the `bd18441` JSON. Hard-test full micro is still
F1 0.970873786407767 and F2 0.9652509652509652.

Two AI Guard rows moved. The historical JSON stays the `bd18441` measurement.
The current numbers below are the 2026-11-05 re-run on commit
`52bd94a7b7dfac5bde8fe8a1cf5c2532051baec7` and are stored in
`docs/benchmark/runs/repro-2026-11-05.json`. Python `.3f` of the current
freeze F2 is 0.965, the same three-decimal text as hard-test F2
0.9652509652509652. The floats differ.

| Row | Historical `bd18441` JSON | After the `fp` ablation fix |
|---|---|---|
| Freeze full micro | fp 24, F1 0.9446494464944649, F2 0.9638554216867468 | fp 22, F1 0.9481481481481483, F2 0.9653092006033182. Unchanged by the ablation fix |
| Hard-test `fp` removed | F2 0.5147058823529411, tp 49, fp 11, fn 55 | Same as historical. Before the fix this was F2 0.570539419087137, tp 55, fn 49 |
| Hard-dev `fp` removed | F2 0.5327102803738318, tp 57, fp 14, fn 59 | Same micro as historical |
| Freeze `fp` removed | F2 0.549717057396928 (0.5497), tp 136, fp 53, fn 126 | F2 0.5506072874493928 (0.5506), tp 136, fp 51, fn 126. Accepted |

The run JSON and `environment.json` do not record a git SHA. That metadata
field is absent. The blobs were added in
`bd18441ca3ed742382b393acc42cc8896ae81c3f`. That commit does not change
`pii_redactor/` or `benchmark/blind_v2/ablate.py`; both match its parent
`38b235ffb5cede349e51362049a03666b8637dc6`. Re-scoring that parent reproduces
fp 24 and the historical `fp`-removed counts. `main` has one commit between
that parent and the current detector tree:
`52bd94a7b7dfac5bde8fe8a1cf5c2532051baec7`. Later commits on this branch do
not change those files. `benchmark/blind_v2/score.py` matches `bd18441`.

Freeze full micro moved because
`pii_redactor/detectors/tb_detector.py` gained
`_spaceless_run_is_not_a_name`. A space-free Thai run longer than
`_GLUED_NAME_MAX_CHARS` (25) is no longer a NAME. Putting only that new
`tb_detector.py` on the `38b235f` tree moves freeze full fp from 24 to 22.
Disabling only that predicate on the current tree moves it back to 24.
The two dropped false positives, offsets only:

| doc_id | style | historical FP | current |
|---|---|---|---|
| b2r-0000 | gov_form | NAME 0:27 | absent |
| b2r-0078 | negative | NAME 0:42 | absent |

No false-negative set changed on the full freeze. ADDRESS false positives
4 to 0, with `other_false_positives` 12 to 16, is a separate relabel in
`_relabel_numberless_addresses`: the same spans become LOCATION and stay
inside the micro false-positive total. It does not explain fp 24 to 22.
Negative clean documents 7/12 to 8/12 is `b2r-0078` losing its only false
positive.

The `fp`-removed ablation moved, before the fix, because `52bd94a` made
`benchmark/blind_v2/ablate.py` call `recover_structured` and `admit_recovery`
even when `fp` was the disabled layer. The fix skips both calls in that one
case. Detector code is unchanged. With the fix, hard-test and hard-dev
`fp`-removed micro match the `bd18441` JSON, including hard-test F2
0.5147058823529411, tp 49, fn 55. Freeze `fp`-removed F2 is 0.5497
historically and 0.5506 on this tree (exact values 0.549717057396928 and
0.5506072874493928). tp 136 and fn 126 match. fp is 53 historically and 51
now. That gap is the legitimate `52bd94a` spaceless-name gate in
`tb_detector.py`, not `ablate.py`. The gate still runs when `fp` is removed,
and the difference is accepted. Before the fix, recovery had turned these
hard-test false negatives into exact matches:

| doc_id | style | span now matched |
|---|---|---|
| hard-test-0008 | prose-zwsp | PHONE 74:97 |
| hard-test-0011 | prose-zwsp | THAI_ID 18:43 |
| hard-test-0013 | prose-zwsp | BANK_ACCOUNT 40:53 and CREDIT_CARD 16:35 |
| hard-test-0015 | prose-zwsp | VEHICLE_PLATE 12:19 |
| hard-test-0024 | prose-thai_digits | PHONE 63:75 |

The same pattern on hard-dev is PHONE 68:91, PHONE 128:151, THAI_ID 38:63,
BANK_ACCOUNT 55:68, CREDIT_CARD 26:45, VEHICLE_PLATE 21:28, PHONE 58:70,
PHONE 133:145. On the freeze it is THAI_ID 85:110, THAI_ID 83:108, PHONE
81:93, PHONE 85:97. Typed false-positive sets did not change. `recover_structured`
rebuilds a view with format controls and Thai digits removed, then maps
checksum spans back onto the original offsets.

The same JSON's original freeze (`blind-v2-repro`, seed `20261101`, plaintext `ce0b88a3dd2281133f85ddbcdc38a5498f83865754e5bb77510bd12553ce8624`) scores AI Guard micro P 0.9142857142857143, R 0.9770992366412213, F1 0.9446494464944649, F2 0.9638554216867468. That is the labeled synthetic freeze, not the sealed protocol corpus. Hard-dev (seed `20261102`, plaintext `b169fcb72add15dc46cdd62fcb3dac179a4d0b9aa467ad0fb29a40514c76273b`) was the split read during the fix: micro P 0.95, R 0.9827586206896551, F1 0.9661016949152542, F2 0.9760273972602741. Do not cite hard-dev as the test result.

## gemma3:1b seeded samples

Five Ollama seeds, 1 through 5, on harness system `llm`. Each request sends `options.seed` and leaves temperature unset, so the model parameter temperature 1 applies. The prompt was not edited. Ablations were skipped. Python 3.13.18. Ollama 0.40.14. `gemma3:1b` digest `97558784bdc9175075a72655bf360b15da17df6b3b9e5182af9f8c0c8e58ba7c`. Detectors and the prompt match `30b97690883f81897cb7c6bac7fa6c2b85c04c57`. Each mean is the arithmetic mean of the five stored values. The range is the min and max of that same value. Cost 0. No API key was used.

Freeze command, seed 1. Seeds 2, 3, 4, and 5 change only `--llm-seed` and the JSON name:

`python -m benchmark.blind_v2 --split freeze --systems llm --no-ablate --no-utility --no-section26 --llm-seed 1 --json docs/benchmark/runs/gemma-freeze-seed-1.json`

Hard-test command, seed 1:

`python -m benchmark.blind_v2 --split hard-test --systems llm --no-ablate --no-utility --no-section26 --llm-seed 1 --json docs/benchmark/runs/gemma-hard-test-seed-1.json`

Freeze wall seconds 141, 118, 115, 115, 116. Hard-test wall seconds 84, 95, 86, 92, 86. The five hard-test seeds took 443 seconds, so that split is scored here.

Freeze, seed `20261101`, 82 documents, plaintext `ce0b88a3dd2281133f85ddbcdc38a5498f83865754e5bb77510bd12553ce8624`:

seed 1 tp 1 fp 3 fn 261 P 0.25 R 0.003816793893129771 F1 0.007518796992481203 F2 0.004752851711026617

seed 2 tp 2 fp 5 fn 260 P 0.2857142857142857 R 0.007633587786259542 F1 0.014869888475836429 F2 0.009478672985781991

seed 3 tp 2 fp 2 fn 260 P 0.5 R 0.007633587786259542 F1 0.015037593984962405 F2 0.009505703422053233

seed 4 tp 2 fp 4 fn 260 P 0.3333333333333333 R 0.007633587786259542 F1 0.014925373134328356 F2 0.009487666034155599

seed 5 tp 1 fp 1 fn 261 P 0.5 R 0.003816793893129771 F1 0.007575757575757576 F2 0.0047619047619047615

Freeze mean±range: tp 1.6 (min 1, max 2); fp 3.0 (min 1, max 5); fn 260.4 (min 260, max 261); P 0.3738095238095238 (min 0.25, max 0.5); R 0.0061068702290076335 (min 0.003816793893129771, max 0.007633587786259542); F1 0.011985482032673193 (min 0.007518796992481203, max 0.015037593984962405); F2 0.007597359782984441 (min 0.004752851711026617, max 0.009505703422053233).

Python `.3f` of that freeze mean is P 0.374, R 0.006, F1 0.012, F2 0.008. F2 0.009 is an unreproduced historical print. The same 2026-11-01 table prints P 0.400 and R 0.008. Those three numbers are not this seeded mean. An earlier request with no seed remains in `docs/benchmark/runs/gemma-freeze.json` (tp 0, fp 5, fn 262). It is not the seeded mean.

Hard-test, seed `20261103`, 60 documents, plaintext `90749a8891d42b924bbfbbb690f9637ab599867013f27c4a3ed459e8f3aaca11`:

seed 1 tp 0 fp 1 fn 104 P 0.0 R 0.0 F1 0.0 F2 0.0

seed 2 tp 0 fp 0 fn 104 P 0.0 R 0.0 F1 0.0 F2 0.0

seed 3 tp 0 fp 0 fn 104 P 0.0 R 0.0 F1 0.0 F2 0.0

seed 4 tp 0 fp 0 fn 104 P 0.0 R 0.0 F1 0.0 F2 0.0

seed 5 tp 0 fp 0 fn 104 P 0.0 R 0.0 F1 0.0 F2 0.0

Hard-test mean±range: tp 0.0 (min 0, max 0); fp 0.2 (min 0, max 1); fn 104.0 (min 104, max 104); P 0.0 (min 0.0, max 0.0); R 0.0 (min 0.0, max 0.0); F1 0.0 (min 0.0, max 0.0); F2 0.0 (min 0.0, max 0.0).

The 2026-11-01 hard-test print is P 0.000, R 0.000, F2 0.000. `.3f` of every seeded hard-test score is 0.000. Exact counts are the seeded rows. Seed 1 has fp 1.

| Field | Record |
|---|---|
| Held-out? | No. Both splits are synthetic comparison locks. Not the sealed protocol corpus |
| MAY | Cite the seeded mean and the min-max range, with the five rows, as local `gemma3:1b` samples at temperature 1 and cost 0 |
| MAY NOT | Cite F2 0.009 as a verified score. It is an unreproduced historical print. Do not cite either mean as a product headline, as held-out, or as real-document accuracy |

## What is not a headline

| Item | Status |
|---|---|
| `gemma3:1b` on the original synthetic freeze | VERIFIED seeded mean, not a headline. Freeze mean±range: tp 1.6 (min 1, max 2); fp 3.0 (min 1, max 5); fn 260.4 (min 260, max 261); P 0.3738095238095238 (min 0.25, max 0.5); R 0.0061068702290076335 (min 0.003816793893129771, max 0.007633587786259542); F1 0.011985482032673193 (min 0.007518796992481203, max 0.015037593984962405); F2 0.007597359782984441 (min 0.004752851711026617, max 0.009505703422053233). F2 0.009 is an unreproduced historical print |
| `gemma3:1b` on hard-test | VERIFIED seeded mean, not a headline. Hard-test mean±range: tp 0.0 (min 0, max 0); fp 0.2 (min 0, max 1); fn 104.0 (min 104, max 104); P 0.0 (min 0.0, max 0.0); R 0.0 (min 0.0, max 0.0); F1 0.0 (min 0.0, max 0.0); F2 0.0 (min 0.0, max 0.0). The printed P 0.000, R 0.000, F2 0.000 matches `.3f` only |
| Section 26 paraphrase recall | Stored `section26.micro_recall` 0.0 on n=8 in `hard-test.json`. Warn/report, not a redaction F1 |
| Historical paper commit `d93d10b` | Absent from this clone. See METHODS. Not an accuracy figure |
| `research/stt52/` gold-v3 F2 0.801 | A different study. Do not cite it as sealed blind-v2 0.799 |

## Outside this repository

`docs/enterprise/release-scope.md` names a separate tree, `ai-guard-docs/stt52-2026`. That tree is not in this workspace and was not edited. If its poster, slides, or abstract still lead with only gold-v4 F2 0.947 and sealed blind-v2 F2 0.799, point them here and show P, R, F1, and F2. Keep 0.947 on the development set, keep 0.799 on the old sealed freeze, add the closed holdout pair 0.834 to 0.871, and keep hard-test F1 0.971 / F2 0.965 comparative only.
