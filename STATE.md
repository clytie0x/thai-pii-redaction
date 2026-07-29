# สถานะงาน (29 ก.ค. 2569 — พร้อม push ครั้งแรก รอเจ้าของสั่ง)

แผนแม่บท: `C:\Users\teera\.claude\plans\ai-for-thai-expressive-lighthouse.md`
เฟสนี้ = local ทั้งหมด **ยังไม่ deploy จนกว่าเจ้าของสั่ง**
ขั้นตอนของวันจริงอยู่ที่ `docs/DEPLOY-DAY.md`

## เสร็จแล้ว (มีหลักฐาน)

- **E0 spike ผ่าน**: paddle cp313 wheel มีจริง, HOME=/opt/ocr-home + chown appuser ใช้ได้,
  offline inference ได้, build เย็น 270s / spike image 2.74GB / RSS 910MB
- **E1-E5 จบ**: สรุป + คำตอบแบบสำรวจอยู่ `docs/evidence/e0-e5-results.md`
  (Text ✓, Vision ✗, GPU ไม่มี, ASR = เจ้าของเลือก — เลขถอดเป็นคำอ่านไทย e4_report.json)
- **Upstream PR #101 merge แล้ว** (`71b7120`) และ PR #102 (ADR tokenmind + port) ตามมา
- **Port repo นี้** ประกอบครบ: sync (SHA-256 manifest + LF normalize), core/Dockerfile
  (OCR baked, UVICORN_WORKERS), api/ (nginx exact allowlist + /v1 + noquery + key inject),
  web/index.html (ห้าฉาก tokenmind-only), docker-compose.yml, .gitlab-ci.yml, README,
  docs/DEPLOY-DESIGN.md (v2), tests/smoke.py
- **Checklist ก-ฌ + ช + ซ ผ่านครบ** — evidence `docs/evidence/checklist-results.md`
  (soak fake 8 สาย 10 นาที 5465 ok 0 5xx, restart recovery, limit 124×429,
  soak tokenmind 2 สาย 222 ok, log 0 PII)

## เสร็จรอบ 29 ก.ค. เย็น — ปิดช่องว่าง "CI ไม่เคยรันจริง"

หลักฐานเก่าทั้งหมดมาจาก `tests/smoke.py` ที่รันบน Windows ด้วย venv ซึ่งยิงคำสั่ง
**เทียบเท่า** ที่ CI ทำ ไม่ใช่ตัวที่ CI จะรัน ช่องนี้ปิดแล้ว

- **S0 spike** (`tests/out/s0-runner-simulation.json`) socket mount ถึง daemon ของ host ได้
  `--network host` บน Docker Desktop เข้าถึงพอร์ตที่ publish บน 127.0.0.1 ได้
  และ shell ของ job คือ `/bin/busybox` ไม่มี bash
  **ข้อสันนิษฐานในสเปกสองข้อผิด** BusyBox build นี้รองรับ process substitution และ
  `grep -E` รับ `\s` ได้ check stage จึงไม่ต้องเขียนใหม่ (บันทึกไว้แทนที่จะเงียบ)
- **S1 re-sync** หมุดขยับ `46c1f9a` → `00b3ffe` (62 ไฟล์) หมุดเก่าเก่ากว่างานแก้ shaping
  แปลว่า `core/requirements.lock` ไม่มี uharfbuzz และ `/analyze-report` อยู่ใน allowlist
  ถ้า deploy ด้วยหมุดเก่า รายงาน PDPA ที่ผู้ใช้โหลดจะวรรณยุกต์เพี้ยนทั้งฉบับ
- **S2 `tests/nginx_contract.py`** อยู่ใน check stage จริง (ไม่ใช่เครื่องมือ local)
  ยืนยันห้าข้อบน `api/Dockerfile` ตัวจริงกับ stub core ที่สะท้อน path + key กลับมา
  พิสูจน์แล้วว่าจับพังได้ เปลี่ยน `location =` เป็น prefix match แล้ว `/detectx` ทะลุถึง core
  และเทสแดงทั้งสองข้อ
- **S3 `tests/run_ci_local.py`** รัน job จริงในอิมเมจจริง **ผ่านครบสาม job**
  check 12.9s / deploy 167.2s / acceptance 4.7s (ยิง thaillm-8b จริง ด้วย PII สังเคราะห์)
  deploy รอบนี้ยังพิสูจน์ว่า lock ใหม่ build ได้ uharfbuzz ลงในอิมเมจเรียบร้อย

## เหลือ — ทั้งหมดเป็นงานที่ออกนอกเครื่อง เจ้าของทำเอง

1. สร้าง project บน `gitlab.nectec.or.th` ใน group ของทีม
2. ตั้ง CI/CD Variables **ก่อน** push ครั้งแรก `APP_AIGUARD_API_KEY` +
   `APP_TOKENMIND_API_KEY` ติ๊ก Masked ทั้งคู่
3. `git remote add origin ...` แล้ว push `main` (repo นี้ยังไม่มี remote เลย)
4. ดูให้ครบสาม stage ไม่ใช่แค่ deploy เขียว
5. คำตอบแบบสำรวจ + การตัดสินใจช่อง ASR ยังรอกรอก/ส่ง

ลำดับเต็มพร้อมกับดักอยู่ที่ `docs/DEPLOY-DAY.md`

## กติกาที่ห้ามลืม

- ไม่มี provider จำลองบน deployment / ไม่มีเดโมสำรอง — service จริงเท่านั้น
- pseudonymized-มี-vault ยังเป็นข้อมูลส่วนบุคคล — ห้ามเคลมเกิน
- ห้ามเคลมสาธารณะ "benchmark เดียวของไทย"
- deploy ขึ้น GitLab = รอคำสั่งเจ้าของเท่านั้น (สิทธิ์ Maintainer มีแล้ว)
- ตัวเลขเวลาจากเครื่องนี้บอกลำดับความใหญ่ ไม่ใช่คำรับประกันบน runner ของผู้จัด
