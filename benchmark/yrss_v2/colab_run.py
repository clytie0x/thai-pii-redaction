"""Run the LLM comparator on another machine and write harness cache files.

The harness reads ``--llm-cache`` files and reuses every finished document, so
the predictions can come from a faster machine (for example a Colab GPU) and
the scoring still happens locally with the key that never leaves it. This file
needs only ``llm_openai.py``, ``types.py`` and the score dedupe rule, so it can
be copied next to them without the rest of the repository.

``python -m benchmark.yrss_v2.colab_run docs.jsonl meta.json out_dir --seeds 1,2,3,4,5``
"""

from __future__ import annotations

import argparse
import hashlib
import json
import threading
import time
from pathlib import Path

from .llm_openai import PROMPT_VERSION, make_predictor, prompt_sha256

WARM_UP_TEXT = "นายตัวอย่าง ระบบ โทร 02-000-0000"  # same text as harness._WARM_UP_TEXT


def dedupe(spans):
    """Same rule as benchmark.blind_v2.score.dedupe_predictions."""
    ordered = sorted(spans, key=lambda item: (item[0], -(item[1] - item[0]), item[2]))
    kept, cursor = [], 0
    for start, end, entity_type in ordered:
        if end <= start or start < cursor:
            continue
        kept.append((start, end, entity_type))
        cursor = end
    return kept


def header(meta: dict, seed: int) -> dict:
    """Same keys and values as harness._cache_header."""
    return {
        "model": meta["model"],
        "seed": seed,
        "base_url": meta["base_url"],
        "prompt_sha256": prompt_sha256(),
        "prompt_version": PROMPT_VERSION,
        "split": meta["split"],
        "corpus_sha256": meta["corpus_sha256"],
    }


def run_seed(docs: list[dict], meta: dict, seed: int, out_dir: Path) -> dict:
    path = out_dir / f"llm-seed{seed}.jsonl"
    predict = make_predictor(
        base_url=meta["base_url"],
        model=meta["model"],
        api_key_env=None,
        seed=seed,
        timeout=float(meta.get("timeout", 900)),
        max_consecutive_failures=int(meta.get("max_failures", 5)),
    )
    done = set()
    if path.is_file():
        rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        if rows and rows[0] != header(meta, seed):
            raise ValueError(f"{path.name} is from another run")
        done = {row["doc_id"] for row in rows[1:]}
    else:
        path.write_text(json.dumps(header(meta, seed), ensure_ascii=False) + "\n", "utf-8")
    predict(WARM_UP_TEXT)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for doc in docs:
            if doc["doc_id"] in done:
                continue
            before = dict(predict.stats)
            started = time.perf_counter()
            found = dedupe([(int(s), int(e), str(t)) for s, e, t in predict(doc["text"])])
            latency = time.perf_counter() - started
            delta = {k: v - before.get(k, 0) for k, v in predict.stats.items()}
            if delta.get("http_errors"):
                continue  # the harness asks these again
            row = {
                "doc_id": doc["doc_id"],
                "text_sha256": hashlib.sha256(doc["text"].encode("utf-8")).hexdigest(),
                "spans": [list(span) for span in found],
                "latency_seconds": latency,
                "stats": delta,
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
    return dict(predict.stats)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmark.yrss_v2.colab_run")
    parser.add_argument("docs", help="JSON Lines of doc_id and text")
    parser.add_argument("meta", help="JSON with model, base_url, split, corpus_sha256")
    parser.add_argument("out_dir")
    parser.add_argument("--seeds", default="1,2,3,4,5")
    args = parser.parse_args(argv)
    docs = [json.loads(x) for x in Path(args.docs).read_text("utf-8").splitlines() if x.strip()]
    meta = json.loads(Path(args.meta).read_text("utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seeds = [int(s) for s in args.seeds.split(",")]
    results: dict[int, object] = {}

    def work(seed: int) -> None:
        try:
            results[seed] = run_seed(docs, meta, seed, out_dir)
        except Exception as exc:  # report every seed, then fail
            results[seed] = f"failed: {type(exc).__name__}: {exc}"

    threads = [threading.Thread(target=work, args=(seed,)) for seed in seeds]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print(json.dumps({str(k): v for k, v in sorted(results.items())}, ensure_ascii=False))
    return 0 if all(isinstance(v, dict) for v in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
