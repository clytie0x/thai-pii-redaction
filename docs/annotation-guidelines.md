# Benchmark annotation guidelines

The standard for annotating the gold set (`benchmark/data/gold.jsonl`), for
authoring any blind-set version, and for adjudicating disputes. When a
document and these rules disagree, either the document is wrong (fix it) or
the rule is wrong (change the rule in its own PR, then re-check the corpora
against it). Do not resolve a dispute by inventing an unwritten convention.

Mechanics are enforced by `tests/test_benchmark_gold.py` and
`benchmark/blind.py validate_draft`; this file records the judgment calls a
validator cannot make.

## Markup mechanics

- Inline markup: `[[TYPE|value]]`. No nesting, no overlap, values are a
  single line, spans are exactly the PII value.
- Contextual cues stay OUTSIDE the brackets: titles (นาย/นาง/นางสาว/ดร.),
  field labels (ที่อยู่ / เบอร์โทร / เลขบัญชี / เกิดวันที่), and surrounding
  punctuation are context, not PII value.
- A value reads verbatim from the document — no normalization inside the
  brackets. If the document writes a phone with Thai digits or stray spaces
  (messy slice), the value carries them.

## The 19 types

These are the structured-PII types; the ten ม.26 sensitive categories are
annotated too, under their own rules (see "Sensitive spans" below). Nothing
outside those two families is annotated: NAME, ADDRESS, PHONE, EMAIL, THAI_ID,
BANK_ACCOUNT, CREDIT_CARD, DATE_OF_BIRTH, PASSPORT, VEHICLE_PLATE,
STUDENT_ID, JURISTIC_ID, DRIVER_LICENSE, LINE_ID, GPS_COORD, HOUSE_REG_ID,
IP_ADDRESS, MAC_ADDRESS, LAND_DEED_ID.

The corpora label **ground truth from the document's fiction**, not detector
behavior: if the document presents a value as a phone number, it is PHONE
whether or not any engine can find it. The product is recall-first — masking
an organization's mailbox or a company account is cheap, missing a person's
is not — so ownership rules below are deliberately broad.

| Type | Annotate | Do not annotate |
|---|---|---|
| NAME | Full personal names (first + last), first names when clearly a specific private person in context | Single-word nicknames, kinship references (พี่เอ), public figures acting in public capacity, organization names |
| ADDRESS | Any specific locatable address presented as an address — residential or organizational (house number + street/soi/tambon chain, building + road + district) | Vague neighborhood mentions (แถวลาดพร้าว), standalone room/house numbers outside an address context |
| PHONE | Any telephone number — personal, direct-line, office, or service — in any Thai format | Public short-code hotlines (1669, 1112, 4-digit numbers) |
| EMAIL | Any email address, including organizational role mailboxes (registrar@, billing@) | — |
| THAI_ID | Any mod-11-valid 13-digit value presented as identifying a person, whatever the surrounding document calls itself (บัตรประชาชน, ใบขับขี่, เลขผู้เสียภาษีบุคคล — a Thai personal taxpayer ID *is* the national ID) | Corporate registration numbers presented as an organization's (avoid 13-digit look-alikes entirely in negative docs) |
| BANK_ACCOUNT | Any bank-account number — personal, merchant, or company | Bill/invoice reference numbers |
| CREDIT_CARD | 13-16 digit card numbers (must pass Luhn) | Loyalty-card and gift-card numbers |
| DATE_OF_BIRTH | A date tied to birth by cue (เกิด / วันเกิด / ว.ด.ป. เกิด) | Business dates, appointment dates (those are DATE to the detector, and unannotated here) |
| PASSPORT | Passport numbers (Thai format `[A-Z]{2}\d{7}` or cue-bearing general format) | Visa/work-permit reference numbers without a passport cue |
| VEHICLE_PLATE | Thai license plates | Lot numbers, equipment/asset codes that merely resemble plates |
| STUDENT_ID | Codes the document's fiction presents as a student/enrollee code, with or without an explicit cue word (weak-cue documents are deliberate detector probes) | Order/receipt numbers even when 8-12 digits |
| JURISTIC_ID | 13-digit `0`-leading mod-11-valid registration number with a juristic cue in context (นิติบุคคล, ทะเบียนบริษัท, ทะเบียนพาณิชย์, เลขผู้เสียภาษี, tax id) | 0-leading checksum-valid runs without a juristic cue stay THAI_ID (the personal label is the recall-safe default) |
| DRIVER_LICENSE | 8-digit licence number with an explicit ใบขับขี่ / ใบอนุญาตขับขี่ / driving-licence cue | Invoice or document reference numbers sitting near someone else's ใบขับขี่ mention; bare 8-digit runs without the cue |
| LINE_ID | The LINE messaging handle following a LINE ID / ไลน์ไอดี cue, with or without a leading `@` | ไลน์ used as a queue/production-line noun (สายการผลิต, คิว) is not a cue |
| GPS_COORD | A `lat, lon` decimal pair (≥4 decimals each, in range) | Two-decimal price pairs sitting near the word พิกัด are not GPS_COORD |
| HOUSE_REG_ID | 11-digit house-registration code with a รหัสประจำบ้าน / เลขรหัสประจำบ้าน cue | Bare 11-digit runs without the cue (reference numbers, lot numbers) |
| IP_ADDRESS | IPv4 (dotted quad, each octet 0-255) or IPv6 (full or `::`-compressed) presented as a device/connection address | Version strings (`v2.4.1.9`, `รุ่น 10.15.7.2`) — same dotted-quad shape, not an address |
| MAC_ADDRESS | Six hex-byte pairs joined by one consistent separator (`:` or `-`) | Time ranges (`10:15-11:30`) — never six pairs, so never a real collision |
| LAND_DEED_ID | 1-6 digit deed number (`โฉนดเลขที่` / `โฉนดที่ดินเลขที่` / `เลขที่โฉนด` / `น.ส.3ก เลขที่` cue immediately before it, same line — the whole กรมที่ดิน form series counts: น.ส.3/3ก/3ข and น.ส.4/4ก/4ข/4ค/4ง/4จ) — no checksum exists, so the cue is the entire evidence | เลขที่ดิน (parcel-within-survey-sheet number), หน้าสำรวจ (survey-page number), ระวาง (survey-sheet number) — sibling numbers frequently printed in the same sentence as the deed number, never annotated even when digits-only and adjacent; a bare `เลขที่ <digits>` with no โฉนด-family cue (a PO/order/document number) stays unannotated too |

Quasi-identifiers the DETECTOR flags on purpose but the corpora never label:
organization names, provinces/districts standing alone, postal codes, generic
dates. A detector prediction of those types on a benchmark document is scored
as a false positive by construction — that cost is accepted and consistent
across gold and blind; do not "fix" it by adding those types to a corpus.

## Sensitive spans (มาตรา 26)

Added for gold-v7. Ten more annotated types, all prose rather than structured
identifiers: RACE_ETHNICITY, POLITICAL_OPINION, RELIGION, HEALTH,
SEXUAL_BEHAVIOR, CRIMINAL_RECORD, DISABILITY, LABOR_UNION, GENETIC, BIOMETRIC.
They are a second annotated family, not new members of the 19: the synthetic
corpus never emits them and the shared-scheme view of the scorer drops them on
both sides, so `benchmark/types.py` keeps them in `SENSITIVE_ENTITY_TYPES` and
scores them through `SCORED_ENTITY_TYPES`.

The detector design they measure is
[2026-08-27 ม.26 span masking](decisions/2026-08-27-section26-span-masking.md);
the gold-v7 authoring record is
[2026-08-27 gold-v7 sensitive](decisions/2026-08-27-gold-v7-sensitive-authoring.md).
There is no checksum and no format to lean on here, so the seven rules below
carry the entire weight of the label.

**S1 — the fact must be predicated of an identified person.** A ม.26 phrase is
annotated only where the document's fiction states the sensitive fact *about* an
identified or identifiable natural person. Co-occurrence with a name is not
enough: a ประกาศ that names its contact officer does not thereby make the
disease it discusses that officer's health data. Not annotated, therefore:
statutes and their titles, ประกาศ / ระเบียบ / แนวทาง / หลักสูตร addressed to the
public, research findings and statistics, seminar and exhibition topics,
organization names that contain a category word (สหภาพแรงงาน… or สมาคมลูกจ้าง…
as the entity's own name), and the "health" of a machine or a system.

Linkage is **document-level**, not sentence- or segment-level. A lab-result line
in a report that names its patient one line above is that patient's health data
and is annotated as such. The detector links per segment, so some of these are
recall misses by construction; the corpus labels ground truth, and a miss is
recorded as a miss.

**S2 — assertion, not naming.** The value is the sensitive fact the sentence
*asserts* about the person. A category word that merely *names* a document, a
section, a field, a purpose, a right, or a class of data is not a value:

- form and letter titles — แบบยินยอมรับการรักษา (`md07`),
  แบบคัดกรองสุขภาพจิตเบื้องต้น (`md11`), หนังสือส่งตัวผู้ป่วยพร้อมประวัติการรักษา
  (`lf17`);
- section headers and field labels — ส่วนที่ 3 ข้อมูลสุขภาพ (`lf15`),
  ประวัติการเจ็บป่วย, การวินิจฉัยหลัก, เหตุผลการส่งตัว, ประวัติการแพ้ยา;
- consent purposes — ยินยอมให้โรงพยาบาลเก็บและใช้ข้อมูลสุขภาพเพื่อการรักษาพยาบาล
  เท่านั้น (`lf11`);
- entitlements — สิทธิการรักษา ประกันสังคม (`lf11`),
  สิทธิการรักษาพยาบาลตามกองทุนประกันสังคม (`dg20`).

A bare category word *is* a value when the sentence asserts it of the person:
ขอลาพักการศึกษา…เนื่องจากปัญหาสุขภาพ (`ed05`) asserts that this student has a
health problem, so ปัญหาสุขภาพ is annotated there. A section header is never a
value; the data underneath it is. This is the same mechanic as "contextual cues
stay outside the brackets", applied to prose.

**S3 — what counts as the fact.** A value names an attribute, state, condition,
symptom, diagnosis, finding, disability, belief, membership, conviction, or a
procedure or course of care the person actually underwent or was prescribed.
The **administration around** that fact is not a value, however medical the
document is: an appointment time or room, a referral's routing between wards or
hospitals, the treating doctor's identity, a treatment entitlement, a consent
clause, a record-keeping act.

The line that decides the near cases is whether the sentence reports **content**
about the person:

- `md05` "มีนัดตรวจติดตามอาการ ในวันที่ 30 กันยายน 2569 … ห้องตรวจเบอร์ 7" is a
  scheduling fact and carries **no** value; `md11` "ผลคัดกรองพบความเสี่ยงระดับปานกลาง"
  reports a screening result and is one.
- `md01` "ข้าพเจ้าได้ตรวจร่างกาย [ชื่อ]" states that an examination happened and
  reports nothing from it, so no value; "เห็นควรให้หยุดพักรักษาตัวเป็นเวลา 5 วัน" in
  the same document prescribes a course of care and is one. `md08`
  "ผลการตรวจร่างกายอยู่ในเกณฑ์ปกติ" reports the result, so the examination there
  *is* a value.
- `md12` and `md13` are a referral and a blank new-patient record. Both are
  entirely administrative and carry no ม.26 value at all.
- **Care the person asks for is content about them.** `sn18`
  "ขอรับการตรวจคัดกรองโรคติดต่อ" is annotated: a requested screening tells the
  reader what this named patient is being screened for, the same way `md01`'s
  prescribed rest tells the reader what care he was put on. Requested and
  prescribed care sit on the same side of the line; only the *scheduling* of it
  (`md05`) sits on the other. Recall-first settles the near call towards the
  label.

**Consent is two different things and they cut differently.** S2 rules out
consent *purposes*, and that rule is about consent to **process data**:
`lf11` ยินยอมให้โรงพยาบาลเก็บและใช้ข้อมูลสุขภาพเพื่อการรักษาพยาบาลเท่านั้น names a
class of data and asserts nothing about the signer, so it carries no value.
Consent to **undergo a procedure** is the opposite: `md07`
ยินยอมให้แพทย์ทำการผ่าตัด asserts that this named person is having an operation,
so การผ่าตัด is a value there. The test is whether the sentence tells you
something about the person or only about a data-handling permission.

A lifestyle fact recorded as clinical history is health data
(`lf02` ประวัติสูบบุหรี่, in a เวชระเบียน). The health of a machine or a system is
not anyone's data (`dg03` การตรวจสอบสุขภาพระบบประจำสัปดาห์).

**S4 — span boundaries.**

- Field labels, headings and titles stay outside, as for every other type.
- Leading verbs of receiving, having, being or finding stay **outside**:
  เข้ารับ, ได้รับ, มี, เป็น, ป่วยเป็น, นับถือ, พบ / ตรวจพบ / ไม่พบ.
  ป่วยเป็นโรคเบาหวาน annotates โรคเบาหวาน. This applies at the **start** of the
  value only. The same verb inside the clause is part of it, which is why
  `md11` ผลคัดกรองพบความเสี่ยงระดับปานกลาง and `md08` ไม่พบโรคที่เป็นอุปสรรคต่อการปฏิบัติงาน
  cut differently: the first has ผลคัดกรอง in front of พบ, the second does not.
- A verb that *is* the sensitive fact stays **inside**: ถูกฟ้อง, ต้องโทษ, จำคุก.
  ถูกฟ้องคดีฉ้อโกง is one value, ถูก included.
- A qualifier that is part of the attribute's own identity stays **inside** —
  a disability class, a sentence term, a diabetes type: คนพิการประเภทที่ 3,
  ต้องโทษจำคุก 2 ปี, โรคเบาหวานชนิดที่ 2.
- A purely temporal or adverbial trailer stays **outside**: มาห้าปีแล้ว,
  ตั้งแต่ปี 2560, ตั้งแต่วัยเด็ก, เมื่อเดือนมิถุนายน 2569, ตามนัดหมายของแพทย์.
- ประวัติ in front of **any** sensitive attribute is **inside** the value —
  having a history of the thing is itself the asserted fact. This is not a
  disease rule: it holds for a condition (`lf11` มีประวัติโรคหอบหืด annotates
  ประวัติโรคหอบหืด), a lifestyle fact (`lf02` ประวัติสูบบุหรี่), a conviction
  (`sn09` ประวัติอาชญากรรมคดียาเสพติด) and sexual behaviour alike
  (`sn18` ให้ประวัติเพศสัมพันธ์โดยไม่ป้องกัน annotates
  ประวัติเพศสัมพันธ์โดยไม่ป้องกัน). ประวัติ standing alone as a form field ahead
  of its data is a label and stays outside (ประวัติการแพ้ยา, ประวัติการเจ็บป่วย in
  `lf11` and `lf17`).
- Two facts joined by a connective (และ, ร่วมกับ) are two values, not one. That
  holds for procedures as well as conditions: `lf17`
  เพื่อตรวจชิ้นเนื้อและวางแผนการรักษาโดยแพทย์เฉพาะทาง is two.

The six boundary disputes §4.3 of the design record left open settle as:

| Phrase in the source | Gold value | Rule |
|---|---|---|
| เคยต้องโทษจำคุก 2 ปี | `ต้องโทษจำคุก 2 ปี` | sentence term is part of the conviction |
| เป็นคนพิการประเภทที่ 3 | `คนพิการประเภทที่ 3` | class is part of the status |
| ถูกฟ้องคดีฉ้อโกง | `ถูกฟ้องคดีฉ้อโกง` | the passive marker is the fact |
| ผลตรวจดีเอ็นเอตรงกับวัตถุพยาน | `ผลตรวจดีเอ็นเอตรงกับวัตถุพยาน` | clause-internal cue, not a field label |
| พบสารพันธุกรรม… | `สารพันธุกรรม` | พบ is a finding verb |
| ป่วยเป็นโรคเบาหวานมาห้าปีแล้ว | `โรคเบาหวาน` | temporal trailer excluded |

**S5 — anchor evidence is not annotated.** Gold labels the fact, never the
detector's evidence chain. A prediction that overlaps an annotated value is a
true positive whatever anchored it, including a CRF `NAME` false positive.

The adjudicated case is row 13 of the design record's §8 ledger. In `lf17` the
detector emits `HEALTH (468, 479) 'การรักษาโดย'`, and its only person anchor is
a CRF `NAME` span over แพทย์เฉพาะทาง, which is not a person's name at all. Both
halves settle in favour of the label. The referral reason
วางแผนการรักษาโดยแพทย์เฉพาะทาง is a course of care planned for a named patient,
so it is a value under S1, S2 and S3 — the field label เหตุผลการส่งตัว stays
outside, and the และ splits it from ตรวจชิ้นเนื้อ, which is a second value. And a
prediction overlapping that value is a true positive however it was anchored,
because gold cannot be conditioned on the detector's internals without
becoming a record of detector behavior. The consequence is recorded honestly
instead: this true positive rests on a `NAME` false positive, so fixing that
`NAME` error would cost a ม.26 true positive. That is a fragility of the design
(§4.2 of the record), not a defect of the annotation.

**S6 — a swallowed span is still annotated.** Where a `NAME`/`SURNAME`
prediction covers the whole ม.26 phrase, the characters are masked but the ม.26
label is lost. The value is annotated anyway and scores as a miss on its
category. Every authoring record for a set containing sensitive spans must state
how many gold sensitive spans were character-covered by *some* prediction as
against left uncovered, because those two failures differ by whether anything
leaked.

**S7 — documents written before the family existed are adjudicated, not
grandfathered.** Opening a new annotated family makes every document in the
corpus in scope for it. A pre-existing document that carries a ม.26 value under
S1 to S4 is annotated, and the edit is listed line by line in that version's
authoring record under the change-control rule at the end of this file.

Two things this rule forbids. It forbids leaving old documents unannotated and
scoring their real ม.26 content as false positives, which would publish a
precision figure that blames the detector for being right. And it forbids the
opposite shortcut of annotating only where the detector happened to fire: the
audit is a **read** of every document that could carry a value, and it produces
misses as readily as hits. gold-v7's pass over the 304 pre-v7 documents added
27 values in 17 documents, of which the detector finds 8.

**Per-category n, and value reuse.** The `n >= 20` floor of
`tests/test_benchmark_gold.py` is **exempt for the ten ม.26 categories** and for
them only. gold-v7 reaches it for `HEALTH` alone; the other nine sit at single
digits, so their per-category recall and precision are indicative and must not
be published as headline numbers. Recorded as a known limit of gold-v7, not as a
permanent licence.

The no-reuse-across-documents rule is exempt for the same ten. It exists so a
detector cannot look good by memorising one identifier string; ม.26 values are
ordinary Thai phrases, two people may genuinely share a diagnosis or a religion,
and forcing every one of them to be a distinct string would deform the documents
to satisfy a rule aimed at something else.

## Judgment-call precedents

Recorded so adjudication is repeatable. Each traces to an existing corpus
decision; add new precedents here when a new dispute is settled.

1. **Standalone room/hotel/house numbers are not PII** outside an address
   chain (gold `id23` leaves a hotel room number unannotated).
2. **Single-word names are not annotated.** The corpus has no one-word NAME
   precedent; a bare nickname after a kinship word (พี่/น้อง/ป้า) stays
   unannotated. A full first-last name is always annotated, cue or not.
3. **Vague area mentions are not ADDRESS.** แถว/ย่าน + district is context;
   an address is annotated from the first locatable component (house number,
   named soi/road with number, or a tambon/amphoe/province chain).
4. **Only public short-code hotlines are excluded from PHONE.** Office lines,
   department numbers, and call-center numbers in normal phone formats are
   annotated (2026-07-28 adjudication: broad ownership matches corpus
   practice and the recall-first product).
5. **DATE_OF_BIRTH requires a birth cue.** A bare date near a person is not a
   birth date; without the cue it stays unannotated (the detector's honest-label
   rule mirrors this).
6. **A value inside another annotated value is never separately annotated**
   (no nesting): the outermost natural unit wins (a full address containing a
   postal code is one ADDRESS).
7. **Address labels stay outside the brackets**: เลขที่ / บ้านเลขที่ / ที่อยู่
   are cues; the ADDRESS span starts at the house-number digits or first named
   locatable component (normalized corpus-wide in the 2026-07-28
   adjudication).
8. **Punctuation intrinsic to the value stays inside**: abbreviations and
   initials (กทม., กรุงเทพฯ, `Nattaya S.`) keep their marks; sentence and
   delimiter punctuation stays outside.
9. **A mod-11-valid 13-digit personal identifier is THAI_ID regardless of the
   document type around it** (driver licenses print the citizen ID; a Thai
   personal taxpayer ID is the citizen ID). Nearest-cue precedence applies to
   choosing between PII types, not to un-labeling valid national IDs.
10. **A phone number as a transfer destination stays PHONE** (PromptPay:
    โอนเงิน...ปลายทาง + a mobile-format number is a phone used for payment,
    not a bank account; gold `ms14`).
11. **A sensitive fact about an unnamed third party is not annotated**, even
    when the sentence names someone: `nc08` แพทย์ผู้ตรวจ [ชื่อ]
    ลงความเห็นให้พักรักษาตัว 3 วัน names the doctor, and the rest is health data
    about a patient the document never identifies (S1, 2026-08-27
    adjudication).
12. **An entitlement or a scheme name is not the data it entitles you to**:
    สิทธิการรักษา ประกันสังคม (`lf11`) and
    หนังสือแจ้งสิทธิการรักษาพยาบาลตามกองทุนประกันสังคม (`dg20`) carry no HEALTH
    value; a benefit is an administrative status, not a health fact.
13. **An organization's own name is not a ม.26 value** even when it is built out
    of a category word (สหภาพแรงงาน…, สมาคมลูกจ้าง…, a party name in a list of
    registered parties). The membership of a named person in that organization
    is (S1/S2, 2026-08-27 adjudication).

## Negative slice

Documents with zero annotations and zero PII of the 16 types, carrying
look-alikes that must not be flagged: receipt/invoice/order numbers, case and
statute numbers, ISBN, prices, lot/tracking numbers, public hotlines.
Organization names and provinces are allowed and expected (see
quasi-identifiers above). No maximal digit token of exactly 13 digits may
appear — even a checksum-invalid one reads as a national-ID look-alike and
turns the document into a detector-behavior probe rather than a clean
negative. Longer tokens (14+ digits) that the document identifies as non-PII
codes are allowed (gold `ng23`).

## Slice contracts

- `name_no_cue`: no title or verb-of-naming cue directly before the NAME —
  the banned family is exactly the test-pinned lists: titles
  นาย/นาง/นางสาว/น.ส./ด.ช./ด.ญ./เด็กชาย/เด็กหญิง and intros
  ลงชื่อ/ผมชื่อ/ดิฉันชื่อ/ชื่อ. Occupational and discourse roles
  (ผู้จัดการ, พยาน, ลูกค้า) are allowed — names introduced only by role words
  are exactly the hard case this slice exists to measure.
- `long_form`: > 500 chars; every document must have at least one entity
  starting before char 450 and at least one starting after char 500 (the
  stride-chunk boundary), enforced per document since v4. Newly authored
  long-form documents should meet the stricter three-zone placement
  (before 450 / 450-550 / after 550) used by the blind set.
- `sensitive`: ม.26 documents under the rules above. Every document carries at
  least one of the 19 structured types as well, so the slice measures the two
  families together; at least six documents are impersonal near-misses with
  zero sensitive spans, which is where the design record's register-veto
  vocabulary gets its only evidence outside the 30 authored dev near-misses.
  The slice is weighted towards the nine categories gold-v6 had no evidence for
  at all, and all ten must appear in it. It also carries the probe documents the
  design record asks for by name: `sn28`, a tier-2 role word whose specificity
  marker sits just past a segment boundary (§8 limit 9), and `sn20`, whose ม.26
  phrase the NER swallows inside a `NAME` span (§8 limit 1). Both are authored
  to fail, and both do — see the authoring record.
- `messy`: OCR-like noise is the point — Thai digits, stray spaces, broken
  wraps. Values still read verbatim, noise included.
- `student_id_varied`: varies one format/context axis per document relative
  to the plain cue-adjacent form — digit count, separators, spacing/gluing,
  cue language, cue distance, or cue strength (weak/absent cue documents are
  deliberate probes of the detector's cue dependence).
- Checksum-bearing values are always valid (mod-11 / Luhn); PII values are
  never reused across documents, with two recorded exceptions, both
  test-exempted: the `bank_phone` slice reuses a value across its paired
  documents by design (the pair varies the cue, not the number), and the ten
  ม.26 categories are exempt everywhere (see "Per-category n, and value reuse"
  above — their values are ordinary Thai phrases, not identifiers).
- Verbatim rule, operationally: the document's source text is `annotated`
  with the markup tokens removed; a validator must be able to reconstruct
  every span from that stripped text (this is exactly what `parse_gold`
  round-trip tests enforce).

## Change control

- The gold set is versioned in `benchmark/gold.py`'s docstring; a change to
  `data/gold.jsonl` bumps that version and lands with its own adjudication or
  authoring record under `docs/decisions/`.
- Adjudication is review-then-fix: reviewers list findings against these
  rules; fixes are applied only for rule violations, never to make a document
  easier for the current detector.
- The blind set follows the same rules but is authored/reviewed only in
  isolated contexts and never opened afterward
  ([protocol](decisions/2026-07-28-blind-set-protocol.md)).
