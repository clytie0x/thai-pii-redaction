# amphrang

*amphrang* (อำพราง, pronounced *ahm-prahng* [ʔam.pʰraːŋ], Thai for "to
conceal, to camouflage") — Thai PII detection and anonymization for Python:
mask personal data before it reaches an external AI, restore it locally.

```
pip install amphrang
```

```python
import amphrang

text = "ผมชื่อสมชาย ใจดี เบอร์ 081-234-5678 บัตรประชาชน 1-2345-67890-12-3"

# Detect: spans index into your text
for entity in amphrang.detect(text):
    print(entity.data_type, entity.span)

# Mask -> send to an LLM -> restore
masked = amphrang.anonymize(text, mode="surrogate")
reply = call_your_llm(masked.text)  # only masked text leaves the process
restored = amphrang.restore(reply, masked.mapping)

# Multi-turn: the mapping never leaves the Session object
with amphrang.Session(mode="token") as session:
    turn1 = session.anonymize(text)
    answer = call_your_llm(turn1.text)
    print(session.restore(answer).text)

# PDPA risk analysis (no raw values in the result)
amphrang.analyze(text)
```

## What it detects

Structured Thai identifiers with checksum validation (national ID mod-11,
phone, bank account, credit card, passport, and more) plus names, addresses,
dates, and organizations via Thai NER (PyThaiNLP thainer-CRF, offline) with
context-cue recall boosters. Detection quality is measured against a
hand-authored, twice-adjudicated gold corpus (in `benchmark/`), including a
negative (no-PII) slice so the false-positive rate is a reported number, not
a guess.

## Measured accuracy

Default engine (thainer-CRF, offline) on the open gold corpus, run 2026-08-25
(`python -m benchmark --source gold`, 648 gold entities):

| entity | n | recall | precision |
|---|---|---|---|
| THAI_ID | 51 | 1.000 | 1.000 |
| CREDIT_CARD | 24 | 1.000 | 1.000 |
| DATE_OF_BIRTH | 45 | 1.000 | 1.000 |
| EMAIL | 47 | 1.000 | 1.000 |
| BANK_ACCOUNT | 35 | 1.000 | 0.972 |
| PASSPORT | 25 | 1.000 | 0.962 |
| ADDRESS | 58 | 1.000 | 0.935 |
| NAME | 199 | 0.990 | 0.995 |
| PHONE | 81 | 0.988 | 1.000 |
| VEHICLE_PLATE | 26 | 0.962 | 1.000 |
| STUDENT_ID | 57 | 0.719 | 1.000 |
| **overall** | **648** | **0.969** | **0.867** |

Overall F2 0.947 (95% CI 0.928–0.964). Precision counts every flagged span
that is not a gold entity, including spans outside the labeling scheme — the
recall-first design accepts that trade. The weakest type is honest too:
STUDENT_ID recall is 0.719, mostly free-form student-number shapes. On the
negative (no-PII) slice, 31 of 45 documents come through with zero false
positives.

The gold corpus is open and the detectors are tuned against it, so it is an
upper bound. The held-out **blind corpus** (encrypted in-repo, 185 documents,
479 entities, scored under an audited reveal budget — see
`docs/decisions/2026-07-28-blind-set-protocol.md`) puts the default engine at
**recall 0.960, precision 0.713, F2 0.898**, and the opt-in fine-tuned engine
at recall 0.983, F2 0.916. Those figures are quoted from the hash-chained
score log (`benchmark/data/blind-scores.jsonl`, reveals 5–6 of 6) — no new
reveal was spent publishing them.

## Design promises

- **Fail closed.** If a masked result would still carry residual PII
  (structured, text-based, or a bare 6+ digit run), `anonymize` raises
  `amphrang.LeakBlockedError` instead of returning a partial mask.
- **Local only.** Detection and masking run in-process. The library makes no
  network calls and keeps no state on disk.
- **The mapping is yours to guard.** `anonymize` returns the
  pseudonym→original mapping to you; keeping it out of logs and storage is
  your responsibility. Prefer `Session` when it can stay in process memory.
- **Honest labels.** Recall is preferred over precision, but a business date
  is labeled `DATE`, not a fake birthday, and an invoice number is not a
  passport.

## CLI

```
amphrang report document.txt
```

Prints a value-free PII risk report (entity counts by type plus a risk level)
for a text file.

## Run the local API server

```
pip install "amphrang[server]"
amphrang serve
```

One process, loopback only; opens the API docs at `http://127.0.0.1:8000/docs`.
(`--no-browser`, `--port` available; a non-loopback bind requires an explicit
`--allow-remote` **and** `AMPHRANG_API_KEY`, so the data plane is never
silently open to a network.)

For a host instead of a laptop, the repository's `Dockerfile` packages the
same server; it refuses to start without `AMPHRANG_API_KEY` (the data plane is
never silently open):

```
docker build -t amphrang . && docker run --rm -p 8000:8000 -e AMPHRANG_API_KEY=change-me amphrang
```

## MCP server (for AI agents)

`pip install amphrang[mcp]` adds `amphrang-mcp` — the same guard as a Model
Context Protocol toolset an agent can call: `detect_pii`, `sanitize`,
`reidentify`, `pdpa_analyze`, `guard_prompt`, `close_session`. Run it over
stdio for a local agent (text never leaves the machine, no auth needed) or
`--transport http` for a shared endpoint. `sanitize` returns masked text plus
an opaque `session_handle`; the pseudonym→original mapping stays in the
server's memory and is never part of a tool result — a returned mapping would
land in the very model context the guard exists to protect (see
`docs/decisions/0003-mcp-no-plaintext-mapping.md`).

The HTTP transport is fail-closed: it refuses to start without
`AMPHRANG_MCP_KEYS="caller_id:key[,caller_id:key...]"` — one key per caller,
checked with a constant-time comparison. There is no "unauthenticated for
now" mode; a shared endpoint with no key would hand the PII guard to
anything that can reach the port.

```
AMPHRANG_MCP_KEYS="agent-a:key-a,agent-b:key-b" amphrang-mcp --transport http --port 8300
```

## Extras

| Extra | Adds |
|---|---|
| `amphrang[server]` | Local FastAPI HTTP server (`amphrang.server.server`) |
| `amphrang[mcp]` | `amphrang-mcp` Model Context Protocol server |
| `amphrang[ml]` | WangchanBERTa/union NER engines + semantic Section-26 detector |

## Stability

Only the `amphrang` module surface follows semver — `detect`, `detect_batch`,
`anonymize`, `anonymize_batch`, `restore`, `analyze`, `Session`, `Entity`,
`LeakBlockedError`, `SessionExpiredError`, and the result dataclasses. `amphrang.engine.*`
(detection/masking core) and `amphrang.server.*` (local HTTP server) are
internal; import them at your own risk.

## Provenance

Extracted from [thai-pii-redaction](https://github.com/Teerapat-Vatpitak/thai-pii-redaction)
(AI Guard 3.0.0), keeping the detection engine and benchmark corpus; the
browser-extension/desktop/native-broker storefronts stayed behind, and the
inherited PDF-redaction and PDPA document-generator surfaces were removed
when the project refocused on guarding LLM traffic (see
`docs/decisions/2026-08-25-production-enterprise-direction.md`). Apache-2.0.
