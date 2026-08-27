# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/). Only the `amphrang` facade is
covered by the semver contract — changes under `amphrang.engine.*` and
`amphrang.server.*` appear here when they change observable behaviour, not
when they change shape.

## [Unreleased]

### Added

- `amphrang[proxy]` / `amphrang-proxy`: OpenAI-compatible sanitizing reverse
  proxy (`POST /v1/chat/completions`, streaming included). Outbound messages
  are masked in token mode with one consistent token per value across the
  history; replies are restored, streamed replies through a bounded-holdback
  restorer that survives tokens split across chunk boundaries. Fail closed:
  leak-blocked requests answer 422 and are never forwarded; tools, tool
  calls, and non-text content parts are rejected (v1 scope). Loopback only;
  upstream configured via `AMPHRANG_PROXY_UPSTREAM` /
  `AMPHRANG_PROXY_UPSTREAM_KEY`.
- API stability policy (README "Stability"): 0.x patch releases never change
  the public surface, breaking surface changes only in minor releases with a
  CHANGELOG entry, `DeprecationWarning` at least one minor release before any
  removal. The surface is pinned in `docs/api-surface.txt` and
  `scripts/check_release.py` now fails CI when it and `amphrang.__all__`
  disagree.
- `amphrang.detect_batch` and `amphrang.anonymize_batch`: many texts in one
  call, item-for-item identical to the single-call functions, with an opt-in
  `workers=N` process-parallel path (each worker loads the NER model once).
  `anonymize_batch` fails closed as a unit; the raised `LeakBlockedError`
  carries the offending position in `batch_index`.
- Five new structured PII types: `JURISTIC_ID` (13-digit `0`-leading Thai
  juristic registration number, mod-11 checksum-verified — the same
  algorithm as `THAI_ID` — disambiguated from `THAI_ID` by a juristic cue in
  a 30-char window), `DRIVER_LICENSE` (8 digits, cue-gated only), `LINE_ID`
  (LINE messaging handle, cue-gated only), `GPS_COORD` (decimal `lat, lon`
  pair, no cue needed), `HOUSE_REG_ID` (11-digit house-registration code,
  cue-gated only). All five score 1.000 recall / 1.000 precision on the new
  gold `business_ids` slice. See
  `docs/decisions/2026-08-26-new-datatype-specs.md` for the checksum
  research and sources.
- Three wave-1 structured PII types, bringing the total to 19: `IP_ADDRESS`
  (IPv4 dotted quad, cue-boosted 0.9 / catch-all 0.8, version strings
  suppressed; IPv6 full or `::`-compressed, 0.9, no cue), `MAC_ADDRESS` (six
  hex pairs, `:` or `-` separator, 0.9, no cue), `LAND_DEED_ID` (1-6 digit
  deed number, cue inside the pattern, 0.9 — wins the digits from an
  overlapping `ADDRESS` claim while the ตำบล/อำเภอ/จังหวัด chain behind it
  still masks as `ADDRESS`). All three score 1.000 recall / 1.000 precision
  on the new gold `digital_ids` slice. Frozen shapes and sources:
  `docs/decisions/2026-08-26-wave1-format-specs.md`.
- Two quasi-identifiers in `analyze()`'s re-identification-risk scan:
  `nationality` and `body_metrics`.
- Person-linked ม.26 sensitive-span masking, default on with no facade
  knob: ten categories (`RACE_ETHNICITY`, `POLITICAL_OPINION`, `RELIGION`,
  `SEXUAL_BEHAVIOR`, `CRIMINAL_RECORD`, `HEALTH`, `DISABILITY`, `GENETIC`,
  `LABOR_UNION`, `BIOMETRIC`) become maskable `detect()`/`anonymize()` spans
  only when their segment is linked to a natural person (name entity,
  title+name, or a first-person pronoun) — an impersonal mention
  ("วันสำคัญทางศาสนา") is left untouched. Both `surrogate` and `token`
  anonymize modes route a sensitive span as a token, never a fabricated
  surrogate value, since a realistic-looking surrogate would assert a false
  personal claim. Wired into the leak guard
  (`SAFE_OUTBOUND_LEAK_TYPES`/`_sensitive_leaks`) and the output
  validator's char-coverage rule. Design record:
  `docs/decisions/2026-08-27-section26-span-masking.md`.
- `docs/pdpa-coverage.md` (`pdpa-profile-v1`): the public PDPA
  statute-coverage profile (mask-always, quasi-identifier, ม.26, out-of-scope,
  and not-personal-data levels), generated from and kept consistent with
  `docs/decisions/2026-08-26-pdpa-data-ontology.md`. `scripts/check_release.py`
  gains a `check_profile()` gate that fails CI if a `data_type` the profile
  references drifts from `TOKEN_LABEL` in `amphrang/engine/anonymizer/
  token_generator.py`, in either direction.
- `docs/annotation-guidelines.md` sensitive-span addendum (rules S1-S7):
  person linkage is document-level; a category word naming a document,
  section, field, purpose, or entitlement is not a value; the value is a
  condition/finding/belief/membership/conviction or a course of care, never
  the administration around it; span-boundary rulings; anchor evidence is
  not annotated; a CRF-swallowed span is annotated anyway and reported as
  covered-not-leaked; pre-existing documents are adjudicated, not
  grandfathered.
- Gold `digital_ids` slice (gold-v6, 24 docs) and `sensitive` slice
  (gold-v7, 28 docs), bringing the gold corpus to 332 documents / 1031
  entities.

### Fixed

- Long documents no longer fail closed spuriously. `anonymize` on documents
  past ~20k characters raised `LeakBlockedError` because the outbound
  rescan's segment check re-ran the NER on isolated between-token segments,
  where the CRF tags bare field labels ("เลขบัตรประชาชน") as person names —
  confirming its own hallucination. The segment check now applies the same
  non-person gate the retag path already uses; real names in a segment are
  still flagged. Found by the performance harness on the L/XL classes.
- `STUDENT_ID` gold recall 0.719 -> 0.860 (precision held at 1.000) and
  `NAME` gold recall 0.969 -> 0.991: evidence-first cue/window widenings
  (new education-context introducers and compounds, a wider student-context
  window, a `มอบหมายให้` role cue, a driver-licence-label lookahead on the
  name-before-passport pass) recovered 16 STUDENT_ID and 7 NAME misses with
  zero collateral flips elsewhere in gold.
- `ADDRESS` gold precision 0.921 -> 0.967 and `NAME` precision 0.974 ->
  0.987: space-free field-label segments ("เลขผู้เสียภาษี", document-title
  lines) no longer tag as `NAME`, and post-merge `ADDRESS` spans with
  neither a digit nor an admin-area word relabel to `LOCATION`. The
  negative slice is unchanged at 15 false positives / 31 of 45 clean docs
  by adjudication — the remaining predictions are deliberate
  quasi-identifier detections (issue/deadline/effective dates and one
  organization name) that the annotation guidelines forbid carving out.
- A trailing sentence-final period no longer kills an `IP_ADDRESS` (IPv4 or
  IPv6) or `MAC_ADDRESS` match ("...IP 192.168.1.44." now still detects):
  the boundary now blocks a fifth dotted IPv4 group without also blocking a
  bare sentence-final period. `LAND_DEED_ID` no longer silently drops
  single-digit deed numbers to the dedupe step's 2-character floor (deed
  numbering starts at 1).
- `น.ส.`+digit lines (the หนังสือรับรองการทำประโยชน์ series, e.g. น.ส.3ก,
  น.ส.4จ) are no longer read as a person title: `_name_hygiene` was
  splitting the line at the first digit run and minting a spurious `NAME`
  span from the abbreviation. `NAME` gold precision 0.980 → 0.988.
- The `nationality` QI's lookbehind narrowed from a blanket "no preceding
  Thai character" (which had silently stopped matching ordinary phrasing
  like "มีสัญชาติไทย") to targeted lookbehinds on the compound prefixes
  (ข้าม/ต่าง/นานา/หลาย) that should actually exclude a QI hit.
- Three evidence-backed `sensitive_span` fixes from gold-v7 authoring: the
  12-character specificity window is now clamped at the segment boundary,
  so a role word one character past a newline can no longer promote a
  tier-2 anchor across it; when a `GENETIC`/`BIOMETRIC` pattern matches
  wholly inside a `HEALTH` cue's claimed span, the cue now yields its label
  instead of masking genetic data as `HEALTH` (`GENETIC` gold recall
  0.667 → 1.000); a CRF `NAME` false positive over legal boilerplate can no
  longer anchor a sensitive span in a person-free document (`HEALTH` gold
  precision 0.588 → 0.667). The last fix carries an accepted, recorded
  cost: a real bare full name (no title, no pronoun) sitting in a
  register-vocabulary segment also loses its linked sensitive span, pinned
  by
  `test_f4_accepted_cost_a_bare_real_name_in_a_register_segment_no_longer_anchors`.

### Changed

- Packaging: dependencies are declared statically in `pyproject.toml`
  (`[project.dependencies]`, `[project.optional-dependencies]`, PEP 735
  `[dependency-groups]` for dev tools) instead of dynamically from
  `requirements*.txt`, which are gone. Reproducible dev installs come from
  the committed `uv.lock` (`uv sync --extra server --extra mcp`); published
  metadata is unchanged in spirit — same floors, same extras. The build
  backend stays setuptools and `VERSION` still drives the version.
- Benchmark corpus append rule: appending to `_CORE_TEMPLATES` can shift
  every downstream synthetic draw for the rest of the corpus whenever the
  template count crosses a `random.randrange` bit-length boundary, not only
  when a template is inserted mid-list. Determinism (same seed → same
  corpus) and `hard_case`-slice stability are the real byte-identity gates
  for a corpus change, not an "append-only, so untouched" assumption.
- The leak-guard field-label regression test
  (`tests/test_leak_guard.py::test_long_document_with_record_name_lines_is_not_leak_blocked`,
  a corpus-line-count pin) no longer exercised what its docstring claimed —
  mutation-testing showed it stayed green even with the field-label gate it
  was meant to pin fully disabled. Replaced with
  `test_field_label_gate_covers_primary_rescan_and_segment_rescan`, a
  detector-independent unit test that calls `scan_outbound_leaks` directly
  with the two field-label hallucinations replayed via monkeypatch.

### Removed

Refocused on guarding LLM traffic (decision record
`docs/decisions/2026-08-25-production-enterprise-direction.md`); the
inherited surfaces that served other jobs were removed. **Breaking** for the
facade: `redact_pdf` and `RedactionResult` are gone from `amphrang`.

- PDF redaction: `amphrang.redact_pdf`, `POST /api/redact-pdf`, the ingest
  chain (`file_detector`, `text_extractor`, `ocr_processor`,
  `quality_validator`), and the `amphrang[ocr]` extra.
- PDPA document generators and their CLI verbs: `receipt issue`/`verify`
  (มาตรา 39), `breach assess` (มาตรา 37(4)), `dsar locate` (มาตรา 30), the
  Thai PDF renderers, the bundled IBM Plex Sans Thai Looped font, and
  `POST /api/analyze-report`. `analyze()` (value-free risk analysis) stays.
- The legacy 8-step `run_pipeline` orchestrator and the `amphrang sanitize`
  CLI verb (`anonymize`/`restore`/`Session` are the supported path).
- The `tner` remote NER engine (`AMPHRANG_NER_ENGINE=tner`): a detector that
  ships text to an external API contradicts the local-only promise. Offline
  engines (`thainer` default, `wangchanberta`, `union`, `finetuned`) are
  unchanged.
- Core dependencies dropped with the PDF stack: pypdfium2, reportlab,
  uharfbuzz, Pillow, pdfplumber. `pip install amphrang` now pulls only
  pythainlp, python-crfsuite, regex, and httpx.

## [0.1.0] — 2026-08-23

First release of amphrang, extracted from
[thai-pii-redaction](https://github.com/Teerapat-Vatpitak/thai-pii-redaction)
(AI Guard 3.0.0). The detection engine, the gold benchmark corpus, and the
PDPA tooling carried over; the browser-extension, desktop, and native-broker
storefronts did not. History before the extraction (1.x–3.0.0) lives in
[that repository's CHANGELOG](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/blob/main/CHANGELOG.md)
and is not repeated here.

### Added

- Public facade: `detect`, `anonymize`, `restore`, `analyze`, `redact_pdf`,
  `Session`, plus `Entity`, the result dataclasses, `LeakBlockedError`, and
  `SessionExpiredError`. This module is the only semver-stable surface.
- `amphrang` CLI: `sanitize`, `report`, and the PDPA artifact generators
  `receipt issue` (มาตรา 39), `breach assess` (มาตรา 37(4)), `dsar locate`
  (มาตรา 30), each producing a value-free JSON + Thai PDF pair.
- `amphrang serve`: one-command local API server, loopback-only by default; a
  non-loopback bind requires both `--allow-remote` and `AMPHRANG_API_KEY`.
- `amphrang-mcp` (`amphrang[mcp]`): Model Context Protocol server exposing
  `detect_pii`, `sanitize`, `reidentify`, `pdpa_analyze`, `guard_prompt`,
  `close_session`. `sanitize` returns an opaque session handle; the mapping
  never enters a tool result (ADR 0003). The HTTP transport refuses to start
  without per-caller `AMPHRANG_MCP_KEYS`.
- PDPA Section 26 coverage completed with `GENETIC` and `BIOMETRIC` sensitive
  categories.
- Bundled IBM Plex Sans Thai Looped font (OFL-1.1, license shipped alongside)
  so Thai renders in generated PDFs on machines without a Thai-capable TTF.
- Decision records: Python owns all logic (0001), the product is one pip
  package (0002), MCP tools never return the mapping (0003).
- Release pipeline: `release.yml` gates a `v*` tag on VERSION/CHANGELOG
  agreement (`scripts/check_release.py`), builds and smoke-tests the wheel,
  publishes to PyPI via trusted publishing, and creates the GitHub Release.
  CI runs on Ubuntu and Windows plus a core-only (no extras) install.
- `Dockerfile` for `amphrang[server]`: non-root, model pre-warmed at build,
  refuses to start without `AMPHRANG_API_KEY`; CI builds and smoke-tests it.
- `docs/standards-mapping.md` (ISO/IEC 20889 and มรด. 6:2566 correspondence),
  `scripts/blind_freeze.py` carried over from
  the predecessor; `.pre-commit-config.yaml`, `.editorconfig`.

### Changed

- Distribution and import name is `amphrang`; the predecessor's `app`,
  `pii_redactor`, and `ai_guard` packages now live under `amphrang.server`,
  `amphrang.engine`, and `amphrang.cli`.

### Fixed

- PDPA artifacts (receipt, breach assessment, DSAR) record the installed
  package version instead of `"unknown"` when amphrang is a pip-installed
  wheel; one shared `amphrang.engine.environment` replaces three private
  copies.
- `anonymize` and `Session.anonymize` normalize Thai digits before detection
  so a Thai-numeral phone number is masked instead of passing through
  silently (independent review, 2026-08-21).
- `restore` reports `generated_pii_count` and `foreign_replacement_count`.
- `detect` returns `original_text` as the exact slice of the caller's text.

### Removed

- Native-broker and private-backend code paths; the vault lives in the
  process that uses it.
- `demo_cli.py`; use the `amphrang` CLI or `amphrang serve` instead.
- `amphrang.server.worker` queue worker (unused by the server; see
  docs/reviews/2026-08-21-facade-review.md).
- PyInstaller frozen-executable lookups (`sys._MEIPASS`, `%APPDATA%` log
  dir) left over from the predecessor's desktop build.

[Unreleased]: https://github.com/Teerapat-Vatpitak/amphrang/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Teerapat-Vatpitak/amphrang/releases/tag/v0.1.0
