"""Real SDK reuse and sessions stay local even after root TNER is warm."""

import pytest
from pii_redactor import stateless
from pii_redactor.config import CoreConfig
from pii_redactor.detectors import tb_detector, tner_client

import amphrang


@pytest.mark.parametrize("mode", ["token", "surrogate"])
@pytest.mark.parametrize("flow", ["prior_mapping", "session"])
def test_sdk_reuse_forwards_its_snapshot_through_the_canonical_anonymizer(monkeypatch, mode, flow):
    local, remote, captured = [], [], []

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

    monkeypatch.setenv("AMPHRANG_NER_ENGINE", "thainer")
    monkeypatch.setenv("AIGUARD_NER_ENGINE", "tner")
    monkeypatch.setenv("AIFORTHAI_API_KEY", "synthetic-root-credential")
    monkeypatch.setattr(tner_client, "TnerEngine", Remote)
    monkeypatch.setitem(tb_detector._ner_cache, "thainer", Local())
    tb_detector._get_ner(config=CoreConfig.from_env())
    remote.clear()
    original = stateless.anonymize

    def anonymize(*args, **kwargs):
        captured.append(kwargs.get("config"))
        return original(*args, **kwargs)

    monkeypatch.setattr(stateless, "anonymize", anonymize)
    text = "โทร 081-234-5678"
    if flow == "prior_mapping":
        first = amphrang.anonymize(text, mode=mode, salt="synthetic")
        second = amphrang.anonymize(text, mode=mode, salt="synthetic", prior_mapping=first.mapping)
        assert amphrang.restore(second.text, second.mapping).text == text
    else:
        with amphrang.Session(mode=mode) as session:
            first = session.anonymize(text)
            second = session.anonymize(text)
            assert session.restore(second.text).text == text
            assert captured and all(snapshot is session._service._config for snapshot in captured)
    assert "081-234-5678" not in second.text
    assert captured and all(snapshot == CoreConfig(allow_remote=False) for snapshot in captured)
    assert local and remote == []
