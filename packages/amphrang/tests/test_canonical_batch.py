"""Config capture and Windows-spawn contracts for SDK batch operations."""

from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context

import pytest
from pii_redactor.config import CoreConfig

import amphrang


def _meaningful(rows):
    return [
        [(entity.span, entity.data_type, entity.original_text) for entity in row] for row in rows
    ]


def test_batches_capture_one_config_for_serial_jobs(monkeypatch):
    config = CoreConfig(allow_remote=False)
    resolutions = []
    observed = []
    monkeypatch.setattr(amphrang, "sdk_core_config", lambda: resolutions.append(1) or config)
    monkeypatch.setattr(
        amphrang,
        "_detect_with_config",
        lambda text, *, config: observed.append(config) or [],
    )
    assert amphrang.detect_batch(["first", "second"]) == [[], []]
    monkeypatch.setattr(
        amphrang,
        "_anonymize_with_config",
        lambda text, *, config, **kwargs: (
            observed.append(config) or amphrang.AnonymizeResult(text, {}, [], {})
        ),
    )
    amphrang.anonymize_batch(["first", "second"])
    assert resolutions == [1, 1]
    assert observed == [config] * 4


@pytest.mark.parametrize("operation", ["detect_batch", "anonymize_batch"])
def test_spawn_uses_parent_snapshot_despite_conflicting_child_env(monkeypatch, operation):
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "thainer")
    monkeypatch.setenv("AIGUARD_NER_ENGINE", "tner")
    monkeypatch.setenv("AIFORTHAI_API_KEY", "synthetic-key")
    texts = ["โทร 081-234-5678", "อีเมล demo@example.com"]
    call = getattr(amphrang, operation)
    serial = call(texts)

    def spawn_after_env_change(fn, jobs, workers):
        monkeypatch.setenv("AMPHRANG_NER_ENGINE", "unsupported-child-engine")
        with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as pool:
            return list(pool.map(fn, jobs))

    monkeypatch.setattr(amphrang, "_run_in_pool", spawn_after_env_change)
    parallel = call(texts, workers=2)
    if operation == "detect_batch":
        assert _meaningful(parallel) == _meaningful(serial)
    else:
        for text, result in zip(texts, parallel):
            restored = amphrang._restore_with_config(
                result.text, result.mapping, config=CoreConfig(allow_remote=False)
            )
            assert restored.text == text
        assert [result.entity_type_counts for result in parallel] == [
            result.entity_type_counts for result in serial
        ]


def test_batch_failure_exposes_safe_metadata_and_index(monkeypatch):
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "thainer")
    with pytest.raises(amphrang.LeakBlockedError) as caught:
        amphrang.anonymize_batch(["hello", "ค่าที่เหลือ 6801234"], workers=2)
    assert caught.value.batch_index == 1
    assert caught.value.leak_types == ["ORPHAN_DIGITS"]
    assert "6801234" not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize("operation", ["detect_batch", "anonymize_batch"])
def test_remote_engine_batch_failure_survives_spawn_without_pickle_error(monkeypatch, operation):
    from pii_redactor.detectors.ner_failure import NERFailureError

    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "tner")
    monkeypatch.setenv("AIFORTHAI_API_KEY", "synthetic-key")
    with pytest.raises(NERFailureError) as caught:
        getattr(amphrang, operation)(["first", "second"], workers=2)
    assert caught.value.code == "ner_unavailable"
    assert caught.value.category == "configuration"
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
