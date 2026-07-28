# สถานะงาน ณ จุด compact (29 ก.ค. 2569 ~00:30)

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

## สถานะรันไทม์ตอนนี้ (สำคัญ — ต้องคืนก่อนเทสต่อ)

- stack `-p team08` รันอยู่ แต่ **core ถูก recreate แบบไม่มี tokenmind key** (สภาพเทส ช.2)
  คืนด้วย: `cd C:\Users\teera\dev\aiguard-aift; $env:APP_AIGUARD_API_KEY='local-dev-key';
  $env:APP_TOKENMIND_API_KEY=$env:TOKENMIND_API_KEY; docker compose -p team08 up -d core`

## เหลือ (ตามลำดับ)

1. **ซ soak**: (ก) recreate core ด้วย `-f docker-compose.yml -f tests/docker-compose.soak-override.yml`
   (เพิ่ม fake เฉพาะเทส) → `SOAK_PROVIDER=fake python tests/smoke.py --soak` (10 นาที 8 สาย
   ต้องไม่มี 5xx, มี 429 ตาม limit, log ไม่มี PII) (ข) soak เบากับ tokenmind จริง
   (~2 สาย 2 นาที — มารยาทต่อ gateway ผู้จัด) (ค) restart recovery อยู่ใน --soak แล้ว
   (ง) เสร็จแล้ว recreate core กลับ config deployment (ไม่มี override)
2. commit ค้าง: tests/smoke.py (SOAK_PROVIDER), tests/docker-compose.soak-override.yml,
   docs/evidence/, STATE.md
3. **ปิดเฟส (task 16)**: อัปเดต evidence สรุป, ฝั่ง upstream — ADR เลข tokenmind detector
   (F2 0.951, report `benchmark/reports/llm-tokenmind-thaillm8b-gold-v4.json`) +
   อัปเดต `docs/platform/ai-for-thai.md` / `docs/project-status.md` / ROADMAP ชี้ port repo
   (ทำบน branch ใหม่หลัง #101 merge), อัปเดต handoff memory
4. รายงานเจ้าของ: ผลเฟส + คำตอบแบบสำรวจ (รอเจ้าของกรอก/ส่งเอง) + ให้ merge PR #101
   + การตัดสินใจช่อง ASR

## กติกาที่ห้ามลืม

- Codex ถามเฉพาะเมื่อเจ้าของสั่ง (memory: codex-only-on-command)
- ไม่มี provider จำลองบน deployment / ไม่มีเดโมสำรอง — service จริงเท่านั้น
- pseudonymized-มี-vault ยังเป็นข้อมูลส่วนบุคคล — ห้ามเคลมเกิน
- ห้ามเคลมสาธารณะ "benchmark เดียวของไทย"
- deploy ขึ้น GitLab = รอคำสั่งเจ้าของเท่านั้น (สร้าง project ใน group team-08 ได้เอง
  เมื่อสั่ง — สิทธิ์ Maintainer มีแล้ว)
