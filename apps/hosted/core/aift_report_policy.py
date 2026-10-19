"""Hosted projection for legally cautious PDPA report recommendations.

The vendored detector remains byte-for-byte aligned with its recorded upstream
slice.  This adapter changes only user-facing recommendation language: a
keyword-based Section 26 signal is not a legal conclusion and must not project
one mandatory legal basis as universally applicable.
"""

from __future__ import annotations

from collections.abc import Callable


SECTION26_PREFIX = "Section 26 sensitive data found"
SECTION26_REVIEW_TEXT = (
    "เป็นสัญญาณ heuristic สำหรับการทบทวน โปรดให้ผู้รับผิดชอบประเมิน"
    "ฐานกฎหมาย เงื่อนไข และข้อยกเว้นตามบริบทก่อนประมวลผล"
)


def install_hosted_report_policy() -> None:
    """Wrap the report builder before `app.server` imports its reference."""

    from pii_redactor import report

    original: Callable[[str], dict] = report.analyze_text
    if getattr(original, "_aift_hosted_policy", False):
        return

    def analyze_text_hosted(text: str) -> dict:
        result = original(text)
        recommendations = result.get("recommendations")
        if isinstance(recommendations, list):
            for recommendation in recommendations:
                if not isinstance(recommendation, dict):
                    continue
                title = recommendation.get("title")
                if isinstance(title, str) and title.startswith(SECTION26_PREFIX):
                    recommendation["desc"] = SECTION26_REVIEW_TEXT
        return result

    analyze_text_hosted._aift_hosted_policy = True  # type: ignore[attr-defined]
    report.analyze_text = analyze_text_hosted
