# amprang

Thai PII detection, anonymization, and PDF redaction for Python — mask
personal data before it reaches an external AI, restore it locally.

```
pip install amprang
```

```python
import amprang

text = "ผมชื่อสมชาย ใจดี เบอร์ 081-234-5678 บัตรประชาชน 1-2345-67890-12-3"

# Detect: spans index into your text
for entity in amprang.detect(text):
    print(entity.data_type, entity.span)

# Mask -> send to an LLM -> restore
masked = amprang.anonymize(text, mode="surrogate")
reply = call_your_llm(masked.text)  # only masked text leaves the process
restored = amprang.restore(reply, masked.mapping)

# Multi-turn: the mapping never leaves the Session object
with amprang.Session(mode="token") as session:
    turn1 = session.anonymize(text)
    answer = call_your_llm(turn1.text)
    print(session.restore(answer).text)

# PDPA risk analysis (no raw values in the result)
amprang.analyze(text)

# Permanent PDF blackout (flattened; scanned PDFs need `pip install amprang[ocr]`)
amprang.redact_pdf("input.pdf", "redacted.pdf")
```

## What it detects

Structured Thai identifiers with checksum validation (national ID mod-11,
phone, bank account, credit card, passport, and more) plus names, addresses,
dates, and organizations via Thai NER (PyThaiNLP thainer-CRF, offline) with
context-cue recall boosters. Detection quality is measured against a
hand-authored, twice-adjudicated gold corpus (in `benchmark/`), including a
negative (no-PII) slice so the false-positive rate is a reported number, not
a guess.

## Design promises

- **Fail closed.** If a masked result would still carry residual PII
  (structured, text-based, or a bare 6+ digit run), `anonymize` raises
  `amprang.LeakBlockedError` instead of returning a partial mask.
- **Local only.** Detection and masking run in-process. The library makes no
  network calls and keeps no state on disk.
- **The mapping is yours to guard.** `anonymize` returns the
  pseudonym→original mapping to you; keeping it out of logs and storage is
  your responsibility. Prefer `Session` when it can stay in process memory.
- **Honest labels.** Recall is preferred over precision, but a business date
  is labeled `DATE`, not a fake birthday, and an invoice number is not a
  passport.

## PDPA tooling (CLI)

The `amprang` console command carries the PDPA artifact generators —
processing receipt (มาตรา 39), breach assessment (มาตรา 37(4)), and DSAR
locate (มาตรา 30) — each producing a value-free JSON + Thai PDF pair:

```
amprang report document.txt
amprang receipt issue document.txt -o receipt.json --pdf receipt.pdf
amprang breach assess ./leaked_files -o breach.json --pdf breach.pdf
amprang dsar locate ./documents --subject-file subject.txt -o dsar.json
```

## Try it in a browser

```
pip install "amprang[server]"
amprang serve
```

One process, loopback only, opens the playground at `http://127.0.0.1:8000/demo`
— paste Thai text, see detection highlights and masked output live. Nothing
leaves the machine. (`--no-browser`, `--no-demo`, `--port` available; a
non-loopback bind requires an explicit `--allow-remote` **and**
`AMPRANG_API_KEY`, so the data plane is never silently open to a network.)

For a host instead of a laptop, the repository's `Dockerfile` packages the
same server; it refuses to start without `AMPRANG_API_KEY` (the data plane is
never silently open):

```
docker build -t amprang . && docker run --rm -p 8000:8000 -e AMPRANG_API_KEY=change-me amprang
```

## MCP server (for AI agents)

`pip install amprang[mcp]` adds `amprang-mcp` — the same guard as a Model
Context Protocol toolset an agent can call: `detect_pii`, `sanitize`,
`reidentify`, `pdpa_analyze`, `guard_prompt`, `close_session`. Run it over
stdio for a local agent (text never leaves the machine, no auth needed) or
`--transport http` for a shared endpoint. `sanitize` returns masked text plus
an opaque `session_handle`; the pseudonym→original mapping stays in the
server's memory and is never part of a tool result — a returned mapping would
land in the very model context the guard exists to protect (see
`docs/decisions/0003-mcp-no-plaintext-mapping.md`).

The HTTP transport is fail-closed: it refuses to start without
`AMPRANG_MCP_KEYS="caller_id:key[,caller_id:key...]"` — one key per caller,
checked with a constant-time comparison. There is no "unauthenticated for
now" mode; a shared endpoint with no key would hand the PII guard to
anything that can reach the port.

```
AMPRANG_MCP_KEYS="agent-a:key-a,agent-b:key-b" amprang-mcp --transport http --port 8300
```

## Extras

| Extra | Adds |
|---|---|
| `amprang[server]` | Local FastAPI HTTP server (`amprang.server.server`) |
| `amprang[mcp]` | `amprang-mcp` Model Context Protocol server |
| `amprang[ml]` | WangchanBERTa/union NER engines + semantic Section-26 detector |
| `amprang[ocr]` | PaddleOCR pipeline for scanned/hybrid PDFs |

## Stability

Only the `amprang` module surface follows semver — `detect`, `anonymize`,
`restore`, `analyze`, `redact_pdf`, `Session`, `Entity`, `LeakBlockedError`,
`SessionExpiredError`, and the result dataclasses. `amprang.engine.*`
(detection/masking core) and `amprang.server.*` (local HTTP server) are
internal; import them at your own risk.

## Provenance

Extracted from [thai-pii-redaction](https://github.com/Teerapat-Vatpitak/thai-pii-redaction)
(AI Guard 3.0.0), keeping the detection engine, benchmark corpus, and PDPA
tooling; the browser-extension/desktop/native-broker storefronts stayed
behind. Apache-2.0.
