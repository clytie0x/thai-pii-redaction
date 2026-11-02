"""Run the existing synthetic Bruno collection against an owned loopback SDK."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import site
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "packages/amphrang"
IS_WINDOWS = sys.platform == "win32"


class CheckFailed(Exception):
    def __init__(self, code, *, request=None, status=None):
        super().__init__(code)
        self.request = request
        self.status = status if type(status) is int and 100 <= status <= 599 else None


@contextmanager
def controlled_interrupts(code):
    previous = {}

    def interrupted(_number, _frame):
        raise CheckFailed(code)

    try:
        for number in (signal.SIGINT, signal.SIGTERM):
            previous[number] = signal.signal(number, interrupted)
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


@contextmanager
def defer_start_interrupts():
    previous, pending = {}, []

    def defer(_number, _frame):
        pending.append(True)

    try:
        for number in (signal.SIGINT, signal.SIGTERM):
            previous[number] = signal.signal(number, defer)
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
    if pending:
        raise CheckFailed("collection_interrupted")


def runtime_identity():
    def normalize(path):
        return os.path.normcase(os.path.realpath(path)) if path else None

    origins = {}
    for name in ("amphrang", "fastapi", "psutil"):
        spec = importlib.util.find_spec(name)
        origins[name] = normalize(spec.origin) if spec else None
    return {
        "prefix": normalize(sys.prefix),
        "executable": normalize(sys.executable),
        "site_packages": [normalize(p) for p in site.getsitepackages()],
        "origins": origins,
        "launcher_cleared": "__PYVENV_LAUNCHER__" not in os.environ,
    }


def launch_plan(environment, cwd):
    environment = dict(environment)
    executable = sys.executable
    if not IS_WINDOWS:
        return executable, environment
    base = getattr(sys, "_base_executable", None)
    if sys.implementation.name != "cpython" or not base or not Path(base).is_file():
        raise CheckFailed("test_interpreter_unqualified")
    if os.path.normcase(os.path.realpath(executable)) == os.path.normcase(os.path.realpath(base)):
        return executable, environment
    # CPython multiprocessing uses this to skip the extra venv redirector.
    environment["__PYVENV_LAUNCHER__"] = executable
    expected = runtime_identity()
    if not all(expected["origins"].values()):
        raise CheckFailed("test_dependency_missing")
    code = (
        "import json,runpy; ns=runpy.run_path("
        + repr(str(Path(__file__).resolve()))
        + ",run_name='sdk_identity'); print(json.dumps(ns['runtime_identity']()))"
    )
    completed = subprocess.run(
        [base, "-c", code],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    actual = None
    try:
        actual = json.loads(completed.stdout)
    except ValueError:
        pass
    if completed.returncode or actual != expected:
        raise CheckFailed("test_interpreter_identity_mismatch")
    return base, environment


def child_environment(source):
    allowed = {
        "PATH",
        "PATHEXT",
        "SystemRoot",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "OS",
        "TEMP",
        "TMP",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
        "XDG_DATA_HOME",
        "PYTHAINLP_DATA",
        "LANG",
        "LC_ALL",
    }
    return {
        **{key: value for key, value in source.items() if key in allowed},
        "PYTHONUTF8": "1",
        "AMPHRANG_NER_ENGINE": "thainer",
        "PYTHAINLP_OFFLINE": "1",
        "CI": "true",
    }


def validate_report(path, expected):
    report = None
    try:
        if path.stat().st_size <= 4 * 1024 * 1024:
            report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if not isinstance(report, list) or len(report) != 1 or not isinstance(report[0], dict):
        raise CheckFailed("collection_report_invalid")
    summary, results = report[0].get("summary"), report[0].get("results")
    if not isinstance(summary, dict) or not isinstance(results, list) or not expected:
        raise CheckFailed("collection_report_invalid")
    if len(results) != len(expected):
        raise CheckFailed("collection_report_incomplete")
    statuses, assertions, tests = {}, 0, 0
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get("test"), dict):
            raise CheckFailed("collection_report_invalid")
        filename = result["test"].get("filename")
        if not isinstance(filename, str):
            raise CheckFailed("collection_report_invalid")
        filename = PurePosixPath(filename.replace("\\", "/")).name
        if filename not in expected or filename in statuses:
            raise CheckFailed("collection_report_incomplete")
        response = result.get("response")
        if (
            result.get("status") != "pass"
            or result.get("error") not in (None, "")
            or not isinstance(response, dict)
            or type(response.get("status")) is not int
            or response["status"] != 200
        ):
            raise CheckFailed(
                "collection_request_failed",
                request=filename,
                status=response.get("status") if isinstance(response, dict) else None,
            )
        for item in (result.get("request"), response):
            if not isinstance(item, dict) or item.get("headers") or item.get("data"):
                raise CheckFailed("collection_report_not_minimized")
        for group in (
            "assertionResults",
            "testResults",
            "preRequestTestResults",
            "postResponseTestResults",
        ):
            entries = result.get(group, [])
            if not isinstance(entries, list) or (group == "assertionResults" and not entries):
                raise CheckFailed("collection_assertions_missing")
            required = expected[filename].get(
                "assertions"
                if group == "assertionResults"
                else "script_tests"
                if group == "testResults"
                else group,
                0,
            )
            if len(entries) != required:
                raise CheckFailed("collection_checks_incomplete")
            if any(not isinstance(e, dict) or e.get("status") != "pass" for e in entries):
                raise CheckFailed("collection_assertion_failed", request=filename)
            if group == "assertionResults":
                assertions += len(entries)
            elif group == "testResults":
                tests += len(entries)
        statuses[filename] = response["status"]
    counts = {
        "totalRequests": len(expected),
        "passedRequests": len(expected),
        "failedRequests": 0,
        "errorRequests": 0,
        "skippedRequests": 0,
        "totalAssertions": assertions,
        "passedAssertions": assertions,
        "failedAssertions": 0,
        "totalTests": tests,
        "passedTests": tests,
        "failedTests": 0,
    }
    if any(
        type(summary.get(key)) is not int or summary[key] != value for key, value in counts.items()
    ):
        raise CheckFailed("collection_summary_invalid")
    if any(key.startswith("failed") and value != 0 for key, value in summary.items()):
        raise CheckFailed("collection_assertion_failed")
    return {
        "requests": len(statuses),
        "assertions": assertions,
        "script_tests": tests,
        "statuses": statuses,
    }


def collection_contract(collection=SDK / "bruno", contract=ROOT / "config/sdk-api-collection.json"):
    metadata = json.loads(contract.read_text(encoding="utf-8"))
    expected = metadata["requests"]
    if metadata.get("schema") != 1 or set(expected) != {p.name for p in collection.glob("*.bru")}:
        raise CheckFailed("collection_source_mismatch")
    for name, checks in expected.items():
        if (
            Path(name).name != name
            or not checks.get("assertions")
            or hashlib.sha256((collection / name).read_bytes()).hexdigest() != checks["sha256"]
        ):
            raise CheckFailed("collection_source_mismatch")
    return expected


class OwnedServer:
    def __init__(self, environment, cwd):
        import psutil

        self.psutil = psutil
        self.environment, self.cwd = dict(environment), cwd
        self.process, self.root, self.listener_pid = None, None, None
        self.known, self.spawn_attempted = set(), False
        self.observation_failed = False
        with socket.socket() as reserved:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                reserved.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            reserved.bind(("127.0.0.1", 0))
            self.port = reserved.getsockname()[1]

    def start(self):
        if self.spawn_attempted:
            raise CheckFailed("owned_server_already_started")
        executable, environment = launch_plan(self.environment, self.cwd)
        with defer_start_interrupts():
            self._spawn(executable, environment)

    def _spawn(self, executable, environment):
        self.spawn_attempted = True
        self.observation_failed = True
        self.process = subprocess.Popen(
            [
                executable,
                "-m",
                "amphrang.cli",
                "serve",
                "--no-browser",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
            ],
            cwd=self.cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        candidate = None
        try:
            candidate = self.psutil.Process(self.process.pid)
        except self.psutil.Error:
            pass
        live = self.process.poll() is None
        self.root = candidate if live else None
        self.observation_failed = live and candidate is None
        self.known = {self.root} if self.root else set()

    def observe(self):
        if self.process is None or not self.root or self.process.poll() is not None:
            return
        try:
            if not self.root.is_running():
                return
            candidates = self.root.children(recursive=True)
            if self.process.poll() is not None:
                return
            parents = {p.pid: p for p in self.known if p.is_running()}
            while candidates:
                pending = []
                for candidate in candidates:
                    parent = parents.get(candidate.ppid())
                    if parent and candidate.create_time() >= parent.create_time():
                        self.known.add(candidate)
                        parents[candidate.pid] = candidate
                    else:
                        pending.append(candidate)
                if len(pending) == len(candidates):
                    break
                candidates = pending
        except self.psutil.Error:
            self.observation_failed = True

    def owns_listener(self):
        if self.process is None or self.process.poll() is not None:
            return False
        self.observe()
        for process in self.known:
            try:
                if process.is_running() and any(
                    c.laddr
                    and c.laddr.ip == "127.0.0.1"
                    and c.laddr.port == self.port
                    and not c.raddr
                    and c.status in {self.psutil.CONN_LISTEN, self.psutil.CONN_NONE}
                    for c in process.net_connections(kind="tcp")
                ):
                    self.listener_pid = process.pid
                    return True
            except (self.psutil.NoSuchProcess, self.psutil.AccessDenied):
                pass
        return False

    def close(self):
        if self.process is None:
            return not self.spawn_attempted
        self.observe()
        children = [p for p in self.known if p.pid != self.process.pid]
        for process in children:
            try:
                if process.is_running():
                    process.terminate()
            except self.psutil.Error:
                pass
        # Keep the original Popen handle for root signals and reaping.
        try:
            if self.process.poll() is None:
                self.process.terminate()
        except OSError:
            pass
        try:
            self.process.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            try:
                if self.process.poll() is None:
                    self.process.kill()
                self.process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                pass
        try:
            _, alive = self.psutil.wait_procs(children, timeout=3)
        except self.psutil.Error:
            alive = children
        for process in alive:
            try:
                if process.is_running():
                    process.kill()
            except self.psutil.Error:
                pass
        try:
            _, alive = self.psutil.wait_procs(alive, timeout=3)
        except self.psutil.Error:
            pass
        return (
            self.process.poll() is not None
            and not alive
            and not getattr(self, "observation_failed", False)
        )


def wait_ready(server):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if server.process.poll() is not None:
            raise CheckFailed("owned_server_exited")
        if server.owns_listener():
            try:
                with opener.open(
                    f"http://127.0.0.1:{server.port}/api/health", timeout=1
                ) as response:
                    health = json.loads(response.read(65537))
                if (
                    health.get("status") == "ok"
                    and health.get("contract_version") == 2
                    and health.get("capabilities", {}).get("api_key_required") is False
                    and server.owns_listener()
                ):
                    return
            except (OSError, ValueError):
                pass
        time.sleep(0.1)
    raise CheckFailed("owned_server_not_ready")


def run_collection(node, cli, report):
    environment = child_environment(os.environ)
    collection = SDK / "bruno"
    expected = collection_contract(collection)
    if not expected or not cli.is_file():
        raise CheckFailed("collection_tool_missing")
    report.parent.mkdir(parents=True, exist_ok=True)
    private = Path(tempfile.mkdtemp(prefix=".sdk-bruno-", dir=report.parent)).resolve()
    identity = private.stat().st_ino
    assert private.parent == report.parent.resolve()
    result = _run_private(node, cli, collection, expected, environment, private)
    if private.resolve() != private or private.stat().st_ino != identity:
        raise CheckFailed("private_workspace_identity_changed")
    if result["owned_server_stopped"]:
        shutil.rmtree(private)
    else:
        (private / "results.json").unlink(missing_ok=True)
        result["private_workspace"] = private.name
    return result


def _run_private(node, cli, collection, expected, environment, private):
    server, result, failure = None, {}, None
    try:
        server = OwnedServer(environment, private)
        server.start()
        wait_ready(server)
        raw_report = private / "results.json"
        completed = subprocess.run(
            [
                node,
                str(cli.resolve()),
                "run",
                "--env",
                "local",
                "--env-var",
                f"base_url=http://127.0.0.1:{server.port}",
                "--reporter-json",
                str(raw_report),
                "--reporter-skip-all-headers",
                "--reporter-skip-body",
            ],
            cwd=collection,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
        if completed.returncode != 0 and not raw_report.exists():
            raise CheckFailed("collection_command_failed")
        result = validate_report(raw_report, expected)
        if completed.returncode != 0:
            raise CheckFailed("collection_command_failed")
        if not server.owns_listener():
            raise CheckFailed("owned_server_lost")
        if server.listener_pid != server.process.pid:
            raise CheckFailed("unexpected_server_launcher")
        result["listener_is_root"] = True
    except CheckFailed as error:
        failure = str(error)
        if error.request in expected:
            result["failed_request"] = error.request
            result["failed_http_status"] = error.status
    except Exception:
        failure = "collection_execution_failed"
    finally:
        try:
            clean = server.close() if server else True
        except Exception:
            clean = False
    return {
        **result,
        "passed": failure is None and clean,
        "failure": failure,
        "owned_server_stopped": clean,
        "limits": "Synthetic loopback SDK and fake-provider collection; not live-provider, Docker, CI or production acceptance.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default=shutil.which("node"))
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.node or args.report.exists():
        print("SDK collection needs Node and a fresh report path.", file=sys.stderr)
        return 2
    try:
        with controlled_interrupts("collection_interrupted"):
            result = run_collection(args.node, args.cli, args.report)
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(result, output, indent=2)
            output.write("\n")
    except Exception:
        print("SDK collection setup failed; details and values suppressed.", file=sys.stderr)
        return 1
    print(
        "Owned SDK collection passed."
        if result["passed"]
        else "SDK collection failed; see the minimized report."
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
