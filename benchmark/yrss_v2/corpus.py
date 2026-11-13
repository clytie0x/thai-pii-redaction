"""Build the YRSS evaluation v2 corpus from authored templates.

A template is Thai text with ``{{kind}}`` or ``{{kind:key}}`` placeholders.
The generator fills each one with a seeded value and records the label span,
so gold comes from construction and never from a detector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from benchmark import blind

from . import values
from .types import DECOY_KINDS, LABELED_KINDS, SCHEME_TYPES

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "yrss-v2"
SEEDS = {"dev": 20261113, "test": 20261114}
VARIANTS = {"dev": 3, "test": 4}
VERSION = "yrss-eval-v2"
KEY_ENV = "YRSS_V2_TEST_KEY_FILE"  # a path to the key file, never the key
BLIND_VERSION = "yrss-v2-test"

_PLACEHOLDER = re.compile(r"\{\{([a-z_0-9]+)(?::([a-z0-9_]+))?\}\}")
_LONG_DIGITS = re.compile(r"[0-9๐-๙]{5,}")
# Share of generated values printed in Thai digits, for kinds where forms do that.
_THAI_DIGIT_RATE = 0.08
_THAI_DIGIT_KINDS = frozenset({"thai_id", "phone", "dob", "date"})
_LATIN = re.compile(r"[A-Za-z]")

# Test-split size targets from the pre-registration.
TARGET_DOCUMENTS = 800
TARGET_FAMILIES = 200
TARGET_NEGATIVE_DOCUMENTS = 160
TARGET_TYPE_COUNT = 150  # minimum entities of every scheme type

# validate_realism thresholds.
MIN_CONSONANTS = 40  # fewer Thai consonants than this is too short to judge marks
MAX_MARK_RATIO = 0.05  # marks per consonant; real Thai text sits well above this
GLUED_MIN_PLACEHOLDERS = 3  # fewer fields than this cannot look glued
GLUED_SHARE = 0.75  # share of fields with no space on either side
NEAR_DUPLICATE_JACCARD = 0.5  # character 5-gram overlap between two families
NGRAM = 5
MAX_GENRE_SHARE = 0.15  # one genre may not dominate the families
MIN_SHORT_SHARE = 0.10  # families of at most SHORT_LINES lines
SHORT_LINES = 2
MIN_LONG_SHARE = 0.05  # families over LONG_CHARS of fixed text
LONG_CHARS = 600
_FAMILY_ID = re.compile(r"[0-9a-f]{12}")
_TITLES = ("นางสาว", "นาง", "นาย", "น.ส.", "คุณ", "ดร.", "ด.ช.", "ด.ญ.")
_MARKS = frozenset(chr(c) for c in (0x0E31, *range(0x0E34, 0x0E3B), *range(0x0E47, 0x0E4F)))
_CONSONANTS = frozenset(chr(c) for c in range(0x0E01, 0x0E2F))


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


class CorpusSealError(RuntimeError):
    """Sealing or opening the test templates failed. Messages carry no text or key."""


def _enc_path(data_dir: Path) -> Path:
    # Beside the data dir, so the `benchmark/data/*.enc -text` rule covers it.
    return data_dir.parent / f"{BLIND_VERSION}.enc"


def _template_bytes(split: str) -> bytes:
    """Template file bytes. The test split is decrypted in memory, never written out."""
    if split != "test":
        return templates_path(split).read_bytes()
    key_file = os.environ.get(KEY_ENV)
    if not key_file:
        raise CorpusSealError(f"set {KEY_ENV} to the path of the test key file")
    try:
        blob = _enc_path(DATA_DIR).read_bytes()
        expected = json.loads(lock_path("test").read_text(encoding="utf-8"))["ciphertext_sha256"]
    except (OSError, ValueError, KeyError):
        raise CorpusSealError("the test ciphertext or its lock is missing or unreadable") from None
    if hashlib.sha256(blob).hexdigest() != expected:
        raise CorpusSealError("the test ciphertext hash does not match its lock")
    try:
        version, plaintext = blind.decrypt(blob, blind.load_master(key_file))
    except blind.BlindError as exc:
        raise CorpusSealError(str(exc)) from None
    if version != BLIND_VERSION:
        raise CorpusSealError("the test ciphertext has the wrong version")
    return plaintext


def load_templates(split: str) -> list[Template]:
    return _parse(_template_bytes(split))


def _parse(raw: bytes) -> list[Template]:
    rows = []
    for line in raw.decode("utf-8").splitlines():
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


def _value(rng: random.Random, kind: str, used: set[str], strict: bool = False) -> str:
    for _ in range(100):
        if kind == "name":
            value = values.person(rng)[0]
        elif kind == "name_en":
            value = values.person(rng)[1]
        else:
            value = values.FACTORIES[kind](rng)
            if kind in _THAI_DIGIT_KINDS and rng.random() < _THAI_DIGIT_RATE:
                # Strict (test) keeps Latin-month dates in Western digits.
                if not (strict and _LATIN.search(value)):
                    value = values.thai_digits(value)
        if value not in used:
            used.add(value)
            return value
    raise RuntimeError(f"exhausted-{kind}")


def render(template: Template, variant: int, *, seed: int, strict: bool = False) -> Document:
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
            value = _value(rng, kind, used, strict)
        else:
            if (kind, key) not in keyed:
                keyed[(kind, key)] = _value(rng, kind, used, strict)
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


def build_corpus(split: str, raw: bytes | None = None) -> Corpus:
    raw = _template_bytes(split) if raw is None else raw
    seed = SEEDS[split]
    documents = [
        render(template, variant, seed=seed, strict=split == "test")
        for template in _parse(raw)
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


def check_targets(lock: dict) -> list[str]:
    """Return error kinds for a test lock that misses the registered size."""
    errors = []
    if lock["documents"] != TARGET_DOCUMENTS:
        errors.append("documents-not-800")
    if lock["families"] != TARGET_FAMILIES:
        errors.append("families-not-200")
    if lock["variants_per_family"] != 4:
        errors.append("variants-not-4")
    if lock["negative_documents"] != TARGET_NEGATIVE_DOCUMENTS:
        errors.append("negative-documents-not-160")
    counts = lock["type_counts"]
    errors += [f"type-below-150:{t}" for t in SCHEME_TYPES if counts.get(t, 0) < TARGET_TYPE_COUNT]
    return errors


def _fixed(template: Template) -> str:
    return _PLACEHOLDER.sub("", template.text)


def _ngrams(text: str) -> set[str]:
    return {text[i : i + NGRAM] for i in range(len(text) - NGRAM + 1)}


def _is_glued(text: str, match: re.Match) -> bool:
    before, after = text[: match.start()], text[match.end() :]
    if not before or before[-1].isspace() or not after or after[0].isspace():
        return False
    # A title right before a name reads as spaced.
    return not (match.group(1) == "name" and before.endswith(_TITLES))


def validate_realism(templates: list[Template], *, dev_templates: list[Template]) -> list[str]:
    """Test-split realism checks. Returns ``kind:family`` strings, never template text."""
    errors: list[str] = []
    for t in templates:
        fixed = _fixed(t)
        consonants = sum(c in _CONSONANTS for c in fixed)
        marks = sum(c in _MARKS for c in fixed)
        if consonants >= MIN_CONSONANTS and marks / consonants < MAX_MARK_RATIO:
            errors.append(f"marks-stripped:{t.family}")
        found = list(_PLACEHOLDER.finditer(t.text))
        if (
            len(found) >= GLUED_MIN_PLACEHOLDERS
            and sum(_is_glued(t.text, m) for m in found) / len(found) >= GLUED_SHARE
        ):
            errors.append(f"fields-glued:{t.family}")
        if not _FAMILY_ID.fullmatch(t.family):
            errors.append(f"family-id-not-opaque:{t.family}")
        if "neg" in t.genre:
            errors.append(f"genre-reveals-negative:{t.family}")
    grams = [(t.family, _ngrams(_fixed(t))) for t in templates]
    others = grams + [(d.family, _ngrams(_fixed(d))) for d in dev_templates]
    for i, (family, a) in enumerate(grams):
        for j, (other, b) in enumerate(others):
            if i != j and a and b and len(a & b) / len(a | b) > NEAR_DUPLICATE_JACCARD:
                errors.append(f"near-duplicate-family:{family}")
                break
    total = len(templates)
    if total:
        genres = Counter(t.genre for t in templates)
        errors += [
            f"genre-over-15pct:{g}" for g, n in genres.items() if n / total > MAX_GENRE_SHARE
        ]
        lines = [len([x for x in t.text.splitlines() if x.strip()]) for t in templates]
        if sum(n <= SHORT_LINES for n in lines) / total < MIN_SHORT_SHARE:
            errors.append("too-few-short-families")
        if sum(len(_fixed(t)) > LONG_CHARS for t in templates) / total < MIN_LONG_SHARE:
            errors.append("too-few-long-families")
    return errors


def seal(draft_path: str | Path, key_path: str | Path, *, data_dir: Path | None = None) -> dict:
    """Validate a draft kept outside every work tree, then write the .enc and its lock.

    There is no overwrite option: a sealed test split is replaced only by hand.
    """
    from . import agreement  # agreement imports this module

    data_dir = DATA_DIR if data_dir is None else Path(data_dir)
    draft_path = Path(draft_path)
    enc, lock_file = _enc_path(data_dir), data_dir / "test.lock.json"
    if agreement.inside_work_tree(draft_path):
        raise CorpusSealError("the draft is inside a repository work tree")
    if enc.exists() or lock_file.exists():
        raise CorpusSealError("the test ciphertext or lock already exists")
    raw = draft_path.read_bytes()
    try:
        templates = _parse(raw)
        dev = _parse((data_dir / "dev-templates.jsonl").read_bytes())
    except (OSError, ValueError, KeyError):
        raise CorpusSealError("a template file is unreadable") from None
    errors = validate_templates(templates)
    errors += validate_realism(templates, dev_templates=dev)
    master = blind.load_master(key_path)
    built = build_corpus("test", raw)
    errors += validate_corpus(built)
    lock = public_lock(built)
    errors += check_targets(lock)
    if errors:
        raise CorpusSealError("draft refused: " + ",".join(sorted(set(errors))))
    blob = blind.encrypt(raw, master, BLIND_VERSION)
    lock["ciphertext_sha256"] = hashlib.sha256(blob).hexdigest()
    enc.write_bytes(blob)
    lock_file.write_text(
        json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return lock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check or lock a YRSS evaluation v2 split.")
    parser.add_argument("--split", choices=sorted(SEEDS), default="dev")
    parser.add_argument("--write-lock", action="store_true")
    parser.add_argument("command", nargs="?", choices=["seal"])
    parser.add_argument("--draft")
    args = parser.parse_args(argv)
    if args.command == "seal":
        if not args.draft or not os.environ.get(KEY_ENV):
            parser.error(f"seal needs --draft and {KEY_ENV}")
        try:
            lock = seal(args.draft, os.environ[KEY_ENV])
        except (CorpusSealError, blind.BlindError) as exc:
            print(f"seal-refused: {exc}")
            return 1
        print(json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.write_lock and args.split == "test":
        parser.error("the test lock is written by seal only")
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
