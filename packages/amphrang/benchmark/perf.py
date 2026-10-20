"""Performance harness: cold start, latency per size class, throughput, memory.

Same discipline as the accuracy benchmark — deterministic corpus, one command,
machine-readable output — but measuring speed instead of recall. Run with
``python -m benchmark.perf`` (full) or ``--profile ci`` (cheap subset with a
catastrophic-regression guard; the ceilings are deliberately loose because CI
runners are shared hardware).

Timing loops take an injected timer and ``run()`` takes injected measure
functions so the logic is testable without the NER model.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from .corpus import build_corpus

# Target document sizes in characters. XL stays well under the server's
# 200k-char work cap so numbers stay comparable with the hosted path.
SIZE_CLASSES: dict[str, int] = {"S": 200, "M": 2_000, "L": 20_000, "XL": 100_000}

_PROFILE_CLASSES = {"ci": ("S", "M"), "full": ("S", "M", "L", "XL")}
_ITERATIONS = {
    "ci": {"S": 10, "M": 5},
    "full": {"S": 30, "M": 15, "L": 5, "XL": 2},
}

# Catastrophic-only ceilings (ms): an order of magnitude above healthy numbers,
# so shared CI hardware never flakes but a 10x regression still fails the job.
CI_THRESHOLDS: dict[tuple[str, str], float] = {
    ("S", "detect"): 5_000.0,
    ("S", "anonymize"): 8_000.0,
    ("M", "detect"): 20_000.0,
    ("M", "anonymize"): 30_000.0,
}

# Guarantees every class has structured PII to find, even the smallest.
_HEADER = "ติดต่อกลับที่ 081-234-5678\n"


def percentile(samples: list[float], p: float) -> float:
    """Nearest-rank percentile (no interpolation): honest for small n."""
    ordered = sorted(samples)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def summarize(durations_s: list[float]) -> dict[str, float]:
    """Seconds in, milliseconds out, rounded so reports stay readable."""
    ms = [d * 1000 for d in durations_s]
    return {
        "n": len(ms),
        "p50_ms": round(percentile(ms, 50), 3),
        "p95_ms": round(percentile(ms, 95), 3),
        "min_ms": round(min(ms), 3),
        "max_ms": round(max(ms), 3),
        "mean_ms": round(statistics.fmean(ms), 3),
    }


def build_perf_documents(seed: int = 42) -> dict[str, str]:
    """One deterministic document per size class, near the target length.

    The body is whole lines from the synthetic accuracy corpus, cycled until
    the target is reached — never sliced mid-line: a partial name/value is
    invisible to detection but visible to the residual scanner, so
    ``anonymize()`` would fail closed and abort the run. The fixed header
    keeps at least one detectable structured value in every class.
    """
    texts = [sample.text for sample in build_corpus(seed=seed, size=200)]
    docs: dict[str, str] = {}
    for name, target in SIZE_CLASSES.items():
        parts = [_HEADER.rstrip("\n")]
        length = len(_HEADER)
        index = 0
        while length < target:
            line = texts[index % len(texts)]
            index += 1
            if length + len(line) + 1 > 1.2 * target:
                break
            parts.append(line)
            length += len(line) + 1
        docs[name] = "\n".join(parts)
    return docs


def anonymize_outcome(text: str) -> bool:
    """Run one anonymize for timing purposes; return True when the leak guard
    blocked. A fail-closed block still executed the full pipeline (detect,
    mask, outbound scans), so its duration is a legitimate sample — the flag
    is reported instead of aborting the run."""
    import amphrang

    try:
        amphrang.anonymize(text, mode="token")
        return False
    except amphrang.LeakBlockedError:
        return True


def measure_callable(
    fn: Callable[[], object],
    iterations: int,
    warmup: int = 1,
    timer: Callable[[], float] = time.perf_counter,
) -> list[float]:
    """Per-iteration durations in seconds; warmup runs execute but are dropped."""
    for _ in range(warmup):
        fn()
    durations: list[float] = []
    for _ in range(iterations):
        start = timer()
        fn()
        durations.append(timer() - start)
    return durations


_COLD_START_CODE = (
    "import time; t0 = time.perf_counter(); "
    "import amphrang; amphrang.detect('ติดต่อ 081-234-5678 นายสมชาย ใจดี'); "
    "print(time.perf_counter() - t0)"
)


def measure_cold_start(samples: int = 3) -> list[float]:
    """Fresh-process import + first detect (model load), once per sample."""
    durations: list[float] = []
    for _ in range(samples):
        proc = subprocess.run(
            [sys.executable, "-c", _COLD_START_CODE],
            capture_output=True,
            text=True,
            check=True,
        )
        durations.append(float(proc.stdout.strip()))
    return durations


def _worker_warmup() -> None:
    import amphrang

    amphrang.detect(_HEADER)


def _worker_detect(text: str) -> int:
    import amphrang

    return len(amphrang.detect(text))


def measure_multi_worker(docs: list[str], workers: int) -> dict[str, float]:
    """Docs/sec across a process pool; pool spin-up and model load are excluded.

    The initializer warms every worker exactly once as it starts, and the
    pre-map forces all workers to start before the clock does.
    """
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(max_workers=workers, initializer=_worker_warmup) as pool:
        list(pool.map(_noop, range(workers)))  # force all workers to spawn now
        start = time.perf_counter()
        list(pool.map(_worker_detect, docs))
        elapsed = time.perf_counter() - start
    return {
        "workers": workers,
        "docs": len(docs),
        "seconds": round(elapsed, 3),
        "docs_per_s": round(len(docs) / elapsed, 3),
    }


def _noop(_index: int) -> None:
    return None


def measure_peak_memory(fn: Callable[[], object]) -> dict[str, float] | None:
    """Peak RSS (MB) sampled while fn runs; None when psutil is unavailable."""
    try:
        import psutil
    except ImportError:
        return None
    import threading

    process = psutil.Process()
    baseline = process.memory_info().rss
    peak = baseline
    stop = threading.Event()

    def sample() -> None:
        nonlocal peak
        while not stop.is_set():
            peak = max(peak, process.memory_info().rss)
            stop.wait(0.01)

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    try:
        fn()
    finally:
        stop.set()
        thread.join()
    peak = max(peak, process.memory_info().rss)
    return {
        "baseline_mb": round(baseline / 1_048_576, 1),
        "peak_mb": round(peak / 1_048_576, 1),
    }


def environment_info() -> dict[str, object]:
    import amphrang

    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "amphrang": amphrang.__version__,
        "ner_engine": os.environ.get("AMPHRANG_NER_ENGINE", "thainer"),
    }


def run(
    profile: str = "full",
    seed: int = 42,
    workers: int = 0,
    memory: bool = False,
    measure: Callable[..., list[float]] | None = None,
    cold_start_fn: Callable[[], list[float]] | None = None,
) -> dict:
    """Measure everything the profile asks for and return the report dict.

    ``workers=0`` skips the multi-worker throughput pass; ``memory=False``
    skips RSS sampling. Both stay off in unit tests and in the CI profile.
    """
    import amphrang

    measure = measure or measure_callable
    if cold_start_fn is None:
        cold_start_fn = lambda: measure_cold_start(3 if profile == "full" else 1)  # noqa: E731

    docs = build_perf_documents(seed=seed)
    classes = _PROFILE_CLASSES[profile]
    iterations = _ITERATIONS[profile]

    latency: dict[str, dict[str, dict]] = {}
    for name in classes:
        text = docs[name]
        blocked: list[bool] = []
        ops = {
            "detect": lambda t=text: amphrang.detect(t),
            "anonymize": lambda t=text, b=blocked: b.append(anonymize_outcome(t)),
        }
        latency[name] = {
            op: summarize(measure(fn, iterations=iterations[name], warmup=1))
            for op, fn in ops.items()
        }
        latency[name]["anonymize"]["leak_blocked"] = any(blocked)

    # Throughput over a mixed batch: mostly short docs, some medium — the
    # shape of interactive LLM traffic, not a synthetic best case.
    batch = [docs["S"]] * 20 + [docs["M"]] * 5
    batch_durations = [
        measure(lambda t=t: amphrang.detect(t), iterations=1, warmup=0)[0] for t in batch
    ]
    total = sum(batch_durations)
    throughput: dict[str, object] = {
        "single_process": {
            "docs": len(batch),
            "seconds": round(total, 3),
            "docs_per_s": round(len(batch) / total, 3) if total else None,
        }
    }
    if workers > 0:
        throughput["multi_worker"] = measure_multi_worker(batch, workers)

    report: dict[str, object] = {
        "profile": profile,
        "environment": environment_info(),
        "cold_start": summarize(cold_start_fn()),
        "latency": latency,
        "throughput": throughput,
    }
    if memory:
        rss = measure_peak_memory(lambda: amphrang.detect(docs[classes[-1]]))
        if rss is not None:
            report["memory"] = rss
    return report


def evaluate_ci_thresholds(
    report: dict, thresholds: dict[tuple[str, str], float] | None = None
) -> list[str]:
    """Return one message per (class, op) whose p95 exceeds its ceiling."""
    thresholds = CI_THRESHOLDS if thresholds is None else thresholds
    failures: list[str] = []
    for (class_name, op), ceiling in thresholds.items():
        stats = report.get("latency", {}).get(class_name, {}).get(op)
        if stats and stats["p95_ms"] > ceiling:
            failures.append(
                f"{class_name}/{op}: p95 {stats['p95_ms']}ms exceeds ceiling {ceiling}ms"
            )
    return failures


def render_markdown(report: dict) -> str:
    env = report["environment"]
    lines = [
        "# amphrang performance report",
        "",
        f"- Profile: {report['profile']}",
        f"- Python: {env['python']} ({env['implementation']})",
        f"- Platform: {env['platform']}",
        f"- CPUs: {env['cpu_count']}",
        f"- amphrang: {env['amphrang']} (engine: {env['ner_engine']})",
        "",
        "## Cold start (fresh process, import + first detect)",
        "",
        f"- n={report['cold_start']['n']}, p50 {report['cold_start']['p50_ms']} ms, "
        f"max {report['cold_start']['max_ms']} ms",
        "",
        "## Latency",
        "",
        "| class | chars | op | n | p50 (ms) | p95 (ms) | min (ms) | max (ms) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for class_name, ops in report["latency"].items():
        for op, stats in ops.items():
            lines.append(
                f"| {class_name} | {SIZE_CLASSES[class_name]} | {op} | {stats['n']} "
                f"| {stats['p50_ms']} | {stats['p95_ms']} | {stats['min_ms']} "
                f"| {stats['max_ms']} |"
            )
    blocked = [
        class_name
        for class_name, ops in report["latency"].items()
        if ops.get("anonymize", {}).get("leak_blocked")
    ]
    if blocked:
        lines += [
            "",
            f"- fail-closed: the leak guard blocked anonymize output on {', '.join(blocked)} — "
            "the timings still cover the full pipeline (detect, mask, outbound scans) up to "
            "the block",
        ]
    single = report["throughput"]["single_process"]
    lines += [
        "",
        "## Throughput (mixed batch: 20 S + 5 M, detect)",
        "",
        f"- single process: {single['docs']} docs in {single['seconds']} s "
        f"= {single['docs_per_s']} docs/s",
    ]
    multi = report["throughput"].get("multi_worker")
    if multi:
        lines.append(
            f"- {multi['workers']} workers: {multi['docs']} docs in {multi['seconds']} s "
            f"= {multi['docs_per_s']} docs/s"
        )
    memory = report.get("memory")
    if memory:
        lines += [
            "",
            "## Memory (RSS during a detect on the largest measured class)",
            "",
            f"- baseline {memory['baseline_mb']} MB, peak {memory['peak_mb']} MB",
        ]
    lines.append("")
    return "\n".join(lines)


def write_text_lf(path: Path, text: str) -> None:
    """Write LF regardless of platform: reports get committed and the repo
    working tree is LF-only (.gitattributes)."""
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="benchmark.perf")
    ap.add_argument("--profile", default="full", choices=["full", "ci"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--workers",
        type=int,
        default=None,
        help="multi-worker throughput pass (default: min(4, cpus) on full, off on ci)",
    )
    ap.add_argument("--json", default=None, help="also write the report as JSON here")
    ap.add_argument("--markdown", default=None, help="also write the report as markdown here")
    args = ap.parse_args(argv)

    if args.workers is None:
        args.workers = min(4, os.cpu_count() or 1) if args.profile == "full" else 0

    report = run(
        profile=args.profile,
        seed=args.seed,
        workers=args.workers,
        memory=args.profile == "full",
    )
    print(render_markdown(report))
    if args.json:
        write_text_lf(Path(args.json), json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if args.markdown:
        write_text_lf(Path(args.markdown), render_markdown(report))

    if args.profile == "ci":
        failures = evaluate_ci_thresholds(report)
        if failures:
            for failure in failures:
                print(f"CI threshold exceeded: {failure}", file=sys.stderr)
            return 1
        print("CI thresholds OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
