"""Section 26 names stay one list across report, semantics, and the leak guard."""

from pii_redactor.leak_guard import SAFE_OUTBOUND_LEAK_TYPES, normalize_outbound_leak_types
from pii_redactor.pdpa_categories import SECTION26_CATEGORIES, canonical_section26
from pii_redactor.report import _SECTION26_KEYWORDS
from pii_redactor.sensitive_detector import _PROTOTYPES


def test_section26_names_match_across_the_three_callers():
    assert tuple(_SECTION26_KEYWORDS) == SECTION26_CATEGORIES
    assert set(_PROTOTYPES) == set(SECTION26_CATEGORIES)
    for name in SECTION26_CATEGORIES:
        assert name in SAFE_OUTBOUND_LEAK_TYPES
    for stale in ("ETHNICITY", "CRIMINAL", "UNION"):
        assert stale not in SAFE_OUTBOUND_LEAK_TYPES
        assert canonical_section26(stale) in SECTION26_CATEGORIES


def test_old_section26_labels_are_stored_under_the_canonical_name():
    assert normalize_outbound_leak_types(["ETHNICITY"]) == ["RACE_ETHNICITY"]
    assert normalize_outbound_leak_types(["UNION", "LABOR_UNION"]) == ["LABOR_UNION"]
    assert normalize_outbound_leak_types(["CRIMINAL"]) == ["CRIMINAL_RECORD"]
