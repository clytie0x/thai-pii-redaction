# ผล checklist local (Docker stack `-p team08`) — 28-29 ก.ค. 2569

Stack: web (20070) / api-nginx (20071) / core — image `team08-core` (OCR baked).
Raw output อยู่ `tests/out/*.json` (gitignored, local เท่านั้น) — ไฟล์นี้คือสรุปถาวร.
PII ที่ใช้ทดสอบเป็นข้อมูลสังเคราะห์ล้วน.

## ก-ฌ (smoke ปกติ) — ผ่านครบ

จาก `smoke-20260728T170908Z.json`:

- **ก health** — api `/health` 200 + container `team08-api-1` healthy
- **ข roundtrip tokenmind จริง** — 200, ไม่มี PII ดิบขาออก, restore ถูก, warnings ว่าง
- **ค noquery log** — ยิง `?q=SECRETQUERYMARKER` แล้ว marker ไม่โผล่ใน log ของ api (log_format noquery ตัด query string)
- **ง allowlist 404** — `/sanitize /reidentify /docs /openapi.json /api/sanitize` → 404 จาก nginx
- **จ webpage** — 20070 ตอบ 200, มีฉากครบ (roundtrip/redact-pdf/analyze-report), 40,783 bytes
- **ฉ vendored check** — `sync_from_upstream.py --check` ผ่าน (vendored slice ตรง manifest)
- **ฌ OCR ใน container** — PDF hybrid สังเคราะห์ → source_type `pdf_hybrid`, 2 entities, ocr_confidence 0.993, human_review false, 95.4s (โมเดล OCR อยู่ใน image, container ไม่มี egress)

## ช failure modes (manual) — ผ่าน

- **ช.1** ไม่ตั้ง `APP_AIGUARD_API_KEY` → `docker compose config` fail-loud ตั้งแต่ boot (`${APP_AIGUARD_API_KEY:?}`)
- **ช.2** ถอด `APP_TOKENMIND_API_KEY` → `/v1/roundtrip` ตอบ 503 "TOKENMIND_API_KEY is not set" ชัดเจน (ไม่ล่มทั้ง stack, ไม่ degrade ไป fake)

## ซ soak ระดับ service — ผ่านครบ (exit gate ROADMAP Track B)

harness `tests/smoke.py --soak` (env knob SOAK_PROVIDER/SOAK_WORKERS/SOAK_SECONDS/SOAK_SKIP_RESTART).

| ส่วน | พารามิเตอร์ | ok | 429 | 5xx | err | ผล |
|---|---|---|---|---|---|---|
| soak หลัก | fake, 8 สาย, 600s | 5465 | 0 | 0 | 0 | ไม่ crash ไม่ 5xx ต่อเนื่อง 10 นาที |
| restart recovery | `docker compose restart` กลางคัน | — | — | — | — | กลับ healthy เองใน <180s |
| limit verification | fake, 24 สาย, 30s | 195 | 124 | 0 | 0 | เกินเพดาน nginx คืน 429 ไม่ใช่ 500/crash |
| soak เบา (provider จริง) | tokenmind, 2 สาย, 120s | 222 | 0 | 0 | 0 | provider จริงเสถียร |

- soak หลัก fake ~9.1 req/s ต่ำกว่าเพดาน 10r/s เล็กน้อย จึงไม่ชน limit เอง — จึงเพิ่ม limit verification (24 สาย) ต่างหากเพื่อพิสูจน์ว่า `limit_conn`/`limit_req` คืน 429 ตอน overload ไม่ใช่ error ฝั่งเรา
- soak เบา tokenmind ใช้ 2 สาย 120s (มารยาทต่อ gateway ผู้จัด — ไม่ยิงของจริง ~2,000 ครั้ง 10 นาที); restart recovery พิสูจน์ครบแล้วในรอบ fake จึง skip
- **log ไม่มี PII** — หลัง soak รวม ~5,900 roundtrip: core 477 บรรทัด + api 10,956 บรรทัด สแกนหา synthetic PII (ชื่อ/เบอร์/ข้อความ restore) = 0 hit ทั้งคู่ (VAULT-4 + noquery ยืนยัน)

## สรุป

checklist ก-ฌ + ช + ซ ผ่านครบบน Docker จริงในเครื่อง — ตรงนิยาม "พร้อมเป็น service รอคำสั่ง deploy" ของเฟส local (ยังไม่ push GitLab, รอเจ้าของสั่ง). Stack ปิดท้ายอยู่ config deployment (core `AIGUARD_PROVIDERS=tokenmind` + key จริง, ทั้งสาม service healthy).
