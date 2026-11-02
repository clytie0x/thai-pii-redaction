"""Versioned assessment inventory, not a complete-detection/legal certificate."""

SENSITIVE = (
    "RACE",
    "ETHNICITY",
    "POLITICAL_OPINION",
    "BELIEF",
    "SEXUAL_BEHAVIOR",
    "CRIMINAL_RECORD",
    "HEALTH",
    "DISABILITY",
    "LABOR_UNION",
    "GENETIC_DATA",
    "BIOMETRIC_IDENTITY",
)
GENERAL = (
    "IDENTITY",
    "CONTACT",
    "LOCATION",
    "FINANCIAL",
    "EDUCATION",
    "EMPLOYMENT",
    "ONLINE",
    "ACTIVITY",
    "RELATIONSHIPS",
    "MEDIA",
    "QUASI_IDENTIFIERS",
)
MODALITIES = ("text", "image", "audio", "video", "genetic_binary")
STRATEGIES = ("keyword", "contextual", "hybrid")
LAW_VERSION = "TH_PDPA_2026_10_31"
DEFAULT_SEMANTIC_THRESHOLD = 0.40
SOURCES = {
    "act": "https://ratchakitcha.soc.go.th/documents/17082307.pdf",
    "access2026": "https://ratchakitcha.soc.go.th/documents/121423.pdf",
    "erasure2024": "https://infocenter.oic.go.th/upload/cms/1744195455_4477.pdf",
}


def coverage_catalog(strategy: str = "contextual") -> list[dict]:
    if strategy not in STRATEGIES:
        raise ValueError("unknown assessment strategy")
    rows = []
    for category in (*GENERAL, *SENSITIVE):
        capability = "partial_text_assessment"
        if category == "MEDIA":
            capability = "text_claims_only"
        rows.append(
            {
                "category": category,
                "section": "26" if category in SENSITIVE else "6",
                "named": category in SENSITIVE,
                "capability": capability,
                "modalities": ["text"],
            }
        )
    for category, section in (("OTHER_PERSONAL", "6"), ("OTHER_DECLARED_SENSITIVE", "26")):
        rows.append(
            {
                "category": category,
                "section": section,
                "named": False,
                "capability": "open_scope_not_assessed",
                "modalities": [],
            }
        )
    return rows
