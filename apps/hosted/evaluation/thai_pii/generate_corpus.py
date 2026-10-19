#!/usr/bin/env python3
"""Generate the immutable synthetic Thai PII evaluation corpus.

The inputs below were constructed locally for this repository. They were not
copied from users, logs, providers, production traffic, or benchmark datasets.
The generator uses only the Python standard library and never opens a network
connection. Values are synthetic-context test shapes; no allocation lookup is
performed and no claim of real-world non-collision is made.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import random
import re
from collections import Counter
from pathlib import Path

SCHEMA_VERSION = 1
SEED = 20260810
ROOT = Path(__file__).resolve().parent
MARKER = re.compile(r"\[\[([A-Z][A-Z0-9_]*)::(.*?)\]\]", re.DOTALL)


def _compile(marked: str) -> tuple[str, list[dict[str, int | str]]]:
    """Remove annotation markers and derive half-open Python-code-point spans."""

    text_parts: list[str] = []
    spans: list[dict[str, int | str]] = []
    cursor = 0
    output_length = 0
    for match in MARKER.finditer(marked):
        prefix = marked[cursor : match.start()]
        value = match.group(2)
        if not value or "[[" in value or "]]" in value:
            raise ValueError("invalid annotation marker")
        text_parts.append(prefix)
        output_length += len(prefix)
        start = output_length
        text_parts.append(value)
        output_length += len(value)
        spans.append({"start_cp": start, "end_cp": output_length, "type": match.group(1)})
        cursor = match.end()
    suffix = marked[cursor:]
    if "[[" in suffix or "]]" in suffix:
        raise ValueError("unparsed annotation marker")
    text_parts.append(suffix)
    return "".join(text_parts), spans


def _base(
    base_id: str,
    scenario: str,
    marked: str,
    phenomena: list[str],
    *,
    action: str = "mask_required",
) -> dict:
    return {
        "base_id": base_id,
        "scenario": scenario,
        "marked": marked,
        "action": action,
        "phenomena": phenomena,
    }


# These are annotation templates, not detector fixtures: no expected output is
# consulted here. Each positive marker states the protective unit a reviewer
# would want masked; it never carries a duplicated raw-value field.
POSITIVE_BASES = [
    _base("name_male_prefix", "person", "ผู้สมัครชื่อ [[NAME::นายกิตติทดสอบ ใจจำลอง]]", ["thai", "title", "space"]),
    _base("name_female_prefix", "person", "ผู้ติดต่อคือ [[NAME::นางพิมพ์ทดสอบ ข้อมูลสมมติ]]", ["thai", "title", "space"]),
    _base("name_miss_prefix", "person", "นักเรียน [[NAME::นางสาวดาราทดสอบ แสงจำลอง]] มารายงานตัว", ["thai", "long-title"]),
    _base("name_label_no_prefix", "person", "ชื่อ-นามสกุล: [[NAME::ชลทดสอบ เมฆสมมติ]]", ["thai", "explicit-label", "no-title"]),
    _base("name_glued", "person", "ชื่อผู้สมัคร:[[NAME::กิตติทดสอบใจจำลอง]]", ["thai", "no-space", "explicit-label"]),
    _base("name_repeated", "person", "[[NAME::นายกิตติทดสอบ ใจจำลอง]] พบ [[NAME::นายกิตติทดสอบ ใจจำลอง]]", ["thai", "repeated"]),
    _base("phone_mobile_08", "phone", "โทร [[PHONE::0800000000]]", ["mobile", "contiguous"]),
    _base("phone_mobile_09", "phone", "เบอร์ติดต่อ [[PHONE::0900000000]]", ["mobile", "contiguous"]),
    _base("phone_mobile_06", "phone", "มือถือ [[PHONE::0600000000]]", ["mobile", "contiguous"]),
    _base("phone_hyphen", "phone", "โทรศัพท์ [[PHONE::089-000-0000]]", ["mobile", "hyphen"]),
    _base("phone_space", "phone", "ติดต่อ [[PHONE::081 000 0000]]", ["mobile", "space"]),
    _base("phone_international", "phone", "หมายเลขไทย [[PHONE::+66 81 000 0000]]", ["international", "space"]),
    _base("phone_parenthesized", "phone", "ติดต่อ [[PHONE::(089) 000-0000]]", ["mobile", "parentheses", "adversarial"]),
    _base("phone_zero_width", "phone", "มือถือ [[PHONE::08\u200b90000000]]", ["mobile", "zero-width", "adversarial"]),
    _base("email_plain", "email", "อีเมล [[EMAIL::person.test@example.invalid]]", ["ascii", "invalid-tld"]),
    _base("email_subdomain", "email", "ส่งถึง [[EMAIL::unit@test.lab.example.invalid]]", ["subdomain", "invalid-tld"]),
    _base("email_plus", "email", "บัญชี [[EMAIL::demo+hr@example.invalid]]", ["plus-alias", "invalid-tld"]),
    _base("email_mixed_case", "email", "Email: [[EMAIL::Demo.User@Example.Invalid]]", ["mixed-case", "invalid-tld"]),
    _base("email_adjacent_thai", "email", "อีเมล[[EMAIL::joined@example.invalid]]สำหรับทดสอบ", ["thai-adjacency", "invalid-tld"]),
    _base("thai_id_checksum", "thai-id", "เลขบัตรประชาชน [[THAI_ID::8000000000006]]", ["checksum-valid-shape", "contiguous"]),
    _base("thai_id_spaced", "thai-id", "เลขประจำตัว [[THAI_ID::8 0000 00000 00 6]]", ["checksum-valid-shape", "space"]),
    _base("thai_id_hyphen", "thai-id", "บัตรประชาชน [[THAI_ID::8-0000-00000-00-6]]", ["checksum-valid-shape", "hyphen"]),
    _base("thai_id_invalid_checksum", "thai-id", "เลขบัตรที่อ่านไม่ชัด [[THAI_ID::8000000000005]]", ["checksum-invalid-shape", "recall-first"]),
    _base("thai_id_thai_digits", "thai-id", "เลขบัตรประชาชน [[THAI_ID::๘๐๐๐๐๐๐๐๐๐๐๐๖]]", ["thai-digits", "length-preserving-normalization"]),
    _base("address_house", "address", "บ้านเลขที่ [[ADDRESS::999/999]]", ["house-number"]),
    _base("address_road", "address", "อาศัยอยู่ถนน[[ADDRESS::ทดสอบ 99]]", ["road", "thai"]),
    _base("address_soi", "address", "ที่อยู่ซอย[[ADDRESS::จำลอง 88]]", ["soi", "thai"]),
    _base("address_admin", "address", "ตำบล[[ADDRESS::หนองทดสอบ]] อำเภอ[[ADDRESS::เมืองจำลอง]]", ["admin-area", "multiple"]),
    _base("address_full", "address", "บ้านเลขที่ [[ADDRESS::999/999 ถนนทดสอบ ตำบลจำลอง อำเภอเมือง นครปฐม 73000]]", ["full-address", "coalescing"]),
    _base("address_multiline", "address", "ที่อยู่:\n[[ADDRESS::999/999 ถนนทดสอบ]]\nตำบล[[ADDRESS::จำลอง]]", ["multiline", "form"]),
    _base("org_hospital", "organization", "หน่วยงาน [[ORGANIZATION::โรงพยาบาลทดสอบกลาง]]", ["hospital", "thai"]),
    _base("org_school", "organization", "สถานศึกษา [[ORGANIZATION::โรงเรียนสาธิตข้อมูล]]", ["school", "thai"]),
    _base("org_university", "organization", "สังกัด [[ORGANIZATION::มหาวิทยาลัยจำลองไทย]]", ["university", "thai"]),
    _base("org_company", "organization", "นายจ้าง [[ORGANIZATION::บริษัท ทดสอบระบบ จำกัด]]", ["company", "thai"]),
    _base("credit_card", "financial", "บัตรทดสอบ [[CREDIT_CARD::4000000000000002]]", ["luhn-valid-test-shape"]),
    _base("iban", "financial", "บัญชีทดสอบ [[IBAN::GB05TEST00000000000000]]", ["mod97-valid-test-shape"]),
    _base("bank_account", "financial", "บัญชีธนาคาร [[BANK_ACCOUNT::000-0-00000-0]]", ["bank-cue", "all-zero-test-shape"]),
    _base("date_birth_numeric", "date", "วันเกิด [[DATE_OF_BIRTH::31/12/2540]]", ["birth-cue", "numeric"]),
    _base("date_birth_thai_month", "date", "เกิดวันที่ [[DATE_OF_BIRTH::31 ธันวาคม 2540]]", ["birth-cue", "thai-month"]),
    _base("date_generic", "date", "วันนัดหมาย [[DATE::10/08/2569]]", ["generic-date"]),
    _base("vehicle_plate", "vehicle", "ทะเบียนรถ [[VEHICLE_PLATE::ทด 0000]]", ["thai-plate", "test-shape"]),
    _base("passport", "identifier", "หนังสือเดินทาง [[PASSPORT::ZZ0000000]]", ["passport-cue", "test-shape"]),
    _base("student_id", "identifier", "รหัสนักศึกษา [[STUDENT_ID::00000000]]", ["student-cue", "all-zero-test-shape"]),
    _base("medical_id", "identifier", "HN: [[MEDICAL_ID::0000]]", ["medical-cue", "all-zero-test-shape"]),
    _base("postal_code", "address", "ที่อยู่สำหรับทดสอบ รหัสไปรษณีย์ [[POSTAL_CODE::00000]]", ["postal-cue", "all-zero-test-shape"]),
    _base("generic_id", "identifier", "เลขที่เอกสาร [[ID_NUMBER::00000000]]", ["generic-id", "all-zero-test-shape"]),
    _base("location", "location", "สถานที่จัดกิจกรรมคือ [[LOCATION::เชียงใหม่]]", ["thai-location", "quasi-identifier"]),
    _base("mixed_hr", "mixed", "ผู้สมัคร [[NAME::นายกิตติทดสอบ ใจจำลอง]] โทร [[PHONE::0800000000]] อีเมล [[EMAIL::hr.case@example.invalid]]", ["hr", "multiple-types"]),
    _base("mixed_health", "mixed", "ผู้ป่วย [[NAME::นางพิมพ์ทดสอบ ข้อมูลสมมติ]] HN [[MEDICAL_ID::0000]] ติดต่อ [[PHONE::0900000000]]", ["healthcare", "multiple-types"]),
    _base("mixed_school", "mixed", "นักเรียน [[NAME::ดาราทดสอบ แสงจำลอง]] รหัสนักศึกษา [[STUDENT_ID::00000000]]", ["school", "multiple-types"]),
    _base("mixed_json", "mixed", "{\"name\":\"[[NAME::ชลทดสอบ เมฆสมมติ]]\",\"email\":\"[[EMAIL::json.case@example.invalid]]\"}", ["json-like", "multiple-types"]),
]

NEGATIVE_BASES = [
    ("neg_money", "ราคา", "ยอดรวม 12,500.75 บาท", ["money"]),
    ("neg_product", "reference", "รหัสสินค้า SKU-0000000000 รุ่นทดลอง", ["product-code"]),
    ("neg_ticket", "reference", "หมายเลขตั๋ว TKT-2026-000042", ["ticket-number"]),
    ("neg_course", "education", "รายวิชา CS101 ตอน 02", ["course-code"]),
    ("neg_ipv4_doc", "technical", "ตัวอย่างเอกสารใช้ IP 192.0.2.44", ["reserved-ip"]),
    ("neg_ipv6_doc", "technical", "ตัวอย่าง IPv6 คือ 2001:db8::42", ["reserved-ip"]),
    ("neg_version", "technical", "ซอฟต์แวร์เวอร์ชัน 2.5.0 build 72", ["version"]),
    ("neg_timestamp", "technical", "บันทึกเวลา 2026-08-10T09:30:00Z", ["timestamp"]),
    ("neg_random_digits", "reference", "ลำดับสุ่ม 1234567 ใช้ทดสอบ", ["short-digit-run"]),
    ("neg_invoice", "commerce", "ใบแจ้งหนี้เลขที่ 2569-004512", ["invoice-number"]),
    ("neg_purchase_order", "commerce", "ใบสั่งซื้อ PO-0000000000", ["purchase-order"]),
    ("neg_date_release", "technical", "รุ่นนี้เผยแพร่วันที่ 10/08/2569", ["non-personal-date"]),
    ("neg_clock", "technical", "ระบบทำงานเวลา 17.40 น.", ["time"]),
    ("neg_amount_equation", "commerce", "รวมเป็นเงิน 600000+120000 = 720000 บาท", ["amount-expression"]),
    ("neg_doc_heading", "document", "แบบประเมินผลการทำงานประจำปี", ["heading"]),
    ("neg_contract_word", "language", "สัญญาเช่าฉบับนี้เป็นแม่แบบ", ["name-like-word"]),
    ("neg_company_term", "language", "บริษัทเป็นนิติบุคคลรูปแบบหนึ่ง", ["generic-organization-term"]),
    ("neg_province_term", "language", "จังหวัดเป็นหน่วยการปกครอง", ["generic-location-term"]),
    ("neg_postcode_list", "address", "พื้นที่บริการ 10110, 10210, 10310", ["postcode-enumeration"]),
    ("neg_malformed_email", "email", "รูปแบบที่ผิด demo@@example และ user@example", ["near-miss"]),
    ("neg_long_digits", "reference", "หมายเลขล็อต 12345678901234567", ["long-digit-run"]),
    ("neg_markdown", "document", "## หัวข้อ\n- รายการหนึ่ง\n- รายการสอง", ["markdown"]),
    ("neg_emoji", "chat", "สถานะการทดสอบ ✅ ผ่านขั้นตอนที่ 3", ["emoji"]),
    ("neg_url_doc", "technical", "คู่มือตัวอย่างอยู่ที่ https://example.invalid/docs", ["invalid-domain"]),
]

AMBIGUOUS_BASES = [
    ("amb_name_word", "person", "วันนี้มีสัญญาเข้าร่วมประชุม", ["name-like-word"]),
    ("amb_bare_name", "person", "กิตติทดสอบ ใจจำลอง", ["bare-name"]),
    ("amb_location", "location", "เชียงใหม่มีอากาศเย็น", ["place-not-person-linked"]),
    ("amb_org", "organization", "โรงเรียนสาธิตข้อมูลเปิดรับสมัคร", ["organization-not-person-linked"]),
    ("amb_ten_digits", "reference", "รหัส 0800000000", ["phone-bank-id-collision"]),
    ("amb_date", "date", "10/08/2569", ["date-without-context"]),
    ("amb_room", "location", "จองห้องประชุม 1204 จำนวน 20 ที่นั่ง", ["facility"]),
    ("amb_plate_shape", "vehicle", "ตัวอย่างรูปแบบ กข 1234", ["quoted-shape"]),
    ("amb_quote_email", "email", "คำว่า person.test@example.invalid เป็นตัวอย่าง", ["quoted-synthetic-value"]),
    ("amb_address_policy", "address", "แบบฟอร์มต้องมีบ้านเลขที่และถนน", ["address-terms-only"]),
    ("amb_student_shape", "identifier", "เลข 00000000 อาจเป็นรหัสหลายชนิด", ["generic-id"]),
    ("amb_medical_word", "identifier", "หัวข้อ HN ใช้ในระบบโรงพยาบาล", ["medical-label-only"]),
]

WRAPPERS = [
    ("plain", "{text}"),
    ("punctuation", "รายการทดสอบ: “{text}” (จบรายการ)"),
]

SECTION26_TERMS = {
    "RACE_ETHNICITY": ("เชื้อชาติ", "รายงานกล่าวถึงนโยบายห้ามเลือกปฏิบัติทางเชื้อชาติ"),
    "POLITICAL_OPINION": ("ความคิดเห็นทางการเมือง", "คู่มืออธิบายคำว่าความคิดเห็นทางการเมืองโดยทั่วไป"),
    "RELIGION": ("ศาสนา", "แบบเรียนมีบทว่าด้วยศาสนาเปรียบเทียบ"),
    "HEALTH": ("ประวัติการรักษา", "ประกาศรณรงค์เรื่องสุขภาพของประชาชน"),
    "SEXUAL_BEHAVIOR": ("รสนิยมทางเพศ", "นโยบายห้ามเลือกปฏิบัติจากรสนิยมทางเพศ"),
    "CRIMINAL_RECORD": ("ประวัติอาชญากรรม", "ข่าวอธิบายคำว่าประวัติอาชญากรรม"),
    "DISABILITY": ("ความพิการ", "อาคารออกแบบเพื่อการเข้าถึงของคนพิการ"),
    "LABOR_UNION": ("สหภาพแรงงาน", "บทเรียนอธิบายบทบาทของสหภาพแรงงาน")
}


def build_corpus() -> dict:
    rng = random.Random(SEED)
    cases: list[dict] = []
    sequence = 1
    for base in POSITIVE_BASES:
        wrappers = list(WRAPPERS)
        rng.shuffle(wrappers)
        for wrapper_name, wrapper in wrappers:
            marked = wrapper.format(text=base["marked"])
            text, spans = _compile(marked)
            cases.append(
                {
                    "case_id": f"C{sequence:04d}",
                    "base_id": base["base_id"],
                    "text": text,
                    "expected_spans": spans,
                    "scenario": base["scenario"],
                    "action": base["action"],
                    "phenomena": sorted(set(base["phenomena"] + [wrapper_name])),
                    "provenance": f"constructed-template:{base['base_id']}",
                }
            )
            sequence += 1
    for base_id, scenario, text, phenomena in NEGATIVE_BASES:
        cases.append(
            {
                "case_id": f"C{sequence:04d}",
                "base_id": base_id,
                "text": text,
                "expected_spans": [],
                "scenario": scenario,
                "action": "do_not_mask",
                "phenomena": sorted(phenomena),
                "provenance": f"constructed-template:{base_id}",
            }
        )
        sequence += 1
    for base_id, scenario, text, phenomena in AMBIGUOUS_BASES:
        cases.append(
            {
                "case_id": f"C{sequence:04d}",
                "base_id": base_id,
                "text": text,
                "expected_spans": [],
                "scenario": scenario,
                "action": "ambiguous",
                "phenomena": sorted(phenomena),
                "provenance": f"constructed-template:{base_id}",
            }
        )
        sequence += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_id": "aiguard-thai-pii-adversarial-v1",
        "synthetic_declaration": (
            "Constructed locally from reviewed templates; no user, log, production, provider, "
            "or real-person record was used. Shape-valid strings are synthetic-context values "
            "and are never contacted or asserted to be unallocated."
        ),
        "offset_unit": "unicode_code_point_half_open",
        "cases": cases,
    }


def build_section26() -> dict:
    cases: list[dict] = []
    sequence = 1
    for category, (positive_term, contextual_negative) in SECTION26_TERMS.items():
        rows = [
            (f"ตรวจพบคำสัญญาณ {positive_term} ในข้อความจำลอง", [category], "review_signal", ["keyword"]),
            (f"รายการแบบฟอร์ม: {positive_term}", [category], "review_signal", ["form-label"]),
            (contextual_negative, [], "no_signal", ["contextual-negative"]),
            (f"ข้อความนี้ปฏิเสธว่าไม่มีข้อมูลเกี่ยวกับ{positive_term}", [], "no_signal", ["negation"]),
        ]
        for index, (text, expected, action, phenomena) in enumerate(rows, start=1):
            template_id = f"s26_{category.lower()}_{index}"
            cases.append(
                {
                    "case_id": f"S{sequence:04d}",
                    "text": text,
                    "expected_categories": expected,
                    "action": action,
                    "phenomena": phenomena,
                    "provenance": f"constructed-template:{template_id}",
                }
            )
            sequence += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_id": "aiguard-section26-heuristic-v1",
        "semantics": "heuristic keyword signal evaluation; not PDPA compliance accuracy",
        "cases": cases,
    }


def _canonical_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus = build_corpus()
    section26 = build_section26()
    corpus_bytes = _canonical_bytes(corpus)
    section26_bytes = _canonical_bytes(section26)
    generator_bytes = Path(inspect.getsourcefile(generate) or __file__).read_bytes()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "manifest_id": "aiguard-thai-pii-adversarial-v1",
        "source_kind": "constructed",
        "license": "CC0-1.0",
        "fixed_seed": SEED,
        "generator": "generate_corpus.py",
        "generator_sha256": _sha256(generator_bytes),
        "corpus_schema": "corpus.schema.json",
        "corpus_schema_sha256": _sha256((ROOT / "corpus.schema.json").read_bytes()),
        "corpus_file": "corpus.v1.json",
        "corpus_sha256": _sha256(corpus_bytes),
        "corpus_case_count": len(corpus["cases"]),
        "section26_file": "section26.v1.json",
        "section26_schema": "section26.schema.json",
        "section26_schema_sha256": _sha256((ROOT / "section26.schema.json").read_bytes()),
        "section26_sha256": _sha256(section26_bytes),
        "section26_case_count": len(section26["cases"]),
        "base_template_count": len(POSITIVE_BASES) + len(NEGATIVE_BASES) + len(AMBIGUOUS_BASES),
        "template_inventory": dict(sorted(Counter(case["scenario"] for case in corpus["cases"]).items())),
        "source_exclusions": [
            "production traffic",
            "user submissions",
            "logs",
            "provider output",
            "scraped data",
            "historical evidence fixtures"
        ],
        "identifier_caveat": (
            "Structured strings were constructed for synthetic contexts. No allocation lookup or contact "
            "was performed, so the evidence does not claim that every possible string is unallocated."
        ),
        "annotation": {
            "method": "template-bound programmatic spans",
            "offset_convention": "Unicode code-point half-open intervals; no scoring-time normalization",
            "detector_output_visible_during_annotation": False,
            "thai_human_adjudication": "pending",
            "ambiguous_cases_excluded_from_headline": True
        }
    }
    (output_dir / "corpus.v1.json").write_bytes(corpus_bytes)
    (output_dir / "section26.v1.json").write_bytes(section26_bytes)
    (output_dir / "manifest.v1.json").write_bytes(_canonical_bytes(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    manifest = generate(args.output_dir.resolve())
    print(
        f"generated {manifest['corpus_case_count']} PII cases and "
        f"{manifest['section26_case_count']} Section 26 cases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
