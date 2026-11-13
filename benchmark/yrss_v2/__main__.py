"""Score systems on a YRSS evaluation v2 split.

``python -m benchmark.yrss_v2 --split dev --systems aiguard,regex --json out.json``
The output has scores only. It never prints document text.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import harness
from .systems import SystemUnavailable, system_names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmark.yrss_v2")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument(
        "--systems", default="aiguard,regex", help="comma list of: " + ", ".join(system_names())
    )
    parser.add_argument("--json", default=None, help="write the report to this file")
    parser.add_argument("--llm-base-url", default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-key-env", default=None, help="name of the variable, not the key")
    parser.add_argument("--llm-seed", type=int, default=None)
    parser.add_argument(
        harness.TEST_FLAG,
        dest="allow_test",
        action="store_true",
        help="the test split is scored once; this flag is needed to score it",
    )
    args = parser.parse_args(argv)

    names = [name.strip() for name in args.systems.split(",") if name.strip()]
    llm_options = None
    if args.llm_base_url or args.llm_model:
        llm_options = {
            "base_url": args.llm_base_url,
            "model": args.llm_model,
            "api_key_env": args.llm_key_env,
            "seed": args.llm_seed,
        }
    try:
        report = harness.run(args.split, names, llm_options=llm_options, allow_test=args.allow_test)
    except harness.TestSplitRefused:
        print(f"yrss-eval-v2: refusing the test split without {harness.TEST_FLAG}", file=sys.stderr)
        return 2
    except (ValueError, SystemUnavailable, harness.CorpusLockError) as exc:
        print(f"yrss-eval-v2: {exc}", file=sys.stderr)
        return 2
    print(harness.render_report(report))
    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
