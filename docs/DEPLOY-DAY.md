# วันที่ deploy ต้องทำอะไรบ้าง

ทุกอย่างในไฟล์นี้เป็นงานที่ **เจ้าของต้องทำเอง** เพราะออกนอกเครื่องทั้งหมด
งานฝั่งเตรียมของจบแล้ว (ดู `STATE.md`) ไฟล์นี้คือลำดับของวันจริง

เวลาที่ควรเผื่อ ประมาณหนึ่งชั่วโมงถ้าไม่มีอะไรผิด และเผื่ออีกเท่าตัวถ้าผิด
เดดไลน์ของงานคือ 17 ส.ค. 2569 นำเสนอ 19 ส.ค.

## 1 สร้าง project บน GitLab

`gitlab.nectec.or.th` ใน group ของทีม (สิทธิ์ Maintainer มีแล้ว)
ชื่อ project ไม่ผูกกับอะไรในโค้ด แต่ `TEAM: "team08"` ใน `.gitlab-ci.yml`
กับพอร์ต 20070/20071 ผูกกับทีมแน่นอน อย่าแก้

## 2 ตั้ง CI/CD Variables ก่อน push

Settings → CI/CD → Variables ติ๊ก **Masked** ทั้งสองตัว

| ตัวแปร | ค่า |
|---|---|
| `APP_AIGUARD_API_KEY` | สุ่มขึ้นมาเอง เป็น key ที่ nginx ฉีดให้ core ไม่ใช่ของผู้จัด |
| `APP_TOKENMIND_API_KEY` | key ของผู้จัดที่ส่งมาทางอีเมล |

ถ้าลืมข้อนี้ deploy job จะล้มตั้งแต่ compose interpolation ด้วยข้อความ
`APP_AIGUARD_API_KEY is required` ซึ่งเป็นพฤติกรรมที่ตั้งใจ ไม่ใช่บั๊ก
บริการต้องไม่บูตแบบเปิดครึ่งใบ

## 3 ต่อ remote แล้ว push `main`

repo นี้ยังไม่มี remote เลย

```bash
git remote add origin <ssh หรือ https ของ project>
git push -u origin main
```

pipeline จะวิ่งเอง `check` → `deploy` → `acceptance`

## 4 ดูให้ครบสาม stage ไม่ใช่แค่ deploy เขียว

- **check** ตรวจกติกา compose ของผู้จัด ความตรงของ vendored slice กับ
  `PORT_MANIFEST.json` และสัญญาของ nginx proxy (`tests/nginx_contract.py`)
- **deploy** build แล้ว `up -d` แล้วรอ healthcheck ของ `team08-api-1`
  ชื่อ service ต้องเป็น `api` เท่านั้น deploy job ของผู้จัด `docker inspect`
  ชื่อนั้นตรง ๆ
- **acceptance** ยิง PII สังเคราะห์ผ่านทั้งสายไปถึง thaillm-8b จริง
  **นี่คือ stage เดียวที่จับได้ว่า key ไปไม่ถึง container** เพราะ healthcheck
  ยังเขียวได้ในความล้มเหลวแบบนั้น (`/health` ไม่ถูก gate)

ถ้า `deploy` เขียวแต่ `acceptance` แดง อย่าเพิ่งดีใจ บริการขึ้นแล้วแต่ทำงาน
ไม่ได้

## 5 ถ้ามีปัญหา ใช้ manual job แทน SSH

stage `ops` มี `logs` `ps` `restart` `shell-cmd` กดจากหน้า pipeline
และมี Dozzle ที่ `https://team08.aiforthai.in.th/logs/`

## สิ่งที่ยังไม่รู้ และจะรู้ตอน push จริงเท่านั้น

- **เวลา build บน runner ของผู้จัด** job timeout คือ 20 นาที core image
  ประมาณ 2.9 GB เพราะ bake โมเดล OCR ไว้ ตัวเลขที่วัดได้ในเครื่องนี้อยู่ใน
  `docs/evidence/` แต่เครื่องนี้ไม่ใช่ runner เน็ตกับดิสก์คนละตัว
  ถ้าชน 20 นาทีจริง ให้คุยกับ Staff พร้อมตัวเลข ไม่ใช่เดา
- **runner tag** ถ้า job ค้าง pending ให้ปลดคอมเมนต์ `tags:` ใน
  `.gitlab-ci.yml` ตาม tag ที่เห็นใน Group → Settings → CI/CD → Runners
- **โควตาของ gateway** `acceptance` ยิงของจริงทุกครั้งที่ push `main`
