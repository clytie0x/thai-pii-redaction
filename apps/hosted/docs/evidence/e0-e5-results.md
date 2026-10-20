# ผลเฟส 0 (E0-E5) — 28 ก.ค. 2569

## E0 OCR feasibility spike — ผ่าน
- python:3.13-slim (digest เดียวกับ repo) + paddlepaddle==3.2.2 (cp313 manylinux wheel มีจริง) + paddleocr>=3.0
- system libs ที่ต้องมี: libgl1 libglib2.0-0 libgomp1
- กลไก cache: ENV HOME=/opt/ocr-home ทั้ง build+runtime แล้ว chown appuser — โมเดลลง /opt/ocr-home/.paddlex/official_models (PP-OCRv5_server_det, th_PP-OCRv5_mobile_rec, PP-LCNet textline_ori)
- รัน offline (--network none) เป็น appuser: ใช้ cache ไม่โหลดซ้ำ อ่านไทย+เบอร์โทรถูกต้อง
- ตัวเลข: cold build 270s, image 2.74GB (เฉพาะ OCR stack), engine init 12.6s (จ่ายครั้งแรกที่มีคำขอสแกน), predict 9.4s/ภาพบรรทัดเดียว @2cpu, peak RSS 910MB
- นัย: หน้าจริงหลายบรรทัด/หลายหน้าจะช้ากว่านี้ — ต้องวัดใน ฌ; healthcheck start_period ต้องเผื่อ; proxy_read_timeout 120s น่าจะพอแต่ต้องวัด

## E1 — key เห็นโมเดล: ptm-tts-1, ptm-asr-1, thaillm-8b (ไม่มี vision)

## E2 — Text: มีหลักฐานแล้ว (tokenmind detector gold OVERALL R0.960/P0.917/F2 0.951, report llm-tokenmind-thaillm8b-gold-v4.json; roundtrip acceptance 9/9) → ติ๊ก Text

## E3 — GPU: ไม่ต้อง (ADR 2026-07-28-finetuned-ner-results: finetuned F2 0.918 gold/0.914 blind, ~100+ms/doc บน CPU เทียบเกณฑ์ 2s) → ตอบ "ไม่มี"

## E4 — ASR (30 ประโยคสังเคราะห์, TTS ptm-tts-1 → ASR ptm-asr-1 → detect_all)
- NAME: type จับได้ 10/10, ตัวสะกดชื่อรอดเป๊ะ 5/10
- ADDRESS: 3/3
- PHONE 0/8, THAI_ID 0/3, MIXED 0/6 — เหตุ: **ASR ถอดเลขเป็นคำอ่านไทย** (081→"ศูนย์แปดหนึ่ง", ขีด→"ลบ") ข้อมูลรอดเชิงเสียงครบ แต่ detector อ่าน Arabic digits
- ตามเกณฑ์ที่ประกาศไว้ (≥70% ตรวจจับได้) = ไม่ผ่าน out-of-box; ชิ้นที่ขาดคือ Thai spoken-number→digit normalizer ฝั่งเรา (deterministic, งานเล็ก)
- bias ที่บันทึก: เสียง TTS สะอาด = ขอบบนแง่ดี ไม่แทนเสียงจริง; เสียงดิบไปถึง ASR ก่อนการปกปิด (trust boundary)
- ทางเลือกช่อง ASR ในแบบสำรวจ: (ก) ไม่ติ๊ก ตามเกณฑ์เข้ม (ข) ติ๊ก เพื่อพัฒนา voice feature คลื่น 2-3 โดยรู้ว่าต้องทำ normalizer — การตัดสินเป็นของเจ้าของ
- report เต็ม: e4_report.json (โฟลเดอร์นี้)

## E5 — Vision: ทดลองไม่ได้ (key ไม่มีโมเดล vision) + มี PaddleOCR ใน image แล้ว → ไม่ติ๊ก

## สรุปคำตอบแบบสำรวจที่มีหลักฐาน
- ชื่อทีม: ai4thai-team08 (AI Guard)
- บริการ: Text ✓ | Vision ✗ | ASR = เจ้าของเลือก (หลักฐานข้างบน) | TTS ✗ (ไม่มีเคสเดี่ยว)
- มีโมเดลส่วนตัวต้องใช้ GPU: ไม่มี
