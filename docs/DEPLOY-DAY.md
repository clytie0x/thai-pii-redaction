# วันที่ deploy ต้องทำอะไรบ้าง

ทุกอย่างในไฟล์นี้เป็นงานที่ **เจ้าของต้องทำเอง** เพราะออกนอกเครื่องทั้งหมด
ไฟล์นี้ใช้ได้ต่อเมื่อ preflight ที่ยังเหลือใน `STATE.md` ผ่านครบ หลักฐานแบบ
release-content commit `71c20b37b1bf2be8f34b67294bc75137931ad3cb`
ครอบคลุม hosted-core `44ef30b`, caller-auth, response minimization และผ่าน
exact provider-free check/build/acceptance/restart แล้ว ส่วน Tokenmind
smoke/soak เดิมเป็น dated evidence:
ต้อง rotate credential แล้วรัน exact live acceptance ใหม่ Public PDF ถูกพัก
จาก hosted release แรกและไม่ใช่ deploy gate รอบนี้

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

## 3 First publication ที่เกิดขึ้นจริง และ corrective push แบบ check-only

remote `origin` ถูกยืนยันและ first publication SHA `298401552726...` สร้าง
remote `main` สำเร็จ GitLab auto-protected the first remote `main` เพราะเป็น
default branch ซึ่งต่างจากสมมติฐานเดิม Pipeline #35715 จึงสร้าง production jobs
ตาม rules เก่า แต่ทุก job เหล่านั้นจบเป็น `skipped` เมื่อ `check` ล้มเหลว ไม่มี
application variable, provider call หรือ production mutation

กติกา repository ปัจจุบันแก้ให้ **Ordinary pushes are check-only** ทุก branch
รวม protected `main`; deploy/acceptance/ops สร้างได้เฉพาะ `web` pipeline ที่
เจ้าของเริ่มผ่าน **Build → Pipelines → Run pipeline** บน protected `main`
correction push ใช้ normal push, ไม่ใช้ `ci.skip`, และต้องยังไม่สร้าง application
variables ตรวจหน้า pipeline ว่ามี `check` เพียง job เดียว

## 4 ทบทวน `main`, สร้าง variables แล้วเริ่ม production pipeline ใหม่

หลัง corrective `check` เขียว ให้ไปที่ **Settings → Repository → Branch rules**
เพื่อตรวจ rule ที่ GitLab สร้างให้อัตโนมัติ: `main` ต้อง protected, force push
ปิด และ push/merge จำกัดตามสิทธิ์ทีม ห้ามแก้ protection ใน recovery session

จากนั้นสร้าง variables สี่ตัว:

| ตัวแปร | ข้อกำหนดของค่า |
|---|---|
| `APP_AIFT_ACCESS_CODE` | สุ่มแยก ใช้แจกผู้เข้าถึงผ่านช่องทางส่วนตัว; ไม่ใช่ per-user account |
| `APP_AIFT_COOKIE_SIGNING_KEY` | สุ่มอย่างน้อย 32 ไบต์ แยกจาก access code |
| `APP_AIGUARD_API_KEY` | สุ่มอย่างน้อย 16 ไบต์ เป็น key ที่ nginx ฉีดให้ core ไม่ใช่ของผู้จัด |
| `APP_TOKENMIND_API_KEY` | key ที่ผู้จัด reissue/rotate หลังเหตุ transcript exposure; ห้ามใช้ค่าเดิมหรือซ้ำกับสาม secret ข้างบน |

**Official Participant Guide requirement:** secret ต้องเป็น Masked และไม่อยู่ใน
source/frontend

**AI Guard security hardening:** ตั้ง Protected, Hidden ถ้ารองรับ, ปิด variable
expansion, scope `team08` และให้ค่าทั้งสี่ไม่ซ้ำกัน ทำขั้นนี้หลัง protect `main`
แล้วเท่านั้น Protected Environment ไม่ใช่ข้อกำหนดของคู่มือและ GitLab CE ปัจจุบัน
ไม่มี UI นี้ environment ของ job ยังคงชื่อ `team08`

`resource_group: team08-production` ทำ serialization และ deploy/acceptance ตรวจ
SHA กับ `origin/main` ซ้ำเพื่อกัน stale deployment คู่มือไม่กำหนด `newest_first`
หรือ automatic rollback; ไม่ใช้สองอย่างนี้เป็น publication gate

หลังได้รับ owner authorization สำหรับ production แยกต่างหาก ไปที่ **Build →
Pipelines → Run pipeline**, เลือก branch `main`, ไม่เพิ่ม variable ชั่วคราว แล้ว
สร้าง pipeline **ใหม่บน exact SHA ปัจจุบัน** source `web` นี้เท่านั้นที่ rules
อนุญาตให้ protected `main` รัน `check → deploy → acceptance` ห้ามกด Retry บน
pipeline #35715 เพราะใช้ SHA/rules เก่า

## 5 ดูให้ครบสาม stage ไม่ใช่แค่ deploy เขียว

- **check** ตรวจกติกา compose ของผู้จัด ความตรงของ vendored slice กับ
  upstream Git object, caller-auth, executable frontend session contract
  และสัญญาของ nginx/web proxy
- **deploy** build แล้ว `up -d` แล้วรอ healthcheck ของ `team08-api-1`
  และ `team08-web-1`
  ชื่อ service ต้องเป็น `api` เท่านั้น deploy job ของผู้จัด `docker inspect`
  ชื่อนั้นตรง ๆ
- **acceptance** login, ยิง PII สังเคราะห์ผ่านทั้งสายไปถึง thaillm-8b จริง,
  ตรวจ minimized response, allowlist, PDPA Report, public PDF denial และ scan log ทุกบรรทัด
  ที่ container ปัจจุบันยังเก็บไว้
  **นี่คือ stage เดียวที่จับได้ว่า key ไปไม่ถึง container** เพราะ healthcheck
  ยังเขียวได้ในความล้มเหลวแบบนั้น (`/health` ไม่ถูก gate)

หลัง platform route ขึ้นแล้วต้องยืนยันว่า 413/429/502/504 เป็น fixed JSON,
upstream body ไม่หลุด และ client-IP/rate-limit semantics หลัง organizer proxy
ตรงกับที่คาด `/health` ยังคงเป็น liveness ไม่ใช่หลักฐานว่า Tokenmind พร้อม

ถ้า `deploy` เขียวแต่ `acceptance` แดง อย่าเพิ่งดีใจ บริการขึ้นแล้วแต่ทำงาน
ไม่ได้

## 6 ถ้ามีปัญหา ใช้ manual job แทน SSH

stage `ops` มี `logs` `ps` `restart` กดจากหน้า pipeline
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
