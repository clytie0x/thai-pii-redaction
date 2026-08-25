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

### Fixed

- Long documents no longer fail closed spuriously. `anonymize` on documents
  past ~20k characters raised `LeakBlockedError` because the outbound
  rescan's segment check re-ran the NER on isolated between-token segments,
  where the CRF tags bare field labels ("เลขบัตรประชาชน") as person names —
  confirming its own hallucination. The segment check now applies the same
  non-person gate the retag path already uses; real names in a segment are
  still flagged. Found by the performance harness on the L/XL classes.

### Changed

- Packaging: dependencies are declared statically in `pyproject.toml`
  (`[project.dependencies]`, `[project.optional-dependencies]`, PEP 735
  `[dependency-groups]` for dev tools) instead of dynamically from
  `requirements*.txt`, which are gone. Reproducible dev installs come from
  the committed `uv.lock` (`uv sync --extra server --extra mcp`); published
  metadata is unchanged in spirit — same floors, same extras. The build
  backend stays setuptools and `VERSION` still drives the version.

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
