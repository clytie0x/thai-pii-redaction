"""Build, lock, and seal the YRSS evaluation v3 corpus.

Train and dev render from the public seed. Test values are drawn with a
fingerprint of the key, and the rendered documents are what get encrypted.
``verify`` checks the ciphertext hash and never decrypts.

The key is a file path in ``YRSS_V3_TEST_KEY_FILE``. It is not read from the
repository and it is not printed.

Seal, from outside the repo, after the key file exists::

    YRSS_V3_TEST_KEY_FILE=/path/to/keyfile python -m benchmark.yrss_v3 seal
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
from benchmark.yrss_v2 import values
from benchmark.yrss_v2.agreement import inside_work_tree
from benchmark.yrss_v2.corpus import (
    _THAI_DIGIT_KINDS,
    _THAI_DIGIT_RATE,
    NEAR_DUPLICATE_JACCARD,
    NGRAM,
)
from benchmark.yrss_v2.types import DECOY_KINDS, LABELED_KINDS, SCHEME_TYPES

from . import families, qi
from .families import FamilyTemplate
from .protocol import BLIND_VERSION, KEY_ENV, MIN_COPY_CHARS, PROTOCOL, VERSION
from .qi import QiSpan

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "yrss-v3"
# Public seeds. Test values also mix in the key, so the seed alone is not the corpus.
SEEDS = {"train": 20261117, "dev": 20261118, "test": 20261119}
VARIANTS = {"train": 2, "dev": 2, "test": 2}
GENERATOR = "benchmark/yrss_v3/corpus.py"
V2_DEV_TEMPLATES = DATA_DIR.parent / "yrss-v2" / "dev-templates.jsonl"

_PLACEHOLDER = re.compile(r"\{\{([a-z_0-9]+)(?::([a-z0-9_]+))?\}\}")
_LONG_DIGITS = re.compile(r"[0-9๐-๙]{5,}")
_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_KNOWN_KINDS = set(LABELED_KINDS) | set(DECOY_KINDS) | set(qi.QI_KINDS)
# Kinds that may be printed in Thai digits. QI dates and ages join the v2 set.
_THAI_DIGIT_OK = set(_THAI_DIGIT_KINDS) | {"be_date", "age"}


class CorpusSealError(RuntimeError):
    """Sealing or opening test-v3 failed. The message is a short code."""


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
    negative: bool
    text: str
    spans: tuple[Span, ...]
    qi: tuple[QiSpan, ...]


def templates_path(split: str) -> Path:
    if split == "test":
        raise CorpusSealError("test-templates-are-not-a-file")
    return DATA_DIR / f"{split}-templates.jsonl"


def lock_path(split: str) -> Path:
    return DATA_DIR / f"{split}.lock.json"


def enc_path(data_dir: Path | None = None) -> Path:
    root = DATA_DIR if data_dir is None else Path(data_dir)
    return root.parent / f"{BLIND_VERSION}.enc"


def template_bytes(split: str) -> bytes:
    """Canonical JSONL for a split. Test bytes exist only in memory."""
    rows = []
    for template in families.templates(split):
        rows.append(
            json.dumps(
                {
                    "family": template.family,
                    "genre": template.genre,
                    "negative": template.negative,
                    "text": template.text,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return ("\n".join(rows) + "\n").encode("utf-8")


def fixed_text(template: FamilyTemplate) -> str:
    return _PLACEHOLDER.sub("", template.text)


def ngrams(text: str) -> set[str]:
    if len(text) < NGRAM:
        return set()
    return {text[i : i + NGRAM] for i in range(len(text) - NGRAM + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def validate_templates(rows: tuple[FamilyTemplate, ...] | list[FamilyTemplate]) -> list[str]:
    """Error codes only. A code may end with a family id, never with template text."""
    errors: list[str] = []
    seen: set[str] = set()
    for template in rows:
        if template.family in seen:
            errors.append(f"duplicate-family:{template.family}")
        seen.add(template.family)
        kinds = [match.group(1) for match in _PLACEHOLDER.finditer(template.text)]
        fixed = fixed_text(template)
        if "{" in fixed or "}" in fixed:
            errors.append(f"stray-brace:{template.family}")
        if any(kind not in _KNOWN_KINDS for kind in kinds):
            errors.append(f"unknown-placeholder:{template.family}")
        if _LONG_DIGITS.search(fixed):
            errors.append(f"long-digit-run-in-fixed-text:{template.family}")
        if "@" in fixed:
            errors.append(f"at-sign-in-fixed-text:{template.family}")
        labeled = [kind for kind in kinds if kind in LABELED_KINDS]
        qi_kinds = [kind for kind in kinds if kind in qi.QI_KINDS]
        if template.negative and (labeled or qi_kinds):
            errors.append(f"negative-has-personal-placeholder:{template.family}")
        if not template.negative and not labeled:
            errors.append(f"positive-without-labeled-placeholder:{template.family}")
    return errors


def split_of_family(family: str) -> str | None:
    for split in families.SPLITS:
        if family.startswith(f"v3-{split}-"):
            return split
    return None


def disjointness_errors() -> list[str]:
    """Family ids and fixed-text overlap. Does not open the v2 ciphertext."""
    errors: list[str] = []
    grouped = {split: list(families.templates(split)) for split in families.SPLITS}
    seen: dict[str, str] = {}
    grams: list[tuple[str, str, set[str]]] = []
    for split, rows in grouped.items():
        for template in rows:
            owner = split_of_family(template.family)
            if owner != split:
                errors.append(f"family-id-split:{template.family}")
            if template.family in seen:
                errors.append(f"family-crosses-splits:{template.family}")
            seen[template.family] = split
            grams.append((split, template.family, ngrams(fixed_text(template))))
    v2_ids, v2_grams = _v2_dev_fixed()
    for family in seen:
        if family in v2_ids:
            errors.append(f"family-id-in-v2-dev:{family}")
    for index, (split, family, left) in enumerate(grams):
        for other_split, other, right in grams[index + 1 :]:
            if split == other_split and family == other:
                continue
            if jaccard(left, right) > NEAR_DUPLICATE_JACCARD:
                errors.append(f"near-duplicate-family:{family}:{other}")
        for right in v2_grams:
            if jaccard(left, right) > NEAR_DUPLICATE_JACCARD:
                errors.append(f"near-duplicate-v2-dev:{family}")
                break
    return errors


def _v2_dev_fixed() -> tuple[set[str], list[set[str]]]:
    """Read only the committed v2 dev templates. Never the sealed test blob."""
    path = V2_DEV_TEMPLATES
    if path.name != "dev-templates.jsonl":
        raise CorpusSealError("refusing-non-dev-v2-file")
    ids: set[str] = set()
    grams: list[set[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        ids.add(row["family"])
        text = _PLACEHOLDER.sub("", row["text"])
        grams.append(ngrams(text))
    return ids, grams


def contamination_hits(external_text: str, *, split: str = "test") -> list[str]:
    """Family ids whose fixed text is too close to ``external_text``.

    A long document that quotes a family still hits, via a whitespace-insensitive
    substring, even when extra characters would pull the Jaccard score down.
    The return value is ids only.
    """
    hits: list[str] = []
    ext_grams = ngrams(external_text)
    compact_external = "".join(external_text.split())
    for template in families.templates(split):
        fixed = fixed_text(template)
        compact = "".join(fixed.split())
        copied = len(compact) >= MIN_COPY_CHARS and compact in compact_external
        if copied or jaccard(ngrams(fixed), ext_grams) > NEAR_DUPLICATE_JACCARD:
            hits.append(template.family)
    return hits


def _fingerprint(master: bytes) -> bytes:
    return hashlib.sha256(b"yrss-v3-test-values\0" + master).digest()


def _rng(seed: int, family: str, variant: int, fingerprint: bytes | None) -> random.Random:
    prefix = fingerprint or b""
    digest = hashlib.sha256(prefix + f"{seed}:{family}:{variant}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _draw(rng: random.Random, kind: str, used: set[str]) -> str:
    for _ in range(100):
        if kind == "name":
            value = values.person(rng)[0]
        elif kind == "name_en":
            value = values.person(rng)[1]
        elif kind in qi.QI_KINDS:
            value = qi.draw_qi(rng, kind)
        else:
            value = values.FACTORIES[kind](rng)
        if kind in _THAI_DIGIT_OK and rng.random() < _THAI_DIGIT_RATE:
            # Same strict rule as v2: do not mix Thai digits into a Latin-letter value.
            if not re.search(r"[A-Za-z]", value):
                value = values.thai_digits(value)
        if value not in used:
            used.add(value)
            return value
    raise CorpusSealError(f"exhausted-{kind}")


def render(
    template: FamilyTemplate, variant: int, *, seed: int, fingerprint: bytes | None
) -> Document:
    rng = _rng(seed, template.family, variant, fingerprint)
    parts: list[str] = []
    spans: list[Span] = []
    qi_spans: list[QiSpan] = []
    keyed: dict[tuple[str, str], str] = {}
    used: set[str] = set()
    cursor = 0
    length = 0
    for match in _PLACEHOLDER.finditer(template.text):
        kind, key = match.group(1), match.group(2)
        if kind not in _KNOWN_KINDS:
            raise CorpusSealError("unknown-placeholder")
        fixed = template.text[cursor : match.start()]
        parts.append(fixed)
        length += len(fixed)
        if key is None:
            value = _draw(rng, kind, used)
        else:
            slot = (kind, key)
            if slot not in keyed:
                keyed[slot] = _draw(rng, kind, used)
            value = keyed[slot]
        if kind in LABELED_KINDS:
            spans.append(Span(length, length + len(value), LABELED_KINDS[kind]))
        elif kind in qi.QI_KINDS:
            qi_spans.append(QiSpan(length, length + len(value), kind, qi.QI_KINDS[kind]))
        parts.append(value)
        length += len(value)
        cursor = match.end()
    parts.append(template.text[cursor:])
    return Document(
        doc_id=f"{template.family}-v{variant}",
        family=template.family,
        genre=template.genre,
        negative=template.negative,
        text="".join(parts),
        spans=tuple(spans),
        qi=tuple(qi_spans),
    )


def render_split(split: str, *, fingerprint: bytes | None = None) -> tuple[Document, ...]:
    """Render one split. Test rendering requires the 32-byte key fingerprint."""
    if split not in SEEDS:
        raise CorpusSealError("unknown-split")
    if split == "test":
        if fingerprint is None or len(fingerprint) != 32:
            raise CorpusSealError("test-requires-key")
    elif fingerprint is not None:
        raise CorpusSealError("key-not-used-on-this-split")
    seed = SEEDS[split]
    return tuple(
        render(template, variant, seed=seed, fingerprint=fingerprint)
        for template in families.templates(split)
        for variant in range(VARIANTS[split])
    )


def validate_documents(documents: tuple[Document, ...] | list[Document]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for doc in documents:
        if doc.doc_id in seen:
            errors.append("duplicate-doc-id")
        seen.add(doc.doc_id)
        if "{{" in doc.text or "}}" in doc.text:
            errors.append("unfilled-placeholder")
        if doc.negative and (doc.spans or doc.qi):
            errors.append("negative-has-spans")
        cursor = 0
        layers = [(span.start, span.end, span.entity_type, None) for span in doc.spans]
        layers += [(span.start, span.end, span.qi_type, span.section26) for span in doc.qi]
        for start, end, label, section in sorted(layers, key=lambda item: item[0]):
            if not 0 <= start < end <= len(doc.text):
                errors.append("span-out-of-range")
                continue
            if start < cursor:
                errors.append("span-overlap")
            cursor = end
            surface = doc.text[start:end]
            if surface != surface.strip():
                errors.append("span-has-outer-space")
            if label in SCHEME_TYPES:
                number = values.digits(surface.translate(_THAI_DIGITS))
                if label == "THAI_ID" and not values.thai_id_valid(number):
                    errors.append("invalid-thai-id")
                if label == "CREDIT_CARD" and not values.luhn_valid(number):
                    errors.append("invalid-card")
            if section is not None and section not in qi.catalog_section26():
                errors.append("unknown-section26")
    return errors


def canonical_bytes(split: str, documents: tuple[Document, ...], templates_sha256: str) -> bytes:
    payload = {
        "documents": [
            {
                "doc_id": doc.doc_id,
                "family": doc.family,
                "genre": doc.genre,
                "negative": doc.negative,
                "qi": [
                    [span.start, span.end, span.qi_type, span.section26 or ""] for span in doc.qi
                ],
                "spans": [[span.start, span.end, span.entity_type] for span in doc.spans],
                "text": doc.text,
            }
            for doc in documents
        ],
        "seed": SEEDS[split],
        "split": split,
        "templates_sha256": templates_sha256,
        "version": VERSION,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def documents_from_canonical(raw: bytes) -> tuple[str, tuple[Document, ...]]:
    try:
        payload = json.loads(raw.decode("utf-8"))
        documents = []
        for row in payload["documents"]:
            documents.append(
                Document(
                    doc_id=row["doc_id"],
                    family=row["family"],
                    genre=row["genre"],
                    negative=bool(row["negative"]),
                    text=row["text"],
                    spans=tuple(Span(item[0], item[1], item[2]) for item in row["spans"]),
                    qi=tuple(
                        QiSpan(item[0], item[1], item[2], item[3] or None) for item in row["qi"]
                    ),
                )
            )
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError, IndexError):
        raise CorpusSealError("plaintext-unreadable") from None
    return payload["split"], tuple(documents)


def public_lock(split: str, documents: tuple[Document, ...], templates_sha256: str) -> dict:
    """Hashes and counts only. No document text and no values."""
    type_counts = Counter(span.entity_type for doc in documents for span in doc.spans)
    qi_counts = Counter(span.qi_type for doc in documents for span in doc.qi)
    section_counts = Counter(
        span.section26 for doc in documents for span in doc.qi if span.section26
    )
    raw = canonical_bytes(split, documents, templates_sha256)
    return {
        "documents": len(documents),
        "entities": sum(type_counts.values()),
        "families": len({doc.family for doc in documents}),
        "generator": GENERATOR,
        "genre_counts": dict(sorted(Counter(doc.genre for doc in documents).items())),
        "negative_documents": sum(1 for doc in documents if doc.negative),
        "plaintext_sha256": hashlib.sha256(raw).hexdigest(),
        "protocol": PROTOCOL,
        "qi_counts": {kind: qi_counts.get(kind, 0) for kind in qi.QI_KINDS},
        "section26_counts": {code: section_counts.get(code, 0) for code in qi.catalog_section26()},
        "seed": SEEDS[split],
        "split": split,
        "templates_sha256": templates_sha256,
        "type_counts": {
            entity_type: type_counts.get(entity_type, 0) for entity_type in SCHEME_TYPES
        },
        "variants_per_family": VARIANTS[split],
        "version": VERSION,
    }


def build_public(split: str) -> tuple[Document, ...]:
    if split == "test":
        raise CorpusSealError("test-requires-key")
    errors = validate_templates(families.templates(split))
    errors += disjointness_errors()
    documents = render_split(split)
    errors += validate_documents(documents)
    if errors:
        raise CorpusSealError("validation-failed:" + ",".join(errors))
    return documents


def _lock_text(lock: dict) -> str:
    return json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_public(split: str, *, data_dir: Path | None = None) -> dict:
    """Write the template JSONL and the lock for train or dev. Refuses test."""
    if split == "test":
        raise CorpusSealError("test-lock-is-written-by-seal-only")
    root = DATA_DIR if data_dir is None else Path(data_dir)
    documents = build_public(split)
    blob = template_bytes(split)
    digest = hashlib.sha256(blob).hexdigest()
    lock = public_lock(split, documents, digest)
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{split}-templates.jsonl").write_bytes(blob)
    (root / f"{split}.lock.json").write_text(_lock_text(lock), encoding="utf-8")
    return lock


def check_public(split: str, *, data_dir: Path | None = None) -> dict:
    root = DATA_DIR if data_dir is None else Path(data_dir)
    documents = build_public(split)
    blob = (root / f"{split}-templates.jsonl").read_bytes()
    if blob != template_bytes(split):
        raise CorpusSealError("templates-drift")
    digest = hashlib.sha256(blob).hexdigest()
    lock = public_lock(split, documents, digest)
    saved = json.loads((root / f"{split}.lock.json").read_text(encoding="utf-8"))
    if saved != lock:
        raise CorpusSealError("lock-mismatch")
    return lock


def seal(key_path: str | Path, *, data_dir: Path | None = None) -> dict:
    """Render the test split with the key, encrypt the documents, write enc and lock.

    There is no overwrite. Plaintext documents are not written.
    """
    root = DATA_DIR if data_dir is None else Path(data_dir)
    key_path = Path(key_path)
    if inside_work_tree(key_path):
        raise CorpusSealError("key-inside-repository")
    destination = enc_path(root)
    lock_file = root / "test.lock.json"
    if destination.exists() or lock_file.exists():
        raise CorpusSealError("already-exists")
    errors = validate_templates(families.templates("test"))
    errors += disjointness_errors()
    if errors:
        raise CorpusSealError("validation-failed:" + ",".join(sorted(set(errors))))
    master = blind.load_master(key_path)
    documents = render_split("test", fingerprint=_fingerprint(master))
    errors = validate_documents(documents)
    if errors:
        raise CorpusSealError("validation-failed:" + ",".join(sorted(set(errors))))
    blob_templates = template_bytes("test")
    digest = hashlib.sha256(blob_templates).hexdigest()
    plaintext = canonical_bytes("test", documents, digest)
    lock = public_lock("test", documents, digest)
    ciphertext = blind.encrypt(plaintext, master, BLIND_VERSION)
    lock["ciphertext_sha256"] = hashlib.sha256(ciphertext).hexdigest()
    root.mkdir(parents=True, exist_ok=True)
    _write_new(destination, ciphertext)
    _write_new(lock_file, _lock_text(lock).encode("utf-8"))
    return lock


def _write_new(path: Path, payload: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def verify_commitment(data_dir: Path | None = None) -> dict:
    """Check the sealed files without the key and without decrypting."""
    root = DATA_DIR if data_dir is None else Path(data_dir)
    destination = enc_path(root)
    lock_file = root / "test.lock.json"
    if not destination.is_file() or not lock_file.is_file():
        raise CorpusSealError("not-sealed")
    try:
        lock = json.loads(lock_file.read_text(encoding="utf-8"))
        ciphertext = destination.read_bytes()
    except (OSError, json.JSONDecodeError):
        raise CorpusSealError("not-sealed") from None
    required = (
        "ciphertext_sha256",
        "documents",
        "families",
        "generator",
        "plaintext_sha256",
        "protocol",
        "section26_counts",
        "seed",
        "split",
        "templates_sha256",
        "version",
    )
    if any(field not in lock for field in required):
        raise CorpusSealError("lock-schema")
    if lock["split"] != "test" or lock["version"] != VERSION or lock["protocol"] != PROTOCOL:
        raise CorpusSealError("lock-schema")
    if hashlib.sha256(ciphertext).hexdigest() != lock["ciphertext_sha256"]:
        raise CorpusSealError("hash-mismatch")
    return lock


def open_sealed(key_path: str | Path, *, data_dir: Path | None = None) -> tuple[Document, ...]:
    """Decrypt the test documents. Used by the single scoring run, not by verify."""
    root = DATA_DIR if data_dir is None else Path(data_dir)
    key_path = Path(key_path)
    if inside_work_tree(key_path):
        raise CorpusSealError("key-inside-repository")
    lock = verify_commitment(root)
    try:
        version, plaintext = blind.decrypt(enc_path(root).read_bytes(), blind.load_master(key_path))
    except blind.BlindError as exc:
        raise CorpusSealError("open-failed") from exc
    if version != BLIND_VERSION:
        raise CorpusSealError("wrong-version")
    if hashlib.sha256(plaintext).hexdigest() != lock["plaintext_sha256"]:
        raise CorpusSealError("plaintext-hash-mismatch")
    split, documents = documents_from_canonical(plaintext)
    if split != "test":
        raise CorpusSealError("wrong-version")
    return documents


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmark.yrss_v3")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seal", help="encrypt the test split; needs YRSS_V3_TEST_KEY_FILE")
    sub.add_parser("verify", help="check the ciphertext hash; does not decrypt")
    check = sub.add_parser("check", help="rebuild a public split and compare its lock")
    check.add_argument("--split", choices=("train", "dev"), required=True)
    check.add_argument("--write-lock", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "seal":
            key_file = os.environ.get(KEY_ENV)
            if not key_file:
                raise CorpusSealError("missing-key-env")
            lock = seal(key_file)
            print(_lock_text(lock), end="")
            return 0
        if args.command == "verify":
            lock = verify_commitment()
            print(_lock_text(lock), end="")
            return 0
        if args.write_lock:
            lock = write_public(args.split)
        else:
            lock = check_public(args.split)
    except (CorpusSealError, blind.BlindError) as exc:
        code = exc.args[0] if exc.args else "refused"
        print(f"yrss-v3:{code}")
        if args.command == "verify" and code == "not-sealed":
            return 2
        return 1
    print(_lock_text(lock), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
