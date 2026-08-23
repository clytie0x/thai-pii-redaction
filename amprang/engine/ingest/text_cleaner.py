"""Text cleaning and normalization — 4-stage pipeline.

Whitespace, Unicode NFC, Thai digit standardization, post-clean encoding check. Earlier
PyThaiNLP word recovery / OCR-error flagging / interactive review stages were removed as
no-ops whose output nothing consumed.
"""

import re
import unicodedata
from dataclasses import dataclass


@dataclass
class CleanResult:
    text: str  # the cleaned text
    post_clean_warnings: list[str]  # any encoding issues found post-clean


THAI_DIGIT_MAP = {
    "๐": "0",
    "๑": "1",
    "๒": "2",
    "๓": "3",
    "๔": "4",
    "๕": "5",
    "๖": "6",
    "๗": "7",
    "๘": "8",
    "๙": "9",
}


def clean_length_preserving(text: str) -> str:
    """Apply only the normalisations that cannot move a character offset.

    Callers holding position-keyed side data (redact-pdf word bboxes) cannot use clean():
    whitespace collapsing / NFC / zero-width stripping shift offsets. Thai-to-Arabic digits
    are 1:1, and without them a Thai-numeral phone number is never detected.
    """
    for thai, ascii_ch in THAI_DIGIT_MAP.items():
        text = text.replace(thai, ascii_ch)
    return text


def clean(
    text: str,
    *,
    interactive: bool = False,
    review_timeout_s: float = 30.0,
) -> CleanResult:
    """Run the cleaning pipeline; returns CleanResult with cleaned text and encoding warnings.

    interactive / review_timeout_s are accepted and ignored (call-site compatibility).
    """
    del interactive, review_timeout_s  # retained for call-site compatibility

    # Stage 1: whitespace normalization
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = text.strip()

    # Stage 2: Unicode NFC
    text = unicodedata.normalize("NFC", text)

    # Stage 3: Thai digit standardization
    for thai, ascii_ch in THAI_DIGIT_MAP.items():
        text = text.replace(thai, ascii_ch)

    # Remove zero-width chars: U+200B, U+200C, U+200D, U+FEFF
    text = re.sub(r"[​‌‍﻿]", "", text)

    # Stage 4: post-clean encoding check
    post_warnings: list[str] = []
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as e:
        post_warnings.append(f"Post-clean encoding issue: {e}")
        text = text.encode("utf-8", errors="replace").decode("utf-8")

    return CleanResult(text=text, post_clean_warnings=post_warnings)
