# 0003 — MCP tools never return the mapping

Date: 2026-08-21 · Status: accepted

## Decision

No MCP tool result may contain the pseudonym→original mapping, in any
encoding. `sanitize` returns masked text plus an opaque `session_handle` to a
server-side in-memory vault (TTL-bounded, droppable via `close_session`);
`reidentify` accepts the handle. The plaintext-mapping API exists only in the
in-process Python facade (`thaiguard.anonymize().mapping`), where the holder is
code, not a model context.

## Why

An MCP tool result always enters the calling model's context. Returning the
mapping would place every raw PII value into the very LLM conversation the
product exists to protect — and agent frameworks routinely log tool results
into observability stacks, so the mapping would also land in third-party logs
nobody intended to hold personal data. An earlier design draft proposed
"return the mapping, the agent keeps it"; an independent review (see
docs/reviews/2026-08-21-facade-review.md) rejected it on exactly these
grounds, adding that prompt injection in any document the agent reads could
then order a restore-and-exfiltrate with no guard left in the loop.

## Residual risk, stated honestly

`reidentify` output does contain real personal data and does enter the
model's context. That is irreducible when the agent's job is to show the
user a restored answer, and it is no *new* exposure when the raw text entered
the conversation from the user in the first place. The tool description
instructs the model to present restored output to the end user only and never
forward it to another service; that is a prompt-level mitigation, not a
guarantee. Flows where raw text never touches the model (file pipelines)
should use the Python facade or CLI instead.

The handle is authority to restore for whoever holds it within the TTL.
Hosted deployments must therefore pair handles with per-caller
authentication; the local stdio server has a single caller by construction.
