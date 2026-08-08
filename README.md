# AI Guard — AI for Thai deployment (team08)

พอร์ตสำหรับ deploy บนแพลตฟอร์ม AI for Thai Service Onboarding 2026 ของ
[AI Guard](https://github.com/Teerapat-Vatpitak/thai-pii-redaction) —
เครื่องมือตรวจจับ ปกปิด และทาดำข้อมูลส่วนบุคคลภาษาไทย (Apache-2.0)

repo หลักบน GitHub คือผลิตภัณฑ์ local-first (extension / desktop / CLI /
Office add-in) และไม่เปลี่ยนบทบาท — repo นี้คือ "เปลือก service" สำหรับ
โครงการนี้โดยเฉพาะ

รูปแบบ deployment เทียบกับ
[Participant Guide](https://app.notion.com/p/PARTICIPANT-GUIDE_1-3a7488d61198800fb15fdcf8b40e9afe)
ทางการอีกครั้งเมื่อ 7 ส.ค. 2569: `team08`, frontend/API ports
`20070/20071`, prefix stripping,
unprefixed `/health`, template-derived GitLab CI, per-service limits,
`50m` × 3 log rotation, masked application variables และ no-SSH ops ตรงกับ shell นี้
ในระดับ config ส่วน runner/platform จริงยังไม่เคยรัน

## โครง

| ส่วน | คืออะไร |
|---|---|
| `core/` | vendored slice ของ repo หลักที่ pin commit `44ef30b` (คัดลอกตาม `sync/PORT_MANIFEST.json` — commit + SHA-256 ต่อไฟล์) + port-owned stateless auth wrapper + Dockerfile ที่เพิ่มชั้น OCR |
| `api/` | nginx ตัวกลาง: เติม `/api` prefix ที่ proxy ของแพลตฟอร์มตัดออก, คง `/v1` aliases, inject contract 2 + internal core key เฉพาะ business route, rate limit และ log แบบไม่มี query string |
| `web/` | หน้า product สาม workflow: Privacy Scan, Safe AI และ PDPA Report (static, เรียก API แบบ same-origin) |
| `sync/` | สคริปต์ sync จาก upstream + manifest — `--check` รันใน CI ทุกครั้ง |

## Trust boundary (พูดตรง ๆ)

- เส้นทางนี้ **stateless**: เซิร์ฟเวอร์ detect → mask → เรียก LLM → restore
  จบในคำขอเดียว literal mapping อยู่ในหน่วยความจำชั่วคราวและไม่ถูกส่งออก
  เป็น mapping DTO ไม่มี vault หรือ session ข้ามคำขอ Response ใช้ strict
  HTTP-v2 projection: คืนจำนวน/ชนิดและสถานะความปลอดภัย แต่ไม่คืน mapping,
  token/original pair หรือ token-bearing entity projection
- ข้อความต้นฉบับของผู้เรียกวิ่งผ่าน reverse proxy และเซิร์ฟเวอร์ของทีมบน
  โครงสร้าง NECTEC ก่อนถูกปกปิด เฉพาะข้อความที่ผ่านการปกปิดและตรวจซ้ำแล้ว
  จึงถูกส่งต่อไปยัง LLM ปลายทาง (`thaillm-8b` ที่
  tokenmind.pathumma.in.th)
- ข้อมูลที่ปกปิดด้วย pseudonymization **ยังเป็นข้อมูลส่วนบุคคลตาม PDPA**
  (ไม่ใช่ anonymization) — เอกสารทุกชิ้นของโปรเจกต์นี้ไม่เคลมเกินจากนี้
- config log ทุกชั้นไม่บันทึกเนื้อหาผู้ใช้ query string หรือ request target;
  audit ของ core เป็น JSONL ที่มีแต่ counts/flags/เวลาออกทาง stdout
  exact local candidate ผ่าน runtime synthetic-PII/secret/cookie/body scan
  ในเครื่องแล้ว
  ทั้ง access log และ nginx rate-limit error path ส่วน log ที่แพลตฟอร์มเห็นจริง
  ยังต้องตรวจหลัง deploy
- provider บน deployment นี้มีตัวเดียวคือ `tokenmind` — ไม่มีโหมดจำลอง
  (`fake` ใช้ได้เฉพาะเทสในเครื่องผ่าน compose override)
- หน้า static และ health เป็น public แต่ business API ทุกเส้นต้อง login ด้วย
  access code เพื่อรับ signed cookie อายุ 30 นาทีแบบ
  `Secure`/`HttpOnly`/`SameSite=Strict` โค้ด frontend ไม่บันทึก code ลง
  browser storage และอ่าน cookie ไม่ได้
  และ internal `AIGUARD_API_KEY`/provider key ยังอยู่คนละ trust boundary
  โดย startup ปฏิเสธการใช้ secret ซ้ำกัน Rate limit เป็น
  defense-in-depth ไม่ใช่ identity ระบบนี้เป็น shared admission gate ไม่ใช่
  per-user account ([ADR](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/blob/main/docs/decisions/2026-08-07-aift-caller-authentication.md))

## พื้นผิว API สาธารณะ

public proxy เปิดแบบ exact-match รวม **16 routes**: 8 เส้นทางด้านล่างและ
alias `/v1` ของแต่ละเส้นทางเท่านั้น

เมื่อ candidate ผ่าน recertification และได้รับอนุญาตให้ deploy ผู้เรียกภายนอก
จะใช้ `https://team08.aiforthai.in.th/api/v1/...` (path ไม่มี `/v1`
ใช้ได้เหมือนกัน — คงไว้ให้ healthcheck ของแพลตฟอร์ม)

| Endpoint | ทำอะไร |
|---|---|
| `GET /api/v1/health` | สถานะบริการ |
| `POST /api/v1/auth/login` | แลก access code เป็น signed cookie อายุ 30 นาที |
| `POST /api/v1/auth/logout` | ล้าง cookie ฝั่ง browser |
| `POST /api/v1/detect` | ตรวจจับ PII คืน offsets (ไม่มี session) |
| `POST /api/v1/guard` | สแกน prompt injection ไทย/อังกฤษ (เตือน ไม่บล็อก) |
| `POST /api/v1/roundtrip` | mask → thaillm-8b → restore ในคำขอเดียว (`provider` ต้องส่ง `"tokenmind"`) |
| `POST /api/v1/analyze-report` | รายงานความเสี่ยง PDPA เป็น PDF ภาษาไทย |

เพดาน config สาธารณะปัจจุบัน: ข้อความ ≤ 20,000 ตัวอักษร และอัตรารวม
10 req/s (เกิน → 429)

nginx คืน fixed value-free JSON สำหรับ 413/429/502/504 และไม่ส่ง upstream
error body ต่อสู่ผู้เรียก `/roundtrip` สอง alias ใช้ read timeout 200 วินาที
ให้ครอบ application policy สูงสุด 3×60 วินาที + backoff 1/2 วินาทีโดยไม่เพิ่ม
retry layer ที่ proxy ส่วน `/health` เป็น liveness เท่านั้น ไม่โทร provider

core ยังเก็บ implementation PDF/OCR ไว้ภายใน แต่ `/redact-pdf` และ
`/v1/redact-pdf` ถูก proxy ปฏิเสธด้วย fixed 404 และไม่มี workflow ในหน้าเว็บ
ความสามารถนี้ไม่อยู่ใน hosted release แรก OCR ยังไม่ production-ready บน
AI for Thai การเปิดใหม่ต้องมี correctness, provenance, timeout และ resource
acceptance แยกต่างหาก หลักฐาน OCR เก่าใน `docs/evidence/` เป็นประวัติการทดลอง
ไม่ใช่คำรับรองของ public deployment ปัจจุบัน

หมุด `44ef30b` รวม shared provider orchestration (สูงสุด 3 attempts,
60 วินาทีต่อ attempt, backoff 1/2 วินาที), Tokenmind แบบหนึ่ง network request
ต่อ `.complete()`, fresh outbound-policy scan ก่อน I/O ทุก attempt และ exact
PDF source intervals แบบ fail-closed หมุดนี้อยู่ก่อน Native Broker และไม่มี
การนำ native/desktop/extension/Office/IPC implementation ใหม่เข้ามาใน port

endpoint ที่มี session (`/sanitize`, `/reidentify`) **ไม่เปิด**บน deployment นี้
โดยตั้งใจ — ความต่อเนื่องข้ามคำขอโดยไม่มี state ฝั่งเซิร์ฟเวอร์เป็นงานคลื่นถัดไป
(caller salt)

path `/v1` เป็น public alias ของ port นี้ Requests ของ business route ใช้ shape
เดิมที่หน้าเว็บต้องการ แต่ nginx ยืนยัน HTTP contract 2 กับ shared core และ
response ใช้ projection ที่ลดข้อมูลแล้ว (`X-AIGuard-Contract-Version: 2`)

## รัน/เทสในเครื่อง

```bash
export APP_AIGUARD_API_KEY='สุ่มแยกอย่างน้อย-16-ไบต์'
export APP_AIFT_ACCESS_CODE='สุ่มอย่างน้อย-16-ไบต์'
export APP_AIFT_COOKIE_SIGNING_KEY='สุ่มแยกอย่างน้อย-32-ไบต์'
export APP_TOKENMIND_API_KEY=sk-...   # เว้นได้; ถ้าตั้งต้องแยกจากสามค่าแรก
docker compose -p team08 up -d --build
curl -fsS http://127.0.0.1:20071/health
```

หมายเหตุ dev: business request ต้อง login ก่อน nginx จึงส่งต่อไปยัง port-owned
auth wrapper จากนั้น nginx เป็นผู้ inject contract/core key ฝั่ง browser ห้าม
ส่งหรือรู้ `X-AIGuard-Key`

sync จาก upstream (ทำจาก checkout ที่สะอาดเท่านั้น):

```bash
python sync/sync_from_upstream.py --from ../thai-pii-redaction
python sync/sync_from_upstream.py --check
```

## ซ้อม pipeline ก่อน push จริง

`.gitlab-ci.yml` รันบน `docker:27.3.1` ที่ pin ด้วย digest ซึ่ง shell คือ BusyBox ash ไม่ใช่ bash
(`apk add bash` ใน `before_script` เปลี่ยนไม่ได้ เพราะ runner เลือก shell ตอน
เริ่ม container) ของที่พิสูจน์บน Windows ด้วย venv จึงไม่ได้พิสูจน์สิ่งที่ CI
จะเจอ `tests/run_ci_local.py` ปิดช่องนั้นด้วยการรัน job จริงในอิมเมจจริง

```bash
python tests/run_ci_local.py --job check      # เร็ว ไม่ต้องมี secret
python tests/run_ci_local.py --all            # check + deploy + acceptance
python tests/run_ci_local.py --job deploy --cold   # จับเวลา build เย็น (ทำเป็นอย่างสุดท้าย)
```

`deploy` กับ `acceptance` ต้องมี `APP_AIGUARD_API_KEY`,
`APP_AIFT_ACCESS_CODE`, `APP_AIFT_COOKIE_SIGNING_KEY` และ
`APP_TOKENMIND_API_KEY` ใน environment ของเครื่อง (ชื่อเดียวกับ CI/CD
Variables ของ GitLab) ค่าไม่ถูกพิมพ์ออกและถูกแทนที่ก่อนเขียนไฟล์ผลลัพธ์เสมอ

ตัวจำลองเป็นการประมาณ ไม่ใช่ runner จริง ความต่างที่รู้ตัวอยู่ใน docstring
ของสคริปต์ ส่วน `tests/nginx_contract.py` ถูกต่อไว้ใน check stage และจะรันบน
runner จริงหลัง owner อนุญาต push หลักฐานวันนี้ยังเป็น local เท่านั้น

release-content commit `71c20b37b1bf2be8f34b67294bc75137931ad3cb` ผ่าน exact local
BusyBox `check` 25.7 วินาที, no-cache build สาม image 230.8 วินาที,
provider-free/fake acceptance + log/rate-limit/restart 28.7 วินาที และ
BusyBox `deploy` simulation 63.5 วินาที รายละเอียดอยู่ที่
`docs/evidence/2026-08-08-local-release-candidate.md` ส่วน GitLab runner,
AI for Thai platform และ live Tokenmind ยังไม่เคยรันและยังอ้างว่าผ่านไม่ได้

CI และตัวจำลอง local ส่งต่อเฉพาะชื่อตัวแปรสี่ตัวข้างต้นผ่าน temporary env file
สิทธิ์จำกัด ค่า access code/cookie/secret ที่ใช้ acceptance อยู่ใน process
memory และไม่ถูกใส่ใน child-process argv ส่วน Docker build context ทั้งสามมี
`.dockerignore` แยก และ core image ใช้ explicit `COPY` allowlist

## Deploy

push ขึ้น `main` → pipeline `check` (กติกา compose + vendored integrity +
สัญญาของ nginx proxy) →
`deploy` (build + up + รอ healthcheck) → `acceptance` (ยิง PII สังเคราะห์ผ่าน
ทั้งสาย พิสูจน์ auth, mask ขาออก, minimized response, allowlist และ log) → manual ops
(logs/ps/restart) ใช้แทน SSH ไม่มี job รับคำสั่ง shell ตามอำเภอใจ

config ที่เช็กอินจะ schedule organizer pipeline เฉพาะ protected `main` แต่
branch สามารถแก้ไฟล์ CI ของตัวเองได้ จึงไม่ใช่ isolation boundary ห้าม push
จนกว่า staff จะยืนยันว่า production-capable runner เป็น **Protected runner**
ที่รับเฉพาะ protected refs หรือจัด isolated branch daemon/runner แยก

Secrets ตั้งใน GitLab Settings → CI/CD → Variables เป็น **Protected + Masked**
และ environment scope `team08`; protect branch `main` ก่อน push:
`APP_AIGUARD_API_KEY`, `APP_AIFT_ACCESS_CODE`,
`APP_AIFT_COOKIE_SIGNING_KEY`, `APP_TOKENMIND_API_KEY`
