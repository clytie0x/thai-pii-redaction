"""Additive, value-free PDPA evidence assessment. Never a legal determination."""

from __future__ import annotations

import math
import os
import re
from collections import Counter
from pathlib import Path

from pii_redactor.detectors.aggregate import detect_all
from pii_redactor.detectors.tb_detector import NERChunkDiagnostics
from pii_redactor.pdpa_catalog import (
    GENERAL,
    LAW_VERSION,
    MODALITIES,
    SENSITIVE,
    SOURCES,
    STRATEGIES,
    coverage_catalog,
)
from pii_redactor.pdpa_lifecycle import plan_lifecycle, validate_context
from pii_redactor.report import scan_section26

_SENSITIVE_PATTERNS = {
    "RACE": r"เชื้อชาติ|\brace\b|\bracial\b",
    "ETHNICITY": r"ชาติพันธุ์|เผ่าพันธุ์|เชื้อสาย|\bethnic(?:ity)?\b",
    "POLITICAL_OPINION": r"ความคิดเห็นทางการเมือง|อุดมการณ์ทางการเมือง|พรรคการเมือง|สมาชิกพรรค|สนับสนุนพรรค|\bpolitical\b|\bvot(?:e|ing)\b",
    "BELIEF": r"ศาสนา|นับถือ|ความเชื่อในลัทธิ|ลัทธิ|ปรัชญา|พุทธ|คริสต์|อิสลาม|ฮินดู|ซิกข์|\breligio\w*\b|\batheis\w*\b|\bphilosophical\b",
    "SEXUAL_BEHAVIOR": r"พฤติกรรมทางเพศ|เพศสัมพันธ์|รสนิยมทางเพศ|เพศวิถี|\bsexual\b",
    "CRIMINAL_RECORD": r"ประวัติอาชญากรรม|คดีอาญา|ต้องโทษ|จำคุก|ถูกพิพากษา|\bcriminal\b|\bconvict\w*\b|\bacquitt\w*\b",
    "HEALTH": r"โรค|สุขภาพ|เบาหวาน|ความดัน|มะเร็ง|ฟอกไต|ป่วย|รักษาตัว|ประจำเดือน|\bHIV\b|\bdiabet\w*\b|\bmedical\b|\bpatient\b|\bdiagnos\w*\b",
    "DISABILITY": r"พิการ|ทุพพลภาพ|สูญเสียการมองเห็น|ต้องใช้รถเข็น|\bdisabil\w*\b|\bwheelchair\b",
    "LABOR_UNION": r"สหภาพแรงงาน|สมาคมลูกจ้าง|\btrade.union\b|\blabou?r.union\b",
    "GENETIC_DATA": r"พันธุกรรม|โครโมโซม|ตรวจยีน|\bDNA\b|\bRNA\b|\bgenetic\w*\b|\bgenom\w*\b|\bBRCA[12]?\b",
    "BIOMETRIC_IDENTITY": r"ข้อมูลชีวภาพ|แม่แบบ(?:ใบหน้า|ลายนิ้วมือ|เสียง)|ลายนิ้วมือ.*ยืนยันตัวตน|\bbiometric\w*\b|\bface.embedding\b|\bfingerprint.template\b",
}
_GENERAL_PATTERNS = {
    "IDENTITY": r"เลขประจำตัว|บัตรประชาชน|หนังสือเดินทาง|สัญชาติ|วันเกิด|\bpassport\b|\bnational.ID\b",
    "CONTACT": r"เบอร์โทร|โทรศัพท์|อีเมล|\be.?mail\b|\bphone\b",
    "LOCATION": r"ที่อยู่|พิกัด|ละติจูด|ลองจิจูด|\bGPS\b|\baddress\b|\blocation\b",
    "FINANCIAL": r"บัญชีธนาคาร|บัตรเครดิต|รายได้|เงินเดือน|ประวัติการชำระ|ยอดหนี้|\bbank.account\b|\bsalary\b",
    "EDUCATION": r"ผลการเรียน|เกรด|รหัสนักศึกษา|รหัสนักเรียน|ประวัติการศึกษา|\bstudent\b|\btranscript\b",
    "EMPLOYMENT": r"รหัสพนักงาน|ข้อมูลพนักงาน|ประวัติการทำงาน|ตำแหน่งงาน|\bemployee\b|\bemployment\b",
    "ONLINE": r"\bIP(?:v[46])?\b|\bMAC\b|\bcookie\b|รหัสอุปกรณ์|บัญชีผู้ใช้|\bdevice.ID\b|\buser.?ID\b|\busername\b",
    "ACTIVITY": r"ประวัติการซื้อ|ประวัติการใช้งาน|ประวัติการเดินทาง|พฤติกรรมการใช้|\bbrowsing\b|\bpurchase.history\b|\bactivity.log\b",
    "RELATIONSHIPS": r"คู่สมรส|ครอบครัว|ผู้ติดต่อฉุกเฉิน|บุตรของ|บิดาของ|มารดาของ|\bspouse\b|\bemergency.contact\b",
    "MEDIA": r"รูปถ่าย|ภาพถ่าย|ลายมือชื่อ|คลิปเสียง|กล้องวงจรปิด|\bCCTV\b|\bphoto\b|\bvoice.record\w*\b|\bsignature\b",
    "QUASI_IDENTIFIERS": r"อายุ\s*\d+|อำเภอ|ตำบล|แขวง|อาชีพ|\bage\s*\d+|\boccupation\b",
}
_PATTERNS = {
    k: re.compile(v, re.IGNORECASE) for k, v in {**_SENSITIVE_PATTERNS, **_GENERAL_PATTERNS}.items()
}
_SUBJECT_PRONOUN = re.compile(
    r"(?:^|[\s:：\"“‘'])(?:ฉัน|ผม|ดิฉัน|ข้าพเจ้า|เรา|เขา|เธอ)|\b(?:I|my|me|mine|he|she|his|her)\b",
    re.IGNORECASE,
)
_SPECIFIC_SUBJECT = re.compile(
    r"(?:ผู้ป่วย|พนักงาน|นักศึกษา|สมาชิก|ผู้สมัคร)(?:รายนี้|คนนี้|รหัส|ชื่อ|หมายเลข)|(?:ข้อมูล|ผลตรวจ|ประวัติ)ของ(?:ฉัน|ผม|ดิฉัน)|\b(?:patient|employee|record)\s*(?:ID|[A-Z]\d{2})",
    re.IGNORECASE,
)
_GENERIC = re.compile(
    r"บทความ|บทเรียน|นิยาม|หมายถึง|อธิบาย|หลักสูตร|กฎหมาย|สรุป|อ่าน|ศึกษา(?:เรื่อง|เกี่ยวกับ)|ขาย|ผลิต|\b(?:article|definition|tutorial|lesson|research.about)\b",
    re.IGNORECASE,
)
_ASSERTION = re.compile(
    r"(?:ฉัน|ผม|ดิฉัน|ข้าพเจ้า|เขา|เธอ)(?:มี|เป็น|เคย|ไม่ได้|ไม่เคย|นับถือ|ได้รับ|ใช้|สนับสนุน|ระบุ|แจ้ง)|(?:ผลตรวจ|ข้อมูล|ประวัติ)ของ|สมาชิก(?:สหภาพ|พรรค)|\b(?:I.am|I.have|my.result|my.record|he.has|she.has|he.is|she.is)\b",
    re.IGNORECASE,
)
_UNCERTAIN = re.compile(
    r"ไม่ทราบ(?:ว่า)?(?:เป็น)?ของใคร|ไม่ระบุเจ้าของ|เจ้าของไม่ชัด|\bunknown.owner\b", re.IGNORECASE
)
_PERSONAL_POSSESSIVE = re.compile(
    r"ของ(?:ฉัน|ผม|ดิฉัน|ข้าพเจ้า|เขา|เธอ)|\b(?:my|his|her|their)\s+(?:HIV|DNA|health|medical|test|diagnos\w*|genetic\w*|racial|ethnic\w*|religio\w*|political|sexual|criminal|disabil\w*|union|biometric\w*|salary|income|bank|phone|email|address|employment|education|family|photo|voice|signature)\b(?!\s+(?:book|textbook|article|course))",
    re.IGNORECASE,
)
_TYPE_FAMILY = {
    "NAME": "IDENTITY",
    "SURNAME": "IDENTITY",
    "THAI_ID": "IDENTITY",
    "PASSPORT": "IDENTITY",
    "ID_NUMBER": "IDENTITY",
    "PHONE": "CONTACT",
    "EMAIL": "CONTACT",
    "ADDRESS": "LOCATION",
    "LOCATION": "LOCATION",
    "POSTAL_CODE": "LOCATION",
    "BANK_ACCOUNT": "FINANCIAL",
    "CREDIT_CARD": "FINANCIAL",
    "IBAN": "FINANCIAL",
    "STUDENT_ID": "EDUCATION",
    "DATE_OF_BIRTH": "QUASI_IDENTIFIERS",
}


def _attribution(
    text: str, start: int, end: int, entities, *, semantic: bool = False, category: str = ""
) -> tuple[str, str]:
    lo = text.rfind("\n", 0, start) + 1
    hi = text.find("\n", end)
    hi = len(text) if hi < 0 else hi
    lo, hi = max(lo, start - 180), min(hi, end + 180)
    segment = text[lo:hi]
    if _UNCERTAIN.search(segment):
        return "ambiguous", "unresolved_subject"
    generic = _GENERIC.search(segment) is not None
    assertion = _ASSERTION.search(segment) is not None
    prefix = segment[: end - lo]
    generic_prefix = list(_GENERIC.finditer(prefix))
    assertion_prefix = list(_ASSERTION.finditer(prefix))
    possessives = list(_PERSONAL_POSSESSIVE.finditer(segment))
    if (
        semantic
        and category in {"BELIEF", "BIOMETRIC_IDENTITY"}
        and not _PATTERNS[category].search(segment)
    ):
        return ("topic" if generic else "ambiguous"), "semantic_relation_unverified"
    if possessives and (not generic_prefix or possessives[-1].start() > generic_prefix[-1].start()):
        return "personal", "possessive_attributed_statement"
    subject = _SUBJECT_PRONOUN.search(segment) or _SPECIFIC_SUBJECT.search(segment)
    identity = any(
        e.data_type in {"NAME", "THAI_ID", "STUDENT_ID", "MEDICAL_ID"} and lo <= e.span[0] < hi
        for e in entities
    )
    if generic and not assertion:
        return "topic", "generic_discussion"
    if generic_prefix and (
        not assertion_prefix or generic_prefix[-1].start() > assertion_prefix[-1].start()
    ):
        return "topic", "generic_discussion_after_unrelated_subject"
    if subject or identity:
        return "personal", "heuristic_subject_link"
    if generic:
        return "topic", "generic_discussion"
    return "ambiguous", "attribution_requires_context"


def assess_text(
    text: str,
    *,
    strategy: str = "contextual",
    context: dict | None = None,
    modality: str = "text",
    model_dir: str | None = None,
    threshold: float = 0.50,
    semantic_backend=None,
) -> dict:
    if (
        not isinstance(text, str)
        or len(text) > 20000
        or strategy not in STRATEGIES
        or modality not in MODALITIES
    ):
        raise ValueError("invalid assessment input")
    c = validate_context(context)
    if os.environ.get("AIGUARD_NER_ENGINE") not in {None, "thainer"}:
        raise ValueError("assessment requires local thainer")
    if type(threshold) not in (int, float) or not 0 <= threshold <= 1:
        raise ValueError("invalid semantic threshold")
    findings = []
    engine = {
        "strategy": strategy,
        "status": "ok" if modality == "text" else "not_assessed",
        "semantic_status": "not_run",
    }
    if modality == "text":
        from pythainlp.corpus import get_corpus_db_detail, get_corpus_default_db
        from pythainlp.tools import get_full_data_path

        candidate = get_corpus_default_db("thainer-1.4", version="1.4")
        if candidate is None:
            filename = get_corpus_db_detail("thainer-1.4", version="1.4").get("filename")
            if not filename:
                raise RuntimeError("local NER asset unavailable")
            candidate = get_full_data_path(filename)
        if not Path(candidate).is_file():
            raise RuntimeError("local NER asset unavailable")
    diagnostics = NERChunkDiagnostics()
    entities = detect_all(text, ner_diagnostics=diagnostics) if modality == "text" else []
    if diagnostics.skipped:
        raise RuntimeError("assessment NER incomplete")
    engine["ner_chunks"] = diagnostics.as_dict()
    if modality == "text":
        raw = []
        if strategy == "keyword":
            aliases = {"RELIGION": "BELIEF", "RACE_ETHNICITY": "RACE"}
            for hit in scan_section26(text):
                category = aliases.get(hit["category"], hit["category"])
                if category == "RACE" and any(v in hit["text"] for v in ("เผ่าพันธุ์", "ชาติพันธุ์")):
                    category = "ETHNICITY"
                raw.append((category, hit["start"], hit["end"], "keyword_legacy", None))
        for category, pattern in _PATTERNS.items():
            if strategy == "keyword" and category in SENSITIVE:
                continue
            for hit in pattern.finditer(text):
                raw.append((category, hit.start(), hit.end(), "context_pattern", None))
        for entity in entities:
            category = _TYPE_FAMILY.get(entity.data_type)
            if category:
                raw.append((category, *entity.span, "identity_detector", None))
        if strategy == "hybrid":
            if semantic_backend is None:
                from pii_redactor.pdpa_semantic import semantic_model

                semantic_backend = semantic_model(model_dir)
            for hit in semantic_backend.topics(text, threshold=threshold):
                if not math.isfinite(float(hit["similarity"])):
                    raise RuntimeError("semantic evidence integrity failure")
                raw.append(
                    (
                        hit["category"],
                        hit["start"],
                        hit["end"],
                        "semantic_similarity",
                        hit["similarity"],
                    )
                )
            engine.update({"semantic_status": "ok", "semantic_identity": semantic_backend.identity})
        seen = set()
        for category, start, end, evidence, similarity in raw:
            if category not in (*SENSITIVE, *GENERAL) or not (0 <= start < end <= len(text)):
                raise RuntimeError("assessment evidence integrity failure")
            attribution, reason = (
                ("personal", "legacy_topic_as_alert")
                if strategy == "keyword"
                else _attribution(
                    text,
                    start,
                    end,
                    entities,
                    semantic=evidence == "semantic_similarity",
                    category=category,
                )
            )
            key = (category, start, end, attribution)
            if key in seen:
                continue
            seen.add(key)
            lo, hi = max(0, start - 45), min(len(text), end + 45)
            finding = {
                "category": category,
                "section": "26" if category in SENSITIVE else "6",
                "start": start,
                "end": end,
                "attribution": attribution,
                "evidence": evidence,
                "reason": reason,
                "polarity": "negated_or_qualified"
                if re.search(r"ไม่|negative|\bnot\b", text[lo:hi], re.I)
                else "unqualified",
                "quoted": any(ch in text[lo:hi] for ch in ('"', "“", "”")),
            }
            if similarity is not None:
                finding["similarity"] = round(float(similarity), 6)
            findings.append(finding)
    sensitive = any(f["section"] == "26" and f["attribution"] != "topic" for f in findings)
    reasons = []
    if modality != "text":
        reasons.append("review_modality")
    if sensitive:
        reasons.append("review_sensitive_processing")
    if any(f["attribution"] == "ambiguous" for f in findings):
        reasons.append("review_attribution_context")
    return {
        "schema": "aiguard.pdpa-assessment/1",
        "legal_clearance": False,
        "rule_version": LAW_VERSION,
        "engine": engine,
        "modality": modality,
        "offset_unit": "python_codepoint_in_assessed_text",
        "source_characters": len(text),
        "coverage": coverage_catalog(strategy),
        "open_scope_limit": True,
        "findings": sorted(findings, key=lambda f: (f["start"], f["category"])),
        "category_counts": dict(Counter(f["category"] for f in findings)),
        "review_reasons": reasons,
        "lifecycle": plan_lifecycle(c, sensitive=sensitive, unsupported=modality != "text"),
        "sources": SOURCES,
    }
