"""Create one PDPA section 39 receipt for each run.

Verification runs the same input again and compares digests. The receipt keeps
counts, types, hashes, and offsets, but never document values. ``entity_id`` and
``score`` stay out of the digest so a new run can match. ``purpose`` and
``controller`` are user text and may contain personal data.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from amprang.engine.detectors.aggregate import detect_all
from amprang.engine.environment import environment as _environment
from amprang.engine.ingest.file_detector import detect_source_type
from amprang.engine.ingest.text_cleaner import clean
from amprang.engine.ingest.text_extractor import extract
from amprang.engine.models import Entity

RECEIPT_SCHEMA = "amprang.processing-receipt/1"

# A receipt missing any of these is rejected rather than partially checked.
_REQUIRED_PATHS = (
    ("source", "sha256"),
    ("source", "bytes"),
    ("source", "source_type"),
    ("result", "digest"),
    ("result", "entity_count"),
    ("result", "fp_count"),
    ("result", "tb_count"),
    ("result", "type_counts"),
    ("environment", "product_version"),
    ("environment", "ner_engine"),
    ("environment", "detector_version"),
)

_ENVIRONMENT_KEYS = ("product_version", "ner_engine", "detector_version")


class SourceChangedError(RuntimeError):
    """The input file changed while the receipt was being issued."""


@dataclass
class ProcessedSource:
    """What one run of the pipeline saw. The unit `verify` recomputes."""

    text: str
    entities: list[Entity]
    source_type: str


@dataclass
class VerifyResult:
    ok: bool
    outcome: str  # match | source_mismatch | result_mismatch |
    # unsupported_schema | malformed_receipt
    differences: list[str] = field(default_factory=list)
    recomputed: dict = field(default_factory=dict)


def process_for_receipt(path: str | Path) -> ProcessedSource:
    """Ingest, clean and detect — the single path both issuing and verifying run, so the two
    cannot drift apart."""
    source_type = detect_source_type(path)
    raw_text, _bboxes, _meta = extract(path, source_type)
    text = clean(raw_text).text
    return ProcessedSource(text=text, entities=detect_all(text), source_type=source_type)


def result_digest(entities: list[Entity]) -> str:
    """A digest over what detection found — spans and types, sorted so detector ordering cannot
    change it."""
    rows = sorted([e.span[0], e.span[1], e.data_type, e.redact_type] for e in entities)
    # Schema string in the preimage so a future schema can never collide with a v1 digest.
    preimage = RECEIPT_SCHEMA + "\n" + json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def _source_fingerprint(path: Path) -> tuple[str, int]:
    """Hash and size from ONE pass, so they can never describe different reads of a changing file."""
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _claims(processed: ProcessedSource, sha256: str, size: int) -> dict:
    """The factual half of a receipt — everything `verify` recomputes.

    Single source for BOTH `build_receipt` and `verify_receipt`: a field added here is compared
    by construction, so no claim can ride along unverified.
    """
    type_counts: dict[str, int] = {}
    for entity in processed.entities:
        type_counts[entity.data_type] = type_counts.get(entity.data_type, 0) + 1
    return {
        "source": {
            "sha256": sha256,
            "bytes": size,
            "source_type": processed.source_type,
        },
        "result": {
            "digest": result_digest(processed.entities),
            "entity_count": len(processed.entities),
            "fp_count": sum(1 for e in processed.entities if e.redact_type == "FP"),
            "tb_count": sum(1 for e in processed.entities if e.redact_type != "FP"),
            "type_counts": dict(sorted(type_counts.items())),
        },
    }


def build_receipt(
    path: str | Path,
    *,
    purpose: str | None = None,
    controller: str | None = None,
    operation: str = "detect",
    issued_at: str | None = None,
) -> dict:
    """Run the pipeline over `path` and return the receipt describing that run.

    `purpose` and `controller` are operator-supplied Section 39 fields; they appear only when
    given (no invented default) and are never inspected.

    Raises SourceChangedError if the file's bytes changed while it was being read.
    """
    path = Path(path)
    # Fingerprinted on both sides of detection: a file rewritten mid-run would otherwise yield a
    # receipt whose hash and findings describe different bytes, unverifiable forever.
    before, _ = _source_fingerprint(path)
    processed = process_for_receipt(path)
    after, size = _source_fingerprint(path)
    if before != after:
        raise SourceChangedError(
            f"{path} changed while the receipt was being issued; nothing can be "
            f"attested about a file that moved under the reader"
        )

    activity: dict = {"operation": operation}
    if purpose:
        activity["purpose"] = purpose
    if controller:
        activity["controller"] = controller

    return {
        "schema": RECEIPT_SCHEMA,
        "issued_at": issued_at or _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "activity": activity,
        **_claims(processed, after, size),
        "environment": _environment(),
    }


def _missing_fields(receipt: dict) -> list[str]:
    missing = []
    for section, key in _REQUIRED_PATHS:
        value = receipt.get(section)
        if not isinstance(value, dict) or key not in value:
            missing.append(f"{section}.{key}")
    return missing


def _diff_claims(receipt: dict, actual: dict) -> list[str]:
    """Every field of the recomputation that the receipt disagrees with."""
    differences = []
    for section, fields in actual.items():
        for key, value in fields.items():
            claimed = receipt[section].get(key)
            if claimed != value:
                differences.append(f"{section}.{key}: receipt {claimed!r}, now {value!r}")
    return differences


def verify_receipt(receipt: dict, path: str | Path) -> VerifyResult:
    """Re-run `path` and report whether it still produces this receipt.

    EVERY factual field is compared, not just the digests. The source hash is checked first and
    alone so a swapped file is never confused with a version upgrade. Environment differences
    are reported on both the mismatch and the match path.
    """
    if receipt.get("schema") != RECEIPT_SCHEMA:
        return VerifyResult(
            ok=False,
            outcome="unsupported_schema",
            differences=[f"schema {receipt.get('schema')!r}, this build reads {RECEIPT_SCHEMA!r}"],
        )
    missing = _missing_fields(receipt)
    if missing:
        return VerifyResult(
            ok=False,
            outcome="malformed_receipt",
            differences=[f"missing field {name}" for name in missing],
        )

    path = Path(path)
    actual_sha, actual_size = _source_fingerprint(path)
    environment = _environment()
    env_differences = [
        f"{key}: receipt {receipt['environment'][key]!r}, now {environment[key]!r}"
        for key in _ENVIRONMENT_KEYS
        if receipt["environment"][key] != environment[key]
    ]

    if actual_sha != receipt["source"]["sha256"]:
        # Stop here; recomputing for a document the receipt never described says nothing.
        return VerifyResult(
            ok=False,
            outcome="source_mismatch",
            differences=[f"source sha256: receipt {receipt['source']['sha256']}, file {actual_sha}"]
            + env_differences,
            recomputed={"source_sha256": actual_sha},
        )

    try:
        processed = process_for_receipt(path)
    except Exception as e:
        # Bytes match but cannot be re-read (typically a renamed file: `detect_source_type` routes
        # on extension). Its own outcome, so a correct file does not look like a broken tool.
        return VerifyResult(
            ok=False,
            outcome="recompute_failed",
            differences=[
                f"the file's bytes match the receipt but it could not be processed "
                f"again as {receipt['source']['source_type']!r}: {e}"
            ]
            + env_differences,
            recomputed={"source_sha256": actual_sha, "source_bytes": actual_size},
        )

    actual = _claims(processed, actual_sha, actual_size)
    recomputed = {**actual["source"], **actual["result"]}
    claim_differences = _diff_claims(receipt, actual)
    if claim_differences:
        return VerifyResult(
            ok=False,
            outcome="result_mismatch",
            differences=claim_differences + env_differences,
            recomputed=recomputed,
        )
    return VerifyResult(
        ok=True, outcome="match", differences=env_differences, recomputed=recomputed
    )
