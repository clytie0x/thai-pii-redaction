"""Byte parity for the exact local Stage 3 Core and parser images."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_IMAGE = os.environ.get("AIGUARD_CORE_IMAGE", "aiguard-stage3-core:local")
PARSER_IMAGE = os.environ.get(
    "AIGUARD_PARSER_IMAGE", "aiguard-pdf-parser-stage3:local"
)
RUN_IMAGES = os.environ.get("AIGUARD_STAGE3_IMAGE_PARITY") == "1"


def _run(arguments: list[str]):
    return subprocess.run(arguments, check=True, capture_output=True, text=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _image_hashes(image: str, roots: list[str]) -> dict[str, str]:
    script = """
import hashlib,json
from pathlib import Path
roots=%s
files=[]
for raw in roots:
    path=Path('/app')/raw
    if path.is_file():
        files.append(path)
    elif path.is_dir():
        files.extend(item for item in path.rglob('*') if item.is_file() and '__pycache__' not in item.parts)
print(json.dumps({str(path.relative_to('/app')).replace('\\\\','/'):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(files)},separators=(',',':'),sort_keys=True))
""" % repr(roots)
    output = _run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            image,
            "python",
            "-c",
            script,
        ]
    )
    return json.loads(output.stdout)


@unittest.skipUnless(RUN_IMAGES, "Stage 3 final-image parity only")
class ImageParityTests(unittest.TestCase):
    def test_core_hosted_overlay_matches_every_current_source_byte(self):
        expected = {
            "aift_auth.py": _sha256(ROOT / "core" / "aift_auth.py"),
            "aift_gateway.py": _sha256(ROOT / "core" / "aift_gateway.py"),
        }
        expected.update(
            {
                str(path.relative_to(ROOT / "core")).replace("\\", "/"): _sha256(path)
                for path in sorted((ROOT / "core" / "aift_hosted3").glob("*.py"))
            }
        )
        self.assertEqual(
            _image_hashes(
                CORE_IMAGE,
                ["aift_auth.py", "aift_gateway.py", "aift_hosted3"],
            ),
            expected,
        )

    def test_parser_runtime_is_an_exact_minimal_source_allowlist(self):
        expected_paths = (
            "THIRD_PARTY_NOTICES.md",
            "healthcheck.py",
            "licenses/OFL-Anuphan.txt",
            "parser_engine.py",
            "protocol.py",
            "requirements.lock",
            "scenarios/hr-resume-pdf-structured-v1.pdf",
            "server.py",
            "worker.py",
        )
        expected = {
            path: _sha256(ROOT / "pdf-parser" / Path(path)) for path in expected_paths
        }
        self.assertEqual(
            _image_hashes(
                PARSER_IMAGE,
                [
                    "THIRD_PARTY_NOTICES.md",
                    "healthcheck.py",
                    "licenses",
                    "parser_engine.py",
                    "protocol.py",
                    "requirements.lock",
                    "scenarios",
                    "server.py",
                    "worker.py",
                ],
            ),
            expected,
        )

    def test_image_revision_labels_are_explicit(self):
        for image in (CORE_IMAGE, PARSER_IMAGE):
            inspected = json.loads(_run(["docker", "image", "inspect", image]).stdout)[0]
            revision = (inspected.get("Config", {}).get("Labels") or {}).get(
                "org.opencontainers.image.revision"
            )
            self.assertIsInstance(revision, str)
            self.assertNotIn(revision, {"", "local-working-tree"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
