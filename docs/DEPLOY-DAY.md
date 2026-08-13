# วันที่ deploy ต้องทำอะไรบ้าง

## Production Web Launch gate (13 ส.ค. 2569)

ส่วนนี้มีผลเหนือ competition demo checklist ด้านล่างสำหรับ descendant ที่เปลี่ยน
runtime/web/proxy:

1. เริ่มจาก `c02ec1c82e22d0e200fbfad68556c169eba68007`; deployed rollback ที่ต้อง
   รักษาคือ `72e18bbe723adaf54c847e4b17c2177dfa60dd68` / Pipeline #35744
2. ตรวจ `docs/PRODUCTION-READINESS.md`: P0/P1 repository-owned ต้องเป็นศูนย์,
   exact branch clean, VERSION `2.5.0`, 16 routes และ public PDF/OCR redaction
   สอง alias fixed 404
3. รัน affected contracts + exact fake-provider local acceptance แล้ว push
   `codex/aift-production-web-launch`; feature pipeline ต้อง `check` อย่างเดียว
   ไม่มี environment, protected secrets หรือ production mutation
4. independent Security/Privacy, Reliability/Ops และ Product/Public UX reviewers
   ต้อง review exact candidate แบบ read-only และไม่มี open P0/P1
5. fast-forward reviewed tree เข้า protected `main`, push ปกติ และรอ main
   check-only pipeline เขียว จากนั้นสร้าง **web pipeline ใหม่** ที่ exact SHA
   โดยไม่ใส่ temporary variables
6. deploy helper ต้อง snapshot previous exact image/Compose set, build/recheck
   remote, mutate ครั้งเดียว, รอ core/api/web healthy+revision ตรง และ rollback
   previous revision อัตโนมัติหาก post-mutation gate ล้ม
7. acceptance ต้องผ่านทั้ง `tests/platform_acceptance.py` (synthetic auth/scan/
   one live Safe AI/report/routes/logs) และ `tests/public_web_acceptance.py`
   บน public edge จริง
8. **hard launch gate:** `http://team08.aiforthai.in.th/` และ `/api/health`
   ต้อง 308 ไป fixed HTTPS path โดยไม่สะท้อน query; HTTPS ต้องมี HSTS หากยัง
   200 plain HTTP ให้หยุด public launch และขอ organizer edge redirect—ห้ามแก้ด้วย
   client-side JavaScript หรือซ่อน access form เท่านั้น
9. browser QA จริงต้องครอบ `/`, `/privacy`, `/terms`, `/help`, `/downloads`,
   invite login/session/refresh/logout/replay denial, Privacy Scan, Safe AI,
   PDPA Report, 429/fixed error, mobile 390px + desktop 1440px, console/mixed
   content และ accessibility/focus
10. ตรวจ application logs ว่ามีเฉพาะ fixed operation/surface, method, status,
    bytes, duration และไม่มี synthetic sentinel/IP/target/query/body/prompt/
    response/mapping/cookie/credential จากนั้นตรวจ limits 256M/256M/2G,
    PID caps, read-only/no-new-privileges, restart/watchdog, exact revision และ
    recoverable previous images

หาก deploy เขียวแต่ public-edge/acceptance แดง candidate อาจกำลังรันอยู่แต่
**ยังไม่พร้อมให้สาธารณะใช้** ให้รักษาสภาพ exact SHA และรายงาน external gate
แทนการลด auth, rate, privacy, provider หรือ route control

ทุกอย่างในไฟล์นี้เป็นงานที่เจ้าของทำเองหรือมอบอำนาจให้ operator อย่างชัดเจน
เพราะออกนอกเครื่องทั้งหมด
ไฟล์นี้ใช้ได้ต่อเมื่อ preflight ใน `STATE.md` ผ่านครบ Production known-good
ปัจจุบันคือ exact `72e18bbe723adaf54c847e4b17c2177dfa60dd68`:
Pipeline #35744 ผ่าน check/deploy/acceptance และ public live acceptance แล้ว
ส่วน `9d38c6753aa0242bc35d09ec3332e90fe3f90079` เป็น rollback ก่อน Sprint 2
ทุก runtime descendant ต้องผ่าน
exact fake-provider local acceptance, feature-branch check, independent reviews
และ pipeline/public acceptance ใหม่ก่อนแทน baseline นี้ Evaluation/tests/docs-only
descendant ต้องผ่าน check/review แต่ไม่ควร deploy runtime ซ้ำโดยไม่มี runtime change Public PDF redaction/OCR
ถูกพักจาก hosted release แรกและไม่ใช่ deploy gate ส่วน PDPA Report PDF ยังเปิด

Participant Guide ทางการยืนยัน team/port/proxy/CI/resource/log/secret shape
แล้ว แต่ไม่ได้ยืนยันว่า candidate ปัจจุบันผ่าน privacy หรือทำงานบน runner จริง
ไฟล์นี้คือลำดับของวันจริงหลัง local gate ปิด

core ที่ใช้วัน deploy ต้องให้ manifest ชี้ exact upstream `44ef30b` ซึ่งหยุดก่อน
Native Broker และ VERSION ต้องคง `2.5.0`

เวลาที่ควรเผื่อ ประมาณหนึ่งชั่วโมงถ้าไม่มีอะไรผิด และเผื่ออีกเท่าตัวถ้าผิด
เดดไลน์ของงานคือ 17 ส.ค. 2569 นำเสนอ 19 ส.ค.

## 1 สร้าง project บน GitLab

project เปล่าที่สร้างแล้วคือ
`https://gitlab.nectec.or.th/ai4thai-service-hackathon/08/aiguard-aift`
ใน namespace slug `08` (สิทธิ์ Maintainer มีแล้ว)
ชื่อ project ไม่ผูกกับอะไรในโค้ด แต่ `TEAM: "team08"` ใน `.gitlab-ci.yml`
กับพอร์ต 20070/20071 ผูกกับทีมแน่นอน อย่าแก้

## 2 ยืนยัน runner และ pipeline source

สถานะที่เจ้าของเห็นปัจจุบัน: runner `#227` เป็น organizer-provided group runner
ของ team-08, online, Docker amd64/Linux, tag `team-08`, accepts untagged และ
ไม่มี Protected flag ทุก job ใน repo pin tag `team-08` แล้วจึงไม่ควรถอด tag
เพื่อให้ไปรันบน instance runner อื่น

**Participant Guide ไม่กำหนด Protected runner** และกล่าวเพียงว่าใช้ runner
ของทีมที่ผู้จัดให้พร้อม tag ที่เห็นเมื่อมี tag อยู่ ดังนั้นการไม่มี Protected
flag เพียงอย่างเดียวไม่ใช่ publication blocker ส่วนการยืนยันว่า project อื่น
เข้าถึง runner/daemon เดียวกันไม่ได้ยังเป็น platform evidence ที่ควรถามผู้จัด;
tag/rules ไม่ได้พิสูจน์ host isolation

Auto DevOps ปิดอยู่แล้ว ให้ยืนยันว่า project `.gitlab-ci.yml` เป็น pipeline
source ที่มีผลจริง ห้ามให้ template อื่น override release pipeline นี้

## 3 First publication และ production attempt ที่เกิดขึ้นจริง

remote `origin` ถูกยืนยันและ first publication SHA `298401552726...` สร้าง
remote `main` สำเร็จ GitLab auto-protected the first remote `main` เพราะเป็น
default branch ซึ่งต่างจากสมมติฐานเดิม Pipeline #35715 จึงสร้าง production jobs
ตาม rules เก่า แต่ทุก job เหล่านั้นจบเป็น `skipped` เมื่อ `check` ล้มเหลว ไม่มี
application variable, provider call หรือ production mutation

กติกา repository ปัจจุบันทำให้ **Ordinary pushes are check-only** ทุก branch
รวม protected `main`; deploy/acceptance/ops สร้างได้เฉพาะ `web` pipeline ที่
เจ้าของเริ่มผ่าน **Build → Pipelines → Run pipeline** บน protected `main`

check-only pipeline #35718 ผ่าน exact `5ae77ad25eb...` บน runner #227 แล้ว
Production pipeline #35722 ที่ SHA เดียวกันผ่าน check และยกสาม service จน
healthy แต่ deploy job ล้มหลัง mutation เพราะ job-container loopback ไปไม่ถึง
host ports 20070/20071 Acceptance/ops ไม่ได้ execute และ #35722 ห้ามนับเป็น
successful deployment evidence

## 4 Credential gate และ production pipeline สำหรับ descendant ใหม่

`main` protected, force push ปิด และ push/merge จำกัด Maintainers แล้ว Owner
ยืนยันว่า project variables มีสี่ชื่อครบโดยไม่เปิดเผยค่า:

| ตัวแปร | ข้อกำหนดของค่า |
|---|---|
| `APP_AIFT_ACCESS_CODE` | สุ่มแยก ใช้แจกผู้เข้าถึงผ่านช่องทางส่วนตัว; ไม่ใช่ per-user account |
| `APP_AIFT_COOKIE_SIGNING_KEY` | สุ่มอย่างน้อย 32 ไบต์ แยกจาก access code |
| `APP_AIGUARD_API_KEY` | สุ่มอย่างน้อย 16 ไบต์ เป็น key ที่ nginx ฉีดให้ core ไม่ใช่ของผู้จัด |
| `APP_TOKENMIND_API_KEY` | key ที่ผู้จัด reissue/rotate หลังเหตุ transcript exposure; ห้ามใช้ค่าเดิมหรือซ้ำกับสาม secret ข้างบน |

**Official Participant Guide requirement:** secret ต้องเป็น Masked และไม่อยู่ใน
source/frontend

**AI Guard security hardening:** metadata ปัจจุบันเป็น Protected, Hidden,
Masked และ scope `team08` ทั้งสี่ตัว โดยไม่อ่านค่าจริง Protected Environment
ไม่ใช่ข้อกำหนดของคู่มือและ GitLab CE ปัจจุบันไม่มี UI นี้ เฉพาะ deploy กับ
acceptance ประกาศ environment `team08`; manual ops ไม่ประกาศ environment
เพื่อไม่ให้รับ application secrets ที่ไม่จำเป็น

`resource_group: team08-production` ทำ serialization และ deploy/acceptance ตรวจ
SHA กับ `origin/main` ซ้ำเพื่อกัน stale deployment คู่มือไม่กำหนด `newest_first`
หรือ automatic rollback; ไม่ใช้สองอย่างนี้เป็น publication gate

หลัง feature branch check-only และ local gates ผ่าน ให้ fast-forward reviewed
commit เข้า `main` แล้ว push ปกติก่อนเพื่อรัน check-only จากนั้นไปที่ **Build →
Pipelines → Run pipeline**, เลือก branch `main`, ไม่เพิ่ม variable ชั่วคราว
และสร้าง pipeline **ใหม่บน exact descendant SHA** ห้าม Retry #35736 หรือ
pipeline ก่อนหน้า เพราะ rules/evidence ต้องประเมินกับ SHA ใหม่

`check` เป็น interruptible ส่วน deploy, acceptance และ ops เป็น
non-interruptible งานตรวจซ้ำยกเลิกได้เมื่อ commit ใหม่มา แต่ production
mutation/acceptance ต้องไม่ถูก auto-cancel กลางทาง

## 5 ดูให้ครบสาม stage ไม่ใช่แค่ deploy เขียว

- **check** ตรวจกติกา compose ของผู้จัด ความตรงของ vendored slice กับ
  upstream Git object, caller-auth, executable frontend session contract
  และสัญญาของ nginx/web proxy
- **deploy** build แล้ว `up -d` แล้วรอ healthcheck ของ `team08-api-1`
  และ `team08-web-1`
  ชื่อ service ต้องเป็น `api` เท่านั้น deploy job ของผู้จัด `docker inspect`
  ชื่อนั้นตรง ๆ Deploy แยก build → recheck remote main → `up --no-build`
  และ probe จากใน api/web container; ห้ามกลับไป curl host-loopback จาก job
- **acceptance** login, ยิง PII สังเคราะห์ผ่านทั้งสายไปถึง thaillm-8b จริง,
  ตรวจ minimized response, allowlist, PDPA Report, public PDF denial และ scan log ทุกบรรทัด
  ที่ container ปัจจุบันยังเก็บไว้
  **นี่คือ stage เดียวที่จับได้ว่า key ไปไม่ถึง container** เพราะ healthcheck
  ยังเขียวได้ในความล้มเหลวแบบนั้น (`/health` ไม่ถูก gate)

acceptance ต่อเฉพาะ build job container เข้า Compose network ชั่วคราวและเรียก
`http://api:8000` พร้อม public Host โดยปิด ambient proxy Path นี้ตรวจ deployed
api/core แต่ bypass organizer edge, TLS, `/api` stripping และ host publication
จึงยังต้องตรวจ public platform แยกหลัง pipeline เขียว

หลัง platform route ขึ้นแล้วต้องยืนยันว่า 413/429/502/504 เป็น fixed JSON,
upstream body ไม่หลุด และ client-IP/rate-limit semantics หลัง organizer proxy
ตรงกับที่คาด `/health` ยังคงเป็น liveness ไม่ใช่หลักฐานว่า Tokenmind พร้อม

competition frontend acceptance หลัง pipeline เขียวต้องใช้ synthetic preset:

1. login แล้วเปิด Guided Demo; ยืนยันลำดับ Privacy Scan → Safe AI → PDPA Report
2. ยืนยัน frontend ยิง `/roundtrip` หนึ่ง invocation ในรอบ Guided ปกติ ไม่มี
   duplicate click/retry ฝั่ง browser (server retry provider เดิมยังเป็น policy เดิม)
3. ชี้การ์ด “ข้อความที่ส่งให้ AI จริง” และตรวจว่าค่าดิบสังเคราะห์ที่ detect พบ
   ไม่อยู่ใน protected input; ห้ามเรียกสิ่งนี้ว่า cryptographic attestation
4. ตรวจ Executive Result Summary และ Raw-vs-Protected ว่าผูกข้อความ/mode ของ
   รอบเดียวกัน custom raw/restored ต้องถูกซ่อนเป็น default ใน Presenter/fullscreen
5. ตรวจ Sensitive Data Map ว่าแสดง count/type/position โดยไม่เปิดค่าที่ตรวจพบ;
   Prompt Risk ต้องบอกชัดว่า warning-only และแสดง unavailable อย่างซื่อตรง
6. ตรวจ Protection Receipt ว่าเป็น request-scoped screen evidence ไม่ใช่
   cryptographic attestation/PDPA certificate และไม่มี mapping/pair/provider body
7. ยืนยัน safety pass, restoration complete, residual signals/leftover tokens
   เป็นศูนย์ และคำตอบ restored แสดงเฉพาะเมื่อทุก gate ผ่าน
8. ยืนยัน score/grade ของ PDPA Report มาจาก endpoint; type context ต้องระบุว่า
   มาจาก Privacy Scan ของข้อความเดียวกัน
9. กด reset ระหว่าง/หลังรอบและ logout; raw/protected/restored/receipt/map/report/timing/
   progress ต้องถูกล้างและ stale response ห้ามกลับมา
10. ตรวจ Token และ Surrogate แยกกันเมื่อจำเป็น: ทั้งคู่เป็น pseudonymization
    ไม่ใช่ anonymization และ Surrogate ไม่ได้ปลอดภัยกว่าโดยอัตโนมัติ
11. เปิด/ปิด Presenter Mode และ fullscreen โดยยืนยันว่าไม่มี request เพิ่ม,
    ออกจากโหมดได้ และ projector/mobile ไม่มี horizontal clipping
12. ตรวจ System Evidence ว่า health แสดง liveness/VERSION เท่านั้น ไม่อ้าง provider
13. ตรวจ public PDF redaction/OCR + forbidden routes ยัง 404, logs ไม่มี user
   content/secret/cookie/request body แล้วทำ resource + restart/revision acceptance

ถ้า `deploy` เขียวแต่ `acceptance` แดง อย่าเพิ่งดีใจ บริการขึ้นแล้วแต่ทำงาน
ไม่ได้

## 6 ถ้ามีปัญหา ใช้ manual job แทน SSH

stage `ops` มี `logs` `ps` `restart` กดจากหน้า pipeline ทั้งสามใช้ direct
Docker commands ไม่ใช้ Compose interpolation และไม่ประกาศ environment `team08`
จึงไม่รับ application secrets Restart ปฏิเสธ stale remote/image revision แล้ว
รอ web/api/core healthy ครบก่อนผ่าน ส่วน `ps` fail closed ถ้า revision ของ
service ใดไม่ตรง pipeline SHA และแสดง resource snapshot
และมี Dozzle ที่ `https://team08.aiforthai.in.th/logs/`
ไม่มี arbitrary shell job; หากต้องวินิจฉัยเพิ่มให้ส่ง reviewed one-shot job
แทนการเปิดช่องรันคำสั่งทั่วไปบน production

## สิ่งที่ยังไม่รู้ และจะรู้ตอน push จริงเท่านั้น

- **เวลา build บน runner ของผู้จัด** job timeout คือ 20 นาที core image
  ที่ rebuild ล่าสุดมีขนาด 809,367,578 ไบต์ (ประมาณ 771.9 MiB) และ bake
  โมเดล OCR ไว้ แต่เครื่องนี้ไม่ใช่ runner เน็ตกับดิสก์คนละตัว
  ถ้าชน 20 นาทีจริง ให้คุยกับ Staff พร้อมตัวเลข ไม่ใช่เดา
- **runner isolation** ทุก job pin tag `team-08` แล้ว และ deploy/acceptance/ops
  schedule เฉพาะ protected `main` Participant Guide ไม่กำหนด Protected flag
  และ runner #227 ที่ไม่มี flag นี้ไม่ใช่ publication blocker เพียงลำพัง แต่ยัง
  ควรให้ staff ยืนยัน project scope/daemon isolation; tag/rules ไม่ใช่ isolation
  boundary
- **runner tag** ถ้า job ค้าง pending ให้ตรวจว่า runner ยังมี tag `team-08`
  ตรงกับ `.gitlab-ci.yml`; อย่าถอด tag เพื่อให้ไปรันบน runner อื่น
- **โควตาของ gateway** `acceptance` ยิงของจริงทุกครั้งที่ protected `main`
  เริ่ม full release pipeline
  (และ retry ได้สูงสุด 3 ครั้งเมื่อเจอ transport/5xx)
- **PDF/OCR** implementation ยังอยู่ภายใน core แต่ public proxy ต้องคืน 404
  ทั้งสอง alias และหน้าเว็บต้องไม่มี upload flow หลักฐานหนึ่งหน้าเดิม (221 วินาที,
  CPU ~1.93/2 cores, memory ชน 6 GiB) เป็นเหตุให้พัก capability นี้ การเปิดใหม่
  ต้องผ่าน correctness/provenance/resource acceptance แยกต่างหาก
