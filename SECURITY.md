# Security policy

Amprang exists to keep Thai personal data out of places it should not go. A
bug that lets personal data through is a security bug, not a quality bug,
and is handled as one.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: open the **Security** tab of
this repository and click **Report a vulnerability**. The report stays
private between you and the maintainer until a fix is released.

Please do not open a public issue for anything that could expose personal
data. If you are unsure whether something qualifies, report it privately
first.

Include, where you can:

- the amprang version (`python -c "import amprang; print(amprang.__version__)"`)
- the entry point involved (facade, CLI, `amprang serve`, `amprang-mcp`)
- a minimal input that reproduces it, with real personal data replaced by
  synthetic values

You should hear back within 7 days. Fixes ship as a patch release with a
CHANGELOG entry; credit is given unless you ask otherwise.

## What counts

In scope — please report:

- masked output from `anonymize`, `Session`, the CLI, or an MCP/HTTP tool
  that still carries a detectable personal-data value without raising
  `LeakBlockedError`
- the pseudonym→original mapping reaching anywhere it should not: an MCP tool
  result, a server log, a response body, disk
- `restore`/`reidentify` producing original values from a session or handle
  the caller should not hold
- authentication or binding bypass in `amprang serve` or
  `amprang-mcp --transport http` (loopback-only default, `--allow-remote`
  gating, `AMPRANG_MCP_KEYS`)
- anything that makes the library contact the network, read, or write
  outside what the call asked for

Out of scope — open a regular issue instead:

- a specific name, address, or identifier the detector misses
  (recall improvements are welcome, but they are not vulnerabilities unless
  the fail-closed guard was also bypassed)
- false positives
- issues in optional third-party engines (PaddleOCR, WangchanBERTa) that do
  not change amprang's own guarantees

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | yes |

Only the latest minor release receives security fixes while the project is
pre-1.0.

## Design notes that bound the threat model

- Detection and masking run in-process and make no network calls.
- `anonymize` fails closed: residual structured, text-based, or bare 6+ digit
  PII in the masked result raises instead of returning a partial mask.
- MCP tools never return the mapping (see
  `docs/decisions/0003-mcp-no-plaintext-mapping.md`).
- The caller owns the mapping returned by the Python facade; keeping it out of
  logs and storage is the caller's responsibility.
