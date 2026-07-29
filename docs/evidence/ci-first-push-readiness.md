# หลักฐาน ทำให้ push แรกขึ้น GitLab เขียว (29 ก.ค. 2569)

ปิดช่องว่างที่ระบุไว้ในดีไซน์ `docs/superpowers/specs/2026-07-29-port-ci-first-push-green-design.md`
คือ `.gitlab-ci.yml` ไม่เคยถูก runner จริงรันเลย และหลักฐานเดิมทั้งหมดมาจาก
`tests/smoke.py` ที่ยิงคำสั่ง **เทียบเท่า** ที่ CI ทำ ไม่ใช่ตัวที่ CI จะรัน

ไม่มี secret และไม่มี PII จริงในเอกสารนี้ ข้อมูลทดสอบทุกชิ้นเป็นของแต่ง

## S0 ตัวจำลองเชื่อถือได้แค่ไหน

ผลดิบ `tests/out/s0-runner-simulation.json`

| ข้อ | ผล |
|---|---|
| S0.1 socket mount สั่ง daemon ของ host ได้ | ผ่าน `docker ps` จากในคอนเทนเนอร์เห็นของบน host, server 29.6.1 |
| S0.2 `--network host` ถึงพอร์ตที่ publish บน 127.0.0.1 | ผ่าน HTTP 200 ไม่ต้องใช้ทางถอย `host.docker.internal` |
| S0.3 job รันด้วย shell ตัวไหน | `/bin/busybox` และไม่มี bash ในอิมเมจ |

**ข้อสันนิษฐานสองข้อในดีไซน์ผิด** บันทึกไว้แทนที่จะเงียบ เพราะคำทำนายที่ถูกทิ้ง
เงียบ ๆ ภายหลังดูไม่ต่างจากคำทำนายที่ไม่เคยตรวจ

- `done < <(grep ...)` ใน check stage — BusyBox build นี้**รองรับ** process
  substitution รันตัวสคริปต์จริงทั้งก้อนใต้ `sh -e` แล้วออก 0 พร้อม `check passed`
- `\s` ใน `grep -oE` — BusyBox grep รับได้ ให้ผลเท่ากับ `[[:space:]]` (2 hit เท่ากัน)
- ส่วน loop ตรวจ bind mount ที่ไม่ match อะไรเลย เป็นเพราะ `docker-compose.yml`
  ไม่มี `volumes:` เลย ไม่ใช่เพราะ pattern พัง ป้อน compose ที่มี `./rel:/app`
  กับ `/data/hack/team08/o:/o` เข้าไป pattern จับได้ทั้งคู่

check stage จึงไม่ต้องเขียนใหม่

## S1 หมุด vendored slice

`46c1f9a` → `00b3ffe` 59 → 62 ไฟล์ `sync --check` ผ่านบนหมุดใหม่

หมุดเก่าเก่ากว่างานแก้ Thai PDF shaping ของ upstream ผลที่ตามมาไม่ใช่เรื่องความสวย
`core/requirements.lock` ไม่มี `uharfbuzz` reportlab ปิด HarfBuzz shaping เงียบ ๆ
เมื่อไม่มีมัน และ `/analyze-report` อยู่ใน allowlist ของ nginx **ถ้า deploy ด้วย
หมุดเก่า รายงาน PDPA ที่ผู้ใช้โหลดจะวรรณยุกต์ซ้อนเพี้ยนทั้งฉบับ**

พิสูจน์หลังแก้ ดึง `/analyze-report` จาก stack ที่รันอยู่จริงผ่าน nginx พอร์ต 20071
แล้ว render ออกมาดู วรรณยุกต์ซ้อนขึ้นถูกทุกคำ (เสี่ยง ที่อยู่ อ่อนไหว ซ้ำ แวดล้อม)

## S2 สัญญาของ nginx proxy

`tests/nginx_contract.py` อยู่ใน check stage จริง ไม่ใช่เครื่องมือ local
รันกับ `api/Dockerfile` **ตัวจริง** โดยมี stub แทน core ที่สะท้อน path และ
ค่า header `X-AIGuard-Key` ที่ได้รับกลับมา

ห้าข้อที่ยืนยัน ผ่านครบ

1. เติม prefix กลับถูก 12 path (6 endpoint × unversioned และ `/v1`) core เห็น `/api/<ชื่อ>`
2. allowlist ปิดที่ proxy จริง 7 path ตาย 404 **และ stub ไม่ถูกเรียกเลย**
   (นับบรรทัด `docker logs` ก่อนหลัง ซึ่งเป็นสิ่งเดียวที่แยก 404 ของ proxy
   ออกจาก 404 ที่ core คืนมาหลังถูก forward)
3. key ถูกฉีดถึง core
4. query string ไม่เข้า access log (VAULT-4 บน Dozzle)
5. ทุก response มี `Cache-Control: no-store`

**พิสูจน์ว่าเทสแดงได้** เปลี่ยน `location = /detect` เป็น prefix match แล้ว
`/detectx` ทะลุถึง core ได้ 200 เทสแดงทั้งข้อสถานะและข้อ "ยังไปถึง core"

## S3 รัน job จริงในอิมเมจจริง

`tests/run_ci_local.py` ผลดิบอยู่ใน `tests/out/ci-local-*.json`

| job | ผล | เวลา |
|---|---|---|
| check | ผ่าน | 12.9s |
| deploy | ผ่าน | 167.2s (อุ่น) |
| acceptance | ผ่าน | 4.7s ยิง thaillm-8b จริง ด้วย PII สังเคราะห์ |

deploy รอบนี้ยังเป็นตัวพิสูจน์ว่า lock ใหม่ build ได้จริง `uharfbuzz` ลงในอิมเมจ
เรียบร้อย ทั้งสาม service ขึ้น healthy

**บั๊กของตัวจำลองเองที่เจอระหว่างทาง** รอบแรกรายงาน
`unrecognized arguments: --check` สำหรับ flag ที่มีอยู่จริง สาเหตุคือ stdin pipe
แบบ text ของ Windows แปลง `\n` เป็น `\r\n` ทุกอาร์กิวเมนต์เลยมี carriage return
ต่อท้าย นี่คือตัวจำลอง**กุ**บั๊กให้ pipeline ซึ่งเป็นสิ่งเดียวที่ตัวจำลองห้ามทำ
แก้เป็นเขียน bytes แล้ว

## เวลา build

| การวัด | เวลา | ขนาดอิมเมจ |
|---|---|---|
| core `--no-cache` | 161s | 2.95GB |
| deploy job อุ่นทั้ง stack | 167.2s | — |

job timeout ของผู้จัดคือ 20 นาที ตัวเลขนี้ห่างประมาณ 7 เท่า

เลือกวัดด้วย `docker build --no-cache` ของ core แทน `docker builder prune -af`
ทั้งเครื่องตามที่ดีไซน์เขียนไว้ เพราะ prune ทำลาย cache ของโปรเจกต์อื่นทุกตัวบน
เครื่องนี้ด้วย ราคาของความต่างคือ **เลขนี้เป็นขอบล่าง** ชั้น `FROM` และ apt
ยังมาจากของที่มีอยู่ บน runner ที่ว่างเปล่าจริงจะช้ากว่านี้ และเครื่องนี้ไม่ใช่
runner ของผู้จัดอยู่แล้ว เน็ตกับดิสก์คนละตัว ตัวเลขบอกลำดับความใหญ่ ไม่ใช่คำรับประกัน

## ที่ยังไม่ได้พิสูจน์ และพิสูจน์ในเครื่องไม่ได้

- runner จริงของผู้จัด tag การจัดคิว cache artifact
- เวลา build บนเครื่องที่ไม่มีอะไรอยู่เลย
- พฤติกรรมของ reverse proxy ของแพลตฟอร์มที่ตัด `/api` ออกจริง ๆ
  (จำลองด้วยการยิงตรงเข้าพอร์ต 20071 ซึ่งเป็นรูปเดียวกับที่ deploy job ของผู้จัดทำ)
- GitLab รัน `script` ทีละรายการแล้วหยุดที่รายการแรกที่ล้ม ตัวจำลองต่อเป็นก้อนเดียว
  แล้วรันใต้ `sh -e` ใกล้แต่ไม่เท่า
