"""Seeded synthetic corpus for the blind-v2 comparison freeze.

Every value is fabricated. The committed lock stores the SHA-256 of the
canonical document JSON, the seed, and aggregate counts. It does not store
document text or entity surfaces. Regenerating with ``GENERATION_SEED`` must
reproduce that hash. Do not edit generated text to chase a score.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .types import REDACTION_TYPES, SECTION26_TYPES

VERSION = "blind-v2-repro"
GENERATION_SEED = 20261101
LOCK_PATH = Path(__file__).resolve().parents[1] / "data" / "blind-v2-repro.lock.json"

_MONTHS = (
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
)

# Textbook given-name/surname pairs. Combinations are synthetic; they are not
# drawn from a real register.
_PEOPLE = (
    ("สมชาย", "ใจดี", "somchai", "jaidee"),
    ("สมหญิง", "รักดี", "somying", "rakdee"),
    ("วิชัย", "ศรีสุข", "wichai", "srisuk"),
    ("วิไล", "สุขใจ", "wilai", "sukjai"),
    ("ประเสริฐ", "ทองดี", "prasert", "thongdee"),
    ("ปราณี", "แก้วใส", "pranee", "kaewsai"),
    ("อนุชา", "พูนผล", "anucha", "poonphon"),
    ("มานี", "มีสุข", "manee", "meesuk"),
    ("ชูใจ", "บุญมา", "chujai", "boonma"),
    ("สมศักดิ์", "แสงทอง", "somsak", "saengthong"),
    ("นิตยา", "วงศ์ดี", "nittaya", "wongdee"),
    ("ธนา", "ตั้งตรง", "thana", "tangtrong"),
    ("กมลชนก", "ใจงาม", "kamonchanok", "jaingam"),
    ("ภาคิน", "สายชล", "pakin", "saichon"),
    ("อรุณี", "พิมพ์ดี", "arunee", "phimdee"),
    ("วรพล", "นาคิน", "woraphon", "nakin"),
)

_BKK = (
    ("จอมพล", "จตุจักร", "10900", "ลาดพร้าว"),
    ("คลองเตย", "คลองเตย", "10110", "สุขุมวิท"),
    ("สามเสนใน", "พญาไท", "10400", "พหลโยธิน"),
    ("สีลม", "บางรัก", "10500", "สีลม"),
)
_PROVINCES = (
    ("สุเทพ", "เมืองเชียงใหม่", "เชียงใหม่", "50200", "นิมมานเหมินทร์"),
    ("ในเมือง", "เมืองขอนแก่น", "ขอนแก่น", "40000", "มิตรภาพ"),
    ("ตลาดใหญ่", "เมืองภูเก็ต", "ภูเก็ต", "83000", "ราษฎร์อุทิศ"),
    ("พระบาท", "เมืองลำปาง", "ลำปาง", "52000", "ฉัตรไชย"),
)

_S26 = {
    "HEALTH": "ผลตรวจสุขภาพระบุโรคความดัน",
    "RELIGION": "นับถือศาสนาพุทธ",
    "RACE_ETHNICITY": "ระบุเชื้อชาติในแบบทะเบียน",
    "POLITICAL_OPINION": "แสดงความคิดเห็นทางการเมืองเรื่องงบประมาณท้องถิ่น",
    "SEXUAL_BEHAVIOR": "ช่องรสนิยมทางเพศไม่ได้กรอก",
    "CRIMINAL_RECORD": "ไม่มีประวัติอาชญากรรม",
    "DISABILITY": "ไม่มีความพิการตามนิยามในแบบฟอร์ม",
    "LABOR_UNION": "ไม่ได้เป็นสมาชิกสหภาพแรงงาน",
}

_FILLER_A = (
    "ฝ่ายสารบรรณขอให้ทุกหน่วยงานตรวจร่างประกาศภายในให้ถ้อยคำตรงกับมติที่ประชุม "
    "และส่งความเห็นกลับมาก่อนปิดภาคเรียน โดยไม่ต้องแนบสำเนาเอกสารส่วนบุคคล "
)
_FILLER_B = (
    "จุดประสงค์คือให้ข้อความในประกาศอ่านแล้วเข้าใจตรงกันทั้งฉบับ "
    "หากย่อหน้าใดยังกำกวมให้ขีดเส้นใต้แล้วเสนอถ้อยคำใหม่ทั้งประโยค "
)
_FILLER_C = (
    "หลังรวมความเห็นแล้ว สำนักจะจัดทำฉบับส่งพิมพ์และปิดประกาศที่บอร์ดกลาง ผู้ปฏิบัติงานทั่วไปไม่ต้องเดินทางมาลงชื่ออีกครั้ง "
)

_NEGATIVES = (
    "สภาพอากาศภาคเหนือมีฝนกระจาย อุณหภูมิกลางวันอยู่ในระดับอบอุ่น ชาวบ้านควรพกร่มเมื่อออกจากบ้าน",
    "สูตรต้มยำน้ำใสใช้ตะไคร้ ใบมะกรูด พริกแห้ง และน้ำปลาประมาณหนึ่งช้อนโต๊ะ เคี่ยวไฟอ่อนจนหอม",
    "ห้องสมุดเปิดให้ยืมอ่านได้โดยลงชื่อในสมุดเยี่ยมของห้องสมุด ไม่ต้องใช้เอกสารราชการ",
    "การแข่งขันฟุตบอลของโรงเรียนจัดที่สนามกลางหมู่บ้าน ผู้ชมเข้าได้โดยไม่ต้องซื้อตั๋ว",
    "สำนักงานหยุดทำการช่วงเทศกาลสงกรานต์และเปิดให้บริการอีกครั้งหลังเทศกาลสิ้นสุด",
    "วิธีดูแลต้นไม้ในกระถางคือรดน้ำตอนเช้า หลีกเลี่ยงแดดจัดทั้งวัน และเปลี่ยนดินเมื่อดินแน่น",
    "บันทึกการประชุมฝ่ายอาคารเรื่องซ่อมหลอดไฟทางเดิน ยังไม่ได้มอบหมายเป็นรายบุคคล",
    "คู่มือแยกขยะเปียกและขยะรีไซเคิลของเทศบาลให้ใช้ถังคนละสีและวางหน้าบ้านในวันเก็บขยะ",
    "บทความแนะนำการเดินทางด้วยรถประจำทางในเมือง ควรเผื่อเวลาช่วงเช้าเพราะรถหนาแน่น",
    "โน้ตสูตรขนมครกใช้หัวกะทิ แป้งข้าวเจ้า และน้ำตาลมะพร้าว คนให้เข้ากันแล้วยกขึ้นตั้งไฟ",
    "กำหนดการซ้อมดนตรีของวงโรงเรียนอยู่ที่หอประชุมหลังเลิกเรียน ผู้สนใจดูบอร์ดกิจกรรม",
    "รายงานน้ำในอ่างเก็บน้ำอยู่ในเกณฑ์ปกติ ไม่มีประกาศเตือนน้ำท่วมในสัปดาห์นี้",
)

_SLICES = {
    "gov_form": "gov_form",
    "bank_letter": "bank_phone",
    "education": "education",
    "card_receipt": "finance",
    "passport_form": "id_docs",
    "vehicle_form": "id_docs",
    "medical": "medical",
    "mixed_email": "mixed",
    "chat": "chat",
    "long_memo": "long_form",
    "adv_grouped_space": "adversarial",
    "adv_every_space": "adversarial",
    "adv_zwsp": "adversarial",
    "adv_thai_digits": "adversarial",
    "adv_arabic_digits": "adversarial",
    "adv_ocr": "adversarial",
    "section26": "section26",
    "negative": "negative",
}


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    entity_type: str


@dataclass(frozen=True)
class Question:
    question_id: str
    question: str
    answer: str
    needs_pii: bool


@dataclass(frozen=True)
class Document:
    doc_id: str
    slice: str
    style: str
    text: str
    spans: tuple[Span, ...]
    section26: tuple[str, ...]
    questions: tuple[Question, ...]


@dataclass(frozen=True)
class Corpus:
    version: str
    seed: int
    documents: tuple[Document, ...]


@dataclass(frozen=True)
class _Person:
    given: str
    surname: str
    en_given: str
    en_sur: str

    @property
    def thai(self) -> str:
        return f"{self.given} {self.surname}"

    @property
    def english(self) -> str:
        return f"{self.en_given.title()} {self.en_sur.title()}"


class _Draft:
    def __init__(self) -> None:
        self._parts: list[str] = []
        self.spans: list[Span] = []

    def add(self, text: str) -> None:
        self._parts.append(text)

    def entity(self, text: str, entity_type: str) -> None:
        if not text:
            raise RuntimeError("empty-entity")
        if entity_type not in REDACTION_TYPES:
            raise RuntimeError("unknown-entity-type")
        start = sum(len(part) for part in self._parts)
        self._parts.append(text)
        self.spans.append(Span(start, start + len(text), entity_type))

    def text(self) -> str:
        return "".join(self._parts)


class _Ctx:
    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.seen: set[tuple[str, str]] = set()
        self.n = 0
        self.email_n = 0

    def person(self) -> _Person:
        return _Person(*self.rng.choice(_PEOPLE))

    def take(self, kind: str, factory) -> str:
        for _ in range(60):
            value = factory()
            key = (kind, value)
            if key not in self.seen:
                self.seen.add(key)
                return value
        raise RuntimeError(f"exhausted-{kind}")

    def doc_id(self) -> str:
        doc_id = f"b2r-{self.n:04d}"
        self.n += 1
        return doc_id


def _digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def _thai_id(rng: random.Random) -> str:
    body = [str(rng.randint(1, 5))]
    body.extend(str(rng.randint(0, 9)) for _ in range(11))
    digits = "".join(body)
    total = sum(int(digits[i]) * (13 - i) for i in range(12))
    check = (11 - (total % 11)) % 10
    return digits + str(check)


def luhn_complete(body: str) -> str:
    """Return ``body`` plus a Luhn check digit. ``body`` is every digit but the last."""
    total = 0
    for index, char in enumerate(reversed(body + "0")):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    check = (10 - (total % 10)) % 10
    return body + str(check)


def iban_from_bban(country: str, bban: str) -> str:
    rearranged = bban + country + "00"
    numeric = "".join(str(ord(char) - 55) if char.isalpha() else char for char in rearranged)
    check = 98 - (int(numeric) % 97)
    return f"{country}{check:02d}{bban}"


def _card(rng: random.Random) -> str:
    body = "4" + "".join(str(rng.randint(0, 9)) for _ in range(14))
    digits = luhn_complete(body)
    return f"{digits[0:4]}-{digits[4:8]}-{digits[8:12]}-{digits[12:16]}"


def _iban(rng: random.Random) -> str:
    bank = f"{rng.randint(10000000, 99999999)}"
    account = f"{rng.randint(0, 9_999_999_999):010d}"
    return iban_from_bban("DE", bank + account)


def _mobile(rng: random.Random) -> str:
    digits = (
        f"0{rng.choice('689')}{rng.randint(0, 9)}"
        f"{rng.randint(0, 999):03d}{rng.randint(0, 9999):04d}"
    )
    return f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"


def _landline(rng: random.Random) -> str:
    digits = f"02{rng.randint(0, 999):03d}{rng.randint(0, 9999):04d}"
    return f"{digits[0:2]}-{digits[2:5]}-{digits[5:9]}"


def _intl_mobile(rng: random.Random) -> str:
    rest = (
        f"{rng.choice('689')}{rng.randint(0, 9)}{rng.randint(0, 999):03d}{rng.randint(0, 9999):04d}"
    )
    return f"+66 {rest[0:2]} {rest[2:5]} {rest[5:9]}"


def _bank(rng: random.Random) -> str:
    digits = "".join(str(rng.randint(0, 9)) for _ in range(10))
    if digits[0] == "0":
        digits = "7" + digits[1:]
    return f"{digits[0:3]}-{digits[3]}-{digits[4:9]}-{digits[9]}"


def _passport(rng: random.Random) -> str:
    letters = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(2))
    return letters + f"{rng.randint(0, 9_999_999):07d}"


def _plate(rng: random.Random, *, leading_digit: bool) -> str:
    letters = "".join(rng.choice("กขคงชธนบปพมยรลวสหอ") for _ in range(2))
    number = rng.randint(1, 9999)
    if leading_digit:
        return f"{rng.randint(1, 9)}{letters} {number}"
    return f"{letters} {number}"


def _student(rng: random.Random) -> str:
    return f"{rng.randint(60, 68)}{rng.randint(0, 999_999_999):09d}"


def _student_dashed(rng: random.Random) -> str:
    return f"{rng.randint(60, 68):02d}-{rng.randint(1, 12):02d}-{rng.randint(0, 9999):04d}"


def _email(ctx: _Ctx, person: _Person) -> str:
    ctx.email_n += 1
    return f"{person.en_given}.{person.en_sur}.{ctx.email_n}@example.com"


def _address(rng: random.Random) -> str:
    house = rng.randint(1, 189)
    extra = rng.randint(1, 30)
    soi = rng.randint(1, 71)
    if rng.random() < 0.5:
        khwaeng, khet, postal, road = rng.choice(_BKK)
        return f"{house}/{extra} ซอย{road} {soi} แขวง{khwaeng} เขต{khet} กรุงเทพมหานคร {postal}"
    tambon, amphoe, province, postal, road = rng.choice(_PROVINCES)
    return f"{house} หมู่ {extra} ถนน{road} ตำบล{tambon} อำเภอ{amphoe} จังหวัด{province} {postal}"


def _dob_numeric(rng: random.Random) -> str:
    return f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.randint(2508, 2548)}"


def _dob_thai(rng: random.Random) -> str:
    return f"{rng.randint(1, 28)} {rng.choice(_MONTHS)} {rng.randint(2508, 2548)}"


def _to_thai_digits(text: str) -> str:
    return text.translate({ord("0") + offset: ord("๐") + offset for offset in range(10)})


def _to_arabic_digits(text: str) -> str:
    return text.translate({ord("0") + offset: 0x0660 + offset for offset in range(10)})


def _grouped_id(digits: str) -> str:
    return f"{digits[0]} {digits[1:5]} {digits[5:10]} {digits[10:12]} {digits[12]}"


def _each_char(text: str) -> str:
    return " ".join(text)


def _zwsp(text: str, marks: str) -> str:
    pieces: list[str] = []
    for index, char in enumerate(text):
        if index:
            pieces.append(marks[(index - 1) % len(marks)])
        pieces.append(char)
    return "".join(pieces)


def _alternate_scripts(text: str) -> str:
    chars: list[str] = []
    thai_turn = True
    for char in text:
        if char.isdigit():
            chars.append(_to_thai_digits(char) if thai_turn else char)
            thai_turn = not thai_turn
        else:
            chars.append(char)
    return "".join(chars)


def _corrupt_ocr(digits: str) -> str:
    index = digits.find("0")
    if index < 0:
        index = 4
    return digits[:index] + "O" + digits[index + 1 :]


def _claim_surface(ctx: _Ctx, kind: str, raw: str, surface: str) -> str:
    identity = _digits(raw) or raw
    if (kind, identity) in ctx.seen or ("surface", surface) in ctx.seen:
        raise RuntimeError("duplicate-surface")
    ctx.seen.add((kind, identity))
    ctx.seen.add(("surface", surface))
    return surface


def _phone(ctx: _Ctx, factory, transform=None) -> str:
    for _ in range(40):
        raw = factory()
        surface = transform(raw) if transform else raw
        identity = _digits(raw)
        if ("phone", identity) in ctx.seen or ("surface", surface) in ctx.seen:
            continue
        ctx.seen.add(("phone", identity))
        ctx.seen.add(("surface", surface))
        return surface
    raise RuntimeError("exhausted-phone")


def _id_surface(ctx: _Ctx, transform) -> str:
    for _ in range(40):
        raw = _thai_id(ctx.rng)
        surface = transform(raw)
        try:
            return _claim_surface(ctx, "thai_id", raw, surface)
        except RuntimeError:
            continue
    raise RuntimeError("exhausted-thai-id")


def _questions(doc_id: str, rows: list[tuple[str, str, bool]]) -> tuple[Question, ...]:
    return tuple(
        Question(f"{doc_id}-q{index}", question, answer, needs_pii)
        for index, (question, answer, needs_pii) in enumerate(rows, start=1)
    )


def _emit(
    ctx: _Ctx,
    style: str,
    draft: _Draft,
    questions: list[tuple[str, str, bool]] | None = None,
    section26: tuple[str, ...] = (),
) -> Document:
    doc_id = ctx.doc_id()
    return Document(
        doc_id=doc_id,
        slice=_SLICES[style],
        style=style,
        text=draft.text(),
        spans=tuple(draft.spans),
        section26=section26,
        questions=_questions(doc_id, questions or []),
    )


def _gov_form(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    thai_id = _id_surface(ctx, lambda raw: raw)
    phone = _phone(ctx, lambda: _mobile(ctx.rng))
    dob = ctx.take("dob", lambda: _dob_thai(ctx.rng) if n == 1 else _dob_numeric(ctx.rng))
    address = ctx.take("address", lambda: _address(ctx.rng))
    draft = _Draft()
    draft.add("คำร้องขอคัดสำเนาทะเบียนบ้าน\nผู้ยื่นคำร้อง ")
    draft.entity(person.thai, "NAME")
    draft.add("\nเลขประจำตัวประชาชน ")
    draft.entity(thai_id, "THAI_ID")
    draft.add("\nเกิดวันที่ ")
    draft.entity(dob, "DATE_OF_BIRTH")
    draft.add("\nที่อยู่ ")
    draft.entity(address, "ADDRESS")
    draft.add("\nเบอร์โทร ")
    draft.entity(phone, "PHONE")
    draft.add("\nขอนัดรับเอกสารที่สำนักงานเขตในวันทำการ\n")
    questions = None
    if n == 0:
        questions = [
            ("เอกสารนี้ขอทำเรื่องอะไร", "คัดสำเนาทะเบียนบ้าน", False),
            ("ผู้ยื่นคำร้องชื่ออะไร", person.thai, True),
            ("เบอร์โทรที่กรอกไว้คือเบอร์ใด", phone, True),
        ]
    return _emit(ctx, "gov_form", draft, questions)


def _bank_letter(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    account = ctx.take("bank", lambda: _bank(ctx.rng))
    phone = _phone(ctx, lambda: _landline(ctx.rng) if n == 0 else _mobile(ctx.rng))
    email = ctx.take("email", lambda: _email(ctx, person))
    draft = _Draft()
    draft.add("เรื่อง แจ้งเปลี่ยนแปลงบัญชีรับเงิน\nเรียน เจ้าหน้าที่การเงิน\n")
    draft.add("ข้าพเจ้า ")
    draft.entity(person.thai, "NAME")
    draft.add(" ขอให้โอนเข้าเลขที่บัญชี ")
    draft.entity(account, "BANK_ACCOUNT")
    draft.add("\nโทร ")
    draft.entity(phone, "PHONE")
    draft.add("\nอีเมล ")
    draft.entity(email, "EMAIL")
    draft.add("\nจึงเรียนมาเพื่อดำเนินการ\n")
    questions = None
    if n == 0:
        questions = [
            ("จดหมายนี้ขอให้ทำอะไร", "เปลี่ยนแปลงบัญชีรับเงิน", False),
            ("เลขที่บัญชีที่แจ้งคืออะไร", account, True),
        ]
    return _emit(ctx, "bank_letter", draft, questions)


def _education(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    student = ctx.take(
        "student",
        lambda: _student_dashed(ctx.rng) if n % 2 else _student(ctx.rng),
    )
    email = ctx.take("email", lambda: _email(ctx, person))
    dob = ctx.take("dob", lambda: _dob_numeric(ctx.rng))
    thai_id = _id_surface(ctx, lambda raw: raw)
    draft = _Draft()
    draft.add("ใบลงทะเบียนเรียนภาคต้น\nชื่อ-นามสกุล ")
    draft.entity(person.thai, "NAME")
    draft.add("\nรหัสนักศึกษา ")
    draft.entity(student, "STUDENT_ID")
    draft.add("\nอีเมล ")
    draft.entity(email, "EMAIL")
    draft.add("\nเกิดวันที่ ")
    draft.entity(dob, "DATE_OF_BIRTH")
    draft.add("\nเลขประจำตัวประชาชน ")
    draft.entity(thai_id, "THAI_ID")
    draft.add("\nสาขาวิชาทั่วไป ห้องเรียนรวม\n")
    questions = None
    if n == 0:
        questions = [
            ("เอกสารนี้ใช้ทำอะไร", "ลงทะเบียนเรียน", False),
            ("รหัสนักศึกษาคืออะไร", student, True),
        ]
    return _emit(ctx, "education", draft, questions)


def _card_receipt(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    card = ctx.take("card", lambda: _card(ctx.rng))
    iban = ctx.take("iban", lambda: _iban(ctx.rng))
    draft = _Draft()
    draft.add("ใบรับเงินค่าสมัครสอบ\nชื่อผู้ชำระ ")
    draft.entity(person.thai, "NAME")
    draft.add("\nหมายเลขบัตร ")
    draft.entity(card, "CREDIT_CARD")
    draft.add("\nIBAN สำหรับโอนต่างประเทศ ")
    draft.entity(iban, "IBAN")
    draft.add("\nรายการนี้เป็นการชำระค่าสมัคร ไม่ใช่ใบกำกับภาษี\n")
    questions = None
    if n == 0:
        questions = [
            ("ใบนี้รับเงินค่าอะไร", "ค่าสมัครสอบ", False),
            ("หมายเลขบัตรบนใบรับเงินคืออะไร", card, True),
        ]
    return _emit(ctx, "card_receipt", draft, questions)


def _passport_form(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    passport = ctx.take("passport", lambda: _passport(ctx.rng))
    phone = _phone(ctx, lambda: _mobile(ctx.rng))
    email = ctx.take("email", lambda: _email(ctx, person))
    dob = ctx.take("dob", lambda: _dob_thai(ctx.rng) if n == 0 else _dob_numeric(ctx.rng))
    thai_id = _id_surface(ctx, lambda raw: raw)
    draft = _Draft()
    draft.add("แบบคำขอต่ออายุหนังสือเดินทาง\nชื่อ ")
    draft.entity(person.thai, "NAME")
    draft.add("\nหนังสือเดินทางเลขที่ ")
    draft.entity(passport, "PASSPORT")
    draft.add("\nเกิดวันที่ ")
    draft.entity(dob, "DATE_OF_BIRTH")
    draft.add("\nเลขประจำตัวประชาชน ")
    draft.entity(thai_id, "THAI_ID")
    draft.add("\nโทร ")
    draft.entity(phone, "PHONE")
    draft.add("\nอีเมล ")
    draft.entity(email, "EMAIL")
    draft.add("\nนัดรับเล่มที่เคาน์เตอร์ในวันทำการ\n")
    return _emit(ctx, "passport_form", draft)


def _vehicle_form(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    plate = ctx.take("plate", lambda: _plate(ctx.rng, leading_digit=n % 2 == 1))
    thai_id = _id_surface(ctx, lambda raw: raw)
    address = ctx.take("address", lambda: _address(ctx.rng))
    draft = _Draft()
    draft.add("คำขอแจ้งเปลี่ยนที่อยู่ผู้ครอบครองรถ\nชื่อ ")
    draft.entity(person.thai, "NAME")
    draft.add("\nทะเบียนรถ ")
    draft.entity(plate, "VEHICLE_PLATE")
    draft.add("\nเลขประจำตัวประชาชน ")
    draft.entity(thai_id, "THAI_ID")
    draft.add("\nที่อยู่ใหม่ ")
    draft.entity(address, "ADDRESS")
    draft.add("\nใช้ประกอบการย้ายทะเบียนเท่านั้น\n")
    return _emit(ctx, "vehicle_form", draft)


def _medical(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    dob = ctx.take("dob", lambda: _dob_numeric(ctx.rng))
    address = ctx.take("address", lambda: _address(ctx.rng))
    phone = _phone(ctx, lambda: _mobile(ctx.rng))
    draft = _Draft()
    draft.add("ใบบันทึกนัดตรวจ\nชื่อ ")
    draft.entity(person.thai, "NAME")
    draft.add("\nเกิดวันที่ ")
    draft.entity(dob, "DATE_OF_BIRTH")
    draft.add("\nที่อยู่ ")
    draft.entity(address, "ADDRESS")
    draft.add("\nโทร ")
    draft.entity(phone, "PHONE")
    draft.add(f"\n{_S26['HEALTH']} นัดติดตามในเดือนถัดไป\n")
    questions = None
    if n == 0:
        questions = [
            ("ใบบันทึกนี้เป็นใบอะไร", "นัดตรวจ", False),
            ("ชื่อบนใบบันทึกคืออะไร", person.thai, True),
        ]
    return _emit(ctx, "medical", draft, questions, ("HEALTH",))


def _mixed_email(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    passport = ctx.take("passport", lambda: _passport(ctx.rng))
    phone = _phone(ctx, lambda: _intl_mobile(ctx.rng) if n == 0 else _mobile(ctx.rng))
    email = ctx.take("email", lambda: _email(ctx, person))
    draft = _Draft()
    draft.add("Subject: Update contact record\n\n")
    draft.add("Please update the student exchange file for ")
    draft.entity(person.english, "NAME")
    draft.add(".\nโทร ")
    draft.entity(phone, "PHONE")
    draft.add("\nPassport ")
    draft.entity(passport, "PASSPORT")
    draft.add("\nEmail ")
    draft.entity(email, "EMAIL")
    draft.add("\nขอบคุณครับ\n")
    questions = None
    if n == 0:
        questions = [
            ("อีเมลขอให้อัปเดตเรื่องอะไร", "Update contact record", False),
            ("ชื่อภาษาอังกฤษในอีเมลคืออะไร", person.english, True),
        ]
    return _emit(ctx, "mixed_email", draft, questions)


def _chat(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    phone = _phone(ctx, lambda: _mobile(ctx.rng))
    draft = _Draft()
    draft.add("พรุ่งนี้ช่วยโทรหา ")
    draft.entity(person.thai, "NAME")
    draft.add(" ที่เบอร์ ")
    draft.entity(phone, "PHONE")
    draft.add(" เรื่องนัดซ้อมฟุตบอลได้ไหม\n")
    questions = None
    if n == 0:
        questions = [
            ("ให้โทรไปเรื่องอะไร", "นัดซ้อมฟุตบอล", False),
            ("ให้โทรหาใคร", person.thai, True),
        ]
    return _emit(ctx, "chat", draft, questions)


def _long_memo(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    phone = _phone(ctx, lambda: _mobile(ctx.rng))
    address = ctx.take("address", lambda: _address(ctx.rng))
    dob = ctx.take("dob", lambda: _dob_numeric(ctx.rng))
    email = ctx.take("email", lambda: _email(ctx, person))
    draft = _Draft()
    draft.add("บันทึกข้อความ\nเรื่อง ขอความร่วมมือตรวจร่างประกาศภายใน\n")
    draft.add("ผู้ร่าง ")
    draft.entity(person.thai, "NAME")
    draft.add("\n")
    draft.add(_FILLER_A)
    draft.add("หากติดต่อกลับได้ที่ ")
    draft.entity(phone, "PHONE")
    draft.add(" หรือ ")
    draft.entity(email, "EMAIL")
    draft.add("\n")
    draft.add(_FILLER_B)
    draft.add("ประชุมวันที่ 4 มีนาคม 2569 ที่ห้องประชุมรวม\n")
    draft.add(_FILLER_C)
    draft.add("ที่อยู่สำหรับส่งเอกสาร ")
    draft.entity(address, "ADDRESS")
    draft.add("\nเกิดวันที่ ")
    draft.entity(dob, "DATE_OF_BIRTH")
    draft.add("\n")
    questions = None
    if n == 0:
        questions = [
            ("ประชุมวันที่เท่าไร", "4 มีนาคม 2569", False),
            ("ผู้ร่างบันทึกชื่ออะไร", person.thai, True),
        ]
    return _emit(ctx, "long_memo", draft, questions)


def _adv_grouped(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    thai_id = _id_surface(ctx, _grouped_id)
    phone = _phone(ctx, lambda: _mobile(ctx.rng))
    draft = _Draft()
    draft.add("แบบฟอร์มที่ตัวเลขถูกเว้นวรรค\nชื่อ ")
    draft.entity(person.thai, "NAME")
    draft.add("\nเลขประจำตัวประชาชน ")
    draft.entity(thai_id, "THAI_ID")
    draft.add("\nโทร ")
    draft.entity(phone, "PHONE")
    draft.add("\n")
    return _emit(ctx, "adv_grouped_space", draft)


def _adv_every_space(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    thai_id = _id_surface(ctx, _each_char)
    phone = _phone(ctx, lambda: _mobile(ctx.rng), transform=_each_char)
    draft = _Draft()
    draft.add("สำเนาที่มีช่องไฟระหว่างทุกตัวอักษร\nชื่อ ")
    draft.entity(_each_char(person.thai), "NAME")
    draft.add("\nเลขประจำตัวประชาชน ")
    draft.entity(thai_id, "THAI_ID")
    draft.add("\nโทร ")
    draft.entity(phone, "PHONE")
    draft.add("\n")
    return _emit(ctx, "adv_every_space", draft)


def _adv_zwsp(ctx: _Ctx, n: int) -> Document:
    marks = "\u200b" if n == 0 else "\u200b\u200c\ufeff"
    person = ctx.person()
    thai_id = _id_surface(ctx, lambda raw: _zwsp(raw, marks))
    draft = _Draft()
    draft.add("ข้อความที่แทรกอักขระความกว้างศูนย์\nชื่อ ")
    draft.entity(_zwsp(person.thai, marks), "NAME")
    draft.add("\nเลขประจำตัวประชาชน ")
    draft.entity(thai_id, "THAI_ID")
    draft.add("\n")
    return _emit(ctx, "adv_zwsp", draft)


def _adv_thai_digits(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    transform = _to_thai_digits if n == 0 else _alternate_scripts
    thai_id = _id_surface(ctx, transform)
    phone = _phone(ctx, lambda: _mobile(ctx.rng), transform=transform)
    draft = _Draft()
    draft.add("แบบที่ใช้เลขไทยหรือเลขปนไทย\nชื่อ ")
    draft.entity(person.thai, "NAME")
    draft.add("\nเลขประจำตัวประชาชน ")
    draft.entity(thai_id, "THAI_ID")
    draft.add("\nโทร ")
    draft.entity(phone, "PHONE")
    draft.add("\n")
    return _emit(ctx, "adv_thai_digits", draft)


def _adv_arabic_digits(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    thai_id = _id_surface(ctx, _to_arabic_digits)
    phone = _phone(ctx, lambda: _mobile(ctx.rng), transform=_to_arabic_digits)
    email = ctx.take("email", lambda: _email(ctx, person))
    draft = _Draft()
    draft.add("แบบที่ใช้เลขอารบิก-อินดิก\nชื่อ ")
    draft.entity(person.thai, "NAME")
    draft.add("\nเลขประจำตัวประชาชน ")
    draft.entity(thai_id, "THAI_ID")
    draft.add("\nโทร ")
    draft.entity(phone, "PHONE")
    draft.add("\nอีเมล ")
    draft.entity(email, "EMAIL")
    draft.add("\n")
    return _emit(ctx, "adv_arabic_digits", draft)


def _adv_ocr(ctx: _Ctx, n: int) -> Document:
    person = ctx.person()
    thai_id = _id_surface(ctx, _corrupt_ocr)
    plate = ctx.take("plate", lambda: _plate(ctx.rng, leading_digit=False))
    glued = person.given + person.surname
    draft = _Draft()
    draft.add("ภาพสแกนที่ตัวอักษรเพี้ยน\nชื่อ ")
    draft.entity(glued, "NAME")
    draft.add("\nเลขประจำตัวประชาชน ")
    draft.entity(thai_id, "THAI_ID")
    draft.add("\nทะเบียน ")
    draft.entity(plate.replace(" ", ""), "VEHICLE_PLATE")
    draft.add("\n")
    return _emit(ctx, "adv_ocr", draft)


def _section26(ctx: _Ctx, n: int) -> Document:
    category = SECTION26_TYPES[n]
    person = ctx.person()
    phone = _phone(ctx, lambda: _mobile(ctx.rng))
    draft = _Draft()
    draft.add("แบบฟอร์มข้อมูลเพิ่มเติม\nชื่อ ")
    draft.entity(person.thai, "NAME")
    draft.add("\nโทร ")
    draft.entity(phone, "PHONE")
    draft.add(f"\n{_S26[category]}\n")
    return _emit(ctx, "section26", draft, section26=(category,))


def _negative(ctx: _Ctx, n: int) -> Document:
    draft = _Draft()
    draft.add(_NEGATIVES[n])
    draft.add("\n")
    questions = None
    if n == 0:
        questions = [("ข้อความนี้พูดถึงฝนแบบใด", "ฝนกระจาย", False)]
    return _emit(ctx, "negative", draft, questions)


_BUILDERS = {
    "gov_form": _gov_form,
    "bank_letter": _bank_letter,
    "education": _education,
    "card_receipt": _card_receipt,
    "passport_form": _passport_form,
    "vehicle_form": _vehicle_form,
    "medical": _medical,
    "mixed_email": _mixed_email,
    "chat": _chat,
    "long_memo": _long_memo,
    "adv_grouped_space": _adv_grouped,
    "adv_every_space": _adv_every_space,
    "adv_zwsp": _adv_zwsp,
    "adv_thai_digits": _adv_thai_digits,
    "adv_arabic_digits": _adv_arabic_digits,
    "adv_ocr": _adv_ocr,
    "section26": _section26,
    "negative": _negative,
}

_PLAN = (
    ("gov_form", 4),
    ("bank_letter", 8),
    ("education", 8),
    ("card_receipt", 8),
    ("passport_form", 5),
    ("vehicle_form", 6),
    ("medical", 3),
    ("mixed_email", 3),
    ("chat", 3),
    ("long_memo", 2),
    ("adv_grouped_space", 2),
    ("adv_every_space", 2),
    ("adv_zwsp", 2),
    ("adv_thai_digits", 2),
    ("adv_arabic_digits", 2),
    ("adv_ocr", 2),
    ("section26", len(SECTION26_TYPES)),
    ("negative", len(_NEGATIVES)),
)


def generate_corpus(seed: int = GENERATION_SEED) -> Corpus:
    """Return the frozen corpus for ``seed``. Only the documented seed is locked."""
    ctx = _Ctx(seed)
    documents = []
    for style, count in _PLAN:
        builder = _BUILDERS[style]
        for index in range(count):
            documents.append(builder(ctx, index))
    return Corpus(version=VERSION, seed=seed, documents=tuple(documents))


def canonical_bytes(corpus: Corpus) -> bytes:
    payload = {
        "documents": [
            {
                "doc_id": doc.doc_id,
                "questions": [
                    {
                        "answer": question.answer,
                        "needs_pii": question.needs_pii,
                        "question": question.question,
                        "question_id": question.question_id,
                    }
                    for question in doc.questions
                ],
                "section26": list(doc.section26),
                "slice": doc.slice,
                "spans": [
                    {"end": span.end, "entity_type": span.entity_type, "start": span.start}
                    for span in doc.spans
                ],
                "style": doc.style,
                "text": doc.text,
            }
            for doc in corpus.documents
        ],
        "seed": corpus.seed,
        "version": corpus.version,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def corpus_sha256(corpus: Corpus) -> str:
    return hashlib.sha256(canonical_bytes(corpus)).hexdigest()


def public_lock(corpus: Corpus) -> dict:
    """Hash and counts only. Never include document text or entity surfaces."""
    type_counts: Counter[str] = Counter()
    slice_counts: Counter[str] = Counter()
    style_counts: Counter[str] = Counter()
    section_counts: Counter[str] = Counter()
    for doc in corpus.documents:
        slice_counts[doc.slice] += 1
        style_counts[doc.style] += 1
        for span in doc.spans:
            type_counts[span.entity_type] += 1
        for category in doc.section26:
            section_counts[category] += 1
    return {
        "documents": len(corpus.documents),
        "generator": "benchmark/blind_v2/corpus.py",
        "labels_committed": False,
        "plaintext_sha256": corpus_sha256(corpus),
        "questions": sum(len(doc.questions) for doc in corpus.documents),
        "redaction_types": list(REDACTION_TYPES),
        "sealed_corpus_untouched": "benchmark/data/blind-v2.enc",
        "section26_counts": dict(sorted(section_counts.items())),
        "section26_types": list(SECTION26_TYPES),
        "seed": corpus.seed,
        "slice_counts": dict(sorted(slice_counts.items())),
        "style_counts": dict(sorted(style_counts.items())),
        "type_counts": dict(sorted(type_counts.items())),
        "version": corpus.version,
    }


def load_lock(path: Path | None = None) -> dict:
    return json.loads((path or LOCK_PATH).read_text(encoding="utf-8"))


def validate_corpus(corpus: Corpus) -> list[str]:
    """Return error kinds. Messages stay free of document text and values."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_surfaces: set[str] = set()
    if corpus.version != VERSION or corpus.seed != GENERATION_SEED:
        errors.append("unexpected-freeze-identity")
    for doc in corpus.documents:
        if doc.doc_id in seen_ids:
            errors.append("duplicate-doc-id")
        seen_ids.add(doc.doc_id)
        if doc.slice != _SLICES.get(doc.style):
            errors.append("slice-mismatch")
        if doc.slice == "negative" and (doc.spans or doc.section26):
            errors.append("negative-has-labels")
        if doc.slice != "negative" and not doc.spans:
            errors.append("positive-without-entities")
        cursor = 0
        for span in doc.spans:
            if not (0 <= span.start < span.end <= len(doc.text)):
                errors.append("span-out-of-range")
                continue
            if span.start < cursor:
                errors.append("span-overlap")
            cursor = span.end
            if span.entity_type not in REDACTION_TYPES:
                errors.append("unknown-entity-type")
            surface = doc.text[span.start : span.end]
            if not surface.strip():
                errors.append("blank-entity")
            if surface in seen_surfaces and span.entity_type != "NAME":
                errors.append("reused-surface")
            seen_surfaces.add(surface)
        for category in doc.section26:
            if category not in SECTION26_TYPES:
                errors.append("unknown-section26")
            if _S26[category] not in doc.text:
                errors.append("section26-phrase-missing")
        for question in doc.questions:
            if question.answer not in doc.text:
                errors.append("answer-not-in-text")
            if question.answer in question.question:
                errors.append("answer-in-question")
            in_span = any(question.answer == doc.text[span.start : span.end] for span in doc.spans)
            if question.needs_pii != in_span:
                errors.append("needs-pii-flag")
        if doc.style == "long_memo" and len(doc.text) <= 500:
            errors.append("long-form-too-short")
        if doc.style == "negative":
            if "@" in doc.text or any(ch.isdigit() for ch in doc.text):
                errors.append("negative-has-digit-or-email")
    expected_styles = {style for style, _count in _PLAN}
    found_styles = {doc.style for doc in corpus.documents}
    if found_styles != expected_styles:
        errors.append("missing-style")
    return errors
