# PDPA Coverage Profile

Profile version `pdpa-profile-v1`. Measured on gold `gold-v7` (dated
2026-08-27, 332 documents, 1031 entities); numbers below are a live
`python -m benchmark --source gold` run against that set, not a copy of an
older report. This is the public conformance artifact for amphrang against
พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562 (PDPA); it is generated FROM, and must
be kept consistent with, the canonical registry at
`docs/decisions/2026-08-26-pdpa-data-ontology.md` (levels A-E, including the
frozen verdicts section) — that record is the source of truth, this document
is its published summary. The ม.26 catch-all ("ข้อมูลอื่นตามที่คณะกรรมการ
ประกาศ") has no fixed list; a new PDPC announcement enters amphrang's
coverage only by a dated amendment to the ontology record, which then flows
into this profile.

`scripts/check_release.py`'s `check_profile()` gate enforces that every
`data_type` this document backtick-references in a table row matches
`TOKEN_LABEL` in `amphrang/engine/anonymizer/token_generator.py` exactly, in
both directions. A row can go stale relative to the code only by breaking
that gate.

## Level A — mask always (span entities)

`detect()` emits a span; `anonymize()` masks it; the leak guard enforces it.

| data_type | Thai label | PDPA basis | gold recall | gold precision |
|---|---|---|---|---|
| `NAME` | ชื่อ | ม.6 | 0.993 | 0.989 |
| `SURNAME` | นามสกุล | ม.6 | unmeasured (not scored as a distinct gold category) | unmeasured |
| `THAI_ID` | บัตรประชาชน | ม.6 | 1.000 | 1.000 |
| เลขประกันสังคม | covered via `THAI_ID` | ม.6, alias verdict 2026-08-26 | see `THAI_ID` row | see `THAI_ID` row |
| เลขผู้เสียภาษีบุคคลธรรมดา | covered via `THAI_ID` | ม.6, alias verdict 2026-08-26 | see `THAI_ID` row | see `THAI_ID` row |
| `PASSPORT` | หนังสือเดินทาง | ม.6 | 1.000 | 0.962 |
| `DRIVER_LICENSE` | ใบขับขี่ | ม.6 | 1.000 | 1.000 |
| `PHONE` | เบอร์โทรศัพท์ | ม.6 | 0.991 | 1.000 |
| `EMAIL` | อีเมล | ม.6 | 1.000 | 1.000 |
| `ADDRESS` | ที่อยู่ | ม.6 | 1.000 | 0.973 |
| `POSTAL_CODE` | รหัสไปรษณีย์ | ม.6 | unmeasured (not scored as a distinct gold category) | unmeasured |
| `DATE_OF_BIRTH` | วันเกิด | ม.6 | 1.000 | 1.000 |
| `BANK_ACCOUNT` | บัญชีธนาคาร | ม.6 | 1.000 | 0.973 |
| `CREDIT_CARD` | บัตรเครดิต | ม.6 | 1.000 | 1.000 |
| `IBAN` | ไอแบน | ม.6 | unmeasured (no gold IBAN instances) | unmeasured |
| `VEHICLE_PLATE` | ทะเบียนรถ | ม.6 | 0.963 | 1.000 |
| `HOUSE_REG_ID` | รหัสประจำบ้าน | ม.6 | 1.000 | 1.000 |
| `GPS_COORD` | พิกัด | indirect identifier, ม.6 ทางอ้อม | 1.000 | 1.000 |
| `LINE_ID` | ไลน์ไอดี | ม.6 | 1.000 | 1.000 |
| `STUDENT_ID` | รหัสนักศึกษา | ม.6 | 0.862 | 1.000 |
| `MEDICAL_ID` | เลขเวชระเบียน | ม.6 | unmeasured (no gold MEDICAL_ID instances) | unmeasured |
| `IP_ADDRESS` | ไอพี | indirect identifier, ม.6 ทางอ้อม | 1.000 | 1.000 |
| `MAC_ADDRESS` | แมคแอดเดรส | indirect identifier, ม.6 ทางอ้อม | 1.000 | 1.000 |
| `LAND_DEED_ID` | โฉนด | ม.6, links person to property | 1.000 | 1.000 |
| `JURISTIC_ID` [^juristic] | ทะเบียนนิติบุคคล | outside PDPA scope (juristic person) | 1.000 | 1.000 |
| `LOCATION`, `DATE`, `ORGANIZATION`, `ID_NUMBER` [^fallback] | สถานที่ วันที่ องค์กร รหัสอ้างอิง | recall-net fallback labels, not PDPA categories | unmeasured (not scored as gold categories) | unmeasured |

[^juristic]: outside PDPA scope (juristic person) — business-confidentiality
    feature. Shipped because a juristic-entity identifier is
    business-sensitive, not because PDPA (a natural-person law, ม.6) requires
    it. Kept in this table because it is a Level A `detect()`/`anonymize()`
    span mechanically, not because it is Level A legally — see the ontology's
    Level E for the legal classification.

[^fallback]: These four exist to keep detection honest when no more specific
    PDPA category fits — they are a recall net, not categories PDPA itself
    names. They do not appear as their own gold-annotated categories, so
    "gold recall/precision" does not apply to them the way it does to a named
    PDPA type.

## Level B — quasi-identifiers (analyze-only)

Detected by `amphrang/engine/reid_risk.py` (`_QI_PATTERNS`); reported via
`analyze()`'s re-identification-risk scan (+10 per QI type found, forced
F-range for gender + district + (DOB|age)). Never masked on its own — a QI
alone is not personal data, only a re-identification signal.

| QI | Thai | Mechanism |
|---|---|---|
| gender (title) | เพศ (คำนำหน้า) | `analyze()` QI scan, `nang`/`nai`/etc. cue |
| date_of_birth | วันเกิด | `analyze()` QI scan, date-shape cue |
| age | อายุ | `analyze()` QI scan, อายุ/ขวบ cue |
| district | แขวง/ตำบล | `analyze()` QI scan |
| province | จังหวัด | `analyze()` QI scan |
| occupation | อาชีพ | `analyze()` QI scan |
| religion | ศาสนา | `analyze()` QI scan |
| nationality | สัญชาติ | `analyze()` QI scan |
| body metrics | น้ำหนัก ส่วนสูง | `analyze()` QI scan |

## Level C — ม.26 sensitive content

The statute enumerates เชื้อชาติ เผ่าพันธุ์, ความคิดเห็นทางการเมือง, ความเชื่อ
ในลัทธิ ศาสนาหรือปรัชญา, พฤติกรรมทางเพศ, ประวัติอาชญากรรม, ข้อมูลสุขภาพ,
ความพิการ, ข้อมูลสหภาพแรงงาน, ข้อมูลพันธุกรรม, ข้อมูลชีวภาพ, and the open
catch-all "ข้อมูลอื่นใดตามที่คณะกรรมการประกาศ" (see the header note on how
that catch-all enters this registry).

Today: doc-level keyword flagging in `analyze()`
(`report.py::_SECTION26_KEYWORDS`, plus the semantic detector
`sensitive_detector.py` under the `[ml]` extra), and, since Task 9/10 of this
campaign, person-linked span masking — a sensitive phrase becomes a maskable
`detect()`/`anonymize()` span only when its segment is linked to a person
(name entity, title+name, or a first-person pronoun). Sensitive words in
impersonal text ("วันสำคัญทางศาสนา") must not flag; that distinction, and its
accepted trade-offs, are the whole subject of the frozen design record
`docs/decisions/2026-08-27-section26-span-masking.md`.

| data_type | Thai label (token) | PDPA basis (ม.26) | gold n | gold recall | gold precision |
|---|---|---|---|---|---|
| `RACE_ETHNICITY` | เชื้อชาติ | เชื้อชาติ เผ่าพันธุ์ | 2 [^floor] | 1.000 | 1.000 |
| `POLITICAL_OPINION` | ความเห็นการเมือง | ความคิดเห็นทางการเมือง | 2 [^floor] | 1.000 | 1.000 |
| `RELIGION` | ศาสนา | ความเชื่อในลัทธิ ศาสนาหรือปรัชญา | 3 [^floor] | 0.667 | 1.000 |
| `SEXUAL_BEHAVIOR` | พฤติกรรมทางเพศ | พฤติกรรมทางเพศ | 2 [^floor] | 1.000 | 1.000 |
| `CRIMINAL_RECORD` | ประวัติคดี | ประวัติอาชญากรรม | 3 [^floor] | 1.000 | 1.000 |
| `HEALTH` | ข้อมูลสุขภาพ | ข้อมูลสุขภาพ | 30 [^health] | 0.333 | 0.667 |
| `DISABILITY` | ความพิการ | ความพิการ | 3 [^floor] | 1.000 | 1.000 |
| `GENETIC` | ข้อมูลพันธุกรรม | ข้อมูลพันธุกรรม | 3 [^floor] | 1.000 | 1.000 |
| `LABOR_UNION` | สหภาพแรงงาน | ข้อมูลสหภาพแรงงาน | 2 [^floor] | 1.000 | 1.000 |
| `BIOMETRIC` | ข้อมูลชีวภาพ | ข้อมูลชีวภาพ | 3 [^floor] | 1.000 | 1.000 |

[^floor]: n < 20 — below the benchmark's reportable-n floor. Treat the
    recall/precision figure as anecdotal, not a stable estimate; a single
    document flips it by a large margin.

[^health]: `HEALTH` is the one Level C category that clears n>=20 on gold-v7,
    so its number is the one worth trusting: recall 0.333 with precision
    0.667. The gap has a known origin: the keyword scan
    (`_SECTION26_KEYWORDS["HEALTH"]`) is a small, literal cue vocabulary
    (โรค, การรักษา, ผล(การ)ตรวจ, สุขภาพ, ประวัติ(การ)รักษา), so any gold HEALTH
    phrasing outside that vocabulary is a miss by construction, not a model
    failure to fix by tuning. `check_release.py` scans a Thai reader would
    have to trust this table over any older document that quotes a
    different HEALTH number — this one is live.

Person-linkage design pointer:
`docs/decisions/2026-08-27-section26-span-masking.md`. It records, among
other things, an accepted cost worth naming here because it directly affects
who gets masked: a **bare full name with no title and no pronoun**, in a
segment that happens to carry register vocabulary (e.g. "แนวทางเวชปฏิบัติ"),
loses its linked sensitive span — the guard that fixed a worse false-positive
(fabricating a ม.26 claim about a person absent from the document) cannot
distinguish that case from a genuine CRF `NAME` false positive. Zero gold
documents currently exercise it; it is pinned by
`test_f4_accepted_cost_a_bare_real_name_in_a_register_segment_no_longer_anchors`.

## Level D — declared out of scope (the honest "no")

| Data | Why |
|---|---|
| รูปถ่าย ภาพใบหน้า เสียง ไฟล์ biometric ดิบ | amphrang is a text library; descriptions of biometrics in text ARE covered (`BIOMETRIC` flag) |
| Cookie ID, device ID, platform user ID | no stable text shape; masking every opaque token would destroy utility. Revisit if a real deployment shows a bounded shape (v1 refusal, recorded in the ontology) |
| ข้อมูลเครดิตบูโร | ม.4(6) exempts credit-bureau data governed by its own law |

## Level E — not personal data under PDPA

- ข้อมูลผู้ถึงแก่กรรม (excluded by the ม.6 definition).
- ข้อมูลนิติบุคคล — `JURISTIC_ID` stays shipped as a business-confidentiality
  feature (see the Level A footnote), not because PDPA requires it.
- Data fully anonymized so no person is identifiable.
- Activities exempted by ม.4 (personal/household use, state security organs,
  press/art under ethics codes, parliament/courts, credit-bureau data).

## Known gaps

- **Foreign-worker SSO number** — the SSO-issued `เลขที่บัตรประกันสังคม` for
  foreign insured persons has no public format documented anywhere amphrang
  could verify; the `THAI_ID` alias verdict only covers the citizen-ID case.
- **RD foreigner TIN** — the 13-digit RD-issued TIN for individuals without a
  Thai citizen ID stays an open gap (the legacy 10-digit TIN transition
  closed 31 ม.ค. 2556 and is not a live gap).
- **Cookie / device IDs** — declared out of scope (Level D) for lack of a
  stable text shape; not a "we forgot", a recorded refusal.
- **The F4 accepted trade** — the ม.26 person-linkage guard that stops a CRF
  `NAME` false positive from fabricating a sensitive claim about an absent
  person also strips the linked span from a real bare full name (no title,
  no pronoun) sitting in a register-vocabulary segment; see the Level C
  section above.
- **Blind-corpus coverage** — the held-out blind evaluation set predates this
  campaign (2026-08-26 onward): none of the Wave 1 types (`IP_ADDRESS`,
  `MAC_ADDRESS`, `LAND_DEED_ID`), Wave 1 QIs (nationality, body metrics), or
  Level C sensitive-span masking are exercised by it. Only the gold-v7 numbers
  in this document reflect them.
