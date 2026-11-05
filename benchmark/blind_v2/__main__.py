"""Reproduce the blind-v2 comparison.

``python -m benchmark.blind_v2`` scores the original freeze.
``--split hard-dev`` and ``--split hard-test`` score the locked prose splits.
``--self-check`` only checks the selected lock. Neither command prints
document text.
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
from .hard_set import (
    generate_hard,
    lock_path,
    validate_hard,
)
from .hard_set import (
    public_lock as hard_public_lock,
)
from .harness import build_systems, default_system_names, render_report, run_benchmark

_HARD_SPLITS = {"hard-dev": "dev", "hard-test": "test"}


def prepare_corpus(split: str):
    """Return ``(corpus, error)``. ``error`` is a short kind with no text."""
    if split == "freeze":
        corpus = generate_corpus()
        problems = sorted(set(validate_corpus(corpus)))
        lock = load_lock()
        digest = corpus_sha256(corpus)
        if problems or digest != lock.get("plaintext_sha256") or public_lock(corpus) != lock:
            kinds = ",".join(problems) if problems else "lock-mismatch"
            return None, kinds
        if corpus.seed != GENERATION_SEED:
            return None, "unexpected-seed"
        return corpus, None
    name = _HARD_SPLITS.get(split)
    if name is None:
        return None, "unknown-split"
    corpus = generate_hard(name)
    problems = sorted(set(validate_hard(corpus)))
    lock = json.loads(lock_path(name).read_text(encoding="utf-8"))
    if problems or hard_public_lock(corpus) != lock:
        kinds = ",".join(problems) if problems else "lock-mismatch"
        return None, kinds
    return corpus, None


def _lock_label(split: str, corpus) -> tuple[str, str]:
    if split == "freeze":
        return corpus_sha256(corpus), LOCK_PATH.name
    name = _HARD_SPLITS[split]
    return hard_public_lock(corpus)["plaintext_sha256"], lock_path(name).name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmark.blind_v2")
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument(
        "--split",
        choices=("freeze", "hard-dev", "hard-test"),
        default="freeze",
    )
    parser.add_argument("--systems", default=",".join(default_system_names()))
    parser.add_argument("--no-ablate", action="store_true")
    parser.add_argument("--no-utility", action="store_true")
    parser.add_argument("--no-section26", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--llm-seed", type=int, default=None)
    parser.add_argument("--json", default=None)
    args = parser.parse_args(argv)

    corpus, error = prepare_corpus(args.split)
    if error:
        print(f"blind-v2-repro: freeze check failed ({error})", file=sys.stderr)
        return 2
    if args.self_check:
        digest, lock_name = _lock_label(args.split, corpus)
        print(
            f"blind-v2-repro OK split={args.split} seed={corpus.seed} "
            f"documents={len(corpus.documents)} sha256={digest} lock={lock_name}"
        )
        return 0

    names = [name.strip() for name in args.systems.split(",") if name.strip()]
    try:
        systems = build_systems(names, llm_seed=args.llm_seed)
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
