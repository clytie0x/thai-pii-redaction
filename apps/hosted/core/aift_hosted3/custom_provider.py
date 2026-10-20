"""Bounded Pathumma transport for queue-approved custom text."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import Callable
from pathlib import Path

from .preview import (
    DEFAULT_SYSTEM_PROMPT,
    MAX_CUSTOM_PROTECTED_UTF8_BYTES,
)


CUSTOM_PROVIDER_ATTEMPT_TIMEOUT_SECONDS = 60.0
CUSTOM_PROVIDER_MAX_ATTEMPTS = 3
MAX_CUSTOM_PROVIDER_INPUT_UTF8_BYTES = MAX_CUSTOM_PROTECTED_UTF8_BYTES
MAX_CUSTOM_PROVIDER_OUTPUT_CODEPOINTS = 32_000
MAX_CUSTOM_PROVIDER_OUTPUT_UTF8_BYTES = 96 * 1024
MAX_CUSTOM_PROVIDER_WORKER_REQUEST_BYTES = 144 * 1024
MAX_CUSTOM_PROVIDER_WORKER_RESPONSE_BYTES = 132 * 1024


class CustomProviderCallError(RuntimeError):
    """A fixed, value-free custom-provider failure."""

    def __init__(self, code: str = "provider_unavailable", *, attempts: int = 0):
        self.code = code if code in {
            "provider_configuration",
            "provider_rejected",
            "provider_response_invalid",
            "provider_timeout",
            "provider_unavailable",
        } else "provider_unavailable"
        self.attempts = attempts if type(attempts) is int and attempts >= 0 else 0
        super().__init__(self.code)


def complete_custom_provider(
    system: str,
    user: str,
    before_attempt: Callable[[int], None],
) -> tuple[str, float, int]:
    """Run the approved three-attempt policy through a bounded child process."""

    _validate_request(system, user)
    started = time.monotonic()
    for attempt in range(CUSTOM_PROVIDER_MAX_ATTEMPTS):
        before_attempt(attempt)
        try:
            response = _complete_once(system, user)
        except CustomProviderCallError as error:
            code = error.code
            retryable = code in {"provider_timeout", "provider_unavailable"}
            if retryable and attempt + 1 < CUSTOM_PROVIDER_MAX_ATTEMPTS:
                time.sleep(2**attempt)
                continue
            raise CustomProviderCallError(
                code,
                attempts=(0 if code == "provider_configuration" else attempt + 1),
            ) from None
        return response, time.monotonic() - started, attempt + 1
    raise CustomProviderCallError(attempts=0)


def _validate_request(system: str, user: str) -> None:
    if system != DEFAULT_SYSTEM_PROMPT or not isinstance(user, str) or not user:
        raise CustomProviderCallError("provider_response_invalid")
    try:
        encoded = user.encode("utf-8")
    except UnicodeEncodeError:
        raise CustomProviderCallError("provider_response_invalid") from None
    if len(encoded) > MAX_CUSTOM_PROVIDER_INPUT_UTF8_BYTES:
        raise CustomProviderCallError("provider_response_invalid")


def _complete_once(system: str, user: str) -> str:
    request_frame = json.dumps(
        {
            "system_b64": urlsafe_b64encode(system.encode("utf-8")).decode("ascii"),
            "user_b64": urlsafe_b64encode(user.encode("utf-8")).decode("ascii"),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    if len(request_frame) > MAX_CUSTOM_PROVIDER_WORKER_REQUEST_BYTES:
        raise CustomProviderCallError("provider_response_invalid")
    environment = _provider_worker_environment()
    worker = Path(__file__).with_name("custom_provider_worker.py")
    try:
        stdout = _run_worker(
            request_frame,
            worker_path=worker,
            environment=environment,
            timeout_seconds=CUSTOM_PROVIDER_ATTEMPT_TIMEOUT_SECONDS,
        )
    finally:
        environment.clear()
        request_frame = b""
    return _worker_response(stdout)


def _provider_worker_environment() -> dict[str, str]:
    base_url = os.environ.get("TOKENMIND_BASE_URL", "")
    api_key = os.environ.get("TOKENMIND_API_KEY", "")
    if not base_url or not api_key:
        raise CustomProviderCallError("provider_configuration")
    environment = {
        "HOME": "/tmp",
        "LANG": "C.UTF-8",
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHAINLP_DATA": os.environ.get("PYTHAINLP_DATA", "/opt/pythainlp-data"),
        "PYTHAINLP_OFFLINE": "1",
        "TOKENMIND_API_KEY": api_key,
        "TOKENMIND_BASE_URL": base_url,
    }
    if os.environ.get("TOKENMIND_ALLOW_HTTP") == "1":
        environment["TOKENMIND_ALLOW_HTTP"] = "1"
    return environment


def _run_worker(
    request_frame: bytes,
    *,
    worker_path: Path,
    environment: dict[str, str],
    timeout_seconds: float,
) -> bytes:
    if (
        not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
        or timeout_seconds > CUSTOM_PROVIDER_ATTEMPT_TIMEOUT_SECONDS
    ):
        raise ValueError("timeout exceeds the custom provider attempt envelope")
    started = time.monotonic()
    process = subprocess.Popen(
        [sys.executable, "-I", str(worker_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=str(worker_path.parent.parent),
        env=environment,
        start_new_session=True,
    )
    try:
        try:
            remaining = float(timeout_seconds) - (time.monotonic() - started)
            if remaining <= 0:
                raise subprocess.TimeoutExpired(process.args, timeout_seconds)
            stdout, _stderr = process.communicate(
                input=request_frame,
                timeout=remaining,
            )
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5.0)
            raise CustomProviderCallError("provider_timeout") from None
        if process.returncode != 0:
            raise CustomProviderCallError()
        if not 1 <= len(stdout) <= MAX_CUSTOM_PROVIDER_WORKER_RESPONSE_BYTES:
            raise CustomProviderCallError("provider_response_invalid")
        return stdout
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5.0)


def _worker_response(stdout: bytes) -> str:
    duplicate = False

    def pairs(rows):
        nonlocal duplicate
        output = {}
        for key, value in rows:
            if key in output:
                duplicate = True
            output[key] = value
        return output

    try:
        value = json.loads(stdout, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CustomProviderCallError("provider_response_invalid") from None
    if duplicate or not isinstance(value, dict):
        raise CustomProviderCallError("provider_response_invalid")
    if set(value) == {"ok", "code"} and value.get("ok") is False:
        raise CustomProviderCallError(str(value.get("code")))
    if set(value) != {"ok", "content_b64"} or value.get("ok") is not True:
        raise CustomProviderCallError("provider_response_invalid")
    encoded = value.get("content_b64")
    if not isinstance(encoded, str) or not encoded or not encoded.isascii():
        raise CustomProviderCallError("provider_response_invalid")
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        content_bytes = urlsafe_b64decode(padded.encode("ascii"))
        if urlsafe_b64encode(content_bytes).decode("ascii").rstrip("=") != encoded.rstrip("="):
            raise ValueError
        content = content_bytes.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        raise CustomProviderCallError("provider_response_invalid") from None
    if (
        not content.strip()
        or len(content) > MAX_CUSTOM_PROVIDER_OUTPUT_CODEPOINTS
        or len(content_bytes) > MAX_CUSTOM_PROVIDER_OUTPUT_UTF8_BYTES
    ):
        raise CustomProviderCallError("provider_response_invalid")
    return content
