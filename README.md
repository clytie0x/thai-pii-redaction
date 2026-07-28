# AI Guard — AI for Thai deployment (team08)

พอร์ตสำหรับ deploy บนแพลตฟอร์ม AI for Thai Service Onboarding 2026 ของ
[AI Guard](https://github.com/Teerapat-Vatpitak/thai-pii-redaction) —
เครื่องมือตรวจจับ ปกปิด และทาดำข้อมูลส่วนบุคคลภาษาไทย (Apache-2.0)

repo หลักบน GitHub คือผลิตภัณฑ์ local-first (extension / desktop / CLI /
Office add-in) และไม่เปลี่ยนบทบาท — repo นี้คือ "เปลือก service" สำหรับ
โครงการนี้โดยเฉพาะ

## โครง

| ส่วน | คืออะไร |
|---|---|
| `core/` | vendored slice ของ repo หลัก (คัดลอกตาม `sync/PORT_MANIFEST.json` — commit + SHA-256 ต่อไฟล์) + Dockerfile ที่เพิ่มชั้น OCR (PaddleOCR ไทย, โมเดล bake ลง image) |
| `api/` | nginx ตัวกลาง: เติม `/api` prefix ที่ proxy ของแพลตฟอร์มตัดออก, ถือ service key แล้ว inject `X-AIGuard-Key` (กติกาห้าม key อยู่ฝั่ง browser), rate limit, log แบบไม่มี query string |
| `web/` | หน้า product ห้าฉาก (static, เรียก API แบบ same-origin) |
| `sync/` | สคริปต์ sync จาก upstream + manifest — `--check` รันใน CI ทุกครั้ง |

## Trust boundary (พูดตรง ๆ)

- เส้นทางนี้ **stateless**: เซิร์ฟเวอร์ detect → mask → เรียก LLM → restore
  จบในคำขอเดียว mapping คืนผู้เรียก ไม่มี vault ไม่มี session ไม่เก็บอะไร
- ข้อความของผู้เรียกวิ่งผ่านโครงสร้างของ NECTEC และไปถึง LLM ปลายทาง
  (`thaillm-8b` ที่ tokenmind.pathumma.in.th) ในรูปที่**ปกปิดแล้ว**
- ข้อมูลที่ปกปิดด้วย pseudonymization **ยังเป็นข้อมูลส่วนบุคคลตาม PDPA**
  (ไม่ใช่ anonymization) — เอกสารทุกชิ้นของโปรเจกต์นี้ไม่เคลมเกินจากนี้
- log ทุกชั้นไม่มีเนื้อหาผู้ใช้: nginx ตัด query string (`$uri` เท่านั้น),
  audit ของ core เป็น JSONL ที่มีแต่ counts/flags/เวลา ออกทาง stdout
- provider บน deployment นี้มีตัวเดียวคือ `tokenmind` — ไม่มีโหมดจำลอง
  (`fake` ใช้ได้เฉพาะเทสในเครื่องผ่าน compose override)

## พื้นผิว API สาธารณะ

ผู้เรียกภายนอกใช้ `https://team08.aiforthai.in.th/api/v1/...`
(path ไม่มี `/v1` ใช้ได้เหมือนกัน — คงไว้ให้ healthcheck ของแพลตฟอร์ม)

| Endpoint | ทำอะไร |
|---|---|
| `GET /api/v1/health` | สถานะบริการ |
| `POST /api/v1/detect` | ตรวจจับ PII คืน offsets (ไม่มี session) |
| `POST /api/v1/guard` | สแกน prompt injection ไทย/อังกฤษ (เตือน ไม่บล็อก) |
| `POST /api/v1/roundtrip` | mask → thaillm-8b → restore ในคำขอเดียว (`provider` ต้องส่ง `"tokenmind"`) |
| `POST /api/v1/redact-pdf` | ทาดำ PDF ระดับ bbox — text layer และเอกสารสแกน (OCR ในตัว) |
| `POST /api/v1/analyze-report` | รายงานความเสี่ยง PDPA เป็น PDF ภาษาไทย |

เพดาน: ข้อความ ≤ 20,000 ตัวอักษร, PDF ≤ 50MB และ ≤ 20 หน้า, อัตรารวม 10 req/s
(เกิน → 429), เส้น PDF ทำพร้อมกันได้ 2 คำขอ

endpoint ที่มี session (`/sanitize`, `/reidentify`) **ไม่เปิด**บน deployment นี้
โดยตั้งใจ — ความต่อเนื่องข้ามคำขอโดยไม่มี state ฝั่งเซิร์ฟเวอร์เป็นงานคลื่นถัดไป
(caller salt)

## รัน/เทสในเครื่อง

```bash
export APP_AIGUARD_API_KEY=dev-key
export APP_TOKENMIND_API_KEY=sk-...   # เว้นได้ /roundtrip จะตอบ 503 ชัดเจน
docker compose -p team08 up -d --build
curl -fsS http://127.0.0.1:20071/health
```

หมายเหตุ dev: หน้าเว็บเรียก `/api/guard` ซึ่งถูก gate ด้วย key — ผ่าน nginx
key ถูก inject ให้อัตโนมัติ ถ้ายิง core ตรง (ไม่ผ่าน nginx) ต้องใส่ header
`X-AIGuard-Key` เอง

sync จาก upstream (ทำจาก checkout ที่สะอาดเท่านั้น):

```bash
python sync/sync_from_upstream.py --from ../thai-pii-redaction
python sync/sync_from_upstream.py --check
```

## Deploy

push ขึ้น `main` → pipeline `check` (กติกา compose + vendored integrity) →
`deploy` (build + up + รอ healthcheck) → `acceptance` (ยิง PII สังเคราะห์ผ่าน
ทั้งสาย พิสูจน์ mask ขาออก/restore ขาเข้า/allowlist) → manual ops
(logs/ps/restart/shell-cmd) ใช้แทน SSH

Secrets ตั้งใน GitLab Settings → CI/CD → Variables (Masked):
`APP_AIGUARD_API_KEY`, `APP_TOKENMIND_API_KEY`
