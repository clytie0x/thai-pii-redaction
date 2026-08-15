# สถานะงาน (15 ส.ค. 2569 — Desktop-first Production Candidate)

## Current productionization candidate

- เริ่มจาก evaluation/main exact
  `c02ec1c82e22d0e200fbfad68556c169eba68007`; known-good deployed runtime
  ยังเป็น `72e18bbe723adaf54c847e4b17c2177dfa60dd68` จาก Pipeline #35744 จนกว่า
  descendant นี้จะผ่าน feature CI, independent review และ protected-main
  `check → deploy → acceptance` จริง
- production web tree ถูก fast-forward เข้า protected `main` แล้ว; corrective branch
  `codex/aift-production-acceptance-fix` แก้เฉพาะ acceptance transport หลัง
  Pipeline #36033 และ VERSION ยัง `2.5.0`
  และต้องคง 16 routes, public `/redact-pdf` + `/v1/redact-pdf` fixed 404,
  Tokenmind provider เดียว, no mapping และ no browser persistence
- live baseline เมื่อ 13 ส.ค. พบว่า plain HTTP ยังคืน app/API 200 และ HTTPS เดิม
  ไม่มี HSTS Candidate จึงเพิ่ม fixed-host 308 จาก forwarded original scheme +
  HSTS ทั้ง web/api และเพิ่ม public-edge acceptance จริง Fixed-host redirect ยังคง
  อยู่และต้องทำงานแบบ fail-closed หาก organizer ส่ง original scheme ในภายหลัง
- Owner รับความเสี่ยงเฉพาะ competition deployment เมื่อ 15 ส.ค. ว่า organizer
  public edge ที่ไม่ทำ HTTP-to-HTTPS redirect เป็น external platform limitation:
  public survey ที่ Owner ให้มาพบว่า host ของอีก 14 ทีมไม่มีทีมใด redirect ไป
  HTTPS; ทีมที่ตอบได้คืน HTTP 200 ทั้งหมด ยกเว้น Team 15 ที่ redirect ไป path อื่น
  บน HTTP และ Participant Guide ระบุ public HTTPS URL แต่ไม่ได้กำหนด team-level
  HTTP 308 ชัดเจน Acceptance จึงรายงาน status ที่ไม่ใช่ 308 เป็น structured
  `PUBLIC_EDGE_WARNING` ซึ่งอย่างเดียวไม่ทำ rollback ทั้งนี้ plain HTTP ยังไม่
  ปลอดภัยและ limitation นี้ยังไม่ได้ถูกแก้
- product surface ปัจจุบันเป็น Desktop-first: CTA หลักพาไปเลือก Desktop 3.0.0,
  Hosted Web App เป็น Private Beta ลำดับรอง และอธิบายก่อน input ว่า Desktop
  ตรวจจับ/ปกปิด/vault/restoration/report ในเครื่องโดยไม่มี provider command
  ส่วน Web รับ raw text ที่บริการ Team 08 และ Safe AI ส่ง Pathumma เฉพาะข้อความ
  ที่ปกป้อง+ตรวจซ้ำแล้ว Quick Start/หลักฐานขั้นสูงเป็น optional disclosure และมี
  static `/privacy`, `/terms`, `/help`, `/downloads`, robots,
  sitemap หน้า download ชี้ Release v3.0.0 ที่ตรวจ HTTP 200 แล้วสำหรับ Desktop
  Windows/Linux/macOS และ manual Extension ZIP โดยไม่สร้าง Store link ที่ยังไม่มี
  และ pin SHA-256/ขนาด/asset identity, SHA256SUMS กับ GitHub provenance Source
  contract จะ fail หาก redirect ออกจาก release-assets.githubusercontent.com,
  asset ถูกแทนที่ หรือ checksum/size ของ artifact ที่ประกาศเปลี่ยน
- Chrome Web Store Developer Dashboard ที่ตรวจแบบ read-only เมื่อ 14 ส.ค. แสดง
  AI Guard 3.0.0 เป็น Draft, ปุ่มส่งตรวจสอบยัง disabled และยังไม่เผยแพร่ หน้าเว็บจึง
  ระบุว่า “เตรียมส่งตรวจสอบ · ยังไม่เผยแพร่” พร้อมบอกว่า manual ZIP ต้องใช้
  Desktop 3.0.0 สำหรับ Native Messaging, แตกไฟล์แล้ว Load unpacked และคำเตือน
  ความน่าเชื่อถือของ OS อาจปรากฏเพราะเลื่อน code signing โดยไม่ชี้ให้ข้ามคำเตือน
  พร้อมเตือนว่า In-page Mask เริ่มหลัง raw text เข้า provider-controlled DOM แล้ว
  และ Side Panel เป็น raw-entry boundary ที่แข็งแรงกว่า
- invite gate ยังอยู่เพื่อคุม provider cost โดยไม่สร้าง account/database Session
  เก็บเฉพาะ SHA-256 token fingerprint+expiry สูงสุด 256 ค่าใน process, logout
  revoke replay และ restart invalidate session เดิม cookie ยังคง Secure/HttpOnly/
  SameSite=Strict/30 นาที
- nginx แยก global/public/work/provider request+connection lanes, ลด body cap เป็น
  128 KiB (login 8 KiB), ไม่ส่ง client IP เข้า core และ application log เหลือ
  fixed operation/surface, method, status, bytes, duration โดยไม่เก็บ IP/target/
  query/body/cookie
- hosted image ไม่ติดตั้ง/prewarm Paddle OCR ที่ public ใช้ไม่ได้แล้ว และ verify
  offline thainer asset tree กับ Sprint 3 digest ระหว่าง build Container เป็น
  read-only/no-new-privileges/PID bounded; core cap-drop all, tmpfs 128 MiB และ
  memory 2 GiB ต้องผ่าน exact-image resource acceptance ก่อน deploy
- healthcheck ใหม่ exit service หลัง local failure ต่อเนื่อง 3 ครั้งเพื่อให้
  `restart: unless-stopped` ฟื้น process; graceful stop 210 วินาที Deploy helper
  เก็บ previous image IDs + historical Compose และ rollback exact prior revision
  เมื่อ post-mutation health/stale gate ล้ม
- Section 26 report wording ถูก project ผ่าน port-owned hosted adapter เป็น
  heuristic review signal ที่ต้องประเมินบริบท ไม่แก้ vendored detector/core
  75 ไฟล์จาก `44ef30b`
- protected-main Pipeline #36033 ที่ exact `0c10f7ed222a7840cc6af8db2fbd455be7f8c53b`
  ผ่าน check+deploy แต่ acceptance พบว่า route probe เดิมพยายาม copy เข้า
  read-only `/app`; acceptance trap จึงคืน exact runtime
  `72e18bbe723adaf54c847e4b17c2177dfa60dd68` healthy ตามนโยบาย ไม่ปล่อย
  candidate ที่ยังไม่ accepted ค้างอยู่ การแก้ใช้ stdin เข้า `python -` ภายใน
  container และผ่าน local read-only report probe โดยไม่อ่าน secret ออกมา
- protected-main web Pipeline #36253 ที่ exact
  `6ce57356540c5f3b47b8ea12a601039f9e8582e3` ผ่าน check+deploy และ internal
  platform acceptance ผ่าน auth, 16-route allowlist, live Pathumma roundtrip,
  report และ sensitive-value log scan แต่ public edge คืน HTTP 200 แทน 308
  ที่ `/?sentinel=must-not-reflect` Acceptance trap คืน exact `72e18bbe...`
  และ Job #140572 ยืนยัน web/api/core revision ตรง, healthy และอยู่ใน resource
  limit แล้ว ประวัติ rollback นี้ต้องเก็บไว้ หลัง owner decision วันที่ 15 ส.ค.
  เฉพาะ failure นี้ถูกจัดเป็น external warning; ไม่ใช่หลักฐานว่า HTTP ปลอดภัย
- strict log audit หลัง rollback พบว่า Uvicorn access stream ยังมี client IP/port
  metadata แม้ไม่มี body, prompt, cookie, mapping หรือ credential Follow-up
  exact `db5c041132ac2d8527a3ab7e629bb767f7298bf0` จึงปิด Uvicorn access log ที่
  launcher และทำให้ local/production
  acceptance fail หากรูปแบบ client-address access record กลับมา Structured
  web/api/audit logs ที่ไม่เก็บ request target ยังคงอยู่ SHA นี้ผ่าน feature
  Pipeline #36257 และ protected-main check-only Pipeline #36258 แล้ว แต่ไม่ได้
  deploy ซ้ำภายใต้นโยบาย acceptance เดิมเพราะจะ rollback แบบ deterministic
- รายการ P0/P1/P2 และ platform evidence ที่ไม่ควรอ้างอยู่ที่
  `docs/PRODUCTION-READINESS.md` งานนี้เปลี่ยน runtime จึงต้อง deploy exact SHA;
  HTTPS/valid TLS/HSTS, protected acceptance, live provider, auth/Secure cookie,
  16-route allowlist+legacy denial, log/resource/restart และ browser QA ยังเป็น
  mandatory ทั้งหมด การขาด HTTP 308 เท่านั้นที่เป็น accepted external warning

แผนแม่บท: `C:\Users\teera\.claude\plans\ai-for-thai-expressive-lighthouse.md`
remote `main` protected และ known-good production Pipeline #35744 ที่ exact
`72e18bbe723adaf54c847e4b17c2177dfa60dd68` ผ่าน
`check → deploy → acceptance` ครบแล้ว web/api/core ใช้ revision เดียวกัน และ
public acceptance ผ่าน health, auth, Privacy Scan, live Tokenmind Safe AI,
PDPA Report, route denial, log privacy, resource และ restart/recovery SHA นี้เป็น
rollback evidence ก่อนหน้า `9d38c6753aa0242bc35d09ec3332e90fe3f90079`
ยังต้องรักษา ขั้นตอนของวันจริงอยู่ที่ `docs/DEPLOY-DAY.md`

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

## Hosted production scope หลัง Sprint 2 (10 ส.ค. 2569)

- product สาธารณะมีสาม workflow เท่านั้น: Privacy Scan, Safe AI, PDPA Report
- frontend เป็น light-theme ภาษาไทย-first สำหรับการนำเสนอ: Guided Demo ร้อย
  Privacy Scan → Safe AI → PDPA Report จาก synthetic scenario เดียวกัน โดยเรียก
  `/roundtrip` ฝั่ง frontend หนึ่งครั้งและหยุดเมื่อขั้นใดไม่ผ่าน มี gallery ห้า
  บริบท + reset, Executive Result Summary, Raw-vs-Protected, Sensitive Data Map,
  Prompt Risk, Protection Receipt, Presenter/fullscreen, entity glossary,
  mode `token`/`surrogate`, เวลา total ที่วัดในเบราว์เซอร์ และการ์ด
  “ข้อความที่ส่งให้ AI จริง” ผลทั้งหมด derive จาก response เดิมและไม่สร้าง
  provider call หรือ public route เพิ่ม
- Protection Receipt เป็นหลักฐานบนหน้าจอเฉพาะคำขอ ไม่ใช่หลักฐานเข้ารหัสหรือ
  ใบรับรอง PDPA และไม่แสดง mapping/pair/provider body/raw value ส่วน Prompt Risk
  เป็น heuristic warning-only ที่ไม่บล็อกและไม่รับรองว่าปลอดภัย
- Presenter/fullscreen ไม่ persist state ไม่เรียก network และซ่อน raw/restored
  ของ custom input โดย default; frontend ไม่มี third-party dependency หรือ
  persistent browser storage ของเนื้อหาผู้ใช้
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

## Sprint 3 evaluation scope (10 ส.ค. 2569)

- สร้าง corpus จาก deterministic local templates เท่านั้น 138 direct-PII cases
  (102 positive, 24 hard negative, 12 ambiguous ที่ไม่นับ headline) และ 32
  Section 26 heuristic cases; ไม่มี production/user/log/provider record
- ครบ entity type ที่ hosted revision ปล่อยออกมา 18 ชนิด Ground truth ใช้
  half-open Python Unicode code-point spans และ generated manifest ผูก seed,
  generator/schema/corpus SHA-256
- baseline บังคับวัด detector ที่ exact production SHA `72e18bbe...` ก่อนพิจารณา
  fix ได้ exact typed P/R/F1 = 76.86/77.50/77.18%, protective-character recall
  91.57% และ hard-negative document FP rate 25.00%; per-type ทุกแถวยัง support
  ต่ำกว่า 25 จึงเป็น descriptive only
- recognized value removal = 100% ทั้ง Token/Surrogate; controlled-echo restore
  exact = 100% ในรอบที่ sanitize สำเร็จ Surrogate สอง zero-width PHONE cases
  ถูกหยุด fail closed ไม่มี unsafe text คืน ส่วน expected-gold removal อยู่ราว
  94% เพราะ detector miss ต้องรายงานช่องว่างนี้ตรง ๆ
- Section 26 แยกเป็น HEURISTIC SIGNAL EVALUATION: recall 100%, precision 50%,
  F1 66.67% บน 32 cases แสดงชัดว่าคำ keyword ใน negation/context ยัง flag;
  ไม่ใช่ PDPA compliance/legal classifier
- evaluator รันใน revision-labelled core image ด้วย `--network none` + socket
  tripwire, environment allowlist, offline thainer; provider calls/production
  credentials/real PII = 0 และ artifact ไม่มี corpus text, replacement หรือ
  reidentification pair
- ไม่มีการแก้ `core/`: manifest-pinned vendored ownership ทำให้ address/name/
  parenthesized-or-zero-width phone remediation เป็น upstream task ไม่ใช่การ
  tune fixture ใน hosted shell
- ไม่มี frontend/runtime/API change ไม่เพิ่ม public evidence card เพื่อหลีกเลี่ยง
  demo clutter หลักฐานอยู่ที่ `docs/evaluation/thai-pii-competition-evaluation.md`
  และ machine result `evaluation/thai_pii/baseline.72e18bbe.json`
- independent Thai human adjudication ยัง pending; จึงห้ามอ้าง population-wide
  accuracy หรือ perfect detection

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
   พิสูจน์ network correction ครั้งแรกบน runner #227; Pipeline #35736 ที่ exact
   `9d38c6753aa0242bc35d09ec3332e90fe3f90079` คือ rollback ก่อน Sprint 2 และ
   Pipeline #35744 ที่ exact `72e18bbe723adaf54c847e4b17c2177dfa60dd68`
   คือ known-good production ปัจจุบัน: check/deploy/acceptance ผ่านครบ สาม image revision
   ตรงกัน public HTTPS และ `/api` stripping ผ่าน login/session/logout, synthetic
   Privacy Scan, live Tokenmind/thaillm roundtrip, PDPA Report, PDF/forbidden-route
   denial, retained-log scan, resource และ restart/recovery
7. เฉพาะ deploy/acceptance ประกาศ environment `team08` และรับ scoped secrets;
   manual ops ใช้ direct Docker commands โดยไม่ประกาศ environment จึงไม่รับ
   application variables Restart ตรวจ remote SHA + image revision ก่อนทำงาน
   และรอ health ทั้งสาม service
8. competition enhancement ที่เปลี่ยน runtime ต้อง push feature branch ให้ check-only เขียว ผ่าน
   exact fake-provider local acceptance และ independent reviews ก่อน fast-forward
   `main`; จากนั้นสร้าง UI pipeline ใหม่บน protected `main` exact SHA ห้าม retry
   pipeline เก่าหรือใช้ rollback #35736/#35744 เป็นหลักฐานของ runtime descendant
9. successful pipeline ต้องผ่าน `check → deploy → acceptance` ครบ แล้วจึงตรวจ
   public HTTPS, organizer `/api` prefix, real browser cookie flow, rate limit,
   Dozzle/log, resources, restart/recovery และ visual QA แยกจาก internal
   Compose-network acceptance
10. Public PDF redaction/OCR ยัง proxy-level 404 ทั้งสอง alias; PDPA Report PDF
    ยังเปิดตามเดิม และ PDF/OCR ไม่ใช่ capability ของ hosted release นี้
11. คำตอบแบบสำรวจ + การตัดสินใจช่อง ASR ยังรอกรอก/ส่ง
12. Sprint 3 เป็น evaluation/tests/docs-only ถ้า feature check และ reviews ผ่าน
    ให้ integrate ตาม protected-main workflow แต่ไม่สร้าง production deployment
    ที่ไร้ runtime change; deployed SHA ต้องคง `72e18bbe...` และแยกจาก evaluation HEAD

ลำดับเต็มพร้อมกับดักอยู่ที่ `docs/DEPLOY-DAY.md` และใช้ได้เมื่อ preflight
ด้านบนผ่านแล้ว

## กติกาที่ห้ามลืม

- ไม่มี provider จำลองบน deployment / ไม่มีเดโมสำรอง — service จริงเท่านั้น
- pseudonymized-มี-vault ยังเป็นข้อมูลส่วนบุคคล — ห้ามเคลมเกิน
- ห้ามเคลมสาธารณะ "benchmark เดียวของไทย"
- production pipeline ต้องมีคำสั่งเจ้าของชัดเจนและต้องอ้าง exact reviewed SHA;
  ordinary branch/main pushes ยังเป็น check-only ตาม executable rules
- ตัวเลขเวลาจากเครื่องนี้บอกลำดับความใหญ่ ไม่ใช่คำรับประกันบน runner ของผู้จัด
