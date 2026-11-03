# What is still missing for a best-in-Thailand claim

This list is the gap between the 2026-11-01 re-run and a claim that AI Guard
is the strongest Thai PII redactor. The numbers on this page are from
[blind-v2-results.md](blind-v2-results.md). A later per-entity measurement is
in [per-entity-results.md](per-entity-results.md). The sealed protocol corpus was
not opened. Nothing here was fixed by weakening detection.

The original freeze moved from AI Guard micro F2 0.920 to 0.964 because
obscured digits and obscured names are recovered and mapped back onto the
source span. That is a recall gain (0.924 to 0.977). Name precision on that
freeze moved from 0.886 to 0.889. The negative slice did not get cleaner.

## Robustness

Checksummed numbers with a zero-width mark, a Thai digit, an Arabic-Indic
digit, a space between digits, or one OCR lookalike are found on both scored
sets. AI Guard national-ID and phone recall are 1.000 on the original freeze
(35 and 44) and on the hard test split (6 and 6).

What is still open:

- Names. Original-freeze recall is 0.914 (70 gold). Hard-test recall is 0.895
  (38 gold) at precision 1.000. The CRF still misses some people when the
  sentence has no title, including after zero-width marks are removed. The
  cue regex on the labeled freeze still leads on names (recall 0.943) because
  those documents use field labels the hard split does not.
- Outside-scheme predictions. The hard test's four negative documents are
  clean, and the original freeze is still 7 of 12 (5 false positives, 12
  outside-scheme predictions, down from 13). A place or organization the NER
  tags is a product label, and it still counts as a micro false positive in
  this twelve-type score. Dropping `LOCATION` would raise the benchmark
  number and break the detection contract that keeps a real province.
- Address precision on the original freeze is unchanged at 0.789 (4 false
  positives, recall 1.000). The hard split's six addresses were exact.

The NER-only baselines still do not recover checksummed identifiers. Removing
AI Guard's format layer drops hard-test micro F2 from 0.965 to 0.515.

## PDPA Section 26 mapping

The public category names are one list in `pii_redactor/pdpa_categories.py`.
`report.py` compiles its keyword patterns from that list. `leak_guard.py`
accepts the same names and maps the old short aliases
(`ETHNICITY`, `CRIMINAL`, `UNION`) onto them. `sensitive_detector.py` uses
the same set as its prototype keys.

That is a naming fix, not coverage. The keyword scan still recalls every
explicit phrase on the original freeze (1.000, n=11) and none of the eight
hard-test paraphrases (0.000). Those paraphrases were written without the
keywords, on purpose. The semantic detector that might catch some of them
needs `sentence-transformers` and did not run. The spans are still not
redacted. That is the warn/report policy.

## Prompt-only LLM

`gemma3:1b` under Ollama ran on every document of both sets. Cost was zero.
Recall was 0.008 on the original freeze and 0.000 on the hard test split.
The model does not reliably emit a JSON span that occurs in the source. A
larger Typhoon was not loaded: the 4B weights do not fit the memory this
process could see (about 4.8 GiB). A bigger local model is the open question,
not another prompt tuned on the hard test split.

Utility on the original freeze (18 questions, same model) shows redaction
cutting PII-answer accuracy (AI Guard 0.556 raw to 0.111 redacted) and also
cutting some safe-question accuracy (0.556 to 0.333). The hard split has no
question set, so it has no utility number.

## OCR memory

This comparison is text. It does not touch the PDF OCR path.

The current roadmap records the hosted one-page OCR route reaching the 6 GiB
core limit in 221 seconds, so the configured 20-page / 300-second surface is
not deploy-ready. The performance gate does not see that path: its fixture is
a text PDF. A claim that includes scans needs a page that finishes inside the
memory limit, with redaction boxes still on the original coordinates.

## Release and version

Three versions are still in play:

- Source `VERSION` is `0.1.0`, reset on 2026-10-19
  (`docs/decisions/2026-10-19-version-reset.md`).
- `ROADMAP.md` and the 2026-08-14 body of `docs/project-status.md` still
  describe owner-authorized 3.0.0 certification of the archived line. Those
  sentences are historical.
- Hosted production still reports `3.0.2`. This comparison did not redeploy
  anything and did not re-query production.

## What this run could not answer

- Whether a larger local Thai model would beat the format-plus-NER stack.
  `gemma3:1b` did not. No paid call was made.
- Whether the semantic Section 26 model would flag the paraphrases. It was
  not installed.
- The sealed protocol corpus. It stayed closed.
