"""Killable, streamed Pathumma transport for protected segment classification."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aift_hosted3.document_artifact import MAX_PROVIDER_RESPONSE_BYTES  # noqa: E402
from aift_hosted3.document_provider import (  # noqa: E402
    DOCUMENT_PROVIDER_ABSOLUTE_TIMEOUT_SECONDS,
    DOCUMENT_SYSTEM_PROMPT,
    MAX_PROVIDER_WORKER_REQUEST_BYTES,
    document_provider_payload,
)

MAX_PROVIDER_WIRE_RESPONSE_BYTES = 32 * 1024


class ProviderWireError(ValueError):
    """The provider transport crossed a fixed value-free boundary."""


def _read_bounded_wire_response(response) -> bytes:
    content_encoding = response.headers.get("content-encoding")
    if content_encoding is not None and content_encoding.strip().lower() != "identity":
        raise ProviderWireError()
    declared = response.headers.get("content-length")
    if declared is not None:
        if not declared.isascii() or not declared.isdigit():
            raise ProviderWireError()
        if int(declared) > MAX_PROVIDER_WIRE_RESPONSE_BYTES:
            raise ProviderWireError()
    body = bytearray()
    for chunk in response.iter_raw():
        if not isinstance(chunk, bytes):
            raise ProviderWireError()
        if len(body) + len(chunk) > MAX_PROVIDER_WIRE_RESPONSE_BYTES:
            body.clear()
            raise ProviderWireError()
        body.extend(chunk)
    if not body:
        raise ProviderWireError()
    return bytes(body)


def _complete_with_provider(provider, system: str, user: str) -> str:
    import httpx

    payload = document_provider_payload(system, user)
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
                json=payload,
                headers=headers,
                timeout=DOCUMENT_PROVIDER_ABSOLUTE_TIMEOUT_SECONDS,
            ) as response:
                response.raise_for_status()
                raw = _read_bounded_wire_response(response)
                bounded = httpx.Response(
                    response.status_code,
                    headers=response.headers,
                    content=raw,
                )
        content = provider._validated_content(bounded)
        if len(content.encode("utf-8")) > MAX_PROVIDER_RESPONSE_BYTES:
            raise ProviderWireError()
        return content
    finally:
        headers.clear()
        provider._api_key = ""
        raw = b""


def _strict_request_frame(raw: bytes) -> str:
    if not 1 <= len(raw) <= MAX_PROVIDER_WORKER_REQUEST_BYTES:
        raise ProviderWireError()
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
        raise ProviderWireError() from None
    if duplicate or not isinstance(value, dict) or set(value) != {"request_b64"}:
        raise ProviderWireError()
    encoded = value.get("request_b64")
    if not isinstance(encoded, str) or not encoded or not encoded.isascii():
        raise ProviderWireError()
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        if base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=") != encoded.rstrip("="):
            raise ValueError
        request = decoded.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        raise ProviderWireError() from None
    document_provider_payload(DOCUMENT_SYSTEM_PROMPT, request)
    return request


def _write(value: dict[str, object]) -> None:
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def main() -> int:
    request = ""
    response = ""
    try:
        request = _strict_request_frame(
            sys.stdin.buffer.read(MAX_PROVIDER_WORKER_REQUEST_BYTES + 1)
        )
        from pii_redactor.ai_client import TokenmindProvider

        response = _complete_with_provider(
            TokenmindProvider(),
            DOCUMENT_SYSTEM_PROMPT,
            request,
        )
        _write(
            {
                "ok": True,
                "content_b64": base64.urlsafe_b64encode(
                    response.encode("utf-8")
                ).decode("ascii").rstrip("="),
            }
        )
        return 0
    except ProviderWireError:
        _write({"ok": False, "code": "provider_response_invalid"})
        return 0
    except Exception:
        _write({"ok": False, "code": "provider_failed"})
        return 0
    finally:
        request = ""
        response = ""


if __name__ == "__main__":
    raise SystemExit(main())
