"""Cross-image proof that the default PDF scenario reaches a clean protection gate."""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PARSER_IMAGE = os.environ.get(
    "AIGUARD_PARSER_IMAGE", "aiguard-pdf-parser-stage3:local"
)
CORE_IMAGE = os.environ.get("AIGUARD_CORE_IMAGE", "aiguard-stage2-contract:local")
RUN_IMAGES = os.environ.get("AIGUARD_SCENARIO_GATE") == "1"
RUN_LIVE_DEFAULT = os.environ.get("AIGUARD_PATHUMMA_DEFAULT_DOCUMENT") == "1"


def _run(arguments: list[str], *, input_text: str | None = None):
    return subprocess.run(
        arguments,
        input=input_text,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _parsed_default_scenario():
    profile = str((ROOT / "pdf-parser" / "seccomp.json").resolve())
    parsed = _run(
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
            "--security-opt",
            f"seccomp={profile}",
            "--pids-limit",
            "32",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--tmpfs",
            "/work:rw,noexec,nosuid,nodev,size=64m,uid=1000,gid=1000,mode=0700",
            PARSER_IMAGE,
            "python",
            "-c",
            (
                "import json;from pathlib import Path;from parser_engine import parse_pdf;"
                "value=parse_pdf(Path('/app/scenarios/hr-resume-pdf-structured-v1.pdf'));"
                "print(json.dumps(value,ensure_ascii=False,separators=(',',':'),"
                "sort_keys=True))"
            ),
        ]
    )
    return parsed, json.loads(parsed.stdout)


@unittest.skipUnless(RUN_IMAGES, "cross-image scenario gate only")
class ScenarioGateTests(unittest.TestCase):
    def test_real_parser_output_passes_real_protector_without_residual_block(self):
        parsed, parser_result = _parsed_default_scenario()
        self.assertEqual(parser_result["segment_count"], 31)
        self.assertEqual(parser_result["omitted_visual_page_numbers"], [1])

        protected = _run(
            [
                "docker",
                "run",
                "--rm",
                "--interactive",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "64",
                "--memory",
                "768m",
                "--cpus",
                "1",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=64m",
                CORE_IMAGE,
                "python",
                "-c",
                "import hashlib,json,sys;"
                "from aift_hosted3.protection import ProtectionService;"
                "value=json.load(sys.stdin);"
                "result=ProtectionService().protect_document("
                "tuple(row['text'] for row in value['segments']),"
                "salt='53'*16,generation_seed=b'G'*32);"
                "print(json.dumps({'detected_entity_count':result.detected_entity_count,"
                "'detected_entity_types':sorted(result.entity_type_counts),"
                "'protected_sha256':hashlib.sha256(result.protected_text.encode('utf-8')).hexdigest()},"
                "separators=(',',':'),sort_keys=True));result.mapping.clear()",
            ],
            input_text=json.dumps(parser_result, ensure_ascii=False),
        )
        gate = json.loads(protected.stdout)
        self.assertEqual(gate["detected_entity_count"], 12)
        self.assertEqual(
            gate["detected_entity_types"],
            [
                "ADDRESS",
                "DATE",
                "DATE_OF_BIRTH",
                "EMAIL",
                "LOCATION",
                "NAME",
                "ORGANIZATION",
                "PHONE",
                "POSTAL_CODE",
            ],
        )
        self.assertEqual(
            gate["protected_sha256"],
            "4e402d73c75b8699706690b7b4cb4a1c2e789d97c32daae1de4eb0999ab5d03f",
        )
        self.assertNotIn("kanthida.s@example.com", protected.stdout)
        self.assertNotIn("081-234-5678", protected.stdout)


@unittest.skipUnless(
    RUN_IMAGES and RUN_LIVE_DEFAULT,
    "protected default-document semantic gate only",
)
class DefaultDocumentSemanticGateTests(unittest.TestCase):
    def test_default_resume_renders_reviewed_major_sections(self):
        self.assertTrue(os.environ.get("TOKENMIND_API_KEY"), "provider key is absent")
        self.assertTrue(
            os.environ.get("TOKENMIND_BASE_URL"), "provider base URL is absent"
        )
        parsed, parser_result = _parsed_default_scenario()
        self.assertEqual(parser_result["segment_count"], 31)

        script = textwrap.dedent(
            """
            import json
            import sys
            import time

            from aift_hosted3.document_artifact import (
                ArtifactProvenance,
                ROLE_HEADINGS_TH,
                render_protected_artifact,
            )
            from aift_hosted3.document_provider import (
                DOCUMENT_SYSTEM_PROMPT,
                complete_document_provider,
                encode_document_provider_request,
            )
            from aift_hosted3.pdf_client import (
                EXTRACTION_REVISION,
                PARSER_REVISION,
                DocumentSegment,
            )
            from aift_hosted3.protection import ProtectionService

            value = json.load(sys.stdin)
            protected = ProtectionService().protect_document(
                tuple(row["text"] for row in value["segments"]),
                salt="53" * 16,
                generation_seed=b"G" * 32,
            )
            parts = protected.protected_text.split("\\n\\n")
            segments = tuple(
                DocumentSegment(
                    page=row["page"],
                    segment_id=row["segment_id"],
                    text=text,
                )
                for row, text in zip(value["segments"], parts, strict=True)
            )
            request = encode_document_provider_request(segments)
            response = ""
            artifact = None
            try:
                started = time.monotonic()
                response = complete_document_provider(
                    DOCUMENT_SYSTEM_PROMPT,
                    request,
                    timeout=200.0,
                )
                elapsed_ms = round((time.monotonic() - started) * 1_000)
                artifact = render_protected_artifact(
                    response.encode("utf-8"),
                    segments=segments,
                    provenance=ArtifactProvenance(
                        hosted_version="3.0.2",
                        source_kind="synthetic_document",
                        source_receipt_id="A" * 22,
                        parser_revision=PARSER_REVISION,
                        extraction_revision=EXTRACTION_REVISION,
                        page_count=value["page_count"],
                        omitted_visual_page_numbers=tuple(
                            value["omitted_visual_page_numbers"]
                        ),
                        scenario_id="hr-resume-pdf-structured-v1",
                        scenario_registry_revision="synthetic-document-registry-v1",
                    ),
                )
                sections = artifact.protected_document_ast["ordered_sections"]
                role_counts = {
                    row["role"]: len(row["segment_ids"])
                    for row in sections
                }
                headings = [
                    "## " + ROLE_HEADINGS_TH[row["role"]]
                    for row in sections
                ]
                heading_positions = [
                    artifact.protected_markdown.index(heading)
                    for heading in headings
                ]
                rendered_ids = [
                    segment_id
                    for row in sections
                    for segment_id in row["segment_ids"]
                ]
                source_once = (
                    len(rendered_ids) == len(set(rendered_ids)) == len(segments)
                    and set(rendered_ids) == {row.segment_id for row in segments}
                )
                print(
                    json.dumps(
                        {
                            "elapsed_ms": elapsed_ms,
                            "headings_in_fixed_order": heading_positions
                            == sorted(heading_positions),
                            "major_roles_present": all(
                                role in role_counts
                                for role in (
                                    "identity",
                                    "contact",
                                    "experience",
                                    "education",
                                    "skills",
                                )
                            ),
                            "provenance_present": artifact.protected_markdown.startswith(
                                "> AI Guard Hosted 3\\.0\\.1"
                            ),
                            "role_counts": role_counts,
                            "section_roles": [row["role"] for row in sections],
                            "segment_count": sum(role_counts.values()),
                            "source_segments_rendered_once": source_once,
                            "structured_output_validated": (
                                artifact.structured_output_validated
                            ),
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                )
            finally:
                if artifact is not None:
                    artifact.clear()
                protected.mapping.clear()
                request = ""
                response = ""
            """
        )
        arguments = [
            "docker",
            "run",
            "--rm",
            "--interactive",
            "--env",
            "TOKENMIND_API_KEY",
            "--env",
            "TOKENMIND_BASE_URL",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "64",
            "--memory",
            "768m",
            "--cpus",
            "1",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=64m",
            CORE_IMAGE,
            "python",
            "-c",
            script,
        ]
        if os.environ.get("TOKENMIND_ALLOW_HTTP") == "1":
            arguments[arguments.index("--read-only"):arguments.index("--read-only")] = [
                "--env",
                "TOKENMIND_ALLOW_HTTP",
            ]
        semantic = _run(
            arguments,
            input_text=json.dumps(parser_result, ensure_ascii=False),
        )
        evidence = json.loads(semantic.stdout)
        print(
            json.dumps(
                {"default_document_semantic_gate": evidence},
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        self.assertEqual(
            evidence["role_counts"],
            {
                "achievements": 5,
                "contact": 6,
                "education": 3,
                "experience": 8,
                "identity": 3,
                "other": 2,
                "skills": 4,
            },
        )
        self.assertEqual(
            evidence["section_roles"],
            [
                "identity",
                "contact",
                "experience",
                "education",
                "skills",
                "achievements",
                "other",
            ],
        )
        self.assertEqual(evidence["segment_count"], 31)
        self.assertTrue(evidence["major_roles_present"])
        self.assertTrue(evidence["headings_in_fixed_order"])
        self.assertTrue(evidence["provenance_present"])
        self.assertTrue(evidence["source_segments_rendered_once"])
        self.assertTrue(evidence["structured_output_validated"])
        for forbidden in ("kanthida.s@example.com", "081-234-5678"):
            self.assertNotIn(forbidden, semantic.stdout)
            self.assertNotIn(forbidden, semantic.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
