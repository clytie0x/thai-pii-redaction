# Methods, results, and limitations

Synthetic data only. No real-document accuracy and no legal-compliance claim.
Headline rows show precision, recall, F1, and F2 from stored fields. Rounded
figures are Python `.3f`. The audit trail is [CLAIM-MAP.md](CLAIM-MAP.md).

## Methods

Four corpora are kept apart.

Gold-v4 is the development set (ชุดพัฒนา). The stored full-system arm is in
`research/yrss2026/baseline.json`. The manifest records commit
`19fe9f0c209c587c7662ee5302edc752f0fd32c8` with a dirty tree. That commit
object is absent here. The file that holds the score was last changed in
`52bd94a7b7dfac5bde8fe8a1cf5c2532051baec7`. Corpus sha256
`01f86b012c438c074b86942e21021cf39b6df54e2bf950cb2301688b1c1b935b`.
There is no gold lock file. The recorded command is
`python -m benchmark.campaign --out <new-dir> --ablations`
(`research/yrss2026/README.md`). It was not re-run for this note.

Sealed blind-v2 is the agent-authored protocol corpus. Reveal 1 is one JSON
line in `benchmark/data/blind-scores.jsonl`, commit
`856db15bbd1451630b22b505be090468002536ff`, ciphertext and plaintext hashes
in `benchmark/data/blind-v2.lock.json`. The entry's own git head
`4cc5eb17aa16f2df7d5e65576cd5ba61f0737540` is absent from this clone.
The historical command is
`python -m benchmark --source blind --blind-version blind-v2`.
It was not run. The ciphertext was not opened, including after the November
detector fixes. The sealed set was not reopened.

yrss-holdout-v1 is a second closed synthetic set, 185 documents and 714
entities, one paired disclosure. Scores are in
`research/yrss2026/heldout-paired.json`. Lock plaintext
`eab1d171c0960f1ad75deb33345b6d307bb97f2126c1ec20c9acd2675db9f299`,
ciphertext `1e5456db9d4df092fa3cbd0b29b599a3a0953441e07c148db50d9fcb23344cae`.
The driver is `python scripts/yrss_paired_eval.py`. The stored JSON does not
include the exact argv. This session did not run it and did not read the
external plaintext.

The synthetic comparison locks are generated, not sealed. `blind-v2-repro`
(seed `20261101`), `hard-dev-v1` (seed `20261102`), and `hard-test-v1`
(seed `20261103`) are checked by hash in
`benchmark/data/blind-v2-repro.lock.json`,
`benchmark/data/hard-dev.lock.json`, and
`benchmark/data/hard-test.lock.json`. Hard-test plaintext
`90749a8891d42b924bbfbbb690f9637ab599867013f27c4a3ed459e8f3aaca11`.
The 2026-11-03 per-entity JSON was measured at
`bd18441ca3ed742382b393acc42cc8896ae81c3f` and recovered onto this branch.
Command, from `docs/benchmark/per-entity-results.md`:

```bash
python -m benchmark.blind_v2 --self-check
python -m benchmark.blind_v2 --self-check --split hard-dev
python -m benchmark.blind_v2 --self-check --split hard-test
python -m benchmark.blind_v2 --systems aiguard,regex,presidio,pythainlp-ner,wangchanberta-ner --no-utility --json docs/benchmark/runs/freeze.json
python -m benchmark.blind_v2 --split hard-dev --systems aiguard,regex,presidio,pythainlp-ner,wangchanberta-ner --no-utility --json docs/benchmark/runs/hard-dev.json
python -m benchmark.blind_v2 --split hard-test --systems aiguard,regex,presidio,pythainlp-ner,wangchanberta-ner --no-utility --json docs/benchmark/runs/hard-test.json
```

Systems on that run: AI Guard (`predict_ablated` with no layer removed; default
thainer CRF), a cue-and-pattern regex baseline, Presidio analyzer 2.2.360,
PyThaiNLP NER 5.4.0, and WangchanBERTa NER. `gemma3:1b` was scored only in the
earlier 2026-11-01 write-up (`docs/benchmark/blind-v2-results.md`), under
local Ollama, at cost 0. This session does not call a hosted model.
`ollama` is not installed here, so gemma was not re-run.

The same commands were run again on 2026-11-05 (Python 3.12.3). Self-checks
matched the lock hashes. Hard-test and hard-dev full micro matched the table
above. Two rows did not. The compare file is
`docs/benchmark/runs/repro-2026-11-05.json`. The historical JSON is unchanged.

The run files do not store a git SHA. That field is absent. The blobs were
added in `bd18441ca3ed742382b393acc42cc8896ae81c3f`, whose detector tree
matches parent `38b235ffb5cede349e51362049a03666b8637dc6`. Re-scoring that
parent reproduces the stored counts. The only later detector commit on
`main` is `52bd94a7b7dfac5bde8fe8a1cf5c2532051baec7`.

Current freeze full micro, and the number to cite for this tree, is fp 22,
F1 0.9481481481481483, F2 0.9653092006033182. The stored F2
0.9638554216867468 is the `38b235f` / `bd18441` measurement. The move is
`_spaceless_run_is_not_a_name` in `pii_redactor/detectors/tb_detector.py`:
space-free runs longer than 25 characters are dropped. It removes NAME 0:27
on `b2r-0000` and NAME 0:42 on `b2r-0078`. Recall is unchanged.

`52bd94a` left `recover_structured` running inside the `fp` ablation. That
was a harness bug, not a detector change. The fix is in
`benchmark/blind_v2/ablate.py`: when `fp` is the disabled layer, neither
`recover_structured` nor `admit_recovery` runs. The full path still calls
both, so `predict_ablated(text, None)` still matches `detect_all`.

After that fix, cite the historical ablation numbers again for hard-test and
hard-dev. Hard-test `fp`-removed micro is F2 0.5147058823529411, tp 49, fp
11, fn 55. Hard-dev is F2 0.5327102803738318, tp 57, fp 14, fn 59. Freeze
`fp`-removed micro is not back to the historical JSON: tp 136 and fn 126
match, fp is 51 rather than 53, and F2 is 0.5506072874493928 rather than
0.549717057396928. Those two false positives are the name-length gate above.
The pre-fix bug score, F2 0.570539419087137 with tp 55 and fn 49, is not the
number to cite.

Layer ablations turn off one assembly step at a time. `fp` removes the format
and checksum detector. `tb` removes the text detector, including its title and
context pass. `address_merge` removes address-span merging. The regex row is
not the `fp` ablation.

## Results

Development set, gold-v4, arm `full`. Not held-out.

| Arm | P | R | F1 | F2 |
|---|---:|---:|---:|---:|
| full | 0.8674033149171271 | 0.9691358024691358 | 0.9154518950437317 | 0.9469240048250904 |

The `.3f` F2 is 0.947. Stored 95% CI 0.9282772820864789 to 0.9639889196675901.

Sealed blind-v2, reveal 1, CRF. True held-out for that old freeze. Not reopened.

| Arm | P | R | F1 | F2 |
|---|---:|---:|---:|---:|
| crf reveal 1 | 0.5775962660443408 | 0.8839285714285714 | 0.6986591390261117 | 0.7991604778818212 |

The `.3f` F2 is 0.799. Stored 95% CI 0.7671418873048201 to 0.8285105086810843.
Negative slice: 9/52 clean, 112 false positives.

yrss-holdout-v1, one paired disclosure, now closed.

| Arm | P | R | F1 | F2 |
|---|---:|---:|---:|---:|
| baseline `19fe9f0` | 0.78748370273794 | 0.84593837535014 | 0.8156650911546253 | 0.8335633452939553 |
| candidate `ed01027` | 0.7989949748743719 | 0.8907563025210085 | 0.8423841059602649 | 0.8707557502738226 |

The `.3f` F2 values are 0.834 and 0.871. Paired F2 difference
+0.03719240497986731, 95% CI 0.026076086386718322 to 0.04825962883307955.

Synthetic hard-test, comparative only, from `docs/benchmark/runs/hard-test.json`.
Not a held-out substitute.

| System | P | R | F1 | F2 |
|---|---:|---:|---:|---:|
| aiguard | 0.9803921568627451 | 0.9615384615384616 | 0.970873786407767 | 0.9652509652509652 |
| regex | 1.0 | 0.25961538461538464 | 0.4122137404580153 | 0.3047404063205417 |
| presidio | 0.6071428571428571 | 0.49038461538461536 | 0.5425531914893617 | 0.51 |
| pythainlp-ner | 0.4444444444444444 | 0.23076923076923078 | 0.30379746835443033 | 0.25531914893617025 |
| wangchanberta-ner | 0.27631578947368424 | 0.40384615384615385 | 0.32812500000000006 | 0.36971830985915494 |

Printed `.3f` for AI Guard is P 0.980, R 0.962, F1 0.971, F2 0.965.
Per-type rows and the original freeze are in
`docs/benchmark/per-entity-results.md`.

Hard-test layer ablation, removed minus full. Exact micro fields from the
same JSON. A negative delta means the removed layer had been helping.

| Layer removed | P | R | F1 | F2 | delta R | delta F2 |
|---|---:|---:|---:|---:|---:|---:|
| none (full) | 0.9803921568627451 | 0.9615384615384616 | 0.970873786407767 | 0.9652509652509652 |  |  |
| fp | 0.8166666666666667 | 0.47115384615384615 | 0.5975609756097561 | 0.5147058823529411 | -0.4903846153846154 | -0.4505450828980241 |
| tb | 1.0 | 0.6346153846153846 | 0.7764705882352941 | 0.6846473029045642 | -0.326923076923077 | -0.280603662346401 |
| address_merge | 0.7575757575757576 | 0.9615384615384616 | 0.8474576271186441 | 0.9124087591240876 | 0.0 | -0.05284220612687762 |

That `fp` row is the historical `bd18441` JSON, and the ablation fix makes
the current hard-test micro match it again. `fn`,
`record_names`, `facility_filter`, and `student_relabel` have delta 0
on this split in that JSON. On the labeled freeze in `freeze.json`, removing
`fp` moves micro F2 by -0.41413836428981876 and removing `tb` moves it by
-0.19338993212013356. Removing `address_merge` moves freeze micro F2 by
-0.05411839254673256.

Section 26 keyword micro recall on the hard-test paraphrases is 0.0 for n=8
(`section26.micro_recall`). The same scan on the labeled freeze is 1.0 for
n=11, where the phrases contain the keywords. Those labels are warn/report.
They are not redaction true positives.

The 2026-11-01 local `gemma3:1b` row on the labeled freeze prints P 0.400,
R 0.008, F2 0.009. Exact F1 is UNVERIFIED. On the hard-test table in that
same file the printed LLM P, R, and F2 are 0.000. No API key was used.

## Limitations

The gold and holdout sets are synthetic, and the hard-test set is produced by
this repository's generator. Generator bias remains. A high hard-test F1 does
not transfer to the sealed corpus: the sealed reveal is F2 0.799 with
precision 0.578, and it was not reopened after the November fixes.

PDPA Section 26 paraphrase detection on the hard-test keyword scan is 0
(n=8). The semantic model was not installed for that run. The product treats
Section 26 as warn/report, not as an automatic redaction block.

The LLM baseline is weak on the committed 2026-11-01 table, and it is absent
from the recovered 2026-11-03 JSON. This session does not invent a gemma
score. A larger local model was not loaded.

The sealed blind-v2 plaintext was not decrypted. Later synthetic locks are a
different artifact (`benchmark/data/blind-v2-repro.lock.json` records
`sealed_corpus_untouched`).

The historical STT52 system commit `d93d10b17be6783d5c684cb47f25d4156ed6fb4b`
is absent from this clone. `research/stt52/README.md` records that fact and
points corpus loading at `61cde3ba1322597411957d3332d742c04d0c16eb`. The
2026-11-03 per-entity worklog reported `test_frozen_paper_gold_can_be_loaded_from_git`
failing because `d93d10b` was missing. This tree's loader no longer asks for
that commit. The pass or fail of `tests/test_human_agreement.py` on this
branch is the pytest count in WORKLOG, not the old count.

Gold and holdout measurement commits are absent, and the gold manifest is
dirty. Those scores stay file-backed. They are not re-certified on current
`main`.

`docs/enterprise/release-scope.md` points YRSS materials at a separate
`ai-guard-docs/stt52-2026` tree. That tree was not in this workspace and was
not edited. If it still tells the story with only 0.947 and 0.799, it needs
the same four-way split as the claim map.
