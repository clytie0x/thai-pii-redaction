"""Reproduce the blind-v2 comparison.

``python -m benchmark.blind_v2`` scores every configured system.
``python -m benchmark.blind_v2 --self-check`` only checks the freeze hash.
Neither command prints document text.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .corpus import (
    GENERATION_SEED,
    LOCK_PATH,
    corpus_sha256,
    generate_corpus,
    load_lock,
    public_lock,
    validate_corpus,
)
from .harness import build_systems, default_system_names, render_report, run_benchmark


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmark.blind_v2")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--systems", default=",".join(default_system_names()))
    parser.add_argument("--no-ablate", action="store_true")
    parser.add_argument("--no-utility", action="store_true")
    parser.add_argument("--no-section26", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)

    corpus = generate_corpus()
    problems = sorted(set(validate_corpus(corpus)))
    lock = load_lock()
    digest = corpus_sha256(corpus)
    if problems or digest != lock.get("plaintext_sha256") or public_lock(corpus) != lock:
        kinds = ",".join(problems) if problems else "lock-mismatch"
        print(f"blind-v2-repro: freeze check failed ({kinds})", file=sys.stderr)
        return 2
    if args.self_check:
        print(
            f"blind-v2-repro OK seed={GENERATION_SEED} documents={len(corpus.documents)} "
            f"sha256={digest} lock={LOCK_PATH.name}"
        )
        return 0
    if corpus.seed != GENERATION_SEED:
        print("blind-v2-repro: unexpected seed", file=sys.stderr)
        return 2

    names = [name.strip() for name in args.systems.split(",") if name.strip()]
    try:
        systems = build_systems(names)
    except ValueError:
        print("blind-v2-repro: unknown system", file=sys.stderr)
        return 2
    report = run_benchmark(
        corpus,
        systems=systems,
        ablate=not args.no_ablate,
        utility=not args.no_utility,
        section26=not args.no_section26,
        limit=max(args.limit, 0),
    )
    print(render_report(report))
    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
