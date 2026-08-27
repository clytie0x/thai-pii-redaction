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

# The ten มาตรา 26 sensitive categories, scored from gold-v7 on. They are a
# second annotated family, not members of the shared structured scheme: the
# synthetic corpus never emits them, the LLM baselines are not asked for them,
# and the blind set's draft validator does not accept them. Keeping them out of
# SHARED_ENTITY_TYPES is what preserves all three, while SCORED_ENTITY_TYPES is
# what makes a HEALTH prediction land on the HEALTH row instead of the
# OUT_OF_SCHEME bucket. Annotation rules: docs/annotation-guidelines.md,
# "Sensitive spans (มาตรา 26)". Detector design:
# docs/decisions/2026-08-27-section26-span-masking.md.
SENSITIVE_ENTITY_TYPES = (
    "RACE_ETHNICITY",
    "POLITICAL_OPINION",
    "RELIGION",
    "HEALTH",
    "SEXUAL_BEHAVIOR",
    "CRIMINAL_RECORD",
    "DISABILITY",
    "LABOR_UNION",
    "GENETIC",
    "BIOMETRIC",
)
SENSITIVE_ENTITY_TYPE_SET = frozenset(SENSITIVE_ENTITY_TYPES)

SCORED_ENTITY_TYPES = SHARED_ENTITY_TYPES + SENSITIVE_ENTITY_TYPES
SCORED_ENTITY_TYPE_SET = frozenset(SCORED_ENTITY_TYPES)

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
