"""Visible synthetic representation study; never reads held-out documents.

Perturbations share seed/template families and are dependent development probes,
not independent samples for a population-level confidence interval.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from pii_redactor.anonymizer import fp_generator as fg
from pii_redactor.detectors import aggregate
from pii_redactor.stateless import (
    StatelessLeakError,
    StatelessProcessingError,
    restore_stateless,
    sanitize_stateless,
)

from .campaign import manifest, offline


def cases(seeds: int = 12):
    rows = []
    for seed in range(seeds):
        rng = random.Random(20261031 + seed)
        values = [
            ("PHONE", "โทร ", fg._gen_phone(rng)),
            ("THAI_ID", "เลขบัตรประชาชน ", fg._gen_thai_id(rng)),
            ("EMAIL", "อีเมล ", fg._gen_email(rng)),
            ("CREDIT_CARD", "บัตรเครดิต ", fg._gen_credit_card(rng)),
            ("IBAN", "IBAN ", "GB82 WEST 1234 5698 7654 32"),
        ]
        for label, cue, value in values:
            compact = re.sub(r"[ -]", "", value)
            profiles = {
                "original": value,
                "format_control": value[:3] + "\u200b" + value[3:],
                "full_width": "".join(
                    chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in value
                ),
                "repeated_separator": "  ".join(
                    compact[i : i + 4] for i in range(0, len(compact), 4)
                ),
            }
            mixed = profiles["repeated_separator"]
            profiles["combined"] = mixed[:5] + "\u200b" + mixed[5:]
            for profile, changed in profiles.items():
                prefix = "ยอดชำระ 250 บาท; " + cue
                text = prefix + changed + " จบงาน"
                rows.append(
                    (f"{label}-{seed}", profile, text, len(prefix), len(prefix) + len(changed))
                )
    return rows


def measure(rows, *, recovery: bool, mode: str) -> dict:
    counts = Counter(documents=len(rows))
    context = (
        patch.object(aggregate, "recover_structured", lambda text: [])
        if not recovery
        else patch.object(aggregate, "recover_structured", aggregate.recover_structured)
    )
    with context:
        for _, _, text, start, end in rows:
            counts["nonpii_characters"] += len(text) - (end - start)
            try:
                result = sanitize_stateless(text, mode=mode, salt="synthetic-study")
            except StatelessLeakError:
                counts["blocked"] += 1
                continue
            except StatelessProcessingError:
                counts["processing_failure"] += 1
                continue
            counts["released"] += 1
            covered = {i for e in result.entities for i in range(e["start"], e["end"])}
            required = {i for i in range(start, end) if not text[i].isspace()}
            counts["safe_release" if required <= covered else "unsafe_release"] += 1
            counts["released_uncovered_characters"] += len(required - covered)
            counts["nonpii_masked_characters"] += len(covered - set(range(start, end)))
            counts["utility_preserved"] += int("250 บาท" in result.sanitized_text)
            try:
                restored = restore_stateless(
                    result.sanitized_text, mapping=result.mapping, mode=mode
                )
                counts["restore_exact"] += int(restored.restored_text == text)
            except (StatelessProcessingError, ValueError):
                counts["restore_failure"] += 1
    for key in (
        "safe_release",
        "unsafe_release",
        "blocked",
        "released",
        "restore_exact",
        "utility_preserved",
        "nonpii_masked_characters",
        "released_uncovered_characters",
    ):
        counts.setdefault(key, 0)
    return dict(counts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seeds", type=int, default=12)
    args = parser.parse_args(argv)
    if args.out.exists():
        raise FileExistsError("study output already exists")
    all_rows = cases(args.seeds)
    with offline():
        result = {
            "manifest": manifest(),
            "base_families": len({r[0] for r in all_rows}),
            "variants": len(all_rows),
            "limits": "Visible constructed dependent development probes; no generalisation CI or real-document claim.",
            "results": {},
        }
        for mode in ("token", "surrogate"):
            result["results"][mode] = {}
            for profile in sorted({r[1] for r in all_rows}):
                selected = [r for r in all_rows if r[1] == profile]
                result["results"][mode][profile] = {
                    arm: measure(selected, recovery=enabled, mode=mode)
                    for arm, enabled in (("raw", False), ("recovery", True))
                }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result["results"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
