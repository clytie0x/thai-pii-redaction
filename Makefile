# One word per chore; every target body matches CONTRIBUTING.md and CI exactly.
# Windows: GNU make (choco install make) runs these under Git Bash's sh.

PY ?= python

.PHONY: install install-locked lint test bench serve api-test lock

install:
	$(PY) -m pip install -e ".[server,mcp]" ruff pytest pre-commit
	pre-commit install

# Same extras, but every transitive dependency pinned by requirements.lock.
install-locked:
	$(PY) -m pip install -r requirements.lock -e ".[server,mcp]" ruff pytest pre-commit
	pre-commit install

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

# Re-pin requirements.lock after editing any requirements*.txt (needs uv).
lock:
	uv pip compile requirements.txt requirements-web.txt requirements-mcp.txt --universal --python-version 3.11 -o requirements.lock
