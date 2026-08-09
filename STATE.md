# สถานะงาน (9 ส.ค. 2569 — competition enhancement from accepted production)

แผนแม่บท: `C:\Users\teera\.claude\plans\ai-for-thai-expressive-lighthouse.md`
remote `main` protected และ production Pipeline #35727 ที่ exact
`42476d09a7d80b6920fcf21c0d2ac0d5c6952872` ผ่าน `check → deploy → acceptance`
ครบแล้ว web/api/core ใช้ revision เดียวกัน และ public acceptance ผ่าน health,
auth, Privacy Scan, live Tokenmind Safe AI, PDPA Report, route denial, log privacy,
resource และ restart/recovery SHA นี้เป็น rollback baseline ของ enhancement sprint
ปัจจุบัน ขั้นตอนของวันจริงอยู่ที่ `docs/DEPLOY-DAY.md`

Participant Guide ทางการถูกอ่านครบและยืนยัน `team08`, พอร์ต `20070/20071`,
frontend `/`, backend `/api` ที่ถูก strip prefix, unprefixed `/health`,
non-main `check`, main-only deploy, per-service limits, `50m` × 3 log rotation,
Masked application variables และ no-SSH ops ส่วน protected-main gate,
protected variables, runner tag และ stale-SHA checks เป็น AI Guard hardening
ไม่ใช่ข้อกำหนดที่คู่มือระบุ

candidate ปัจจุบัน sync จาก main commit `44ef30b` ครบ 75 ไฟล์ผ่าน manifest
hash โดยคง `/v1` public aliases แต่ nginx inject contract 2 ให้ strict-v2 core
หน้าเว็บใช้ minimized DTO แล้ว Roundtrip ไม่คืน mapping, token/original pair
หรือ token-bearing entity projection

owner รับ ADR caller-auth เมื่อ 7 ส.ค.: static frontend กับ health เป็น public
ส่วน business API ต้องแลก access code เป็น signed cookie อายุ 30 นาทีแบบ
Secure/HttpOnly/SameSite=Strict internal core key และ provider key แยกกัน

## Hosted release-candidate scope (9 ส.ค. 2569)

- product สาธารณะมีสาม workflow เท่านั้น: Privacy Scan, Safe AI, PDPA Report
- frontend เป็น light-theme ภาษาไทย-first สำหรับการนำเสนอ: Guided Demo ร้อย
  Privacy Scan → Safe AI → PDPA Report จาก synthetic scenario เดียวกัน โดยเรียก
  `/roundtrip` ฝั่ง frontend หนึ่งครั้งและหยุดเมื่อขั้นใดไม่ผ่าน มี gallery ห้า
  บริบท + reset, Protection Evidence, mode `token`/`surrogate`, เวลา total ที่วัด
  ในเบราว์เซอร์ และการ์ด “ข้อความที่ส่งให้ AI จริง” ผลทุกอย่างยังมาจาก API จริง
  ไม่มีการเก็บเนื้อหาผู้ใช้ในพื้นที่จัดเก็บของเบราว์เซอร์หรือ third-party dependency
- ทุก CI job ถูก pin ด้วย runner tag `team-08`; feature branch/MR และ push ทุก
  branch รวม protected `main` รัน `check` เท่านั้น ส่วน deploy/acceptance/ops
  ต้องเป็น UI-created pipeline บน protected `main` ตาม executable rules
- exact proxy allowlist มี 16 routes (8 canonical + 8 `/v1` aliases)
- `/redact-pdf` และ `/v1/redact-pdf` คืน proxy-level 404; frontend ไม่มี
  upload/call/preview/download ของ PDF redaction
- implementation PDF/OCR และหลักฐานเก่าคงอยู่ภายใน core/เอกสารประวัติ แต่ OCR
  ยังไม่ production-ready บน AI for Thai การเปิดใหม่ต้องผ่าน correctness,
  provenance, timeout และ resource acceptance แยกต่างหาก
- hosted core sync ถึง `44ef30b` ซึ่งรวม shared provider retries/fresh outbound
  scans, Tokenmind single-attempt และ authoritative PDF intervals โดยหยุดก่อน
  Native Broker; VERSION ยังเป็น 2.5.0
- public 413/429/502/504 เป็น fixed value-free JSON, upstream error body ถูก
  intercept และ roundtrip สอง alias ใช้ timeout 200 วินาทีให้ครอบ shared
  provider envelope; health ยังคงเป็น liveness

## เสร็จแล้ว (มีหลักฐาน)

- **E0 spike ผ่าน**: paddle cp313 wheel มีจริง, HOME=/opt/ocr-home + chown appuser ใช้ได้,
  offline inference ได้, build เย็น 270s / spike image 2.74GB / RSS 910MB
- **E1-E5 จบ**: สรุป + คำตอบแบบสำรวจอยู่ `docs/evidence/e0-e5-results.md`
  (Text ✓, Vision ✗, GPU ไม่มี, ASR = เจ้าของเลือก — เลขถอดเป็นคำอ่านไทย e4_report.json)
- **Upstream PR #101 merge แล้ว** (`71b7120`) และ PR #102 (ADR tokenmind + port) ตามมา
- **Port repo นี้** ประกอบครบ: sync (SHA-256 manifest + LF normalize), core/Dockerfile
  (OCR baked, UVICORN_WORKERS), api/ (nginx exact allowlist + /v1 + noquery + key inject),
  web/index.html (หน้าเดิมห้าฉาก tokenmind-only ซึ่งถูกแทนด้วยสาม workflow
  ปัจจุบันด้านบนแล้ว), docker-compose.yml, .gitlab-ci.yml, README,
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
- **release-content commit** `71c20b37b1bf2be8f34b67294bc75137931ad3cb`
  ผ่าน local BusyBox `check` 25.7 วินาที, no-cache build สาม image 230.8
  วินาที, provider-free/fake acceptance + log/rate-limit/restart 28.7 วินาที
  และ BusyBox `deploy` simulation 63.5 วินาที; revision label ตรง commit
  ทั้งสามอิมเมจ
- **exact local profile** detect 100/100 หลัง warmup ได้ p50 6.02 ms,
  p95 7.58 ms, max 12.57 ms; one-page scanned-PDF route ผ่านใน 221.0 วินาที
  แต่ใช้ CPU เฉลี่ยประมาณ 1.93/2 cores และ memory peak ชน 6 GiB
  (`memory.events max=8247`, ไม่มี OOM/restart) จึงเป็น resource gate แดง
- ทุก descendant ที่เปลี่ยน frontend หรือ CI ต้องผ่าน Product/Judge review,
  security review และ exact-revision fake-provider acceptance ใหม่ก่อน
  fast-forward local `main`; หลักฐาน commit เก่าไม่ครอบ descendant โดยอัตโนมัติ

## Production evidence และสิ่งที่ยังเหลือ

1. runner #227 เป็น organizer-provided team-08 group runner, online,
   Docker amd64/Linux, tag `team-08`, accepts untagged และไม่มี Protected flag
   คู่มือไม่กำหนด Protected runner และ flag ที่ขาดไม่ใช่ publication blocker
   เพียงลำพัง แต่ staff ควรยืนยัน project scope/daemon isolation; tag เป็นเพียง
   scheduling control ไม่ใช่ isolation proof
2. first publication `298401552726...` pipeline #35715 และ correction
   `f0359dc7b71f...` pipeline #35716 เป็น historical failed-check evidence;
   ไม่มี production mutation #35718 ที่ exact `5ae77ad25eb...` ผ่าน check-only
   จริงบน runner #227
3. owner ยืนยัน project variables สี่ชื่อครบ โดย metadata เป็น Protected,
   Masked, Hidden และ scope `team08`; repository/Codex ไม่อ่านค่าจริง
4. historical production pipeline #35722 บน `5ae77ad25eb...` ผ่าน check และ build/up
   จน web/api/core healthy แต่ deploy ล้มที่ job-container
   `127.0.0.1:20070/20071`; acceptance และ manual ops ไม่ได้ execute
   stack ที่ยกสำเร็จคงอยู่ แต่ #35722 ไม่ใช่ successful acceptance evidence
5. descendant correction เปลี่ยน deploy เป็น in-container probe, ต่อเฉพาะ
   acceptance job เข้า exact Compose network ชั่วคราว, ปิด ambient proxy,
   รักษา public Host และ cleanup เสมอ ทั้งยังแยก build/recheck/up เพื่อลด
   stale-main race
6. Pipeline #35727 ที่ exact `42476d09a7d80b6920fcf21c0d2ac0d5c6952872`
   พิสูจน์ correction บน runner #227: check/deploy/acceptance ผ่านครบ สาม image
   revision ตรงกัน public HTTPS และ `/api` stripping ผ่าน login/session/logout,
   synthetic Privacy Scan, live Tokenmind/thaillm roundtrip, PDPA Report, PDF และ
   forbidden-route denial, retained-log scan, resource และ restart/recovery
7. เฉพาะ deploy/acceptance ประกาศ environment `team08` และรับ scoped secrets;
   manual ops ใช้ direct Docker commands โดยไม่ประกาศ environment จึงไม่รับ
   application variables Restart ตรวจ remote SHA + image revision ก่อนทำงาน
   และรอ health ทั้งสาม service
8. competition enhancement ต้อง push feature branch ให้ check-only เขียว ผ่าน
   exact fake-provider local acceptance และ independent reviews ก่อน fast-forward
   `main`; จากนั้นสร้าง UI pipeline ใหม่บน protected `main` exact SHA ห้าม retry
   pipeline เก่าหรือใช้ baseline #35727 เป็นหลักฐานของ descendant
9. successful pipeline ต้องผ่าน `check → deploy → acceptance` ครบ แล้วจึงตรวจ
   public HTTPS, organizer `/api` prefix, real browser cookie flow, rate limit,
   Dozzle/log, resources, restart/recovery และ visual QA แยกจาก internal
   Compose-network acceptance
10. Public PDF redaction/OCR ยัง proxy-level 404 ทั้งสอง alias; PDPA Report PDF
    ยังเปิดตามเดิม และ PDF/OCR ไม่ใช่ capability ของ hosted release นี้
11. คำตอบแบบสำรวจ + การตัดสินใจช่อง ASR ยังรอกรอก/ส่ง

ลำดับเต็มพร้อมกับดักอยู่ที่ `docs/DEPLOY-DAY.md` และใช้ได้เมื่อ preflight
ด้านบนผ่านแล้ว

## กติกาที่ห้ามลืม

- ไม่มี provider จำลองบน deployment / ไม่มีเดโมสำรอง — service จริงเท่านั้น
- pseudonymized-มี-vault ยังเป็นข้อมูลส่วนบุคคล — ห้ามเคลมเกิน
- ห้ามเคลมสาธารณะ "benchmark เดียวของไทย"
- production pipeline ต้องมีคำสั่งเจ้าของชัดเจนและต้องอ้าง exact reviewed SHA;
  ordinary branch/main pushes ยังเป็น check-only ตาม executable rules
- ตัวเลขเวลาจากเครื่องนี้บอกลำดับความใหญ่ ไม่ใช่คำรับประกันบน runner ของผู้จัด
