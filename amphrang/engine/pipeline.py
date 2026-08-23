"""End-to-end pipeline orchestrator (Steps 1-8)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path

from amphrang.engine.ai_client import AIProvider, FakeLLMProvider
from amphrang.engine.exporter import ExportResult
from amphrang.engine.models import AIResponse, EntityRegistry, ReverseResult
from amphrang.engine.output_validator import ValidationResult
from amphrang.engine.session_vault import SessionVault


@dataclass
class PipelineResult:
    """Full end-to-end result, all intermediate outputs preserved."""

    input_path: str | None
    raw_text: str
    clean_text: str
    entity_registry: EntityRegistry
    pseudonymized_text: str
    ai_response: AIResponse
    reverse_result: ReverseResult
    validation_result: ValidationResult
    export_result: ExportResult | None  # None if export_path not provided
    vault: SessionVault
    session_id: str


def run_pipeline(
    input_path: str | None = None,
    *,
    text: str | None = None,
    output_path: str | None = None,
    fmt: str = "txt",
    provider: AIProvider | None = None,
    salt: str | None = None,
    system_prompt: str | None = None,
    overwrite: bool = False,
) -> PipelineResult:
    """Run the 8-step PII redaction pipeline; returns PipelineResult with all intermediates.

    Exactly one of input_path / text is required (ValueError otherwise). output_path None
    skips export. Raises FileNotFoundError, PIILeakError, ExportError, VaultTimeoutError.
    """
    if input_path is None and text is None:
        raise ValueError("Provide either input_path or text")
    if input_path is not None and text is not None:
        raise ValueError("Provide either input_path or text, not both")
    if input_path is not None and not Path(input_path).exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if provider is None:
        provider = FakeLLMProvider()
    if salt is None:
        salt = secrets.token_hex(16)

    vault = SessionVault()

    # --- Step 1: Ingest ---
    if input_path is not None:
        from amphrang.engine.ingest.file_detector import detect_source_type
        from amphrang.engine.ingest.text_extractor import extract

        source_type = detect_source_type(input_path)
        raw_text, _bboxes, extract_meta = extract(input_path, source_type)
    else:
        raw_text = text
        source_type = "text"
        extract_meta = {}

    from amphrang.engine.ingest.text_cleaner import clean

    clean_result = clean(raw_text)
    clean_text = clean_result.text

    # Quality check is informational; do not halt on low score
    from amphrang.engine.ingest.quality_validator import validate as validate_quality

    validate_quality(clean_text, source_type, ocr_confidence=extract_meta.get("ocr_confidence"))

    # --- Step 2: Detection ---
    from amphrang.engine.detectors.aggregate import detect_all

    all_entities = detect_all(clean_text)
    fp_count = sum(entity.redact_type == "FP" for entity in all_entities)
    entity_registry = EntityRegistry(
        entities=all_entities,
        fp_count=fp_count,
        tb_count=len(all_entities) - fp_count,
    )

    # --- Step 3+4: Pseudonymization ---
    from amphrang.engine.anonymizer.anonymizer import anonymize

    pseudo_doc = anonymize(clean_text, entity_registry, vault, salt=salt)
    pseudonymized_text = pseudo_doc.text

    # --- Step 5: Send to AI ---
    from amphrang.engine.ai_client import send_to_ai

    ai_response = send_to_ai(
        pseudonymized_text,
        entity_registry,
        vault,
        provider,
        system_prompt=system_prompt,
    )

    # --- Step 6: Reverse mapping ---
    from amphrang.engine.reverse_mapper import reverse_map

    reverse_result = reverse_map(
        ai_response,
        entity_registry,
        vault,
        mode="surrogate",
    )

    # --- Step 7: Output validation ---
    from amphrang.engine.output_validator import validate_output

    validation_result = validate_output(reverse_result, entity_registry, vault)

    # --- Step 8: Export (optional) ---
    export_result = None
    if output_path is not None:
        from amphrang.engine.exporter import export

        export_result = export(
            reverse_result,
            validation_result,
            output_path,
            fmt=fmt,
            overwrite=overwrite,
        )

    return PipelineResult(
        input_path=input_path,
        raw_text=raw_text,
        clean_text=clean_text,
        entity_registry=entity_registry,
        pseudonymized_text=pseudonymized_text,
        ai_response=ai_response,
        reverse_result=reverse_result,
        validation_result=validation_result,
        export_result=export_result,
        vault=vault,
        session_id=vault.session_id,
    )
