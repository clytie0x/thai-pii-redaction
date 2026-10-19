"""Container-level lifecycle contract for the secretless Stage 3 PDF parser."""

from __future__ import annotations

import json
import os
import subprocess
import time
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGE = os.environ.get("AIGUARD_PARSER_IMAGE", "aiguard-pdf-parser-stage3:local")
RUN_LIFECYCLE = os.environ.get("AIGUARD_PARSER_LIFECYCLE") == "1"


def _docker(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *arguments],
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _client_source(body: str) -> str:
    return (
        "import json,socket,struct,time\n"
        "def frame(value):\n"
        " p=json.dumps(value,separators=(',',':'),sort_keys=True).encode()\n"
        " return struct.pack('>I',len(p))+p\n"
        "def receive(sock):\n"
        " size=struct.unpack('>I',sock.recv(4))[0]\n"
        " data=b''\n"
        " while len(data)<size:\n"
        "  data+=sock.recv(size-len(data))\n"
        " return json.loads(data)\n"
        f"{body}\n"
    )


@unittest.skipUnless(RUN_LIFECYCLE, "container lifecycle only")
class ParserLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.name = f"aiguard-parser-lifecycle-{uuid.uuid4().hex[:12]}"
        profile = str((ROOT / "pdf-parser" / "seccomp.json").resolve())
        _docker(
            "run",
            "--name",
            self.name,
            "--detach",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--security-opt",
            f"seccomp={profile}",
            "--pids-limit",
            "32",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--tmpfs",
            "/run/aiguard-pdf:rw,noexec,nosuid,nodev,size=1m,uid=1000,gid=1000,mode=0770",
            "--tmpfs",
            "/work:rw,noexec,nosuid,nodev,size=64m,uid=1000,gid=1000,mode=0700",
            IMAGE,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            state = _docker("inspect", self.name, "--format", "{{.State.Running}}")
            if state.stdout.strip() == "true":
                probe = _docker(
                    "exec",
                    self.name,
                    "python",
                    "-c",
                    _client_source(
                        "s=socket.socket(socket.AF_UNIX);s.connect('/run/aiguard-pdf/parser.sock');"
                        "s.sendall(frame({'protocol_version':1,'operation':'health','body_bytes':0}));"
                        "print(json.dumps(receive(s),sort_keys=True))"
                    ),
                    check=False,
                )
                if probe.returncode == 0:
                    self.assertEqual(
                        json.loads(probe.stdout),
                        {"ok": True, "protocol_version": 1, "status": "ready"},
                    )
                    return
            time.sleep(0.1)
        self.fail(f"parser did not become ready: {_docker('logs', self.name, check=False).stderr}")

    def tearDown(self):
        _docker("rm", "--force", self.name, check=False)

    def _exec_client(self, body: str, *, detached: bool = False):
        arguments = ["exec"]
        if detached:
            arguments.append("--detach")
        arguments.extend([self.name, "python", "-c", _client_source(body)])
        return _docker(*arguments)

    def _scenario(self) -> dict[str, object]:
        result = self._exec_client(
            "s=socket.socket(socket.AF_UNIX);s.connect('/run/aiguard-pdf/parser.sock');"
            "s.sendall(frame({'protocol_version':1,'operation':'parse_scenario','body_bytes':0,"
            "'scenario_id':'hr-resume-pdf-structured-v1'}));"
            "print(json.dumps(receive(s),ensure_ascii=False,sort_keys=True))"
        )
        return json.loads(result.stdout)

    def test_slow_header_and_body_are_bounded_and_capacity_recovers(self):
        slow_header = self._exec_client(
            "s=socket.socket(socket.AF_UNIX);s.connect('/run/aiguard-pdf/parser.sock');"
            "s.sendall(b'\\x00');time.sleep(1.2);"
            "print(json.dumps(receive(s),sort_keys=True))"
        )
        self.assertEqual(
            json.loads(slow_header.stdout),
            {"code": "document_parser_unavailable", "ok": False},
        )

        slow_body = self._exec_client(
            "s=socket.socket(socket.AF_UNIX);s.connect('/run/aiguard-pdf/parser.sock');"
            "s.sendall(frame({'protocol_version':1,'operation':'parse_document','body_bytes':100,"
            "'source_kind':'standard'}));assert receive(s)=={'ok':True,'status':'ready'};"
            "s.sendall(b'%');time.sleep(10.2);"
            "print(json.dumps(receive(s),sort_keys=True))"
        )
        self.assertEqual(
            json.loads(slow_body.stdout),
            {"code": "document_parser_unavailable", "ok": False},
        )
        recovered = self._scenario()
        self.assertTrue(recovered["ok"])
        self.assertEqual(recovered["result"]["segment_count"], 31)
        leftovers = _docker(
            "exec",
            self.name,
            "sh",
            "-c",
            "find /work -mindepth 1 -maxdepth 1 -print",
        )
        self.assertEqual(leftovers.stdout.strip(), "")

    def test_unlink_failure_stops_pid1_with_exit_70(self):
        self._exec_client(
            "data=open('/app/scenarios/hr-resume-pdf-structured-v1.pdf','rb').read();"
            "s=socket.socket(socket.AF_UNIX);s.connect('/run/aiguard-pdf/parser.sock');"
            "s.sendall(frame({'protocol_version':1,'operation':'parse_document','body_bytes':len(data),"
            "'source_kind':'standard'}));assert receive(s)=={'ok':True,'status':'ready'};"
            "s.sendall(data[:1]);time.sleep(3);s.sendall(data[1:]);time.sleep(2)",
            detached=True,
        )
        deadline = time.monotonic() + 2.5
        found = False
        while time.monotonic() < deadline:
            probe = _docker(
                "exec",
                self.name,
                "sh",
                "-c",
                "find /work -name 'job-*.pdf' -type f | head -n 1",
                check=False,
            )
            if probe.returncode == 0 and probe.stdout.strip():
                found = True
                break
            time.sleep(0.05)
        self.assertTrue(found, "the held upload never created its private spool")
        _docker("exec", self.name, "chmod", "0500", "/work")

        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            state = json.loads(_docker("inspect", self.name).stdout)[0]["State"]
            if not state["Running"]:
                self.assertEqual(state["ExitCode"], 70)
                mounts = json.loads(_docker("inspect", self.name).stdout)[0]["HostConfig"]["Tmpfs"]
                self.assertIn("/work", mounts)
                return
            time.sleep(0.1)
        self.fail("parser kept serving after private-spool cleanup failed")

    def test_three_failed_health_probes_stop_pid1_for_clean_restart(self):
        _docker("exec", self.name, "rm", "/run/aiguard-pdf/parser.sock")
        for _ in range(3):
            _docker(
                "exec",
                self.name,
                "python",
                "/app/healthcheck.py",
                check=False,
            )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = json.loads(_docker("inspect", self.name).stdout)[0]["State"]
            if not state["Running"]:
                self.assertEqual(state["ExitCode"], 0)
                return
            time.sleep(0.1)
        self.fail("parser healthcheck did not stop an unrecoverable PID 1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
