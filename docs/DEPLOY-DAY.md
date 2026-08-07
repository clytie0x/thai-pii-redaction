# วันที่ deploy ต้องทำอะไรบ้าง

ทุกอย่างในไฟล์นี้เป็นงานที่ **เจ้าของต้องทำเอง** เพราะออกนอกเครื่องทั้งหมด
ไฟล์นี้ใช้ได้ต่อเมื่อ preflight ที่ยังเหลือใน `STATE.md` ผ่านครบ หลักฐานแบบ
dated working tree ครอบคลุม current-core `8c6efef`, caller-auth ADR,
response minimization, Docker, Tokenmind/OCR smoke, soak/failure และ local
pipeline approximation แล้ว แต่ยังห้ามใช้แทน exact committed rebuild:
resource/PDF gate กับ live Tokenmind หลัง rotate credential ต้องปิดก่อน

Participant Guide ทางการยืนยัน team/port/proxy/CI/resource/log/secret shape
แล้ว แต่ไม่ได้ยืนยันว่า candidate ปัจจุบันผ่าน privacy หรือทำงานบน runner จริง
ไฟล์นี้คือลำดับของวันจริงหลัง local gate ปิด

เวลาที่ควรเผื่อ ประมาณหนึ่งชั่วโมงถ้าไม่มีอะไรผิด และเผื่ออีกเท่าตัวถ้าผิด
เดดไลน์ของงานคือ 17 ส.ค. 2569 นำเสนอ 19 ส.ค.

## 1 สร้าง project บน GitLab

`gitlab.nectec.or.th` ใน group ของทีม (สิทธิ์ Maintainer มีแล้ว)
ชื่อ project ไม่ผูกกับอะไรในโค้ด แต่ `TEAM: "team08"` ใน `.gitlab-ci.yml`
กับพอร์ต 20070/20071 ผูกกับทีมแน่นอน อย่าแก้

## 2 ตั้ง CI/CD Variables ก่อน push

protect branch `main` ก่อน แล้วตั้ง Settings → CI/CD → Variables เป็น
**Protected + Masked** ทั้งสี่ตัว พร้อม environment scope `team08`
จากนั้น protect environment `team08` และกำหนด **Allowed to deploy** เฉพาะ
owner/maintainers

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

repo นี้ยังไม่มี remote เลย

```bash
git remote add origin <ssh หรือ https ของ project>
git push -u origin main
```

pipeline จะวิ่งเอง `check` → `deploy` → `acceptance`

## 4 ดูให้ครบสาม stage ไม่ใช่แค่ deploy เขียว

- **check** ตรวจกติกา compose ของผู้จัด ความตรงของ vendored slice กับ
  upstream Git object, caller-auth, executable frontend session contract
  และสัญญาของ nginx/web proxy
- **deploy** build แล้ว `up -d` แล้วรอ healthcheck ของ `team08-api-1`
  และ `team08-web-1`
  ชื่อ service ต้องเป็น `api` เท่านั้น deploy job ของผู้จัด `docker inspect`
  ชื่อนั้นตรง ๆ
- **acceptance** login, ยิง PII สังเคราะห์ผ่านทั้งสายไปถึง thaillm-8b จริง,
  ตรวจ minimized response, allowlist, report/one-page OCR และ scan log ทุกบรรทัด
  ที่ container ปัจจุบันยังเก็บไว้
  **นี่คือ stage เดียวที่จับได้ว่า key ไปไม่ถึง container** เพราะ healthcheck
  ยังเขียวได้ในความล้มเหลวแบบนั้น (`/health` ไม่ถูก gate)

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
- **runner isolation** config ปัจจุบัน schedule เฉพาะ protected `main` แต่
  ยังต้องให้ staff ยืนยันว่า production-capable runner เป็น Protected จริง
  หรือจัด isolated branch runner/daemon ก่อน push
- **runner tag** ถ้า job ค้าง pending ให้ปลดคอมเมนต์ `tags:` ใน
  `.gitlab-ci.yml` ตาม tag ที่เห็นใน Group → Settings → CI/CD → Runners
- **โควตาของ gateway** `acceptance` ยิงของจริงทุกครั้งที่ push `main`
  (และ retry ได้สูงสุด 3 ครั้งเมื่อเจอ transport/5xx)
- **PDF resource** one-page OCR บนเครื่องพัฒนาใช้เวลาประมาณ 214 วินาทีและ
  แตะเพดาน memory 6 GiB ในชุด probe; ห้ามตีความ cap 20 หน้าเป็น capability
  จนกว่าจะลด/พักเส้นนี้หรือแก้ execution model และผ่าน platform measurement
