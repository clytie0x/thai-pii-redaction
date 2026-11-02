"""SDK contracts for the direct first-party core migration."""

import builtins
import inspect
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import pytest
from pii_redactor import report, session_service, stateless
from pii_redactor.config import CoreConfig
from pii_redactor.detectors import aggregate, tb_detector
from pii_redactor.models import Entity

import amphrang


def test_facade_uses_canonical_types_and_operations():
    assert amphrang.Entity is Entity
    assert amphrang._detect_all is aggregate.detect_all
    assert amphrang._sanitize_stateless is stateless.sanitize_stateless
    assert amphrang._restore_stateless is stateless.restore_stateless
    assert amphrang._analyze_text is report.analyze_text
    assert amphrang._SessionService is session_service.SessionService
    assert amphrang.LeakBlockedError is stateless.StatelessLeakError
    assert amphrang.SessionExpiredError is session_service.SessionExpiredError


def test_sdk_config_is_local_only_immutable_and_prefix_isolated(monkeypatch):
    from amphrang._core_config import sdk_audit_config, sdk_core_config

    monkeypatch.setenv("AIGUARD_NER_ENGINE", "tner")
    monkeypatch.setenv("AIGUARD_FINETUNED_MODEL_DIR", "root-model")
    monkeypatch.setenv("AIFORTHAI_API_KEY", "synthetic-key")
    monkeypatch.setenv("AIGUARD_AUDIT_STDOUT", "1")
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "finetuned")
    monkeypatch.setenv("AMPHRANG_FINETUNED_MODEL_DIR", "sdk-model")
    monkeypatch.setenv("AMPHRANG_AUDIT_STDOUT", "0")
    config = sdk_core_config()
    assert config == CoreConfig(
        engine="finetuned", finetuned_model_dir="sdk-model", allow_remote=False
    )
    assert sdk_audit_config().stdout is False
    assert "synthetic-key" not in repr(config)
    with pytest.raises(FrozenInstanceError):
        config.allow_remote = True


def test_private_helpers_require_explicit_keyword_config():
    for name in (
        "_detect_with_config",
        "_anonymize_with_config",
        "_restore_with_config",
        "_analyze_with_config",
    ):
        parameter = inspect.signature(getattr(amphrang, name)).parameters["config"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is inspect.Parameter.empty


@pytest.mark.parametrize("config", [None, CoreConfig(engine="tner", allow_remote=True)])
def test_private_helpers_reject_implicit_or_remote_configs(config):
    for helper, arguments in (
        (amphrang._detect_with_config, ("synthetic",)),
        (amphrang._anonymize_with_config, ("synthetic",)),
        (amphrang._restore_with_config, ("synthetic", {})),
        (amphrang._analyze_with_config, ("synthetic",)),
    ):
        with pytest.raises((TypeError, ValueError)):
            helper(*arguments, config=config)


def test_public_signatures_stay_stable():
    expected = {
        "detect": ["text"],
        "anonymize": ["text", "mode", "salt", "prior_mapping"],
        "restore": ["text", "mapping", "mode"],
        "analyze": ["text"],
        "detect_batch": ["texts", "workers"],
        "anonymize_batch": ["texts", "mode", "salt", "workers"],
        "Session": ["mode", "ttl_s"],
    }
    for name, parameters in expected.items():
        assert list(inspect.signature(getattr(amphrang, name)).parameters) == parameters


def test_detect_preserves_source_spans_and_passes_snapshot(monkeypatch):
    config = CoreConfig(allow_remote=False)
    seen = []

    def detect(text, *, config):
        seen.append((text, config))
        return [Entity("synthetic", "FP", "PHONE", (5, len(text)), 1.0, text[5:])]

    monkeypatch.setattr(amphrang, "_detect_all", detect)
    text = "โทร: ๐๘๑-๒๓๔-๕๖๗๘"
    entities = amphrang._detect_with_config(text, config=config)
    assert seen == [("โทร: 081-234-5678", config)]
    assert entities[0].original_text == text[5:]
    assert entities[0].span == (5, len(text))


def test_public_calls_resolve_each_snapshot_once(monkeypatch):
    config = CoreConfig(allow_remote=False)
    calls = []
    monkeypatch.setattr(amphrang, "sdk_core_config", lambda: calls.append(1) or config)
    for name, helper, arguments in (
        ("detect", "_detect_with_config", ("synthetic",)),
        ("anonymize", "_anonymize_with_config", ("synthetic",)),
        ("restore", "_restore_with_config", ("synthetic", {})),
        ("analyze", "_analyze_with_config", ("synthetic",)),
    ):
        observed = []
        monkeypatch.setattr(
            amphrang,
            helper,
            lambda *args, config, observed=observed, **kwargs: observed.append(config),
        )
        getattr(amphrang, name)(*arguments)
        assert observed == [config]
    assert len(calls) == 4


def test_session_captures_config_for_its_lifecycle(monkeypatch):
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "thainer")
    monkeypatch.setenv("AIGUARD_NER_ENGINE", "tner")
    with amphrang.Session() as session:
        config = session._service._config
        assert config == CoreConfig(engine="thainer", allow_remote=False)
        monkeypatch.setenv("AMPHRANG_NER_ENGINE", "unsupported-after-construction")
        masked = session.anonymize("โทร 081-234-5678")
        assert masked.mapping == {}
        assert "081-234-5678" not in masked.text
        assert session.restore(masked.text).text == "โทร 081-234-5678"
        assert session._service._config is config


def test_remote_engine_is_rejected_even_with_warm_root_cache(monkeypatch):
    from pii_redactor.detectors.ner_failure import NERFailureError

    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "tner")
    monkeypatch.setenv("AIGUARD_NER_ENGINE", "tner")
    monkeypatch.setattr(tb_detector, "_ner_cache", {"tner": object()})
    with pytest.raises(NERFailureError) as caught:
        amphrang.detect("ข้อความสังเคราะห์")
    assert caught.value.code == "ner_unavailable"
    assert caught.value.category == "configuration"


def test_unsupported_sdk_engine_never_falls_back_to_valid_root(monkeypatch):
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "unsupported-sdk-engine")
    monkeypatch.setenv("AIGUARD_NER_ENGINE", "thainer")
    with pytest.raises(ValueError, match="unsupported-sdk-engine"):
        amphrang.detect("ข้อความสังเคราะห์")


def test_missing_explicit_engine_dependency_never_falls_back(monkeypatch):
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "wangchanberta")
    monkeypatch.setenv("AIGUARD_NER_ENGINE", "thainer")
    monkeypatch.setattr(tb_detector, "_ner_cache", {})
    original_import = builtins.__import__

    def missing_transformers(name, *args, **kwargs):
        if name == "transformers":
            raise ImportError("synthetic missing dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_transformers)
    with pytest.raises(tb_detector.NEREngineUnavailableError):
        amphrang.detect("ข้อความสังเคราะห์")


def test_model_directories_remain_isolated_with_warm_root_cache(monkeypatch, tmp_path):
    from pii_redactor.detectors import finetuned_engine

    root_directory = tmp_path / "root-model"
    sdk_directory = tmp_path / "sdk-model"
    root_directory.mkdir()
    sdk_directory.mkdir()
    monkeypatch.setenv("AIGUARD_NER_ENGINE", "finetuned")
    monkeypatch.setenv("AIGUARD_FINETUNED_MODEL_DIR", str(root_directory))
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "finetuned")
    monkeypatch.setenv("AMPHRANG_FINETUNED_MODEL_DIR", str(sdk_directory))
    made = []

    class FakeEngine:
        def __init__(self, model_dir):
            self.thresholds = {}
            made.append(model_dir)

        def spans(self, text):
            return []

    monkeypatch.setattr(finetuned_engine, "FinetunedEngine", FakeEngine)
    monkeypatch.setattr(tb_detector, "_finetuned_cache", {})
    aggregate.detect_all("synthetic text", config=CoreConfig.from_env())
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(amphrang.detect, ["synthetic text"] * 4))
    assert sorted(made) == sorted([str(root_directory.resolve()), str(sdk_directory.resolve())])


def test_mapping_reuse_and_legacy_sensitive_restore(monkeypatch):
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "thainer")
    first = amphrang.anonymize("โทร 081-234-5678")
    token = next(iter(first.mapping))
    second = amphrang.anonymize("โทร 081-234-5678", prior_mapping=first.mapping)
    assert token in second.text
    legacy = f"[ข้อมูลสุขภาพ_{'a' * 25}_{'b' * 20}_1]"
    restored = amphrang.restore(legacy, {legacy: "ข้อมูลสุขภาพสังเคราะห์"})
    assert restored.text == "ข้อมูลสุขภาพสังเคราะห์"


def test_cli_report_uses_public_canonical_analysis(monkeypatch, tmp_path, capsys):
    from argparse import Namespace

    from amphrang.cli import cmd_report

    source = tmp_path / "synthetic.txt"
    source.write_text("โทร 081-234-5678", encoding="utf-8")
    calls = []
    monkeypatch.setattr(
        amphrang,
        "analyze",
        lambda text: calls.append(text)
        or {
            "direct_pii_count": 0,
            "fp_count": 0,
            "tb_count": 0,
            "breakdown": [],
            "section26": [{"category": "HEALTH", "start": 0, "end": 3}],
        },
    )
    cmd_report(Namespace(file=str(source)))
    assert calls == ["โทร 081-234-5678"]
    output = capsys.readouterr().out
    assert "Total entities detected: 0" in output
    assert "HEALTH" in output
    assert "081-234-5678" not in output


SENSITIVE_CATEGORIES = [
    ("RACE_ETHNICITY", "เชื้อชาติ"),
    ("POLITICAL_OPINION", "ความคิดเห็นทางการเมือง"),
    ("RELIGION", "ศาสนา"),
    ("HEALTH", "โรค"),
    ("SEXUAL_BEHAVIOR", "เพศวิถี"),
    ("CRIMINAL_RECORD", "คดี"),
    ("DISABILITY", "ความพิการ"),
    ("LABOR_UNION", "สหภาพแรงงาน"),
    ("GENETIC", "พันธุกรรม"),
    ("BIOMETRIC", "ลายนิ้วมือ"),
]


@pytest.mark.parametrize(("category", "keyword"), SENSITIVE_CATEGORIES)
def test_sensitive_policy_warns_without_masking_and_protects_identifiers(
    monkeypatch, category, keyword
):
    from pii_redactor import sensitive_detector

    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "thainer")
    monkeypatch.setattr(aggregate, "detect_tb", lambda *args, **kwargs: [])
    monkeypatch.setattr(sensitive_detector, "detect_sensitive", lambda text: [])
    warning = f"section26:{category}"
    sensitive_only = f"ข้อมูลสังเคราะห์ {keyword}"
    assert amphrang.detect(sensitive_only) == []
    masked = amphrang.anonymize(sensitive_only)
    assert masked.text == sensitive_only
    assert masked.mapping == {}
    assert masked.entities == []
    assert masked.warnings == [warning]
    with amphrang.Session() as session:
        masked = session.anonymize(sensitive_only)
        assert masked.text == sensitive_only
        assert masked.warnings == [warning]

    text = f"{sensitive_only} โทร 081-234-5678"
    masked = amphrang.anonymize(text)
    assert keyword in masked.text
    assert "081-234-5678" not in masked.text
    assert masked.entity_type_counts == {"PHONE": 1}
    assert masked.warnings == [warning]
    analysis = amphrang.analyze(text)
    assert [hit["category"] for hit in analysis["section26"]] == [category]
    assert all("text" not in hit for hit in analysis["section26"])
    assert "081-234-5678" not in repr(analysis)


def test_session_expiry_uses_canonical_error(monkeypatch):
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "thainer")
    with amphrang.Session(ttl_s=10) as session:
        now = [0.0]
        session._service._now = lambda: now[0]
        masked = session.anonymize("โทร 081-234-5678")
        now[0] = 11.0
        with pytest.raises(amphrang.SessionExpiredError):
            session.restore(masked.text)


def test_invalid_mapping_exception_drops_raw_inputs_and_chain(monkeypatch):
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "thainer")
    marker = "SYNTHETIC_PRIVATE_PAYLOAD"
    with pytest.raises(stateless.StatelessProcessingError) as caught:
        amphrang.restore(marker, {marker: 42})
    assert marker not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    frame = caught.value.__traceback__
    while frame is not None:
        if frame.tb_frame.f_code.co_filename == amphrang.__file__:
            assert frame.tb_frame.f_locals == {}
        frame = frame.tb_next
