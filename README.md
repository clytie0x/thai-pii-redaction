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
unprefixed `/health`, non-main `check`, main-only deploy, per-service limits,
`50m` × 3 log rotation, **Masked** application variables และ no-SSH ops
ตรงกับ shell นี้ในระดับ config ส่วน protected-main gate, protected variables,
runner tag และ stale-SHA checks เป็น AI Guard security hardening เพิ่มเอง
runner #227 ผ่านทั้ง check-only และ production path แล้ว Historical attempt
#35722 เก็บไว้เป็นหลักฐาน defect ของ host-loopback probe และ Pipeline #35727
พิสูจน์ network correction ครั้งแรก ส่วน known-good production rollback ก่อน
Sprint 2 คือ Pipeline #35736 บน exact
`9d38c6753aa0242bc35d09ec3332e90fe3f90079` ซึ่งผ่าน
check/deploy/acceptance, public HTTPS, live Tokenmind, log privacy, resource และ
restart/recovery ครบ Sprint 2 descendant ต้องสร้างหลักฐาน exact-SHA ใหม่

## โครง

| ส่วน | คืออะไร |
|---|---|
| `core/` | vendored slice ของ repo หลักที่ pin commit `44ef30b` (คัดลอกตาม `sync/PORT_MANIFEST.json` — commit + SHA-256 ต่อไฟล์) + port-owned stateless auth wrapper + Dockerfile ที่เพิ่มชั้น OCR |
| `api/` | nginx ตัวกลาง: เติม `/api` prefix ที่ proxy ของแพลตฟอร์มตัดออก, คง `/v1` aliases, inject contract 2 + internal core key เฉพาะ business route, rate limit และ log แบบไม่มี query string |
| `web/` | หน้า product light-theme สาม workflow: Privacy Scan, Safe AI และ PDPA Report พร้อม Guided Demo, Executive Result Summary, Raw-vs-Protected, Sensitive Data Map, Prompt Risk, Protection Receipt, Presenter/fullscreen, entity glossary และ System Evidence (static, same-origin, ไม่มี third-party dependency หรือ persistent browser storage ของเนื้อหาผู้ใช้) |
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
  ในเครื่องแล้ว และ production rollback #35736 ผ่าน retained-log scan บน
  แพลตฟอร์มจริง ทุก descendant ต้องตรวจใหม่ก่อนอ้างหลักฐานเดียวกัน
- provider บน deployment นี้มีตัวเดียวคือ `tokenmind` — ไม่มีโหมดจำลอง
  (`fake` ใช้ได้เฉพาะเทสในเครื่องผ่าน compose override)
- หน้า static และ health เป็น public แต่ business API ทุกเส้นต้อง login ด้วย
  access code เพื่อรับ signed cookie อายุ 30 นาทีแบบ
  `Secure`/`HttpOnly`/`SameSite=Strict` โค้ด frontend ไม่บันทึก code หรือเนื้อหา
  ผู้ใช้ลงพื้นที่จัดเก็บของเบราว์เซอร์ และอ่าน cookie ไม่ได้
  และ internal `AIGUARD_API_KEY`/provider key ยังอยู่คนละ trust boundary
  โดย startup ปฏิเสธการใช้ secret ซ้ำกัน Rate limit เป็น
  defense-in-depth ไม่ใช่ identity ระบบนี้เป็น shared admission gate ไม่ใช่
  per-user account ([ADR](https://github.com/Teerapat-Vatpitak/thai-pii-redaction/blob/main/docs/decisions/2026-08-07-aift-caller-authentication.md))

หน้า hosted demo ใช้ภาษาไทยเป็นหลักและมี scenario gallery สังเคราะห์ห้าบริบท
ข้อมูลตัวอย่างเป็น input เท่านั้น แต่ละชุดมีคำสั่งสรุปเฉพาะบริบทแบบกำหนดตายตัว
เพื่อให้เห็นการกู้คืนในงานจริง การเลือกไม่ส่ง request จนผู้ใช้กด CTA
Guided Demo ร้อยสาม workflow ตามลำดับจริงและหยุดทันทีเมื่อขั้นใดไม่ผ่าน โดย
frontend เรียก `/roundtrip` หนึ่งครั้งต่อรอบ (server อาจ retry provider เดิมตาม
policy ที่จำกัดไว้และไม่มี fallback ไป provider อื่น) Safe AI แสดง
`sanitized_text` เป็นการ์ดกลาง “ข้อความที่ส่งให้ AI จริง” พร้อม Protection
Evidence จาก strict response และจะไม่แสดง `restored_text` จนกว่า
safety/restoration/warnings จะผ่านครบ

Sprint 2 วาง evidence stage หลังผล Safe AI โดยสรุป verdict สำหรับคำขอนั้น,
เทียบ Raw กับ Protected, แสดงแผนที่ตำแหน่งแบบไม่เปิดค่าที่ตรวจพบ, Prompt Risk
แบบ warning-only และ Protection Receipt ที่สร้างใน browser จาก response เดิม
เท่านั้น Receipt ไม่ใช่ลายเซ็น/หลักฐานเข้ารหัส ไม่ใช่ใบรับรอง PDPA และไม่มี
mapping, token/original pair, provider body หรือ request identifier การ์ดเหล่านี้
ไม่เรียก provider เพิ่ม และผูกกับข้อความ/mode ของรอบที่ผ่าน strict gate เท่านั้น

Presenter Mode และ fullscreen เป็นการจัด presentation ด้วย CSS ในหน่วยความจำ
หน้าเว็บ ไม่เรียก API และไม่ persist state เมื่อใช้ข้อความ custom ค่า raw/restored
ถูกซ่อนเป็นค่าเริ่มต้นใน presentation view ผู้ใช้ยังออกจาก fullscreen, reset และ
logout ได้เสมอ หาก request ที่อาจถึง provider ยังไม่ยืนยันผล frontend จะคง
single-flight lock ตาม timeout boundary แทนการเริ่ม request ซ้อนอย่างไม่รู้ชะตา

mode สาธารณะมีเฉพาะ `token` และ `surrogate`: Token เป็น placeholder แบบวงเล็บ
ที่บอกประเภทและสุ่ม namespace ต่อคำขอ จึง audit ง่ายแต่ไม่ใช่ค่าทึบ ส่วน
Surrogate ใช้ข้อมูลสมมุติที่รักษารูปแบบเป็นธรรมชาติมากขึ้นและไม่ได้ปลอดภัยกว่า
โดยอัตโนมัติ ทั้งสองเป็น reversible pseudonymization ไม่ใช่ anonymization
mapping อยู่ชั่วคราวในคำขอเดียวและไม่ถูก projection กลับ
หน้าเว็บ เวลา Privacy Scan, Safe AI, PDPA Report และ Guided Demo เป็น total
elapsed ที่วัดด้วย monotonic browser clock ไม่ใช่ detector/provider/stage
telemetry

PDPA Report แสดง score/grade ที่ endpoint คืนก่อนเปิดปุ่มดาวน์โหลด ประเภทที่
แสดงร่วมกันถูกระบุชัดว่ามาจาก Privacy Scan ของข้อความเดียวกัน เพราะ report
endpoint ไม่คืน breakdown ไฟล์อยู่ใน memory ของหน้าชั่วคราวและถูกล้างเมื่อ
input เปลี่ยน reset logout หรือ session หมดอายุ Health/System Evidence เป็น
liveness + VERSION เท่านั้น ไม่ใช่หลักฐานว่า Tokenmind พร้อม

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
| `GET /api/v1/auth/session` | ตรวจสถานะ signed session โดยไม่คืน cookie หรือ secret |
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

## ซ้อม pipeline และเทียบ Docker-executor network

`.gitlab-ci.yml` รันบน `docker:27.3.1` ที่ pin ด้วย digest ซึ่ง shell คือ BusyBox ash ไม่ใช่ bash
(`apk add bash` ใน `before_script` เปลี่ยนไม่ได้ เพราะ runner เลือก shell ตอน
เริ่ม container) ของที่พิสูจน์บน Windows ด้วย venv จึงไม่ได้พิสูจน์สิ่งที่ CI
จะเจอ `tests/run_ci_local.py` ปิดช่องนั้นด้วยการรัน job จริงในอิมเมจจริง

```bash
python tests/run_ci_local.py --job check      # เร็ว ไม่ต้องมี secret
python tests/run_ci_local.py --job check --gitlab-network  # topology แบบ runner
python tests/run_ci_local.py --all            # check + deploy + acceptance
python tests/run_ci_local.py --job deploy --cold   # จับเวลา build เย็น (ทำเป็นอย่างสุดท้าย)
```

`deploy` กับ `acceptance` ต้องมี `APP_AIGUARD_API_KEY`,
`APP_AIFT_ACCESS_CODE`, `APP_AIFT_COOKIE_SIGNING_KEY` และ
`APP_TOKENMIND_API_KEY` ใน environment ของเครื่อง (ชื่อเดียวกับ CI/CD
Variables ของ GitLab) ค่าไม่ถูกพิมพ์ออกและถูกแทนที่ก่อนเขียนไฟล์ผลลัพธ์เสมอ

ตัวจำลองเป็นการประมาณ ไม่ใช่ runner จริง ความต่างที่รู้ตัวอยู่ใน docstring
ของสคริปต์ `tests/nginx_contract.py` รันบน runner #227 ใน pipeline #35715 และ
#35716 แล้ว ครั้งแรกพบ host-loopback assumption และครั้งที่สองพบว่า friendly
job hostname ไม่ใช่ Docker daemon container identity #35718 พิสูจน์การ resolve
ด้วย GitLab job label จริง Production attempt #35722 พบ assumption เดียวกันใน
deploy/acceptance path หลัง container healthy; correction ใช้ in-container probe
และต่อเฉพาะ acceptance job เข้า Compose network ชั่วคราวด้วย exact labels
Pipeline #35727 พิสูจน์ corrected path ครบ check/deploy/acceptance บน exact
`42476d09a7d80b6920fcf21c0d2ac0d5c6952872`; Pipeline #35736 บน exact
`9d38c6753aa0242bc35d09ec3332e90fe3f90079` คือ known-good production
rollback ที่ใหม่กว่าและผ่าน live/platform acceptance ครบก่อน Sprint 2

release-content commit `71c20b37b1bf2be8f34b67294bc75137931ad3cb` ผ่าน exact local
BusyBox `check` 25.7 วินาที, no-cache build สาม image 230.8 วินาที,
provider-free/fake acceptance + log/rate-limit/restart 28.7 วินาที และ
BusyBox `deploy` simulation 63.5 วินาที รายละเอียดอยู่ที่
`docs/evidence/2026-08-08-local-release-candidate.md` หลักฐาน production/live
ต้องอ้าง exact GitLab pipeline แยกต่างหาก; #35722 ไม่ถึง acceptance และห้ามใช้
เป็นหลักฐานว่า Tokenmind หรือ public platform ผ่าน ส่วน rollback #35736 มี
production acceptance แยกแล้ว แต่หลักฐานนั้นไม่ครอบ Sprint 2 descendant
โดยอัตโนมัติ

CI และตัวจำลอง local ส่งต่อเฉพาะชื่อตัวแปรสี่ตัวข้างต้นผ่าน temporary env file
สิทธิ์จำกัด ค่า access code/cookie/secret ที่ใช้ acceptance อยู่ใน process
memory และไม่ถูกใส่ใน child-process argv ส่วน Docker build context ทั้งสามมี
`.dockerignore` แยก และ core image ใช้ explicit `COPY` allowlist

## Deploy

Participant Guide กำหนดให้ branch อื่นรัน `check` อย่างเดียวและ deploy จาก
`main` เท่านั้น ส่วน AI Guard เพิ่ม protected-ref gate ให้ production:

| ref/pipeline | งานที่ถูกสร้าง |
|---|---|
| feature branch push หรือ merge request | `check` เท่านั้น |
| push ทุก branch รวม protected/unprotected `main` | `check` เท่านั้น |
| protected `main` จากปุ่ม Run pipeline | `check → deploy → acceptance` แล้วจึงมี manual `logs/ps/restart` |
| tag, schedule หรือ API-triggered pipeline | ไม่สร้าง pipeline production |

ทุก job inherit tag `team-08` จาก `default.tags` ตรงกับ tag ที่เห็นบน runner
`#227` นี่เป็น repository-side scheduling hardening ไม่ใช่หลักฐานว่า Docker host
หรือ daemon แยกจริง Participant Guide ไม่กำหนดให้ runner ต้องมี Protected flag;
runner #227 ที่ไม่มี flag นี้จึงไม่ใช่ publication blocker เพียงลำพัง แต่ควรให้
ผู้จัดยืนยัน scope/daemon isolation เป็น platform evidence

GitLab auto-protected the first remote `main` เมื่อสร้าง default branch จริง
pipeline #35715 จึงพิสูจน์ว่าสมมติฐาน unprotected-bootstrap เดิมไม่ถูกต้อง
Executable rules ปัจจุบันทำให้ **Ordinary pushes are check-only** เสมอ แม้
`main` protected แล้ว ส่วน production ต้องเริ่มด้วยปุ่ม Run pipeline บน protected
`main` เท่านั้น วิธีนี้ไม่ใช้ `ci.skip` และแยก source publication ออกจาก
production authorization อย่างชัดเจน

ชื่อ secret มีสี่ตัวเท่านั้น: `APP_AIGUARD_API_KEY`,
`APP_AIFT_ACCESS_CODE`, `APP_AIFT_COOKIE_SIGNING_KEY`,
`APP_TOKENMIND_API_KEY` คู่มือกำหนดให้ secret เป็น **Masked** ส่วน Protected,
Hidden (ถ้ารองรับ), expansion off และ environment scope `team08` เป็น AI Guard
security hardening ที่ให้ตั้งหลัง protect `main` แล้ว Protected Environment ไม่ใช่
ข้อกำหนดของคู่มือและ GitLab CE ปัจจุบันไม่มี UI นี้ เฉพาะ `deploy` และ
`acceptance` ประกาศ environment `team08` เพื่อรับ scoped variables; manual ops
ไม่ประกาศ environment และใช้ direct Docker commands จึงไม่ต้องรับสี่ secret

`check` เป็น interruptible เพื่อยกเลิกงานตรวจที่ซ้ำเมื่อ commit ใหม่มา ส่วน
`deploy`, `acceptance` และ manual ops เป็น non-interruptible เพื่อไม่ให้
auto-cancel ทิ้ง production mutation หรือ acceptance ไว้กึ่งกลาง
