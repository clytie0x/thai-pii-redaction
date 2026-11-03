"""Bounded marshal fingerprints without loading or constructing cached code."""

from __future__ import annotations

import hashlib
import marshal
import struct
import sys

MAX_NODES = 200_000
MAX_DEPTH = 200
MAX_LONG_DIGITS = 4096


def _fingerprint(kind, *values):
    result = hashlib.sha256(kind.encode() + b"\0")
    for value in values:
        result.update(len(value).to_bytes(8, "little"))
        result.update(value)
    return result.digest()


class _Reader:
    def __init__(self, data):
        self.data = memoryview(data)
        self.position = 0
        self.remaining_nodes = MAX_NODES
        self.references = []
        self.filename = None

    def _take(self, size):
        if size < 0 or size > len(self.data) - self.position:
            raise ValueError("artifact_identity_invalid")
        value = bytes(self.data[self.position : self.position + size])
        self.position += size
        return value

    def _integer(self):
        return int.from_bytes(self._take(4), "little", signed=True)

    def _float(self):
        value = self._take(self._take(1)[0]).decode("ascii")
        return struct.pack("<d", float(value))

    def _object(self, depth=0):
        self.remaining_nodes -= 1
        if depth > MAX_DEPTH or self.remaining_nodes < 0:
            raise ValueError("artifact_identity_invalid")
        tag = self._take(1)[0]
        kind = chr(tag & 0x7F)
        slot = None
        if tag & 0x80:
            slot = len(self.references)
            self.references.append(None)
        if kind == "r":
            index = self._integer()
            if slot is not None or not 0 <= index < len(self.references):
                raise ValueError("artifact_identity_invalid")
            result = self.references[index]
            if result is None:
                raise ValueError("artifact_identity_invalid")
            return result
        if kind in {"N", "F", "T", "S", "."}:
            result = (kind, _fingerprint(kind), None)
        elif kind in {"i", "l"}:
            if kind == "i":
                number = self._integer()
            else:
                count = self._integer()
                if abs(count) > MAX_LONG_DIGITS:
                    raise ValueError("artifact_identity_invalid")
                number = 0
                for index in range(abs(count)):
                    digit = int.from_bytes(self._take(2), "little")
                    if digit > 0x7FFF:
                        raise ValueError("artifact_identity_invalid")
                    number |= digit << (15 * index)
                if count < 0:
                    number = -number
            raw = number.to_bytes((number.bit_length() + 8) // 8, "little", signed=True)
            result = ("integer", _fingerprint("integer", raw), None)
        elif kind in {"f", "g", "x", "y"}:
            if kind == "f":
                raw = self._float()
            elif kind == "x":
                raw = self._float() + self._float()
            else:
                raw = self._take(8 if kind == "g" else 16)
            numeric = "float" if kind in {"f", "g"} else "complex"
            result = (numeric, _fingerprint(numeric, raw), None)
        elif kind in {"s", "u", "t", "a", "A", "z", "Z"}:
            size = self._take(1)[0] if kind in {"z", "Z"} else self._integer()
            raw = self._take(size)
            if kind == "s":
                result = ("bytes", _fingerprint("bytes", raw), None)
            else:
                if kind in {"a", "A", "z", "Z"} and not raw.isascii():
                    raise ValueError("artifact_identity_invalid")
                raw.decode("utf-8", errors="surrogatepass")
                result = ("text", _fingerprint("text", raw), raw)
        elif kind in {"(", ")", ">"}:
            count = self._take(1)[0] if kind == ")" else self._integer()
            if not 0 <= count <= self.remaining_nodes:
                raise ValueError("artifact_identity_invalid")
            values = [self._object(depth + 1)[1] for _ in range(count)]
            collection = "tuple"
            if kind == ">":
                collection = "frozenset"
                if len(set(values)) != len(values):
                    raise ValueError("artifact_identity_invalid")
                values.sort()
            result = (collection, _fingerprint(collection, *values), None)
        elif kind == "c":
            # CPython 3.11-3.13 use five integers, five objects, filename,
            # name/qualname, first line, line table and exception table.
            header = self._take(20)
            values = [self._object(depth + 1)[1] for _ in range(5)]
            filename = self._object(depth + 1)
            if filename[0] != "text" or not filename[2]:
                raise ValueError("artifact_identity_invalid")
            if self.filename is None:
                self.filename = filename[2]
            elif self.filename != filename[2]:
                raise ValueError("artifact_identity_invalid")
            values.extend(self._object(depth + 1)[1] for _ in range(2))
            first_line = self._take(4)
            values.extend(self._object(depth + 1)[1] for _ in range(2))
            result = ("code", _fingerprint("code", header, first_line, *values), None)
        else:
            raise ValueError("artifact_identity_invalid")
        if slot is not None:
            self.references[slot] = result
        return result

    def fingerprint(self):
        value = self._object()
        if value[0] != "code" or self.position != len(self.data):
            raise ValueError("artifact_identity_invalid")
        return value[1]


def verify_cache_body(source, body, level):
    """Compare data fingerprints, never unmarshal or execute untrusted bytes."""
    if sys.implementation.name != "cpython" or not (3, 11) <= sys.version_info[:2] <= (3, 13):
        raise ValueError("artifact_identity_invalid")
    expected_code = compile(source, "<aiguard-source>", "exec", dont_inherit=True, optimize=level)
    expected = marshal.dumps(expected_code)
    if _Reader(body).fingerprint() != _Reader(expected).fingerprint():
        raise ValueError("artifact_identity_invalid")
