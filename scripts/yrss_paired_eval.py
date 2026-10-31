"""One registered paired held-out disclosure, run only by an isolated evaluator.

Plaintext and per-document sufficient statistics stay in the evaluator process.
Only aggregate results leave this command. There is no retry/force option.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import zipfile
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

BASE = "19fe9f0c209c587c7662ee5302edc752f0fd32c8"
VERSION = "yrss-holdout-v1"
ROOT = Path(__file__).resolve().parents[1]
IDENTITY_FIELDS = (
    "source_sha256",
    "scorer_sha256",
    "model_sha256",
    "pythainlp_assets_sha256",
    "requirements_sha256",
    "corpus_sha256",
    "packages",
    "python",
    "runtime_evaluator_sha256",
    "paired_driver_sha256",
)
SLICE_COUNTS = {
    "address_varied": 12,
    "bank_phone": 11,
    "education": 11,
    "finance": 11,
    "gov_form": 11,
    "id_docs": 19,
    "long_form": 12,
    "medical": 11,
    "messy": 12,
    "name_no_cue": 12,
    "negative": 52,
    "student_id_varied": 11,
}


def reserve(data_dir: Path, identity: dict) -> Path:
    path = data_dir / f"{VERSION}.paired-reservation.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(
            {"status": "reserved", "created": datetime.now(UTC).isoformat(), **identity},
            stream,
            indent=2,
        )
    return path


def public_arm(result: dict) -> dict:
    return {k: v for k, v in result.items() if k != "counts"}


def verify_arm_identity(reference: dict, current: dict) -> None:
    for key in IDENTITY_FIELDS:
        if key not in reference or key not in current or reference[key] != current[key]:
            raise ValueError(f"arm identity mismatch: {key}")


def arm_identity(root: Path) -> dict:
    from pythainlp.corpus import corpus_path, get_corpus_path

    def digest(p):
        return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

    files = {
        p.relative_to(root).as_posix(): digest(p)
        for p in sorted((root / "pii_redactor").rglob("*.py"))
    }
    assets_root = Path(corpus_path())
    assets = {
        p.relative_to(assets_root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(assets_root.rglob("*"))
        if p.is_file() and p.suffix not in (".py", ".pyc")
    }
    return {
        "source_sha256": hashlib.sha256(
            json.dumps(files, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "scorer_sha256": digest(root / "benchmark/scorer.py"),
        "model_sha256": {
            "thainer-1.4": hashlib.sha256(
                Path(get_corpus_path("thainer-1.4")).read_bytes()
            ).hexdigest()
        },
        "pythainlp_assets_sha256": assets,
        "requirements_sha256": digest(root / "requirements.lock"),
        "corpus_sha256": digest(root / "benchmark/data/gold.jsonl"),
        "packages": dict(
            sorted(
                (d.metadata["Name"].lower(), d.version) for d in importlib.metadata.distributions()
            )
        ),
        "python": platform.python_version(),
        "runtime_evaluator_sha256": {
            name: digest(root / "benchmark" / name)
            for name in ("runner.py", "gold.py", "scorer.py", "types.py", "blind.py")
        },
        "paired_driver_sha256": digest(Path(__file__)),
    }


def worker(args) -> dict:
    sys.path.insert(0, str(args.worker_root))
    from benchmark.blind import load_blind
    from benchmark.runner import BenchmarkIntegrityError, predict_samples
    from benchmark.scorer import _prepare_predictions, _score_group, score
    from pii_redactor.detectors.tb_detector import NERChunkDiagnostics

    expected = json.loads(args.identity.read_text(encoding="utf-8"))["manifest"]
    with ExitStack() as stack:

        def denied(*a, **k):
            raise RuntimeError("evaluation network disabled")

        stack.enter_context(patch.dict(os.environ, {"PYTHAINLP_OFFLINE": "1"}))
        stack.enter_context(patch.object(socket, "getaddrinfo", denied))
        for target in ("connect", "connect_ex"):
            stack.enter_context(patch.object(socket.socket, target, denied))
        identity = arm_identity(args.worker_root)
        verify_arm_identity(expected, identity)
        samples, lock = load_blind(args.key_file, data_dir=args.data_dir, version=VERSION)
        diagnostics = NERChunkDiagnostics()
        predictions = predict_samples(samples, "crf", diagnostics=diagnostics)
        if diagnostics.skipped:
            raise BenchmarkIntegrityError(diagnostics.as_dict())
        metrics = score(samples, predictions)
        counts = []
        exposure = {
            "uncovered_entities": 0,
            "partially_uncovered_entities": 0,
            "uncovered_characters": 0,
        }
        for sample, preds in zip(samples, _prepare_predictions(predictions, shared_only=False)):
            _, row = _score_group([sample], [preds])
            counts.append(
                (0, row["false_positives"], 0)
                if row["gold_entities"] == 0
                else (row["tp"], row["fp"], row["fn"])
            )
            covered = {i for start, end, _ in preds for i in range(start, end)}
            for gold in sample.spans:
                missing = len(set(range(gold.start, gold.end)) - covered)
                exposure["uncovered_characters"] += missing
                exposure["uncovered_entities"] += int(missing == gold.end - gold.start)
                exposure["partially_uncovered_entities"] += int(0 < missing < gold.end - gold.start)
        verify_arm_identity(identity, arm_identity(args.worker_root))
    return {
        "metrics": metrics,
        "identity": identity,
        "counts": counts,
        "exposure": exposure,
        "ner_chunks": diagnostics.as_dict(),
        "corpus": {
            k: lock[k] for k in ("version", "plaintext_sha256", "ciphertext_sha256", "documents")
        },
    }


def evaluate(args) -> dict:
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))["manifest"]
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))["manifest"]
    if baseline["git"]["head"] != BASE:
        raise ValueError("baseline commit differs from pre-registration")
    for key in (k for k in IDENTITY_FIELDS[1:] if k != "runtime_evaluator_sha256"):
        if baseline[key] != candidate[key]:
            raise ValueError(f"non-detector comparison drift: {key}")
    for name in ("runner.py", "gold.py", "scorer.py", "types.py"):
        if (
            baseline["runtime_evaluator_sha256"][name]
            != candidate["runtime_evaluator_sha256"][name]
        ):
            raise ValueError("runtime evaluator comparison drift")
    # The sole registered loader-file change aligns freeze validation with the
    # written maximal-token rule. No other parser/loader difference is allowed.
    old_blind = subprocess.check_output(
        ["git", "show", f"{BASE}:benchmark/blind.py"], cwd=ROOT
    ).replace(b"\r\n", b"\n")
    old_rule = b'if re.search(r"\\d{13}", stripped):'
    new_rule = b'if re.search(r"(?<!\\d)\\d{13}(?!\\d)", stripped):'
    if (
        old_blind.count(old_rule) != 1
        or hashlib.sha256(old_blind.replace(old_rule, new_rule)).hexdigest()
        != candidate["runtime_evaluator_sha256"]["blind.py"]
    ):
        raise ValueError("unregistered blind-loader difference")
    if args.out.exists():
        raise FileExistsError("paired output already exists")
    lock = json.loads((args.data_dir / f"{VERSION}.lock.json").read_text(encoding="utf-8"))
    if (
        lock.get("documents") != 185
        or lock.get("slice_counts") != SLICE_COUNTS
        or lock.get("reveal_budget") != 2
    ):
        raise ValueError("held-out composition differs from pre-registration")
    reservation = reserve(
        args.data_dir,
        {
            "baseline_source_sha256": baseline["source_sha256"],
            "candidate_source_sha256": candidate["source_sha256"],
        },
    )
    archive = subprocess.check_output(
        ["git", "archive", "--format=zip", BASE, "pii_redactor", "benchmark", "requirements.lock"],
        cwd=ROOT,
    )
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="yrss-baseline-", dir=artifacts) as folder:
            with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
                bundle.extractall(folder)
            results = []
            for root, evidence in ((Path(folder), args.baseline), (ROOT, args.candidate)):
                command = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker-root",
                    str(root),
                    "--identity",
                    str(evidence.resolve()),
                    "--data-dir",
                    str(args.data_dir.resolve()),
                    "--key-file",
                    str(args.key_file.resolve()),
                ]
                process = subprocess.run(
                    command, cwd=root, capture_output=True, check=False, timeout=180
                )
                if process.returncode:
                    raise RuntimeError("isolated evaluation arm failed; no result disclosed")
                results.append(json.loads(process.stdout))
        before, after = results
        if before["corpus"] != after["corpus"]:
            raise ValueError("paired corpus mismatch")
        sys.path.insert(0, str(ROOT))
        from benchmark.campaign import paired_f2_interval

        result = {
            "schema": 1,
            "version": VERSION,
            "protocol": "docs/decisions/2026-10-31-yrss-heldout.md",
            "baseline_commit": BASE,
            "candidate_commit": candidate["git"]["head"],
            "candidate_git_dirty": candidate["git"]["dirty"],
            "driver_sha256": hashlib.sha256(
                Path(__file__).read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest(),
            "baseline": public_arm(before),
            "candidate": public_arm(after),
            "paired_f2": paired_f2_interval(before["counts"], after["counts"]),
            "scored_arms": 2,
            "network": "disabled in both arms",
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
        reservation.write_text(
            json.dumps(
                {
                    **json.loads(reservation.read_text(encoding="utf-8")),
                    "status": "complete",
                    "scored_arms": 2,
                    "report_sha256": hashlib.sha256(args.out.read_bytes()).hexdigest(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return result
    except Exception:
        reservation.write_text(
            json.dumps(
                {
                    **json.loads(reservation.read_text(encoding="utf-8")),
                    "status": "failed",
                    "note": "Integrity failure; no automatic retry authorized.",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "candidate", "data-dir", "key-file", "out", "worker-root", "identity"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    if args.worker_root:
        print(json.dumps(worker(args)))
    else:
        result = evaluate(args)
        print(json.dumps({"paired_f2": result["paired_f2"], "scored_arms": 2}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Evaluation failed: {type(error).__name__}; no content disclosed.", file=sys.stderr)
        raise SystemExit(1) from None
