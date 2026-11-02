"""Candidate reuse must use the same explicit profile as detection and release."""

import importlib

import pytest

from pii_redactor.config import CoreConfig
from pii_redactor.detectors import tb_detector, tner_client
from pii_redactor.models import Entity, EntityRegistry
from pii_redactor.session_vault import SessionVault
from pii_redactor.stateless import sanitize_stateless

anon = importlib.import_module("pii_redactor.anonymizer.anonymizer")


@pytest.fixture
def warm_remote_and_local(monkeypatch):
    local, remote = [], []

    class Local:
        def tag(self, text):
            local.append(text)
            return [(text, "O")]

    class Remote:
        def __init__(self, *, api_key):
            remote.append("constructed")

        def tag(self, text):
            remote.append("tagged")
            return [(text, "O")]

    monkeypatch.setenv("AIGUARD_NER_ENGINE", "tner")
    monkeypatch.setenv("AIFORTHAI_API_KEY", "synthetic-root-credential")
    monkeypatch.setattr(tner_client, "TnerEngine", Remote)
    monkeypatch.setitem(tb_detector._ner_cache, "thainer", Local())
    tb_detector._get_ner(config=CoreConfig.from_env())
    assert remote == ["constructed"]
    remote.clear()
    return local, remote


@pytest.mark.parametrize("mode", ["token", "surrogate"])
def test_seeded_reuse_scans_share_the_explicit_local_snapshot(
    monkeypatch, warm_remote_and_local, mode
):
    local, remote = warm_remote_and_local
    config = CoreConfig(allow_remote=False)
    scans = []
    for name in ("scan_outbound_leaks", "scan_residual_signals"):
        original = getattr(anon, name)

        def scan(text, context, *, config=None, original=original):
            scans.append((text, config))
            return original(text, context, config=config)

        monkeypatch.setattr(anon, name, scan)
    text = "Synthetic contact: 081-234-5678"
    first = sanitize_stateless(text, mode=mode, salt="synthetic", config=config)
    previous = next(iter(first.mapping))
    second = sanitize_stateless(
        text, mode=mode, salt="synthetic", prior_mapping=first.mapping, config=config
    )
    assert second.mapping and "081-234-5678" not in second.sanitized_text
    assert scans and all(snapshot is config for _, snapshot in scans)
    assert previous in local and remote == []


@pytest.mark.parametrize("mode", ["token", "surrogate"])
def test_unsafe_seed_is_still_rejected_by_the_local_candidate_scan(warm_remote_and_local, mode):
    local, remote = warm_remote_and_local
    unsafe = "081-999-0000"
    result = sanitize_stateless(
        "โทร 081-234-5678",
        mode=mode,
        salt="synthetic",
        prior_mapping={unsafe: "081-234-5678"},
        config=CoreConfig(allow_remote=False),
    )
    assert unsafe not in result.sanitized_text
    assert unsafe in local and remote == []


def test_direct_anonymizer_resolves_root_default_once_and_passes_that_object(monkeypatch):
    config = CoreConfig(engine="thainer")
    resolutions, scans = [], []
    monkeypatch.setattr(
        anon, "resolve_config", lambda value=None: resolutions.append(value) or config
    )
    monkeypatch.setattr(
        anon, "scan_outbound_leaks", lambda text, context, *, config: scans.append(config) or []
    )
    monkeypatch.setattr(
        anon, "scan_residual_signals", lambda text, context, *, config: scans.append(config) or []
    )
    text = "a@b.co"
    entity = Entity("synthetic", "FP", "EMAIL", (0, len(text)), 1.0, text)
    vault = SessionVault()
    vault.seed("[อีเมล_1]", text)
    result = anon.anonymize(
        text, EntityRegistry([entity], 1, 0), vault, salt="synthetic", mode="token"
    )
    assert result.text == "[อีเมล_1]"
    assert resolutions == [None]
    assert scans and all(snapshot is config for snapshot in scans)


def test_pipeline_forwards_one_profile_through_every_protection_step(
    monkeypatch, warm_remote_and_local
):
    from pii_redactor import ai_client, output_validator, pipeline
    from pii_redactor.detectors import aggregate

    config = CoreConfig(allow_remote=False)
    captures = []
    for module, name in (
        (aggregate, "detect_all"),
        (anon, "anonymize"),
        (ai_client, "send_to_ai"),
        (output_validator, "validate_output"),
    ):
        original = getattr(module, name)

        def operation(*args, config=None, original=original, name=name, **kwargs):
            captures.append((name, config))
            return original(*args, config=config, **kwargs)

        monkeypatch.setattr(module, name, operation)
    result = pipeline.run_pipeline(text="โทร 081-234-5678", salt="synthetic", config=config)
    assert result.reverse_result.text == "โทร 081-234-5678"
    assert {name for name, _ in captures} == {
        "detect_all",
        "anonymize",
        "send_to_ai",
        "validate_output",
    }
    assert all(snapshot is config for _, snapshot in captures)
    assert warm_remote_and_local[0] and warm_remote_and_local[1] == []


def test_direct_candidate_failure_clears_anonymizer_profile_frames(monkeypatch):
    config = CoreConfig(finetuned_model_dir="synthetic-private-model", allow_remote=False)
    vault = SessionVault()
    vault.seed("[อีเมล_1]", "a@b.co")
    registry = EntityRegistry([Entity("synthetic", "FP", "EMAIL", (0, 6), 1.0, "a@b.co")], 1, 0)

    def fail(text, context, *, config):
        raise RuntimeError("synthetic candidate failure")

    monkeypatch.setattr(anon, "scan_outbound_leaks", fail)
    with pytest.raises(RuntimeError) as caught:
        anon.anonymize("a@b.co", registry, vault, salt="synthetic", mode="token", config=config)
    trace = caught.value.__traceback__
    frames = []
    while trace:
        if trace.tb_frame.f_code.co_filename == anon.__file__:
            frames.append(trace.tb_frame.f_locals)
        trace = trace.tb_next
    assert frames and all(frame == {} for frame in frames)
