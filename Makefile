# One word per chore; every target body matches CONTRIBUTING.md and CI exactly.
# Windows: GNU make (choco install make) runs these under Git Bash's sh.

PY ?= python

.PHONY: install sync lint test bench serve api-test lock

# pip path — range-resolved, same as what a library consumer gets.
# --group needs pip >= 25.1.
install:
	$(PY) -m pip install -e ".[server,mcp]" --group dev
	pre-commit install

# uv path — reproducible dev env pinned by uv.lock (dev group installs by default).
sync:
	uv sync --extra server --extra mcp
	uv run pre-commit install

lint:
	ruff check .
	ruff format --check .

test:
	$(PY) -m pytest -q

bench:
	$(PY) -m benchmark --source gold

serve:
	$(PY) -m amphrang.cli serve --no-browser

# Needs `make serve` (or `amphrang serve`) running in another terminal.
api-test:
	cd bruno && bru run --env local

# Re-pin uv.lock after editing dependencies in pyproject.toml (CI fails when stale).
lock:
	uv lock
