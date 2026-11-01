"""One list of PDPA Section 26 category names.

Report keywords, the semantic prototypes, and the outbound leak labels all
use these names. Older short labels still normalize to the same category.
"""

from __future__ import annotations

SECTION26_CATEGORIES = (
    "RACE_ETHNICITY",
    "POLITICAL_OPINION",
    "RELIGION",
    "HEALTH",
    "SEXUAL_BEHAVIOR",
    "CRIMINAL_RECORD",
    "DISABILITY",
    "LABOR_UNION",
)

SECTION26_PATTERNS = {
    "RACE_ETHNICITY": r"(?:เชื้อชาติ|เผ่าพันธุ์|สัญชาติ)",
    "POLITICAL_OPINION": r"(?:ความคิดเห็นทางการเมือง|พรรคการเมือง|อุดมการณ์)",
    "RELIGION": r"(?:ศาสนา|ความเชื่อ|พุทธ|คริสต์|อิสลาม|ฮินดู)",
    "HEALTH": r"(?:โรค|การรักษา|ผล(?:การ)?ตรวจ|สุขภาพ|ประวัติ(?:การ)?รักษา)",
    "SEXUAL_BEHAVIOR": r"(?:เพศ(?:สัมพันธ์|วิถี)|รสนิยมทางเพศ)",
    "CRIMINAL_RECORD": r"(?:คดี|ต้องโทษ|จำคุก|ประวัติอาชญากรรม|ถูกฟ้อง)",
    "DISABILITY": r"(?:ทุพพลภาพ|ความพิการ|คนพิการ)",
    "LABOR_UNION": r"(?:สหภาพแรงงาน|สมาคมลูกจ้าง)",
}

# Labels that predate the single list. They are accepted and stored canonically.
SECTION26_ALIASES = {
    "ETHNICITY": "RACE_ETHNICITY",
    "CRIMINAL": "CRIMINAL_RECORD",
    "UNION": "LABOR_UNION",
}


def canonical_section26(label: str) -> str | None:
    if label in SECTION26_PATTERNS:
        return label
    return SECTION26_ALIASES.get(label)
