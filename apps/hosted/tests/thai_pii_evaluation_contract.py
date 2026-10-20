#!/usr/bin/env python3
"""Deterministic, synthetic-only, provider-free Sprint 3 evaluation contract."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "evaluation" / "thai_pii"
BASELINE_SHA = "72e18bbe723adaf54c847e4b17c2177dfa60dd68"
EXPECTED_TYPES = {
    "ADDRESS",
    "BANK_ACCOUNT",
    "CREDIT_CARD",
    "DATE",
    "DATE_OF_BIRTH",
    "EMAIL",
    "IBAN",
    "ID_NUMBER",
    "LOCATION",
    "MEDICAL_ID",
    "NAME",
    "ORGANIZATION",
    "PASSPORT",
    "PHONE",
    "POSTAL_CODE",
    "STUDENT_ID",
    "THAI_ID",
    "VEHICLE_PLATE",
}
SECTION26 = {
    "RACE_ETHNICITY",
    "POLITICAL_OPINION",
    "RELIGION",
    "HEALTH",
    "SEXUAL_BEHAVIOR",
    "CRIMINAL_RECORD",
    "DISABILITY",
    "LABOR_UNION",
}
CORPUS_KEYS = {
    "case_id",
    "base_id",
    "text",
    "expected_spans",
    "scenario",
    "action",
    "phenomena",
    "provenance",
}
SPAN_KEYS = {"start_cp", "end_cp", "type"}
FORBIDDEN_DATA_KEYS = re.compile(
    r"(?:mapping|original|replacement|token|surrogate|masked|sanitized|restored|"
    r"provider|request_body|cookie|session|credential|password|access_key|api_key)",
    re.IGNORECASE,
)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{12,}", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\b(?:glpat-|sk-)[A-Za-z0-9_-]{20,}\b"),
)


def load(name: str) -> dict:
    return json.loads((EVAL / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from walk_keys(child)


def walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child)


def import_evaluator():
    spec = importlib.util.spec_from_file_location("thai_pii_evaluator", EVAL / "evaluate.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_schema_and_spans(corpus: dict, capabilities: dict) -> None:
    assert set(capabilities["entity_types"]) == EXPECTED_TYPES
    assert corpus["schema_version"] == 1
    assert corpus["corpus_id"] == "aiguard-thai-pii-adversarial-v1"
    assert corpus["offset_unit"] == "unicode_code_point_half_open"
    assert "no user" in corpus["synthetic_declaration"]
    assert len(corpus["cases"]) >= 100
    ids: set[str] = set()
    actions = Counter()
    phenomena: set[str] = set()
    expected_types: set[str] = set()
    scenarios: set[str] = set()
    for case in corpus["cases"]:
        assert set(case) == CORPUS_KEYS, case.get("case_id")
        assert re.fullmatch(r"C\d{4}", case["case_id"])
        assert case["case_id"] not in ids
        ids.add(case["case_id"])
        assert case["text"] and len(case["text"]) <= 20_000
        assert case["provenance"] == f"constructed-template:{case['base_id']}"
        assert case["action"] in {"mask_required", "do_not_mask", "ambiguous"}
        actions[case["action"]] += 1
        scenarios.add(case["scenario"])
        phenomena.update(case["phenomena"])
        previous_end = 0
        for span in case["expected_spans"]:
            assert set(span) == SPAN_KEYS
            assert span["type"] in EXPECTED_TYPES
            assert 0 <= span["start_cp"] < span["end_cp"] <= len(case["text"])
            assert span["start_cp"] >= previous_end
            previous_end = span["end_cp"]
            expected_types.add(span["type"])
        if case["action"] == "mask_required":
            assert case["expected_spans"], case["case_id"]
        else:
            assert not case["expected_spans"], case["case_id"]
    assert actions["mask_required"] >= 100
    assert actions["do_not_mask"] >= 20
    assert actions["ambiguous"] >= 10
    assert expected_types == EXPECTED_TYPES
    for required_scenario in {
        "person",
        "phone",
        "email",
        "thai-id",
        "address",
        "organization",
        "financial",
        "mixed",
    }:
        assert required_scenario in scenarios
    for required_phenomenon in {
        "zero-width",
        "parentheses",
        "hyphen",
        "space",
        "thai-digits",
        "mixed-case",
        "json-like",
        "multiline",
        "non-personal-date",
        "product-code",
        "ticket-number",
        "course-code",
        "reserved-ip",
        "version",
        "timestamp",
        "name-like-word",
    }:
        assert required_phenomenon in phenomena, required_phenomenon


def assert_section26(section26: dict) -> None:
    assert section26["schema_version"] == 1
    assert section26["semantics"].startswith("heuristic keyword signal")
    assert len(section26["cases"]) == 32
    by_category: dict[str, Counter] = defaultdict(Counter)
    ids = set()
    for case in section26["cases"]:
        assert set(case) == {
            "case_id",
            "text",
            "expected_categories",
            "action",
            "phenomena",
            "provenance",
        }
        assert re.fullmatch(r"S\d{4}", case["case_id"])
        assert case["case_id"] not in ids
        ids.add(case["case_id"])
        assert set(case["expected_categories"]) <= SECTION26
        for category in case["expected_categories"]:
            by_category[category]["positive"] += 1
        for category in SECTION26:
            if category.lower() in case["provenance"] and not case["expected_categories"]:
                by_category[category]["negative"] += 1
    for category in SECTION26:
        assert by_category[category]["positive"] == 2
        assert by_category[category]["negative"] == 2


def assert_provenance_regeneration(manifest: dict) -> None:
    assert manifest["source_kind"] == "constructed"
    assert manifest["license"] == "CC0-1.0"
    assert manifest["fixed_seed"] == 20260810
    assert manifest["corpus_case_count"] == 138
    assert manifest["section26_case_count"] == 32
    assert manifest["generator_sha256"] == sha256(EVAL / "generate_corpus.py")
    assert manifest["corpus_schema_sha256"] == sha256(EVAL / "corpus.schema.json")
    assert manifest["section26_schema_sha256"] == sha256(EVAL / "section26.schema.json")
    assert manifest["corpus_sha256"] == sha256(EVAL / "corpus.v1.json")
    assert manifest["section26_sha256"] == sha256(EVAL / "section26.v1.json")
    assert manifest["annotation"]["detector_output_visible_during_annotation"] is False
    assert manifest["annotation"]["ambiguous_cases_excluded_from_headline"] is True
    assert manifest["annotation"]["thai_human_adjudication"] == "pending"
    assert manifest["annotation"]["offset_convention"].startswith("Unicode code-point half-open")
    assert "production traffic" in manifest["source_exclusions"]
    assert "historical evidence fixtures" in manifest["source_exclusions"]

    corpus_schema = load("corpus.schema.json")
    section26_schema = load("section26.schema.json")
    assert corpus_schema["additionalProperties"] is False
    assert corpus_schema["properties"]["cases"]["items"]["additionalProperties"] is False
    assert corpus_schema["properties"]["cases"]["items"]["properties"]["expected_spans"]["items"]["additionalProperties"] is False
    assert section26_schema["additionalProperties"] is False
    assert section26_schema["properties"]["cases"]["items"]["additionalProperties"] is False

    honey = "SPRINT3_HONEY_SECRET_VALUE_DO_NOT_LEAK"
    with tempfile.TemporaryDirectory(prefix="aiguard-sprint3-") as temporary:
        output = Path(temporary)
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONUTF8": "1",
            "APP_TOKENMIND_API_KEY": honey,
            "UNRELATED_SECRET_TOKEN": honey,
        }
        completed = subprocess.run(
            [sys.executable, str(EVAL / "generate_corpus.py"), "--output-dir", str(output)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        assert honey not in completed.stdout + completed.stderr
        for name in ("corpus.v1.json", "section26.v1.json", "manifest.v1.json"):
            generated = (output / name).read_bytes()
            assert generated == (EVAL / name).read_bytes(), name
            assert honey.encode() not in generated
        corpus = load("corpus.v1.json")
        assert not any(case["text"] in completed.stdout for case in corpus["cases"])


def assert_safety_and_boundaries(corpus: dict, baseline: dict) -> None:
    for path in EVAL.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        assert path.suffix in {".py", ".json", ".md"}, path.name
        data = path.read_bytes()
        assert b"\0" not in data, path.name
        text = data.decode("utf-8")
        for pattern in SECRET_PATTERNS:
            assert not pattern.search(text), path.name

    for key in walk_keys(corpus):
        assert not FORBIDDEN_DATA_KEYS.search(key), key

    result_text = json.dumps(baseline, ensure_ascii=False, sort_keys=True)
    result_strings = tuple(walk_strings(baseline))
    for case in corpus["cases"]:
        assert not any(case["text"] in item for item in result_strings), case["case_id"]
        for span in case["expected_spans"]:
            value = case["text"][span["start_cp"] : span["end_cp"]]
            assert value not in result_strings, case["case_id"]
            if len(value) >= 8:
                assert not any(value in item for item in result_strings), case["case_id"]
    assert "APP_TOKENMIND_API_KEY" not in result_text
    assert "APP_AIGUARD_API_KEY" not in result_text
    assert baseline["artifact_privacy"] == {
        "contains_corpus_text": False,
        "contains_credentials": False,
        "contains_generated_replacements": False,
        "contains_provider_body": False,
        "contains_reidentification_pairs": False,
    }

    generator_tree = ast.parse((EVAL / "generate_corpus.py").read_text(encoding="utf-8"))
    evaluator_text = (EVAL / "evaluate.py").read_text(encoding="utf-8")
    evaluator_tree = ast.parse(evaluator_text)
    banned_imports = {"httpx", "requests", "urllib", "subprocess", "aiohttp"}
    for tree in (generator_tree, evaluator_tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not {alias.name.split(".")[0] for alias in node.names} & banned_imports
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in banned_imports
    for forbidden in (
        "aift_gateway",
        "app.server",
        "ai_client",
        "provider_factory",
        "/api/roundtrip",
    ):
        assert forbidden not in evaluator_text
    assert "_install_network_tripwire()" in evaluator_text
    assert "PYTHAINLP_OFFLINE" in evaluator_text
    assert not re.search(r"['\"]C\d{4}['\"]", evaluator_text)

    relative = EVAL.relative_to(ROOT).parts
    assert relative[0] == "evaluation"
    assert relative[0] not in {"core", "web", "api"}
    for dockerfile in (ROOT / "core" / "Dockerfile", ROOT / "web" / "Dockerfile", ROOT / "api" / "Dockerfile"):
        assert "evaluation" not in dockerfile.read_text(encoding="utf-8").lower()
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "evaluation" not in compose.lower()


def assert_math_and_result(corpus: dict, manifest: dict, baseline: dict) -> None:
    evaluator = import_evaluator()
    assert evaluator._prf(8, 2, 4) == {
        "tp": 8,
        "fp": 2,
        "fn": 4,
        "precision": 0.8,
        "recall": 0.666667,
        "f1": 0.727273,
        "f2": 0.689655,
    }
    synthetic_cases = [
        {
            "case_id": "C9998",
            "base_id": "math_positive",
            "text": "abcdef",
            "expected_spans": [{"start_cp": 1, "end_cp": 4, "type": "NAME"}],
            "scenario": "math",
            "action": "mask_required",
            "phenomena": ["plain"],
            "provenance": "constructed-template:math_positive",
        },
        {
            "case_id": "C9999",
            "base_id": "math_negative",
            "text": "uvwxyz",
            "expected_spans": [],
            "scenario": "math",
            "action": "do_not_mask",
            "phenomena": ["plain"],
            "provenance": "constructed-template:math_negative",
        },
    ]
    scored = evaluator._score_detection(
        synthetic_cases,
        {
            "C9998": [{"start_cp": 1, "end_cp": 4, "type": "NAME", "redact_type": "TB"}],
            "C9999": [{"start_cp": 0, "end_cp": 2, "type": "DATE", "redact_type": "FP"}],
        },
    )
    assert scored["exact_typed_entity"]["tp"] == 1
    assert scored["exact_typed_entity"]["fp"] == 1
    assert scored["exact_typed_entity"]["fn"] == 0
    assert scored["negative_controls"]["document_false_positive_rate"] == 1.0

    assert baseline["repository_sha"] == BASELINE_SHA
    assert baseline["production_baseline_sha"] == BASELINE_SHA
    assert baseline["runtime"]["image_revision"] == BASELINE_SHA
    assert baseline["runtime"]["network_attempts"] == 0
    assert baseline["runtime"]["provider_calls"] == 0
    assert baseline["runtime"]["credentials_required"] is False
    assert baseline["corpus"]["sha256"] == manifest["corpus_sha256"]
    assert baseline["corpus"]["cases"] == len(corpus["cases"])
    assert baseline["corpus"]["expected_entities"] == sum(
        len(case["expected_spans"]) for case in corpus["cases"] if case["action"] != "ambiguous"
    )
    assert baseline["determinism"]["passes"] == 3
    assert baseline["determinism"]["all_passes_identical"] is True
    assert baseline["determinism"]["ner_diagnostics"]["skipped"] == 0
    assert set(baseline["prediction_inventory"]) == {case["case_id"] for case in corpus["cases"]}
    exact = baseline["detection"]["exact_typed_entity"]
    assert exact["tp"] + exact["fn"] == baseline["corpus"]["expected_entities"]
    spans = baseline["detection"]["span_metrics"]
    assert spans["exact_matches"] == exact["tp"]
    assert spans["expected_entities"] == baseline["corpus"]["expected_entities"]
    assert spans["typed_iou_gte_0_5_matches"] >= spans["exact_matches"]
    assert baseline["detection"]["ambiguous"]["documents_excluded_from_headline"] == 12
    assert baseline["section26"]["label"].startswith("HEURISTIC SIGNAL EVALUATION")
    for mode in ("token", "surrogate"):
        result = baseline["protection"]["modes"][mode]
        assert result["documents_attempted"] == baseline["corpus"]["positive_cases"]
        assert result["recognized_raw_value_removal_rate"] == 1.0
        assert result["exact_restoration_rate"] == 1.0
        assert result["zero_leftover_rate"] == 1.0
        assert result["safe_disposition_rate"] == 1.0
    assert baseline["protection"]["provider_calls"] == 0
    assert baseline["protection"]["reidentification_pair_material_exported"] is False
    assert baseline["performance"]["samples"] >= len(corpus["cases"]) * 3
    assert "not a hosted SLA" in baseline["performance"]["scope"]


def main() -> int:
    corpus = load("corpus.v1.json")
    section26 = load("section26.v1.json")
    manifest = load("manifest.v1.json")
    capabilities = load("capabilities.json")
    baseline = load("baseline.72e18bbe.json")
    assert_schema_and_spans(corpus, capabilities)
    assert_section26(section26)
    assert_provenance_regeneration(manifest)
    assert_safety_and_boundaries(corpus, baseline)
    assert_math_and_result(corpus, manifest, baseline)
    print(
        "Thai PII evaluation contract ok: 138 constructed cases, deterministic spans/math, "
        "offline provider-free evidence, ambiguous cases separated, no runtime/API widening"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
