# Contributing

Thanks for looking. This is a small project with a narrow purpose; the rules
below exist to keep it that way.

## Setup

```
git clone https://github.com/Teerapat-Vatpitak/amphrang
cd amphrang
python -m venv .venv
# Windows: .venv\Scripts\activate   macOS/Linux: source .venv/bin/activate
pip install -e ".[server,mcp]" ruff pytest
```

Python 3.11+ is required. The PyThaiNLP NER model downloads on first use.

Then activate the commit hooks (same ruff config as CI, plus line-ending and
merge-conflict checks — see `.pre-commit-config.yaml`):

```
pip install pre-commit
pre-commit install
```

With GNU make installed, `make install` does both steps above in one go, and
`make install-locked` does the same with every transitive dependency pinned by
`requirements.lock` (regenerate it with `make lock` after editing any
`requirements*.txt`; needs [uv](https://docs.astral.sh/uv/)). The other chores
are one word each — `make lint`, `make test`, `make bench`, `make serve`,
`make api-test` — and each target body is exactly the commands documented
below, so make is a convenience, never a requirement.

## Trying the API (Bruno)

`bruno/` is a committed [Bruno](https://www.usebruno.com/) collection covering
the local server's endpoints (health, detect, sanitize → reidentify,
roundtrip, analyze, guard, audit-log), with the `X-Amphrang-Contract-Version`
header and request-chaining already wired. Open the folder in the Bruno app
(collection → Open, pick `bruno/`, environment `local`), or run it headless
with the CLI while `amphrang serve` is running:

```
npm install -g @usebruno/cli
cd bruno && bru run --env local
```

Requests use synthetic personal data only — same rule as tests. The Sanitize
request keeps its session handle in runtime variables, never in the committed
environment file. CI runs this collection against a live server (the
`api-collection` job), so a PR that changes the API must update the
collection with it.

## Before you open a pull request

Run exactly what CI runs:

```
ruff check .
ruff format --check .
python -m pytest -q
```

All three must be clean. If a change touches detection, also run the
benchmark against the gold corpus and paste the before/after numbers in the
PR:

```
python -m benchmark --source gold
```

Recall regressions on the gold corpus are not merged, even when precision
improves. Proposing or relabeling a gold document has its own workflow in
[docs/benchmark-contribution.md](docs/benchmark-contribution.md) and follows
[docs/annotation-guidelines.md](docs/annotation-guidelines.md). A business
date labeled `DATE` instead of being dropped is the honest-label rule in
action; see README "Design promises".

## Rules that are not up for debate in a PR

These come from the decision records in `docs/decisions/`. Read them before
proposing anything structural.

1. **Python owns all logic** (ADR 0001). Detection, masking, vault, policy,
   PDPA artifacts live in Python only. HTML/JS is presentation that calls an
   API and renders the result; it may not duplicate any logic.
2. **The product is the pip package** (ADR 0002). No new storefront
   (desktop, extension, add-in) without its own decision record.
3. **MCP tools never return the mapping** (ADR 0003). `sanitize` returns a
   session handle; the pseudonym→original mapping never enters a tool result
   in any encoding.
4. **Fail closed.** A masked result that still carries residual PII raises.
   Never add a path that returns a partial mask silently.
5. **Only the `amphrang` facade is semver-stable.** `amphrang.engine.*` and
   `amphrang.server.*` are internal and may change without notice. Changing
   anything exported from `amphrang/__init__.py` needs a CHANGELOG entry
   under the right heading.

If a change needs to bend one of these, open an issue first and propose a new
decision record; do not fold the bend into a feature PR.

## Style

- Ruff does formatting and linting; do not hand-format around it.
- Match the surrounding code. Do not refactor adjacent code in the same PR.
- Tests go in `tests/`, named `test_*.py`. A bug fix comes with a test that
  failed before the fix.
- Test inputs use synthetic personal data only. Never commit a real name,
  ID number, phone number, or address, including in fixtures and benchmark
  data.

## Developer Certificate of Origin

By contributing you certify the
[Developer Certificate of Origin 1.1](https://developercertificate.org/): the
contribution is your own work (or you have the right to submit it) and you
agree to it being distributed under the Apache-2.0 license. Sign off each
commit to say so:

```
git commit -s -m "..."
```

This adds a `Signed-off-by:` trailer with your name and email. Pull requests
with unsigned commits will be asked to sign before merge.

## Security issues

Do not open a public issue for anything that could expose personal data.
See [SECURITY.md](SECURITY.md).
