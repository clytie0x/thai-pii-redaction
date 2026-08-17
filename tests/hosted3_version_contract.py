#!/usr/bin/env python3
"""Stage 7 Hosted version and channel-truth migration contract."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HOSTED_VERSION = "3.0.1"
WEB_SURFACES = (
    "index.html",
    "app.html",
    "downloads.html",
    "privacy.html",
    "help.html",
    "terms.html",
    "developers.html",
)


def main() -> int:
    version = (ROOT / "core/VERSION").read_text("utf-8").strip()
    assert version == HOSTED_VERSION

    web = {
        name: (ROOT / "web" / name).read_text("utf-8") for name in WEB_SURFACES
    }
    joined = "\n".join(web.values())
    assert "Hosted 2.5.0" not in joined
    assert "Hosted candidate" not in joined
    assert "local candidate" not in joined.lower()
    for required in (
        "Hosted 3.0.1",
        "Desktop 3.0.0",
        "Extension 3.0.0 Manual",
        "Standard access",
        "Priority Invite",
        "40 exact same-origin locations",
        "HTTP contract version 2",
    ):
        assert required in joined, required

    readme = (ROOT / "README.md").read_text("utf-8")
    assert "exactly **40 routes**" in readme
    assert "Hosted 3.0.1" in readme
    assert "HTTP contract" in readme
    assert "Desktop 3.0.0" in readme
    assert "Extension" in readme and "3.0.0" in readme

    approval = (ROOT / "core/aift_hosted3/approval.py").read_text("utf-8")
    assert "HTTP_CONTRACT_VERSION = 2" in approval
    public_acceptance = (ROOT / "tests/public_web_acceptance.py").read_text("utf-8")
    assert 'health.get("version") == "3.0.1"' in public_acceptance

    docs = (ROOT / "docs/production-web-redesign.md").read_text("utf-8")
    state = (ROOT / "STATE.md").read_text("utf-8")
    assert "HOSTED3_IMPLEMENTATION_STAGE=stage9_complete" in docs
    assert "Production is Hosted `3.0.0` with exactly 40 public locations" in state

    print(
        "hosted3 version contract ok: Hosted 3.0.1 candidate/40, HTTP contract 2, "
        "Desktop/Extension unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
