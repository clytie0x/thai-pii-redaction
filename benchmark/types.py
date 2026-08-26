from __future__ import annotations

from dataclasses import dataclass

SHARED_ENTITY_TYPES = (
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
    "JURISTIC_ID",
    "DRIVER_LICENSE",
    "LINE_ID",
    "GPS_COORD",
    "HOUSE_REG_ID",
    "IP_ADDRESS",
    "MAC_ADDRESS",
    "LAND_DEED_ID",
)
SHARED_ENTITY_TYPE_SET = frozenset(SHARED_ENTITY_TYPES)
OUT_OF_SCHEME_TYPE = "OUT_OF_SCHEME"


@dataclass(frozen=True)
class GoldSpan:
    start: int
    end: int
    entity_type: str


@dataclass
class Sample:
    text: str
    spans: list[GoldSpan]
    template_id: str
    slice: str
