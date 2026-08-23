"""The breach assessment rendered as a Thai PDF slip.

Whitelist renderer over `BreachAssessment.to_json_dict()`, which carries no value, excerpt, or
hash to begin with, so the PII-free property is structural. The method statement and NAME note
are drawn verbatim from the dict so JSON and PDF cannot disagree. Unlike `render_receipt`, this
writes the file itself (`render_breach_pdf(assessment, output_path) -> None`).
"""

from __future__ import annotations

import textwrap
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# One label vocabulary across every PDF surface.
from amphrang.engine.report_pdf import _TYPE_LABELS
from amphrang.engine.thai_pdf_text import draw_text, register_thai_font

_TITLE = "Amphrang — รายงานประเมินผลกระทบจากข้อมูลรั่วไหล"
_SUBTITLE = "จัดทำเพื่อประกอบการแจ้งเหตุตาม พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล มาตรา 37(4)"

_NOTES = [
    "ข้อจำกัดและวิธีอ่านรายงานนี้",
    "รายงานนี้บันทึกสิ่งที่ระบบตรวจพบและวิธีประมาณการเท่านั้น ไม่ใช่บทสรุปทางกฎหมาย "
    "และไม่ได้ชี้ว่าต้องแจ้งเหตุต่อสำนักงานคณะกรรมการคุ้มครองข้อมูลส่วนบุคคลหรือไม่",
    "การตรวจจับไม่มีทางครบถ้วนร้อยเปอร์เซ็นต์ จำนวนที่พบคือสิ่งที่ระบบเห็น ไม่ใช่สิ่งที่มีอยู่ทั้งหมด",
    "ชื่อไฟล์ที่ปรากฏเป็นชื่อไฟล์ที่ผู้ควบคุมข้อมูลตั้งเอง ชื่อไฟล์เองอาจเป็นข้อมูลอ่อนไหวได้ "
    "รายงานนี้ปฏิบัติต่อชื่อไฟล์เช่นเดียวกับที่ปฏิบัติต่อเอกสารต้นทาง",
]


def _wrap(text: str, width: int = 100) -> list[str]:
    """Word-wrap a verbatim paragraph statement; `draw_text` only draws one line."""
    return textwrap.wrap(text, width=width) or [""]


def render_breach_pdf(assessment: dict, output_path: str | Path) -> None:
    """Draw `assessment` (a `BreachAssessment.to_json_dict()` dict) onto an A4 PDF at
    `output_path`.

    Only counts, type/category labels, grades, version strings, and failed-file basenames +
    short reasons reach the canvas. `OSError` from the write propagates uncaught.
    """
    font = register_thai_font()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _width, height = A4
    y = height - 56

    def line(txt: str, size: int = 11, dy: int = 16) -> None:
        nonlocal y
        if y < 60:
            c.showPage()
            y = height - 56
        draw_text(c, 56, y, txt, font, size)
        y -= dy

    files = assessment["files"]
    subjects = assessment["subjects"]
    name_weak = assessment["name_weak_identifier"]
    risk = assessment["risk"]
    environment = assessment["environment"]

    line(_TITLE, 17, 22)
    line(_SUBTITLE, 10, 20)
    line(
        f"ประเมินเมื่อ {assessment['assessed_at']}   เวอร์ชันระบบ {environment['product_version']}",
        9,
        22,
    )

    line("เอกสารที่ประเมิน", 13, 18)
    line(
        f"- รวม {files['total']} ไฟล์   ประเมินสำเร็จ {files['assessed']} ไฟล์   "
        f"ล้มเหลว {len(files['failed'])} ไฟล์   ข้าม {files['skipped']['count']} ไฟล์"
    )
    for failed in files["failed"]:
        line(f"  - {failed['basename']}  {failed['reason']}", 9, 13)
    for name in files["skipped"]["basenames"]:
        line(f"  - {name}  ข้ามเนื่องจากนามสกุลไฟล์ไม่รองรับ", 9, 13)
    line("", 4, 8)

    line("ประเภทข้อมูลส่วนบุคคลที่พบ", 13, 18)
    if assessment["types"]:
        for data_type, counts in assessment["types"].items():
            label = _TYPE_LABELS.get(data_type, data_type)
            line(f"- {label}  รวม {counts['total']} ครั้ง  ค่าที่ไม่ซ้ำกัน {counts['distinct']} ค่า")
    else:
        line("- ไม่พบ")

    line("ประมาณการจำนวนเจ้าของข้อมูลที่ได้รับผลกระทบ", 13, 18)
    if subjects["no_strong_identifiers"]:
        line("- ไม่พบตัวระบุแบบเข้ม จึงประมาณจำนวนเจ้าของข้อมูลไม่ได้")
    else:
        line(f"- ช่วง {subjects['min']} ถึง {subjects['max']} คน")
    for seg in _wrap(subjects["method"]):
        line(seg, 8, 12)

    line("ชื่อบุคคล เป็นตัวบ่งชี้อ่อน แยกจากช่วงประมาณการด้านบน", 13, 18)
    line(f"- จำนวนชื่อที่ไม่ซ้ำกัน {name_weak['distinct']} ชื่อ")
    for seg in _wrap(name_weak["note"]):
        line(seg, 8, 12)

    line("ข้อมูลอ่อนไหวตามมาตรา 26 (แจ้งธง ไม่ปกปิดอัตโนมัติ)", 13, 18)
    if assessment["section26"]:
        for category, count in assessment["section26"].items():
            line(f"- {category}  พบใน {count} ไฟล์")
    else:
        line("- ไม่พบ")

    line("ระดับความเสี่ยงจากข้อมูลแวดล้อม สูงสุดในเอกสารทั้งหมด", 13, 18)
    line(f"- เกรดสูงสุด {risk['max_grade']}")
    if risk["distribution"]:
        dist_str = "  ".join(f"{grade} {n} ไฟล์" for grade, n in risk["distribution"].items())
        line(f"- การกระจาย {dist_str}", 10, 14)

    line("รายละเอียดต่อไฟล์", 13, 18)
    for row in assessment["file_rows"]:
        total_entities = sum(row["type_counts"].values())
        review_flag = "ต้องตรวจทานโดยมนุษย์" if row["human_review"] else "ไม่ต้องตรวจทานเพิ่ม"
        line(
            f"- {row['basename']}  ชนิดไฟล์ {row['source_type']}  พบ {total_entities} รายการ  "
            f"เกรด {row['risk_grade']}  {review_flag}",
            9,
            13,
        )

    line("สภาพแวดล้อมที่ใช้ประมวลผล", 13, 18)
    line(f"- เครื่องมือรู้จำชื่อเฉพาะ  {environment['ner_engine']}")
    line(f"- ไลบรารีตรวจจับ  {environment.get('detector_version', 'unknown')}", dy=22)

    y = min(y, 150)
    for i, note in enumerate(_NOTES):
        line(note, 12 if i == 0 else 8, 18 if i == 0 else 12)

    c.showPage()
    c.save()

    Path(output_path).write_bytes(buf.getvalue())
