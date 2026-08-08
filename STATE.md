# สถานะงาน (7 ส.ค. 2569 — exact local candidate; ยังไม่ push)

แผนแม่บท: `C:\Users\teera\.claude\plans\ai-for-thai-expressive-lighthouse.md`
เฟสนี้ = local ทั้งหมด **ยังไม่ deploy จนกว่าเจ้าของสั่ง**
ขั้นตอนของวันจริงอยู่ที่ `docs/DEPLOY-DAY.md`

Participant Guide ทางการถูกอ่านซ้ำเมื่อ 7 ส.ค. และยืนยัน `team08`,
พอร์ต `20070/20071`, frontend `/`, backend `/api` ที่ถูก strip prefix,
unprefixed `/health`, template-derived GitLab CI, main-only deploy,
per-service limits, `50m` × 3 log rotation, masked `APP_*`, และ no-SSH ops
ตรงกับ deployment shell นี้ในระดับ config

candidate ปัจจุบัน sync จาก main commit `8c6efef` ครบ 75 ไฟล์ผ่าน manifest
hash โดยคง `/v1` public aliases แต่ nginx inject contract 2 ให้ strict-v2 core
หน้าเว็บใช้ minimized DTO แล้ว Roundtrip ไม่คืน mapping, token/original pair
หรือ token-bearing entity projection

owner รับ ADR caller-auth เมื่อ 7 ส.ค.: static frontend กับ health เป็น public
ส่วน business API ต้องแลก access code เป็น signed cookie อายุ 30 นาทีแบบ
Secure/HttpOnly/SameSite=Strict internal core key และ provider key แยกกัน

## Hosted release-candidate scope (8 ส.ค. 2569)

- product สาธารณะมีสาม workflow เท่านั้น: Privacy Scan, Safe AI, PDPA Report
- exact proxy allowlist มี 16 routes (8 canonical + 8 `/v1` aliases)
- `/redact-pdf` และ `/v1/redact-pdf` คืน proxy-level 404; frontend ไม่มี
  upload/call/preview/download ของ PDF redaction
- implementation PDF/OCR และหลักฐานเก่าคงอยู่ภายใน core/เอกสารประวัติ แต่ OCR
  ยังไม่ production-ready บน AI for Thai การเปิดใหม่ต้องผ่าน correctness,
  provenance, timeout และ resource acceptance แยกต่างหาก

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

## เสร็จรอบ 3 ส.ค. — re-sync หมุดใหม่ + ถอดสลัก flake ใน acceptance

- **S4 re-sync** หมุด `00b3ffe` → `078e988` (69 ไฟล์ ตาม upstream CI ที่เขียวแล้ว)
  ได้งาน detection ชุด gov-form (gold F2 0.910→0.918), OCR fallback/merge-safe
  retries และฟอนต์ไทย bundled ซึ่งเข้าเส้น detect/redact-pdf/analyze-report
  ที่เปิดบน deployment ทั้งหมด SLICE เพิ่ม `licenses/OFL-1.1.txt` ตามที่ NOTICE ชี้
- **acceptance เลิกเทสอารมณ์ของโมเดล** รอบเต็มรอบแรกจับได้ว่า
  `grep -q` เบอร์โทรบน `restored_text` ผูกอยู่กับว่า thaillm ทวนโทเคนหรือไม่
  (echo 19/25 ที่ temp 0.0 — แดงเงียบทั้งที่บริการตอบ 200) แก้เป็น assert
  หน้าที่ของเราแบบ deterministic (ตรวจเจอครบ / ไม่มีค่าจริงหลุด / ไม่มี token
  residue) + assert โทเคนที่โมเดล**ทวนจริง**ต้องกลับเป็นค่าจริง + curl retry 3
  ครั้งเฉพาะ transport/5xx (เคส key หายยังแดงเพราะ 503 ล้มครบ) ทุกทางล้มมี echo
  พิสูจน์แดงเป็นครบ 6 เคสใต้ busybox ของอิมเมจ CI จริง
- **รันเต็มหลังแก้เขียวครบสาม job** check 70.8s / deploy 77.5s / acceptance
  86.0s (thaillm-8b จริง) และดึง `/analyze-report` จาก stack จริงตรวจด้วยตา
  PDF ฝัง `IBMPlexSansThaiLooped` วรรณยุกต์ซ้อนถูกทุกคำ
  รายละเอียด + ตัวเลขดิบอยู่ `docs/evidence/ci-first-push-readiness.md` (S4)

## เสร็จรอบ 7 ส.ค. — current-core/auth/minimized response

- **S5 sync** `078e988` → `8c6efef` (75 vendored files) รวม strict HTTP v2,
  fail-closed outbound policy, safe errors/logs และ explicit-TNER failure
- **caller auth** unit contract 11/11 ผ่าน ครอบคลุม fail-loud config, public
  health, login, cookie flags, tamper/expiry/secret rotation, cross-site,
  logout และทุก business route; startup ปฏิเสธการใช้ caller/signing/core/provider
  secret ซ้ำกัน
- **frontend session contract** รัน JavaScript จริงผ่าน: stale auth/detect/
  roundtrip/PDF response ไม่เขียนทับ state ใหม่, logout/401 ล้าง PII และ
  PDF bytes, login/logout ไม่แข่งกัน, astral span ตรง และคำตอบ unsafe ไม่ถูกแสดง
- **nginx contract** ผ่าน 12 business/health aliases, 6 auth aliases, 9
  proxy-denied paths, internal key/contract injection, web syntax และ
  api/web query-log regression รวม rate-limit warning path
- **dated local working-tree Docker stack** buildใหม่และ web/api/core healthy ทั้งหมด
  runtime auth/privacy probe ผ่าน 401/403/signed-cookie/strict-v2 minimized
  detect และไม่พบ synthetic honeytoken, PII, cookie หรือ secret ใน log
- **dated live smoke** 8/8 ผ่าน: health, auth, Tokenmind roundtrip, no-query log,
  allowlist, webpage, vendored integrity และ scanned-PDF OCR
- **dated local GitLab approximation** ผ่านครบใน BusyBox runner image:
  check 21.5s / deploy 59.2s (warm cache) / acceptance 8.8s; acceptance
  login จริง, เรียก Tokenmind จริง, ตรวจ minimized response และ scan log
- **exact committed candidate** `e075ca46807a1d318447ed4280821941d20608ba`
  ผ่าน local BusyBox `check` 28.0 วินาทีและ provider-free `deploy` 244.3
  วินาที; web/api/core healthy และ revision label ตรง commit ทั้งสามอิมเมจ
- **exact local profile** detect 100/100 หลัง warmup ได้ p50 6.02 ms,
  p95 7.58 ms, max 12.57 ms; one-page scanned-PDF route ผ่านใน 221.0 วินาที
  แต่ใช้ CPU เฉลี่ยประมาณ 1.93/2 cores และ memory peak ชน 6 GiB
  (`memory.events max=8247`, ไม่มี OOM/restart) จึงเป็น resource gate แดง
- independent security/compatibility review จบแล้วและไม่พบ static code blocker
  เพิ่มเติม; external/runtime gates ด้านล่างยังคงเปิด

## เหลือก่อนออกนอกเครื่อง

1. exact candidate ยังไม่ได้รัน live Tokenmind `acceptance`; credential เดิม
   ต้องถูก rotate/reissue ก่อน หลักฐาน live ด้านบนเป็น dated working-tree
   evidence เท่านั้น
2. fake-provider 8-worker/10-minute soak + restart ผ่านแล้ว (5849 success,
   0 failure) และ light Tokenmind 60 วินาทีผ่าน 50/50; คงตัวเลขเป็น dated
   local evidence ไม่ใช่ platform SLA
3. fail-loud ของ auth secrets และ fixed failure เมื่อ provider key หายผ่านแล้ว
4. local image IDs ของ exact candidate คือ web `ff8d654a...` (26,020,221
   bytes), api `2df7e1ac...` (26,006,890 bytes) และ core `2d938778...`
   (809,367,137 bytes); เป็น local image IDs ไม่ใช่ registry digests
   Public PDF ถูกพักจาก hosted release แรกแล้ว; ตัวเลขเดิมคงไว้เป็น historical evidence
5. public HTTPS/browser routing และ trusted proxy client identity สำหรับ login
   limiter ยังเปิดอยู่ ส่วน PDF authoritative source-to-box เป็น future internal gate
6. Tokenmind credential ที่ปรากฏใน transcript ระหว่าง read-only compose probe
   ต้อง rotate ก่อนใช้ภายนอก; ลบ ignored repo-root `.env` โดยไม่อ่านค่าแล้ว
7. staff ต้องยืนยันว่า runner ที่ถือ production Docker socket เป็น Protected
   และรับเฉพาะ protected refs หรือจัด isolated branch runner/daemon
8. GitLab push/runner, public HTTPS/proxy และ official platform acceptance
   ยังไม่เกิดขึ้น

## เหลือหลัง local recertification — งานออกนอกเครื่อง เจ้าของทำเอง

1. สร้าง project บน `gitlab.nectec.or.th` ใน group ของทีม
2. ตั้ง CI/CD Variables **ก่อน** push ครั้งแรก `APP_AIGUARD_API_KEY`,
   `APP_AIFT_ACCESS_CODE`, `APP_AIFT_COOKIE_SIGNING_KEY` และ
   `APP_TOKENMIND_API_KEY` เป็น Protected + Masked, scope `team08`; protect
   `main` และเปิด outdated-deployment protection
3. `git remote add origin ...` แล้ว push `main` (repo นี้ยังไม่มี remote เลย)
4. ดูให้ครบสาม stage ไม่ใช่แค่ deploy เขียว
5. คำตอบแบบสำรวจ + การตัดสินใจช่อง ASR ยังรอกรอก/ส่ง

ลำดับเต็มพร้อมกับดักอยู่ที่ `docs/DEPLOY-DAY.md` และใช้ได้เมื่อ preflight
ด้านบนผ่านแล้ว

## กติกาที่ห้ามลืม

- ไม่มี provider จำลองบน deployment / ไม่มีเดโมสำรอง — service จริงเท่านั้น
- pseudonymized-มี-vault ยังเป็นข้อมูลส่วนบุคคล — ห้ามเคลมเกิน
- ห้ามเคลมสาธารณะ "benchmark เดียวของไทย"
- deploy ขึ้น GitLab = รอคำสั่งเจ้าของเท่านั้น (สิทธิ์ Maintainer มีแล้ว)
- ตัวเลขเวลาจากเครื่องนี้บอกลำดับความใหญ่ ไม่ใช่คำรับประกันบน runner ของผู้จัด
