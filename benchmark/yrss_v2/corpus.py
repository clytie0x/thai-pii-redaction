"""Build the YRSS evaluation v2 corpus from authored templates.

A template is Thai text with ``{{kind}}`` or ``{{kind:key}}`` placeholders.
The generator fills each one with a seeded value and records the label span,
so gold comes from construction and never from a detector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import values
from .types import DECOY_KINDS, LABELED_KINDS, SCHEME_TYPES

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "yrss-v2"
SEEDS = {"dev": 20261113, "test": 20261114}
VARIANTS = {"dev": 3, "test": 4}
VERSION = "yrss-eval-v2"

_PLACEHOLDER = re.compile(r"\{\{([a-z_0-9]+)(?::([a-z0-9_]+))?\}\}")
_LONG_DIGITS = re.compile(r"[0-9๐-๙]{5,}")
# Share of generated values printed in Thai digits, for kinds where forms do that.
_THAI_DIGIT_RATE = 0.08
_THAI_DIGIT_KINDS = frozenset({"thai_id", "phone", "dob", "date"})


@dataclass(frozen=True)
class Template:
    family: str
    genre: str
    negative: bool
    text: str


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    entity_type: str


@dataclass(frozen=True)
class Document:
    doc_id: str
    family: str
    genre: str
    text: str
    spans: tuple[Span, ...]


@dataclass(frozen=True)
class Corpus:
    version: str
    split: str
    seed: int
    templates_sha256: str
    documents: tuple[Document, ...]


def templates_path(split: str) -> Path:
    return DATA_DIR / f"{split}-templates.jsonl"


def lock_path(split: str) -> Path:
    return DATA_DIR / f"{split}.lock.json"


def load_templates(split: str) -> list[Template]:
    rows = []
    for line in templates_path(split).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows.append(Template(row["family"], row["genre"], bool(row["negative"]), row["text"]))
    return rows


def _kinds(template: Template) -> list[str]:
    return [match.group(1) for match in _PLACEHOLDER.finditer(template.text)]


def validate_templates(templates: list[Template]) -> list[str]:
    """Return error kinds. Messages never carry template text."""
    errors: list[str] = []
    seen: set[str] = set()
    for template in templates:
        if template.family in seen:
            errors.append("duplicate-family")
        seen.add(template.family)
        kinds = _kinds(template)
        fixed = _PLACEHOLDER.sub(" ", template.text)
        if "{" in fixed or "}" in fixed:
            errors.append("stray-brace")
        if any(kind not in LABELED_KINDS and kind not in DECOY_KINDS for kind in kinds):
            errors.append("unknown-placeholder")
        if _LONG_DIGITS.search(fixed):
            errors.append("long-digit-run-in-fixed-text")
        if "@" in fixed:
            errors.append("at-sign-in-fixed-text")
        labeled = [kind for kind in kinds if kind in LABELED_KINDS]
        if template.negative and labeled:
            errors.append("negative-has-labeled-placeholder")
        if not template.negative and not labeled:
            errors.append("positive-without-labeled-placeholder")
    return errors


def _value(rng: random.Random, kind: str, used: set[str]) -> str:
    for _ in range(100):
        if kind == "name":
            value = values.person(rng)[0]
        elif kind == "name_en":
            value = values.person(rng)[1]
        else:
            value = values.FACTORIES[kind](rng)
            if kind in _THAI_DIGIT_KINDS and rng.random() < _THAI_DIGIT_RATE:
                value = values.thai_digits(value)
        if value not in used:
            used.add(value)
            return value
    raise RuntimeError(f"exhausted-{kind}")


def render(template: Template, variant: int, *, seed: int) -> Document:
    """Fill one template. The seed mixes in the family, so order does not matter."""
    digest = hashlib.sha256(f"{seed}:{template.family}:{variant}".encode()).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    parts: list[str] = []
    spans: list[Span] = []
    keyed: dict[tuple[str, str], str] = {}
    used: set[str] = set()
    cursor = 0
    length = 0
    for match in _PLACEHOLDER.finditer(template.text):
        kind, key = match.group(1), match.group(2)
        if kind not in LABELED_KINDS and kind not in DECOY_KINDS:
            raise ValueError("unknown-placeholder")
        fixed = template.text[cursor : match.start()]
        parts.append(fixed)
        length += len(fixed)
        if key is None:
            value = _value(rng, kind, used)
        else:
            if (kind, key) not in keyed:
                keyed[(kind, key)] = _value(rng, kind, used)
            value = keyed[(kind, key)]
        if kind in LABELED_KINDS:
            spans.append(Span(length, length + len(value), LABELED_KINDS[kind]))
        parts.append(value)
        length += len(value)
        cursor = match.end()
    parts.append(template.text[cursor:])
    return Document(
        doc_id=f"{template.family}-v{variant}",
        family=template.family,
        genre=template.genre,
        text="".join(parts),
        spans=tuple(spans),
    )


def build_corpus(split: str) -> Corpus:
    raw = templates_path(split).read_bytes()
    seed = SEEDS[split]
    documents = [
        render(template, variant, seed=seed)
        for template in load_templates(split)
        for variant in range(VARIANTS[split])
    ]
    return Corpus(VERSION, split, seed, hashlib.sha256(raw).hexdigest(), tuple(documents))


def validate_corpus(corpus: Corpus) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for doc in corpus.documents:
        if doc.doc_id in seen:
            errors.append("duplicate-doc-id")
        seen.add(doc.doc_id)
        if "{{" in doc.text or "}}" in doc.text:
            errors.append("unfilled-placeholder")
        cursor = 0
        for span in doc.spans:
            if not 0 <= span.start < span.end <= len(doc.text):
                errors.append("span-out-of-range")
                continue
            if span.start < cursor:
                errors.append("span-overlap")
            cursor = span.end
            surface = doc.text[span.start : span.end]
            if surface != surface.strip():
                errors.append("span-has-outer-space")
            if span.entity_type not in SCHEME_TYPES:
                errors.append("unknown-entity-type")
            number = values.digits(surface.translate(str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")))
            if span.entity_type == "THAI_ID" and not values.thai_id_valid(number):
                errors.append("invalid-thai-id")
            if span.entity_type == "CREDIT_CARD" and not values.luhn_valid(number):
                errors.append("invalid-card")
    return errors


def canonical_bytes(corpus: Corpus) -> bytes:
    payload = {
        "documents": [
            {
                "doc_id": doc.doc_id,
                "family": doc.family,
                "genre": doc.genre,
                "spans": [[span.start, span.end, span.entity_type] for span in doc.spans],
                "text": doc.text,
            }
            for doc in corpus.documents
        ],
        "seed": corpus.seed,
        "split": corpus.split,
        "version": corpus.version,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def public_lock(corpus: Corpus) -> dict:
    """Hashes and counts only. No document text and no values."""
    type_counts = Counter(span.entity_type for doc in corpus.documents for span in doc.spans)
    family_counts: dict[str, set[str]] = {entity_type: set() for entity_type in SCHEME_TYPES}
    for doc in corpus.documents:
        for span in doc.spans:
            family_counts[span.entity_type].add(doc.family)
    return {
        "documents": len(corpus.documents),
        "entities": sum(type_counts.values()),
        "families": len({doc.family for doc in corpus.documents}),
        "families_per_type": {t: len(family_counts[t]) for t in SCHEME_TYPES},
        "generator": "benchmark/yrss_v2/corpus.py",
        "genre_counts": dict(sorted(Counter(doc.genre for doc in corpus.documents).items())),
        "negative_documents": sum(1 for doc in corpus.documents if not doc.spans),
        "plaintext_sha256": hashlib.sha256(canonical_bytes(corpus)).hexdigest(),
        "protocol": "docs/decisions/2026-11-13-yrss-eval-v2.md",
        "seed": corpus.seed,
        "split": corpus.split,
        "templates_sha256": corpus.templates_sha256,
        "type_counts": {t: type_counts.get(t, 0) for t in SCHEME_TYPES},
        "variants_per_family": VARIANTS[corpus.split],
        "version": corpus.version,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check or lock a YRSS evaluation v2 split.")
    parser.add_argument("--split", choices=sorted(SEEDS), default="dev")
    parser.add_argument("--write-lock", action="store_true")
    args = parser.parse_args(argv)
    errors = validate_templates(load_templates(args.split))
    corpus = build_corpus(args.split)
    errors += validate_corpus(corpus)
    if errors:
        print(json.dumps(dict(Counter(errors)), sort_keys=True))
        return 1
    lock = public_lock(corpus)
    if args.write_lock:
        lock_path(args.split).write_text(
            json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    elif lock != json.loads(lock_path(args.split).read_text(encoding="utf-8")):
        print("lock-mismatch")
        return 1
    print(json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
