"""Preserve the SDK's existing quasi-identifier reports in the shared core."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.http_v2 import RECOMMENDATION_TEMPLATES, ReidProjection
from pii_redactor.reid_risk import assess_reid_risk

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("ผู้สมัคร สัญชาติไทย อาศัยในกรุงเทพ", "nationality"),
        ("เขามีสัญชาติไทยโดยกำเนิด", "nationality"),
        ("ผู้ต้องหาถือสัญชาติลาว", "nationality"),
        ("น้ำหนัก 62 กก. ส่วนสูง 171 ซม.", "body_metrics"),
    ],
)
def test_existing_sdk_quasi_identifiers_keep_their_category_and_weight(text, category):
    result = assess_reid_risk(text)
    assert result.qi_found == [category]
    assert result.score == 10.0 and result.grade == "A"


@pytest.mark.parametrize("prefix", ["ข้าม", "ต่าง", "นานา", "หลาย"])
def test_nationality_prefix_exclusions_are_preserved(prefix):
    assert "nationality" not in assess_reid_risk(f"องค์กร{prefix}สัญชาติจัดประชุม").qi_found


def test_http_qi_projection_accepts_existing_sdk_categories_in_order():
    values = ["religion", "nationality", "body_metrics"]
    result = ReidProjection(
        score=30.0, grade="B", quasi_identifier_categories=values, high_risk_combination=False
    )
    assert result.quasi_identifier_categories == values
    with pytest.raises(ValidationError):
        ReidProjection(
            score=30.0,
            grade="B",
            quasi_identifier_categories=list(reversed(values)),
            high_risk_combination=False,
        )


def test_office_qi_allowlist_keeps_canonical_order():
    source = (ROOT / "office-addin/src/api.ts").read_text(encoding="utf-8")
    block = re.search(r"const QI_CATEGORIES = \[(.*?)\] as const", source, re.S).group(1)
    assert re.findall(r'"([a-z_]+)"', block) == [
        "gender",
        "date_of_birth",
        "age",
        "district",
        "province",
        "occupation",
        "religion",
        "nationality",
        "body_metrics",
    ]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is needed for the desktop contract")
def test_desktop_contract_projects_existing_sdk_qi_categories():
    payload = {
        "overall_score": 20.0,
        "overall_grade": "A",
        "risk_label": "Very Low Risk",
        "direct_pii_count": 0,
        "fp_count": 0,
        "tb_count": 0,
        "section26_categories": [],
        "reidentification": {
            "score": 20.0,
            "grade": "A",
            "quasi_identifier_categories": ["nationality", "body_metrics"],
            "high_risk_combination": False,
        },
        "breakdown": [],
        "recommendations": [RECOMMENDATION_TEMPLATES["clear"]],
    }
    program = (
        "import {validateAnalyze} from './desktop/src/contract-v2.js';"
        f"const result=validateAnalyze({json.dumps(payload, ensure_ascii=True)});"
        "if (result.reidentification.quasi_identifier_categories.join(',') !=="
        "'nationality,body_metrics') throw new Error('QI projection changed');"
    )
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module", "-e", program],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
