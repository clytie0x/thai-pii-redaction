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
มาตรา 4 (application exemptions). Indirect identifiers (IP address, MAC
address, cookie ID, location data) enter via ม.6's "ไม่ว่าทางตรงหรือทางอ้อม"
limb as read by Thai practitioner consensus. Citation audit 2026-08-26
(Task 1): no PDPC publication states this — the basis is the statute plus
consensus, not regulator guidance.

## Treatment levels

| Level | Treatment | Mechanism |
|---|---|---|
| **A** | Mask always | `detect()` emits a span entity; `anonymize()` masks it; leak guard enforces it |
| **B** | Quasi-identifier | `analyze()` reports it (reid-risk QI scan); never masked alone |
| **C** | Sensitive content (ม.26) | flagged in `analyze()` and, since 2026-08-27, masked as a person-linked span |
| **D** | Declared out of scope | documented refusal with rationale — the honest "no" |
| **E** | Not personal data under PDPA | documented so users know why it is absent |

## Level A — mask always (span entities)

**Amendment 2026-08-27 — the numbers below are a planning snapshot.** Every
recall/precision figure in this section is what gold measured on **2026-08-26**,
before the campaign's Wave-1 and Wave-2 work landed, and several have moved since
(`NAME` and `STUDENT_ID` among them). They are left as recorded rather than
hand-updated row by row: this record is a registry of *categories and treatment
levels*, and a table of numbers maintained in two places drifts in one of them.
**The live per-type numbers are in `docs/pdpa-coverage.md`**, refreshed from a
`python -m benchmark --source gold` run; where the two disagree, the profile wins.
The `campaign Wave 1` markers below have all shipped.

| Category (PDPA basis) | data_type | Status 2026-08-26 |
|---|---|---|
| ชื่อ นามสกุล (ม.6) | `NAME`, `SURNAME` | shipped, gold R 0.991 / P 0.987 |
| เลขบัตรประชาชน (ม.6) | `THAI_ID` | shipped, 1.000/1.000, mod-11 checksum |
| เลขประกันสังคม (ม.6) | covered via `THAI_ID` | alias verdict 2026-08-26; no new detector, foreign-worker gap recorded |
| เลขผู้เสียภาษีบุคคลธรรมดา (ม.6) | covered via `THAI_ID` | alias verdict 2026-08-26; no new detector, foreigner-TIN gap recorded |
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
| **IP address** (indirect identifier, ม.6 "ทางอ้อม") | `IP_ADDRESS` | **campaign Wave 1** |
| **MAC address** (indirect identifier, ม.6 "ทางอ้อม") | `MAC_ADDRESS` | **campaign Wave 1** |
| **เลขโฉนดที่ดิน** (ม.6, links person to property) | `LAND_DEED_ID` | **campaign Wave 1**; shape frozen 2026-08-26 — 1–6 digits, cue-gated, no checksum |
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

**Amendment 2026-08-27 — this section's status is superseded, its registry is not.**
The two status sentences below are flipped inline: person-linked span masking
**shipped on 2026-08-27**, so ม.26 content is no longer flag-only and the proxy no
longer forwards the sensitive sentence verbatim. The enumeration, the ten category
names and the catch-all rule are unchanged and still binding. As in Level A, no
numbers live here — `docs/pdpa-coverage.md` carries the live per-category gold
figures, and the frozen design and its accepted costs are in
`docs/decisions/2026-08-27-section26-span-masking.md`.

The statute's full enumeration: เชื้อชาติ, เผ่าพันธุ์, ความคิดเห็นทางการเมือง,
ความเชื่อในลัทธิ ศาสนาหรือปรัชญา, พฤติกรรมทางเพศ, ประวัติอาชญากรรม,
ข้อมูลสุขภาพ, ความพิการ, ข้อมูลสหภาพแรงงาน, ข้อมูลพันธุกรรม, ข้อมูลชีวภาพ,
and the open catch-all "ข้อมูลอื่นใดตามที่คณะกรรมการประกาศ".

amphrang categories (all 10 shipped as **span masking**, on by default, since
2026-08-27; they remain document-level flags as well): `RACE_ETHNICITY`,
`POLITICAL_OPINION`, `RELIGION`, `SEXUAL_BEHAVIOR`, `CRIMINAL_RECORD`,
`HEALTH`, `DISABILITY`, `LABOR_UNION`, `GENETIC`, `BIOMETRIC` — keyword scan
in `report.py::_SECTION26_KEYWORDS` plus the semantic detector
(`sensitive_detector.py`, `[ml]` extra only), and the span detector
`detectors/sensitive_span.py` that does the masking.

**The gap this registry named as the flagship is closed.** It was: flags are
doc-level, so the sanitizing proxy forwarded the sensitive sentence verbatim, and
a document saying "นายสมชายเป็นมะเร็ง" masked the name and shipped the diagnosis.
Campaign Wave 2 delivered **person-linked span masking**: a sensitive phrase
becomes a maskable entity only when the surrounding segment is linked to a
person (name entity or personal reference). Sensitive words in impersonal
text ("วันสำคัญทางศาสนา") are not personal data under ม.26 and do not
flag — that distinction is the whole subject of the frozen design record.

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

## Frozen verdicts (campaign Task 1, 2026-08-26)

Full evidence, sources, and probe output:
`docs/decisions/2026-08-26-wave1-format-specs.md`.

1. **เลขประกันสังคม** — `thai_id_alias` (2026-08-26). สปส.1-03 field 2.3 makes
   the citizen ID the insured-person identifier; no new detector. Recorded gaps:
   the SSO-issued `เลขที่บัตรประกันสังคม` for foreign insured persons has no
   public format, and the citizen mod-11 is unverified for DOPA type-`0`
   numbers. `_RE_THAI_ID` is not loosened.
2. **เลขผู้เสียภาษีบุคคลธรรมดา** — `thai_id_alias` (2026-08-26). ประกาศอธิบดี
   กรมสรรพากร (ฉบับที่ 3), in force 1 ก.พ. 2555; no new detector. The legacy
   10-digit TIN is a **closed** gap (transition ended 31 ม.ค. 2556); the
   RD-issued 13-digit TIN for individuals without a citizen ID stays open.
3. **เลขโฉนดที่ดิน** — shape frozen (2026-08-26): **1–6 digits, cue-gated only,
   no checksum** (narrowed from the 1–8 candidate; กรมที่ดิน numbers deeds
   sequentially per อำเภอ from 1). `เลขที่ดิน`, `หน้าสำรวจ`, `ระวาง`, and condo
   `N/M` titles are out of scope. `LAND_DEED_ID` must score above the 0.85
   `ADDRESS` claim already made on `<deed number> ตำบล…`.
4. **IP / MAC citation audit** — the former "PDPC guidance" basis for IP address
   was **not supported** by either source cited below; no PDPC publication says
   it. The basis is ม.6's `ทางอ้อม` limb plus practitioner consensus, and the
   Level A / Level B placement of `IP_ADDRESS` is flagged in the record as a
   treatment choice rather than one the sources compel.

## Sources

- ราชกิจจานุเบกษา, พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562 —
  https://ratchakitcha.soc.go.th/documents/17082307.pdf (มาตรา 4, 6, 26)
- มาตรา-by-มาตรา mirrors — https://pdpa.sidata.plus/article-6/ ,
  https://pdpa.sidata.plus/article-26/
- Scope and exemptions — https://www.dharmniti.co.th/pdpa-scope-exceptions/
- Personal-data examples (general) —
  https://t-reg.co/blog/t-reg-knowledge/what-is-personal-data/ (checked
  2026-08-26: does **not** mention IP/MAC/cookie — do not cite it for those)
- Device identifiers as ข้อมูลส่วนบุคคล, practitioner consensus without
  attribution — https://www.marketingoops.com/data/personal-data-in-pdpa-2019/ ,
  https://www.dharmniti.co.th/pdpa-liability-for-business-owners/
- IP address in isolation vs in combination —
  https://pdpathailand.com/pdpa/content/article9943.php
- Repo inventory verified against `benchmark/types.py`,
  `amphrang/engine/anonymizer/token_generator.py`,
  `amphrang/engine/report.py`, `amphrang/engine/reid_risk.py`,
  `amphrang/engine/sensitive_detector.py` (read-only, 2026-08-26).
