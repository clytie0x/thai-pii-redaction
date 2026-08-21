# 0002 — Product surface: one pip package

Date: 2026-08-21 · Status: accepted

## Decision

The product is the `aiguard` pip package, and only it:

- **SDK** — the `aiguard` facade (the only semver-stable import surface)
- **CLI** — the `aiguard` command (sanitize/report + PDPA receipt, breach,
  DSAR artifacts)
- **MCP adapter** — `aiguard-mcp` (local stdio; HTTP for a shared endpoint)
- **`[server]` extra** — the local FastAPI app, also the body of the AI for
  Thai deployment

Not products: the web playground (a living demo of the package — dumb
presentation per ADR 0001, deletable without loss), and the archived
predecessor's Desktop/Extension/Office storefronts.

Not built until a real user signal exists: desktop app, browser extension,
Office add-in. Each revival requires its own decision record.

## Why

The predecessor shipped five storefronts before its first user. Post-mortem
agents advocating four different directions (SDK, consumer, B2B, research)
independently converged on the same keep-list — engine, benchmark corpus,
PDPA tooling — and the same drop-list — every storefront and the broker.
Surface is added when demand pulls it, never ahead of it.

## AI for Thai obligation

The platform deployment is an obligation-closing deliverable, not a product
track: the sibling port pins a released `aiguard[server]` version behind its
nginx shell, text-only routes (the PDF route stays closed — measured at 221 s
and the 6 GiB ceiling for a single OCR page), then freezes to security fixes
and version bumps.
