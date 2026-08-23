"""The DSAR locate result rendered as a Thai PDF slip.

Whitelist renderer over `DsarResult.to_json_dict()`, which carries no identifier value, document
value, or hash to begin with, so the PII-free property is structural. Method statements are drawn
verbatim from `payload["method"]` so JSON and PDF cannot disagree. Writes the file itself
(`render_dsar_pdf(result_dict, output_path) -> None`), same contract as `render_breach_pdf`.
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

_TITLE = "Amphrang — ผลการค้นหาไฟล์สำหรับคำขอใช้สิทธิของเจ้าของข้อมูล"
_SUBTITLE = "จัดทำเพื่อประกอบการตอบคำขอตาม พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล มาตรา 30"

_NOTES = [
    "ข้อจำกัดและวิธีอ่านผลการค้นหานี้",
    "ผลการค้นหานี้ระบุเฉพาะไฟล์ที่พบ ไม่ใช่บทสรุปว่าคำขอใช้สิทธิได้รับการตอบสนองครบถ้วนแล้ว "
    "ผู้ควบคุมข้อมูลต้องให้บริการเนื้อหาจากไฟล์ที่พบเองต่อไป",
    "เครื่องมือนี้ไม่คัดลอก ไม่ยกข้อความ และไม่แสดงเนื้อหาของเอกสารใด ๆ การค้นหาคือหน้าที่ทั้งหมดของเครื่องมือนี้",
    "ไฟล์ที่ไม่พบว่าตรงกันจะถูกนับรวมในจำนวนทั้งหมดเท่านั้น ไม่ปรากฏเป็นรายการในรายงานนี้",
]


def _wrap(text: str, width: int = 100) -> list[str]:
    """Word-wrap a verbatim paragraph statement; `draw_text` only draws one line."""
    return textwrap.wrap(text, width=width) or [""]


def _type_counts_str(counts: dict) -> str:
    if not counts:
        return "ไม่มี"
    return "  ".join(
        f"{_TYPE_LABELS.get(data_type, data_type)} {n}" for data_type, n in counts.items()
    )


def _occurrence_counts_str(counts: dict) -> str:
    """Like `_type_counts_str` but spelled "N ครั้ง": `matched_identifier_counts` counts
    occurrences, not distinct identifiers, and a plain number read as the latter."""
    if not counts:
        return "ไม่มี"
    return "  ".join(
        f"{_TYPE_LABELS.get(data_type, data_type)} {n} ครั้ง" for data_type, n in counts.items()
    )


def render_dsar_pdf(result_dict: dict, output_path: str | Path) -> None:
    """Draw `result_dict` (a `DsarResult.to_json_dict()` dict) onto an A4 PDF at `output_path`.

    Only type names/counts, basenames, grades, flags, verbatim method statements, version strings,
    and the timestamp reach the canvas. `OSError` from the write propagates uncaught.
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

    files = result_dict["files"]
    subject = result_dict["subject"]
    method = result_dict["method"]
    environment = result_dict["environment"]

    line(_TITLE, 17, 22)
    line(_SUBTITLE, 10, 20)
    line(
        f"ค้นหาเมื่อ {result_dict['assessed_at']}   เวอร์ชันระบบ {environment['product_version']}",
        9,
        22,
    )

    line("ตัวระบุตัวตนที่ผู้ขอข้อมูลให้มา", 13, 18)
    if subject["types"]:
        for data_type, count in subject["types"].items():
            label = _TYPE_LABELS.get(data_type, data_type)
            line(f"- {label}  จำนวน {count} รายการ")
    else:
        line("- ไม่มี")

    line("เอกสารที่ตรวจสอบ", 13, 18)
    line(
        f"- รวม {files['total']} ไฟล์   ตรวจสำเร็จ {files['assessed']} ไฟล์   "
        f"พบไฟล์ที่ตรงกัน {files['matched']} ไฟล์   ล้มเหลว {len(files['failed'])} ไฟล์   "
        f"ข้าม {files['skipped']['count']} ไฟล์"
    )
    for failed in files["failed"]:
        line(f"  - {failed['basename']}  {failed['reason']}", 9, 13)
    for name in files["skipped"]["basenames"]:
        line(f"  - {name}  ข้ามเนื่องจากนามสกุลไฟล์ไม่รองรับ", 9, 13)
    line("", 4, 8)

    line("ไฟล์ที่พบว่าตรงกับผู้ขอข้อมูล", 13, 18)
    matched_files = result_dict["matched_files"]
    if not matched_files:
        line("- ไม่พบไฟล์ที่ตรงกับผู้ขอข้อมูล")
    else:
        for row in matched_files:
            review_flag = "ต้องตรวจทานโดยมนุษย์" if row["human_review"] else "ไม่ต้องตรวจทานเพิ่ม"
            third_party = (
                "อาจมีข้อมูลของบุคคลอื่นปะปน"
                if row["third_party_possible"]
                else "ไม่พบข้อมูลอื่นปะปนเกินตัวระบุที่ตรงกัน"
            )
            weak_note = (
                "ตรงกันเฉพาะชื่อ ต้องยืนยันตัวตนเพิ่มเติม" if row["weak_only"] else "มีตัวระบุที่เข้มกว่าชื่อร่วมด้วย"
            )
            line(
                f"- {row['basename']}  ชนิดไฟล์ {row['source_type']}  "
                f"เกรดความเสี่ยง {row['risk_grade']}  {review_flag}  {third_party}  {weak_note}",
                9,
                13,
            )
            line(
                f"    ตัวระบุที่ตรงกัน  {_occurrence_counts_str(row['matched_identifier_counts'])}",
                8,
                12,
            )
            line(
                f"    ข้อมูลส่วนบุคคลทั้งหมดในไฟล์  {_type_counts_str(row['type_counts'])}",
                8,
                12,
            )

    line("วิธีการจับคู่และข้อจำกัด (ข้อความต้นฉบับ)", 13, 18)
    for statement in (
        method["match"],
        method["ocr_limitation"],
        method["third_party"],
        method["name_weak_match"],
        method["scope"],
    ):
        for seg in _wrap(statement):
            line(seg, 8, 12)
        line("", 4, 6)

    line("สภาพแวดล้อมที่ใช้ประมวลผล", 13, 18)
    line(f"- เครื่องมือรู้จำชื่อเฉพาะ  {environment['ner_engine']}")
    line(f"- ไลบรารีตรวจจับ  {environment.get('detector_version', 'unknown')}", dy=22)

    y = min(y, 150)
    for i, note in enumerate(_NOTES):
        line(note, 12 if i == 0 else 8, 18 if i == 0 else 12)

    c.showPage()
    c.save()

    Path(output_path).write_bytes(buf.getvalue())
