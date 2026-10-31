import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_pair_reservation_cannot_be_reused(tmp_path):
    from scripts.yrss_paired_eval import reserve

    reserve(tmp_path, {"candidate": "synthetic"})
    with pytest.raises(FileExistsError):
        reserve(tmp_path, {"candidate": "replacement"})


def test_aggregate_arm_drops_private_per_document_counts():
    from scripts.yrss_paired_eval import public_arm

    result = public_arm({"metrics": {"overall": {}}, "counts": [(1, 0, 0)], "identity": {}})
    assert "counts" not in result
    assert result["metrics"] == {"overall": {}}


def test_arm_identity_rejects_modified_detector_or_model():
    from scripts.yrss_paired_eval import verify_arm_identity

    reference = dict.fromkeys(
        (
            "source_sha256",
            "scorer_sha256",
            "model_sha256",
            "pythainlp_assets_sha256",
            "requirements_sha256",
            "corpus_sha256",
            "packages",
            "python",
            "runtime_evaluator_sha256",
            "paired_driver_sha256",
        ),
        "original",
    )
    for field in reference:
        with pytest.raises(ValueError, match="arm identity mismatch"):
            verify_arm_identity(reference, {**reference, field: "changed"})


def test_isolated_worker_smoke_uses_only_synthetic_temporary_data(tmp_path):
    from benchmark.blind import freeze, generate_key
    from benchmark.campaign import manifest
    from scripts.yrss_paired_eval import VERSION, worker

    root = Path(__file__).resolve().parents[1]
    data = tmp_path / "data"
    data.mkdir()
    key = tmp_path / "test.key"
    generate_key(key)
    draft = tmp_path / "draft.jsonl"
    records = [
        {
            "doc_id": "smoke-positive",
            "slice": "medical",
            "layer": "natural",
            "annotated": "โทร [[PHONE|081-234-5678]] ครับ",
        },
        {
            "doc_id": "smoke-negative",
            "slice": "negative",
            "layer": "negative",
            "annotated": "เอกสารทดสอบระบบ",
        },
    ]
    draft.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8"
    )
    freeze(draft, key, data_dir=data, version=VERSION, type_minimums={}, reveal_budget=2)
    identity = tmp_path / "identity.json"
    identity.write_text(json.dumps({"manifest": manifest()}), encoding="utf-8")
    result = worker(
        SimpleNamespace(worker_root=root, identity=identity, key_file=key, data_dir=data)
    )
    assert result["metrics"]["overall"]["gold_entities"] == 1
    assert result["ner_chunks"]["skipped"] == 0
    assert len(result["counts"]) == 2
    assert "081-234-5678" not in json.dumps(result)
