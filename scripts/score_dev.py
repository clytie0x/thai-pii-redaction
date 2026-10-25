"""Score the open development set in benchmark/data/dev/*.jsonl.

The dev set is for tuning and may be read freely, unlike the blind sets.
Prints overall entity metrics, the full/partial leak rates, a per-type table
and the negative-slice false positives.

    $env:PYTHONUTF8='1'
    .\\.venv\\Scripts\\python.exe scripts\\score_dev.py [--engine crf] [--json out.json] [--leaks]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.gold import parse_gold
from benchmark.runner import predict_samples
from benchmark.scorer import score

DEV_DIR = Path(__file__).resolve().parents[1] / "benchmark" / "data" / "dev"


def load_dev(paths=None):
    samples = []
    for path in sorted(paths or DEV_DIR.glob("*.jsonl")):
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                samples.append(parse_gold(r["doc_id"], r["slice"], r["annotated"]))
    return samples


def leaked_values(samples, predictions):
    """Yield (doc_id, type, value, kind) for every gold entity left readable."""
    for sample, preds in zip(samples, predictions):
        for g in sample.spans:
            chars = [k for k in range(g.start, g.end) if sample.text[k].isalnum()]
            covered = {k for k in chars for p in preds if p[0] <= k < p[1]}
            if not chars or len(covered) == len(chars):
                continue
            kind = "full" if not covered else "partial"
            yield sample.template_id, g.entity_type, sample.text[g.start : g.end], kind


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="score_dev")
    ap.add_argument("--engine", default="crf")
    ap.add_argument("--json", default=None)
    ap.add_argument("--leaks", action="store_true", help="list every leaked dev value")
    ap.add_argument("files", nargs="*")
    args = ap.parse_args(argv)

    samples = load_dev(args.files or None)
    predictions = predict_samples(samples, args.engine)
    report = score(samples, predictions, bootstrap_iters=0)
    o = report["overall"]
    print(
        f"docs={report['corpus']['samples']} entities={report['corpus']['entities']} "
        f"R={o['recall']:.3f} P={o['precision']:.3f} F2={o['f2']:.3f} "
        f"full_leak={o['full_leak_entities']} ({o['full_leak_rate']:.3f}) "
        f"partial_leak={o['partial_leak_entities']} ({o['partial_leak_rate']:.3f})"
    )
    print(f"{'type':<15}{'n':>5}{'recall':>8}{'prec':>8}{'full':>6}{'part':>6}")
    for t, m in sorted(report["by_type"].items()):
        n = report["corpus"]["by_type"].get(t, 0)
        print(
            f"{t:<15}{n:>5}{m['recall']:>8.3f}{m['precision']:>8.3f}"
            f"{m['full_leak']:>6}{m['partial_leak']:>6}"
        )
    neg = report["by_slice"].get("negative")
    if neg:
        print(
            f"negative docs={neg['documents']} clean={neg['clean_docs']} "
            f"false_positives={neg['false_positives']}"
        )
    if args.leaks:
        for doc_id, etype, value, kind in leaked_values(samples, predictions):
            print(f"LEAK {kind:<7} {etype:<14} {doc_id:<12} {value}")
    if args.json:
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
