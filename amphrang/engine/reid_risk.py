"""Re-identification risk assessment."""

import re
from dataclasses import dataclass


@dataclass
class ReidRiskResult:
    score: float  # 0.0 to 100.0
    grade: str  # "A" | "B" | "C" | "D" | "F"
    qi_found: list[str]  # quasi-identifiers detected (e.g. ["gender", "district", "date_of_birth"])
    high_risk_combo: bool  # True if {gender + district + (DOB|age)} combo found
    warnings: list[str]  # human-readable warnings


# Quasi-identifier detection patterns
_QI_PATTERNS = {
    "gender": re.compile(r"(?:นาย|นาง(?:สาว)?|ด\.ช\.|ด\.ญ\.)\s*\w", re.UNICODE),
    "date_of_birth": re.compile(r"\b(?:\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\d{4}-\d{2}-\d{2})\b"),
    "age": re.compile(r"(?:อายุ\s*\d+\s*ปี|\d+\s*ขวบ)", re.UNICODE),
    "district": re.compile(r"(?:แขวง|ตำบล)\s*\w+", re.UNICODE),
    "province": re.compile(r"(?:จังหวัด|จ\.)\s*\w+", re.UNICODE),
    "occupation": re.compile(r"(?:อาชีพ|ทำงาน(?:เป็น)?|ประกอบอาชีพ)\s*\w+", re.UNICODE),
    "religion": re.compile(r"(?:ศาสนา|พุทธ|คริสต์|อิสลาม|ฮินดู|ซิกข์)", re.UNICODE),
    "nationality": re.compile(
        r"(?<![ก-๙])สัญชาติ\s*(?:ไทย|ลาว|พม่า|เมียนมา|กัมพูชา|เขมร|จีน|เวียดนาม|มาเลเซีย|อินเดีย|ญี่ปุ่น|เกาหลี|อเมริกัน|อังกฤษ|ฝรั่งเศส|เยอรมัน|[ก-๙]{2,12})",
        re.UNICODE,
    ),
    "body_metrics": re.compile(
        r"(?:น้ำหนัก\s*\d{2,3}(?:\.\d+)?\s*(?:กก\.?|กิโลกรัม)|ส่วนสูง\s*\d{2,3}\s*(?:ซม\.?|เซนติเมตร))",
        re.UNICODE,
    ),
}


def assess_reid_risk(text: str) -> ReidRiskResult:
    """Assess re-identification risk from quasi-identifiers: +10 per QI type, forced F-range
    for gender + district + (DOB|age), capped at 100. Grades A..F in 20-point bands.
    """
    qi_found = []

    for qi_type, pattern in _QI_PATTERNS.items():
        if pattern.search(text):
            qi_found.append(qi_type)

    score = len(qi_found) * 10.0

    has_gender = "gender" in qi_found
    has_district = "district" in qi_found
    has_dob_or_age = "date_of_birth" in qi_found or "age" in qi_found
    high_risk_combo = has_gender and has_district and has_dob_or_age

    if high_risk_combo:
        score = max(score, 85.0)  # Mandatory F-range

    score = min(score, 100.0)

    if score <= 20:
        grade = "A"
    elif score <= 40:
        grade = "B"
    elif score <= 60:
        grade = "C"
    elif score <= 80:
        grade = "D"
    else:
        grade = "F"

    warnings = []
    if high_risk_combo:
        warnings.append(
            "High re-identification risk: gender + district + (age/DOB) combination detected. "
            "This combination may uniquely identify a person even without direct PII."
        )
    if "religion" in qi_found:
        warnings.append("Religion mentioned — PDPA Section 26 sensitive category.")
    if score >= 60:
        warnings.append(
            f"Re-identification risk score {score:.0f}/100 — consider removing quasi-identifiers."
        )

    return ReidRiskResult(
        score=score,
        grade=grade,
        qi_found=qi_found,
        high_risk_combo=high_risk_combo,
        warnings=warnings,
    )
