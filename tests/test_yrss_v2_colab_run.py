"""The off-machine LLM runner writes files the harness cache accepts. Synthetic text only."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

from benchmark.blind_v2.score import dedupe_predictions
from benchmark.yrss_v2 import colab_run, harness
from benchmark.yrss_v2.corpus import canonical_bytes


def test_dedupe_matches_the_scorer_rule():
    spans = [(0, 5, "NAME"), (2, 8, "PHONE"), (10, 12, "EMAIL"), (10, 15, "NAME"), (20, 20, "X")]
    assert colab_run.dedupe(spans) == dedupe_predictions(spans)


def test_written_cache_is_reused_by_the_harness(tmp_path, monkeypatch):
    docs = [
        SimpleNamespace(doc_id="d1", text="คุณสมชาย โทร 081"),
        SimpleNamespace(doc_id="d2", text="ไม่มีข้อมูล"),
    ]
    corpus = SimpleNamespace(split="dev", documents=docs, version="v", seed=1)
    monkeypatch.setattr(harness, "canonical_bytes", lambda c: b"corpus")
    options = {"model": "m", "seed": 3, "base_url": "http://127.0.0.1:11434/v1"}
    meta = {
        "model": "m",
        "base_url": options["base_url"],
        "split": "dev",
        "corpus_sha256": hashlib.sha256(b"corpus").hexdigest(),
    }

    def fake_make_predictor(**kwargs):
        def predict(text):
            predict.stats["requests"] += 1
            return [(0, 3, "NAME"), (1, 4, "PHONE")] if "โทร" in text else []

        predict.stats = {"requests": 0, "http_errors": 0}
        return predict

    monkeypatch.setattr(colab_run, "make_predictor", fake_make_predictor)
    colab_run.run_seed([{"doc_id": d.doc_id, "text": d.text} for d in docs], meta, 3, tmp_path)

    cache = harness.DocumentCache(
        tmp_path / "llm-seed3.jsonl", harness._cache_header(options, corpus)
    )
    first = cache.get(docs[0])
    assert first["spans"] == [[0, 3, "NAME"]]
    assert cache.get(docs[1])["spans"] == []
    assert first["stats"] == {"requests": 1, "http_errors": 0}


def test_header_matches_the_harness_for_a_real_split():
    from benchmark.yrss_v2.corpus import build_corpus

    corpus = build_corpus("dev")
    options = {"model": "m", "seed": 2, "base_url": "u"}
    meta = {
        "model": "m",
        "base_url": "u",
        "split": "dev",
        "corpus_sha256": hashlib.sha256(canonical_bytes(corpus)).hexdigest(),
    }
    assert colab_run.header(meta, 2) == harness._cache_header(options, corpus)
