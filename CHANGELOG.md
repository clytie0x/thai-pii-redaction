# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/). Only the `amprang` facade is
covered by the semver contract — changes under `amprang.engine.*` and
`amprang.server.*` appear here when they change observable behaviour, not
when they change shape.

## [Unreleased]

## [0.1.0] — unreleased

First release of amprang, extracted from
[thai-pii-redaction](https://github.com/Teerapat-Vatpitak/thai-pii-redaction)
(AI Guard 3.0.0). The detection engine, the gold benchmark corpus, and the
PDPA tooling carried over; the browser-extension, desktop, and native-broker
storefronts did not.

### Added

- Public facade: `detect`, `anonymize`, `restore`, `analyze`, `redact_pdf`,
  `Session`, plus `Entity`, the result dataclasses, `LeakBlockedError`, and
  `SessionExpiredError`. This module is the only semver-stable surface.
- `amprang` CLI: `sanitize`, `report`, and the PDPA artifact generators
  `receipt issue` (มาตรา 39), `breach assess` (มาตรา 37(4)), `dsar locate`
  (มาตรา 30), each producing a value-free JSON + Thai PDF pair.
- `amprang serve`: one-command local playground, loopback-only by default; a
  non-loopback bind requires both `--allow-remote` and `AMPRANG_API_KEY`.
- `amprang-mcp` (`amprang[mcp]`): Model Context Protocol server exposing
  `detect_pii`, `sanitize`, `reidentify`, `pdpa_analyze`, `guard_prompt`,
  `close_session`. `sanitize` returns an opaque session handle; the mapping
  never enters a tool result (ADR 0003). The HTTP transport refuses to start
  without per-caller `AMPRANG_MCP_KEYS`.
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

### Changed

- Distribution and import name is `amprang`; the predecessor's `app`,
  `pii_redactor`, and `ai_guard` packages now live under `amprang.server`,
  `amprang.engine`, and `amprang.cli`.

### Fixed

- PDPA artifacts (receipt, breach assessment, DSAR) record the installed
  package version instead of `"unknown"` when amprang is a pip-installed
  wheel; one shared `amprang.engine.environment` replaces three private
  copies.
- `anonymize` and `Session.anonymize` normalize Thai digits before detection
  so a Thai-numeral phone number is masked instead of passing through
  silently (independent review, 2026-08-21).
- `restore` reports `generated_pii_count` and `foreign_replacement_count`.
- `detect` returns `original_text` as the exact slice of the caller's text.

### Removed

- Native-broker and private-backend code paths; the vault lives in the
  process that uses it.
- `demo_cli.py`; use the `amprang` CLI or `amprang serve` instead.
- PyInstaller frozen-executable lookups (`sys._MEIPASS`, `%APPDATA%` log
  dir) left over from the predecessor's desktop build.

[Unreleased]: https://github.com/Teerapat-Vatpitak/amprang/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Teerapat-Vatpitak/amprang/releases/tag/v0.1.0
