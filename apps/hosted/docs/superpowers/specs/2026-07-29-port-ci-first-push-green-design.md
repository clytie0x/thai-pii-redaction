# ดีไซน์ ทำให้ push แรกขึ้น GitLab เขียว (29 ก.ค. 2569)

สถานะ อนุมัติดีไซน์แล้ว รอแผนลงมือ
ขอบเขต repo นี้ล้วน ไม่แตะ repo หลักและไม่ push ขึ้น GitLab

## 1 ปัญหา

port repo ประกอบครบและผ่าน checklist ก-ฌ บน Docker ในเครื่องแล้ว
(`docs/evidence/checklist-results.md`) แต่ `.gitlab-ci.yml` ของมัน
**ไม่เคยถูกรันโดย runner จริงสักครั้ง** เพราะยังไม่มี project บน
gitlab.nectec.or.th

หลักฐานที่มีทั้งหมดมาจาก `tests/smoke.py` ซึ่งรันบน Windows ด้วย venv ของ
repo หลัก และยิงคำสั่งที่ **เทียบเท่า** สิ่งที่ CI ทำ ไม่ใช่ตัวสคริปต์ที่ CI
จะรันจริง ความต่างนี้ซ่อนบั๊กได้ทั้งคลาส

ตัวอย่างที่พบระหว่างออกแบบ check stage ใช้ `done < <(grep ...)` ซึ่งเป็น
process substitution ของ bash ล้วน ขณะที่ image ที่ประกาศคือ `docker:27.3.1`
(alpine ให้ ash ไม่ให้ bash) `before_script` ลง bash ทีหลังก็จริง แต่ runner
เลือก shell ตอนเริ่ม container ไม่ใช่หลัง apk add **ยังไม่ยืนยันว่าพังจริง**
แต่นี่คือรูปแบบของบั๊กที่ทำให้ push แรกแดงโดยเสียเวลาเปล่า

ราคาของช่องว่างนี้สูงกว่าปกติ เพราะ deploy บนแพลตฟอร์มคือการ **แทนที่**
service ที่รันอยู่ ความผิดพลาดที่เจอหลัง deploy คือความผิดพลาดที่ผู้ใช้เห็นแล้ว

## 2 เป้าหมาย

1. push ครั้งแรกขึ้น GitLab `main` แล้ว pipeline เขียวครบทั้ง check deploy
   acceptance โดยไม่ต้องนั่ง debug บน runner ของผู้จัด
2. มีตาข่ายถาวรที่จับได้ทันทีเมื่อมีคนแก้ nginx allowlist ผิด **ก่อน**
   ของขึ้น production ไม่ใช่หลัง
3. มีตัวเลขเวลา build เย็นจริง เทียบกับ timeout 20 นาทีของ runner

## 3 นอกขอบเขต

- ไม่ push ขึ้น GitLab และไม่สร้าง project (เป็นคำสั่งเจ้าของแยกต่างหาก)
- ไม่แตะ detection mask vault provider หรือโค้ดใด ๆ ใน `core/`
  (ยกเว้นการ re-sync ตามข้อ S1 ซึ่งคัดลอกจาก upstream ทั้งดุ้น)
- ไม่ทำงานคลื่น 2 (residue scan, caller salt, confidence, processing receipt)
- ไม่แก้ `web/index.html` ให้เป็น Material Design 3 (งานแยก ตัดสินทีหลัง)

## 4 ข้อจำกัดที่รู้ตัวและยอมรับ

- **การจำลอง runner เป็นการประมาณ ไม่ใช่ของจริง** GitLab รัน script ทีละ
  รายการและหยุดเมื่อรายการล้ม ตัวจำลองต่อบรรทัดแล้วรันด้วย `sh -e` ซึ่งใกล้
  แต่ไม่เท่า ข้อนี้ต้องเขียนไว้ในหัวไฟล์ของตัวจำลอง
- **เครื่องนี้ไม่ใช่ runner ของผู้จัด** เลขเวลา build บอกลำดับความใหญ่ว่า
  เสี่ยงชน 20 นาทีไหม ไม่ใช่คำรับประกัน เน็ตกับดิสก์คนละตัว
- Docker Desktop ต้องรันอยู่ตลอดงานนี้ WSL Ubuntu ไม่มี docker ของตัวเอง
- `sync --check` พิสูจน์ว่า `core/` ตรงกับ manifest เท่านั้น มัน **ไม่**
  พิสูจน์ว่า manifest ชี้ไป commit ที่ใหม่พอ ความสดเป็นการตัดสินใจของคน

## 5 โครงงาน สี่ก้อนเรียงตามลำดับบังคับ

### S0 spike พิสูจน์ว่าจำลองได้จริง

ด่านแรก แบบเดียวกับที่ E0 เคยเป็นด่านแรกของเฟสก่อน **ถ้าไม่ผ่านต้องกลับมา
ตัดสินใจใหม่ ไม่ใช่ดันต่อ**

ต้องพิสูจน์สามข้อ

| # | ข้อพิสูจน์ | วิธี |
|---|---|---|
| S0.1 | container `docker:27.3.1` ที่ mount docker socket สั่ง `docker compose up` แล้วสร้าง container บน daemon ของ host ได้จริง | รัน compose ของ repo นี้จากในตัว container แล้ว `docker ps` บน host เห็น |
| S0.2 | `--network host` บน Docker Desktop for Windows ทำให้ `curl 127.0.0.1:20071` จากในตัว CI container ถึง port ที่ compose publish | ยก stack แล้ว curl `/health` จากในตัว container |
| S0.3 | runner รัน script ด้วย shell ตัวไหน | ใส่ `readlink /proc/$$/exe` เป็นบรรทัดแรกของ script ที่จำลอง |

ทางถอยถ้า S0.2 ไม่ผ่าน ใช้ socket แต่ไม่ใช้ host network แล้วเรียกผ่าน
`host.docker.internal` แทน ซึ่ง **ไม่ตรงกับ runner** ต้องบันทึกเป็นข้อจำกัด
ของการจำลองอย่างชัดเจน ไม่ใช่แกล้งว่าเหมือน

ผลของ S0 ทั้งสามข้อเขียนลง `tests/out/` แล้วสรุปเข้า `docs/evidence/`

### S1 sync ไฟล์ที่ล้า

หมุดปัจจุบันคือ upstream `46c1f9a` main ของ repo หลักเดินไป 8 commit แล้ว
ในบรรดา 59 ไฟล์ที่ vendor มา เปลี่ยนไฟล์เดียวคือ `demo/playground.html`
(+170/-33 จากงาน Material Design 3)

ไฟล์นั้นไม่ถูกเสิร์ฟบน deployment เพราะ nginx allowlist ไม่เปิด `/demo`
ความเสี่ยงจึงต่ำ แต่ปล่อยไว้แปลว่า manifest โกหกว่าเราพอร์ตจาก main

งานคือ รัน `python sync/sync_from_upstream.py --from <repo หลัก>` จาก working
tree ที่สะอาด แล้ว commit `core/` กับ manifest ในคอมมิตเดียว ต้องมาก่อน S2
เพราะทุกอย่างหลังจากนี้ตรวจสถานะที่ sync แล้ว

### S2 `tests/nginx_contract.py` ตาข่ายถาวร

เทสที่เข้า check stage ของ `.gitlab-ci.yml` จริง ของที่ส่งมอบมีสามชิ้น
คือสคริปต์เทส ไดเรกทอรี `tests/stub-core/` และ **บรรทัดที่เพิ่มใน
`.gitlab-ci.yml` เรียกมัน** ขาดชิ้นสุดท้ายแปลว่าเทสไม่เคยรันบน runner

**ข้อบังคับทางเทคนิค** ต้องรันบน runner ได้ ซึ่งมีแต่ `python3` เปล่าจาก
`apk add` ไม่มี venv ไม่มี httpx ไม่มี pytest ดังนั้น **stdlib ล้วน**
(`urllib`, `subprocess`, `json`) และคืน exit code ไม่ศูนย์เมื่อล้ม รูปแบบ
เดียวกับ `tests/smoke.py` ที่เป็น python ธรรมดา ไม่ใช่ pytest

**โครงจำลอง** สามชิ้นบน docker network ชั่วคราว

- ตัวปลอมชื่อ `core` สร้างจาก `tests/stub-core/` (Dockerfile + default.conf
  บน `nginx:alpine`) ตอบ 200 ทุก path ด้วย body JSON ที่สะท้อน path ที่ได้รับ
  กับค่า header `X-AIGuard-Key` ที่ได้รับ ชื่อ container ต้องเป็น `core` เป๊ะ
  เพราะ `api/default.conf.template` hardcode `http://core:8000` ไว้
- ตัวจริงคือ image ที่ build จาก `api/Dockerfile` **ของจริง** ไม่ใช่สำเนา
  ตั้ง `AIGUARD_API_KEY` เป็นค่าทดสอบและ `NGINX_ENVSUBST_FILTER` ตามของจริง
- ยิงจากข้างนอกเข้า port ที่ publish

**ห้าข้อที่ยืนยัน**

1. **prefix ถูกเติมกลับ** 12 path ที่ต้องผ่าน (6 endpoint x unversioned และ
   `/v1`) ได้ 200 ครบ และ body สะท้อนว่า core เห็น `/api/<ชื่อ>`
2. **allowlist ปิดจริงที่ proxy** path ที่ต้องตาย (`/sanitize` `/reidentify`
   `/docs` `/openapi.json` `/api/health` `/detectx` `/v1/sanitize`) ได้ 404
   **และตัวปลอมไม่เคยถูกเรียก** ตรวจด้วยจำนวนบรรทัดใน `docker logs` ของตัวปลอม
   ก่อนและหลัง ข้อนี้แยก 404 ที่มาจาก proxy ออกจาก 404 ที่มาจาก core
3. **key ถูกฉีด** ค่าใน body ที่ตัวปลอมสะท้อนกลับตรงกับค่าทดสอบที่ตั้งไว้
4. **log ไม่มี query string** ยิง `/detect?q=SECRET_MARKER` แล้ว
   `docker logs` ของ api ไม่มีสตริงนั้น (VAULT-4 บน Dozzle)
5. **ไม่ cache** response ทุกตัวมี `Cache-Control: no-store`

**ต้นทุนที่เพิ่มใน check stage** build image nginx เล็กสองตัว หลักวินาที
ต่อ branch push รับได้

**การเก็บกวาด** ลบ container network และ image ทดสอบทุกครั้งแม้ล้มกลางทาง
(try/finally) ชื่อทุกอย่างมี prefix ที่ชนกับของ deployment ไม่ได้

### S3 `tests/run_ci_local.py` ตัวจำลอง pipeline

เครื่องมือในเครื่องล้วน **ไม่ถูกอ้างใน `.gitlab-ci.yml`** จึงไม่มีทางไปรัน
บน runner จริง

**วิธีทำงาน** รันบน Windows ด้วย python ของ venv repo หลัก (pyyaml 6.0.3 มีแล้ว)

1. อ่าน `.gitlab-ci.yml` ด้วย pyyaml
2. ต่อ `default.before_script` เข้ากับ `script` ของ job ที่สั่ง เป็นข้อความเดียว
3. โยนเข้า `docker run --rm --network host -v <socket> -v <repo>:/w -w /w`
   บน image `docker:27.3.1` ด้วย `sh -e`
4. ฉีด `TEAM` `BASE` `BASE_1` จาก `variables` ในไฟล์ และตัวแปร `APP_` จาก env
   ของเครื่อง

**อินเทอร์เฟซ**

```
python tests/run_ci_local.py --job check
python tests/run_ci_local.py --job acceptance
python tests/run_ci_local.py --all
python tests/run_ci_local.py --job deploy --cold
```

`--cold` ใช้ได้กับ `--job` เดียวเท่านั้น ใส่คู่กับ `--all` ต้อง error ออกมา
ตรง ๆ ไม่ใช่ยอมรับเงียบ ๆ (เหตุผลอยู่ใต้หัวข้อลำดับที่บังคับ)

`--cold` สั่ง `docker builder prune -af` ก่อนเริ่ม (เจ้าของอนุมัติให้ล้างทั้ง
เครื่องแล้ว) แล้วจับเวลา job นั้นแยกต่างหาก

**ลำดับที่บังคับ** รอบ `--cold` ต้องเป็นกิจกรรมสุดท้ายของงานทั้งชุด เพราะการ
prune ทำให้ทุก build หลังจากนั้นช้าไปหมดรวมทั้งของโปรเจกต์อื่น ลำดับที่ถูกคือ
รัน `--all` แบบอุ่นให้เขียวครบก่อน แล้วค่อยรัน `--job deploy --cold` รอบเดียว
เพื่อเก็บตัวเลข ห้ามใส่ `--cold` คู่กับ `--all` ในรอบเดียว

**ผลลัพธ์** JSON ลง `tests/out/ci-local-<ts>.json` ต่อ job เก็บ ชื่อ job
exit code เวลาที่ใช้ และ 50 บรรทัดท้ายของ output ที่ **กรอง secret ออกแล้ว**
รูปแบบเดียวกับ `smoke.py` แล้วสรุปถาวรเข้า `docs/evidence/`

**การจัดการ secret** อ่านจาก env ของเครื่องเท่านั้น (`TOKENMIND_API_KEY` และ
`AIGUARD_API_KEY` ที่สุ่มขึ้นสำหรับรอบทดสอบ) ไม่พิมพ์ค่าลง stdout ไม่เขียนลง
ไฟล์ผล และ redact ด้วยการแทนค่าที่รู้จักก่อนบันทึกทุกครั้ง

**สิ่งที่จะซ่อมเมื่อเจอ** ทุกอย่างที่ทำให้ job แดงถือเป็นบั๊กของ
`.gitlab-ci.yml` หรือ compose และแก้ในรอบนี้ ไม่ใช่จดไว้เฉย ๆ ตัวอย่างที่
คาดไว้แล้วคือ process substitution ใน check stage ถ้าพังจริงให้เขียนใหม่ด้วย
โครงสร้างที่ POSIX sh รองรับ (pipe เข้า while หรือ temp file) ไม่ใช่การหวังพึ่ง
ว่า runner จะมี bash

## 6 การจัดการความล้มเหลว

| สถานการณ์ | พฤติกรรมที่ต้องการ |
|---|---|
| S0 ข้อใดข้อหนึ่งไม่ผ่าน | หยุด รายงานเจ้าของ พร้อมทางถอยที่วัดผลได้ ไม่เดินต่อไป S2 |
| `nginx_contract.py` ล้ม | exit ไม่ศูนย์ พิมพ์ข้อที่ล้มพร้อมค่าที่ได้เทียบกับที่คาด ทำความสะอาด container ครบ |
| ตัวจำลองล้มเพราะ docker ไม่ขึ้น | ข้อความบอกให้เปิด Docker Desktop ไม่ใช่ stack trace เปล่า |
| build เย็นเกิน 20 นาที | ไม่ถือว่าเทสล้ม แต่บันทึกเป็นตัวเลขและยกเป็นเรื่องที่ต้องคุยกับ Staff พร้อมข้อมูล |
| secret ไม่มีใน env ตอนรัน acceptance | บอกชื่อตัวแปรที่ขาดแล้วหยุด ไม่รันแบบครึ่ง ๆ และไม่สลับไป provider จำลอง |

## 7 นิยามว่าเสร็จ

- S0 สามข้อมีผลบันทึกจริง หรือมีทางถอยที่บันทึกข้อจำกัดไว้ชัด
- `sync --check` ผ่านบนหมุดใหม่ที่ชี้ main ของ repo หลัก
- `tests/nginx_contract.py` ผ่านครบห้าข้อในเครื่อง และผ่านอีกครั้งเมื่อถูก
  เรียกจาก check stage ผ่านตัวจำลอง
- ทั้งสาม job ผ่านในตัวจำลอง โดย acceptance ยิง tokenmind จริง
- มีตัวเลขเวลา build เย็นและอุ่นบันทึกไว้ พร้อมคำเตือนว่าเครื่องนี้ไม่ใช่ runner
- `docs/evidence/` มีสรุปถาวรที่ไม่มี secret และไม่มี PII
- ทุก container กับ image ที่งานนี้สร้างถูกลบหมด stack `team08` กลับสู่สภาพเดิม

## 8 ความเสี่ยง

- **`--network host` บน Docker Desktop for Windows** เป็นความไม่แน่นอนหลัก
  ถ้าใช้ไม่ได้ ความเหมือนจริงของการจำลองลดลงและต้องบันทึกไว้ตรง ๆ
- **docker socket จาก container** อาจติดสิทธิ์บน named pipe ของ Windows
  ทางถอยคือรันตัวจำลองจาก WSL Ubuntu ซึ่งเห็น socket ผ่าน integration
- **การ prune ทั้งเครื่อง** ทำให้ build โปรเจกต์อื่นครั้งถัดไปช้า เจ้าของ
  อนุมัติแล้ว แต่ควรทำเป็นขั้นสุดท้ายของงาน
- **acceptance job ยิง gateway จริง** ใช้โควตาจริง Staff ยืนยันว่าไม่ติด limit
  แต่ยังต้องใช้ข้อมูลสังเคราะห์ล้วนตามกติกาเดิม
