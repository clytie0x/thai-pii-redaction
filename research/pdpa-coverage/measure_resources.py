"""Independent process resource probes using fixed fictional public text only."""

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def worker(strategy, model_dir):
    for key in (
        "HF_HUB_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "HF_HUB_DISABLE_IMPLICIT_TOKEN",
        "DO_NOT_TRACK",
    ):
        os.environ[key] = "1"
    start = time.perf_counter()
    sys.path.insert(0, str(ROOT))
    import psutil
    from pii_redactor.pdpa_assessment import assess_text

    if strategy == "hybrid":
        import torch

        torch.set_num_threads(4)
    text = "My medical test is negative. My personal data require review."
    assess_text(text, strategy=strategy, model_dir=model_dir, threshold=0.4)
    cold = time.perf_counter() - start
    timings = []
    for _ in range(20):
        tick = time.perf_counter()
        assess_text(text, strategy=strategy, model_dir=model_dir, threshold=0.4)
        timings.append((time.perf_counter() - tick) * 1000)
    memory = psutil.Process().memory_info()
    return {
        "strategy": strategy,
        "cold_start_seconds": cold,
        "warm_ms": {"p50": statistics.median(timings), "p95": sorted(timings)[18]},
        "rss_mb": memory.rss / 1024**2,
        "peak_mb": getattr(memory, "peak_wset", memory.rss) / 1024**2,
        "peak_kind": "peak_working_set" if hasattr(memory, "peak_wset") else "sampled_rss",
        "probe": "fixed_public_synthetic_text",
        "network": "local_artifacts_only",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=["keyword", "contextual", "hybrid"])
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker, args.model_dir)))
        return
    if not args.out or args.out.exists():
        raise ValueError("resource output must be new")
    results = {}
    for strategy in ("keyword", "contextual", "hybrid"):
        process = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                strategy,
                "--model-dir",
                args.model_dir,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        results[strategy] = json.loads(process.stdout)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "methods": results,
                "limits": "Single fixed public probe, separate processes; not workload/population/SLO evidence.",
            },
            stream,
            indent=2,
        )
        stream.write("\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
