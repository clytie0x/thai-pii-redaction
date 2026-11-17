"""WP3 risk, TRIR, over-redaction, and the paired sign-flip."""

from __future__ import annotations

from benchmark.yrss_v2.stats import holm as v2_holm
from benchmark.yrss_v3.corpus import contamination_hits, render_split
from benchmark.yrss_v3.metrics import over_redaction_rate, per_type_scores
from benchmark.yrss_v3.protocol import K_ANONYMITY
from benchmark.yrss_v3.qi import (
    QiSpan,
    catalog_section26,
    document_risk,
    qi_signature,
    synthetic_population,
    trir_by_section26,
)
from benchmark.yrss_v3.stats import holm, sign_flip_difference
from pii_redactor.pdpa_categories import SECTION26_CATEGORIES


def test_section26_codes_are_the_product_catalog():
    assert catalog_section26() == SECTION26_CATEGORIES
    assert K_ANONYMITY == 5


def test_residual_signature_keeps_a_partially_redacted_quasi_identifier():
    text = "ชื่อเล่น มิ้น อายุ 34 ปี"
    nick = QiSpan(text.index("มิ้น"), text.index("มิ้น") + len("มิ้น"), "nickname", None)
    age = QiSpan(text.index("34 ปี"), text.index("34 ปี") + len("34 ปี"), "age", None)
    qi = (nick, age)
    assert qi_signature(text, qi) == (("age", "34 ปี"), ("nickname", "มิ้น"))
    covered = qi_signature(text, qi, redacted=[(nick.start, nick.end), (age.start, age.end)])
    assert covered == ()
    partial = qi_signature(text, qi, redacted=[(age.start, age.start + 1)])
    assert ("age", "34 ปี") in partial
    assert ("nickname", "มิ้น") in partial
    repeated = "มิ้น มิ้น"
    first = repeated.index("มิ้น")
    second = repeated.index("มิ้น", first + 1)
    width = len("มิ้น")
    collapsed = qi_signature(
        repeated,
        (
            QiSpan(first, first + width, "nickname", None),
            QiSpan(second, second + width, "nickname", None),
        ),
    )
    assert collapsed == (("nickname", "มิ้น"),)


def test_document_risk_uses_cooccurrence_and_ignores_empty_keys():
    common = (("age", "34 ปี"), ("nickname", "มิ้น"))
    rare = (("nickname", "โอ๊ต"),)
    population = (common,) * 5 + (rare,)
    signatures = (common, rare, ())
    report = document_risk(signatures, population, k=5)
    assert report["risky_documents"] == 1
    assert report["documents_with_residual_qi"] == 2
    assert report["risk_rate"] == 1 / 3
    assert report["k"] == 5
    # A different combination is not the same co-occurrence, even if it shares a field.
    mixed = (("age", "34 ปี"),)
    assert document_risk((mixed,), population, k=5)["risky_documents"] == 1


def test_population_size_is_the_callers_and_trir_rejects_unknown_codes():
    rows = synthetic_population(7, 4, fields=("nickname", "age"))
    assert len(rows) == 4
    assert rows == synthetic_population(7, 4, fields=("nickname", "age"))
    report = trir_by_section26([("HEALTH", True), ("HEALTH", False), ("RELIGION", False)])
    assert report["HEALTH"] == {"rate": 0.5, "successes": 1, "trials": 2}
    assert report["RELIGION"]["rate"] == 0.0
    assert report["GENETIC"]["rate"] is None
    assert set(report) == set(catalog_section26())
    try:
        trir_by_section26([("NOT_A_CODE", True)])
    except ValueError as exc:
        assert str(exc) == "unknown-section26"
    else:
        raise AssertionError("unknown-code-accepted")


def test_contamination_flags_a_copied_family_and_not_an_unrelated_note():
    from benchmark.yrss_v3.corpus import fixed_text
    from benchmark.yrss_v3.families import templates

    copied = next(iter(templates("test")))
    quoted = "คำนำหน้า " + fixed_text(copied) + " เชิงอรรถที่ยาวมาก " + ("ก" * 80)
    assert copied.family in contamination_hits(quoted)
    assert contamination_hits("ประกาศปิดทำการของโรงอาหารโดยไม่มีข้อมูลส่วนบุคคลเลย") == []


def test_over_redaction_and_perfect_per_type_scores():
    text = "abcdefghij"
    assert over_redaction_rate(text, [(0, 4)], [(0, 6)]) == 2 / 6
    assert over_redaction_rate(text, [(0, 4)], [(0, 4)]) == 0.0
    assert over_redaction_rate(text, [(0, len(text))], [(0, len(text))]) == 0.0
    documents = render_split("dev")
    predictions = [
        [(span.start, span.end, span.entity_type) for span in doc.spans] for doc in documents
    ]
    scored = per_type_scores(documents, predictions)
    assert scored["micro"]["recall"] == 1.0
    assert scored["micro"]["precision"] == 1.0
    present = [row for row in scored["by_type"].values() if row["n"]]
    assert present
    assert all(row["f2"] == 1.0 for row in present)


def test_sign_flip_matches_holm_and_separates_a_tied_system_from_a_better_one():
    assert holm([0.01, 0.04, 0.2]) == v2_holm([0.01, 0.04, 0.2])
    tied = sign_flip_difference([(3, 1, 1)] * 4, [(3, 1, 1)] * 4, n_permutations=50, seed=0)
    assert tied["p_value"] == 1.0
    better = sign_flip_difference(
        [(8, 0, 0)] * 8,
        [(0, 0, 8)] * 8,
        n_permutations=200,
        seed=0,
    )
    assert better["p_value"] < 0.05
    again = sign_flip_difference(
        [(8, 0, 0)] * 8,
        [(0, 0, 8)] * 8,
        n_permutations=200,
        seed=0,
    )
    assert again == better
