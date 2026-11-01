"""Harder synthetic splits for robustness work.

``dev`` may be inspected while fixing detectors. ``test`` uses another seed
and other sentence frames. Score ``test`` only after the fix is frozen.
Neither split is the sealed protocol corpus. All values are fabricated.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from benchmark.blind_v2.corpus import (
    _PEOPLE,
    _address,
    _bank,
    _card,
    _dob_numeric,
    _iban,
    _mobile,
    _passport,
    _Person,
    _plate,
    _student,
    _thai_id,
)
from benchmark.blind_v2.types import REDACTION_TYPES, SECTION26_TYPES

DEV_SEED = 20261102
TEST_SEED = 20261103
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Paraphrases that must not contain the keyword scanner's current cues.
DEV_PARAPHRASE = {
    "HEALTH": "น้ำตาลในเลือดสูงจนต้องกินยาทุกเช้า",
    "RELIGION": "ไปทำบุญที่วัดทุกวันพระ",
    "RACE_ETHNICITY": "บรรพบุรุษมาจากกลุ่มชาติพันธุ์กะเหรี่ยง",
    "POLITICAL_OPINION": "เขาเลือกพรรคเดิมทุกครั้งที่มีการเลือกตั้ง",
    "SEXUAL_BEHAVIOR": "เขาเปิดเผยว่าชอบคนเพศเดียวกัน",
    "CRIMINAL_RECORD": "เขาเคยถูกควบคุมตัวไว้ที่สถานีหลายวัน",
    "DISABILITY": "เขาใช้วีลแชร์มาตั้งแต่ยังเป็นเด็ก",
    "LABOR_UNION": "เขาเข้ากลุ่มคนงานที่ต่อรองค่าจ้างร่วมกัน",
}
TEST_PARAPHRASE = {
    "HEALTH": "หมอให้ยาเม็ดเพราะระดับกลูโคสไม่คงที่",
    "RELIGION": "เช้าวันพระเขาถือศีลและนั่งสมาธิที่ศาลา",
    "RACE_ETHNICITY": "ครอบครัวพูดภาษาของชุมชนบนดอย",
    "POLITICAL_OPINION": "เขาแจกใบปลิวของผู้สมัครคนเดิมหน้าตลาด",
    "SEXUAL_BEHAVIOR": "เขารักคนที่เป็นผู้ชายด้วยกัน",
    "CRIMINAL_RECORD": "ตำรวจเคยพาเขาไปห้องสอบสวนข้ามคืน",
    "DISABILITY": "ทางลาดหน้าบ้านทำไว้ให้รถเข็นของเขา",
    "LABOR_UNION": "เพื่อนร่วมกะรวมตัวกันขอขึ้นค่าแรง",
}

_DEV_FRAMES = (
    "เมื่อวาน {name} เล่าว่ากำลังจะย้าย และขอให้โทรหา {phone} ถ้ามีอะไรด่วน",
    "ในแชทมีคนส่งที่อยู่ใหม่ของ {name} มาว่า {address} พร้อมเบอร์ {phone}",
    "อีเมลภาษาอังกฤษลงท้ายว่า please reach {english} at {email} about the move",
    "{name} อ่านเลขสิบสามหลัก {thai_id} ออกเสียงทีละตัวให้เจ้าหน้าที่ฟัง",
    "เขาบอกรหัสนักเรียน {student} ปนกับวันเกิด {dob} ระหว่างเล่าประวัติ",
    "ใบเสร็จที่วางบนโต๊ะมีบัตร {card} และบัญชี {bank} ของ {name}",
    "เพื่อนส่งพาสปอร์ต {passport} กับไอแบน {iban} มาในข้อความยาว",
    "รถที่จอดหน้าบ้านป้าย {plate} เป็นของ {name} ที่เพิ่งกลับจากเชียงใหม่",
)
_TEST_FRAMES = (
    "บันทึกช่วยจำ: ไปเจอ {name} แถวร้านกาแฟ เขาให้เบอร์ติดต่อ {phone} ไว้",
    "จดหมายถึงตัวเองบอกว่า {name} ย้ายไปอยู่ {address} แล้ว",
    "A short English note says {english} can be mailed at {email} after Friday",
    "ตอนกรอกแบบเขาท่อง {thai_id} ผิดแล้วแก้ โดยไม่มีป้ายชื่อช่อง",
    "สมุดบันทึกนักเรียนเขียน {student} ไว้ข้างวันเกิด {dob}",
    "ภาพถ่ายสลิปโชว์ {card} และ {bank} ปนในประโยคของ {name}",
    "เขาแปะ {passport} กับ {iban} ไว้ท้ายโน้ตเดินทาง",
    "ป้ายทะเบียน {plate} โผล่ในเรื่องเล่าของ {name} เรื่องรถตู้รับส่ง",
)

_NEGATIVES_DEV = (
    "สูตรแกงส้มใช้มะละกอ กุ้งแห้ง และน้ำปลาเล็กน้อย เคี่ยวให้เข้ากันแล้วชิม",
    "พยากรณ์อากาศบอกว่าภาคอีสานมีฝนบางพื้นที่ ควรพกร่มเมื่อออกจากบ้าน",
    "ห้องสมุดเปิดให้ยืมอ่านโดยเขียนชื่อเล่นในสมุดเยี่ยมของห้อง",
    "การแข่งขันฟุตบอลของโรงเรียนจัดที่สนามหญ้าหลังอาคารเรียน",
)
_NEGATIVES_TEST = (
    "วิธีปลูกผักบุ้งในกระถางคือรดน้ำตอนเช้าและอย่าให้แดดจัดทั้งวัน",
    "ประกาศปิดปรับปรุงทางเดินเชื่อมอาคารเป็นเวลาหนึ่งสัปดาห์",
    "โน้ตสูตรขนมครกใช้หัวกะทิกับแป้งข้าวเจ้า คนให้เข้ากันแล้วตั้งไฟ",
    "รายงานน้ำในอ่างเก็บน้ำอยู่ในเกณฑ์ปกติไม่มีประกาศเตือน",
)


@dataclass(frozen=True)
class HardSpan:
    start: int
    end: int
    entity_type: str


@dataclass(frozen=True)
class HardDocument:
    doc_id: str
    split: str
    style: str
    text: str
    spans: tuple[HardSpan, ...]
    section26: tuple[str, ...]


@dataclass(frozen=True)
class HardCorpus:
    split: str
    seed: int
    documents: tuple[HardDocument, ...]


def _people():
    return [_Person(*row) for row in _PEOPLE]


_SECTION26_KEYWORDS = (
    "เชื้อชาติ",
    "เผ่าพันธุ์",
    "สัญชาติ",
    "ความคิดเห็นทางการเมือง",
    "พรรคการเมือง",
    "อุดมการณ์",
    "ศาสนา",
    "ความเชื่อ",
    "พุทธ",
    "คริสต์",
    "อิสลาม",
    "ฮินดู",
    "โรค",
    "การรักษา",
    "สุขภาพ",
    "ผลตรวจ",
    "เพศสัมพันธ์",
    "เพศวิถี",
    "รสนิยมทางเพศ",
    "คดี",
    "ต้องโทษ",
    "จำคุก",
    "ประวัติอาชญากรรม",
    "ถูกฟ้อง",
    "ทุพพลภาพ",
    "ความพิการ",
    "คนพิการ",
    "สหภาพแรงงาน",
    "สมาคมลูกจ้าง",
)


def _zw(text: str) -> str:
    return "\u200b".join(text)


def _spaced(text: str) -> str:
    return " ".join(text)


def _thai_digits(text: str) -> str:
    return text.translate({ord("0") + offset: ord("๐") + offset for offset in range(10)})


def _arabic_digits(text: str) -> str:
    return text.translate({ord("0") + offset: 0x0660 + offset for offset in range(10)})


def _ocr_digits(text: str) -> str:
    """Swap one digit for a lookalike that folds back to the same digit."""
    for index, char in enumerate(text):
        if char == "0":
            return text[:index] + "O" + text[index + 1 :]
        if char == "1":
            return text[:index] + "l" + text[index + 1 :]
    return text


def _fill(frame: str, values: dict[str, tuple[str, str]]) -> tuple[str, list[HardSpan]]:
    text = frame
    spans: list[HardSpan] = []
    # Replace the leftmost marker each time so offsets stay on the final text.
    while True:
        found = [(text.find("{" + key + "}"), key) for key in values if "{" + key + "}" in text]
        found = [(pos, key) for pos, key in found if pos >= 0]
        if not found:
            break
        pos, key = min(found)
        surface, entity_type = values[key]
        marker = "{" + key + "}"
        text = text[:pos] + surface + text[pos + len(marker) :]
        if entity_type:
            spans.append(HardSpan(pos, pos + len(surface), entity_type))
    spans.sort(key=lambda span: (span.start, span.end))
    return text, spans


def _values(rng: random.Random, email_n: int, transform: str) -> dict[str, tuple[str, str]]:
    person = rng.choice(_people())
    thai_id = _thai_id(rng)
    phone = _mobile(rng)
    if transform == "zwsp":
        thai_id = _zw(thai_id)
        phone = _zw(phone)
    elif transform == "spaced":
        thai_id = _spaced(thai_id)
        phone = _spaced(phone)
    elif transform == "thai_digits":
        thai_id = _thai_digits(thai_id)
        phone = _thai_digits(phone)
    elif transform == "arabic_digits":
        thai_id = _arabic_digits(thai_id)
        phone = _arabic_digits(phone)
    elif transform == "ocr":
        thai_id = _ocr_digits(thai_id)
    name = person.thai
    if transform == "zwsp":
        name = _zw(name)
    elif transform == "spaced":
        name = _spaced(name.replace(" ", ""))
    elif transform == "ocr":
        name = person.given + person.surname
    return {
        "name": (name, "NAME"),
        "english": (person.english, "NAME"),
        "phone": (phone, "PHONE"),
        "address": (_address(rng), "ADDRESS"),
        "email": (_email_for(person, email_n), "EMAIL"),
        "thai_id": (thai_id, "THAI_ID"),
        "student": (_student(rng), "STUDENT_ID"),
        "dob": (_dob_numeric(rng), "DATE_OF_BIRTH"),
        "card": (_card(rng), "CREDIT_CARD"),
        "bank": (_bank(rng), "BANK_ACCOUNT"),
        "passport": (_passport(rng), "PASSPORT"),
        "iban": (_iban(rng), "IBAN"),
        "plate": (_plate(rng, leading_digit=False), "VEHICLE_PLATE"),
    }


def _email_for(person, number: int) -> str:
    return f"{person.en_given}.{person.en_sur}.{number}@example.com"


def generate_hard(split: str) -> HardCorpus:
    if split not in {"dev", "test"}:
        raise ValueError("unknown split")
    seed = DEV_SEED if split == "dev" else TEST_SEED
    frames = _DEV_FRAMES if split == "dev" else _TEST_FRAMES
    negatives = _NEGATIVES_DEV if split == "dev" else _NEGATIVES_TEST
    paraphrases = DEV_PARAPHRASE if split == "dev" else TEST_PARAPHRASE
    rng = random.Random(seed)
    documents: list[HardDocument] = []
    transforms = ("clean", "zwsp", "spaced", "thai_digits", "arabic_digits", "ocr")
    email_n = 0
    for transform in transforms:
        for index, frame in enumerate(frames):
            email_n += 1
            text, spans = _fill(frame, _values(rng, email_n, transform))
            if transform == "clean" and index == 0:
                text += " มีเสียงรบกวนจากพัดลมและตัวอักษรซ้อนกันเล็กน้อย"
            documents.append(
                HardDocument(
                    doc_id=f"hard-{split}-{len(documents):04d}",
                    split=split,
                    style=f"prose-{transform}",
                    text=text,
                    spans=tuple(spans),
                    section26=(),
                )
            )
    for category in SECTION26_TYPES:
        email_n += 1
        person = rng.choice(_people())
        frame = (
            "บันทึกเล่าว่า {name} " + paraphrases[category]
            if split == "dev"
            else "โน้ตส่วนตัวกล่าวถึง {name} ว่า" + paraphrases[category]
        )
        text, spans = _fill(frame, {"name": (person.thai, "NAME")})
        documents.append(
            HardDocument(
                doc_id=f"hard-{split}-{len(documents):04d}",
                split=split,
                style="section26-paraphrase",
                text=text,
                spans=tuple(spans),
                section26=(category,),
            )
        )
    for index, negative in enumerate(negatives):
        documents.append(
            HardDocument(
                doc_id=f"hard-{split}-{len(documents):04d}",
                split=split,
                style="negative",
                text=negative,
                spans=(),
                section26=(),
            )
        )
    return HardCorpus(split=split, seed=seed, documents=tuple(documents))


def canonical_bytes(corpus: HardCorpus) -> bytes:
    payload = {
        "documents": [
            {
                "doc_id": doc.doc_id,
                "section26": list(doc.section26),
                "spans": [
                    {"end": span.end, "entity_type": span.entity_type, "start": span.start}
                    for span in doc.spans
                ],
                "split": doc.split,
                "style": doc.style,
                "text": doc.text,
            }
            for doc in corpus.documents
        ],
        "seed": corpus.seed,
        "split": corpus.split,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def public_lock(corpus: HardCorpus) -> dict:
    type_counts: Counter[str] = Counter()
    style_counts: Counter[str] = Counter()
    for doc in corpus.documents:
        style_counts[doc.style] += 1
        for span in doc.spans:
            type_counts[span.entity_type] += 1
    return {
        "documents": len(corpus.documents),
        "labels_committed": False,
        "plaintext_sha256": hashlib.sha256(canonical_bytes(corpus)).hexdigest(),
        "redaction_types": list(REDACTION_TYPES),
        "section26_paraphrase_documents": sum(1 for doc in corpus.documents if doc.section26),
        "seed": corpus.seed,
        "split": corpus.split,
        "style_counts": dict(sorted(style_counts.items())),
        "type_counts": dict(sorted((key, value) for key, value in type_counts.items() if value)),
        "version": f"hard-{corpus.split}-v1",
    }


def lock_path(split: str) -> Path:
    return DATA_DIR / f"hard-{split}.lock.json"


def validate_hard(corpus: HardCorpus) -> list[str]:
    errors: list[str] = []
    paraphrases = DEV_PARAPHRASE if corpus.split == "dev" else TEST_PARAPHRASE
    cues = (
        "เลขประจำตัว",
        "เบอร์โทร",
        "ที่อยู่ ",
        "รหัสนักศึกษา",
        "หนังสือเดินทาง",
        "เลขที่บัญชี",
        "หมายเลขบัตร",
        "เกิดวันที่",
        "ทะเบียนรถ",
    )
    for doc in corpus.documents:
        if any(cue in doc.text for cue in cues) or "{" in doc.text:
            errors.append("field-label")
        cursor = -1
        for span in doc.spans:
            if not (0 <= span.start < span.end <= len(doc.text)) or span.start < cursor:
                errors.append("bad-span")
            cursor = span.end
            if span.entity_type not in REDACTION_TYPES:
                errors.append("bad-type")
        if doc.style == "negative" and (doc.spans or any(ch.isdigit() for ch in doc.text)):
            errors.append("dirty-negative")
        for category in doc.section26:
            phrase = paraphrases[category]
            if phrase not in doc.text:
                errors.append("missing-paraphrase")
            for keyword in _SECTION26_KEYWORDS:
                if keyword in doc.text:
                    errors.append("paraphrase-has-keyword")
    if not any(doc.style == "prose-zwsp" for doc in corpus.documents):
        errors.append("missing-zwsp")
    if not any("\u0e50" <= ch <= "\u0e59" for doc in corpus.documents for ch in doc.text):
        errors.append("missing-thai-digits")
    if not any("\u0660" <= ch <= "\u0669" for doc in corpus.documents for ch in doc.text):
        errors.append("missing-arabic-digits")
    return errors
