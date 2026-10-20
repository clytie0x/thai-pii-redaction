# 0001 — Python owns all logic

Date: 2026-08-21 · Status: accepted

## Rule

Every piece of product logic — detection, masking, vault, restoration, policy,
PDPA artifacts, adapters — lives in Python, in this repository. Other
languages are allowed only as the dumbest possible presentation layer: HTML/JS
that takes input, calls a amphrang API, and renders the response. No
detection, masking, or policy logic may ever be duplicated outside Python.

## Why

The predecessor repository (thai-pii-redaction) ran one Python core behind
five storefronts across three languages. The cost was not the storefronts
themselves but proving correctness and package integrity across three
runtimes for a bus-factor-of-one project: its Phase 8 native-broker campaign
(Rust broker, byte-level package attestation, six integration slices) existed
almost entirely to secure cross-language, cross-process seams. With one
language and one process, those seams do not exist: the vault lives in the
memory of the process that uses it, and there is no IPC to authenticate.

A second, subtler failure this rule prevents: a "second brain". The
predecessor's original sin was detection logic that existed twice with
different behavior. A JS layer that is forbidden from holding logic cannot
drift from the engine.

## Exceptions and review triggers

- `demo/playground.html` and any AIFT frontend page: presentation only.
- A future browser extension is the one place the rule cannot hold (Chrome
  requires JS). It stays behind its own go/no-go decision; if that day comes,
  this ADR gets revisited as a whole, not silently eroded.
- Accepted trade-offs: bigger desktop binaries than a Rust shell would give
  (if a desktop ever exists, it is pywebview + PyInstaller), and raw-speed
  ceilings that do not matter because the bottleneck is the NER model.
