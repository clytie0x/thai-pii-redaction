"""Synthetic configuration isolation checks for the shared core."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import pytest

from pii_redactor.config import AuditConfig, CoreConfig, resolve_config


def test_namespace_snapshot_is_immutable_and_does_not_read_root(monkeypatch):
    monkeypatch.setenv("AIGUARD_NER_ENGINE", "tner")
    monkeypatch.setenv("AIGUARD_FINETUNED_MODEL_DIR", "private-root-model")
    monkeypatch.setenv("AIFORTHAI_API_KEY", "synthetic-secret")
    monkeypatch.delenv("AMPHRANG_NER_ENGINE", raising=False)
    monkeypatch.delenv("AMPHRANG_FINETUNED_MODEL_DIR", raising=False)
    sdk = CoreConfig.from_env(prefix="AMPHRANG", allow_remote=False)
    assert sdk == CoreConfig(engine="thainer", allow_remote=False)
    root = resolve_config()
    monkeypatch.setenv("AIGUARD_NER_ENGINE", "union")
    assert root.engine == "tner"
    assert root.tner_api_key == "synthetic-secret"
    assert "synthetic-secret" not in repr(root)
    assert "private-root-model" not in repr(root)
    assert resolve_config(sdk) is sdk
    with pytest.raises(FrozenInstanceError):
        sdk.engine = "union"


def test_audit_prefix_is_independent(monkeypatch, tmp_path, capsys):
    from pii_redactor.audit import write_process_log, write_security_log

    monkeypatch.setenv("AIGUARD_AUDIT_STDOUT", "1")
    monkeypatch.setenv("AMPHRANG_AUDIT_STDOUT", "0")
    config = AuditConfig.from_env(prefix="AMPHRANG")
    path = write_process_log(
        "synthetic", "scan", 0, "pass", [], 0, output_dir=str(tmp_path), audit_config=config
    )
    assert path.exists()
    assert capsys.readouterr().out == ""
    monkeypatch.setenv("AIGUARD_AUDIT_STDOUT", "0")
    write_process_log(
        "stdout",
        "scan",
        0,
        "pass",
        [],
        0,
        output_dir=str(tmp_path),
        audit_config=AuditConfig(stdout=True),
    )
    assert '"step": "scan"' in capsys.readouterr().out
    assert not (tmp_path / "audit_stdout_process.jsonl").exists()
    security_path = write_security_log(
        "security",
        "layer1",
        "clean",
        0,
        0,
        None,
        False,
        output_dir=str(tmp_path),
        audit_config=AuditConfig(stdout=True),
    )
    assert '"type": "security"' in capsys.readouterr().out
    assert not security_path.exists()
    with pytest.raises(FrozenInstanceError):
        config.stdout = True


def test_offline_snapshot_does_not_read_provider_credential(monkeypatch):
    from pii_redactor import config as config_module

    class OfflineEnvironment(dict):
        def get(self, name, default=None):
            assert name != "AIFORTHAI_API_KEY"
            return super().get(name, default)

    environment = OfflineEnvironment(AIFORTHAI_API_KEY="synthetic-provider-secret")
    monkeypatch.setattr(config_module.os, "environ", environment)
    config = CoreConfig.from_env()
    assert config.engine == "thainer"
    assert config.tner_api_key == ""
    assert "synthetic-provider-secret" not in repr(config)


def test_local_cache_is_thread_safe_and_profiles_are_independent(monkeypatch):
    from pii_redactor.detectors import tb_detector as tb

    made = []
    monkeypatch.setattr(tb, "_ner_cache", {})
    monkeypatch.setattr(tb, "NER", lambda *, engine: made.append(engine) or object())
    configs = [CoreConfig(), CoreConfig(engine="wangchanberta")]
    monkeypatch.setitem(tb._ENGINE_CONFIG["wangchanberta"], "requires", None)
    with ThreadPoolExecutor(max_workers=8) as pool:
        loaded = list(
            pool.map(
                lambda i: tb._load_ner(configs[i % 2].engine, config=configs[i % 2]), range(40)
            )
        )
    assert made.count("thainer") == made.count("thainer-v2") == 1
    assert all(item is loaded[i % 2] for i, item in enumerate(loaded))


def test_remote_rejected_before_warm_cache(monkeypatch):
    from pii_redactor.detectors import tb_detector as tb

    monkeypatch.setattr(tb, "_ner_cache", {"tner": object()})
    with pytest.raises(tb.NEREngineUnavailableError):
        tb._load_ner("tner", config=CoreConfig(engine="tner", allow_remote=False))


def test_finetuned_cache_uses_directory_and_artifact(monkeypatch, tmp_path):
    from pii_redactor.detectors import finetuned_engine
    from pii_redactor.detectors import tb_detector as tb

    class FakeEngine:
        def __init__(self, model_dir):
            made.append(model_dir)
            self.thresholds = {}

        def spans(self, text):
            return []

    made = []
    monkeypatch.setattr(tb, "_finetuned_cache", {})
    monkeypatch.setattr(finetuned_engine, "FinetunedEngine", FakeEngine)
    dirs = [tmp_path / "one", tmp_path / "two"]
    for directory in dirs:
        directory.mkdir()
    configs = [CoreConfig(engine="finetuned", finetuned_model_dir=str(d)) for d in dirs]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(
            pool.map(
                lambda i: tb._detect_tb_finetuned("plain text", config=configs[i % 2]), range(30)
            )
        )
    assert sorted(made) == sorted(str(d.resolve()) for d in dirs)
    (dirs[0] / "thresholds.json").write_text('{"PERSON":0.9}', encoding="utf-8")
    tb._detect_tb_finetuned("plain text", config=configs[0])
    assert len(made) == 3
    monkeypatch.setenv("AIGUARD_FINETUNED_MODEL_DIR", str(dirs[0]))
    with pytest.raises(finetuned_engine.FinetunedEngineUnavailableError):
        tb._detect_tb_finetuned(
            "plain text", config=CoreConfig(engine="finetuned", allow_remote=False)
        )


def test_remote_clients_never_share_credentials(monkeypatch):
    from pii_redactor.detectors import tb_detector as tb
    from pii_redactor.detectors import tner_client

    made = []
    monkeypatch.setattr(
        tner_client, "TnerEngine", lambda *, api_key: made.append(api_key) or object()
    )
    monkeypatch.setattr(tb, "_ner_cache", {})
    first = tb._load_ner("tner", config=CoreConfig(engine="tner", tner_api_key="synthetic-one"))
    second = tb._load_ner("tner", config=CoreConfig(engine="tner", tner_api_key="synthetic-two"))
    assert first is not second
    assert made == ["synthetic-one", "synthetic-two"]
    assert "tner" not in tb._ner_cache


def test_concurrent_profiles_leave_environment_unchanged(monkeypatch):
    import os

    from pii_redactor import leak_guard, stateless
    from pii_redactor.detectors import aggregate

    monkeypatch.setenv("AIGUARD_NER_ENGINE", "tner")
    monkeypatch.setenv("AIFORTHAI_API_KEY", "synthetic-root-secret")
    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "thainer")
    monkeypatch.setenv("SECOND_NER_ENGINE", "wangchanberta")
    configs = [
        CoreConfig.from_env(prefix=prefix, allow_remote=False) for prefix in ("AMPHRANG", "SECOND")
    ]
    before = dict(os.environ)
    seen = []

    def detect(text, *, config, **kwargs):
        seen.append((text, config))
        return []

    monkeypatch.setattr(aggregate, "detect_tb", detect)
    monkeypatch.setattr(leak_guard, "detect_tb", detect)

    def sanitize(index):
        config = configs[index % 2]
        return stateless.sanitize_stateless(
            config.engine, mode="token", salt="synthetic", config=config
        ).sanitized_text

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(sanitize, range(30)))
    assert results == [configs[index % 2].engine for index in range(30)]
    assert all(text == config.engine and config in configs for text, config in seen)
    assert dict(os.environ) == before


def test_explicit_none_model_dir_never_uses_root(monkeypatch, tmp_path):
    from pii_redactor.detectors.finetuned_engine import (
        FinetunedEngine,
        FinetunedEngineUnavailableError,
    )

    monkeypatch.setenv("AIGUARD_FINETUNED_MODEL_DIR", str(tmp_path))
    with pytest.raises(FinetunedEngineUnavailableError):
        FinetunedEngine(None)


def _record_detection(monkeypatch):
    from pii_redactor import leak_guard
    from pii_redactor.detectors import aggregate

    seen = []

    def detect(text, *, config, **kwargs):
        seen.append(config)
        monkeypatch.setenv("AIGUARD_NER_ENGINE", "tner")
        return []

    monkeypatch.setattr(aggregate, "detect_tb", detect)
    monkeypatch.setattr(leak_guard, "detect_tb", detect)
    return seen


def test_one_snapshot_through_stateless_restore_and_reports(monkeypatch):
    from pii_redactor import report, stateless

    monkeypatch.setenv("AIGUARD_NER_ENGINE", "thainer")
    seen = _record_detection(monkeypatch)
    result = stateless.sanitize_stateless("plain text", mode="token", salt="synthetic")
    assert result.sanitized_text == "plain text"
    assert len(seen) >= 2
    assert all(config is seen[0] and config.engine == "thainer" for config in seen)
    config = CoreConfig(engine="wangchanberta", allow_remote=False)
    seen.clear()
    stateless.restore_stateless("plain text", mapping={}, config=config)
    report.generate_report("plain text", config=config)
    report.analyze_text("plain text", config=config)
    assert len(seen) == 3
    assert all(item is config for item in seen)


def test_explicit_sanitize_and_session_keep_config(monkeypatch):
    from pii_redactor import stateless
    from pii_redactor.session_service import SessionService

    config = CoreConfig(allow_remote=False)
    seen = _record_detection(monkeypatch)
    stateless.sanitize_stateless("plain text", mode="token", salt="synthetic", config=config)
    service = SessionService(config=config)
    try:
        result = service.sanitize("plain text", mode="token")
        service.restore(result.session_id, "a new reply")
    finally:
        service.close()
    assert len(seen) >= 5
    assert all(item is config for item in seen)


def test_partial_trusted_span_rescans_with_same_config(monkeypatch):
    from pii_redactor import leak_guard
    from pii_redactor.models import Entity

    config = CoreConfig(allow_remote=False)
    seen = []
    text = "left trusted right"

    def detect(value, *, config):
        seen.append((value, config))
        if value == text:
            return [Entity("synthetic", "TB", "NAME", (0, len(text)), 0.9, text)]
        return []

    monkeypatch.setattr(leak_guard, "detect_tb", detect)
    assert (
        leak_guard.scan_outbound_leaks(
            text, leak_guard.OutboundGuardContext(frozenset({"trusted"})), config=config
        )
        == []
    )
    assert [value for value, _ in seen] == [text, "left ", " right"]
    assert all(item is config for _, item in seen)


def test_custom_scanners_keep_two_argument_protocol(monkeypatch):
    from pii_redactor import stateless
    from pii_redactor.session_vault import SessionVault

    seen = _record_detection(monkeypatch)
    calls = []

    def custom(text, vault):
        calls.append((text, vault))
        return []

    config = CoreConfig(allow_remote=False)
    vault = SessionVault()
    result = stateless.sanitize_into_vault(
        "plain text",
        vault,
        mode="token",
        salt="synthetic",
        config=config,
        scan_leaks=custom,
        scan_residual=custom,
    )
    assert result.sanitized_text == "plain text"
    assert len(calls) == 2
    assert seen == [config]


def test_replaced_module_scanner_keeps_two_argument_protocol(monkeypatch):
    from pii_redactor import leak_guard

    def custom(text, context):
        return []

    monkeypatch.setattr(leak_guard, "scan_outbound_leaks", custom)
    leak_guard.enforce_outbound_policy(
        "plain text",
        guard_context=leak_guard.OutboundGuardContext(),
        scan_leaks=custom,
        scan_residual=custom,
        config=CoreConfig(allow_remote=False),
    )


def test_ai_retries_reuse_operation_snapshot(monkeypatch):
    from pii_redactor import ai_client
    from pii_redactor.models import EntityRegistry
    from pii_redactor.session_vault import SessionVault

    monkeypatch.setenv("AIGUARD_NER_ENGINE", "thainer")
    seen = _record_detection(monkeypatch)
    calls = []

    def complete(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise ai_client.ProviderCallError(category="timeout", error_type="TimeoutError")
        return "safe reply"

    monkeypatch.setattr(ai_client, "complete_provider_call", complete)
    monkeypatch.setattr(ai_client, "_sleep", lambda duration: None)
    result = ai_client.send_to_ai(
        "plain text", EntityRegistry([], 0, 0), SessionVault(), ai_client.FakeLLMProvider()
    )
    assert result.text == "safe reply"
    assert len(seen) == 2
    assert all(item is seen[0] and item.engine == "thainer" for item in seen)


def _assert_error_drops_config(error, config):
    """Inspect retained objects, including fields hidden from repr."""
    import types
    from collections.abc import Mapping

    pending = [error]
    seen = set()
    product_frames = 0
    while pending:
        value = pending.pop()
        assert value is not config, "exception graph retains configuration"
        if isinstance(value, str):
            assert config.tner_api_key not in value
            assert config.finetuned_model_dir not in value
            continue
        if id(value) in seen:
            continue
        seen.add(id(value))
        if isinstance(value, BaseException):
            pending.extend((value.args, value.__dict__, value.__cause__, value.__context__))
            if isinstance(value, BaseExceptionGroup):
                pending.extend(value.exceptions)
            traceback = value.__traceback__
            while traceback:
                frame = traceback.tb_frame
                if frame.f_globals.get("__name__", "").startswith("pii_redactor."):
                    product_frames += 1
                    pending.append(frame.f_locals)
                traceback = traceback.tb_next
        elif isinstance(value, Mapping):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, (tuple, list, set, frozenset)):
            pending.extend(value)
        elif isinstance(value, types.FunctionType):
            if value.__module__.startswith("pii_redactor.") and value.__closure__:
                pending.extend(cell.cell_contents for cell in value.__closure__)
        elif type(value).__module__.startswith("pii_redactor."):
            pending.append(vars(value))
    assert product_frames > 0, "test must inspect a real product failure"


@pytest.mark.parametrize(
    "operation",
    [
        "sanitize_invalid",
        "sanitize_ner",
        "into_vault",
        "restore_empty",
        "detect_tb",
        "detect_all",
        "outbound_scan",
        "outbound_policy_ner",
        "outbound_policy",
        "ai_send",
        "pre_send_residual",
        "pre_send_size",
        "pre_send_timeout",
        "session_sanitize",
        "session_restore",
    ],
)
def test_public_failure_graph_drops_sensitive_configuration(monkeypatch, operation):
    from pii_redactor import ai_client, leak_guard, stateless
    from pii_redactor.detectors import tb_detector
    from pii_redactor.detectors.aggregate import detect_all
    from pii_redactor.detectors.ner_failure import NERFailureError
    from pii_redactor.models import EntityRegistry
    from pii_redactor.session_service import ModeMismatchError, SessionExpiredError, SessionService
    from pii_redactor.session_vault import SessionVault, VaultTimeoutError

    config = CoreConfig(
        engine="tner",
        allow_remote=False,
        tner_api_key="synthetic-review-credential",
        finetuned_model_dir="synthetic-review-private-model-dir",
    )
    vault = SessionVault()
    registry = EntityRegistry([], 0, 0)

    def no_leaks(text, context):
        return []

    def residual(text, context):
        return ["orphan_digits:8"]

    monkeypatch.setattr(ai_client, "scan_outbound_leaks", no_leaks)
    monkeypatch.setattr(
        ai_client,
        "scan_residual_signals",
        no_leaks if operation in {"pre_send_size", "pre_send_timeout"} else residual,
    )
    if operation == "pre_send_timeout":

        def expire():
            raise VaultTimeoutError("synthetic expiry")

        monkeypatch.setattr(vault, "check_idle", expire)
    service = SessionService(config=config)
    actions = {
        "sanitize_invalid": lambda: stateless.sanitize_stateless(
            "plain", mode="invalid", salt="s", config=config
        ),
        "sanitize_ner": lambda: stateless.sanitize_stateless(
            "ข้อความทดสอบ", mode="token", salt="s", config=config
        ),
        "into_vault": lambda: stateless.sanitize_into_vault(
            "ข้อความทดสอบ", vault, mode="token", salt="s", config=config
        ),
        "restore_empty": lambda: stateless.restore_stateless("", mapping={}, config=config),
        "detect_tb": lambda: tb_detector.detect_tb("ข้อความทดสอบ", config=config),
        "detect_all": lambda: detect_all("ข้อความทดสอบ", config=config),
        "outbound_scan": lambda: leak_guard.scan_outbound_leaks(
            "ข้อความทดสอบ", vault, config=config
        ),
        "outbound_policy_ner": lambda: leak_guard.enforce_outbound_policy(
            "ข้อความทดสอบ", guard_context=vault, config=config
        ),
        "outbound_policy": lambda: leak_guard.enforce_outbound_policy(
            "plain", guard_context=vault, scan_leaks=no_leaks, scan_residual=residual, config=config
        ),
        "ai_send": lambda: ai_client.send_to_ai(
            "plain", registry, vault, ai_client.FakeLLMProvider(), config=config
        ),
        "pre_send_residual": lambda: ai_client._validate_pre_send("plain", vault, config=config),
        "pre_send_size": lambda: ai_client._validate_pre_send("x" * 400004, vault, config=config),
        "pre_send_timeout": lambda: ai_client._validate_pre_send("plain", vault, config=config),
        "session_sanitize": lambda: service.sanitize("plain", mode="invalid"),
        "session_restore": lambda: service.restore("missing", "plain"),
    }
    expected = {
        "sanitize_invalid": ValueError,
        "sanitize_ner": NERFailureError,
        "into_vault": NERFailureError,
        "restore_empty": ValueError,
        "detect_tb": NERFailureError,
        "detect_all": NERFailureError,
        "outbound_scan": NERFailureError,
        "outbound_policy_ner": NERFailureError,
        "outbound_policy": leak_guard.OutboundPolicyError,
        "ai_send": ai_client.PreSendValidationError,
        "pre_send_residual": ai_client.PreSendValidationError,
        "pre_send_size": ai_client.PreSendValidationError,
        "pre_send_timeout": VaultTimeoutError,
        "session_sanitize": ModeMismatchError,
        "session_restore": SessionExpiredError,
    }
    try:
        with pytest.raises(expected[operation]) as caught:
            actions[operation]()
        _assert_error_drops_config(caught.value, config)
    finally:
        service.close()


def test_native_wrapped_ner_failure_is_contained_at_stateless_boundary():
    from pii_redactor.detectors.ner_failure import NERFailureError
    from pii_redactor.native_broker_context import BrokerOperationContext, activate_broker_operation
    from pii_redactor.stateless import sanitize_stateless

    config = CoreConfig(
        engine="tner",
        allow_remote=False,
        tner_api_key="synthetic-review-credential",
        finetuned_model_dir="synthetic-review-private-model-dir",
    )
    context = BrokerOperationContext(
        outer_deadline_ms=1000,
        local_detection_phases=3,
        intermediate_text_chars=1000,
        local_phase_deadline_ms=500,
        schedule_watchdog=lambda *args: None,
        terminate=lambda: None,
    )
    with activate_broker_operation(context):
        with pytest.raises(NERFailureError) as caught:
            sanitize_stateless("ข้อความทดสอบ", mode="token", salt="s", config=config)
    _assert_error_drops_config(caught.value, config)


@pytest.mark.parametrize("operation", ["sanitize", "into_vault", "restore"])
@pytest.mark.parametrize("rejection", ["cap", "phase"])
def test_native_rejection_preserves_control_type_without_configuration(operation, rejection):
    from pii_redactor import stateless
    from pii_redactor.detectors.aggregate import detect_all
    from pii_redactor.native_broker_context import (
        BrokerOperationContext,
        NativeBrokerOperationError,
        NativeBrokerPayloadTooLarge,
        activate_broker_operation,
    )
    from pii_redactor.session_vault import SessionVault

    config = CoreConfig(
        engine="tner",
        allow_remote=False,
        tner_api_key="synthetic-review-credential",
        finetuned_model_dir="synthetic-review-private-model-dir",
    )
    context = BrokerOperationContext(
        outer_deadline_ms=1000,
        local_detection_phases=1,
        intermediate_text_chars=1 if rejection == "cap" else 1000,
        local_phase_deadline_ms=500,
        schedule_watchdog=lambda *args: None,
        terminate=lambda: None,
    )
    actions = {
        "sanitize": lambda: stateless.sanitize_stateless(
            "synthetic source", mode="token", salt="s", config=config
        ),
        "into_vault": lambda: stateless.sanitize_into_vault(
            "synthetic source", SessionVault(), mode="token", salt="s", config=config
        ),
        "restore": lambda: stateless.restore_stateless(
            "synthetic source", mapping={}, config=config
        ),
    }
    with activate_broker_operation(context):
        if rejection == "phase":
            detect_all("plain", config=CoreConfig(allow_remote=False))
        with pytest.raises(
            NativeBrokerPayloadTooLarge if rejection == "cap" else NativeBrokerOperationError
        ) as caught:
            actions[operation]()
    _assert_error_drops_config(caught.value, config)


@pytest.mark.parametrize("operation", ["sanitize", "sanitize_transaction", "restore"])
@pytest.mark.parametrize("rejection", ["cap", "phase"])
def test_session_native_rejection_drops_service_graph_and_keeps_session(operation, rejection):
    from pii_redactor.detectors.aggregate import detect_all
    from pii_redactor.native_broker_context import (
        BrokerOperationContext,
        NativeBrokerOperationError,
        NativeBrokerPayloadTooLarge,
        activate_broker_operation,
    )
    from pii_redactor.session_service import SessionService

    config = CoreConfig(
        allow_remote=False,
        tner_api_key="synthetic-review-credential",
        finetuned_model_dir="synthetic-review-private-model-dir",
    )
    service = SessionService(config=config)
    previous = service.sanitize("Synthetic contact: 081-234-5678", mode="token")
    context = BrokerOperationContext(
        outer_deadline_ms=1000,
        local_detection_phases=1,
        intermediate_text_chars=1 if rejection == "cap" else 1000,
        local_phase_deadline_ms=500,
        schedule_watchdog=lambda *args: None,
        terminate=lambda: None,
    )
    actions = {
        "sanitize": lambda: service.sanitize("synthetic source", mode="token"),
        "sanitize_transaction": lambda: service.sanitize_transaction(
            "synthetic source", mode="token", finalize=lambda outcome: outcome
        ),
        "restore": lambda: service.restore(previous.session_id, "synthetic source"),
    }
    try:
        with activate_broker_operation(context):
            if rejection == "phase":
                detect_all("plain", config=CoreConfig(allow_remote=False))
            with pytest.raises(
                NativeBrokerPayloadTooLarge if rejection == "cap" else NativeBrokerOperationError
            ) as caught:
                actions[operation]()
        _assert_error_drops_config(caught.value, config)
        assert service.session_count == 1
        assert (
            "081-234-5678"
            in service.restore(previous.session_id, previous.sanitized_text).restored_text
        )
    finally:
        service.close()
