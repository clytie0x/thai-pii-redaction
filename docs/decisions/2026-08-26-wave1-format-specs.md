# Frozen legal-format verdicts for PDPA campaign Wave 1

Date: 2026-08-26
Status: accepted

## Context

The PDPA data ontology (`docs/decisions/2026-08-26-pdpa-data-ontology.md`) shipped
with three open verdicts it could not settle from repo evidence alone. Each one
gates detector work: two of them decide whether a *new detector exists at all*,
and the third decides whether a shape is tight enough to ship. Task 1 of the
PDPA-standard campaign is research only — no code changed in this session.

The repo rule is honest labels. A verdict of `thai_id_alias` means the category
is genuinely the same number space the shipped `THAI_ID` detector already covers,
so the correct engineering action is **no new detector** plus gold documents that
prove the coverage in the new context. Anything the evidence does not reach is
written down as a gap, not smoothed over.

## Verdicts

| Question | Verdict |
|---|---|
| `SSO_NUMBER` | **`thai_id_alias`** — for Thai insured persons the SSO identifier is the 13-digit citizen ID. Foreign insured persons are a **recorded gap** (see §1.3) |
| `PERSONAL_TIN` | **`thai_id_alias`** — personal TIN = citizen ID since 1 Feb 2555 (2012), by ประกาศอธิบดีกรมสรรพากร. Legacy 10-digit TIN is a **closed** gap (expired 31 ม.ค. 2556); foreigner RD-issued TIN is an **open** gap (see §2.3) |
| `LAND_DEED_SHAPE` | **1–6 digits, cue-gated only, no checksum** — not `too_loose_to_ship`, but the cue gate is the entire precision story and the range is narrowed from the candidate 1–8 |
| IP / MAC citation basis | **citation was wrong** — the ontology's "PDPC guidance" basis for IP address is not supported by either source it cites. Corrected in §4 |

---

## 1. เลขประกันสังคม — `thai_id_alias`

### 1.1 The evidence

The official SSO registration form **สปส.1-03 (แบบขึ้นทะเบียนผู้ประกันตน)** puts
both identifiers in one field, and the parenthetical settles who uses which.
Field 2.3 reads:

```
2.3  เลขประจำตัวประชาชน/เลขที่บัตรประกันสังคม (สำหรับคนต่างด้าว)
```

Read plainly: the citizen ID is the insured-person identifier, and the
SSO-issued card number is the *substitute* reserved for คนต่างด้าว. The same
form has a separate `สำหรับเจ้าหน้าที่` box where the officer writes
`เลขที่บัตรประกันสังคม`, i.e. that number is assigned by SSO at registration and
is not something a Thai national brings with them.

Text extracted in this session with `pdfminer` from the สปส.1-03 PDF hosted at
`fineart.tu.ac.th` (see Sources). The hosting is a university mirror; the form
itself is the SSO's own numbered form.

Corroboration on the Thai-national side: every SSO self-service channel
authenticates the insured person by the 13-digit citizen ID — the SSO website
e-services and the SSO Connect app both take `เลขประจำตัวประชาชน 13 หลัก` as the
username. There is no separate "SSO number" a Thai insured person ever quotes.

### 1.2 Consequence — no new detector

`SSO_NUMBER` is not a data type. The ontology row becomes "covered via
`THAI_ID`". Runtime confirmation, this session:

```
'ผู้ประกันตนมาตรา 33 เลขที่บัตรประกันสังคม 3109900543215 โรงพยาบาลตามสิทธิ'
   -> [('THAI_ID', '3109900543215', 1.0)]
'ประกันสังคม เลขประจำตัวประชาชน 1101700123456 ส่งเงินสมทบเดือนสิงหาคม'
   -> [('THAI_ID', '1101700123456', 1.0)]
```

Both values are checksum-valid citizen IDs constructed in this session from the
repo's own `is_valid_thai_id` (they are synthetic, not real people's numbers).
The ประกันสังคม context neither helps nor hurts — the checksum carries the
detection, exactly as it should for an alias.

**Task 6 obligation.** Because the coverage claim rests on context rather than on
a distinct shape, the gold corpus must contain documents where a citizen ID
appears under a ประกันสังคม heading (payroll contribution lists, สปส.1-03
excerpts, hospital-rights letters). Without those, the coverage profile would be
asserting a claim the benchmark never exercises.

### 1.3 Recorded gap — foreign insured persons

Two different numbers can appear for a foreign worker, and amphrang's position
on them is not the same.

**(a) The DOPA 13-digit number (บัตรชมพู).** Registered migrant workers and their
Thailand-born children hold `บัตรประจำตัวคนซึ่งไม่มีสัญชาติไทย`, whose 13-digit
number starts `00`. The DOPA registration office's own status-of-person briefing
counts them under exactly that label — `แรงงานต่างด้าว (เลข 00)` and
`บุตรที่เกิดในไทย (เลข 00)` — and states they are registered
`ตามกฎหมายทะเบียนราษฎร`. That is the same statute and the same numbering system
that issues citizen IDs. On 18 July 2561 (2018) the SSO board resolved to amend
SSO regulations so a migrant worker may present this card *instead of* the social
security card when claiming medical benefits, which puts the DOPA number squarely
into ประกันสังคม documents.

amphrang already handles the shape. A `0`-leading checksum-valid 13-digit number
is emitted as `THAI_ID` by default — `_disambiguate_thai_juristic` deliberately
lets the personal label win without a juristic cue. Verified this session with a
**synthetic** `00`-leading number (no real pink-card number was used or sought):

```
'ผู้ประกันตนต่างด้าว เลขประจำตัว 0005600123451 ตามบัตรชมพู ส่งเงินสมทบ'
   -> [('THAI_ID', '0005600123451', 1.0)]
```

What is **not** verified: that real DOPA type-`0` numbers carry the citizen mod-11
check digit. DOPA's public explainer of the 13-digit number describes only
`ประเภทบุคคลซึ่งมี 8 ประเภท` (types 1–8) and says digit 13 verifies the number,
without extending the statement to type `0`. Real pink-card numbers are personal
data and are not public record, so the five-real-vector bar cannot be met — this
is "the evidence does not exist publicly", not "we did not try". The shipped
behaviour is therefore correct *if* the checksum holds and silently misses *if*
it does not. **`_RE_THAI_ID` must not be loosened to cover the uncertainty.**

**(b) The SSO-issued `เลขที่บัตรประกันสังคม`.** Format unverified. The SSO does
not publish a specification, and no public source found in this session states
its digit count or whether it carries a check digit. Secondary sources describe
it as 13 digits, which is not enough to ship on. **Open gap; no detector.**

**(c) A labelling defect, not a masking defect.** A `00`-leading number under a
tax cue is routed to `JURISTIC_ID`, because `_disambiguate_thai_juristic` reads
`เลข(?:ประจำตัว)?ผู้เสียภาษี` as juristic evidence:

```
'เลขประจำตัวผู้เสียภาษี 0005600123451 ของแรงงานต่างด้าว'
   -> [('JURISTIC_ID', '0005600123451', 1.0)]
```

A natural person's number is then labelled as a business identifier — which the
ontology's Level E calls "outside PDPA scope". The value is still masked
(`JURISTIC_ID` is in `SAFE_OUTBOUND_LEAK_TYPES` and the leak guard), so this is a
reporting-honesty defect, not a leak. Recorded here; fixing it needs a signal
that separates a foreign natural person from a company, which the cue alone does
not carry.

---

## 2. เลขผู้เสียภาษีบุคคลธรรมดา — `thai_id_alias`

### 2.1 The rule and its date

**ประกาศอธิบดีกรมสรรพากร เรื่อง กำหนดให้ผู้มีหน้าที่เสียภาษีเงินได้บุคคลธรรมดา
บริษัทหรือห้างหุ้นส่วนนิติบุคคล และผู้จ่ายเงินได้ซึ่งมีหน้าที่หักภาษี ณ ที่จ่าย
มีและใช้เลขประจำตัวในการปฏิบัติการตามประมวลรัษฎากร (ฉบับที่ 3)**, signed
11 มกราคม 2555, in force from 1 กุมภาพันธ์ 2555.

For a natural person holding a citizen ID the announcement directs
`ให้ใช้เลขประจำตัวประชาชนนั้นในการปฏิบัติการตามประมวลรัษฎากร`, and such a person
need not apply for a separate tax-ID card. A standing Revenue Department page
states the same duty for filing personal income tax returns.

Verdict: **personal TIN = citizen ID**. No new detector.

### 2.2 The legacy 10-digit TIN — a closed gap

The old 10-digit `เลขประจำตัวผู้เสียภาษีอากร` was not abolished overnight. The
Revenue Department's `คำชี้แจง` on `การใช้เลขประจำตัว 13 หลัก` allowed already-issued
numbers to continue in non-return uses until **31 มกราคม 2556 (2013)**, while tax
returns required 13 digits immediately. A later amendment (ข้อ 4/1) confirms the
same 31 ม.ค. 2556 boundary for correcting an already-used number.

The expected verdict in the ontology was "legacy 10-digit TINs are a recorded gap
unless evidence shows they still circulate". The evidence shows the opposite of
still-circulating: the transition window closed thirteen years ago and every
current filing, invoice, and withholding certificate carries 13 digits.

**Verdict: closed gap.** No 10-digit TIN pattern is to be added. If a genuinely
current document with a 10-digit TIN is ever produced, it reopens by dated
amendment — that is the registry's whole contract.

### 2.3 Open gap — foreigners without a citizen ID

The same `คำชี้แจง` provides that an individual with neither a citizen ID nor a
business registration number receives a **13-digit TIN issued by the Revenue
Department**. That number belongs to a natural person and is personal data under
ม.6, but its structure — leading digit, whether it carries the citizen check
digit — is not published. If it is `0`-leading and checksum-valid it lands in
exactly the mislabelling described in §1.3(c); if it is checksum-invalid it is
missed entirely. **Open gap, no detector, no loosening of `_RE_THAI_ID`.**

### 2.4 Interplay probe — the shipped disambiguation is correct

The ontology's claim was that a `เลข(?:ประจำตัว)?ผู้เสียภาษี` cue near a `0`-leading
number yields `JURISTIC_ID`, while near a 1–9-leading citizen ID the
`_disambiguate_thai_juristic` pass keeps `THAI_ID`. Confirmed in this session:

```
'เลขประจำตัวผู้เสียภาษี 0-1075-36000-10-2 ตามหนังสือรับรอง'
   -> [('JURISTIC_ID', '0-1075-36000-10-2', 1.0)]
'เลขประจำตัวผู้เสียภาษี 3109900543215 ของนายสมชาย'
   -> [('THAI_ID', '3109900543215', 1.0)]
'เลขประจำตัวผู้เสียภาษีอากร 1101700123456 ยื่นแบบ ภ.ง.ด.90'
   -> [('THAI_ID', '1101700123456', 1.0)]
```

`0107536000102` is the real, public DBD registration number of
ธนาคารไทยพาณิชย์ จำกัด (มหาชน), already used as a verified vector in
`docs/decisions/2026-08-26-new-datatype-specs.md`. The two citizen IDs are
synthetic and checksum-valid.

The tax cue therefore already discriminates a personal TIN from a juristic TIN by
the leading digit alone, with no code change needed for the Thai-national case.

---

## 3. เลขโฉนดที่ดิน — shape frozen at 1–6 digits, cue-gated only

### 3.1 What the number is

The Department of Lands defines `เลขที่โฉนด` as the per-parcel number issued
within one **อำเภอ**, running `เริ่มจากเลขที่ 1 ไปตามลำดับจนหมดเขตอำเภอนั้น`.

That single sentence decides the shape question:

- It is a **plain sequential integer**, not a structured code. There are no
  positional fields to validate and **no check digit** — nothing to compute one
  from.
- It has **no fixed width**. Deed number `1` is as real as deed number `81875`.
- It is **not globally unique**. `โฉนดเลขที่ 2086` identifies a parcel only
  together with its อำเภอ/จังหวัด, which is why real documents always print the
  locality alongside it.

Three sibling numbers travel with it on the same deed and are frequently printed
in the same sentence: `เลขที่ดิน` (parcel number within the survey sheet),
`หน้าสำรวจ` (survey-page sequence within the ตำบล), and `ระวาง` (the survey sheet
itself). They are separate identifiers with their own numbering and are **out of
scope for this verdict** — a decision Task 2 inherits, not one it may quietly
widen.

### 3.2 Real published examples

Five title numbers from public auction notices published by Bangkok Commercial
Asset Management (BAM), a listed company whose auction listings are public
record. Each was read from its own listing page in this session.

| # | เลขที่เอกสารสิทธิ์ | Property | Locality |
|---|---|---|---|
| 1 | `33886` | ที่ดินเปล่า | แขวงท่าข้าม เขตบางขุนเทียน กรุงเทพมหานคร |
| 2 | `81875` | ทาวน์เฮ้าส์ | ตำบลคลองสอง อำเภอคลองหลวง ปทุมธานี |
| 3 | `58694` | อาคารพาณิชย์ | แขวงคลองขวาง เขตภาษีเจริญ กรุงเทพมหานคร |
| 4 | `33106` | อาคารพาณิชย์ | แขวงบางชัน เขตมีนบุรี กรุงเทพมหานคร |
| 5 | `2086` | ทาวน์เฮ้าส์ | ตำบลบางเสาธง สมุทรปราการ |

Observed range: **4–5 digits**. No 1–3 digit or 6+ digit example was found in a
public listing, which is a sampling artefact of urban auction stock rather than
evidence of a floor or ceiling.

**A confounder found in the same sample.** Condominium unit titles
(หนังสือกรรมสิทธิ์ห้องชุด, อ.ช.2) are numbered in a `building/unit` slash form —
`845/544` in บางกะปิ, `1/108` in พระประแดง — and are *not* โฉนดที่ดิน. A digits-only
pattern will never match them, which is correct, but any future widening toward a
slash form would collide with document numbering and with `_RE_VEHICLE_PLATE`
territory. Not in scope.

### 3.3 Why 1–6 and not the candidate 1–8

`too_loose_to_ship` would be the wrong verdict: the shape is not unknown, it is
*unstructured*, and a cue-gated unstructured integer is exactly what
`HOUSE_REG_ID` and `DRIVER_LICENSE` already ship as. What the evidence does not
support is the upper end of the 1–8 candidate.

- The floor stays at **1** because the Department of Lands says numbering starts
  at 1 — a 1-digit deed number is a real value, not noise.
- The ceiling drops to **6**. Deed numbering restarts per อำเภอ; Thailand has
  roughly 900 districts. A 7- or 8-digit deed number would require a single
  district to have issued over a million titles, and no source or example
  supports it. Cutting 8→6 removes two orders of magnitude of digit space at zero
  evidential cost.

**The cue gate is the whole precision story.** There is no checksum and no
structure, so an uncued digit run must never be labelled a deed number. The
frozen spec is:

| Field | Value |
|---|---|
| Shape | `\d{1,6}`, pure digits, cue-gated **only** |
| Checksum | none — none exists |
| Cue | `โฉนด` family (`โฉนดที่ดิน`, `โฉนดเลขที่`, `เลขที่โฉนด`), cue **before** the value — plus the `น.ส.` form family, see the amendment below |
| Siblings out of scope | `เลขที่ดิน`, `หน้าสำรวจ`, `ระวาง` |
| Condo titles out of scope | `N/M` slash form (อ.ช.2) |

**Amendment, 2026-08-27 — the `น.ส.` form family is part of the shipped cue.** The
table above records only the `โฉนด` family, which is what this record froze. It is
not what shipped. `23b4744` ("feat: detect IP_ADDRESS, MAC_ADDRESS, LAND_DEED_ID")
already added `น\.ส\.\s*[34]\s*(?:ก|ข)?\s*เลขที่` to `_RE_LAND_DEED`, and
`docs/annotation-guidelines.md` names `น.ส.3ก เลขที่` as deed-cue annotation law, so
code and guidelines had both moved ahead of this section. The final review round of
the PDPA-standard campaign widened the same alternative to the full กรมที่ดิน form
series and this amendment closes the drift; the frozen shape, checksum verdict,
score and out-of-scope siblings above are all unchanged.

The cue now reads `น\.ส\.\s*(?:3\s*[กข]?|4\s*[กขคงจ]?)\s*เลขที่`. The two halves are
different documents and the distinction matters legally, not only lexically:

| Form | Document |
|---|---|
| `น.ส.3`, `น.ส.3ก`, `น.ส.3ข` | หนังสือรับรองการทำประโยชน์ — a utilization certificate, not title |
| `น.ส.4`, `น.ส.4ก`, `น.ส.4ข`, `น.ส.4ค`, `น.ส.4ง`, `น.ส.4จ` | **โฉนดที่ดิน** — the title deed itself |

`น.ส.4ก`/`ข`/`ค` issue under กฎกระทรวง ฉบับที่ 5 (พ.ศ. 2497) and `น.ส.4ง` under
ฉบับที่ 17 (พ.ศ. 2514); กรมที่ดิน has stopped issuing ก–ง, and `น.ส.4จ` is the current
ครุฑแดง form. The retired forms stay in the cue because the paper still circulates
and a document quoting one carries a real deed number. Sources: กรมที่ดิน Q&A on
`น.ส.4 ง` <https://www.dol.go.th/question-answer/Q2401-006730>, and the
`น.ส.4 จ` explainer at
<https://www.ddproperty.com/คู่มือซื้อขาย/นส.-4-จ.-คืออะไร-ซื้อขายที่ดินได้ไหม-49768>.

Measured on the corpus this record's numbers come from: **zero** of the 332 gold
documents contain a `น.ส.3`/`น.ส.4` string at all, so the `LAND_DEED_ID` row stays
`22 / 1.000 / 1.000` and the widening carries no measured regression — and no gold
evidence either.

### 3.4 Current behaviour — measured, and one collision Task 2 must handle

Nothing detects a deed number today:

```
'โฉนดที่ดินเลขที่ 81875 เลขที่ดิน 44 หน้าสำรวจ 2919'  -> []
'ที่ดินโฉนดเลขที่ 33106 เนื้อที่ 20 ตารางวา'          -> []
```

But a deed number sitting immediately before `ตำบล` is already claimed by the
address detector as a house number, at score **0.85**:

```
'โฉนดเลขที่ 2086 ตำบลบางเสาธง'
   -> [('ADDRESS', '2086', (11, 15), 0.85), ('ADDRESS', 'บางเสาธง', (20, 28), 0.85)]
'โฉนดที่ดินเลขที่ 58694 แขวงคลองขวาง เขตภาษีเจริญ'
   -> [('ADDRESS', 'คลองขวาง', (27, 35), 0.85), ('ADDRESS', 'ภาษีเจริญ', (39, 48), 0.85)]
```

The collision is specific to `ตำบล` (the `แขวง` form does not trigger it) and it
is the single most common real-world phrasing, since deed numbers are always
printed with their locality. Consequences for Task 2:

- `LAND_DEED_ID` must score **above 0.85** or `_deduplicate` will keep the
  `ADDRESS` label on the very sentences that matter. **0.9**, matching the other
  cue-gated types, satisfies this.
- The value is masked either way today, so this is again a labelling defect, not
  a leak — but the coverage profile cannot claim land-deed coverage while the
  span reports as `ADDRESS`.

---

## 4. IP address and MAC address — citation corrected

No legal research was needed for the shapes: both are RFC-defined and are not in
dispute. The brief's step was a citation audit of the ontology's basis line for
IP address, `(indirect identifier, PDPC guidance)`. **The audit fails.**

Checked in this session, both sources the ontology lists at the bottom:

- `t-reg.co/blog/t-reg-knowledge/what-is-personal-data/` — enumerates personal
  data examples (ชื่อ, เลขที่บัญชีธนาคาร, บัตรประชาชน, เบอร์โทรศัพท์) and **does
  not mention IP address, MAC address, cookie ID, or location data at all**.
- `marketingoops.com/data/personal-data-in-pdpa-2019/` — **does** carry the list
  `ข้อมูลอุปกรณ์หรือเครื่องมือ เช่น IP Address, MAC Address, Cookie ID`, but
  attributes it to nothing. No PDPC publication, no มาตรา.

So one cited source does not say it and the other says it without authority.
"PDPC guidance" is an overclaim and is removed.

**What the evidence actually supports.** The honest chain is:

1. **Primary.** ม.6 of the PDPA defines personal data as data identifying a
   natural person `ไม่ว่าทางตรงหรือทางอ้อม`. Device identifiers reach Level A
   through the *indirect* limb of that definition — statute, already cited.
2. **Secondary consensus.** Thai practitioner sources converge on listing
   `IP Address, MAC Address, Cookie ID` as ข้อมูลส่วนบุคคล (dharmniti, marketingoops,
   hrdi). Consensus, not authority.
3. **The nuance none of the consensus sources state.** PDPA Thailand's article on
   `เลขที่อยู่ไอพี` takes the narrower and better-reasoned position:
   `IP Address โดยลำพังแล้วไม่จัดว่าเป็นข้อมูลส่วนบุคคล` — an IP alone is not
   personal data; it becomes personal data when it sits with other data that lets
   the device's user be identified.
4. **Negative finding.** No PDPC or other government publication located in this
   session lists IP address as personal data. The DGA's government PDPA FAQ
   defines ข้อมูลส่วนบุคคล with the ทางตรง/ทางอ้อม test but gives no device
   examples.

**Corrected basis line** for the ontology: `(indirect identifier, ม.6 "ทางอ้อม")`.
The ontology's Sources section gains the pdpathailand citation and loses the
implication that the PDPC has spoken on this.

**A concern this raises, deliberately not resolved here.** Point 3 is the Level B
argument, not the Level A argument: a bare IP address in isolation is closer to a
quasi-identifier than to a mask-always span. The ontology places `IP_ADDRESS` at
Level A. That placement is defensible for a sanitizing proxy — an IP in a log
line forwarded to an external AI rarely travels alone — but it is a treatment
choice, not something the sources compel. Flagged for the campaign owner; **not
changed in this task**, which is docs-only and has no mandate to re-level a
category.

**Current behaviour**, measured this session — neither type exists yet, so there
is no precedence conflict for Wave 1 to resolve:

```
'เข้าระบบจาก IP 203.150.19.24 เมื่อเวลา 09.15 น.'       -> []
'MAC address ของเครื่อง 00:1A:2B:3C:4D:5E ลงทะเบียนแล้ว' -> []
```

---

## Consequences

- **No `SSO_NUMBER` detector and no `PERSONAL_TIN` detector.** Both are `THAI_ID`
  by identity, not by approximation. The ontology rows say "covered via
  `THAI_ID`".
- **Task 6 must add gold documents** putting a citizen ID in a ประกันสังคม context
  and in a `เลขประจำตัวผู้เสียภาษี` context. The alias verdicts are only as honest
  as the benchmark that exercises them.
- **`_RE_THAI_ID` stays as it is.** Three separate gaps (foreign SSO card number,
  RD-issued foreigner TIN, unverified type-`0` checksum) all tempt a looser
  pattern. Loosening it would trade a measured 1.000/1.000 for unmeasured recall.
- **`LAND_DEED_ID` ships at 0.9, `\d{1,6}`, cue-gated only**, and must outrank the
  `ADDRESS` 0.85 claim on the `<deed number> ตำบล…` phrasing. No checksum will be
  claimed, because none exists.
- **The ontology's IP basis line and Sources list are corrected** by the amendment
  landing with this record.
- **Two labelling defects are on record** (foreign natural person under a tax cue
  reported as `JURISTIC_ID`; deed number before `ตำบล` reported as `ADDRESS`).
  Both mask correctly today, so neither is a leak, and neither is fixed here.

## Blind set

Nothing in this record was derived from `benchmark/data/blind-*`, and no blind
run was performed.

## Sources

**เลขประกันสังคม**

- แบบขึ้นทะเบียนผู้ประกันตน **สปส.1-03**, field 2.3 and the `สำหรับเจ้าหน้าที่`
  box — text extracted with `pdfminer` in this session.
  <https://fineart.tu.ac.th/images/mainfile/fatu-form/Administrative-form/form-03.pdf>
- สำนักงานประกันสังคม e-services — insured persons authenticate with the 13-digit
  citizen ID. <https://www.sso.go.th/eservices/esv/>
- กรมการปกครอง (สำนักบริหารการทะเบียน), "การจัดการสถานะบุคคล —
  กลุ่มของบุคคลซึ่งไม่มีสัญชาติไทยที่เข้ามาในประเทศ" — counts
  `แรงงานต่างด้าว (เลข 00)` and `บุตรที่เกิดในไทย (เลข 00)` registered
  `ตามกฎหมายทะเบียนราษฎร`, as of 1 ก.ค. 2561. Text extracted in this session.
  <https://www.bora.dopa.go.th/wp-content/uploads/2022/02/Status-of-person.pdf>
- Hfocus, "แก้ระเบียบแรงงานต่างด้าวใช้บัตรประจำตัวเพื่อใช้สิทธิรักษาแทนบัตรประกันสังคมได้"
  — the 18 ก.ค. 2561 SSO board resolution. (Host returns 403 to direct fetch;
  content read through search extraction.)
  <https://www.hfocus.org/content/2018/07/16104>
- กรมการปกครอง, "เลขประจำตัวประชาชน 13 หลัก บอกอะไร" — describes
  `ประเภทบุคคลซึ่งมี 8 ประเภท` and digit 13 as the verification digit; **does not**
  extend either statement to type `0`.
  <https://multi.dopa.go.th/secofdopa/news/cate10/view207>
- กรมการปกครอง (Registration Law), กลุ่มบุคคล `00` = registered migrant workers
  since พ.ศ. 2547. (Host returns 403 to direct fetch; content read through search
  extraction.) <https://www.gotoknow.org/posts/643736>

**เลขผู้เสียภาษีบุคคลธรรมดา**

- ประกาศอธิบดีกรมสรรพากร ... มีและใช้เลขประจำตัวในการปฏิบัติการตามประมวลรัษฎากร
  (ฉบับที่ 3), 11 ม.ค. 2555, in force 1 ก.พ. 2555.
  <https://www.rd.go.th/31768.html>
- กรมสรรพากร, คำชี้แจง "การใช้เลขประจำตัว 13 หลัก" — the RD-issued 13-digit TIN for
  individuals without a citizen ID, and the 31 ม.ค. 2556 transition deadline for
  10-digit numbers. <https://www.rd.go.th/46203.html>
- กรมสรรพากร, ประกาศอธิบดี ... ข้อ 4/1 — confirms the same 31 ม.ค. 2556 boundary.
  <https://www.rd.go.th/46555.html>
- กรมสรรพากร, "เลขประจำตัวประชาชนใช้แทนเลขประจำตัวผู้เสียภาษีอากร" — the standing
  filing duty for individuals. <https://www.rd.go.th/14688.html>

**เลขโฉนดที่ดิน**

- กรมที่ดิน definition of `เลขที่โฉนด` (per-อำเภอ sequential from 1), together with
  `เลขที่ดิน`, `หน้าสำรวจ`, `ระวาง`. The กรมที่ดิน Q&A page
  (`dol.go.th/question-answer/1410-120419`) returns 404 to direct fetch; the
  definition was read through search extraction and cross-checked against
  Thansettakij's deed explainer.
  <https://www.thansettakij.com/real-estate/561480>
- BAM public auction listings — the five real title numbers in §3.2 and the two
  condominium `N/M` examples. <https://www.bam.co.th/th/auction-property/13333>,
  `/13500`, `/12500`, `/13900`, `/13001`, `/13800`, `/13100`

**IP / MAC**

- ราชกิจจานุเบกษา, พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562, ม.6 (`ทางตรงหรือทางอ้อม`)
  — already cited by the ontology.
  <https://ratchakitcha.soc.go.th/documents/17082307.pdf>
- PDPA Thailand, "เลขที่อยู่ไอพี (IP Address)" — the in-isolation-vs-in-combination
  position. <https://pdpathailand.com/pdpa/content/article9943.php>
- ธรรมนิติ, "PDPA กับความรับผิดของผู้ประกอบการ" — lists
  `ข้อมูลอุปกรณ์หรือเครื่องมือ เช่น IP address, MAC address, Cookie ID`.
  <https://www.dharmniti.co.th/pdpa-liability-for-business-owners/>
- marketingoops — same list, no attribution. Retained in the ontology as
  consensus, not as authority.
  <https://www.marketingoops.com/data/personal-data-in-pdpa-2019/>
- t-reg.co — **checked and found not to support the IP-address claim** it was
  cited for. <https://t-reg.co/blog/t-reg-knowledge/what-is-personal-data/>
- DGA, "FAQ เกี่ยวกับการคุ้มครองข้อมูลส่วนบุคคล (PDPA)" — negative finding: the
  ทางตรง/ทางอ้อม test with no device examples. Text extracted in this session.
  <https://www.dga.or.th/wp-content/uploads/2022/10/1.FAQ-เกี่ยวกับการคุ้มครองข้อมูลส่วนบุคคล-PDPA.pdf>

**Repo**

- Probes run with `./.venv/Scripts/python.exe` against
  `amphrang/engine/detectors/fp_detector.py::detect_fp` and
  `amphrang/engine/detectors/thai_id.py::is_valid_thai_id`, read-only,
  2026-08-26. No code was modified in this task.
