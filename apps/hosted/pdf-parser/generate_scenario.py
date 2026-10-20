"""Generate the deterministic fictional Thai résumé used by Hosted 3.0 tests."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

PAPER = HexColor("#F3F1EB")
INK = HexColor("#151515")
BLUE = HexColor("#3266A8")
CORAL = HexColor("#D95D4F")
MUTED = HexColor("#667085")


def build(output: Path, font_path: Path) -> str:
    pdfmetrics.registerFont(TTFont("Anuphan", str(font_path)))
    canvas = Canvas(
        str(output),
        pagesize=A4,
        invariant=1,
        pageCompression=1,
        pdfVersion=(1, 7),
    )
    width, height = A4
    canvas.setTitle("AI Guard fictional Thai resume scenario")
    canvas.setAuthor("AI Guard")
    canvas.setCreator("AI Guard deterministic scenario generator v1")
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setFillColor(BLUE)
    canvas.rect(0, height - 122, width, 122, fill=1, stroke=0)
    canvas.setFillColor(CORAL)
    canvas.rect(48, height - 100, 8, 58, fill=1, stroke=0)
    canvas.setFillColor(PAPER)
    canvas.setFont("Anuphan", 25)
    canvas.drawString(72, height - 65, "นางสาวกานต์ธิดา สุขใจ")
    canvas.setFont("Anuphan", 12)
    canvas.drawString(72, height - 91, "ตัวอย่างสังเคราะห์สำหรับทดสอบ AI Guard")

    left = 56
    right = 315
    top = height - 158
    canvas.setFillColor(INK)
    canvas.setFont("Anuphan", 14)
    canvas.drawString(left, top, "ข้อมูลติดต่อ")
    canvas.drawString(right, top, "ประสบการณ์ทำงาน")
    canvas.setStrokeColor(BLUE)
    canvas.setLineWidth(1.2)
    canvas.line(left, top - 8, 270, top - 8)
    canvas.line(right, top - 8, width - 52, top - 8)

    canvas.setFillColor(INK)
    canvas.setFont("Anuphan", 11)
    left_lines = [
        "อีเมล: kanthida.s@example.com",
        "โทรศัพท์: 081-234-5678",
        "ที่อยู่: 88/12 ถนนสุขุมวิท",
        "แขวงพระโขนง เขตคลองเตย",
        "กรุงเทพมหานคร 10110",
        "วันเกิด: 14 กุมภาพันธ์ 2540",
        "",
        "การศึกษา",
        "วิทยาศาสตรบัณฑิต สาขาสถิติ",
        "มหาวิทยาลัยตัวอย่าง พ.ศ. 2562",
        "",
        "ทักษะ",
        "Python · SQL · การวิเคราะห์ข้อมูล",
        "การสื่อสารภาษาไทยและอังกฤษ",
        "การออกแบบรายงานเชิงธุรกิจ",
    ]
    right_lines = [
        "บริษัท สมมติ ดาต้า จำกัด · 2565–ปัจจุบัน",
        "วิเคราะห์ข้อมูลยอดขายและพฤติกรรมลูกค้า",
        "สร้างรายงานสำหรับทีมบริหารประจำสัปดาห์",
        "ปรับปรุงขั้นตอนตรวจคุณภาพข้อมูลภายในทีม",
        "",
        "บริษัท ตัวอย่าง รีเสิร์ช จำกัด · 2562–2565",
        "เตรียมชุดข้อมูลสำหรับงานวิจัยตลาด",
        "ประสานงานกับทีมผลิตภัณฑ์และฝ่ายกฎหมาย",
        "จัดทำคู่มือข้อมูลที่นำกลับมาใช้ซ้ำได้",
        "",
        "ผลงานที่เลือก",
        "ลดเวลาจัดทำรายงานประจำสัปดาห์ลงอย่างชัดเจน",
        "สร้างระบบแจ้งเตือนคุณภาพข้อมูล 12 ประเภท",
        "ฝึกอบรมผู้ใช้งานภายในองค์กร 40 คน",
        "",
        "เอกสารนี้เป็นข้อมูลสมมติ ไม่ใช่บุคคลจริง",
    ]
    leading = 28
    for index in range(max(len(left_lines), len(right_lines))):
        y = top - 38 - index * leading
        if index < len(left_lines) and left_lines[index]:
            canvas.drawString(left, y, left_lines[index])
        if index < len(right_lines) and right_lines[index]:
            canvas.drawString(right, y, right_lines[index])

    canvas.setFillColor(MUTED)
    canvas.setFont("Anuphan", 9)
    canvas.drawString(56, 34, "Synthetic scenario: hr-resume-pdf-structured-v1 · source PDF remains unchanged")
    canvas.save()
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    print(build(args.output, args.font))


if __name__ == "__main__":
    main()
