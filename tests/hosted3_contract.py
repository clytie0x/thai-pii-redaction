"""Hosted 3 release-candidate route and implementation-stage fence."""

from __future__ import annotations

import json
import hashlib
import re
import runpy
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "hosted3" / "contract.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_release_owned_version_survives_sync(sync_module: dict[str, object]) -> None:
    with tempfile.TemporaryDirectory(prefix="aiguard-version-sync-") as temporary:
        root = Path(temporary)
        upstream = root / "upstream"
        target_core = root / "core"
        target_manifest = root / "sync" / "PORT_MANIFEST.json"
        shutil.copytree(ROOT / "core", upstream)
        (upstream / "VERSION").write_text("2.5.0\n", encoding="utf-8")
        subprocess.run(["git", "init", "--quiet"], cwd=upstream, check=True)
        subprocess.run(["git", "config", "core.autocrlf", "false"], cwd=upstream, check=True)
        subprocess.run(["git", "config", "user.email", "sync@example.invalid"], cwd=upstream, check=True)
        subprocess.run(["git", "config", "user.name", "Hosted sync contract"], cwd=upstream, check=True)
        subprocess.run(["git", "add", "."], cwd=upstream, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=upstream, check=True)

        target_core.mkdir()
        (target_core / "VERSION").write_text("3.0.1\n", encoding="utf-8")
        target_manifest.parent.mkdir()
        do_sync = sync_module["do_sync"]
        do_sync.__globals__["CORE"] = target_core
        do_sync.__globals__["MANIFEST"] = target_manifest
        do_sync(upstream)

        require(
            (target_core / "VERSION").read_text("utf-8").strip() == "3.0.1",
            "vendored sync overwrote Hosted VERSION",
        )
        manifest = json.loads(target_manifest.read_text("utf-8"))
        require(
            manifest["files"]["VERSION"]
            == hashlib.sha256(b"2.5.0\n").hexdigest(),
            "upstream VERSION provenance disappeared from manifest",
        )


def main() -> int:
    contract = json.loads(FIXTURE.read_text(encoding="utf-8"))
    nginx = (ROOT / "api" / "default.conf.template").read_text(encoding="utf-8")
    version = (ROOT / "core" / "VERSION").read_text(encoding="utf-8").strip()
    security_lock = (ROOT / "core" / "requirements-aift-security.lock").read_text(
        encoding="utf-8"
    )
    redesign = (ROOT / "docs" / "production-web-redesign.md").read_text(
        encoding="utf-8"
    )

    require(contract["schema_revision"] == "hosted3-plan-2026-08-16", "fixture revision drift")
    require(version == contract["current_hosted_version"], "Hosted release VERSION drift")
    require(contract["target_hosted_version"] == "3.0.1", "target version drift")

    existing = contract["existing_canonical_routes"]
    additive = contract["additive_canonical_routes"]
    require(len(existing) == len(set(existing)), "existing canonical route duplicates")
    require(len(additive) == len(set(additive)), "additive canonical route duplicates")
    require(not set(existing).intersection(additive), "existing/additive route overlap")

    exact_routes = re.findall(r"^\s*location = (/[^ {]+) \{", nginx, re.MULTILINE)
    current_expected = existing + [f"/v1{path}" for path in existing]
    planned_routes = additive + [f"/v1{path}" for path in additive]
    target_routes = current_expected + planned_routes
    expected_surface = existing + additive + [f"/v1{path}" for path in existing + additive]
    require(exact_routes == expected_surface, "Stage 5 exact local route surface/order drift")
    require(len(exact_routes) == contract["target_exact_route_count"] == 40, "Stage 5 must expose exactly 40 locations")
    require(
        len(target_routes) == len(set(target_routes)) == contract["target_exact_route_count"],
        "approved 40-route arithmetic drift",
    )

    # Exact locations are the public allowlist. Reject any new prefix/regex
    # matcher, which would otherwise evade exact-route enumeration.
    declarations = re.findall(
        r"^\s*location\s+(?:(=|~\*|~|\^~)\s+)?([^\s{]+)\s*\{",
        nginx,
        re.MULTILINE,
    )
    non_exact = [(modifier, path) for modifier, path in declarations if modifier != "="]
    require(
        all(
            not modifier and (path in {"/", "/internal-health"} or path.startswith("@"))
            for modifier, path in non_exact
        ),
        f"unapproved non-exact Nginx location: {non_exact}",
    )

    sync_module = runpy.run_path(str(ROOT / "sync" / "sync_from_upstream.py"))
    is_port_owned = sync_module["_is_port_owned"]
    require(is_port_owned("aift_hosted3/authority.py"), "Hosted overlay is not port-owned")
    require(is_port_owned("VERSION"), "Hosted VERSION is not release-owned")
    require(not is_port_owned("aift_hosted3x/authority.py"), "overlay prefix is too broad")
    require(not is_port_owned("app/server.py"), "vendored server became port-owned")
    require(not is_port_owned("unreviewed.py"), "arbitrary core extras became port-owned")
    verify_release_owned_version_survives_sync(sync_module)

    require("cryptography==50.0.0" in security_lock, "approved AEAD dependency pin missing")
    require(
        contract["queue"]["claim_grant_sequence"]
        == ["priority", "priority", "priority", "standard"],
        "approved queue weighting drift",
    )
    require(contract["queue"]["provider_slots"] == 2, "provider slot contract drift")
    require(
        sum(
            (
                contract["queue"]["standard_capacity"],
                contract["queue"]["priority_capacity"],
            )
        )
        == contract["queue"]["total_capacity"],
        "queue class capacities do not equal total capacity",
    )
    for ticket_kind, ttl in contract["ticket_ttl_seconds"].items():
        require(ttl >= contract["minimum_review_seconds"][ticket_kind], f"{ticket_kind} TTL")

    require(
        "### Hosted 3.0 approved access and queue contract" in redesign,
        "authoritative Hosted 3.0 contract missing",
    )
    require(
        f"HOSTED3_IMPLEMENTATION_STAGE={contract['implementation_stage']}" in redesign,
        "durable implementation stage marker drift",
    )
    for modality in ("Audio", "TTS", "Vision", "OCR"):
        require(modality in redesign, f"excluded modality not documented: {modality}")

    print(
        "hosted3 contract ok: Hosted 3.0.1 release candidate exposes exactly 40 "
        "approved locations with the reviewed implementation-stage marker"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
