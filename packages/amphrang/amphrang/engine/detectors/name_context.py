"""Context-based Thai name detection (recall booster for the CRF NER).

Thai names are introduced by high-precision cues (titles, name labels, role words). This pass
works on word TOKENS so it does not fire on substrings like "นายก", and emits TB/NAME entities
scored slightly above the CRF so a complete name wins de-duplication. Recall > precision.
"""

from __future__ import annotations

import re
import uuid
from difflib import SequenceMatcher

from pythainlp.tokenize import word_tokenize

# Imported, not copied, so this rule and `_name_hygiene` cannot drift apart. No cycle:
# tb_detector imports name_context only inside function bodies.
from amphrang.engine.detectors.tb_detector import _NAME_DOC_COMPOUND_RE
from amphrang.engine.models import Entity

# Titles that, as standalone tokens, almost always precede a person name.
_TITLES = {
    "นาย",
    "นาง",
    "นางสาว",
    "น.ส.",
    "ด.ช.",
    "ด.ญ.",
    "เด็กชาย",
    "เด็กหญิง",
}
# "ชื่อ" is only a name cue right after a first-person pronoun.
_PRONOUNS = {"ผม", "ดิฉัน", "ฉัน", "หนู", "กระผม", "ข้าพเจ้า"}
# Cues that introduce a name with no "ชื่อ" in between ("ข้าพเจ้า <name>").
# ONLY tokens newmm keeps whole belong here: the loop compares whole tokens, so a cue newmm
# splits (ผู้ร้อง -> ผู้|ร้อง) is dead code. Check with word_tokenize before adding one.
_DIRECT_NAME_CUES = {"ข้าพเจ้า", "ผู้เสียหาย"}
# Compound self-introductions newmm may keep as one token.
_INTRO_COMPOUND = {"ผมชื่อ", "ดิฉันชื่อ", "ฉันชื่อ", "หนูชื่อ", "ลงชื่อ"}

# {1,} not {2,}: newmm splits some real first names into single-char tokens
# (สราวุธ -> ส|รา|วุธ), and the per-entity >=2-char chokepoint still applies.
_THAI_WORD = re.compile(r"^[ก-๛]+$")
_NEVER_NAME_CHARS = {"ๆ", "ฯ"}
# Thai-script tokens that are not names even right after a cue.
_NOT_NAME = {
    "ชื่อ",
    "นามสกุล",
    "คือ",
    "ครับ",
    "ค่ะ",
    "คะ",
    "นะ",
    "และ",
    "ที่",
    "ของ",
    "จาก",
    "อยู่",
    "เป็น",
    "อายุ",
    "มา",
    "ไป",
    "ได้",
    "เบอร์",
    "อีเมล",
    "โทร",
    # document-label nouns, otherwise the group collector swallows the label after the name as
    # a fake surname. Both compound tokens and their newmm splits.
    "เลข",
    "หมายเลข",
    "บัตร",
    "บัตรประชาชน",
    "เลขบัตรประชาชน",
    "ประชาชน",
    "รหัส",
    "รหัสพนักงาน",
    "พนักงาน",
    "บัญชี",
    "เลขบัญชี",
    "เลขที่บัญชี",
    "ธนาคาร",
    "โทรศัพท์",
    "มือถือ",
    "ที่อยู่",
    "ทะเบียน",
    "เอกสาร",
}


_NOT_NAME |= {"เลขที่", "หนังสือเดินทาง", "ลายมือชื่อ", "รายการ", "เงื่อนไข"}

# Form-label nouns and the standard letter closing that leaked through `_name_hygiene`'s
# tail-segment gate. Leading newmm tokens / whole tokens only, never prefixes.
_NOT_NAME |= {"เลขประจำตัว", "ตำแหน่ง", "อาชีพ", "ขอแสดงความนับถือ"}

# Formal-letter salutation verb ("เรียน ผู้ปกครอง"), never a given name; blocking the token
# fixes every collector at once.
_NOT_NAME |= {"เรียน"}

# Trailing field labels the CRF glues onto NAME spans; วันเกิด/ความสัมพันธ์ are kept whole by
# newmm so the วัน/ความ entries never see them, ประจำตัว is the split-off half of รหัสประจำตัว.
_NOT_NAME |= {"วันเกิด", "ความสัมพันธ์", "ประจำตัว"}

# Verbs/functional tokens that begin prose, never a Thai given name. Exact whole-token matches
# only: a prefix rule would kill real names (การุณ).
_LEAD_STOP = {
    "ต้อง",
    "ควร",
    "จะ",
    "ให้",
    "โปรด",
    "กรุณา",
    "สามารถ",
    "ขอ",
    "กรอก",
    "แนบ",
    "แสดง",
    "ชำระ",
    "ดำเนิน",
    "ดำเนินการ",
    "ยอมรับ",
    "ได้",
    "ได้รับ",
    "รับ",
    "อยู่",
    "เป็น",
    "คือ",
    "ประสงค์",
    "ทุก",
    "ราย",
    # second-person honorific opening a sentence ("ท่านมียอดค้างชำระ"), never a given name
    "ท่าน",
}
_ACCOUNT_TYPES = {"ออมทรัพย์", "กระแสรายวัน", "ฝากประจำ"}

# Role cues matched at CHARACTER level: newmm splits ผู้-compounds (ผู้ป่วย -> ผู้|ป่วย), so
# token-level matching never fires. Each cue carries the prose continuations that veto it when
# GLUED to the cue ("ผู้ป่วยใน ห้องพิเศษ" is a ward, not a person). Longest cue first so
# ผู้ยื่นอุทธรณ์ is not consumed as ผู้ยื่น + อุทธรณ์-as-name.
_ROLE_CUES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ผู้ค้ำประกันเงินกู้", ("ต้อง", "ควร", "มี", "ร่วม")),
    ("ผู้รับมอบอำนาจ", ("ต้อง", "ควร", "ช่วง")),
    ("ผู้รับการตรวจ", ("ต้อง", "ควร")),
    ("ผู้ยื่นอุทธรณ์", ("ต้อง", "ควร")),
    ("ผู้ยื่นคำร้อง", ("ต้อง", "ควร")),
    ("ผู้ค้ำประกัน", ("ต้อง", "ควร", "มี", "ร่วม")),
    ("ผู้เอาประกันภัย", ("ต้อง", "ควร")),
    ("ผู้เสียหาย", ("ต้อง", "ควร", "ได้", "แจ้ง", "ถูก", "มี", "ให้", "ไม่", "จะ", "ทั้ง")),
    ("ผู้ปกครอง", ("ต้อง", "ควร", "ของ", "นักเรียน", "และ")),
    ("ผู้สั่งซื้อ", ("สินค้า", "ต้อง", "ควร")),
    ("ผู้ถือบัตร", ("ต้อง", "ควร", "สามารถ", "ทุก")),
    ("ผู้เดินทาง", ("ต้อง", "ควร", "ทุก", "ที่")),
    ("ผู้ขับขี่", ("ต้อง", "ควร", "ที่", "ทุก")),
    # Tried before the bare ผู้ติดต่อ: its กรณี veto would otherwise silence the emergency-contact
    # row, where the CRF carries no PERSON span.
    ("ผู้ติดต่อกรณีฉุกเฉิน", ("ต้อง", "ควร", "ติดต่อ", "โทร", "ได้", "แจ้ง")),
    # กรณี veto: otherwise "กรณีฉุกเฉิน กาญจนา" becomes the two name groups and evicts the real
    # name in dedupe.
    ("ผู้ติดต่อ", ("หลัก", "สำรอง", "สอบถาม", "กลับ", "ได้", "ประสาน", "กรณี")),
    ("ผู้สมัคร", ("งาน", "สอบ", "ทุก", "ที่", "สามารถ", "รหัส")),
    ("ผู้แจ้ง", ("ความ", "เบาะแส", "เตือน")),
    ("ผู้ยื่น", ("ภาษี", "แบบ")),
    # หญิง/ชาย are NOT vetoes but skipped qualifiers (_ROLE_QUALIFIERS); vetoing them shipped
    # "ผู้ป่วยชาย ธงชัย รักถิ่น" in the clear where the CRF had no PERSON span.
    ("ผู้ป่วย", ("ใน", "นอก", "ราย", "ทุก", "ต้อง", "ควร", "ที่", "จะ", "ได้", "เรื้อรัง")),
    ("ผู้กู้", ("ร่วม", "ยืม", "ต้อง", "ควร")),
    ("มอบอำนาจให้", ("__require_space__",)),
    # Same shape, corporate-letter register; recovers gold bz01
    # ("บริษัท... มอบหมายให้ ปกรณ์ ตั้งสิริกุล เดินทางไป...").
    ("มอบหมายให้", ("__require_space__",)),
    # Card/receipt issuance rows; __require_space__ makes glued forms (ออกให้แก่, ออกให้ทะเบียน)
    # no-ops, a stated recall cost on the แก่ form.
    ("ออกให้", ("__require_space__",)),
    ("ชื่อบัญชี", ("ผู้ใช้",)),
)
# Tokens that may sit between a role cue and the name ("ผู้ป่วยชื่อวิภาวดี",
# "ผู้ค้ำประกันเงินกู้คือ สราวุธ").
_ROLE_LINKERS = {"คือ", "ชื่อ", "ได้แก่"}
# Gender qualifiers glued onto the role word ("ผู้ป่วยหญิง รัตนา แสงวิเชียร"); the collector steps
# OVER them like _ROLE_LINKERS. Because a skipped qualifier stays unmasked, `_role_cue_names`
# then demands two REAL groups ("ผู้ป่วยหญิง อายุ 52 ปี" must not mint อายุ).
_ROLE_QUALIFIERS = {"หญิง", "ชาย"}

# Bare "ชื่อ" as a field label: line start + mandatory delimiter, so ชื่อบัญชี/ชื่อบริษัท and
# mid-sentence prose cannot fire. The delimiter admits a LINE BREAK because OCR of a government
# form puts the label on its own line and the value on the next.
_LINE_NAME_LABEL_RE = re.compile(r"(?m)^[ \t]*ชื่อ(?:-นามสกุล)?(?:[ \t:：]+|[ \t:：]*\r?\n)")
# OCR joins nearby form fields on one line, so the label may sit mid-line here, but the
# lookbehind keeps it the WORD ชื่อ ("ดูรายชื่อ สาขา" must not tag the next two words).
_INLINE_NAME_LABEL_RE = re.compile(
    r"(?m)(?:สัญชาติ|คำนำหน้า|เพศ)[^\r\n]{0,30}?(?<![ก-๛])ชื่อ(?:-นามสกุล)?[ \t:：]+"
)
_NON_PERSON_LEADS = {
    "บริษัท",
    "ห้าง",
    "ธนาคาร",
    "โรงพยาบาล",
    "มหาวิทยาลัย",
    "โรงเรียน",
    "สำนักงาน",
    "โรงงาน",
    "มูลนิธิ",
    "โครงการ",
    "สมาคม",
    "สหกรณ์",
    "หน่วยงาน",
}
# First-collected-token check for the role and roster passes: a cue must not vouch for a
# juristic person. หจก/บจก are the abbreviations leading vendor rows in procurement rosters.
_ORG_LEAD_TOKENS = _NON_PERSON_LEADS | {"หจก", "บจก"}

# "<kinship>ชื่อ <first> <last>"; the kinship word is what makes bare ชื่อ a person label
# (กรอกชื่อ/ระบุชื่อ never fire).
_KINSHIP_NAME_LABEL_RE = re.compile(
    r"(?:คุณแม่|คุณพ่อ|แม่|พ่อ|พี่สาว|พี่ชาย|พี่|น้องสาว|น้องชาย|น้อง|ลูกสาว|ลูกชาย|ลูก"
    r"|ภรรยา|สามี|ป้า|ลุง|ย่า|ยาย|ปู่|ตา|หลาน|เพื่อน|แฟน)ชื่อ[ \t:：]*"
)

# Numbered rosters need header evidence: numbered lists are also agendas and invoices
# ("1. การชำระ เงินล่วงหน้า" is name-shaped). ผลการคัดเลือก/ผู้มาประชุม are only safe alongside
# the _ORG_LEAD_TOKENS check in `_roster_names`, since a selection result can list companies.
_ROSTER_HEADER_RE = re.compile(
    r"รายชื่อ|ผู้เข้าสอบ|ผู้เข้าพัก|ผู้มีสิทธิ์|ผู้ผ่านการ|ทะเบียนผู้"
    r"|ผลการคัดเลือก|ผู้มาประชุม|ผู้เข้าร่วมประชุม"
)
_ROSTER_CUE_RE = re.compile(r"(?m)(?:^|(?<=\s))(?:ลำดับที่[ \t]*\d+[ \t.]*|\d{1,3}\.[ \t]+)")
_ROSTER_HEADER_WINDOW = 300

# Two-group Thai name followed by an id-document label or value: passport (hotel/visa rosters)
# and driver licence. The licence arm recovers gold-v5 bz06/bz09/bz17 (Thai label) and bz13
# (the latin label), transport rows where the CRF tags no PERSON at all.
_NAME_BEFORE_PASSPORT_RE = re.compile(
    r"([ก-๛]{2,25})[ \t]([ก-๛]{2,25})[ \t]+"
    r"(?=passport|[A-Z]{2}\d{7}|ใบขับขี่|ใบอนุญาตขับ|[Dd]river'?s?[ \t]*[Ll]icen[cs]e)"
)

# Latin-script names: the Thai CRF never tags them. Cue-driven only (a global capitalized-bigram
# scan makes "Name Bangkok Bank" a person), with an org/place stoplist.
_LATIN_CUE_RE = re.compile(
    r"(?:(?:Name|ชื่อ)[ \t]*[:：=][ \t]*|(?:Name|ชื่อ)[ \t]+|contact person[ \t:：]*"
    r"|Mr\.?[ \t]+|Ms\.?[ \t]+|Mrs\.?[ \t]+|ผู้ยื่น[ \t]+|ผู้แจ้ง[ \t]+"
    r"|ที่นั่งสอบ[ \t]*[A-Za-z]?\d+[ \t]+)"
)
_LATIN_NAME_RE = re.compile(r"[A-Z][a-z]{1,20}(?:[ \t](?:[A-Z]\.|[A-Z][a-z]{1,20})){1,3}")
_LATIN_TRAILING_PASSPORT_RE = re.compile(
    r"([A-Z][a-z]{1,20}(?:[ \t](?:[A-Z]\.|[A-Z][a-z]{1,20})){1,2})[ \t]+(?=passport|[A-Z]{2}\d{7})"
)
_LATIN_ORG_STOP = {
    "bank",
    "company",
    "limited",
    "public",
    "hospital",
    "university",
    "hotel",
    "road",
    "river",
    "province",
    "district",
    "tower",
    "office",
    "department",
    "faculty",
    "school",
    "service",
    "customer",
    "group",
    "branch",
    "building",
    "resort",
    "airport",
    "station",
    "palace",
    "temple",
    "market",
    "mall",
    "co",
    "ltd",
    "plc",
}


def _is_name_token(tok: str) -> bool:
    return (
        bool(_THAI_WORD.match(tok))
        and tok not in _NOT_NAME
        and tok not in _TITLES
        and tok not in _NEVER_NAME_CHARS
    )


# --- glued (space-deleted) Thai name runs -----------------------------------
# OCR deletes the space inside a Thai name ("สมชายใจดี"). The discriminator is the TOKENIZER:
# names are not dictionary words, so newmm splits a real glued name into 2+ pieces, while the
# prose/form nouns in these positions are single tokens ("ขอแสดงความนับถือ", หมายเหตุ). The stop
# set below covers the multi-token form compounds the token count alone lets through.
_GLUED_NAME_MIN_CHARS = 4
_GLUED_NAME_MAX_CHARS = 25
_GLUED_NAME_MAX_TOKENS = 4
_GLUED_RUN_RE = re.compile(r"[ก-ฮเ-ไ][ก-ฮะ-์]*")
_NON_PERSON_LEAD_PREFIXES = tuple(sorted(_NON_PERSON_LEADS))
# Form/document nouns and particles never part of a person name. Checked per TOKEN, not as a
# prefix. Only measured leaks belong here: `ใบ`/`แบบ` would reject the real given names
# ใบเฟิร์น / แบบบุญมี (recall > precision).
_GLUED_RUN_STOP = {
    "การ",
    "ความ",
    "ผู้",
    "ร้องขอ",
    "วัน",
    "เดือน",
    "ปี",
    "ปีเกิด",
    "ที่อยู่",
    "ข้อมูล",
    "รายละเอียด",
    "ส่วนบุคคล",
    "บุคคล",
    "เงินได้",
    "ภาษี",
    "ภาษีเงินได้",
    "จดทะเบียน",
    "ทะเบียน",
    "สาขา",
    "ฝ่าย",
    "แผนก",
    "หนังสือ",
    "คำร้อง",
    "สำเนา",
    "ยินยอม",
    "ยอมให้",
    "รับรอง",
    "เพิ่มเติม",
    "ชำระเงิน",
    "ค่าธรรมเนียม",
    "หมายเหตุ",
}


def is_glued_name_run(run: str) -> bool:
    """True when a spaceless Thai run may be a name whose space OCR deleted."""
    if not (_GLUED_NAME_MIN_CHARS <= len(run) <= _GLUED_NAME_MAX_CHARS):
        return False
    if _GLUED_RUN_RE.fullmatch(run) is None:
        return False
    if run in _NOT_NAME or run in _TITLES:
        return False
    if run.startswith(_NON_PERSON_LEAD_PREFIXES):
        return False
    if _NAME_DOC_COMPOUND_RE.match(run):
        return False
    tokens = [t for t in word_tokenize(run, keep_whitespace=False) if t.strip()]
    if not (2 <= len(tokens) <= _GLUED_NAME_MAX_TOKENS):
        return False
    return all(
        _is_name_token(t) and t not in _LEAD_STOP and t not in _GLUED_RUN_STOP for t in tokens
    )


def is_non_person_segment(seg: str) -> bool:
    """True when a space-separated Thai run is a form label or prose fragment.

    Shared with `tb_detector._name_hygiene`. Judges the LEADING newmm token only: checking every
    token would reject real surnames newmm splits onto a stop word ("ทองอยู่" -> ทอง|อยู่).
    """
    tokens = [t for t in word_tokenize(seg, keep_whitespace=False) if t.strip()]
    if not tokens:
        return True
    lead = tokens[0]
    return (
        lead in _NOT_NAME
        or lead in _LEAD_STOP
        or lead in _GLUED_RUN_STOP
        or lead in _NON_PERSON_LEADS
    )


# --- same-line role/label trimming for CRF NAME spans --------------------------
# The CRF glues a leading role word or trailing field label onto the name on form lines; gold
# (docs/annotation-guidelines.md) treats those as context, not value. Trimming UNMASKS text, so:
# - whole-token, closed-lexicon evidence only, never a prefix match; a trailing group is cut
#   only when EVERY token is a label, so ทองอยู่ -> ทอง|อยู่ survives;
# - no given name begins with the nominalizer ผู้, so a leading ผู้X token is a role compound;
#   when newmm splits it, bare ผู้ vouches for one role token only, never a glued first name;
# - >= 2 space-separated groups must remain after every step; when in doubt keep the span
#   (over-masking is the safe direction).
_TRIM_GROUP_RE = re.compile(r"[^ \t]+")
_ROLE_NOMINALIZER = "ผู้"


def _head_trim_lexicon() -> frozenset[str]:
    # Built per call: the sets receive |= additions across the module.
    # _LEAD_STOP is deliberately NOT here: it says a word never STARTS a name in prose, not that
    # it is not a name. ประสงค์ is a real given name and was unmasked out of a correct CRF span.
    return frozenset(_NOT_NAME | _GLUED_RUN_STOP | _NON_PERSON_LEADS)


def trim_same_line_name_edges(seg: str) -> tuple[int, int]:
    """Trim role-word heads and truncate at trailing field labels.

    Returns (start, end) offsets into ``seg``. Used by `tb_detector._name_hygiene` on same-line
    spans.
    """

    def groups(lo: int, hi: int) -> list[tuple[int, int]]:
        return [(lo + m.start(), lo + m.end()) for m in _TRIM_GROUP_RE.finditer(seg[lo:hi])]

    def group_tokens(lo: int, hi: int) -> list[str]:
        return [t for t in word_tokenize(seg[lo:hi], keep_whitespace=False) if t.strip()]

    start, end = 0, len(seg)
    # Tail first: a trailing label group must not count toward the head trim's two-group floor
    # ("ผู้ค้ำประกัน ดารณี อายุ" head-first would leave "ดารณี อายุ").
    gs = groups(start, end)
    for i in range(2, len(gs)):
        toks = group_tokens(*gs[i])
        if toks and all(t in _NOT_NAME for t in toks):
            end = gs[i - 1][1]
            break
    # Head: trim leading role/label groups while >= 2 groups remain.
    head_lex = _head_trim_lexicon()
    while True:
        gs = groups(start, end)
        if not gs:
            break
        g_lo, g_hi = gs[0]
        toks = group_tokens(g_lo, g_hi)
        if not toks:
            break
        lead = toks[0]
        if all(t in head_lex for t in toks):
            new_start = g_hi
        elif lead == _ROLE_NOMINALIZER:
            # newmm split the compound: advance past ผู้ + one role token only, or a glued row
            # (ผู้|ค้ำ|สม|ศรี) loses the given name with the role.
            new_start = min(g_lo + len(lead) + (len(toks[1]) if len(toks) > 1 else 0), g_hi)
        elif lead.startswith(_ROLE_NOMINALIZER):
            new_start = g_lo + len(lead)
        else:
            break
        if len(groups(new_start, end)) < 2:
            break
        start = new_start
    gs = groups(start, end)
    if gs:
        start, end = gs[0][0], gs[-1][1]
    return start, end


def _make_name(text: str, start: int, end: int, score: float) -> Entity:
    return Entity(
        entity_id=str(uuid.uuid4()),
        redact_type="TB",
        data_type="NAME",
        span=(start, end),
        score=score,
        original_text=text[start:end],
    )


def _token_spans(text: str) -> list[tuple[str, int, int]]:
    tokens = word_tokenize(text, keep_whitespace=True)
    spans: list[tuple[str, int, int]] = []
    pos = 0
    for t in tokens:
        i = text.find(t, pos)
        if i == -1:
            i = pos
        spans.append((t, i, i + len(t)))
        pos = i + len(t)
    return spans


def _collect_two_groups(
    spans: list[tuple[str, int, int]], start_idx: int
) -> tuple[int, int] | None:
    """Collect two horizontal-space-separated groups of name tokens (first + last name).

    A single Thai token after a role word is far more often prose than a mononym. A newline ends
    the attempt; a leading _LEAD_STOP token aborts it.
    """
    n = len(spans)
    collected: list[tuple[int, int]] = []
    groups = 0
    first_token_of_name = True
    j = start_idx
    while j < n:
        tok, ts, te = spans[j]
        if tok.strip() == "":
            if any(ch in tok for ch in "\n\r"):
                break
            if not collected:
                j += 1
                continue
            if groups == 1:
                break
            groups = 1
            first_token_of_name = True  # next token starts the second group
            j += 1
            continue
        if not _is_name_token(tok) or te - ts > 25:
            break
        if first_token_of_name and tok in _LEAD_STOP:
            # a verb opening EITHER group means this is prose, not a name
            return None
        if first_token_of_name and groups == 0 and tok in _ACCOUNT_TYPES:
            return None
        first_token_of_name = False
        collected.append((ts, te))
        j += 1
    if not collected or groups < 1:
        return None
    return collected[0][0], collected[-1][1]


def _index_after(spans: list[tuple[str, int, int]], char_pos: int) -> int | None:
    """First token index starting at or after char_pos; None if a token
    straddles the boundary (cannot align a glued cue to token space)."""
    for idx, (_t, s, e) in enumerate(spans):
        if s >= char_pos:
            return idx
        if s < char_pos < e:
            return None
    return None


def _role_cue_names(text: str, spans: list[tuple[str, int, int]]) -> list[Entity]:
    ents: list[Entity] = []
    claimed: list[tuple[int, int]] = []
    for cue, vetoes in _ROLE_CUES:
        # O(occurrences) scan; scanning from every char position was O(P^2) per cue.
        search_from = 0
        while True:
            pos = text.find(cue, search_from)
            if pos == -1:
                break
            search_from = pos + 1
            cue_end = pos + len(cue)
            if any(pos < c_end and c_start < cue_end for c_start, c_end in claimed):
                continue
            after = text[cue_end : cue_end + 12]
            if "__require_space__" in vetoes:
                if not after[:1].isspace():
                    continue
            elif any(after.startswith(v) for v in vetoes):
                continue
            # optional linker/qualifier token(s) between cue and name
            idx = _index_after(spans, cue_end)
            if idx is None:
                continue
            skipped_qualifier = False
            while idx < len(spans):
                tok = spans[idx][0]
                if tok in _ROLE_QUALIFIERS:
                    skipped_qualifier = True
                elif not (tok in _ROLE_LINKERS or (tok.strip() == "" and "\n" not in tok)):
                    break
                idx += 1
            if idx < len(spans) and spans[idx][0] in _ORG_LEAD_TOKENS:
                continue
            got = _collect_two_groups(spans, idx)
            if got and skipped_qualifier and " " not in text[got[0] : got[1]]:
                # A skipped qualifier stays unmasked, so it must buy a real two-group name
                # ("ผู้ป่วยหญิง อายุ 52 ปี" must not mint "อายุ").
                got = None
            if got:
                claimed.append((pos, got[1]))
                ents.append(_make_name(text, got[0], got[1], 0.88))
    return ents


def _line_label_names(text: str, spans: list[tuple[str, int, int]]) -> list[Entity]:
    ents = []
    for m in _LINE_NAME_LABEL_RE.finditer(text):
        idx = _index_after(spans, m.end())
        if idx is None:
            continue
        while idx < len(spans) and spans[idx][0].strip() == "":
            idx += 1
        if idx >= len(spans) or spans[idx][0] in _NON_PERSON_LEADS:
            continue
        got = _collect_two_groups(spans, idx)
        if got:
            ents.append(_make_name(text, got[0], got[1], 0.88))
    return ents


def _inline_label_names(text: str, spans: list[tuple[str, int, int]]) -> list[Entity]:
    ents = []
    for m in _INLINE_NAME_LABEL_RE.finditer(text):
        idx = _index_after(spans, m.end())
        if idx is None:
            continue
        while idx < len(spans) and spans[idx][0].strip() == "":
            idx += 1
        if idx >= len(spans) or spans[idx][0] in _NON_PERSON_LEADS:
            continue
        got = _collect_two_groups(spans, idx)
        if got:
            ents.append(_make_name(text, got[0], got[1], 0.87))
    return ents


def _kinship_label_names(text: str, spans: list[tuple[str, int, int]]) -> list[Entity]:
    ents = []
    for m in _KINSHIP_NAME_LABEL_RE.finditer(text):
        idx = _index_after(spans, m.end())
        if idx is None:
            continue
        got = _collect_two_groups(spans, idx)
        if got:
            ents.append(_make_name(text, got[0], got[1], 0.88))
    return ents


def _roster_names(text: str, spans: list[tuple[str, int, int]]) -> list[Entity]:
    ents = []
    for m in _ROSTER_CUE_RE.finditer(text):
        head_ctx = text[max(0, m.start() - _ROSTER_HEADER_WINDOW) : m.start()]
        if not _ROSTER_HEADER_RE.search(head_ctx):
            continue
        idx = _index_after(spans, m.end())
        if idx is None:
            continue
        while idx < len(spans) and spans[idx][0].strip() == "" and "\n" not in spans[idx][0]:
            idx += 1
        if idx >= len(spans) or spans[idx][0] in _ORG_LEAD_TOKENS:
            continue
        got = _collect_two_groups(spans, idx)
        if got:
            ents.append(_make_name(text, got[0], got[1], 0.87))
    return ents


# A Thai char right before a captured group means {2,25} clipped a run: the "name" starts mid-word.
_THAI_CHAR_RE = re.compile(r"[ก-๛]")


def _is_label_group(run: str) -> bool:
    """True when the run IS one form-label token, not merely led by one."""
    tokens = [t for t in word_tokenize(run, keep_whitespace=False) if t.strip()]
    return len(tokens) == 1 and is_non_person_segment(run)


def _passport_roster_names(text: str) -> list[Entity]:
    ents = []
    for m in _NAME_BEFORE_PASSPORT_RE.finditer(text):
        if not (_is_name_token(m.group(1)) and _is_name_token(m.group(2))):
            continue
        # `_is_name_token` is vacuous on arbitrary <=25-char runs, so two structural checks:
        # 1. the first group must start at a WORD boundary ({2,25} clips "บันทึกการตรวจ" to
        #    "นทึกการตรวจ", and a name never begins mid-word);
        # 2. a group is a label only when the label token IS the whole group; judging the lead
        #    token unmasked the real surname บัตรทอง -> บัตร|ทอง.
        if m.start(1) > 0 and _THAI_CHAR_RE.match(text[m.start(1) - 1]):
            continue
        if _is_label_group(m.group(1)) or _is_label_group(m.group(2)):
            continue
        ents.append(_make_name(text, m.start(1), m.end(2), 0.88))
    return ents


def _latin_names(text: str) -> list[Entity]:
    ents = []
    seen: set[tuple[int, int]] = set()

    def _accept(m_start: int, value: str):
        parts = re.split(r"[ \t]+", value)
        if any(p.rstrip(".").lower() in _LATIN_ORG_STOP for p in parts):
            return
        span = (m_start, m_start + len(value))
        if span not in seen:
            seen.add(span)
            ents.append(_make_name(text, span[0], span[1], 0.88))

    for cue in _LATIN_CUE_RE.finditer(text):
        m = _LATIN_NAME_RE.match(text, cue.end())
        if m:
            _accept(m.start(), m.group(0))
    for m in _LATIN_TRAILING_PASSPORT_RE.finditer(text):
        _accept(m.start(1), m.group(1))
    return ents


def detect_name_context_passes(text: str) -> list[tuple[str, Entity]]:
    """All cue passes, tagged by provenance.

    "strong" passes (title/intro tokens, line-start labels) are always trusted; "extended" passes
    cost precision on the blind set, so the fine-tuned engine keeps them only when the model
    agrees a person is there. The default CRF path keeps everything (recall-first).
    """
    if not text or not text.strip():
        return []

    spans = _token_spans(text)

    tagged: list[tuple[str, Entity]] = []
    tagged.extend(("extended", e) for e in _role_cue_names(text, spans))
    tagged.extend(("strong", e) for e in _line_label_names(text, spans))
    tagged.extend(("extended", e) for e in _inline_label_names(text, spans))
    tagged.extend(("extended", e) for e in _kinship_label_names(text, spans))
    tagged.extend(("extended", e) for e in _roster_names(text, spans))
    tagged.extend(("extended", e) for e in _passport_roster_names(text))
    tagged.extend(("extended", e) for e in _latin_names(text))
    tagged.extend(("strong", e) for e in _token_pass_names(text, spans))
    return tagged


def detect_name_context(text: str) -> list[Entity]:
    """Detect names introduced by a title, label, role word, or roster cue."""
    return [e for _pass, e in detect_name_context_passes(text)]


# A conjunction right after an accepted NAME introduces the NEXT person ("... และ ธงชัย รักถิ่น");
# the CRF stops at และ and no cue reaches a mid-sentence third name.
_CONJUNCTION_AFTER_NAME_RE = re.compile(r"[ \t]*(?:และ|กับ)[ \t]+")
# Wide enough for two 25-char groups plus separators, small enough to tokenize cheaply.
_CONJUNCTION_WINDOW = 160


def detect_conjunction_names(text: str, entities: list[Entity]) -> list[Entity]:
    """Names introduced by และ/กับ directly after an already-accepted NAME.

    Two REAL groups are required (a space inside the span): `_collect_two_groups` returns a
    single group when the second head token is rejected, and "และ มารดา ของเด็ก" is not a person.
    """
    seeds = [e for e in entities if e.data_type == "NAME"]
    if not seeds:
        return []
    ents: list[Entity] = []
    seen: set[tuple[int, int]] = set()
    for seed in seeds:
        m = _CONJUNCTION_AFTER_NAME_RE.match(text, seed.span[1])
        if m is None:
            continue
        # Tokenize only a bounded tail: re-tokenizing the whole document doubled the
        # _token_spans cost of every detect call.
        window = text[m.end() : m.end() + _CONJUNCTION_WINDOW]
        spans = [(t, s + m.end(), e + m.end()) for t, s, e in _token_spans(window)]
        got = _collect_two_groups(spans, 0)
        if got is None or got in seen:
            continue
        if " " not in text[got[0] : got[1]]:
            continue
        seen.add(got)
        ents.append(_make_name(text, got[0], got[1], 0.87))
    return ents


_PARALLEL_NAME_LINE_RE = re.compile(r"^[ \t]*([ก-๛]{2,25})[ \t]+([ก-๛]{2,25})[ \t]*$")
_PARALLEL_NAME_STOP = _NOT_NAME | _LEAD_STOP | _NON_PERSON_LEADS
# The optional second Thai group keeps the single-token shape matching while also admitting
# the common "given name, space, surname" co-applicant line.
_OCR_CO_APPLICANT_RE = re.compile(
    r"(?m)^[ \t]*(?:และ|แถะ)[^ก-๛\r\n]{2,}"
    r"(?P<name>[ก-๛]{4,25}(?:[ \t]+[ก-๛]{2,25})?)[ \t]*$"
)
_OCR_CO_APPLICANT_STOP = (
    "กรอก",
    "ขอ",
    "คำ",
    "บริษัท",
    "ผู้",
    "มูลนิธิ",
    "เอกสาร",
    "โรงงาน",
    "โครงการ",
)


def _repeated_ocr_co_applicant_names(text: str, entities: list[Entity]) -> list[Entity]:
    """Find a name after an OCR form mark, repeated or alone on a 2-id record."""
    if sum(entity.data_type == "THAI_ID" for entity in entities) < 2:
        return []
    if not any(entity.data_type == "NAME" for entity in entities):
        return []

    matches = list(_OCR_CO_APPLICANT_RE.finditer(text))
    # Two valid national ids mean two people, so a SINGLE co-applicant line is the second person
    # (the คร.1 shape); otherwise the name must be repeated.
    solitary = len(matches) == 1
    recovered = []
    for match in matches:
        value = match.group("name")
        if value.startswith(_OCR_CO_APPLICANT_STOP):
            continue
        repeated = any(
            other is not match and SequenceMatcher(None, value, other.group("name")).ratio() >= 0.8
            for other in matches
        )
        if repeated or solitary:
            recovered.append(_make_name(text, *match.span("name"), 0.87))
    return recovered


def detect_parallel_record_names(text: str, entities: list[Entity]) -> list[Entity]:
    """Recover a missed name in repeated NAME/THAI_ID rows."""
    recovered = _repeated_ocr_co_applicant_names(text, entities)
    rows: list[tuple[str, int, int]] = []
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        stripped = line.strip()
        if stripped:
            start = offset + line.index(stripped)
            rows.append((stripped, start, start + len(stripped)))
        offset += len(raw_line)

    def _covered(row: tuple[str, int, int], data_type: str) -> bool:
        return any(
            entity.data_type == data_type and entity.span[0] <= row[1] and entity.span[1] >= row[2]
            for entity in entities
        )

    pairs: list[tuple[tuple[str, int, int], re.Match[str]]] = []
    for index, row in enumerate(rows[:-1]):
        match = _PARALLEL_NAME_LINE_RE.fullmatch(row[0])
        if match and _covered(rows[index + 1], "THAI_ID"):
            pairs.append((row, match))

    if not any(_covered(row, "NAME") for row, _match in pairs):
        return recovered

    for row, match in pairs:
        if _covered(row, "NAME"):
            continue
        if match.group(1) in _PARALLEL_NAME_STOP or match.group(2) in _PARALLEL_NAME_STOP:
            continue
        recovered.append(_make_name(text, row[1], row[2], 0.87))
    return recovered


def _token_pass_names(text: str, spans: list[tuple[str, int, int]]) -> list[Entity]:
    """The original token-level pass: titles and self-introduction labels."""
    ents: list[Entity] = []
    n = len(spans)
    for idx, (tok, _s, _e) in enumerate(spans):
        is_title = tok in _TITLES
        is_direct = tok in _DIRECT_NAME_CUES
        if is_direct:
            # A direct cue introduces a NAME only when a space follows it
            # ("ข้าพเจ้าขอแสดงความนับถือ" is a glued letter closing, not a name), except when the
            # glued run passes `is_glued_name_run` (OCR: "ข้าพเจ้าสมชายใจดี").
            nxt = spans[idx + 1][0] if idx + 1 < n else ""
            if nxt.strip() != "":
                glued = _GLUED_RUN_RE.match(text, spans[idx][2])
                if glued is not None and is_glued_name_run(glued.group(0)):
                    ents.append(_make_name(text, glued.start(), glued.end(), 0.88))
                continue
        is_cue = is_title or tok in _INTRO_COMPOUND or is_direct
        if not is_cue and tok == "ชื่อ":
            # cue only if the previous non-space token is a first-person pronoun
            j = idx - 1
            while j >= 0 and spans[j][0].strip() == "":
                j -= 1
            is_cue = j >= 0 and spans[j][0] in _PRONOUNS
        if not is_cue:
            continue

        # Collect first name + optional surname as 2 space-separated groups; count groups, not
        # tokens, since Thai first names often tokenize into several tokens.
        collected: list[tuple[int, int]] = []
        j = idx + 1
        space_seen = False
        while j < n:
            ttok, ts, te = spans[j]
            if ttok.strip() == "":  # whitespace
                if any(ch in ttok for ch in "\n\r") and collected:
                    # A name never spans a line break, but only once something is collected:
                    # OCR puts the label on its own line ("ข้าพเจ้า\nวิชัย ประสงค์ดี").
                    break
                if not collected:  # leading space (or line break) before the name
                    j += 1
                    continue
                if space_seen:  # second gap -> first+surname already captured
                    break
                space_seen = True
                j += 1
                continue
            if _is_name_token(ttok):
                collected.append((ts, te))
                j += 1
            else:
                break

        if collected:
            # Include the title in the span so this fuller entity wins de-duplication against a
            # CRF hit that clipped the surname.
            start = spans[idx][1] if is_title else collected[0][0]
            end = collected[-1][1]
            # A collected document compound is a header the cue vouched for by accident; judged
            # sans title so a real "นาย <name>" span cannot self-reject.
            if _NAME_DOC_COMPOUND_RE.match(text[collected[0][0] : end]):
                continue
            if end - start >= 2:  # span chokepoint
                ents.append(
                    Entity(
                        entity_id=str(uuid.uuid4()),
                        redact_type="TB",
                        data_type="NAME",
                        span=(start, end),
                        score=0.9,
                        original_text=text[start:end],
                    )
                )
    return ents
