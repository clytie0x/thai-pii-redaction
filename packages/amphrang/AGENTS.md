# Repository Guidelines

## Project Structure & Module Organization

`amphrang/` is the Python package: `engine/` holds detection and masking,
`server/` HTTP services, and `proxy/` the OpenAI-compatible proxy. The top-level
facade is the only semver-stable import surface; changes to exports in
`amphrang/__init__.py` must also update `CHANGELOG.md` and `docs/api-surface.txt`.
Use `tests/` for tests and fixtures, `benchmark/` for scoring and corpora, `bruno/`
for API scenarios, `scripts/` for utilities, `docs/decisions/` for architecture,
and `examples/prompts/` for synthetic samples.

## Build, Test, and Development Commands

Python 3.11+ is required. Set up the reproducible environment with:

```sh
uv sync --extra server --extra mcp
uv run pre-commit install
```

Run tools through `uv run`; the `Makefile` provides equivalent targets after
activating `.venv`.

- `uv run ruff check .` and `uv run ruff format --check .` run lint checks.
- `uv run python -m pytest -q` runs the test suite.
- `uv run python -m benchmark --source gold` scores the gold corpus.
- `uv run python -m amphrang.cli serve --no-browser` starts the local API.
- `cd bruno && bru run --env local` tests a running server; install Bruno CLI with
  `npm install -g @usebruno/cli` first.
- `uv lock` refreshes `uv.lock` after dependency edits; CI requires it to be current.

## Coding Style & Naming Conventions

Follow `.editorconfig`: spaces, UTF-8, LF, four-space default indentation, and two
spaces in JSON, YAML, TOML, and Markdown. Ruff targets Python 3.11, uses a 100-column
limit and double quotes, and sorts imports. Use `snake_case` for modules/functions,
`PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants.

## Testing Guidelines

Pytest discovers `tests/test_*.py`, `Test*`, and `test_*`. There is no coverage
threshold; bug fixes require regression tests. Use synthetic personal data only in
tests, fixtures, benchmarks, and PRs.
Detection changes must preserve gold-corpus recall and include before/after benchmark
results. API changes must update `bruno/` when the contract changes.

## Commit & Pull Request Guidelines

Recent history uses imperative Conventional-style subjects such as `fix:`, `feat:`,
`docs:`, `bench:`, and `docs+ci:`. Keep each commit and PR to one logical change and
sign commits with `git commit -s`. PRs must explain what and why, link the issue or
decision record, and include exact verification output. Report possible PII exposure
privately as directed by `SECURITY.md`, never in a public issue.

## Architecture Constraints

Read `docs/decisions/` before structural changes: Python owns all product logic, the
pip package is the product, MCP tools never expose mappings, and masking must fail
closed rather than return partially sanitized text.
