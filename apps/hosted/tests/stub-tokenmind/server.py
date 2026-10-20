#!/usr/bin/env python3
"""Value-free local OpenAI-compatible provider for Stage 6 browser evidence."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

MAX_BODY = 96 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "AIGuardStage6Stub/1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send(self, status: int, value: object) -> None:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self._send(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if not 0 <= length <= MAX_BODY:
            self._send(413, {"error": "request_too_large"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            messages = payload["messages"]
            user = next(row["content"] for row in reversed(messages) if row["role"] == "user")
            document = json.loads(user)
        except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError):
            document = None
        if isinstance(document, dict) and isinstance(document.get("segments"), list):
            roles = ("identity", "contact", "profile", "experience", "education", "skills", "achievements", "other")
            content = json.dumps(
                {
                    "classifications": [
                        {"segment_id": row["segment_id"], "role": roles[index % len(roles)]}
                        for index, row in enumerate(document["segments"])
                    ]
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        else:
            try:
                content = str(user)
            except UnboundLocalError:
                self._send(400, {"error": "invalid_request"})
                return
        self._send(200, {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
