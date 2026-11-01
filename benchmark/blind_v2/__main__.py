"""Check the reproducible blind-v2 freeze.

The comparison harness is a separate entry on this module. ``--self-check``
only regenerates the corpus in memory and compares the hash and validation
kinds with the committed lock. It does not print document text.
"""

from __future__ import annotations

import argparse
import sys

from .corpus import (
    GENERATION_SEED,
    LOCK_PATH,
    corpus_sha256,
    generate_corpus,
    load_lock,
    public_lock,
    validate_corpus,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmark.blind_v2")
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="regenerate the synthetic freeze and compare it with the lock",
    )
    args = parser.parse_args(argv)
    if not args.self_check:
        print(
            "blind-v2-repro: pass --self-check to verify the freeze "
            "(the comparison harness is added separately)",
            file=sys.stderr,
        )
        return 2

    corpus = generate_corpus()
    problems = sorted(set(validate_corpus(corpus)))
    digest = corpus_sha256(corpus)
    lock = load_lock()
    mismatch = digest != lock.get("plaintext_sha256") or public_lock(corpus) != lock
    if problems or mismatch or corpus.seed != GENERATION_SEED:
        kinds = ",".join(problems) if problems else "lock-mismatch"
        print(f"blind-v2-repro: freeze check failed ({kinds})", file=sys.stderr)
        return 2
    print(
        f"blind-v2-repro OK seed={corpus.seed} documents={len(corpus.documents)} "
        f"sha256={digest} lock={LOCK_PATH.name}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
