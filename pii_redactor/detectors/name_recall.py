"""Extra NAME recall for names the Thai CRF does not tag.

The thainer CRF is silent on two kinds of names: names in Latin script, and
Thai names with no title in front. Two passes cover the common cases.

1. Latin-script names after a cue that says "a person follows": a name
   label (Name, Guest name, ชื่อ...), a person-role label (Guest:,
   ผู้โดยสาร 1:), a courtesy title (Khun, คุณ, Dr.), or a table row whose
   next cell is an email. There is no cue-free scan: in Thai text a
   capitalised Latin pair is far more often a brand or a product.
2. Thai names found by word list: a given name from the PyThaiNLP name
   lists, one space, a family name from the same lists. Thai prose puts no
   space between words, so this shape is rare outside names.

Every span here scores below the CRF and the older cue passes, so it only
adds coverage and never replaces a span they produced.
"""

from __future__ import annotations

import re
from functools import lru_cache
from importlib.resources import files

from pythainlp.corpus import thai_family_names, thai_female_names, thai_male_names, thai_words

from pii_redactor.detectors.name_context import (
    _LATIN_ORG_STOP,
    _TITLES,
    _is_name_token,
    _make_name,
    is_non_person_segment,
)
from pii_redactor.models import Entity

_SCORE = 0.84

# --- Latin-script names ------------------------------------------------------

# "Somchai Jaidee", "Somchai K. Jaidee", or all capitals as printed on a
# passport. Mixed case inside one name is not accepted.
_CAP = r"[A-Z][a-z]{1,20}(?:-[A-Z][a-z]{1,20})?"
_UP = r"[A-Z]{2,20}"
_LATIN_NAME = (
    rf"(?P<name>{_CAP}(?:[ \t]+(?:[A-Z]\.|{_CAP})){{1,3}}|{_UP}(?:[ \t]+{_UP}){{1,3}})(?![A-Za-z])"
)
_PAREN = r"(?:[ \t]*\([^()\n]{1,24}\))?"
_SEP = r"(?:[ \t]*[:：=][ \t]*|[ \t]+)"
_COLON = r"[ \t]*[:：][ \t]*"
_NUMBER = r"(?:[ \t]*(?:[Nn]o\.?[ \t]*)?[0-9๐-๙]{1,2})?"
_LINE_START = r"(?m:^)[ \t]*(?:[-*•>][ \t]*)?"

# English words for the person a form is about.
_EN_ROLES = (
    r"guest|applicant|co-applicant|insured|passenger|traveller|traveler"
    r"|card[ \t]?holder|policy[ \t]?holder|account[ \t]+holder|customer|client|patient"
    r"|employee|landlord|borrower|lender|guarantor"
    r"|beneficiary|payer|attendee|participant|visitor"
    r"|signatory|dear"
    r"|(?:prepared|approved|signed|requested|reported|booked)[ \t]+by"
)

# The word before "name" when the label names a thing, not a person.
_NON_PERSON_NAME_QUALIFIERS = frozenset(
    "company hotel bank product file project brand domain business school shop store branch "
    "team device host server user login item event course plan package model organization "
    "organisation agency department building street village place trade group file folder "
    "merchant vendor supplier program programme app system network wifi campaign font".split()
)

# Thai words after ชื่อ that make the label name a thing, not a person.
# ชื่อเสียง and ชื่อดัง are "fame" and "famous".
_TH_NON_PERSON_NAME_RE = re.compile(
    r"บริษัท|ร้าน|สินค้า|โครงการ|ไฟล์|ผู้ใช้|เรื่อง|ทีม|แบรนด์|ธนาคาร|สาขา|โรงแรม|รุ่น|วิชา"
    r"|หลักสูตร|เสียง|ดัง|กลุ่ม|ระบบ|เว็บ|โดเมน|หน่วยงาน|องค์กร|โรงเรียน|มหาวิทยาลัย|สถานที่"
    r"|อาคาร|หมู่บ้าน|ถนน|ซอย|แอป|โปรแกรม|อุปกรณ์|กิจการ|ห้าง|นิติบุคคล|ยี่ห้อ"
    r"|ผลิตภัณฑ์|เข้าใช้|ตำแหน่ง|แผนก|ฝ่าย|ห้อง|เมือง|จังหวัด|ประเทศ|เพลง|หนังสือ(?!เดินทาง)"
)
# "ชื่อภาษาอังกฤษ" alone after ชื่อ is a bare field label, not a person cue.
_TH_NON_PERSON_GAP_START_RE = re.compile(r"[ \t]*ภาษาอังกฤษ[ \t]*")
# ผู้-roles that are usually a company.
_TH_ORG_ROLES = r"ผลิต|ให้บริการ|จัดจำหน่าย|นำเข้า|ส่งออก|พัฒนา|สนับสนุน|ใช้|จัดงาน|รับเหมา"

_SHARED_MAILBOX = (
    r"info|sales|support|contact|admin|hello|help|service|services|hr|billing|office"
    r"|enquiry|inquiry|booking|reservation|noreply|no-reply|marketing|careers|jobs"
)
_EMAIL_AHEAD = r"(?=[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"

_LATIN_CUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Name: / Guest name: / Name (EN): / Name – Surname / Surname/Given name /
    # "my name is". The word before it is checked in `_latin_label_names`.
    re.compile(
        r"(?<![A-Za-z])(?:(?P<qualifier>[A-Za-z]+)[ \t]+)?(?i:names?|surname)"
        r"(?:[ \t]*[/–—-][ \t]*(?i:surname|(?:given[ \t]+|last[ \t]+|family[ \t]+)?names?))?"
        rf"{_PAREN}(?:[ \t]+is[ \t]+|{_SEP}){_LATIN_NAME}"
    ),
    # A role label with a colon, anywhere on a line: "Applicant: ...".
    re.compile(
        rf"(?<![A-Za-z])(?i:{_EN_ROLES})(?i:[ \t]+person)?{_NUMBER}{_PAREN}{_COLON}{_LATIN_NAME}"
    ),
    # With no colon the label must open the line and be explicit: a
    # salutation, or a role followed by "person" ("Insured person ...").
    re.compile(rf"{_LINE_START}(?i:dear|(?:{_EN_ROLES})[ \t]+person)[ \t]+{_LATIN_NAME}"),
    # A Thai role label with a colon: "ผู้โดยสาร ๑: ...". ผู้ makes a person
    # noun from a verb, so the label is a person unless it is a company role.
    re.compile(
        rf"ผู้(?!{_TH_ORG_ROLES})[ก-๛]{{2,14}}(?:[ \t]*(?:คนที่|ที่)?[ \t]*[0-9๐-๙]{{1,2}})?"
        rf"{_PAREN}{_COLON}{_LATIN_NAME}"
    ),
    # Courtesy titles the older pass does not know.
    re.compile(rf"(?:(?<![A-Za-z])(?:Khun|Miss|Dr\.?)[ \t]+|(?<![ก-๛])คุณ[ \t]*){_LATIN_NAME}"),
    # A table row: the name opens the line and the next cell is a personal
    # email. A shared mailbox (info@, sales@) belongs to an organisation.
    re.compile(
        rf"{_LINE_START}(?:\d{{1,3}}[.)][ \t]*)?{_LATIN_NAME}[ \t]*[—–\-|,;:/<(][ \t]*"
        rf"(?!(?i:{_SHARED_MAILBOX})@){_EMAIL_AHEAD}"
    ),
)

# ชื่อ ("name") earlier on the same line, with only Thai words between it and
# the Latin name: "ชื่อผู้ถือบัตร (ตามหน้าบัตร): ...", "สะกดชื่อเป็นอังกฤษว่า ...".
_TH_NAME_LABEL_RE = re.compile(
    rf"(?P<lead>[ก-๛]{{0,4}})ชื่อ(?P<gap>[ก-๛ \t()/–-]{{0,40}}?){_SEP}{_LATIN_NAME}"
)
_TH_NAME_LABEL_LEAD_STOP = ("ราย", "ตั้ง")

# Capitalised English words that follow a label but are not a person.
_LATIN_WORD_STOP = _LATIN_ORG_STOP | frozenset(
    "the and for with from this that please thank thanks you your our dear sir madam "
    "team staff support sales marketing admin manager director officer engineer executive "
    "assistant center centre care relations services number no code id type status date "
    "address email phone mobile tel fax signature form report summary total amount payment "
    "invoice receipt order booking reservation confirmation reference policy account card "
    "licence license passport visa mastercard credit debit room floor class flight gate seat "
    "terminal standard premium gold silver platinum plus pro cloud pay app web online system "
    "project international thailand thai bangkok house trading corp inc solutions tech "
    "information details list notes meeting charge us today name names surname given "
    "first last full middle family english express resources payable desk retail mall air "
    "automobile boots shoes sandals sneakers loafers".split()
)
# A product noun right after the pair ("Dr. Martens Jadon boots") means the
# pair is a brand or model, not a person.
_PRODUCT_NOUN_AFTER_RE = re.compile(
    r"[ \t]+(?i:boots?|shoes?|sandals?|sneakers?|loafers?|jackets?|bags?|watch(?:es)?)(?![A-Za-z])"
)


def _latin_name_ok(value: str) -> bool:
    parts = [part.rstrip(".").lower() for part in re.split(r"[ \t]+", value)]
    return not any(part in _LATIN_WORD_STOP for part in parts)


def _latin_label_names(text: str) -> list[Entity]:
    spans: set[tuple[int, int]] = set()
    for pattern in _LATIN_CUE_PATTERNS:
        for match in pattern.finditer(text):
            qualifier = match.groupdict().get("qualifier")
            if qualifier and qualifier.lower() in _NON_PERSON_NAME_QUALIFIERS:
                continue
            if _PRODUCT_NOUN_AFTER_RE.match(text, match.end("name")):
                continue
            if _latin_name_ok(match.group("name")):
                spans.add(match.span("name"))
    for match in _TH_NAME_LABEL_RE.finditer(text):
        if match.group("lead").endswith(_TH_NAME_LABEL_LEAD_STOP):
            continue
        gap = match.group("gap")
        if _TH_NON_PERSON_NAME_RE.search(gap) or _TH_NON_PERSON_GAP_START_RE.fullmatch(gap):
            continue
        if _latin_name_ok(match.group("name")):
            spans.add(match.span("name"))
    return [_make_name(text, start, end, _SCORE) for start, end in sorted(spans)]


# --- Thai names by word list ---------------------------------------------------

_THAI_RUN_RE = re.compile(r"[ก-๎]+")
_MAX_FAMILY_CHARS = 20
# Count in the Thai National Corpus list from which a word is everyday Thai.
_EVERYDAY_MIN_COUNT = 1000


@lru_cache(maxsize=1)
def _everyday_words() -> frozenset[str]:
    """Words that are frequent in the Thai National Corpus list.

    The file is read line by line. ``tnc.word_freqs()`` gives the same data
    but keeps about 10 MB of it alive for one small set.
    """
    words = set()
    source = files("pythainlp.corpus").joinpath("tnc_freq.txt")
    with source.open(encoding="utf-8-sig") as lines:
        for line in lines:
            word, _tab, count = line.rstrip("\n").partition("\t")
            if count.isdigit() and int(count) >= _EVERYDAY_MIN_COUNT:
                words.add(word)
    return frozenset(words)


def _thai_lexicon_names(text: str) -> list[Entity]:
    """A listed given name, one space, then a family name.

    The name lists also hold everyday words (ผล, ประเภท, สุทธิ, ภาษี), so a
    pair of two frequent words is left alone: "กำไร สุทธิ" is a table
    header. A family name that is not listed is accepted only when the given
    name is not a frequent word and the word ชื่อ ("name") sits right
    before the pair.
    """
    runs = [match.span() for match in _THAI_RUN_RE.finditer(text)]
    if len(runs) < 2:
        return []
    # PyThaiNLP keeps these sets itself, so nothing is copied here.
    female, male, family = thai_female_names(), thai_male_names(), thai_family_names()
    given = female | male
    found: list[Entity] = []
    for (start, mid), (mid2, end) in zip(runs, runs[1:], strict=False):
        if text[mid:mid2] not in (" ", "\t"):
            continue
        first, last = text[start:mid], text[mid2:end]
        if first not in given or len(last) > _MAX_FAMILY_CHARS:
            continue
        if first in _TITLES or not (_is_name_token(first) and _is_name_token(last)):
            continue
        everyday = _everyday_words()
        if last in family:
            if first in everyday and last in everyday:
                continue
            if not _has_name_evidence(text, start, end) and _looks_like_plain_words(
                first, last, everyday, given
            ):
                continue
        elif first in everyday or not _after_name_word(text, start):
            continue
        if is_non_person_segment(text[start:end]):
            continue
        found.append(_make_name(text, start, end, _SCORE))
    return found


# Words just before a pair that say a person follows: a title, ชื่อ, or a
# person-role noun. Without one, an everyday pair is far more likely prose.
_NAME_EVIDENCE_BEFORE_RE = re.compile(
    r"(?:นาย|นาง|นางสาว|น\.ส\.|ด\.ช\.|ด\.ญ\.|เด็กชาย|เด็กหญิง|คุณ|ชื่อ|นามสกุล|ผู้[ก-๛]{2,10}"
    r"|ลูกค้า|พยาน|เจ้าของ|พนักงาน|นักเรียน|นักศึกษา|อาจารย์|ครู|หมอ|นพ\.|พญ\.|ดร\.|จำเลย|โจทก์"
    r"|สมาชิก|ผู้ป่วย|เจ้าหน้าที่)[ \t:：]*$"
)
_NAME_EVIDENCE_WINDOW = 40
# A national ID or an email on the same line makes it a person record.
_RECORD_CONTEXT_RE = re.compile(
    r"[0-9]{1}-?[0-9]{4}-?[0-9]{5}-?[0-9]{2}-?[0-9]|[\w.+-]+@[\w-]+\.\w+"
)


def _has_name_evidence(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - _NAME_EVIDENCE_WINDOW) : start]
    before = before.rsplit("\n", 1)[-1]
    if _NAME_EVIDENCE_BEFORE_RE.search(before):
        return True
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    line = text[line_start : len(text) if line_end < 0 else line_end]
    return bool(_RECORD_CONTEXT_RE.search(line))


def _looks_like_plain_words(
    first: str, last: str, everyday: frozenset[str], given: set[str]
) -> bool:
    """An untitled pair that reads as two ordinary words, not a name."""
    if first in everyday:
        return True
    plain = thai_words()
    # Two dictionary words where the second is also everyday or a given name
    # ("อุทัย ธานี", "สมหวัง สมใจ") is a place or a wish, not a surname.
    return first in plain and last in plain and (last in everyday or last in given)


def _after_name_word(text: str, start: int) -> bool:
    return text[max(0, start - 6) : start].rstrip(" \t:：").endswith("ชื่อ")


def detect_name_recall(text: str) -> list[Entity]:
    """Names the CRF and the older cue passes leave out."""
    return _latin_label_names(text) + _thai_lexicon_names(text)
