# สถานะงาน (29 ก.ค. 2569 — soak เฟส local เสร็จ)

แผนแม่บท: `C:\Users\teera\.claude\plans\ai-for-thai-expressive-lighthouse.md`
(อนุมัติแล้ว รวมข้อแก้จาก Codex) — เฟสนี้ = local ทั้งหมด **ยังไม่ deploy จนกว่าเจ้าของสั่ง**

## เสร็จแล้ว (มีหลักฐาน)

- **E0 spike ผ่าน**: paddle cp313 wheel มีจริง, HOME=/opt/ocr-home + chown appuser ใช้ได้,
  offline inference ได้, build เย็น 270s / spike image 2.74GB / RSS 910MB
- **E1-E5 จบ**: สรุป + คำตอบแบบสำรวจอยู่ `docs/evidence/e0-e5-results.md`
  (Text ✓, Vision ✗, GPU ไม่มี, ASR = เจ้าของเลือก — เลขถอดเป็นคำอ่านไทย e4_report.json)
- **Upstream PR #101** (branch `feat/hosted-readiness`, 2 commits ถึง 46c1f9a):
  6 จุด (ALLOWED_HOSTS / PROVIDERS / header fix / audit boot check / AUDIT_STDOUT /
  PDF+text caps + sanitize error) + tests/test_hosted_readiness.py 18 เทส —
  **CI เขียวครบ 11 checks รอเจ้าของ merge**
- **Port repo นี้** ประกอบครบ: sync (SHA-256 manifest + LF normalize + --check ผ่าน,
  vendor จาก upstream commit `46c1f9a`), core/Dockerfile (OCR baked, UVICORN_WORKERS),
  api/ (nginx exact allowlist + /v1 + noquery + key inject, digest จริงตรวจแล้ว),
  web/index.html (ห้าฉาก tokenmind-only), docker-compose.yml, .gitlab-ci.yml
  (check+deploy+acceptance+ops), README, docs/DEPLOY-DESIGN.md (v2), tests/smoke.py
- **Checklist ผ่านแล้ว**: ก ข(roundtrip tokenmind จริงผ่าน nginx) ค ง จ ฉ ฌ(OCR
  ใน container: pdf_hybrid, 2 entities, conf 0.993, 95.4s) — evidence
  `tests/out/smoke-20260728T170908Z.json` — ช.1 (compose fail-loud) ✓,
  ช.2 (ถอด key → 503 "TOKENMIND_API_KEY is not set") ✓
- core image: `team08-core` 2.94GB, build 213s (อุ่นบางส่วนจาก spike layers)

## สถานะรันไทม์ตอนนี้

- stack `-p team08` อยู่ config deployment ครบ: core `AIGUARD_PROVIDERS=tokenmind` + key จริง,
  ทั้งสาม service healthy — พร้อมเป็น service (ไม่มี override ค้าง)
- ถ้าต้องรัน soak fake อีก: `docker compose -p team08 -f docker-compose.yml -f tests/docker-compose.soak-override.yml up -d core`
  แล้วคืนด้วย `docker compose -p team08 up -d core` (ไม่มี -f) — ต้อง set `$env:APP_AIGUARD_API_KEY`
  + `$env:APP_TOKENMIND_API_KEY=$env:TOKENMIND_API_KEY` ก่อนทุกครั้ง

## เหลือ (ตามลำดับ)

1. ~~ซ soak~~ **เสร็จ 29 ก.ค.** — ผลอยู่ `docs/evidence/checklist-results.md`: soak หลัก fake 8 สาย
   10 นาที (5465 ok, 0 5xx/err) + restart recovery + limit verification 24 สาย (124×429, 0 5xx)
   + soak เบา tokenmind 2 สาย 120s (222 ok, 0 5xx) + log 0 PII. checklist ก-ฌ + ช + ซ ผ่านครบ
2. ~~commit port repo~~ (smoke.py knob + `docs/evidence/checklist-results.md` + STATE) — commit รอบนี้
3. **ปิดเฟส (task 16) — ติด PR #101 ยังไม่ merge**: ADR เลข tokenmind detector — verify แล้ว
   report `benchmark/reports/llm-tokenmind-thaillm8b-gold-v4.json` มีจริง R0.960/P0.917/F2 0.951
   gold v4 252 docs / 648 entities, failed 0 + อัปเดต `docs/platform/ai-for-thai.md` /
   `docs/project-status.md` / ROADMAP ชี้ port repo — ทำบน branch ใหม่ **หลัง #101 merge เท่านั้น**
4. รายงานเจ้าของ: ให้ merge PR #101 (unblock task 16) + คำตอบแบบสำรวจ (รอกรอก/ส่งเอง)
   + การตัดสินใจช่อง ASR

## กติกาที่ห้ามลืม

- Codex ถามเฉพาะเมื่อเจ้าของสั่ง (memory: codex-only-on-command)
- ไม่มี provider จำลองบน deployment / ไม่มีเดโมสำรอง — service จริงเท่านั้น
- pseudonymized-มี-vault ยังเป็นข้อมูลส่วนบุคคล — ห้ามเคลมเกิน
- ห้ามเคลมสาธารณะ "benchmark เดียวของไทย"
- deploy ขึ้น GitLab = รอคำสั่งเจ้าของเท่านั้น (สร้าง project ใน group team-08 ได้เอง
  เมื่อสั่ง — สิทธิ์ Maintainer มีแล้ว)
