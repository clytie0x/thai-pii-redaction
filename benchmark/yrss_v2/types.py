"""Scored scheme for the YRSS evaluation v2.

Eleven types. DRIVER_LICENSE takes the place of STUDENT_ID, which only
students hold. The product still detects STUDENT_ID; it is just not scored.
"""

from __future__ import annotations

STRUCTURED_TYPES = (
    "THAI_ID",
    "PHONE",
    "EMAIL",
    "BANK_ACCOUNT",
    "CREDIT_CARD",
    "PASSPORT",
    "VEHICLE_PLATE",
    "DRIVER_LICENSE",
)
CONTEXTUAL_TYPES = ("NAME", "ADDRESS", "DATE_OF_BIRTH")
SCHEME_TYPES = STRUCTURED_TYPES + CONTEXTUAL_TYPES

# Template placeholder -> label. Decoys carry no label.
LABELED_KINDS = {
    "name": "NAME",
    "name_en": "NAME",
    "address": "ADDRESS",
    "dob": "DATE_OF_BIRTH",
    "thai_id": "THAI_ID",
    "phone": "PHONE",
    "email": "EMAIL",
    "bank": "BANK_ACCOUNT",
    "card": "CREDIT_CARD",
    "passport": "PASSPORT",
    "plate": "VEHICLE_PLATE",
    "licence": "DRIVER_LICENSE",
}
DECOY_KINDS = ("date", "amount", "order_code", "ref_no", "bad_id13", "tracking", "org")
