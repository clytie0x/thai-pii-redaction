# AI Guard Hosted 3.0 Deploy and Application API Guide

สถานะเอกสาร: **Current production guide**
วันที่ตรวจล่าสุด: **17 สิงหาคม 2569**
Production URL: <https://team08.aiforthai.in.th/>
Public App: <https://team08.aiforthai.in.th/app>
Runtime version: **Hosted 3.0.0**
HTTP contract: **2**
Runtime revision: `f07745209e3da3b926eb6802f2ca2919e5b9fe9d`
Protected production pipeline: **#36540**

เอกสารนี้เป็นแหล่งอ้างอิงปัจจุบันสำหรับ deployment, same-origin application
API, authentication, data flow, acceptance, rollback และ operations ของ
AI Guard Hosted 3.0.0 เอกสาร deployment รุ่นก่อนหน้าที่ยังกล่าวถึง Hosted
2.5.0, 16 routes หรือสถาปัตยกรรม 3 services ให้ถือเป็นหลักฐานประวัติเท่านั้น

## 1. Product และ trust boundary

AI Guard เป็นผลิตภัณฑ์ Desktop-first โดย Desktop 3.0.0 เก็บการตรวจจับ,
pseudonymization, vault/mapping, restoration และรายงานช่วยตรวจทาน PDPA
ไว้บนอุปกรณ์ และไม่มีคำสั่งเรียก provider ภายนอก

Hosted 3.0.0 เป็นช่องทางแยกต่างหาก:

- ข้อความและ text-layer PDF ที่ผู้ใช้เลือกถึง AI for Thai organizer edge,
  API proxy และ AI Guard Core ก่อนการปกป้อง
- Pathumma ได้รับเฉพาะ exact protected text ที่ผู้ใช้ตรวจและอนุมัติแล้ว
- Pathumma ไม่ได้รับ source PDF, original text หรือ reversible mapping
- Token และ Surrogate เป็น reversible pseudonymization ไม่ใช่ anonymization
- AI Guard แทนที่เฉพาะ PII ที่ตรวจพบ ข้อมูลที่ตรวจไม่พบอาจยังอยู่
- รายงาน PDPA และ Section 26 เป็นเครื่องมือช่วยตรวจทาน ไม่ใช่คำวินิจฉัย
  ทางกฎหมายหรือใบรับรอง compliance

## 2. Current architecture

```text
Public HTTPS
  |
  +-- /, /app, /developers, /privacy, /help, /terms, /downloads
  |      -> web (static nginx, host loopback port 20070)
  |
  +-- /api/*
         -> AI for Thai organizer edge strips /api
         -> api (exact-match nginx, host loopback port 20071)
         -> restores /api and injects the internal service contract
         -> core (FastAPI, internal network only)
              |
              +-- Unix socket -> pdf-parser (networkless)
              |
              +-- HTTPS -> Tokenmind / Pathumma thaillm-8b
                           protected text only
```

| Service | หน้าที่ | ขอบเขต runtime |
|---|---|---|
| `web` | Home, App และ reference pages | read-only, non-root, loopback `20070` |
| `api` | exact route allowlist, limits, fixed errors, internal key injection | read-only, non-root, loopback `20071` |
| `core` | auth, detect, guard, preview, approval, queue, execute, report | internal network only, read-only, non-root |
| `pdf-parser` | bounded text-layer PDF extraction | secretless, networkless, Unix socket, read-only |

ทั้ง 4 services ใช้ `no-new-privileges`, drop capabilities, bounded
CPU/memory/PID, volatile tmpfs, bounded rotating logs และ health watchdog
ร่วมกับ Docker restart policy

## 3. Public access model

Hosted 3.0.0 เป็น public Web App ที่ใช้ **same-origin application API
contract** ไม่ใช่ public arbitrary third-party API, ไม่ออก developer API key
และไม่เปิด broad CORS

### Standard access

- เริ่มผ่าน `POST /api/auth/guest`
- ได้ signed browser session อายุไม่เกิน 30 นาที
- ไม่ต้องมีบัญชีผู้ใช้หรือรหัสเชิญ
- ไม่มี artificial one-run total cap แต่ยังอยู่ใต้ rate, queue และ capacity limits

### Priority Invite

- แลก issued high-entropy invite ผ่าน `POST /api/auth/login`
- ได้ signed Priority browser session อายุไม่เกิน 30 นาที
- มี rate และ queue weight สูงกว่า Standard
- ไม่ใช่สิทธิ์ admin และไม่เปิด logs, secrets, mapping หรือ session อื่น

Cookies เป็น `Secure`, `HttpOnly`, `SameSite=Strict`, `Path=/` Logout revoke
token ปัจจุบัน และ Core restart ทำให้ session เก่าใช้ไม่ได้ ระบบไม่มี user
database และเก็บเพียง SHA-256 token fingerprints กับ expiry ใน bounded process
memory

## 4. Exact application API contract

Public proxy มี 20 canonical paths และ exact `/v1` aliases อีก 20 paths รวม
**40 exact locations** ทุก path ภายนอกใช้ `/api/...`

| Method | Canonical path | Purpose |
|---|---|---|
| GET | `/health` | liveness และ VERSION เท่านั้น |
| POST | `/auth/login` | exchange Priority Invite เป็น signed session |
| POST | `/auth/logout` | revoke Priority session และ clear cookie |
| GET | `/auth/session` | authenticated/expiry state, service-class และ timing headers โดยไม่คืน credential, subject หรือ token |
| POST | `/detect` | PII counts, types และ spans |
| POST | `/guard` | prompt-risk heuristic ที่ไม่ block ด้วยตัวเอง |
| POST | `/roundtrip` | Priority compatibility path ผ่าน shared queue |
| POST | `/analyze-report` | automated PDPA review และ report PDF |
| POST | `/auth/guest` | start Standard browser authority |
| POST | `/auth/guest/end` | end Standard authority |
| POST | `/guest/preview` | preview server-owned synthetic scenario |
| POST | `/guest/execute` | execute approved synthetic scenario |
| POST | `/protection-preview` | provider-free custom-text protection preview |
| POST | `/protection-execute` | execute approved custom protected text |
| POST | `/document-preview` | extract/protect bounded text-layer PDF |
| POST | `/document-execute` | create approved protected document artifact |
| POST | `/provider-queue/join` | join content-free provider queue |
| GET | `/provider-queue/status` | read content-free status only |
| POST | `/provider-queue/claim` | foreground long-poll claim handoff |
| POST | `/provider-queue/cancel` | cancel queued work before provider start |

แต่ละ canonical path มี exact alias ที่เพิ่ม `/v1` หลัง `/api` เช่น
`/api/detect` และ `/api/v1/detect` Prefix, wildcard, implicit versions,
unknown methods, query-bearing control calls, internal routes, PDF redaction
และ OCR routes ถูกปฏิเสธแบบ fail closed

Public health ตรวจได้โดยไม่ใช้ credential:

```bash
curl -fsS https://team08.aiforthai.in.th/api/health
```

Expected current shape:

```json
{
  "status": "ok",
  "version": "3.0.0",
  "contract_version": 2,
  "capabilities": {
    "control_token_required": false,
    "api_key_required": true
  }
}
```

`api_key_required` refers to the internal proxy-to-Core service control. A
Standard browser user does not receive or submit an API key.

Business routes ใช้ผ่าน official Web App และ signed same-origin browser
authority เอกสารนี้ไม่ประกาศ API-key quick start สำหรับ third-party client

## 5. User data flows

### Inspect and report

```text
raw text -> organizer edge -> AI Guard Core
         -> detect / guard / analyze-report
         -> minimized result or report
```

เส้นทางนี้ไม่เรียก Pathumma

### Protect text for AI

```text
raw text -> organizer edge -> AI Guard Core
         -> detect and pseudonymize
         -> provider-free preview and outbound decision
         -> user reviews exact protected payload
         -> explicit approval -> queue -> matching claim
         -> fresh outbound scan before every provider attempt
         -> protected text only -> Pathumma thaillm-8b
         -> output validation -> residual check -> restoration validation
         -> verified result or fail-closed error
```

Reversible mapping อยู่ชั่วคราวใน request scope, ไม่อยู่ใน provider payload,
public response หรือ queue record และไม่ได้ตั้งใจ persist ระบบไม่อ้าง secure
memory zeroization

### Text-layer PDF to Protected Markdown

```text
user selects PDF (no automatic upload)
  -> explicit Upload and extract
  -> organizer edge -> AI Guard Core
  -> bounded temporary spool -> networkless parser
  -> selectable-text segments and metadata
  -> source spool cleanup
  -> protect detected PII -> exact protected preview
  -> approval -> queue -> fresh outbound scan
  -> protected segments only -> Pathumma
  -> segment classification/order validation
  -> deterministic Protected Markdown rendering
```

- Maximum PDF body: 5 MiB
- Source PDF remains unchanged and is not sanitized
- Source PDF never reaches Pathumma
- No PII restoration into the protected document artifact
- Scanned/image-only PDF, OCR, visual layout reconstruction และ redacted/rebuilt
  PDF ไม่รองรับ

## 6. Important limits

| Control | Current boundary |
|---|---|
| Text length | 20,000 Unicode code points |
| Standard text/report | 6 requests/minute per signed Standard session |
| Priority text/report | 30 requests/minute per issued Priority session |
| Standard document preview | 1 request/minute |
| Priority document preview | 4 requests/minute |
| Standard queue join | 1 request/minute |
| Priority queue join | 6 requests/minute |
| Legacy `/roundtrip` | 6 requests/minute globally, 2/minute per presented session key |
| Global provider work | maximum 2 concurrent operations |
| Per authority provider work | maximum 1 unresolved operation |
| Active queue records | maximum 12, content-free |
| Provider envelope | bounded retries under the 200-second proxy envelope |

Limits เป็น safeguards ไม่ใช่ throughput หรือ uptime promise Queue position
เป็นค่าประมาณและไม่มี ETA

## 7. Protected deployment workflow

### Required protected variables

Production ใช้ชื่อ variable 5 รายการต่อไปนี้ ค่าเป็น secret และห้ามใส่ใน
repository, screenshots, command arguments หรือเอกสาร:

- `APP_AIGUARD_API_KEY`
- `APP_AIFT_ACCESS_CODE`
- `APP_AIFT_COOKIE_SIGNING_KEY`
- `APP_AIFT_PRIORITY_INVITES_JSON`
- `APP_TOKENMIND_API_KEY`

### Release sequence

1. ทำงานบน feature branch และให้ ordinary push รัน `check` เท่านั้น
2. ตรวจ review, contracts, built images และ browser evidence ให้ผ่าน
3. Fast-forward exact reviewed SHA ไป `main`
4. Push `main` ตามปกติ ซึ่งยังคงเป็น check-only
5. สร้าง **UI-created pipeline** บน protected `main` exact SHA
6. ต้องผ่าน `check -> deploy -> acceptance` ตามลำดับ
7. หลัง acceptance ผ่าน จึงรัน manual `logs`, `ps` และ `restart` jobs
8. ตรวจ public HTTPS, health, App, 40 routes, denial paths และ browser flow

Production jobs ถูก serialize ด้วย `resource_group: team08-production`
Deploy และ acceptance เป็น non-interruptible และตรวจ latest remote `main`
เพื่อปฏิเสธ stale SHA

## 8. Acceptance and rollback

`scripts/deploy_production.sh` ทำงานตามหลักการ:

- retain previous exact image IDs และ Compose source ก่อน mutation
- build exact candidate revision
- recheck remote `main` ก่อนและหลัง mutation
- start 4 services และ health/revision gate ทุก service
- ไม่ยอม deploy เมื่อไม่มี recoverable previous release

Mandatory acceptance ตรวจอย่างน้อย:

- exact running image revision
- Standard และ Priority auth
- custom text preview/approval/queue/Pathumma/result
- PDF preview/queue/Protected Markdown/artifact provenance
- legacy Priority roundtrip compatibility
- 40 public canonical/alias routes และ near-match denials
- report, resources, isolation, configured tmpfs และ value-free logs; post-flow
  temp cleanup ถูกพิสูจน์แยกใน local parser/lifecycle contracts
- real public HTTPS edge, product pages, HSTS และ release links/metadata ที่
  แสดงบน Downloads; external release artifact identity ถูกตรวจใน release-source
  contract แยกต่างหาก

หาก acceptance ล้ม `scripts/rollback_production.sh` จะ restore previous exact
release และรอ health ทุก service Failed pipeline ห้าม retry เพื่อใช้เป็น
หลักฐานของ descendant ใหม่ ต้องสร้าง commit/pipeline ใหม่

## 9. Operations runbook

### Read-only health

```bash
curl -fsS https://team08.aiforthai.in.th/api/health
```

Health เป็น liveness เท่านั้น ไม่ใช่ provider readiness

### GitLab operational jobs

| Job | Purpose |
|---|---|
| `logs` | read bounded logs ของ 4 services โดยไม่รับ application secrets |
| `ps` | verify exact revision, process health, ports และ resource snapshot |
| `restart` | ใช้ได้เมื่อ job SHA เท่ากับ latest `main` และ deployed image revisions เท่านั้น จากนั้น restart 4 services และรอ health recovery |

Pipeline #36540 ops jobs ผ่านครบในเวลาที่ `f0774520...` เป็นทั้ง latest main และ
deployed revision หลังจาก docs-only commits ขยับ `main` ต่อมา old `f077` restart
job จะ fail latest-main check ส่วน ops job จาก current main จะ fail image-revision
check จนกว่าจะมี protected deploy/acceptance pipeline ใหม่ ดังนั้นเอกสารนี้ไม่อ้าง
ว่า restart job ปัจจุบันสามารถ restart runtime `f077` ได้โดยตรง

### Incident order

1. หยุดการ deploy เพิ่มและบันทึกเวลา/อาการแบบ value-free
2. ตรวจ public `/api/health`
3. ตรวจ GitLab pipeline, exact revision และ `ps`
4. ตรวจ bounded logs โดยห้ามคัดลอก body, cookie, invite หรือ secret
5. ก่อน restart ต้องยืนยันว่า latest main, job SHA และ deployed revisions ตรงกัน
6. ถ้าไม่ตรงกัน ห้ามฝืนรัน restart job ให้สร้าง reviewed protected
   deploy/acceptance pipeline ใหม่หรือประสานผู้ดูแล platform ตาม authority ที่มี
7. ถ้า candidate acceptance ไม่ผ่าน ให้ใช้ automatic rollback result
8. ถ้าสาเหตุอยู่ที่ organizer edge หรือ provider ให้รายงานขอบเขตตามจริง

## 10. Logging and privacy controls

Application access logs มีเฉพาะ fixed operation/surface, method, status,
response bytes และ duration ไม่บันทึก:

- client IP
- request target หรือ query
- request/response body
- prompt หรือ provider payload
- mapping
- cookie หรือ invite
- API key หรือ credential

Docker log rotation จำกัด 50 MiB x 3 files ต่อ service Organizer edge metadata
retention อยู่นอกขอบเขตที่ repository ตรวจยืนยันได้

## 11. Current evidence

| Evidence | Result |
|---|---|
| Runtime | Hosted 3.0.0, contract 2, revision `f0774520...` |
| Pipeline | #36540 passed check, deploy and mandatory acceptance |
| Ops | logs #143199, revision/process #143200, restart #143201 passed |
| Services | web, api, core, pdf-parser healthy after restart |
| API surface | exactly 40 same-origin locations |
| Browser | 64 route/viewport states passed |
| Evaluation | 138 constructed PII cases and separate 32-case Section 26 set |

Evaluation เป็น deterministic synthetic/adversarial evidence ไม่ใช่ population
benchmark และไม่พิสูจน์ perfect detection

## 12. Known limitations

- Single replica ตาม AI for Thai platform envelope ไม่มี zero-downtime SLA
- Restart job ผูกกับ latest-main และ exact deployed revision; docs-only main ที่
  ใหม่กว่า runtime ทำให้ต้องผ่าน protected deploy/acceptance ใหม่ก่อนใช้ restart
- Organizer plain HTTP edge ไม่ redirect; URL ที่ให้ใช้คือ HTTPS ซึ่งมี valid
  TLS และ HSTS
- Health ไม่ใช่ provider readiness
- Detection มี false positive และ false negative ได้
- Text-layer PDF only; ไม่มี OCR หรือ rebuilt/redacted PDF
- Audio, TTS, images และ Vision ไม่อยู่ใน Hosted 3.0 scope
- Desktop Windows/macOS artifacts ยังไม่มี code signing/notarization
- Repository ไม่พิสูจน์ organizer certificate renewal, Docker daemon
  isolation, disk management, external alerting หรือ edge retention policy

## 13. Ownership

ผู้รับผิดชอบหลักหลัง Deploy คือ **นายธีรภัทร เวชพิทักษ์ หัวหน้าทีม AI Guard
(Team 08)** รับผิดชอบ production health, logs, exact revision, protected
pipeline, restart/recovery, rollback, credential rotation และ incident
coordination ช่องทางติดต่อใช้ข้อมูลที่ส่งใน AIFT Deployment Checklist

## 14. Historical document precedence

ไฟล์ต่อไปนี้เก็บ design, rollout และ incident history ของรุ่นก่อนหน้า จึงอาจมี
ข้อความ 2.5.0, 16 routes, 3 services หรือ SHA เก่า:

- `docs/DEPLOY-DESIGN.md`
- `docs/DEPLOY-DAY.md`
- `docs/GITLAB-HANDOFF.md`
- `docs/PRODUCTION-READINESS.md`

เมื่อต้องตอบคำถามสถานะปัจจุบัน ให้ใช้เอกสารนี้, `README.md`, ส่วน Current
release boundary ตอนต้นของ `STATE.md`, executable `.gitlab-ci.yml`, current
Compose/scripts และ public `/developers` เป็นหลัก
