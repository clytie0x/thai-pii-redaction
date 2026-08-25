"""Value-canonicalization helpers shared by the anonymizer."""

from __future__ import annotations

import re

_NAME_TYPE = "NAME"

_NAME_TITLE_RE = re.compile(r"^(?:นางสาว|นาย|นาง|น\.ส\.|ด\.ช\.|ด\.ญ\.|เด็กชาย|เด็กหญิง|คุณ)\s*")


def canonical_value(data_type: str, value: str) -> str:
    """Fold formatting differences that would inflate a distinct count. Strong types get bespoke
    normalization; NAME strips a leading title but stays a WEAK identifier (never feeds
    subjects_min/max); everything else gets a whitespace/case fold.
    """
    if data_type == "THAI_ID":
        return re.sub(r"\D", "", value)
    if data_type == "PASSPORT":
        return re.sub(r"[\s-]", "", value).upper()
    if data_type == "PHONE":
        digits = re.sub(r"\D", "", value)
        # +66 drops the domestic leading 0 (66 + 9 mobile / 66 + 8 landline digits); fold back so
        # "+66 81 234 5678" and "081-234-5678" count once.
        if digits.startswith("66") and len(digits) in (10, 11):
            digits = "0" + digits[2:]
        return digits
    if data_type == "EMAIL":
        return value.strip().casefold()
    if data_type == _NAME_TYPE:
        stripped = _NAME_TITLE_RE.sub("", value.strip())
        return re.sub(r"\s+", " ", stripped).strip().casefold()
    return re.sub(r"\s+", " ", value.strip()).casefold()
