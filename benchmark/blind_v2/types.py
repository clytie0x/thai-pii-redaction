"""Entity scheme for the reproducible blind-v2 comparison set.

The eleven shared benchmark types plus IBAN, which the product detects and the
historical gold scheme leaves out. Section 26 categories are warn/report
labels, not redaction entities.
"""

from __future__ import annotations

REDACTION_TYPES = (
    "THAI_ID",
    "PHONE",
    "EMAIL",
    "BANK_ACCOUNT",
    "CREDIT_CARD",
    "PASSPORT",
    "VEHICLE_PLATE",
    "STUDENT_ID",
    "DATE_OF_BIRTH",
    "NAME",
    "ADDRESS",
    "IBAN",
)

SECTION26_TYPES = (
    "HEALTH",
    "RELIGION",
    "RACE_ETHNICITY",
    "POLITICAL_OPINION",
    "SEXUAL_BEHAVIOR",
    "CRIMINAL_RECORD",
    "DISABILITY",
    "LABOR_UNION",
)

REDACTION_TYPE_SET = frozenset(REDACTION_TYPES)
SECTION26_TYPE_SET = frozenset(SECTION26_TYPES)
