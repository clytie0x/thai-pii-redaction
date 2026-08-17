# Deploy design v3 — AIFT team08 production web (2026-08-13)

> **Historical design record.** Current production deployment and application
> API guidance is maintained in
> [`HOSTED-3-DEPLOY-API-GUIDE.md`](HOSTED-3-DEPLOY-API-GUIDE.md). Route counts,
> service topology, version and runtime identity in this file must not be used
> as current status unless the current guide explicitly incorporates them.

ฉบับนี้ **แทนที่** design ก่อน public-web productionization โดยรักษา port
แยกและ 16-route contract เดิม แต่เปลี่ยน hosted runtime ให้ตรง capability ที่
เปิดใช้จริง:

1. **repo พอร์ตแยก** (repo นี้) — ไฟล์ deploy ไม่อยู่ใน repo หลักอีกต่อไป
   ดังนั้นงาน v1 เรื่อง `docker-compose.deploy.yml`, `.gitlab-ci.yml` ใน repo
   หลัก และการแก้ `tests/test_workflow_pins.py` ถูกยกเลิกทั้งหมด
2. **OCR ไม่อยู่ใน hosted image** — internal source code ยังอยู่ใน vendored
   slice เพื่อรักษา upstream compatibility แต่ public aliases คืน fixed 404 และ
   image ไม่ติดตั้ง/prewarm Paddle OCR dependency ที่ไม่สามารถเปิดใช้ใน resource
   envelope นี้

มติ hosted release แรก (8 ส.ค. 2569): เก็บ implementation ข้างต้นไว้ภายใน
core แต่พัก public PDF/OCR จาก nginx และ frontend หลัง exact profile ชนเพดาน
6 GiB เส้น `/redact-pdf` ทั้งสอง alias ต้องคืน proxy-level 404 การเปิดใหม่ต้อง
ผ่าน correctness/provenance/timeout/resource acceptance แยกต่างหาก

มติ provider: ไม่มี provider จำลองบน deployment
(`AIGUARD_PROVIDERS=tokenmind` เท่านั้น), ไม่มีเดโมสำรอง — มาตรฐานการเทส
ระดับ service, พื้นผิว API เป็น stateless + เดโมเท่านั้น

## สถาปัตยกรรม

สาม service (ดู `docker-compose.yml` เป็น source of truth):
`web` (nginx static :3000 → 127.0.0.1:20070) / `api` (nginx :8000 →
127.0.0.1:20071 — เติม `/api` กลับ, ถือ key, rate limit, log noquery,
allowlist แบบ `location =` รายตัว, `/v1/*` เป็น alias ที่เป็นสัญญาสาธารณะ) /
`core` (FastAPI text/report runtime, ไม่ publish; PDF-redaction/OCR route ไม่ถูก
public proxy expose)

การแก้ปัญหาที่ v1 วิเคราะห์ไว้ยังใช้ทั้งหมด: proxy แพลตฟอร์มตัด `/api` →
nginx เติมกลับ (ไม่มี double-mount router — พิสูจน์แล้วว่าเปิดช่องโหว่),
`TrustedHostMiddleware` อ่านจาก `AIGUARD_ALLOWED_HOSTS`, compose fail-loud
เรื่อง `APP_AIGUARD_API_KEY`

ต่างจาก v1 ตามรีวิว (Codex 28 ก.ค.):
- `location =` รายตัว ห้าม prefix กว้าง (กัน route ภายในโผล่)
- ประกาศ `server_name` เพื่อให้ rate-limit key (`$server_name`) ไม่ว่าง
- `client_max_body_size` 128k สำหรับ public text surface และ 8k สำหรับ login;
  ไม่มี public upload route
- `Cache-Control: no-store` ทุก response
- audit ออก stdout (`AIGUARD_AUDIT_STDOUT=1`) แทน bind mount ไฟล์โตไม่จำกัด
  → ไม่มี bind mount เลยทั้ง compose และเห็นใน Dozzle จริง
- `UVICORN_WORKERS=1` จนกว่าจะวัด (โมเดล cache ต่อโปรเซส)
- acceptance เป็น stage แยกหลัง deploy ใน `.gitlab-ci.yml`; deploy,
  acceptance และ ops schedule เฉพาะ UI-created pipeline บน protected `main`
  ส่วนทุก branch/MR และ ordinary push รวม protected `main` มี check-only
  pipeline ที่ไม่ deploy
- ทุก job inherit runner tag `team-08`; tag จำกัด scheduling แต่ไม่แทน
  daemon isolation Participant Guide ไม่กำหนด Protected runner; การไม่มี flag
  นี้ไม่ใช่ publication blocker เพียงลำพัง แต่ยังต้องขอ platform evidence เรื่อง
  project scope/daemon isolation
- proxy errors 413/429/502/504 เป็น fixed value-free JSON; roundtrip เท่านั้น
  ใช้ read timeout 200 วินาทีให้ครอบ shared core policy 3×60 + backoff 1/2
  โดย nginx ไม่มี retry layer
- `/health` เป็น liveness ตาม platform contract ไม่ใช่ live-provider readiness
- rate/cost control ไม่พึ่ง organizer client-IP forwarding: public/auth/work
  มี global lane และ valid session cookie เป็น fairness key เสริม ส่วน Safe AI
  มี global 6/min + caller 2/min และ concurrency global 2/caller 1
- application logs ไม่เก็บ client IP/target/query/body; rate key อยู่เฉพาะ
  nginx shared memory และ X-Forwarded-For ไม่ส่งต่อเข้า core
- session authority ใช้ process-local SHA-256 fingerprint สูงสุด 256 ค่า;
  logout revoke และ process restart invalidate session เดิม ไม่มี user database
- web/api/core เป็น read-only/no-new-privileges/PID bounded; core cap-drop all,
  tmpfs 128 MiB, memory 2 GiB และ model tree ผ่าน exact digest check
- health probe ที่ล้มต่อเนื่อง 3 ครั้งสั่ง process exit ให้ Docker restart;
  deploy เก็บ exact previous image/Compose set และ rollback เมื่อ candidate
  post-mutation gate ล้ม
- edge request ที่มี `X-Forwarded-Proto: http` คืน fixed-host 308 โดยไม่สะท้อน
  query/Host และ HTTPS responses มี HSTS; real public edge เป็น mandatory
  acceptance เพราะ source config อย่างเดียวพิสูจน์ organizer routing ไม่ได้

## เพดานบน deployment (env ใน compose)

ข้อความ 20,000 ตัวอักษร (`AIGUARD_MAX_TEXT_CHARS`), request body 128 KiB,
public 30/s, auth 10/min, work 20/s global + 30/min/caller และ Safe AI
6/min global + 2/min/caller พร้อม concurrency 2/1 ส่วน PDF/OCR ไม่ใช่ public
capability

## สิ่งที่ v1 ถามผู้จัดแล้วยังต้องรอคำตอบ

project scope/daemon isolation ของ runner ที่มี tag `team-08` — คู่มือ
ไม่กำหนด Protected flag และ tag ถูก pin ใน `.gitlab-ci.yml` แล้วแต่คำถามเรื่อง
สิทธิ์ระดับ platform ยังต้องให้ผู้จัดยืนยัน
certificate renewal, host disk/watchdog/alerting และ edge metadata retention
ยังเป็น platform evidence ที่ repository อ้างแทนไม่ได้ `/data/hack` ตัดทิ้ง
(ไม่ใช้ bind mount แล้ว)
