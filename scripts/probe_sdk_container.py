"""Value-free HTTP probe sent over stdin to the owned SDK image container."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

EXPECTED = {
    "health": 200,
    "sanitize": 200,
    "reidentify": 200,
    "missing_key": 401,
    "wrong_key": 401,
    "phone_masked": True,
    "phone_restored": True,
}


class ProbeFailed(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def probe(port, key):
    if type(port) is not int or not 1 <= port <= 65535 or not key:
        raise ProbeFailed("invalid_probe_setup")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    base = f"http://127.0.0.1:{port}"

    def request(path, payload=None, credential=None):
        headers = {"X-Amphrang-Contract-Version": "2"}
        if credential is not None:
            headers["X-Amphrang-Key"] = credential
        if payload is not None:
            headers["Content-Type"] = "application/json"
        prepared = urllib.request.Request(
            base + path,
            headers=headers,
            data=None if payload is None else json.dumps(payload).encode(),
        )
        try:
            with opener.open(prepared, timeout=2) as response:
                raw = response.read(65537)
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            return status, None
        except OSError:
            return None, None
        parsed = None
        try:
            if len(raw) <= 65536:
                parsed = json.loads(raw)
        except ValueError:
            pass
        return status, parsed

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        status, health = request("/api/health")
        if (
            status == 200
            and isinstance(health, dict)
            and health.get("status") == "ok"
            and health.get("contract_version") == 2
            and health.get("capabilities", {}).get("api_key_required") is True
        ):
            break
        time.sleep(0.1)
    else:
        raise ProbeFailed("keyed_health_not_ready")
    phone = "081-234-5678"
    original = "Synthetic contact: " + phone
    payload = {"text": original, "mode": "token"}
    status, masked = request("/api/sanitize", payload, key)
    if (
        status != 200
        or not isinstance(masked, dict)
        or masked.get("safety", {}).get("status") != "pass"
        or masked.get("safety", {}).get("residual_count") != 0
        or masked.get("entity_type_counts", {}).get("PHONE") != 1
        or "mapping" in masked
        or phone in json.dumps(masked)
        or not isinstance(masked.get("sanitized_text"), str)
        or not isinstance(masked.get("session_id"), str)
    ):
        raise ProbeFailed("keyed_sanitize_invalid")
    status, restored = request(
        "/api/reidentify",
        {"text": masked["sanitized_text"], "session_id": masked["session_id"]},
        key,
    )
    if (
        status != 200
        or not isinstance(restored, dict)
        or restored.get("restored_text") != original
        or "mapping" in restored
    ):
        raise ProbeFailed("keyed_restore_invalid")
    if request("/api/sanitize", payload)[0] != 401:
        raise ProbeFailed("missing_key_not_denied")
    wrong_key = "synthetic-wrong-key" if key != "synthetic-wrong-key" else "other-invalid-key"
    if request("/api/sanitize", payload, wrong_key)[0] != 401:
        raise ProbeFailed("wrong_key_not_denied")
    return dict(EXPECTED)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    result = None
    try:
        result = probe(args.port, os.environ.get("AMPHRANG_API_KEY"))
    except Exception:
        pass
    if result is None:
        print("SDK keyed image probe failed; bodies and credentials suppressed.", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
