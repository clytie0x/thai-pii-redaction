# PDPA data ontology — the canonical coverage registry

Date: 2026-08-26. Owner goal on record: amphrang becomes the reference
implementation ("the standard") for PDPA-compliant handling of Thai text
before it reaches an external AI. This record organizes every category of
data the law touches into one registry, assigns each category exactly one
treatment level, and is the source of truth the public **PDPA Coverage
Profile** (`docs/pdpa-coverage.md`, Wave 3 of the campaign plan) is written
from. A category not in this registry is a registry bug, not an implicit
"no".

Legal basis reviewed 2026-08-26 (agent research, sources at the bottom):
มาตรา 6 (definition of personal data — identifies a natural person directly
or indirectly; excludes the deceased), มาตรา 26 (sensitive categories),
มาตรา 4 (application exemptions), plus PDPC-aligned guidance on indirect
identifiers (IP address, cookie ID, location data).

## Treatment levels

| Level | Treatment | Mechanism |
|---|---|---|
| **A** | Mask always | `detect()` emits a span entity; `anonymize()` masks it; leak guard enforces it |
| **B** | Quasi-identifier | `analyze()` reports it (reid-risk QI scan); never masked alone |
| **C** | Sensitive content (ม.26) | today flag-only in `analyze()`; campaign target = person-linked span masking |
| **D** | Declared out of scope | documented refusal with rationale — the honest "no" |
| **E** | Not personal data under PDPA | documented so users know why it is absent |

## Level A — mask always (span entities)

| Category (PDPA basis) | data_type | Status 2026-08-26 |
|---|---|---|
| ชื่อ นามสกุล (ม.6) | `NAME`, `SURNAME` | shipped, gold R 0.991 / P 0.987 |
| เลขบัตรประชาชน (ม.6) | `THAI_ID` | shipped, 1.000/1.000, mod-11 checksum |
| เลขประกันสังคม (ม.6) | alias of `THAI_ID` (see open verdicts) | pending Task 1 verdict |
| เลขผู้เสียภาษีบุคคลธรรมดา (ม.6) | alias of `THAI_ID` (see open verdicts) | pending Task 1 verdict |
| หนังสือเดินทาง (ม.6) | `PASSPORT` | shipped, 1.000/0.962 |
| ใบขับขี่ (ม.6) | `DRIVER_LICENSE` | shipped, 1.000/1.000 |
| เบอร์โทรศัพท์ (ม.6) | `PHONE` | shipped, 0.988/1.000 |
| อีเมล (ม.6) | `EMAIL` | shipped, 1.000/1.000 |
| ที่อยู่ รหัสไปรษณีย์ (ม.6) | `ADDRESS`, `POSTAL_CODE` | shipped, 1.000/0.967 |
| วันเกิด (ม.6) | `DATE_OF_BIRTH` | shipped, 1.000/1.000 |
| บัญชีธนาคาร บัตรเครดิต IBAN (ม.6) | `BANK_ACCOUNT`, `CREDIT_CARD`, `IBAN` | shipped (IBAN unmeasured — profile must say so) |
| ทะเบียนรถ (ม.6) | `VEHICLE_PLATE` | shipped, 0.962/1.000 |
| รหัสประจำบ้าน (ม.6) | `HOUSE_REG_ID` | shipped, 1.000/1.000 |
| พิกัด GPS (indirect identifier) | `GPS_COORD` | shipped, 1.000/1.000 |
| LINE ID (ม.6) | `LINE_ID` | shipped, 1.000/1.000 |
| รหัสนักศึกษา (ม.6) | `STUDENT_ID` | shipped, 0.860/1.000 |
| เลขเวชระเบียน (ม.6) | `MEDICAL_ID` | shipped (unmeasured — profile must say so) |
| **IP address** (indirect identifier, PDPC guidance) | `IP_ADDRESS` | **campaign Wave 1** |
| **MAC address** (indirect identifier) | `MAC_ADDRESS` | **campaign Wave 1** |
| **เลขโฉนดที่ดิน** (ม.6, links person to property) | `LAND_DEED_ID` | **campaign Wave 1, shape pending Task 1** |
| Fallback labels (recall net) | `LOCATION`, `DATE`, `ORGANIZATION`, `ID_NUMBER` | shipped; honest-labels catch-alls, not PDPA categories themselves |

## Level B — quasi-identifiers (analyze-only)

Detected by `amphrang/engine/reid_risk.py` (`_QI_PATTERNS`); reported via
`analyze()` with a combination score, never masked alone.

| QI | Status |
|---|---|
| เพศ (คำนำหน้า), วันเกิด, อายุ, แขวง/ตำบล, จังหวัด, อาชีพ, ศาสนา | shipped |
| **สัญชาติ** | **campaign Wave 1** |
| **น้ำหนัก ส่วนสูง** | **campaign Wave 1** |

## Level C — ม.26 sensitive content

The statute's full enumeration: เชื้อชาติ, เผ่าพันธุ์, ความคิดเห็นทางการเมือง,
ความเชื่อในลัทธิ ศาสนาหรือปรัชญา, พฤติกรรมทางเพศ, ประวัติอาชญากรรม,
ข้อมูลสุขภาพ, ความพิการ, ข้อมูลสหภาพแรงงาน, ข้อมูลพันธุกรรม, ข้อมูลชีวภาพ,
and the open catch-all "ข้อมูลอื่นใดตามที่คณะกรรมการประกาศ".

amphrang categories (all 10 shipped as flags): `RACE_ETHNICITY`,
`POLITICAL_OPINION`, `RELIGION`, `SEXUAL_BEHAVIOR`, `CRIMINAL_RECORD`,
`HEALTH`, `DISABILITY`, `LABOR_UNION`, `GENETIC`, `BIOMETRIC` — keyword scan
in `report.py::_SECTION26_KEYWORDS` plus the semantic detector
(`sensitive_detector.py`, `[ml]` extra only).

**The gap this registry names as the flagship**: flags are doc-level; the
sanitizing proxy currently forwards the sensitive sentence verbatim. A
document saying "นายสมชายเป็นมะเร็ง" masks the name and ships the diagnosis.
Campaign Wave 2 targets **person-linked span masking**: a sensitive phrase
becomes a maskable entity only when the surrounding segment is linked to a
person (name entity or personal reference). Sensitive words in impersonal
text ("วันสำคัญทางศาสนา") are not personal data under ม.26 and must not
flag — that distinction is the design spike's whole job.

The ม.26 catch-all ("ข้อมูลอื่นตามที่คณะกรรมการประกาศ") has no fixed list;
the profile will state that new PDPC announcements enter this registry by a
dated amendment, which is what "being the standard" obliges us to track.

## Level D — declared out of scope (the honest "no")

| Data | Why |
|---|---|
| รูปถ่าย ภาพใบหน้า เสียง ไฟล์ biometric ดิบ | amphrang is a text library; descriptions of biometrics in text ARE covered (`BIOMETRIC` flag) |
| Cookie ID, device ID, platform user ID | no stable text shape; masking every opaque token would destroy utility. Revisit if a real deployment shows a bounded shape (v1 refusal, recorded here) |
| ข้อมูลเครดิตบูโร | ม.4(6) exempts credit-bureau data governed by its own law |

## Level E — not personal data under PDPA

- ข้อมูลผู้ถึงแก่กรรม (excluded by the ม.6 definition).
- ข้อมูลนิติบุคคล — `JURISTIC_ID` stays shipped as a business-confidentiality
  feature, and the coverage profile must label it "outside PDPA scope" so
  the legal mapping stays honest.
- Data fully anonymized so no person is identifiable.
- Activities exempted by ม.4 (personal/household use, state security organs,
  press/art under ethics codes, parliament/courts, credit-bureau data).

## Open verdicts (owned by campaign Task 1)

1. **เลขประกันสังคม**: expected verdict — for Thai insured persons the SSO
   number IS the 13-digit citizen ID, so coverage = `THAI_ID` alias (no new
   detector); verify, and check whether foreign-worker SSO numbers pass the
   citizen mod-11 (if not, decide cue-gated handling or a recorded gap).
2. **เลขผู้เสียภาษีบุคคลธรรมดา**: expected verdict — personal TIN = citizen
   ID since 2012; legacy 10-digit TINs are a recorded gap unless evidence
   shows they still circulate.
3. **เลขโฉนดที่ดิน**: shape unverified (candidate 1–8 digits, cue-gated
   only); Task 1 freezes it or records "shape too loose to ship".

## Sources

- ราชกิจจานุเบกษา, พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562 —
  https://ratchakitcha.soc.go.th/documents/17082307.pdf (มาตรา 4, 6, 26)
- มาตรา-by-มาตรา mirrors — https://pdpa.sidata.plus/article-6/ ,
  https://pdpa.sidata.plus/article-26/
- Scope and exemptions — https://www.dharmniti.co.th/pdpa-scope-exceptions/
- Personal-data examples incl. indirect identifiers —
  https://t-reg.co/blog/t-reg-knowledge/what-is-personal-data/ ,
  https://www.marketingoops.com/data/personal-data-in-pdpa-2019/
- Repo inventory verified against `benchmark/types.py`,
  `amphrang/engine/anonymizer/token_generator.py`,
  `amphrang/engine/report.py`, `amphrang/engine/reid_risk.py`,
  `amphrang/engine/sensitive_detector.py` (read-only, 2026-08-26).
