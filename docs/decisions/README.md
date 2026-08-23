# Decision records

Why the code looks the way it does. Each record is dated by when the decision
was made and is not continuously maintained; a newer record wins over an older
one where they overlap.

## amprang (current)

| Record | What it decides |
|---|---|
| [0001 Python owns all logic](0001-python-owns-all-logic.md) | Every piece of product logic lives in Python in this repository; HTML/JS is presentation only. |
| [0002 Product surface](0002-product-surface.md) | The product is the `amprang` pip package (SDK, CLI, MCP adapter, `[server]` extra) and nothing else until a real user signal exists. |
| [0003 MCP tools never return the mapping](0003-mcp-no-plaintext-mapping.md) | `sanitize` returns an opaque session handle; the pseudonym→original mapping never enters a tool result. |

## Inherited from thai-pii-redaction

These were written in the predecessor repository before the extraction and
are kept because the engine, benchmark, and PDPA tooling they describe carried
over unchanged. File paths inside them use the predecessor's layout:
`pii_redactor/` is now `amprang/engine/`, `app/` is `amprang/server/`,
`ai_guard.py` is `amprang/cli.py`. Anything about Desktop, Extension, Office,
native broker, or store distribution is out of scope here (see 0002).

| Record | What it decides |
|---|---|
| [2026-07-13 recall benchmark design](2026-07-13-thai-pii-recall-benchmark-design.md) | Recall-first scoring, the synthetic/gold corpus split, and the benchmark as the product's own detection ensemble. |
| [2026-07-15 NER engine strategy](2026-07-15-ner-engine-strategy-decision.md) | thainer CRF stays the default engine; WangchanBERTa/union are opt-in extras. |
| [2026-07-19 audit v2 findings](2026-07-19-audit-v2-findings.md) | Findings and dispositions from the second independent audit of the engine and API. |
| [2026-07-25 gold set and LLM baseline](2026-07-25-gold-set-and-llm-baseline.md) | Hand-authored gold corpus as the evaluation standard; hosted LLMs as a comparison baseline, never a detector. |
| [2026-07-28 blind set protocol](2026-07-28-blind-set-protocol.md) | Encrypted blind corpus, hash-chained score log, reveal rules. Referenced by `benchmark/blind.py`. |
| [2026-07-28 gold adjudication](2026-07-28-gold-adjudication.md) | Two-pass adjudication that produced gold-v3. |
| [2026-07-28 engine comparison](2026-07-28-engine-comparison-after-campaigns.md) | CRF vs WangchanBERTa vs union after the recall campaigns. |
| [2026-07-28 fine-tuned NER results](2026-07-28-finetuned-ner-results.md) | Results of the fine-tuned engine experiment (`finetuned_engine.py`). |
| [2026-07-28 ONNX runtime evaluation](2026-07-28-onnx-runtime-evaluation.md) | Why ONNX export was evaluated and not adopted. |
| [2026-07-28 Tokenmind detector and AIFT port](2026-07-28-tokenmind-detector-and-aift-port.md) | Tokenmind as an LLM provider for the benchmark and the AI for Thai deployment shape. |
| [2026-07-29 processing receipt (มาตรา 39)](2026-07-29-processing-receipt.md) | A per-run receipt authenticated by re-running the input, not a cumulative RoPA. |
| [2026-08-01 breach assessment (มาตรา 37(4))](2026-08-01-breach-assessment.md) | Value-free breach assessment over a set of leaked files. |
| [2026-08-01 DSAR helper (มาตรา 30)](2026-08-01-dsar-helper.md) | DSAR locate over a corpus with a subject file; shared scan helpers in `scan_common.py`. |
| [2026-08-04 weakness closure campaign](2026-08-04-weakness-closure-campaign.md) | The recall-leak closure work the hard-case tests pin. |
| [2026-08-05 HTTP contract v2](2026-08-05-http-contract-v2.md) | Strict v2 response projections; mapping-oriented fields leave the wire. |
| [2026-08-06 session-namespaced token identity](2026-08-06-session-namespaced-token-identity.md) | Token mode's vault-generation tag plus per-token nonce. |
