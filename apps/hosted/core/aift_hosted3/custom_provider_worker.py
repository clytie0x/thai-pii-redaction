"""Killable streamed Pathumma transport for queue-approved custom text."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aift_hosted3.custom_provider import (  # noqa: E402
    MAX_CUSTOM_PROVIDER_INPUT_UTF8_BYTES,
    MAX_CUSTOM_PROVIDER_OUTPUT_CODEPOINTS,
    MAX_CUSTOM_PROVIDER_OUTPUT_UTF8_BYTES,
    MAX_CUSTOM_PROVIDER_WORKER_REQUEST_BYTES,
)
from aift_hosted3.preview import DEFAULT_SYSTEM_PROMPT  # noqa: E402


MAX_CUSTOM_PROVIDER_WIRE_RESPONSE_BYTES = 640 * 1024


class CustomProviderWireError(ValueError):
    """The custom provider crossed a fixed value-free transport boundary."""


class CustomProviderConfigurationError(ValueError):
    """Operator configuration could not construct the approved provider."""


def _build_provider(factory=None):
    if factory is None:
        from pii_redactor.ai_client import TokenmindProvider

        factory = TokenmindProvider
    try:
        return factory()
    except ValueError:
        raise CustomProviderConfigurationError() from None


def _read_bounded_wire_response(response) -> bytes:
    content_encoding = response.headers.get("content-encoding")
    if content_encoding is not None and content_encoding.strip().lower() != "identity":
        raise CustomProviderWireError()
    declared = response.headers.get("content-length")
    if declared is not None:
        if not declared.isascii() or not declared.isdigit():
            raise CustomProviderWireError()
        if int(declared) > MAX_CUSTOM_PROVIDER_WIRE_RESPONSE_BYTES:
            raise CustomProviderWireError()
    body = bytearray()
    for chunk in response.iter_raw():
        if not isinstance(chunk, bytes):
            raise CustomProviderWireError()
        if len(body) + len(chunk) > MAX_CUSTOM_PROVIDER_WIRE_RESPONSE_BYTES:
            body.clear()
            raise CustomProviderWireError()
        body.extend(chunk)
    if not body:
        raise CustomProviderWireError()
    return bytes(body)


def _payload(system: str, user: str) -> dict[str, object]:
    if system != DEFAULT_SYSTEM_PROMPT:
        raise CustomProviderWireError()
    return {
        "model": "thaillm-8b",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.0,
        "max_tokens": 1024,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }


def _complete_with_provider(provider, system: str, user: str) -> str:
    import httpx

    headers = {
        "Accept-Encoding": "identity",
        "Authorization": f"Bearer {provider._api_key}",
    }
    raw = b""
    try:
        with provider._client() as client:
            with client.stream(
                "POST",
                provider._url,
                json=_payload(system, user),
                headers=headers,
                timeout=60.0,
            ) as response:
                response.raise_for_status()
                raw = _read_bounded_wire_response(response)
                bounded = httpx.Response(
                    response.status_code,
                    headers=response.headers,
                    content=raw,
                )
        content = provider._validated_content(bounded)
        encoded = content.encode("utf-8")
        if (
            len(content) > MAX_CUSTOM_PROVIDER_OUTPUT_CODEPOINTS
            or len(encoded) > MAX_CUSTOM_PROVIDER_OUTPUT_UTF8_BYTES
        ):
            raise CustomProviderWireError()
        return content
    finally:
        headers.clear()
        provider._api_key = ""
        raw = b""


def _decode_b64(value: object) -> str:
    if not isinstance(value, str) or not value or not value.isascii():
        raise CustomProviderWireError()
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        if base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=") != value.rstrip("="):
            raise ValueError
        return decoded.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        raise CustomProviderWireError() from None


def _strict_request_frame(raw: bytes) -> tuple[str, str]:
    if not 1 <= len(raw) <= MAX_CUSTOM_PROVIDER_WORKER_REQUEST_BYTES:
        raise CustomProviderWireError()
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
        value = json.loads(raw, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CustomProviderWireError() from None
    if duplicate or not isinstance(value, dict) or set(value) != {"system_b64", "user_b64"}:
        raise CustomProviderWireError()
    system = _decode_b64(value.get("system_b64"))
    user = _decode_b64(value.get("user_b64"))
    if (
        system != DEFAULT_SYSTEM_PROMPT
        or not user
        or len(user.encode("utf-8")) > MAX_CUSTOM_PROVIDER_INPUT_UTF8_BYTES
    ):
        raise CustomProviderWireError()
    return system, user


def _write(value: dict[str, object]) -> None:
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def main() -> int:
    system = ""
    user = ""
    response = ""
    try:
        system, user = _strict_request_frame(
            sys.stdin.buffer.read(MAX_CUSTOM_PROVIDER_WORKER_REQUEST_BYTES + 1)
        )
        try:
            provider = _build_provider()
        except CustomProviderConfigurationError:
            _write({"ok": False, "code": "provider_configuration"})
            return 0
        response = _complete_with_provider(provider, system, user)
        _write(
            {
                "ok": True,
                "content_b64": base64.urlsafe_b64encode(
                    response.encode("utf-8")
                ).decode("ascii").rstrip("="),
            }
        )
        return 0
    except CustomProviderWireError:
        _write({"ok": False, "code": "provider_response_invalid"})
        return 0
    except Exception as error:
        code = "provider_unavailable"
        try:
            import httpx

            if isinstance(error, httpx.HTTPStatusError):
                status = getattr(getattr(error, "response", None), "status_code", None)
                code = (
                    "provider_unavailable"
                    if status == 429 or (type(status) is int and status >= 500)
                    else "provider_rejected"
                )
            elif isinstance(error, httpx.TimeoutException):
                code = "provider_timeout"
            elif isinstance(error, httpx.HTTPError):
                code = "provider_unavailable"
            elif isinstance(error, (ValueError, KeyError, TypeError, IndexError)):
                code = "provider_response_invalid"
        except Exception:
            code = "provider_unavailable"
        _write({"ok": False, "code": code})
        return 0
    finally:
        system = ""
        user = ""
        response = ""


if __name__ == "__main__":
    raise SystemExit(main())
