"""Owned-process cleanup continues on failures and rejects stale identities."""

import signal
import subprocess
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from scripts import run_sdk_api_collection as gate


@pytest.fixture(autouse=True)
def reserve_only_a_fake_port(monkeypatch):
    @contextmanager
    def reserved(*_args, **_kwargs):
        yield SimpleNamespace(
            setsockopt=lambda *a: None,
            bind=lambda *a: None,
            getsockname=lambda: ("127.0.0.1", 12345),
        )

    monkeypatch.setattr(gate.socket, "socket", reserved)


class ProcessError(Exception):
    pass


class Denied(ProcessError):
    pass


class Missing(ProcessError):
    pass


class Process:
    def __init__(self, pid, parent=0, deny_stop=False, deny_kill=False):
        self.pid, self.parent, self.live = pid, parent, True
        self.deny_stop, self.deny_kill = deny_stop, deny_kill
        self.descendants = []

    def is_running(self):
        return self.live

    def create_time(self):
        return self.pid

    def ppid(self):
        return self.parent

    def children(self, recursive):
        return self.descendants

    def terminate(self):
        if self.deny_stop:
            raise Denied()
        self.live = False

    def kill(self):
        if self.deny_kill:
            raise Denied()
        self.live = False


class NativeProcess:
    def __init__(self, root, ignore_terminate=False, exited=False):
        self.pid, self.root = root.pid, root
        self.ignore_terminate, self.exited = ignore_terminate, exited
        self.reaped = self.killed = self.terminated = False

    def poll(self):
        return 0 if self.exited or not self.root.live else None

    def terminate(self):
        self.terminated = True
        if not self.ignore_terminate:
            self.root.live = False

    def kill(self):
        self.killed = True
        self.root.live = False

    def wait(self, timeout):
        if self.poll() is None:
            raise subprocess.TimeoutExpired("synthetic-owned-server", timeout)
        self.reaped = True
        return 0


def module(root):
    return SimpleNamespace(
        Process=lambda _: root,
        Error=ProcessError,
        NoSuchProcess=Missing,
        AccessDenied=Denied,
        wait_procs=lambda processes, timeout: (
            [p for p in processes if not p.live],
            [p for p in processes if p.live],
        ),
    )


def owner(root, child=None, native=None):
    server = object.__new__(gate.OwnedServer)
    server.root, server.psutil = root, module(root)
    server.process = native or NativeProcess(root)
    server.known = {root}
    if child:
        root.descendants = [child]
        server.known.add(child)
    return server


@pytest.mark.parametrize("deny_kill", [False, True])
def test_child_stop_failure_does_not_prevent_root_reap_and_remaining_cleanup(deny_kill):
    root = Process(1)
    child = Process(2, parent=1, deny_stop=True, deny_kill=deny_kill)
    server = owner(root, child)
    assert server.close() is (not deny_kill)
    assert server.process.terminated and server.process.reaped
    assert not root.live


def test_root_timeout_uses_native_handle_kill_and_reaps():
    root = Process(1)
    native = NativeProcess(root, ignore_terminate=True)
    server = owner(root, native=native)
    assert server.close()
    assert native.killed and native.reaped


def test_snapshot_after_original_exit_cannot_adopt_a_reused_pid(tmp_path, monkeypatch):
    unrelated = Process(1)
    native = NativeProcess(unrelated, exited=True)
    monkeypatch.setitem(sys.modules, "psutil", module(unrelated))
    monkeypatch.setattr(gate.subprocess, "Popen", lambda *a, **k: native)
    monkeypatch.setattr(gate, "launch_plan", lambda env, cwd: (sys.executable, env))
    server = gate.OwnedServer({}, tmp_path)
    server.start()
    assert server.root is None and not server.known
    assert server.close() and native.reaped
    assert unrelated.live


def test_descendant_snapshot_requires_current_owned_ancestry():
    root, unrelated = Process(1), Process(2, parent=99)
    root.descendants = [unrelated]
    server = owner(root)
    server.observe()
    assert unrelated not in server.known


def test_cancel_after_spawn_cannot_claim_cleanup_without_stopping_native(tmp_path, monkeypatch):
    root = Process(1)
    native = NativeProcess(root)
    handlers = {signal.SIGINT: object(), signal.SIGTERM: object()}

    def install(number, handler):
        old = handlers[number]
        handlers[number] = handler
        return old

    def snapshot(_pid):
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        return root

    api = module(root)
    api.Process = snapshot
    monkeypatch.setitem(sys.modules, "psutil", api)
    monkeypatch.setattr(signal, "signal", install)
    monkeypatch.setattr(gate.subprocess, "Popen", lambda *a, **k: native)
    if hasattr(gate, "launch_plan"):
        monkeypatch.setattr(gate, "launch_plan", lambda env, cwd: (sys.executable, env))
    cli = tmp_path / "bruno.js"
    cli.touch()
    with gate.controlled_interrupts("collection_interrupted"):
        report = gate.run_collection("node", cli, tmp_path / "report.json")
    assert not report["passed"]
    assert report["owned_server_stopped"] and not root.live and native.reaped
