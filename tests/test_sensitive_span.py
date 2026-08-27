"""Person-linked ม.26 sensitive-span masking.

Pins the frozen design record `docs/decisions/2026-08-27-section26-span-masking.md`:
the two-tier anchor (§4.2), the segment scope (§4.1), the forward-only capped span
shape (§4.3), the merge coverage invariant (§4.4), the token labels (§5.2), masking
in both modes (§5.3), the outbound guard pass (§6.2) and the char-coverage rule in
`_layer1_pii_scan` (§6.3).
"""

from __future__ import annotations

import time
import uuid

import pytest

import amphrang
from amphrang.engine.anonymizer.token_generator import TOKEN_LABEL
from amphrang.engine.detectors.aggregate import detect_all
from amphrang.engine.detectors.sensitive_span import (
    MAX_SPAN_CHARS,
    SENSITIVE_DATA_TYPE_SET,
    SENSITIVE_DATA_TYPES,
    detect_sensitive_spans,
    merge_sensitive_spans,
)
from amphrang.engine.leak_guard import (
    SAFE_OUTBOUND_LEAK_TYPES,
    OutboundGuardContext,
    scan_outbound_leaks,
)
from amphrang.engine.models import Entity, EntityRegistry, ReverseResult, VaultRecord
from amphrang.engine.output_validator import PIILeakError, _layer1_pii_scan
from amphrang.engine.session_vault import SessionVault

SALT = "sensitive-span-test-salt"


def _spans(text: str, person_spans: list[tuple[int, int]] | None = None) -> list[Entity]:
    return detect_sensitive_spans(text, person_spans or [])


def _ent(
    data_type: str,
    span: tuple[int, int],
    text: str,
    *,
    redact_type: str = "TB",
) -> Entity:
    return Entity(
        entity_id=str(uuid.uuid4()),
        redact_type=redact_type,
        data_type=data_type,
        span=span,
        score=0.9,
        original_text=text[span[0] : span[1]],
    )


# ---------------------------------------------------------------------------
# §4.2 two-tier anchor — positives, all ten categories
# ---------------------------------------------------------------------------

# (case id, document, expected data_type, keyword the span must start with)
POSITIVES = [
    (
        "p_race_01",
        "นายสมชาย ใจดี ระบุเชื้อชาติกะเหรี่ยงในแบบฟอร์ม",
        "RACE_ETHNICITY",
        "เชื้อชาติ",
    ),
    ("p_race_02", "ผู้เสียหายรายนี้มีชาติพันธุ์ม้ง", "RACE_ETHNICITY", "ชาติพันธุ์"),
    (
        "p_pol_01",
        "ข้าพเจ้าขอแสดงความคิดเห็นทางการเมืองอย่างเปิดเผย",
        "POLITICAL_OPINION",
        "ความคิดเห็นทางการเมือง",
    ),
    (
        "p_pol_02",
        "นายอนันต์ พงษ์ไพบูลย์ สังกัดพรรคการเมืองฝ่ายค้าน",
        "POLITICAL_OPINION",
        "พรรคการเมือง",
    ),
    ("p_relig_01", "ดิฉันนับถือศาสนาอิสลามมาตั้งแต่เกิด", "RELIGION", "ศาสนา"),
    (
        "p_health_01",
        "ผู้ป่วยรายนี้มีประวัติการรักษามะเร็งเต้านม",
        "HEALTH",
        "ประวัติการรักษา",
    ),
    ("p_health_02", "ผู้ป่วยรายนี้เป็นโรคเบาหวาน", "HEALTH", "โรค"),
    ("p_sex_01", "ผมขอเปิดเผยรสนิยมทางเพศของตนเอง", "SEXUAL_BEHAVIOR", "รสนิยมทางเพศ"),
    (
        "p_crime_01",
        "นายอนันต์ พงษ์ไพบูลย์ เคยต้องโทษจำคุก",
        "CRIMINAL_RECORD",
        "ต้องโทษ",
    ),
    ("p_crime_02", "จำเลยรายนี้ถูกฟ้องคดีฉ้อโกง", "CRIMINAL_RECORD", "ถูกฟ้อง"),
    ("p_disab_01", "ลูกจ้างรายนี้มีความพิการทางการได้ยิน", "DISABILITY", "ความพิการ"),
    (
        "p_union_01",
        "นายสมชาย ใจดี เป็นสมาชิกสหภาพแรงงานรัฐวิสาหกิจ",
        "LABOR_UNION",
        "สหภาพแรงงาน",
    ),
    (
        "p_gene_01",
        "ผู้ต้องหารายนี้มีสารพันธุกรรมตรงกับวัตถุพยาน",
        "GENETIC",
        "พันธุกรรม",
    ),
    (
        "p_bio_01",
        "ดิฉันยินยอมให้จัดเก็บลายนิ้วมือไว้ในระบบ",
        "BIOMETRIC",
        "ลายนิ้วมือ",
    ),
]


@pytest.mark.parametrize(("case_id", "text", "data_type", "keyword"), POSITIVES)
def test_person_linked_span_is_detected(case_id, text, data_type, keyword):
    found = _spans(text)
    assert len(found) == 1, (case_id, [(e.data_type, e.original_text) for e in found])
    entity = found[0]
    assert entity.data_type == data_type, case_id
    assert entity.original_text.startswith(keyword), (case_id, entity.original_text)
    assert entity.redact_type == "TB"
    assert entity.score == 0.9
    assert text[entity.span[0] : entity.span[1]] == entity.original_text


def test_positives_cover_every_category():
    assert {row[2] for row in POSITIVES} == set(SENSITIVE_DATA_TYPES)


def test_bare_name_span_anchors_a_sensitive_span():
    text = "สมชาย ใจดี ป่วยเป็นโรคเบาหวาน"
    assert _spans(text) == []
    found = _spans(text, [(0, 10)])
    assert [e.data_type for e in found] == ["HEALTH"]


def test_name_span_swallowed_by_the_hit_is_not_its_own_anchor():
    # The only "person" span lies inside the sensitive hit, so it cannot anchor it.
    text = "สมาคมลูกจ้างในประเทศไทยจัดประชุมประจำปี"
    assert _spans(text, [(5, 12)]) == []
    # One character wider and it is no longer swallowed — but this fixture also carries the
    # register word ในประเทศไทย, and since Task 10b F4 that vetoes the NAME-span route too,
    # so the segment stays impersonal on two independent grounds.
    assert _spans(text, [(5, 13)]) == []
    # The swallow rule on its own, in a segment carrying no register vocabulary.
    plain = "สมาคมลูกจ้างจัดประชุมประจำปี"
    assert _spans(plain, [(5, 12)]) == []
    assert [e.data_type for e in _spans(plain, [(5, 13)])] == ["LABOR_UNION"]


# ---------------------------------------------------------------------------
# §4.2 the four near-miss classes
# ---------------------------------------------------------------------------

NEAR_MISSES = [
    # 1. the only person word lies inside the union's own name
    ("n_union_01", "สมาคมลูกจ้างในประเทศไทยจัดประชุมประจำปี"),
    # 2. the role word is part of an organization name (org-forming word before it)
    ("n_crime_01", "สมาคมพนักงานสอบสวนจัดอบรมเรื่องคดีอาญา"),
    # 3. impersonal institutional register vetoes a tier-2 anchor
    ("n_health_01", "ประกาศกรมควบคุมโรค เรื่อง แนวทางการรักษาผู้ป่วยไข้เลือดออก"),
    # 4. the bare title is not a person reference
    ("n_health_02", "นายจ้างต้องจัดทำประวัติการรักษาพยาบาลตามระเบียบ"),
    ("n_health_03", "นายทะเบียนบันทึกประวัติการรักษาไว้ในแฟ้มกลาง"),
    ("n_health_04", "นายอำเภอลงนามในหนังสือเรื่องโรคระบาดประจำถิ่น"),
]


@pytest.mark.parametrize(("case_id", "text"), NEAR_MISSES)
def test_impersonal_near_miss_emits_nothing(case_id, text):
    assert _spans(text) == [], (case_id, [(e.data_type, e.original_text) for e in _spans(text)])


def test_specificity_marker_promotes_a_vetoed_role_reference():
    # Same register word, but "รายนี้" makes it a specific individual.
    vetoed = "ตามระเบียบว่าด้วยการรักษาผู้ป่วยของโรงพยาบาล"
    assert _spans(vetoed) == []
    promoted = "ผู้ป่วยรายนี้เข้ารับการรักษาตามระเบียบของโรงพยาบาล"
    assert [e.data_type for e in _spans(promoted)] == ["HEALTH"]


def test_register_veto_does_not_apply_to_a_named_person():
    text = "ประกาศฉบับนี้ระบุว่า นายสมชาย ใจดี แจ้งเชื้อชาติกะเหรี่ยงในแบบฟอร์ม"
    assert [e.data_type for e in _spans(text)] == ["RACE_ETHNICITY"]


def test_the_specificity_window_is_clamped_at_the_segment_end():
    # Task 10b F1, the design record's §8 limit 9 with gold evidence (`sn28`): ดังกล่าว
    # sits one character past the newline and promoted the tier-2 ผู้ป่วย across it, so a
    # segment carrying two register words (ประกาศ, แนวทาง) emitted a span about nobody.
    text = "ประกาศแนวทางการรักษาพยาบาลสำหรับผู้ป่วย\nดังกล่าวให้สถานพยาบาลทุกแห่งถือปฏิบัติ"
    assert _spans(text) == [], [(e.data_type, e.original_text) for e in _spans(text)]
    # Control: the same marker inside the segment still promotes the role word.
    same_segment = "ประกาศแนวทางการรักษาพยาบาลสำหรับผู้ป่วยดังกล่าวให้สถานพยาบาลถือปฏิบัติ"
    assert [e.data_type for e in _spans(same_segment)] == ["HEALTH"]


def test_a_name_span_anchor_is_vetoed_by_the_impersonal_register():
    # Task 10b F4. `ยื่นคำร้องตามมาตรา` is a real CRF NAME false positive over legal
    # boilerplate; as a tier-1 anchor it was never vetoed, so it conjured a
    # CRIMINAL_RECORD span in a document with no person in it at all. The register veto
    # now reaches the NAME-span route, whose evidence is a model guess.
    text = "ให้ผู้เสียหายยื่นคำร้องตามมาตรา 193 ในคดีอาญา"
    name_false_positive = [(13, 31)]
    assert _spans(text, name_false_positive) == []
    assert [e.data_type for e in detect_all(text) if e.data_type in SENSITIVE_DATA_TYPE_SET] == []


def test_a_lexical_tier1_anchor_still_beats_the_register_veto_beside_a_name_span():
    # Gold `sn05`'s shape: เผยแพร่ vetoes the NAME span, the ข้าพเจ้า pronoun is not
    # vetoable, so the span still fires. The two lexical tier-1 routes are unchanged.
    text = "ข้าพเจ้า นายเอกรัตน์ มั่นคงดี ยอมรับว่าได้เผยแพร่ความคิดเห็นทางการเมือง"
    assert [e.data_type for e in _spans(text, [(9, 28)])] == ["POLITICAL_OPINION"]


# ---------------------------------------------------------------------------
# §3 category-error veto for HEALTH
# ---------------------------------------------------------------------------


def test_health_category_error_is_dropped_not_trimmed():
    text = "นายสมชาย ใจดี ตรวจสอบสุขภาพระบบประจำสัปดาห์"
    assert _spans(text) == []


def test_health_category_error_veto_does_not_touch_a_real_health_span():
    text = "นายสมชาย ใจดี ตรวจสุขภาพประจำปีที่โรงพยาบาล"
    found = _spans(text)
    assert [e.data_type for e in found] == ["HEALTH"]
    assert found[0].original_text.startswith("สุขภาพ")


# ---------------------------------------------------------------------------
# Task 10b F3 — the result cue yields its label to the specific category
# ---------------------------------------------------------------------------


def test_a_result_cue_yields_its_label_to_genetic():
    # Gold `sn13`: HEALTH's ผลตรวจ matches six characters before GENETIC's ดีเอ็นเอ, wins
    # the region on start order, and masks genetic data under the wrong category. The
    # characters are unchanged; only the label moves.
    text = "ผู้ต้องหารายนี้ ผลตรวจดีเอ็นเอตรงกับวัตถุพยาน"
    found = _spans(text)
    assert [(e.data_type, e.original_text) for e in found] == [
        ("GENETIC", "ผลตรวจดีเอ็นเอตรงกับวัตถุพยาน")
    ]


def test_a_result_cue_yields_its_label_to_biometric():
    text = "ผู้ต้องหารายนี้ ผลตรวจลายนิ้วมือตรงกับที่เกิดเหตุ"
    found = _spans(text)
    assert [(e.data_type, e.original_text) for e in found] == [
        ("BIOMETRIC", "ผลตรวจลายนิ้วมือตรงกับที่เกิดเหตุ")
    ]


def test_a_result_cue_with_no_specific_keyword_stays_health():
    text = "ผู้ป่วยรายนี้ ผลตรวจเลือดอยู่ในเกณฑ์ปกติ"
    assert [e.data_type for e in _spans(text)] == ["HEALTH"]


def test_a_health_keyword_that_is_not_a_result_cue_keeps_its_label():
    # โรค asserts a health fact on its own, so it does not yield. Only the result cue,
    # which asserts nothing until the following keyword says what was tested, does.
    text = "ผู้ป่วยรายนี้มีโรคทางพันธุกรรมในครอบครัว"
    assert [e.data_type for e in _spans(text)] == ["HEALTH"]


# ---------------------------------------------------------------------------
# §4.1 segment scope
# ---------------------------------------------------------------------------


def test_a_single_space_never_splits_a_segment():
    text = "นายสมชาย ใจดี มีโรคประจำตัว"
    assert [e.data_type for e in _spans(text)] == ["HEALTH"]


def test_two_spaces_split_the_segment():
    text = "นายสมชาย ใจดี ลงชื่อ  บันทึกโรคประจำตัวไว้"
    assert _spans(text) == []


def test_a_newline_splits_the_segment():
    text = "บันทึกประวัติการรักษาไว้\nนายสมชาย ใจดี ลงชื่อรับทราบ"
    assert _spans(text) == []


# ---------------------------------------------------------------------------
# §4.3 span shape
# ---------------------------------------------------------------------------


def test_span_never_expands_backwards_past_the_keyword():
    text = "ผู้ป่วยรายนี้มีโรคเบาหวาน"
    found = _spans(text)
    assert len(found) == 1
    assert text[found[0].span[0] :].startswith("โรค")


def test_span_is_capped_at_max_span_chars():
    long_tail = "เบาหวานชนิดที่สองซึ่งควบคุมระดับน้ำตาลได้ยากมากและต้องพบแพทย์ทุกเดือนอย่างต่อเนื่อง"
    text = "ผู้ป่วยรายนี้มีโรค" + long_tail
    found = _spans(text)
    assert len(found) == 1
    start, end = found[0].span
    assert end - start <= MAX_SPAN_CHARS
    assert text[start:].startswith("โรค")


def test_blocked_span_clamps_the_forward_end():
    text = "ผู้ป่วยรายนี้มีโรคเบาหวาน1234567890123"
    blocked = [(text.index("1234567890123"), len(text))]
    found = detect_sensitive_spans(text, [], blocked_spans=blocked)
    assert len(found) == 1
    assert found[0].span[1] <= blocked[0][0]


def test_sensitive_spans_never_overlap_each_other():
    text = "ผู้ป่วยรายนี้มีประวัติการรักษาโรคเบาหวาน และนับถือศาสนาอิสลาม"
    found = _spans(text)
    assert len(found) >= 2
    for left, right in zip(found, found[1:], strict=False):
        assert left.span[1] <= right.span[0]


# ---------------------------------------------------------------------------
# §4.4 merge — coverage / non-overlap / entity_id invariant
# ---------------------------------------------------------------------------


def _covered(entities: list[Entity]) -> set[int]:
    covered: set[int] = set()
    for entity in entities:
        covered.update(range(*entity.span))
    return covered


def _assert_merge_invariant(text: str, kept: list[Entity], sensitive: list[Entity]):
    merged = merge_sensitive_spans(text, kept, sensitive)
    # coverage: nothing the pipeline already covered may be uncovered
    assert _covered(kept) <= _covered(merged)
    # non-overlap
    ordered = sorted(merged, key=lambda e: e.span[0])
    assert [e.span for e in ordered] == [e.span for e in merged], "output must be sorted by start"
    for left, right in zip(ordered, ordered[1:], strict=False):
        assert left.span[1] <= right.span[0], (left.span, right.span)
    # unique entity ids
    ids = [e.entity_id for e in merged]
    assert len(ids) == len(set(ids))
    # original_text stays true to the span
    for entity in merged:
        assert entity.original_text == text[entity.span[0] : entity.span[1]]
    return merged


def test_merge_two_remainder_fixture_keeps_both_sides():
    """A sensitive span strictly inside an ORGANIZATION splits it into TWO pieces.

    Revision 1 of the record kept only the longer side and silently uncovered
    characters 0..4. A natural corpus produces zero cases of this shape, so this
    fixture is the only thing that can catch the regression.
    """
    text = "ก" * 20
    org = _ent("ORGANIZATION", (0, 20), text)
    health = _ent("HEALTH", (5, 10), text)
    merged = _assert_merge_invariant(text, [org], [health])
    assert [(e.data_type, e.span) for e in merged] == [
        ("ORGANIZATION", (0, 5)),
        ("HEALTH", (5, 10)),
        ("ORGANIZATION", (10, 20)),
    ]
    # lowest-start piece inherits the original id; further pieces are fresh
    assert merged[0].entity_id == org.entity_id
    assert merged[1].entity_id == health.entity_id
    assert merged[2].entity_id not in {org.entity_id, health.entity_id}


def test_merge_two_sensitive_spans_inside_one_organization():
    text = "ก" * 30
    org = _ent("ORGANIZATION", (0, 30), text)
    a = _ent("HEALTH", (5, 10), text)
    b = _ent("RELIGION", (15, 20), text)
    merged = _assert_merge_invariant(text, [org], [a, b])
    assert [(e.data_type, e.span) for e in merged] == [
        ("ORGANIZATION", (0, 5)),
        ("HEALTH", (5, 10)),
        ("ORGANIZATION", (10, 15)),
        ("RELIGION", (15, 20)),
        ("ORGANIZATION", (20, 30)),
    ]


def test_merge_sensitive_inside_location_yields_characters():
    text = "ก" * 20
    loc = _ent("LOCATION", (2, 18), text)
    health = _ent("HEALTH", (6, 9), text)
    merged = _assert_merge_invariant(text, [loc], [health])
    assert [(e.data_type, e.span) for e in merged] == [
        ("LOCATION", (2, 6)),
        ("HEALTH", (6, 9)),
        ("LOCATION", (9, 18)),
    ]


def test_merge_never_trims_a_structured_fp_hit():
    text = "ก" * 30
    thai_id = _ent("THAI_ID", (10, 23), text, redact_type="FP")
    candidate = _ent("HEALTH", (5, 28), text)
    merged = _assert_merge_invariant(text, [thai_id], [candidate])
    assert ("THAI_ID", (10, 23)) in [(e.data_type, e.span) for e in merged]
    assert [(e.data_type, e.span) for e in merged if e.data_type == "HEALTH"] == [
        ("HEALTH", (5, 10)),
        ("HEALTH", (23, 28)),
    ]
    # the split candidate keeps one id and mints the other
    health = [e for e in merged if e.data_type == "HEALTH"]
    assert health[0].entity_id == candidate.entity_id
    assert health[1].entity_id != candidate.entity_id


def test_merge_never_trims_a_name():
    text = "ก" * 30
    name = _ent("NAME", (12, 20), text)
    candidate = _ent("RELIGION", (8, 26), text)
    merged = _assert_merge_invariant(text, [name], [candidate])
    assert ("NAME", (12, 20)) in [(e.data_type, e.span) for e in merged]
    assert [(e.data_type, e.span) for e in merged if e.data_type == "RELIGION"] == [
        ("RELIGION", (8, 12)),
        ("RELIGION", (20, 26)),
    ]


def test_merge_drops_a_candidate_fully_covered_by_a_blocker():
    text = "ก" * 20
    thai_id = _ent("THAI_ID", (0, 20), text, redact_type="FP")
    candidate = _ent("HEALTH", (4, 12), text)
    merged = _assert_merge_invariant(text, [thai_id], [candidate])
    assert [(e.data_type, e.span) for e in merged] == [("THAI_ID", (0, 20))]


def test_merge_sensitive_candidates_never_overlap_each_other():
    text = "ก" * 20
    first = _ent("HEALTH", (2, 12), text)
    second = _ent("RELIGION", (8, 18), text)
    merged = _assert_merge_invariant(text, [], [first, second])
    assert [(e.data_type, e.span) for e in merged] == [
        ("HEALTH", (2, 12)),
        ("RELIGION", (12, 18)),
    ]


def test_merge_mixed_fixture_holds_the_invariant():
    text = "ก" * 60
    kept = [
        _ent("NAME", (0, 8), text),
        _ent("ORGANIZATION", (10, 40), text),
        _ent("THAI_ID", (44, 57), text, redact_type="FP"),
    ]
    sensitive = [
        _ent("HEALTH", (4, 20), text),
        _ent("RELIGION", (25, 30), text),
        _ent("GENETIC", (50, 60), text),
    ]
    merged = _assert_merge_invariant(text, kept, sensitive)
    assert _covered(kept) <= _covered(merged)
    assert {e.data_type for e in merged} >= {"NAME", "ORGANIZATION", "THAI_ID"}


def test_merge_without_sensitive_spans_returns_the_list_unchanged():
    text = "ก" * 20
    kept = [_ent("NAME", (0, 8), text), _ent("ORGANIZATION", (10, 18), text)]
    assert merge_sensitive_spans(text, kept, []) == kept


# ---------------------------------------------------------------------------
# §3 wiring into detect_all
# ---------------------------------------------------------------------------


def test_detect_all_emits_person_linked_sensitive_spans():
    text = "นายสมชาย ใจดี ป่วยเป็นโรคเบาหวาน"
    types = [e.data_type for e in detect_all(text)]
    assert "HEALTH" in types


def test_detect_all_is_untouched_on_an_impersonal_document():
    text = "ประกาศกรมควบคุมโรค เรื่อง แนวทางการรักษาผู้ป่วยไข้เลือดออก"
    assert not [e for e in detect_all(text) if e.data_type in SENSITIVE_DATA_TYPE_SET]


# ---------------------------------------------------------------------------
# §5.2 token labels
# ---------------------------------------------------------------------------

EXPECTED_LABELS = {
    "HEALTH": "ข้อมูลสุขภาพ",
    "CRIMINAL_RECORD": "ประวัติคดี",
    "DISABILITY": "ความพิการ",
    "GENETIC": "ข้อมูลพันธุกรรม",
    "BIOMETRIC": "ข้อมูลชีวภาพ",
    "RELIGION": "ศาสนา",
    "RACE_ETHNICITY": "เชื้อชาติ",
    "SEXUAL_BEHAVIOR": "พฤติกรรมทางเพศ",
    "POLITICAL_OPINION": "ความเห็นการเมือง",
    "LABOR_UNION": "สหภาพแรงงาน",
}


def test_token_labels_are_registered_exactly():
    for data_type, label in EXPECTED_LABELS.items():
        assert TOKEN_LABEL[data_type] == label
    assert len(set(TOKEN_LABEL.values())) == len(TOKEN_LABEL)


def test_every_sensitive_type_is_a_safe_outbound_leak_type():
    for data_type in SENSITIVE_DATA_TYPES:
        assert data_type in SAFE_OUTBOUND_LEAK_TYPES
    # the three stale short names stay: removing a member of a fail-closed
    # allowlist is a separate, separately-verified change (record §6.2)
    for stale in ("CRIMINAL", "ETHNICITY", "UNION"):
        assert stale in SAFE_OUTBOUND_LEAK_TYPES


# ---------------------------------------------------------------------------
# §5.3 / §5.4 masking is a token in BOTH modes, and it round-trips
# ---------------------------------------------------------------------------

TWO_HEALTH_DOC = "นายสมชาย ใจดี ป่วยเป็นโรคเบาหวาน และเข้ารับการรักษาที่โรงพยาบาลศิริราช"


@pytest.mark.parametrize("mode", ["token", "surrogate"])
def test_two_health_span_round_trip(mode):
    masked = amphrang.anonymize(TWO_HEALTH_DOC, mode=mode, salt=SALT)
    assert masked.entity_type_counts.get("HEALTH") == 2, masked.entity_type_counts
    assert "โรคเบาหวาน" not in masked.text
    # a token in BOTH modes: the ม.26 label is what replaces the diagnosis
    assert "[ข้อมูลสุขภาพ_" in masked.text, masked.text
    assert amphrang.restore(masked.text, masked.mapping).text == TWO_HEALTH_DOC


def test_surrogate_mode_still_fakes_the_name_realistically():
    masked = amphrang.anonymize(TWO_HEALTH_DOC, mode="surrogate", salt=SALT)
    assert "[ชื่อ_" not in masked.text
    assert "สมชาย" not in masked.text


def test_analyze_counts_the_sensitive_span():
    """The intended behaviour change of §7: analyze() now counts ม.26 spans.

    `section26` stays driven by the untouched report.py flag scan, so it is unaffected.
    """
    report = amphrang.analyze(TWO_HEALTH_DOC)
    health = [row for row in report["breakdown"] if row["data_type"] == "HEALTH"]
    assert [row["count"] for row in health] == [2], report["breakdown"]
    assert [row["category"] for row in report["section26"]] == ["HEALTH"]


# ---------------------------------------------------------------------------
# §6.2 outbound guard
# ---------------------------------------------------------------------------


def test_scan_outbound_leaks_is_clean_on_masked_output():
    masked = amphrang.anonymize(TWO_HEALTH_DOC, mode="token", salt=SALT)
    context = OutboundGuardContext(frozenset(masked.mapping))
    assert scan_outbound_leaks(masked.text, context) == []


def test_scan_outbound_leaks_reports_an_unmasked_sensitive_phrase():
    leaks = scan_outbound_leaks(TWO_HEALTH_DOC, OutboundGuardContext())
    assert any(leak.data_type in SENSITIVE_DATA_TYPE_SET for leak in leaks)


# ---------------------------------------------------------------------------
# §6.3 _layer1_pii_scan char coverage
# ---------------------------------------------------------------------------

_L1_TEXT = "ติดต่อ 081-234-5678 ได้ทุกวัน"
_L1_SPLIT = 10


def _l1_vault(text: str, ranges: tuple[tuple[int, int], ...]) -> SessionVault:
    vault = SessionVault()
    for start, end in ranges:
        vault.write(
            VaultRecord(
                entity_id=str(uuid.uuid4()),
                original=text[start:end],
                pseudonym=f"PSEUDO_{start}_{end}",
                type="TB",
                data_type="NAME",
                span=(start, end),
                timestamp=time.monotonic(),
            )
        )
    return vault


def test_layer1_excuses_a_span_covered_by_two_contiguous_restored_ranges():
    """The §6.3 change: a detection straddling two adjacent validated ranges is expected.

    The merge splits one CRF span into an entity plus a sensitive span, so the
    restored text re-detects the original wide span across two ranges.
    """
    ranges = ((0, _L1_SPLIT), (_L1_SPLIT, len(_L1_TEXT)))
    detected = detect_all(_L1_TEXT)
    assert any(e.span[0] < _L1_SPLIT < e.span[1] for e in detected), detected
    reverse_result = ReverseResult(text=_L1_TEXT, restored_ranges=ranges)
    clean, flags = _layer1_pii_scan(reverse_result, _l1_vault(_L1_TEXT, ranges))
    assert clean, flags


def test_layer1_still_halts_when_one_character_was_not_restored():
    ranges = ((0, _L1_SPLIT), (_L1_SPLIT + 1, len(_L1_TEXT)))
    reverse_result = ReverseResult(text=_L1_TEXT, restored_ranges=ranges)
    clean, flags = _layer1_pii_scan(reverse_result, _l1_vault(_L1_TEXT, ranges))
    assert not clean
    assert any(flag.startswith("unexpected_pii_count:") for flag in flags)


def test_validate_output_raises_pii_leak_error_on_the_uncovered_character():
    from amphrang.engine.output_validator import validate_output

    ranges = ((0, _L1_SPLIT), (_L1_SPLIT + 1, len(_L1_TEXT)))
    reverse_result = ReverseResult(
        text=_L1_TEXT,
        restored_ranges=ranges,
        audit_summary={"total_entities": 0, "replaced_count": 0},
    )
    registry = EntityRegistry(entities=[], fp_count=0, tb_count=0)
    with pytest.raises(PIILeakError):
        validate_output(reverse_result, registry, _l1_vault(_L1_TEXT, ranges))
