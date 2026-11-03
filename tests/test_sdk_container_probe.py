"""The real image probe must test keyed masking/restoration and both auth denials."""

import io
import json
import urllib.error

import pytest

from scripts import probe_sdk_container as probe

PHONE = "081-234-5678"


class Response:
    status = 200

    def __init__(self, data):
        self.data = json.dumps(data).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def read(self, _limit):
        return self.data


class Service:
    def __init__(self, failure=None):
        self.failure = failure

    def open(self, request, timeout):
        url = request.full_url
        if url.endswith("/api/health"):
            return Response(
                {"status": "ok", "contract_version": 2, "capabilities": {"api_key_required": True}}
            )
        if request.get_header("X-amphrang-contract-version") != "2":
            raise urllib.error.HTTPError(url, 400, "contract", {}, io.BytesIO(b"private-error"))
        key = request.get_header("X-amphrang-key")
        if key != "synthetic-key":
            if (key is None and self.failure == "missing_key") or (
                key is not None and self.failure == "wrong_key"
            ):
                return Response({"status": "ok"})
            raise urllib.error.HTTPError(url, 401, "auth", {}, io.BytesIO(b"private-error"))
        if url.endswith("/api/sanitize"):
            data = {
                "sanitized_text": "[PHONE_TOKEN]",
                "session_id": "opaque",
                "entity_type_counts": {"PHONE": 1},
                "safety": {"status": "pass", "residual_count": 0},
            }
            if self.failure == "raw_value":
                data["accidental"] = PHONE
            if self.failure == "mapping":
                data["mapping"] = {"value": "unrelated"}
            return Response(data)
        return Response(
            {
                "status": "ok",
                "restored_text": "wrong"
                if self.failure == "restore"
                else "Synthetic contact: " + PHONE,
            }
        )


def test_probe_checks_the_actual_contract_and_projects_no_text(monkeypatch):
    monkeypatch.setattr(probe.urllib.request, "build_opener", lambda *_args: Service())
    result = probe.probe(8000, "synthetic-key")
    assert result == probe.EXPECTED
    assert PHONE not in json.dumps(result) and "synthetic-key" not in json.dumps(result)


@pytest.mark.parametrize("failure", ["missing_key", "wrong_key", "raw_value", "mapping", "restore"])
def test_probe_cannot_pass_on_auth_or_privacy_failure(monkeypatch, failure):
    monkeypatch.setattr(probe.urllib.request, "build_opener", lambda *_args: Service(failure))
    with pytest.raises(probe.ProbeFailed) as error:
        probe.probe(8000, "synthetic-key")
    assert "private-error" not in str(error.value)
    assert error.value.__context__ is None
