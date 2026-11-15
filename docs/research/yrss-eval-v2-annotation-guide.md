# YRSS evaluation v2: annotation and template guide

Protocol: [pre-registration](../decisions/2026-11-13-yrss-eval-v2.md).
This guide is all a template author or a human annotator needs. An author
must not read detector code, benchmark code, earlier corpora, or results.

## What gets a label

Eleven types. A label covers the value only, never the field name before it.

| Type | Label this | Do not label |
|---|---|---|
| NAME | given name and surname of a person, Thai or English, without the title | titles (นาย, คุณ, Dr.), company names, place names, job titles |
| ADDRESS | a postal address that can locate a home or office: house number through postal code | a province or district on its own, a branch name |
| DATE_OF_BIRTH | a date that the text says is a birth date | any other date: issue, expiry, appointment, payment |
| THAI_ID | a 13-digit national ID number with a valid check digit | 13-digit numbers that fail the check, order numbers |
| PHONE | a Thai mobile or landline number | extension numbers, short codes such as 1669 |
| EMAIL | a full e-mail address | a domain or a web address |
| BANK_ACCOUNT | a Thai bank account number | amounts, branch codes |
| CREDIT_CARD | a payment card number with a valid Luhn digit | expiry dates, CVV, masked cards showing four digits |
| PASSPORT | a passport number | visa numbers, flight numbers |
| VEHICLE_PLATE | a Thai vehicle registration plate | chassis or engine numbers |
| DRIVER_LICENSE | a driving licence number | licence class, issue and expiry dates |

One mention is one label. If the same person is named three times, that is
three NAME labels. Labels never overlap.

## Template format

One JSON object per line.

```json
{"family": "dev-p-001", "genre": "gov_form", "negative": false, "text": "..."}
```

`text` is a complete Thai document with placeholders in double braces. The
generator replaces each placeholder with a generated value and records the
label. Write `{{kind}}` for a new value, or `{{kind:key}}` to reuse the same
value later in the same document (for example `{{name:a}}` twice for one
person).

Labeled placeholders:

| Placeholder | Type |
|---|---|
| `{{name}}` | NAME, Thai given name and surname |
| `{{name_en}}` | NAME, English given name and surname |
| `{{address}}` | ADDRESS |
| `{{dob}}` | DATE_OF_BIRTH |
| `{{thai_id}}` | THAI_ID |
| `{{phone}}` | PHONE |
| `{{email}}` | EMAIL |
| `{{bank}}` | BANK_ACCOUNT |
| `{{card}}` | CREDIT_CARD |
| `{{passport}}` | PASSPORT |
| `{{plate}}` | VEHICLE_PLATE |
| `{{licence}}` | DRIVER_LICENSE |

Unlabeled placeholders, for values that look like personal data but are not:

| Placeholder | Value |
|---|---|
| `{{date}}` | a date that is not a birth date |
| `{{amount}}` | a money amount |
| `{{order_code}}` | an order or ticket code with letters and digits |
| `{{ref_no}}` | a long all-digit reference number |
| `{{bad_id13}}` | 13 digits that fail the national ID check |
| `{{tracking}}` | a parcel tracking code |
| `{{org}}` | a company or agency name |

## Rules for authors

1. Never type a personal value by hand. Every name, number, address, e-mail
   and birth date comes from a placeholder. Text outside placeholders must
   contain no personal data. Fixed text may contain ordinary words, section
   numbers, and years, but no digit run longer than four digits.
2. Put the title outside the placeholder: `นาย{{name}}`, `คุณ{{name}}`.
3. Use `{{dob}}` only where the sentence makes it a birth date. Use
   `{{date}}` everywhere else.
4. A negative template has no labeled placeholder. It should still be
   tempting: use the unlabeled placeholders and personal-sounding topics.
5. Write the way real Thai documents and messages are written. Mix forms
   with field labels, running prose, chat messages, e-mails, and requests
   typed to an AI assistant. Many values should appear without a field label.
6. Each family must differ from the others in purpose and wording, not only
   in which placeholders it uses.
7. Length varies: some of two lines, most of five to fifteen lines, a few of
   more than 600 characters.
