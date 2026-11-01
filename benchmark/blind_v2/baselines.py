"""Comparison detectors that are not the full AI Guard pipeline.

The regex baseline is a small cue-and-pattern set. It is not ``detect_fp``.
PyThaiNLP NER and WangchanBERTa NER return mapped tags only: they do not run
the product's format, false-negative, or address layers. Presidio is optional.
"""

from __future__ import annotations

import re

from .score import dedupe_predictions
from .types import REDACTION_TYPE_SET

_MONTHS = "มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม"
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_THAI_ID_RE = re.compile(r"(?<!\d)(\d{13}|\d \d{4} \d{5} \d{2} \d)(?!\d)")
_CARD_RE = re.compile(r"(?<!\d)(\d{4}-\d{4}-\d{4}-\d{4})(?!\d)")
_IBAN_RE = re.compile(r"\b([A-Z]{2}\d{2}[A-Z0-9]{11,30})\b")
_PHONE_RE = re.compile(r"(?<!\d)(0[689]\d-\d{3}-\d{4}|02-\d{3}-\d{4}|\+66 \d{2} \d{3} \d{4})(?!\d)")
_BANK_RE = re.compile(r"เลขที่บัญชี\s+(\d{3}-\d-\d{5}-\d)")
_PASSPORT_RE = re.compile(r"(?:หนังสือเดินทางเลขที่|Passport)\s+([A-Z]{2}\d{7})")
_PLATE_RE = re.compile(r"ทะเบียน(?:รถ)?\s+([0-9]?[ก-ฮ]{2}\s*\d{1,4})")
_STUDENT_RE = re.compile(r"รหัสนักศึกษา\s+(\d{2}-\d{2}-\d{4}|\d{8,12})")
_DOB_RE = re.compile(rf"เกิดวันที่\s+(\d{{1,2}}/\d{{1,2}}/\d{{4}}|\d{{1,2}} (?:{_MONTHS}) \d{{4}})")
_ADDRESS_RE = re.compile(r"ที่อยู่(?:ใหม่|สำหรับส่งเอกสาร)?\s+(\S.+)")
_NAME_RE = re.compile(
    r"(?:ชื่อ(?:-นามสกุล)?|ผู้ยื่นคำร้อง|ข้าพเจ้า|ผู้ร่าง|ชื่อผู้ชำระ|โทรหา)\s+"
    r"([ก-๙]{2,}(?:\s+[ก-๙]{2,})?)"
)
_EN_NAME_RE = re.compile(r"\bfor ([A-Z][a-z]+ [A-Z][a-z]+)\b")

_NER_TAG_MAP = {
    "PERSON": "NAME",
    "PER": "NAME",
    "EMAIL": "EMAIL",
    "PHONE": "PHONE",
    "DATE": "DATE",
    "DTM": "DATE",
    "LOCATION": "LOCATION",
    "LOC": "LOCATION",
    "GPE": "LOCATION",
    "ORGANIZATION": "ORGANIZATION",
    "ORG": "ORGANIZATION",
}


def _digits(text: str) -> str:
    return "".join(char for char in text if char.isdigit())


def _thai_id_ok(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 13:
        return False
    total = sum(int(digits[index]) * (13 - index) for index in range(12))
    return digits[12] == str((11 - (total % 11)) % 10)


def _luhn_ok(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 16:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _iban_ok(value: str) -> bool:
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", value):
        return False
    rearranged = value[4:] + value[:4]
    numeric = "".join(str(ord(char) - 55) if char.isalpha() else char for char in rearranged)
    return int(numeric) % 97 == 1


def _add(found: list[tuple[int, int, str]], match: re.Match[str], entity_type: str) -> None:
    found.append((match.start(1), match.end(1), entity_type))


def regex_predict(text: str) -> list[tuple[int, int, str]]:
    found: list[tuple[int, int, str]] = []
    for match in _EMAIL_RE.finditer(text):
        found.append((match.start(), match.end(), "EMAIL"))
    for match in _THAI_ID_RE.finditer(text):
        if _thai_id_ok(match.group(1)):
            _add(found, match, "THAI_ID")
    for match in _CARD_RE.finditer(text):
        if _luhn_ok(match.group(1)):
            _add(found, match, "CREDIT_CARD")
    for match in _IBAN_RE.finditer(text):
        if _iban_ok(match.group(1)):
            _add(found, match, "IBAN")
    for match in _PHONE_RE.finditer(text):
        _add(found, match, "PHONE")
    for match in _BANK_RE.finditer(text):
        _add(found, match, "BANK_ACCOUNT")
    for match in _PASSPORT_RE.finditer(text):
        _add(found, match, "PASSPORT")
    for match in _PLATE_RE.finditer(text):
        _add(found, match, "VEHICLE_PLATE")
    for match in _STUDENT_RE.finditer(text):
        _add(found, match, "STUDENT_ID")
    for match in _DOB_RE.finditer(text):
        _add(found, match, "DATE_OF_BIRTH")
    for match in _ADDRESS_RE.finditer(text):
        _add(found, match, "ADDRESS")
    for match in _NAME_RE.finditer(text):
        _add(found, match, "NAME")
    for match in _EN_NAME_RE.finditer(text):
        _add(found, match, "NAME")
    return dedupe_predictions(found)


def align_ner_tags(text: str, pairs: list[tuple[str, str]]) -> list[tuple[int, int, str]]:
    """Map ``(token, BIO-tag)`` pairs back onto ``text`` without inventing spans."""
    pos = 0
    aligned: list[tuple[int, int, str]] = []
    current: list | None = None
    for token, tag in pairs:
        if not token:
            continue
        start = text.find(token, pos)
        if start < 0:
            current = None
            continue
        end = start + len(token)
        pos = end
        prefix, _, label = tag.partition("-")
        mapped = _NER_TAG_MAP.get(label)
        if prefix not in {"B", "I"} or mapped is None:
            if current is not None:
                aligned.append((current[0], current[1], current[2]))
                current = None
            continue
        if current is not None and prefix == "I" and current[2] == mapped:
            current[1] = end
            continue
        if current is not None:
            aligned.append((current[0], current[1], current[2]))
        current = [start, end, mapped]
    if current is not None:
        aligned.append((current[0], current[1], current[2]))
    return dedupe_predictions(aligned)


class RegexBaseline:
    name = "regex"
    cost_usd = 0.0

    def prepare(self) -> str | None:
        return None

    def predict(self, text: str) -> list[tuple[int, int, str]]:
        return regex_predict(text)


class _CachedNER:
    def __init__(self, name: str, engine: str, unavailable: str) -> None:
        self.name = name
        self.cost_usd = 0.0
        self._engine = engine
        self._unavailable = unavailable
        self._tagger = None

    def prepare(self) -> str | None:
        if self._engine == "thainer-v2":
            try:
                import transformers  # noqa: F401
            except ImportError:
                return self._unavailable
        try:
            from pythainlp.tag import NER

            self._tagger = NER(engine=self._engine)
        except Exception as exc:
            return f"{self.name} failed to load ({type(exc).__name__})"
        return None

    def predict(self, text: str) -> list[tuple[int, int, str]]:
        if self._tagger is None:
            raise RuntimeError("ner-not-prepared")
        return align_ner_tags(text, list(self._tagger.tag(text)))


class PyThaiNLPNER(_CachedNER):
    def __init__(self) -> None:
        super().__init__(
            "pythainlp-ner",
            "thainer",
            "PyThaiNLP thainer NER is unavailable",
        )


class WangchanBERTaNER(_CachedNER):
    def __init__(self) -> None:
        super().__init__(
            "wangchanberta-ner",
            "thainer-v2",
            "transformers is not installed (requirements-ml.txt); WangchanBERTa NER was not run",
        )


_PRESIDIO_MAP = {
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "CREDIT_CARD": "CREDIT_CARD",
    "IBAN_CODE": "IBAN",
    "PERSON": "NAME",
    "LOCATION": "LOCATION",
    "DATE_TIME": "DATE",
    "THAI_ID": "THAI_ID",
    "BANK_ACCOUNT": "BANK_ACCOUNT",
    "PASSPORT": "PASSPORT",
    "VEHICLE_PLATE": "VEHICLE_PLATE",
    "STUDENT_ID": "STUDENT_ID",
    "DATE_OF_BIRTH": "DATE_OF_BIRTH",
    "ADDRESS": "ADDRESS",
    "IBAN": "IBAN",
    "EMAIL": "EMAIL",
    "PHONE": "PHONE",
    "NAME": "NAME",
}


def _dedupe_prefer_scheme(spans: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Drop overlaps, keeping a redaction-type span ahead of a generic label."""
    ordered = sorted(
        spans,
        key=lambda item: (
            0 if item[2] in REDACTION_TYPE_SET else 1,
            item[0],
            -(item[1] - item[0]),
            item[2],
        ),
    )
    kept: list[tuple[int, int, str]] = []
    occupied: list[tuple[int, int]] = []
    for start, end, entity_type in ordered:
        if end <= start:
            continue
        if any(start < right and left < end for left, right in occupied):
            continue
        kept.append((start, end, entity_type))
        occupied.append((start, end))
    kept.sort(key=lambda item: (item[0], item[1], item[2]))
    return kept


def _presidio_recognizers():
    from presidio_analyzer import Pattern, PatternRecognizer

    specs = (
        ("THAI_ID", r"(?<!\d)\d{13}(?!\d)", ("ประชาชน", "บัตร")),
        ("THAI_ID", r"(?<!\d)\d \d{4} \d{5} \d{2} \d(?!\d)", ("ประชาชน",)),
        ("PHONE", r"(?<!\d)0[689]\d-\d{3}-\d{4}(?!\d)", ("โทร", "เบอร์")),
        ("PHONE", r"(?<!\d)02-\d{3}-\d{4}(?!\d)", ("โทร",)),
        ("PHONE", r"(?<!\d)\+66 \d{2} \d{3} \d{4}(?!\d)", ("โทร",)),
        ("BANK_ACCOUNT", r"(?<!\d)\d{3}-\d-\d{5}-\d(?!\d)", ("บัญชี",)),
        ("PASSPORT", r"(?<![A-Za-z0-9])[A-Z]{2}\d{7}(?![A-Za-z0-9])", ("Passport", "เดินทาง")),
        ("VEHICLE_PLATE", r"(?<=ทะเบียน )[0-9]?[ก-ฮ]{2}\s*\d{1,4}", ("ทะเบียน",)),
        ("VEHICLE_PLATE", r"(?<=ทะเบียนรถ )[0-9]?[ก-ฮ]{2}\s*\d{1,4}", ("ทะเบียน",)),
        ("STUDENT_ID", r"(?<=รหัสนักศึกษา )\d{2}-\d{2}-\d{4}", ("นักศึกษา",)),
        ("STUDENT_ID", r"(?<=รหัสนักศึกษา )\d{8,12}", ("นักศึกษา",)),
        ("DATE_OF_BIRTH", r"(?<=เกิดวันที่ )\d{1,2}/\d{1,2}/\d{4}", ("เกิด",)),
        ("DATE_OF_BIRTH", rf"(?<=เกิดวันที่ )\d{{1,2}} (?:{_MONTHS}) \d{{4}}", ("เกิด",)),
        ("IBAN", r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", ("IBAN",)),
        ("ADDRESS", r"(?<=ที่อยู่ ).+", ()),
        ("ADDRESS", r"(?<=ที่อยู่ใหม่ ).+", ()),
        ("NAME", r"(?<=ชื่อ )[ก-๙]{2,}(?:\s+[ก-๙]{2,})?", ()),
        ("NAME", r"(?<=ชื่อ-นามสกุล )[ก-๙]{2,}(?:\s+[ก-๙]{2,})?", ()),
        ("NAME", r"(?<=ผู้ยื่นคำร้อง )[ก-๙]{2,}(?:\s+[ก-๙]{2,})?", ()),
        ("NAME", r"(?<=ข้าพเจ้า )[ก-๙]{2,}(?:\s+[ก-๙]{2,})?", ()),
        ("NAME", r"(?<=ผู้ร่าง )[ก-๙]{2,}(?:\s+[ก-๙]{2,})?", ()),
        ("NAME", r"(?<=ชื่อผู้ชำระ )[ก-๙]{2,}(?:\s+[ก-๙]{2,})?", ()),
        ("NAME", r"(?<=โทรหา )[ก-๙]{2,}(?:\s+[ก-๙]{2,})?", ()),
        ("NAME", r"(?<=for )[A-Z][a-z]+ [A-Z][a-z]+", ()),
    )
    recognizers = []
    for entity_type, pattern, context in specs:
        recognizers.append(
            PatternRecognizer(
                supported_entity=entity_type,
                supported_language="en",
                patterns=[Pattern(name=entity_type.lower(), regex=pattern, score=0.6)],
                context=list(context),
            )
        )
    return recognizers


class PresidioBaseline:
    name = "presidio"
    cost_usd = 0.0

    def __init__(self) -> None:
        self._engine = None

    def prepare(self) -> str | None:
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider
        except ImportError:
            return "presidio-analyzer is not installed"
        try:
            import spacy

            spacy.load("en_core_web_sm")
        except Exception:
            return "spaCy model en_core_web_sm is not installed; Presidio was not run"
        try:
            provider = NlpEngineProvider(
                nlp_configuration={
                    "nlp_engine_name": "spacy",
                    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
                }
            )
            engine = AnalyzerEngine(
                nlp_engine=provider.create_engine(),
                supported_languages=["en"],
            )
            for recognizer in _presidio_recognizers():
                engine.registry.add_recognizer(recognizer)
            self._engine = engine
        except Exception as exc:
            return f"Presidio failed to initialize ({type(exc).__name__})"
        return None

    def predict(self, text: str) -> list[tuple[int, int, str]]:
        if self._engine is None:
            raise RuntimeError("presidio-not-prepared")
        found: list[tuple[int, int, str]] = []
        for result in self._engine.analyze(text=text, language="en"):
            entity_type = _PRESIDIO_MAP.get(result.entity_type, result.entity_type)
            surface = text[result.start : result.end]
            if entity_type == "THAI_ID" and not _thai_id_ok(surface):
                continue
            if entity_type == "IBAN" and not _iban_ok(surface):
                continue
            if entity_type == "CREDIT_CARD" and not _luhn_ok(surface):
                continue
            if entity_type not in REDACTION_TYPE_SET and entity_type not in {
                "LOCATION",
                "DATE",
                "ORGANIZATION",
            }:
                entity_type = "OTHER"
            found.append((result.start, result.end, entity_type))
        return _dedupe_prefer_scheme(found)
