# สถานะงาน (9 ส.ค. 2569 — first publication complete; pre-deployment correction)

แผนแม่บท: `C:\Users\teera\.claude\plans\ai-for-thai-expressive-lighthouse.md`
remote `main` ถูก first-publish แล้ว แต่ **ยังไม่ deploy production**
ขั้นตอนของวันจริงอยู่ที่ `docs/DEPLOY-DAY.md`

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
- frontend เป็น light-theme ภาษาไทย-first สำหรับการนำเสนอ: มี synthetic demo
  presets ห้าบริบท + reset, Privacy Scan แบบ CTA ชัด, Safe AI สามช่วงโดยเน้น
  “ข้อความที่ส่งให้ AI จริง” และ PDPA Report แบบดู score/grade ก่อนดาวน์โหลด
  ตัวอย่างเป็นเพียง input ผลทุกอย่างยังเรียก API จริง ไม่มี persistence หรือ
  third-party frontend dependency
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

## เหลือก่อน production deployment

1. exact candidate ยังไม่ได้รัน live Tokenmind `acceptance`; credential เดิม
   ต้องถูก rotate/reissue ก่อน หลักฐาน live ด้านบนเป็น dated working-tree
   evidence เท่านั้น
2. fake-provider 8-worker/10-minute soak + restart ผ่านแล้ว (5849 success,
   0 failure) และ light Tokenmind 60 วินาทีผ่าน 50/50; คงตัวเลขเป็น dated
   local evidence ไม่ใช่ platform SLA
3. fail-loud ของ auth secrets และ fixed failure เมื่อ provider key หายผ่านแล้ว
4. no-cache acceptance image IDs ของ release-content commit คือ web
   `5ba79750f70f...`, api `998e3fc9b36c...` และ core `974852b84706...`;
   เป็น local image IDs ไม่ใช่ registry digests
   Public PDF ถูกพักจาก hosted release แรกแล้ว; ตัวเลขเดิมคงไว้เป็น historical evidence
5. public HTTPS/browser routing และ trusted proxy client identity สำหรับ login
   limiter ยังเปิดอยู่ ส่วน PDF correctness/resource/platform acceptance เป็น future gate
6. Tokenmind credential ที่ปรากฏใน transcript ระหว่าง read-only compose probe
   ต้อง rotate ก่อนใช้ภายนอก; ลบ ignored repo-root `.env` โดยไม่อ่านค่าแล้ว
7. Runner #227 เป็น organizer-provided team-08 group runner, online,
   Docker amd64/Linux, tag `team-08`, accepts untagged และไม่มี Protected flag
   คู่มือไม่กำหนด Protected runner และ flag ที่ขาดไม่ใช่ publication blocker
   เพียงลำพัง แต่ staff ควรยืนยัน project scope/daemon isolation; tag เป็นเพียง
   scheduling control ไม่ใช่ isolation proof
8. first publication สร้าง remote `main` ที่ `298401552726...`; GitLab
   auto-protected default branch และ pipeline #35715 ใช้ runner #227 จริง
   `check` หยุดที่ nginx contract เพราะ test ใช้ host-loopback assumption
   deploy/acceptance/ops เป็น skipped ทั้งหมดและไม่มี production mutation
   SHA นี้จึงเป็น historical first-publication evidence ไม่ใช่ deployment evidence
9. corrective push `f0359dc7b71f...` สร้าง check-only pipeline #35716 จริง
   (หนึ่ง job, ไม่มี production jobs) แต่หยุดเมื่อ friendly runner hostname
   resolve เป็น Docker container ไม่ได้ การแก้ descendant ใช้ GitLab job label
   และมี hostname-inspection fallback สำหรับ simulator; #35716 เป็น historical
   failed-check evidence และไม่มี production mutation
10. public HTTPS/proxy และ official platform acceptance ยังไม่เกิดขึ้น

## เหลือหลัง local recertification — งานออกนอกเครื่อง เจ้าของทำเอง

1. push corrective exact `main` ปกติ (ไม่ใช้ `ci.skip`) โดยยังไม่สร้าง
   application variables; executable rules ต้องสร้าง `check` job เดียว
2. ยืนยัน corrective pipeline เขียวและไม่มี production jobs
3. ทบทวน branch rule ที่ GitLab สร้างให้อัตโนมัติ แล้วสร้าง `APP_AIGUARD_API_KEY`,
   `APP_AIFT_ACCESS_CODE`, `APP_AIFT_COOKIE_SIGNING_KEY` และ
   `APP_TOKENMIND_API_KEY`: Masked ตามคู่มือ และเพิ่ม Protected/Hidden,
   expansion off, scope `team08` ตาม AI Guard hardening
4. หลัง owner อนุญาต production แยกต่างหาก จึงกด Run pipeline ใหม่บน exact
   protected-main SHA; ห้าม retry pipeline แรก
5. ดูให้ครบสาม stage ไม่ใช่แค่ deploy เขียว
6. คำตอบแบบสำรวจ + การตัดสินใจช่อง ASR ยังรอกรอก/ส่ง

ลำดับเต็มพร้อมกับดักอยู่ที่ `docs/DEPLOY-DAY.md` และใช้ได้เมื่อ preflight
ด้านบนผ่านแล้ว

## กติกาที่ห้ามลืม

- ไม่มี provider จำลองบน deployment / ไม่มีเดโมสำรอง — service จริงเท่านั้น
- pseudonymized-มี-vault ยังเป็นข้อมูลส่วนบุคคล — ห้ามเคลมเกิน
- ห้ามเคลมสาธารณะ "benchmark เดียวของไทย"
- deploy ขึ้น GitLab = รอคำสั่งเจ้าของเท่านั้น (สิทธิ์ Maintainer มีแล้ว)
- ตัวเลขเวลาจากเครื่องนี้บอกลำดับความใหญ่ ไม่ใช่คำรับประกันบน runner ของผู้จัด
