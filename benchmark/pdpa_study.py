"""Fresh scoped category/attribution comparison. No old held-out corpus access."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from pii_redactor.pdpa_assessment import assess_text
from pii_redactor.pdpa_catalog import GENERAL, MODALITIES, SENSITIVE, STRATEGIES

from .campaign import file_digest, offline
from .scorer import _prf

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "research/pdpa-coverage"
ATTRIBUTIONS = {"personal", "topic", "ambiguous"}


def records_from_bytes(raw: bytes, split: str) -> list[dict]:
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    ids, families = set(), set()
    for row in rows:
        if (
            row.get("split") != split
            or not isinstance(row.get("text"), str)
            or len(row["text"]) > 20000
            or row.get("modality") not in MODALITIES
            or row.get("scope") not in {"sensitive", "general", "modality"}
        ):
            raise ValueError("corpus schema mismatch")
        if row["doc_id"] in ids or row["family_id"] in families:
            raise ValueError("corpus family mismatch")
        ids.add(row["doc_id"])
        families.add(row["family_id"])
        allowed = set(SENSITIVE if row["scope"] == "sensitive" else GENERAL)
        for target in row["targets"]:
            if target["category"] not in allowed or target["attribution"] not in ATTRIBUTIONS:
                raise ValueError("corpus target mismatch")
        if row["scope"] == "modality" and (row["targets"] or row["modality"] == "text"):
            raise ValueError("corpus modality mismatch")
    return rows


def score_predictions(records, reports) -> dict:
    if len(records) != len(reports):
        raise ValueError("incomplete study predictions")
    counts = {name: Counter() for name in ("personal", "topic", "joint")}
    categories = {c: Counter() for c in (*SENSITIVE, *GENERAL)}
    denominators = Counter()
    for row, report in zip(records, reports):
        if row["scope"] == "modality":
            denominators["unsupported_records"] += 1
            denominators["unsupported_reviewed"] += int(
                report["engine"]["status"] == "not_assessed"
                and "review_modality" in report.get("review_reasons", [])
            )
            continue
        allowed = set(SENSITIVE if row["scope"] == "sensitive" else GENERAL)
        gold = {(t["category"], t["attribution"]) for t in row["targets"]}
        predicted = {
            (t["category"], t["attribution"])
            for t in report["findings"]
            if t["category"] in allowed
        }
        gp = {c for c, a in gold if a == "personal"}
        pp = {c for c, a in predicted if a == "personal"}
        views = {
            "personal": (gp, pp),
            "topic": ({c for c, a in gold}, {c for c, a in predicted}),
            "joint": (gold, predicted),
        }
        for name, (truth, pred) in views.items():
            counts[name].update(tp=len(truth & pred), fp=len(pred - truth), fn=len(truth - pred))
        for category in allowed:
            categories[category].update(
                tp=int(category in gp & pp),
                fp=int(category in pp - gp),
                fn=int(category in gp - pp),
            )
        denominators["text_records"] += 1
        reviewed = any(a in {"personal", "ambiguous"} for c, a in predicted)
        denominators["reviewed_records"] += int(reviewed)
        if gold and all(a == "topic" for c, a in gold):
            denominators["topic_only_records"] += 1
            denominators["topic_only_false_alerts"] += int(bool(pp))
            denominators["topic_only_reviewed"] += int(reviewed)
    result = {
        name: {
            **{k: value.get(k, 0) for k in ("tp", "fp", "fn")},
            **_prf(*(value.get(k, 0) for k in ("tp", "fp", "fn"))),
        }
        for name, value in counts.items()
    }
    result["by_category"] = {
        category: {
            **{k: v.get(k, 0) for k in ("tp", "fp", "fn")},
            **_prf(*(v.get(k, 0) for k in ("tp", "fp", "fn"))),
        }
        for category, v in categories.items()
    }
    result["macro_personal_f2"] = statistics.mean(v["f2"] for v in result["by_category"].values())
    legacy = set(SENSITIVE) - {"GENETIC_DATA", "BIOMETRIC_IDENTITY"}
    result["shared_legacy_sensitive_macro_f2"] = statistics.mean(
        result["by_category"][c]["f2"] for c in legacy
    )
    result.update(denominators)
    result["topic_only_false_alert_rate"] = denominators["topic_only_false_alerts"] / max(
        1, denominators["topic_only_records"]
    )
    result["topic_only_review_rate"] = denominators["topic_only_reviewed"] / max(
        1, denominators["topic_only_records"]
    )
    return result


def source_identity() -> dict:
    from pythainlp.corpus import get_corpus_db_detail, get_corpus_default_db
    from pythainlp.tools import get_full_data_path

    ner_path = get_corpus_default_db("thainer-1.4", version="1.4")
    if ner_path is None:
        filename = get_corpus_db_detail("thainer-1.4", version="1.4").get("filename")
        if not filename:
            raise ValueError("local NER identity missing")
        ner_path = get_full_data_path(filename)
    paths = [
        *sorted((ROOT / "pii_redactor").rglob("*.py")),
        ROOT / "ai_guard.py",
        Path(__file__),
        *(
            ROOT / "benchmark" / name
            for name in ("scorer.py", "campaign.py", "blind.py", "gold.py")
        ),
    ]
    files = {p.relative_to(ROOT).as_posix(): file_digest(p) for p in paths}
    return {
        "python": platform.python_version(),
        "ner_asset_sha256": hashlib.sha256(Path(ner_path).read_bytes()).hexdigest(),
        "protocol_sha256": file_digest(ROOT / "docs/research/pdpa-coverage-plan.md"),
        "corpus_lock_sha256": file_digest(DATA / "context-evaluation.lock.json"),
        "source_files": files,
        "source_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        "packages": dict(
            sorted(
                (d.metadata["Name"].lower(), d.version) for d in importlib.metadata.distributions()
            )
        ),
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
    }


def run_arm(records, strategy, threshold, model) -> dict:
    reports, timings = [], []
    for row in records:
        start = time.perf_counter()
        # Labels, IDs, scope and split never enter a detector.
        report = assess_text(
            row["text"],
            strategy=strategy,
            modality=row["modality"],
            semantic_backend=model if strategy == "hybrid" else None,
            threshold=threshold,
        )
        elapsed = time.perf_counter() - start
        if row["modality"] == "text":
            timings.append(elapsed * 1000)
        reports.append(report)
    score = score_predictions(records, reports)
    ordered = sorted(timings)
    score["warm_ms"] = {
        "p50": statistics.median(ordered),
        "p95": ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))],
        "text_records": len(ordered),
    }
    score["ner_chunks"] = {
        k: sum(r["engine"]["ner_chunks"][k] for r in reports)
        for k in ("attempted", "succeeded", "skipped")
    }
    return score


def select_configuration(results: dict) -> dict:
    def choose(pool, fallback):
        eligible = [
            (name, r) for name, r in pool.items() if r["topic_only_false_alert_rate"] <= 0.20
        ]
        if not eligible:
            return fallback, False
        best = max(r["macro_personal_f2"] for name, r in eligible)
        name, _ = min(
            ((name, r) for name, r in eligible if r["macro_personal_f2"] >= best - 0.01),
            key=lambda pair: pair[1]["warm_ms"]["p50"],
        )
        return name, True

    recommended, eligible = choose(results, "contextual")
    hybrids = {name: r for name, r in results.items() if name.startswith("hybrid_")}
    fallback = max(hybrids, key=lambda name: hybrids[name]["macro_personal_f2"])
    hybrid, hybrid_eligible = choose(hybrids, fallback)
    if recommended.startswith("hybrid_"):
        hybrid = recommended
    return {
        "recommended_available_strategy": recommended,
        "hybrid_threshold": float(hybrid.split("_")[1]),
        "eligibility_met": eligible,
        "hybrid_eligibility_met": hybrid_eligible,
    }


def calibrate(path: Path, model) -> dict:
    lock = json.loads((DATA / "context-evaluation.lock.json").read_text())
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != lock["calibration"]["sha256"]:
        raise ValueError("calibration identity mismatch")
    rows = records_from_bytes(raw, "calibration")
    if len(rows) != 70:
        raise ValueError("calibration composition mismatch")
    identity = source_identity()
    results = {
        strategy: run_arm(rows, strategy, 0.50, model) for strategy in ("keyword", "contextual")
    }
    for threshold in (0.40, 0.50, 0.60, 0.70):
        results[f"hybrid_{threshold:.2f}"] = run_arm(rows, "hybrid", threshold, model)
    selected = select_configuration(results)
    if identity != source_identity():
        raise ValueError("calibration source changed")
    return {
        "schema": "pdpa-calibration/1",
        "identity": identity,
        "calibration_sha256": lock["calibration"]["sha256"],
        "records": len(rows),
        "model": model.identity,
        "results": results,
        **selected,
        "operational_default": "contextual_until_optional_model_packaging_review",
        "limits": "Small AI-authored synthetic calibration; similarity is not probability.",
    }


def evaluate(key_file: Path, selection: Path, model) -> dict:
    from .blind import decrypt, load_master

    lock = json.loads((DATA / "context-evaluation.lock.json").read_text())
    chosen = json.loads(selection.read_text())
    if chosen["identity"] != source_identity() or chosen["model"] != model.identity:
        raise ValueError("frozen selection identity mismatch")
    before = source_identity()
    reservation = DATA / "context-evaluation.reservation.json"
    with reservation.open("x") as stream:
        json.dump(
            {
                "status": "reserved",
                "identity": before["source_sha256"],
                "strategies": list(STRATEGIES),
            },
            stream,
        )
    try:
        blob = (DATA / "context-evaluation.enc").read_bytes()
        if hashlib.sha256(blob).hexdigest() != lock["ciphertext_sha256"]:
            raise ValueError("cipher mismatch")
        version, raw = decrypt(blob, load_master(key_file))
        if (
            version != "pdpa-context-v1"
            or hashlib.sha256(raw).hexdigest() != lock["plaintext_sha256"]
        ):
            raise ValueError("corpus mismatch")
        rows = records_from_bytes(raw, "evaluation")
        if len(rows) != 210:
            raise ValueError("evaluation composition mismatch")
        result = {
            "schema": "pdpa-evaluation/1",
            "identity": before,
            "model": model.identity,
            "corpus_sha256": lock["plaintext_sha256"],
            "records": len(rows),
            "threshold": chosen["hybrid_threshold"],
            "selected_on_calibration": chosen["recommended_available_strategy"],
            "results": {
                name: run_arm(rows, name, chosen["hybrid_threshold"], model) for name in STRATEGIES
            },
            "limits": lock["limitations"],
        }
        if before != source_identity():
            raise ValueError("evaluation source changed")
        reservation.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "scored_strategies": 3,
                    "source_sha256": before["source_sha256"],
                    "corpus_sha256": lock["plaintext_sha256"],
                }
            )
            + "\n"
        )
        return result
    except Exception:
        reservation.write_text(json.dumps({"status": "failed", "retry_authorized": False}) + "\n")
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["calibration", "evaluation"], required=True)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists():
        raise FileExistsError("study output already exists")
    for key in (
        "HF_HUB_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "HF_HUB_DISABLE_IMPLICIT_TOKEN",
        "DO_NOT_TRACK",
    ):
        os.environ[key] = "1"
    import torch

    from pii_redactor.pdpa_semantic import semantic_model

    torch.set_num_threads(4)
    with offline():
        start = time.perf_counter()
        model = semantic_model(args.model_dir)
        cold = time.perf_counter() - start
        result = (
            calibrate(args.calibration, model)
            if args.mode == "calibration"
            else evaluate(args.key_file, args.selection, model)
        )
    result["cold_model_load_seconds"] = cold
    result["model_threads"] = 4
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {
                "mode": args.mode,
                "records": result["records"],
                "metrics": {
                    name: {
                        key: r[key]
                        for key in ("macro_personal_f2", "topic_only_false_alert_rate", "warm_ms")
                    }
                    for name, r in result["results"].items()
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"pdpa_study_error: {type(error).__name__}; no content disclosed", file=sys.stderr)
        raise SystemExit(1) from None
