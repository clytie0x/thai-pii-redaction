"""Static contract for the Stage 6 local Hosted caller surface."""

from __future__ import annotations

import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    nginx = (ROOT / "api" / "default.conf.template").read_text(encoding="utf-8")
    frontend = "\n".join(
        (ROOT / "web" / name).read_text(encoding="utf-8")
        for name in ("index.html", "app.html", "hosted3-app.js", "developers.html")
    )
    core = (ROOT / "core" / "app" / "server.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    state = (ROOT / "STATE.md").read_text(encoding="utf-8")
    deploy_day = (ROOT / "docs" / "DEPLOY-DAY.md").read_text(encoding="utf-8")

    exact_routes = re.findall(r"^\s*location = (/[^ {]+) \{", nginx, re.MULTILINE)
    hosted3 = json.loads((ROOT / "tests/fixtures/hosted3/contract.json").read_text(encoding="utf-8"))
    require(len(exact_routes) == 40, f"expected 40 local Stage 5 routes, got {len(exact_routes)}")
    require(len(exact_routes) == len(set(exact_routes)), "duplicate public route")
    for path in ("/redact-pdf", "/v1/redact-pdf"):
        require(path not in exact_routes, f"public PDF route exposed: {path}")
    for path in ("/analyze-report", "/v1/analyze-report"):
        require(path in exact_routes, f"PDPA report route missing: {path}")
    require('location / {\n    return 404;' in nginx, "fixed proxy 404 fallback missing")

    for marker in ("redact-pdf", 'id="pdfFile"', 'id="pdfPick"', "after_png_b64"):
        require(marker not in frontend, f"frontend PDF execution marker remains: {marker}")
    require('@app.post("/api/redact-pdf"' in core, "internal PDF code was removed")

    current_docs = "\n".join((readme, state, deploy_day))
    for claim in ("production-ready", "correctness", "resource acceptance"):
        require(claim in current_docs, f"current PDF quarantine documentation missing: {claim}")
    require("40 routes" in current_docs, "Hosted 3.0.0 route count is not documented")
    require("Production is Hosted `3.0.1` with exactly 40 public locations" in state, "deployed Hosted 3.0/40 truth is not explicit")
    for path in ("/auth/guest", "/protection-preview", "/document-preview", "/provider-queue/join", "/provider-queue/claim", "/provider-queue/cancel"):
        require(f'"/api{path}"' in frontend, f"Stage 6 caller path missing {path}")
    require('localStorage' not in frontend and 'sessionStorage' not in frontend, "Stage 6 browser persistence leaked")
    require('href="/developers"' in frontend and 'same-origin application contract' in frontend, "developer reference is incomplete")
    print("public surface contract ok: deployed Hosted 3.0.0 uses the approved 40-route caller")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
