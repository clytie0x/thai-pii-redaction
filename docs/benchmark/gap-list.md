# What is still missing for a best-in-Thailand claim

This list is the gap between the 2026-11-01 blind-v2 comparison and a claim
that AI Guard is the strongest Thai PII redactor. The numbers are from
[blind-v2-results.md](blind-v2-results.md). The sealed protocol corpus was
not opened. Nothing here was fixed by weakening detection.

## Robustness

On this freeze AI Guard micro F2 is 0.920. The misses that matter are the
adversarial surfaces, not the clean labeled forms:

- Thai national IDs: recall 0.829. Checksum-valid ASCII forms are found.
  Per-character spaces, zero-width characters, Thai digits, Arabic-Indic
  digits, and an OCR letter standing in for a digit still get through.
- Phones: recall 0.864, the same as the regex baseline. The shared misses are
  the non-ASCII and fully spaced numbers.
- Names: recall 0.886, below the cue regex (0.943). Glued OCR names, names
  with a zero-width character, and names with a space between every character
  are the weak shapes. WangchanBERTa NER alone reaches name recall 0.914 but
  precision 0.577, so borrowing its tags without the product's filters would
  not be a gain.
- Negative documents: 7 of 12 stay clean. Five false positives land on text
  that has no gold span, and 13 further predictions are outside the twelve
  redaction types. A best-in-Thailand system has to keep that slice clean
  without giving up the adversarial recall above.

The NER-only baselines show the other half of the gap. PyThaiNLP `thainer`
and WangchanBERTa `thainer-v2` do not recover checksum IDs, bank accounts,
cards, passports, plates, student ids, birth dates, or IBANs. Those types
are a format layer, and removing AI Guard's format layer drops micro F2 from
0.920 to 0.543. The product already has the right split. The open work is the
surfaces the format layer still rejects.

## PDPA Section 26 mapping

Policy is warn/report, not automatic redaction. The keyword scan recalled
every explicit phrase on this freeze (micro recall 1.000, n=11). That is not
mapping coverage:

- The phrases were written to contain the current keywords. A paraphrase
  without those words is unmeasured. The semantic detector that would catch
  some of them needs `sentence-transformers` and did not run.
- The category names are not one list. `pii_redactor/report.py` and
  `sensitive_detector.py` use `RACE_ETHNICITY`, `CRIMINAL_RECORD`,
  `LABOR_UNION`, and `SEXUAL_BEHAVIOR`. `leak_guard.py` and the entity model
  comment use `ETHNICITY`, `CRIMINAL`, and `UNION`, and the outbound allow-list
  has no sexual-behavior label. A warn finding and a leak-guard label for the
  same fact can disagree.
- Because the spans are not redacted, a downstream model still sees the
  sensitive phrase. That is intentional. It is also why keyword recall cannot
  be reported as redaction quality.

## OCR memory

This comparison is text. It does not touch the PDF OCR path.

The current roadmap records the hosted one-page OCR route reaching the 6 GiB
core limit in 221 seconds, so the configured 20-page / 300-second surface is
not deploy-ready. The performance gate does not see that path: its fixture is
a text PDF. A best-in-Thailand claim that includes scans needs a page that
finishes inside the memory limit, with redaction boxes still on the original
coordinates. No OCR deskew belongs in that work unless the coordinates move
with it.

## Release and version

Three versions are in play, and they are not the same artifact:

- Source `VERSION` is `0.1.0`, reset on 2026-10-19
  (`docs/decisions/2026-10-19-version-reset.md`).
- `ROADMAP.md` and the 2026-08-14 body of `docs/project-status.md` still
  describe owner-authorized 3.0.0 certification of the archived line. Those
  sentences are historical. They are not the version of this tree.
- Hosted production still reports `3.0.2`. `apps/hosted/STATE.md` says the
  source restart was not deployed, and public health was still 3.0.2 at the
  last recorded production check. This comparison did not redeploy anything
  and did not re-query production.

Until the source version, the docs a reader opens first, and the running
service name the same release, a "best" claim does not have a version to
attach to.

## What this run could not answer

- Prompt-only LLM redaction, and the raw-versus-redacted question set, were
  skipped. Nothing local was listening: no Ollama model, no llama.cpp model
  file, no OpenRouter free-tier key. A paid model was not required and was
  not called. The question set is 18 questions, twice per system (raw and
  redacted), plus one redaction prompt per document. That is a few hundred
  short prompts if someone later chooses a hosted free tier. It is not a
  reason to spend money now.
- The regex baseline shares this generator's field labels. Its micro F2 of
  0.938 is a ceiling on clean forms, not a field result.
- Presidio's Thai row is only as strong as the pattern recognizers in the
  harness. It is not an official Thai Presidio model.
- Layers that scored a zero delta here can still matter on gold and on the
  sealed blind corpus. This list does not retire them.
