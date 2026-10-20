"""Hosted-deployment readiness knobs (deploy design v2, 2026-07-28).

Six small generic changes that let a hosted port run the same core:
AMPHRANG_ALLOWED_HOSTS, AMPHRANG_PROVIDERS, the acceptance-script header fix,
the audit-dir boot check, AMPHRANG_AUDIT_STDOUT, and the text work cap.
Env-driven import-time behavior is tested in a subprocess so this
process's `amphrang.server.server` module stays untouched.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from amphrang.server import server
from amphrang.server.server import app

ROOT = Path(__file__).resolve().parent.parent
V2_HEADERS = {"X-Amphrang-Contract-Version": "2"}


@pytest.fixture()
def client():
    return TestClient(app, base_url="http://localhost")


# ── AMPHRANG_ALLOWED_HOSTS ──────────────────────────────────────────────
def test_parse_csv_env_splits_strips_and_drops_empties():
    assert server._parse_csv_env("a.example, b.example ,,") == ["a.example", "b.example"]
    assert server._parse_csv_env("") == []
    assert server._parse_csv_env(None) == []


def test_default_trusted_hosts_unchanged_when_env_unset(client):
    # this process imported amphrang.server.server without the env var -> exact old default
    assert client.get("/api/health").status_code == 200
    foreign = TestClient(app, base_url="http://evil.example")
    assert foreign.get("/api/health").status_code == 400


def test_env_allowed_host_is_accepted_in_fresh_process():
    # Import-time wiring must honor the env var; prove it in a subprocess so
    # the already-imported module here is not disturbed.
    code = (
        "import os\n"
        "os.environ['AMPHRANG_ALLOWED_HOSTS'] = 'team08.aiforthai.in.th'\n"
        "from fastapi.testclient import TestClient\n"
        "from amphrang.server.server import app\n"
        "c = TestClient(app, base_url='http://team08.aiforthai.in.th')\n"
        "assert c.get('/api/health').status_code == 200\n"
        "local = TestClient(app, base_url='http://localhost')\n"
        "assert local.get('/api/health').status_code == 400\n"
        "print('OK')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, timeout=120
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "OK" in proc.stdout


# ── AMPHRANG_PROVIDERS ──────────────────────────────────────────────────
def test_provider_allowlist_env_narrows_surface_in_fresh_process():
    code = (
        "import os\n"
        "os.environ['AMPHRANG_PROVIDERS'] = 'fake'\n"
        "from fastapi.testclient import TestClient\n"
        "from amphrang.server.server import app\n"
        "c = TestClient(app, base_url='http://localhost')\n"
        "h = {'X-Amphrang-Contract-Version': '2'}\n"
        "r = c.post('/api/roundtrip', headers=h, json={'text': 'ทดสอบข้อความธรรมดา', 'mode': 'token', 'provider': 'tokenmind'})\n"
        "assert r.status_code == 400, r.status_code\n"
        "r2 = c.post('/api/roundtrip', headers=h, json={'text': 'ทดสอบข้อความธรรมดา', 'mode': 'token', 'provider': 'fake'})\n"
        "assert r2.status_code == 200, r2.status_code\n"
        "print('OK')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, timeout=180
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "OK" in proc.stdout


def test_unknown_provider_name_fails_the_boot_loudly():
    code = (
        "import os\n"
        "os.environ['AMPHRANG_PROVIDERS'] = 'typo_provider'\n"
        "try:\n"
        "    import amphrang.server.server\n"
        "except ValueError as e:\n"
        "    assert 'typo_provider' in str(e)\n"
        "    print('BOOT_REFUSED')\n"
        "else:\n"
        "    print('BOOT_ACCEPTED')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, timeout=120
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "BOOT_REFUSED" in proc.stdout


def test_no_env_keeps_full_registry(client):
    r = client.post(
        "/api/roundtrip",
        headers=V2_HEADERS,
        json={"text": "ทดสอบ", "mode": "token", "provider": "no_such"},
    )
    assert r.status_code == 400
    for name in ("fake", "pathumma", "tokenmind", "ollama", "claude"):
        assert name not in json.dumps(r.json())


def test_hosted_adapter_exposes_only_allowlisted_v2_routes():
    code = (
        "import os\n"
        "os.environ['AMPHRANG_API_KEY'] = 'synthetic-hosted-key'\n"
        "os.environ['AMPHRANG_PROVIDERS'] = 'fake'\n"
        "from fastapi.testclient import TestClient\n"
        "from amphrang.server.hosted import app\n"
        "paths = {getattr(route, 'path', None) for route in app.routes}\n"
        "expected = {'/api/health', '/api/detect', '/api/analyze', '/api/guard', '/api/sanitize', '/api/reidentify', '/api/roundtrip'}\n"
        "assert paths == expected, paths\n"
        "c = TestClient(app, base_url='http://localhost')\n"
        "h = {'X-Amphrang-Contract-Version': '2', 'X-Amphrang-Key': 'synthetic-hosted-key'}\n"
        "assert c.get('/api/health').status_code == 200\n"
        "for path in ('/', '/docs', '/redoc', '/openapi.json', '/api/audit-log', '/api/shutdown', '/api/session/synthetic'):\n"
        "    method = c.delete if path.startswith('/api/session/') else c.post if path == '/api/shutdown' else c.get\n"
        "    response = method(path, headers=h)\n"
        "    assert response.status_code == 404, (path, response.status_code)\n"
        "print('OK')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "OK" in proc.stdout


@pytest.mark.parametrize("missing_name", ["AMPHRANG_API_KEY", "AMPHRANG_PROVIDERS"])
def test_hosted_adapter_refuses_missing_authority_or_provider_policy(missing_name):
    code = (
        "import os\n"
        "os.environ['AMPHRANG_API_KEY'] = 'synthetic-hosted-key'\n"
        "os.environ['AMPHRANG_PROVIDERS'] = 'fake'\n"
        f"os.environ.pop({missing_name!r})\n"
        "try:\n"
        "    import amphrang.server.hosted\n"
        "except RuntimeError as error:\n"
        f"    assert {missing_name!r} in str(error)\n"
        "    print('BOOT_REFUSED')\n"
        "else:\n"
        "    print('BOOT_ACCEPTED')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "BOOT_REFUSED" in proc.stdout


@pytest.mark.parametrize("provider_policy", [",", " , , "])
def test_hosted_adapter_refuses_effectively_empty_provider_policy(provider_policy):
    code = (
        "import os, sys\n"
        "os.environ['AMPHRANG_API_KEY'] = 'synthetic-hosted-key'\n"
        f"os.environ['AMPHRANG_PROVIDERS'] = {provider_policy!r}\n"
        "try:\n"
        "    import amphrang.server.hosted\n"
        "except RuntimeError as error:\n"
        "    assert 'AMPHRANG_PROVIDERS' in str(error)\n"
        "    assert 'amphrang.server.server' not in sys.modules\n"
        "    print('BOOT_REFUSED')\n"
        "else:\n"
        "    print('BOOT_ACCEPTED')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "BOOT_REFUSED" in proc.stdout


# ── audit stdout mode ──────────────────────────────────────────────────
def test_audit_stdout_mode_prints_json_and_writes_no_file(monkeypatch, tmp_path, capsys):
    from amphrang.engine.audit import write_process_log

    monkeypatch.setenv("AMPHRANG_AUDIT_STDOUT", "1")
    path = write_process_log(
        session_id="s1",
        step="test",
        entity_count=2,
        validation_result="pass",
        flags=["a"],
        latency_ms=1.0,
        output_dir=str(tmp_path),
    )
    out = capsys.readouterr().out.strip()
    entry = json.loads(out)
    assert entry["step"] == "test" and entry["entity_count"] == 2
    assert list(tmp_path.iterdir()) == []  # nothing touched the filesystem
    assert path.parent == tmp_path  # would-be path still reported


def test_audit_file_mode_unchanged_without_env(monkeypatch, tmp_path):
    from amphrang.engine.audit import write_security_log

    monkeypatch.delenv("AMPHRANG_AUDIT_STDOUT", raising=False)
    path = write_security_log(
        session_id="s2",
        layer="layer1",
        pii_scan_result="clean",
        mapping_table_access_count=0,
        retry_count=0,
        error_type=None,
        rollback_occurred=False,
        output_dir=str(tmp_path),
    )
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["layer"] == "layer1"


# ── audit dir boot check ───────────────────────────────────────────────
def test_audit_dir_boot_check_fails_loudly_when_unwritable(monkeypatch, tmp_path):
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("file, not dir", encoding="utf-8")
    # a probe write under a FILE path raises OSError on every platform
    monkeypatch.setattr(server, "_get_audit_log_dir", lambda: str(blocker / "logs"))
    monkeypatch.delenv("AMPHRANG_AUDIT_STDOUT", raising=False)
    with pytest.raises(RuntimeError, match="not writable"):
        server._check_audit_dir_writable()


def test_audit_dir_boot_check_skipped_in_stdout_mode(monkeypatch, tmp_path):
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("file, not dir", encoding="utf-8")
    monkeypatch.setattr(server, "_get_audit_log_dir", lambda: str(blocker / "logs"))
    monkeypatch.setenv("AMPHRANG_AUDIT_STDOUT", "1")
    server._check_audit_dir_writable()  # no raise


# ── text length cap ────────────────────────────────────────────────────
def test_text_endpoints_reject_over_limit(client, monkeypatch):
    monkeypatch.setattr(server, "_MAX_TEXT_CHARS", 10)
    long_text = "ก" * 11
    for path, payload in [
        ("/api/detect", {"text": long_text}),
        ("/api/guard", {"text": long_text}),
        ("/api/sanitize", {"text": long_text}),
        ("/api/analyze", {"text": long_text}),
        ("/api/roundtrip", {"text": long_text, "mode": "token", "provider": "fake"}),
    ]:
        r = client.post(path, headers=V2_HEADERS, json=payload)
        assert r.status_code == 413, f"{path} -> {r.status_code}"


def test_text_cap_default_does_not_bite_normal_input(client):
    r = client.post(
        "/api/detect",
        headers=V2_HEADERS,
        json={"text": "ผมชื่อ นายสมชาย ใจดี"},
    )
    assert r.status_code == 200


def test_reidentify_empty_text_is_now_a_clean_400(client):
    r = client.post(
        "/api/reidentify",
        headers=V2_HEADERS,
        json={"session_id": "nope", "text": "  "},
    )
    assert r.status_code == 400
