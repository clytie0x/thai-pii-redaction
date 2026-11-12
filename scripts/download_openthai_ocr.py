#!/usr/bin/env python3
"""Download OpenThai2.0-OCR-Text into a local directory.

This is the only network path for that model. OCR never calls it. The
revision and SHA-256 pins match the Hugging Face snapshot cited in
docs/decisions/2026-11-12-openthai-ocr-engine.md. A changed upstream file
fails here until the pin is updated on purpose.

Usage:
    python scripts/download_openthai_ocr.py --dest /path/outside/the/repo
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

REVISION = "39fa41bdd49f067ba41b1d9de79c06ab506d67d4"
_HOST = "https://huggingface.co/iapp/OpenThai2.0-OCR-Text/resolve/"
BASE = f"{_HOST}{REVISION}/"

# Hashes are the SHA256SUMS entries from that revision. pytorch/rec_weights.pt
# is a training checkpoint and is not downloaded.
PINNED: tuple[tuple[str, str], ...] = (
    ("NOTICE", "4c0e4f27877836de51e29aec3918b6c743c3028cd4163b6661fd540336db32b3"),
    ("config.json", "11599c0dae206381cb8ea11c1b7ce130b2e7971c19219f409785ee8c02ab5d94"),
    ("det.onnx", "193bab7a04fca699a6c82e6abb5b81bdb28177f0abd4062552b04908dafb19f8"),
    ("det.yml", "3ac018be6f97499a08faa3bbdeb33640968d9307f6736d152902747a9f259593"),
    ("rec.onnx", "82ec89533346faadcb30df96703dad2dd7521de65709e60d83fd9745b8968124"),
    ("rec_dict.txt", "259ef2636cec0eeae225ae9fd9a63fa9305285650c22d7ec34fe8a82b24c2f1a"),
    ("runtime/__init__.py", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    (
        "runtime/line_engine.py",
        "5d5d672658d2a82ca6b32e230bb551eefe5d1e4efa46ff21908bfcfd75e5495c",
    ),
    (
        "runtime/thai_norm.py",
        "53a03ac139fb0de3e7aec0f5b8ab69b0b519fb5e636f7c1de09cb357b023344a",
    ),
)


def _fetch(rel: str) -> bytes:
    request = urllib.request.Request(
        BASE + rel, headers={"User-Agent": "aiguard-openthai-download"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def _check(rel: str, payload: bytes, digest: str) -> None:
    actual = hashlib.sha256(payload).hexdigest()
    if actual != digest:
        raise SystemExit(f"checksum mismatch for {rel}")


def _store(dest: Path, rel: str, payload: bytes) -> None:
    target = dest / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".partial")
    temporary.write_bytes(payload)
    temporary.replace(target)


def download(dest: Path, fetch=_fetch) -> None:
    """Save each pinned file only after its SHA-256 matches."""
    dest.mkdir(parents=True, exist_ok=True)
    for rel, digest in PINNED:
        payload = fetch(rel)
        _check(rel, payload, digest)
        _store(dest, rel, payload)
        print(f"saved {rel}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download OpenThai2.0-OCR-Text")
    parser.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args(argv)
    download(args.dest)
    print(f"OpenThai OCR model saved under {args.dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
