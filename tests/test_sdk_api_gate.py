"""The API collection gate must reject partial/HTTP failures and retain no bodies."""

import copy
import json
import signal
from types import SimpleNamespace

import pytest

from scripts import run_sdk_api_collection as gate
from scripts.run_sdk_api_collection import CheckFailed, child_environment, validate_report


def good_report():
    return [
        {
            "iterationIndex": 0,
            "summary": {
                "totalRequests": 1,
                "passedRequests": 1,
                "failedRequests": 0,
                "errorRequests": 0,
                "skippedRequests": 0,
                "totalAssertions": 1,
                "passedAssertions": 1,
                "failedAssertions": 0,
                "totalTests": 0,
                "passedTests": 0,
                "failedTests": 0,
            },
            "results": [
                {
                    "test": {"filename": "Health.bru"},
                    "status": "pass",
                    "request": {"headers": {}},
                    "response": {"status": 200, "headers": {}},
                    "assertionResults": [{"status": "pass", "rhsExpr": "private-marker"}],
                    "testResults": [],
                    "preRequestTestResults": [],
                    "postResponseTestResults": [],
                }
            ],
        }
    ]


def validate(tmp_path, value, expected=None):
    file = tmp_path / "private-report.json"
    file.write_text(json.dumps(value), encoding="utf-8")
    return validate_report(file, expected or {"Health.bru": {"assertions": 1, "script_tests": 0}})


def test_valid_report_projects_only_counts_and_fixed_request_names(tmp_path):
    summary = validate(tmp_path, good_report())
    assert summary["requests"] == 1 and summary["assertions"] == 1
    assert summary["statuses"] == {"Health.bru": 200}
    assert "private-marker" not in json.dumps(summary)


def test_actual_collection_contract_pins_all_committed_checks():
    expected = gate.collection_contract()
    assert len(expected) == 8
    assert sum(item["assertions"] for item in expected.values()) == 9
    assert sum(item["script_tests"] for item in expected.values()) == 4


def test_failed_request_diagnostics_do_not_include_error_body(tmp_path):
    report = good_report()
    report[0]["results"][0]["response"]["status"] = 500
    report[0]["results"][0]["error"] = "private-marker"
    with pytest.raises(CheckFailed) as error:
        validate(tmp_path, report)
    assert error.value.request == "Health.bru" and error.value.status == 500
    assert "private-marker" not in str(error.value)


@pytest.mark.parametrize(
    "failure",
    [
        "http_error",
        "assertion",
        "script",
        "error",
        "skipped",
        "duplicate",
        "missing",
        "request_body",
        "response_body",
        "headers",
        "summary",
        "empty_assertions",
    ],
)
def test_partial_or_private_report_cannot_pass(tmp_path, failure):
    report = copy.deepcopy(good_report())
    result = report[0]["results"][0]
    if failure == "http_error":
        result["response"]["status"] = 500
    elif failure == "assertion":
        result["assertionResults"][0]["status"] = "fail"
    elif failure == "script":
        result["testResults"] = [{"status": "fail", "error": "private-marker"}]
    elif failure == "error":
        result["error"] = "private-marker"
    elif failure == "skipped":
        report[0]["summary"]["skippedRequests"] = 1
    elif failure == "duplicate":
        report[0]["results"].append(copy.deepcopy(result))
    elif failure == "missing":
        result["test"]["filename"] = "Other.bru"
    elif failure in {"request_body", "response_body"}:
        result[failure.split("_")[0]]["data"] = "private-marker"
    elif failure == "headers":
        result["response"]["headers"] = {"private": "private-marker"}
    elif failure == "summary":
        report[0]["summary"]["passedRequests"] = 0
    else:
        result["assertionResults"] = []
    with pytest.raises(CheckFailed) as error:
        validate(tmp_path, report)
    assert "private-marker" not in str(error.value)


def test_invalid_json_has_no_raw_exception_context(tmp_path):
    file = tmp_path / "bad.json"
    file.write_text("private-marker invalid JSON", encoding="utf-8")
    with pytest.raises(CheckFailed) as error:
        validate_report(file, {"Health.bru"})
    assert error.value.__context__ is None
    assert "private-marker" not in str(error.value)


@pytest.mark.parametrize(
    "required", [{"assertions": 2, "script_tests": 0}, {"assertions": 1, "script_tests": 1}]
)
def test_committed_checks_cannot_be_dropped_even_with_a_consistent_summary(tmp_path, required):
    with pytest.raises(CheckFailed):
        validate(tmp_path, good_report(), {"Health.bru": required})


def test_child_environment_keeps_tools_but_no_operator_credentials():
    result = child_environment(
        {
            "PATH": "tools",
            "HOME": "model-cache",
            "SystemRoot": "Windows",
            "AMPHRANG_API_KEY": "private",
            "AMPHRANG_TOKEN": "private",
            "AIFORTHAI_API_KEY": "private",
            "GITHUB_TOKEN": "private",
            "TOKENMIND_API_KEY": "private",
            "HTTPS_PROXY": "private",
        }
    )
    assert result["PATH"] == "tools" and result["HOME"] == "model-cache"
    assert "private" not in result.values()
    assert result["AMPHRANG_NER_ENGINE"] == "thainer" and result["PYTHAINLP_OFFLINE"] == "1"


def test_cli_interrupts_use_fixed_errors_and_restore_signal_handlers(monkeypatch):
    handlers = {signal.SIGINT: object(), signal.SIGTERM: object()}
    previous = dict(handlers)

    def install(number, handler):
        old = handlers[number]
        handlers[number] = handler
        return old

    monkeypatch.setattr(signal, "signal", install)
    with pytest.raises(CheckFailed, match="synthetic_interrupted"):
        with gate.controlled_interrupts("synthetic_interrupted"):
            handlers[signal.SIGTERM](signal.SIGTERM, None)
    assert handlers == previous


@pytest.mark.parametrize("failure", [None, "command", "report", "cleanup"])
def test_server_uses_fresh_private_cwd_and_is_stopped_even_on_failure(
    tmp_path, monkeypatch, failure
):
    observed = {}

    class FakeServer:
        port = 12345
        listener_pid = 1
        process = SimpleNamespace(pid=1)

        def __init__(self, environment, cwd):
            assert cwd.parent == tmp_path and cwd != gate.SDK and not list(cwd.iterdir())
            observed["directory"] = cwd
            (cwd / "logs").mkdir()

        def owns_listener(self):
            return True

        def start(self):
            pass

        def close(self):
            observed["stopped"] = True
            return failure != "cleanup"

    def report(path, expected):
        assert path.parent == observed["directory"] and expected
        if failure == "report":
            raise CheckFailed("collection_report_invalid")
        return {"requests": 8, "assertions": 8, "statuses": {}}

    cli = tmp_path / "bru.js"
    cli.touch()
    monkeypatch.setattr(gate, "OwnedServer", FakeServer)
    monkeypatch.setattr(gate, "wait_ready", lambda _: None)
    monkeypatch.setattr(gate, "validate_report", report)
    monkeypatch.setattr(
        gate.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1 if failure == "command" else 0),
    )
    result = gate.run_collection("node", cli, tmp_path / "summary.json")
    assert result["passed"] is (failure is None)
    assert result["owned_server_stopped"] is (failure != "cleanup")
    assert observed["stopped"]
    assert observed["directory"].exists() is (failure == "cleanup")
    if failure == "cleanup":
        assert result["private_workspace"] == observed["directory"].name
