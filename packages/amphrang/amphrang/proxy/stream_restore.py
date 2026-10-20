"""Restore bracket tokens in streamed text without buffering the stream.

Bracket tokens have a bounded length (``_TOKEN_MAX_LENGTH``), so the restorer
never holds back more than one token's worth of text after an unresolved
``[``. Text that merely looks bracketed passes through verbatim, and a ``[``
opening before a real token does not hide it: on a mismatch only the single
``[`` is emitted and scanning resumes inside.
"""

from __future__ import annotations

from amphrang.engine.anonymizer.token_generator import _TOKEN_MAX_LENGTH


class StreamRestorer:
    """Feed chunks in, get restored text out; ``flush()`` drains the tail."""

    def __init__(self, mapping: dict[str, str]):
        self._mapping = dict(mapping)
        self._buffer = ""

    def feed(self, chunk: str) -> str:
        self._buffer += chunk
        return self._drain(final=False)

    def flush(self) -> str:
        return self._drain(final=True)

    def _drain(self, *, final: bool) -> str:
        out: list[str] = []
        buffer = self._buffer
        while buffer:
            start = buffer.find("[")
            if start == -1:
                out.append(buffer)
                buffer = ""
                break
            out.append(buffer[:start])
            buffer = buffer[start:]
            close = buffer.find("]")
            if close == -1:
                if final:
                    out.append(buffer)
                    buffer = ""
                    break
                if len(buffer) > _TOKEN_MAX_LENGTH:
                    # No token can be this long; release the '[' and rescan.
                    out.append(buffer[0])
                    buffer = buffer[1:]
                    continue
                break  # hold: a token may still be completing
            candidate = buffer[: close + 1]
            if len(candidate) <= _TOKEN_MAX_LENGTH and candidate in self._mapping:
                out.append(self._mapping[candidate])
                buffer = buffer[close + 1 :]
                continue
            # Not one of ours: release the '[' only, so an inner token is
            # still found on the next pass.
            out.append(buffer[0])
            buffer = buffer[1:]
        self._buffer = buffer
        return "".join(out)
