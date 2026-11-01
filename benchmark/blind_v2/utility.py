"""Utility of a document after redaction, on a small synthetic question set.

An answer counts as correct when the normalized expected text occurs in the
model reply. Questions marked ``needs_pii`` ask for a value the gold span
covers; the others ask for a fact outside those spans.
"""

from __future__ import annotations

from .llm import LLMUnavailable, complete, probe_llm


def answer_correct(expected: str, actual: str) -> bool:
    needle = " ".join(expected.casefold().split())
    haystack = " ".join(actual.casefold().split())
    return bool(needle) and needle in haystack


def redact(text: str, spans: list[tuple[int, int, str]]) -> str:
    ordered = sorted(spans, key=lambda item: (item[0], -(item[1] - item[0])))
    kept: list[tuple[int, int]] = []
    cursor = 0
    for start, end, _entity_type in ordered:
        if end <= start or start < cursor:
            continue
        kept.append((start, end))
        cursor = end
    updated = text
    for start, end in reversed(kept):
        updated = updated[:start] + "[REDACTED]" + updated[end:]
    return updated


def question_prompt(document: str, question: str) -> str:
    return (
        "Answer the question using only the document. "
        "If the document does not contain the answer, reply ไม่ทราบ.\n"
        f"Document:\n{document}\nQuestion: {question}\nAnswer:"
    )


def score_utility(documents, predictions_by_system: dict[str, list], complete_fn) -> dict:
    questions = [(doc, question) for doc in documents for question in doc.questions]
    if not questions:
        return {"status": "skipped", "reason": "the freeze has no questions", "systems": {}}
    systems = {}
    for name, predictions in predictions_by_system.items():
        by_id = {doc.doc_id: prediction for doc, prediction in zip(documents, predictions)}
        tallies = {
            "pii_raw": 0,
            "pii_redacted": 0,
            "pii_n": 0,
            "safe_raw": 0,
            "safe_redacted": 0,
            "safe_n": 0,
        }
        try:
            for document, question in questions:
                raw = complete_fn(question_prompt(document.text, question.question))
                masked = redact(document.text, by_id[document.doc_id])
                redacted = complete_fn(question_prompt(masked, question.question))
                raw_ok = answer_correct(question.answer, raw)
                redacted_ok = answer_correct(question.answer, redacted)
                if question.needs_pii:
                    tallies["pii_n"] += 1
                    tallies["pii_raw"] += int(raw_ok)
                    tallies["pii_redacted"] += int(redacted_ok)
                else:
                    tallies["safe_n"] += 1
                    tallies["safe_raw"] += int(raw_ok)
                    tallies["safe_redacted"] += int(redacted_ok)
        except LLMUnavailable as exc:
            return {"status": "skipped", "reason": exc.reason, "systems": {}}
        systems[name] = {
            "pii_n": tallies["pii_n"],
            "pii_raw_accuracy": _rate(tallies["pii_raw"], tallies["pii_n"]),
            "pii_redacted_accuracy": _rate(tallies["pii_redacted"], tallies["pii_n"]),
            "safe_n": tallies["safe_n"],
            "safe_raw_accuracy": _rate(tallies["safe_raw"], tallies["safe_n"]),
            "safe_redacted_accuracy": _rate(tallies["safe_redacted"], tallies["safe_n"]),
        }
    return {"status": "ok", "reason": "", "systems": systems}


def probe_utility() -> tuple[bool, str]:
    probe = probe_llm()
    return probe.available, probe.reason or ""


def _rate(hits: int, total: int) -> float | None:
    if total == 0:
        return None
    return hits / total


def default_complete(prompt: str) -> str:
    return complete(prompt)
