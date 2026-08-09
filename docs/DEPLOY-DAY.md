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

## 2 ตั้ง CI/CD Variables ก่อน push

protect branch `main` ก่อน แล้วตั้ง Settings → CI/CD → Variables เป็น
**Protected + Masked + Hidden (ถ้ารองรับ)** ทั้งสี่ตัว ปิด variable expansion
พร้อม environment scope `team08`
จากนั้น protect environment `team08` และกำหนด **Allowed to deploy** เฉพาะ
owner/maintainers

ปิด Auto DevOps หรือยืนยันว่า project `.gitlab-ci.yml` เป็น pipeline source
ที่มีผลจริง ห้ามให้ template อื่น override release pipeline นี้

ตรวจ runner ก่อน push ด้วย: runner ที่มองเห็น production Docker daemon ต้อง
ถูกตั้งเป็น **Protected runner** และรับเฉพาะ protected refs ถ้ายืนยันไม่ได้
ต้องให้ staff จัด isolated daemon/runner สำหรับ branch; `rules:` ในไฟล์ CI
อย่างเดียวกัน branch แก้เองได้จึงไม่ใช่ security boundary

| ตัวแปร | ค่า |
|---|---|
| `APP_AIFT_ACCESS_CODE` | สุ่มแยก ใช้แจกผู้เข้าถึงผ่านช่องทางส่วนตัว; ไม่ใช่ per-user account |
| `APP_AIFT_COOKIE_SIGNING_KEY` | สุ่มอย่างน้อย 32 ไบต์ แยกจาก access code |
| `APP_AIGUARD_API_KEY` | สุ่มอย่างน้อย 16 ไบต์ เป็น key ที่ nginx ฉีดให้ core ไม่ใช่ของผู้จัด |
| `APP_TOKENMIND_API_KEY` | key ที่ผู้จัด reissue/rotate หลังเหตุ transcript exposure; ห้ามใช้ค่าเดิมหรือซ้ำกับสาม secret ข้างบน |

ถ้าลืมข้อนี้ deploy job จะล้มตั้งแต่ compose interpolation ด้วยข้อความ
`... is required` ซึ่งเป็นพฤติกรรมที่ตั้งใจ ไม่ใช่บั๊ก
บริการต้องไม่บูตแบบเปิดครึ่งใบ

ใน GitLab CI/CD settings เปิด **Prevent outdated deployment jobs** และตั้ง
resource group `team08-production` เป็น `newest_first` เมื่อ resource group
ปรากฏ ตัว job ตรวจ `origin/main` ซ้ำก่อน deploy/acceptance อยู่แล้ว จึงปฏิเสธ
pipeline เก่าที่มารันทีหลัง แต่ project settings นี้เป็นชั้นป้องกัน production
เพิ่มเติม

## 3 ต่อ remote แล้ว push `main`

repo นี้ยังไม่มี remote เลย ต้องเปิดหน้า **Code → Clone** แล้วคัดลอก SSH URL
จาก UI ก่อน ค่าที่คาดคือ
`git@gitlab.nectec.or.th:ai4thai-service-hackathon/08/aiguard-aift.git`
แต่ห้ามตั้งจากการคาดเดาเพียงอย่างเดียว

```bash
git remote add origin <SSH URL ที่ยืนยันจาก GitLab UI>
git push -u origin main
```

เมื่อ `main` ถูก protect ก่อน publication และ owner controls ครบ pipeline จะ
วิ่งเอง `check` → `deploy` → `acceptance` ทุก job inherit runner tag `team-08`

ถ้า GitLab รุ่นนี้สร้าง protected rule ให้ branch ที่ยังไม่มีไม่ได้ ให้ owner
อนุญาต first publication แบบปกติ (ไม่ใช้ `ci.skip`) executable rules จะสร้าง
เฉพาะ `check`; deploy/acceptance/ops ต้องเห็น
`CI_COMMIT_REF_PROTECTED == "true"` จึงจะถูกสร้าง หลัง protect branch,
environment, runner และตั้ง variables ครบแล้ว ต้องสร้าง **pipeline ใหม่** บน
protected `main` หรือ push reviewed follow-up commit ห้าม retry pipeline แรก
แล้วคาดว่า rules จะเปลี่ยน

## 4 ดูให้ครบสาม stage ไม่ใช่แค่ deploy เขียว

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

## 5 ถ้ามีปัญหา ใช้ manual job แทน SSH

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
  schedule เฉพาะ protected `main` แต่ยังต้องให้ staff ยืนยันว่า
  production-capable runner เป็น Protected จริงหรือจัด isolated branch
  runner/daemon ก่อน pipeline เต็ม tag/rules ไม่ใช่ isolation boundary
- **runner tag** ถ้า job ค้าง pending ให้ตรวจว่า runner ยังมี tag `team-08`
  ตรงกับ `.gitlab-ci.yml`; อย่าถอด tag เพื่อให้ไปรันบน runner อื่น
- **โควตาของ gateway** `acceptance` ยิงของจริงทุกครั้งที่ protected `main`
  เริ่ม full release pipeline
  (และ retry ได้สูงสุด 3 ครั้งเมื่อเจอ transport/5xx)
- **PDF/OCR** implementation ยังอยู่ภายใน core แต่ public proxy ต้องคืน 404
  ทั้งสอง alias และหน้าเว็บต้องไม่มี upload flow หลักฐานหนึ่งหน้าเดิม (221 วินาที,
  CPU ~1.93/2 cores, memory ชน 6 GiB) เป็นเหตุให้พัก capability นี้ การเปิดใหม่
  ต้องผ่าน correctness/provenance/resource acceptance แยกต่างหาก
