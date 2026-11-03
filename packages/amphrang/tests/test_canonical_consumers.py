"""Internal compatibility and benchmark callers have exactly one core."""

import ast
import importlib
import re
from pathlib import Path

import pytest
from pii_redactor.config import CoreConfig
from pii_redactor.models import Entity

from benchmark import runner
from benchmark.types import Sample

ENGINE = Path(__file__).resolve().parents[1] / "amphrang/engine"
ALIASES = sorted(
    path.relative_to(ENGINE).with_suffix("").as_posix().replace("/", ".")
    for path in ENGINE.rglob("*.py")
    if path.name != "__init__.py" and path.name != "sensitive_span.py"
)


@pytest.mark.parametrize("module", ALIASES)
def test_internal_module_is_the_canonical_module_object(module):
    legacy = importlib.import_module(f"amphrang.engine.{module}")
    canonical = importlib.import_module(f"pii_redactor.{module}")
    assert legacy is canonical


def test_compatibility_tree_contains_no_detector_vault_or_provider_implementation():
    assert not (ENGINE / "detectors/sensitive_span.py").exists()
    for source in ENGINE.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            for node in ast.walk(tree)
        ), source


def test_retired_sensitive_expectations_have_live_replacements():
    root = ENGINE.parents[1]
    guide = (root / "docs/migrations/shared-core.md").read_text(encoding="utf-8")
    ledger = guide.split("## S5.1 private-test expectation ledger", 1)[1]
    rows = re.findall(
        r"\| `(test_\w+)` \| (Preserved|Superseded policy) \| `(test_\w+)` \|", ledger
    )
    assert len(rows) == 49 and len({name for name, _, _ in rows}) == 49
    tests = ast.parse((root / "tests/test_sensitive_span.py").read_text(encoding="utf-8"))
    current = {node.name for node in tests.body if isinstance(node, ast.FunctionDef)}
    assert all(replacement in current for _, _, replacement in rows)
    assert sum(status == "Preserved" for _, status, _ in rows) == 5


def test_alias_monkeypatch_and_cache_identity_are_shared(monkeypatch):
    legacy = importlib.import_module("amphrang.engine.detectors.tb_detector")
    canonical = importlib.import_module("pii_redactor.detectors.tb_detector")
    cache = {"synthetic": object()}
    monkeypatch.setattr(legacy, "_ner_cache", cache)
    assert canonical._ner_cache is cache


def test_benchmark_uses_one_local_config_snapshot_without_environment_mutation(monkeypatch):
    from pii_redactor.detectors import aggregate

    snapshot = CoreConfig(engine="finetuned", finetuned_model_dir="sdk-model", allow_remote=False)
    captures, resolutions = [], []
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "synthetic-original")
    monkeypatch.setenv("AIGUARD_NER_ENGINE", "tner")
    monkeypatch.setattr(runner, "sdk_core_config", lambda: resolutions.append(1) or snapshot)

    def detect(text, *, ner_diagnostics=None, config):
        captures.append(config)
        return [Entity("synthetic", "TB", "NAME", (0, len(text)), 1.0, text)]

    monkeypatch.setattr(aggregate, "detect_all", detect)
    samples = [Sample("synthetic", [], "synthetic", "core")] * 2
    assert runner.predict_samples(samples, "crf") == [[(0, 9, "NAME")]] * 2
    assert resolutions == [1]
    assert len(captures) == 2 and all(config is captures[0] for config in captures)
    assert captures[0] == CoreConfig(
        engine="thainer", finetuned_model_dir="sdk-model", allow_remote=False
    )
    import os

    assert os.environ["AMPHRANG_NER_ENGINE"] == "synthetic-original"
    assert os.environ["AIGUARD_NER_ENGINE"] == "tner"


def test_strategy_runner_binds_both_engines_to_same_sdk_profile(monkeypatch):
    from pii_redactor.detectors import aggregate

    snapshot = CoreConfig(finetuned_model_dir="sdk-model", allow_remote=False)
    captures, resolutions = [], []
    monkeypatch.setattr(runner, "sdk_core_config", lambda: resolutions.append(1) or snapshot)
    monkeypatch.setattr(
        runner, "build_corpus", lambda **kwargs: [Sample("synthetic", [], "s", "core")]
    )
    monkeypatch.setattr(runner, "score", lambda *args, **kwargs: {})

    def detect(text, *, ner_diagnostics, config):
        captures.append(config)
        return []

    monkeypatch.setattr(aggregate, "detect_all", detect)
    results = runner.run_strategy_comparison()
    assert set(results) == {"crf", "wcb", "union", "route"}
    assert resolutions == [1]
    assert [config.engine for config in captures] == ["thainer", "wangchanberta"]
    assert all(
        config.allow_remote is False and config.finetuned_model_dir == "sdk-model"
        for config in captures
    )


def test_perf_measurements_reuse_one_sdk_profile(monkeypatch):
    import amphrang
    from benchmark import perf

    snapshot = CoreConfig(allow_remote=False)
    resolutions, captures = [], []
    monkeypatch.setattr(perf, "sdk_core_config", lambda: resolutions.append(1) or snapshot)
    monkeypatch.setattr(perf, "build_perf_documents", lambda **kwargs: {"S": "one", "M": "two"})
    monkeypatch.setattr(
        amphrang, "_detect_with_config", lambda text, *, config: captures.append(config) or []
    )
    monkeypatch.setattr(
        amphrang,
        "_anonymize_with_config",
        lambda text, *, config, **kwargs: captures.append(config),
    )

    def measure(function, iterations, warmup):
        function()
        return [0.01] * iterations

    perf.run(profile="ci", measure=measure, cold_start_fn=lambda: [0.01])
    assert resolutions == [1]
    assert captures and all(config is snapshot for config in captures)


def test_perf_cold_children_receive_captured_sdk_settings(monkeypatch):
    from types import SimpleNamespace

    from benchmark import perf

    snapshot = CoreConfig(finetuned_model_dir="sdk-model", allow_remote=False)
    captures, resolutions = [], []
    monkeypatch.setattr(perf, "sdk_core_config", lambda: resolutions.append(1) or snapshot)

    def run(*args, env, **kwargs):
        captures.append(env)
        monkeypatch.setenv("AMPHRANG_NER_ENGINE", "unsupported-between-children")
        return SimpleNamespace(stdout="0.01")

    monkeypatch.setattr(perf.subprocess, "run", run)
    assert perf.measure_cold_start(2) == [0.01, 0.01]
    assert resolutions == [1]
    assert all(env["AMPHRANG_NER_ENGINE"] == "thainer" for env in captures)
    assert all(env["AMPHRANG_FINETUNED_MODEL_DIR"] == "sdk-model" for env in captures)
