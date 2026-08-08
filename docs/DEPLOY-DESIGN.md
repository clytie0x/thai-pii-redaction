# Deploy design v2 — AIFT team08 (2026-07-28)

ฉบับนี้ **แทนที่** `docs/superpowers/specs/2026-07-27-aift-team08-deploy-design.md`
ใน repo หลัก (working doc, gitignored) สองมติที่เปลี่ยนจาก v1:

1. **repo พอร์ตแยก** (repo นี้) — ไฟล์ deploy ไม่อยู่ใน repo หลักอีกต่อไป
   ดังนั้นงาน v1 เรื่อง `docker-compose.deploy.yml`, `.gitlab-ci.yml` ใน repo
   หลัก และการแก้ `tests/test_workflow_pins.py` ถูกยกเลิกทั้งหมด
2. **OCR อยู่ในสโคปของ image/internal core ตามมติเดิม** — v1 ตัด OCR ออกจาก image; เจ้าของกำหนดใหม่ว่า
   เอกสารสแกนต้องใช้ได้จริงบน deployment (พิสูจน์ความเป็นไปได้แล้วใน E0
   spike: build เย็น 270s, image ~2.7GB ส่วน OCR, inference offline ได้,
   RSS peak 910MB)

มติ hosted release แรก (8 ส.ค. 2569): เก็บ implementation ข้างต้นไว้ภายใน
core แต่พัก public PDF/OCR จาก nginx และ frontend หลัง exact profile ชนเพดาน
6 GiB เส้น `/redact-pdf` ทั้งสอง alias ต้องคืน proxy-level 404 การเปิดใหม่ต้อง
ผ่าน correctness/provenance/timeout/resource acceptance แยกต่างหาก

มติเพิ่มเติมของเจ้าของ (28 ก.ค.): ไม่มี provider จำลองบน deployment
(`AIGUARD_PROVIDERS=tokenmind` เท่านั้น), ไม่มีเดโมสำรอง — มาตรฐานการเทส
ระดับ service, พื้นผิว API เป็น stateless + เดโมเท่านั้น

## สถาปัตยกรรม

สาม service (ดู `docker-compose.yml` เป็น source of truth):
`web` (nginx static :3000 → 127.0.0.1:20070) / `api` (nginx :8000 →
127.0.0.1:20071 — เติม `/api` กลับ, ถือ key, rate limit, log noquery,
allowlist แบบ `location =` รายตัว, `/v1/*` เป็น alias ที่เป็นสัญญาสาธารณะ) /
`core` (FastAPI + internal OCR, ไม่ publish; PDF route ไม่ถูก public proxy expose)

การแก้ปัญหาที่ v1 วิเคราะห์ไว้ยังใช้ทั้งหมด: proxy แพลตฟอร์มตัด `/api` →
nginx เติมกลับ (ไม่มี double-mount router — พิสูจน์แล้วว่าเปิดช่องโหว่),
`TrustedHostMiddleware` อ่านจาก `AIGUARD_ALLOWED_HOSTS`, compose fail-loud
เรื่อง `APP_AIGUARD_API_KEY`

ต่างจาก v1 ตามรีวิว (Codex 28 ก.ค.):
- `location =` รายตัว ห้าม prefix กว้าง (กัน route ภายในโผล่)
- ประกาศ `server_name` เพื่อให้ rate-limit key (`$server_name`) ไม่ว่าง
- `client_max_body_size` 1m สำหรับ public text surface; ไม่มี public upload route
- `Cache-Control: no-store` ทุก response
- audit ออก stdout (`AIGUARD_AUDIT_STDOUT=1`) แทน bind mount ไฟล์โตไม่จำกัด
  → ไม่มี bind mount เลยทั้ง compose และเห็นใน Dozzle จริง
- `UVICORN_WORKERS=1` จนกว่าจะวัด (โมเดล cache ต่อโปรเซส)
- acceptance เป็น stage แยกหลัง deploy ใน `.gitlab-ci.yml`

## เพดานบน deployment (env ใน compose)

ข้อความ 20,000 ตัวอักษร (`AIGUARD_MAX_TEXT_CHARS`) และอัตรา 10 req/s รวม
burst 10 ส่วน PDF limits เป็น internal-only และไม่ใช่ public capability

## สิ่งที่ v1 ถามผู้จัดแล้วยังต้องรอคำตอบ

Host header ที่ proxy ส่งเข้า container (เผื่อค่าใน `AIGUARD_ALLOWED_HOSTS`
แล้ว), runner tags (คอมเมนต์ไว้ใน `.gitlab-ci.yml`) — คำถามเรื่องสิทธิ์
`/data/hack` ตัดทิ้ง (ไม่ใช้ bind mount แล้ว)
