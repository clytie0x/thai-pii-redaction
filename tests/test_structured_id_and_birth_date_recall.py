"""Recall and honest labels for plates, birth dates, licences, accounts.

Each group pins one mechanism found on the YRSS v2 dev split:

- a plate written with a hyphen between the letters and the number;
- a birth date with an English or abbreviated Thai month, or behind a cue
  the detector did not know (born, mark-stripped OCR of วันเกิด);
- a licence number that sits a clause away from its cue;
- an account in the 3-6-1 layout, or behind the short cue บช.;
- a phone number glued in front of an e-mail address.

Every value is invented. The controls keep the generic label, or stay
unflagged, when the cue or the shape is missing.
"""

from __future__ import annotations

import pytest

from pii_redactor.detectors.fp_detector import detect_fp


def _found(text: str) -> set[tuple[str, str]]:
    return {(e.data_type, e.original_text) for e in detect_fp(text)}


def _of(text: str, data_type: str) -> set[str]:
    return {e.original_text for e in detect_fp(text) if e.data_type == data_type}


def _type_at(text: str, value: str) -> set[str]:
    start = text.index(value)
    end = start + len(value)
    return {e.data_type for e in detect_fp(text) if e.span[0] < end and start < e.span[1]}


# ── VEHICLE_PLATE: hyphen between letters and number ───────────────────────


@pytest.mark.parametrize(
    ("text", "plate"),
    [
        ("รถกระบะสีเทา ทะเบียน 3ขฬ-2716 จอดอยู่หน้าโกดัง", "3ขฬ-2716"),
        ("มอเตอร์ไซค์ทะเบียน ฌต-41 หายจากลานจอด", "ฌต-41"),
        ("เช่ารถตู้ ป้าย งพ-905 สามวัน", "งพ-905"),
        ("คันของน้องคือ 7ธว-6602 ครับ", "7ธว-6602"),
        ("มีรถ ชฎ-3350 ขับตามมาตลอดทาง", "ชฎ-3350"),
        ("ทะเบียนรถผฆ-118", "ผฆ-118"),
        ("ทะเบียน กข-1234", "กข-1234"),
        ("รถป้าย 1กข-5678", "1กข-5678"),
        ("ขับ 8มญ-4170 มารับ", "8มญ-4170"),
    ],
)
def test_hyphenated_plate_is_found(text, plate):
    assert _of(text, "VEHICLE_PLATE") == {plate}


@pytest.mark.parametrize(
    "text",
    [
        "ประชุมที่ห้อง ก-12 ชั้นสอง",
        "ยื่นแบบ ภงด-53 ภายในวันที่เจ็ด",
        "รหัสสินค้า กข-1234 หมดสต็อก",
        "เครื่องปรับอากาศรุ่น ทส-450 ราคาพิเศษ",
        "SKU AB-1234 พร้อมส่ง",
        "เอกสารเลขที่ นร-0507 ลงรับแล้ว",
        "คะแนนกลุ่ม ขค-12 สูงสุด",
        "งวด ตค-2568 จ่ายแล้ว",
        "ทางหลวง ทล-304",
        "ล็อต ผล-2345",
        "หมวด นว-204",
        "แปลง กท-1123",
        "คดีแดง ผบ-4512",
        "รายวิชา ศท-1012",
        "วิชา ศท-1012 ภาคเรียนที่สอง",
        "เครื่อง ซบ-350",
    ],
)
def test_plate_like_code_is_not_a_plate(text):
    assert _of(text, "VEHICLE_PLATE") == set()


def test_spaced_plate_is_unchanged():
    assert _of("รถทะเบียน 2ฒษ 7140 สีขาว", "VEHICLE_PLATE") == {"2ฒษ 7140"}


# ── DATE_OF_BIRTH: date forms ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "date"),
    [
        ("Date of birth: 4 February 1988", "4 February 1988"),
        ("DOB 14 Sep 1992", "14 Sep 1992"),
        ("Born on July 9, 1979 in Lampang", "July 9, 1979"),
        ("เกิดเมื่อ ๗ May ๑๙๘๕ ที่ลำปาง", "๗ May ๑๙๘๕"),
        ("ว/ด/ป เกิด 5 มิ.ย. 2540", "5 มิ.ย. 2540"),
        ("วันเกิด 9 ต.ค. 38 ค่ะ", "9 ต.ค. 38"),
        ("อายุ 41 ปี เกิด 21 กันยายน ค.ศ. 1984", "21 กันยายน ค.ศ. 1984"),
        ("Date of birth18 ก.พ. 2529Sex F", "18 ก.พ. 2529"),
        ("Date of birth30 November 1990Sex M", "30 November 1990"),
        ("เกิดวันที่ 3 สิงหาคม พ.ศ. 2511", "3 สิงหาคม พ.ศ. 2511"),
    ],
)
def test_birth_date_forms_are_found(text, date):
    assert _of(text, "DATE_OF_BIRTH") == {date}


# ── DATE_OF_BIRTH: cue wording ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "date"),
    [
        ("Somying — born 03/11/2531", "03/11/2531"),
        ("birth date 1994-06-27", "1994-06-27"),
        ("Birthday: 12/12/2540", "12/12/2540"),
        ("วนเกด 02/08/2541", "02/08/2541"),
        ("เกดวนท 30 เมษายน 2519", "30 เมษายน 2519"),
        ("วันเดือนปีเกิด 08-10-1996", "08-10-1996"),
    ],
)
def test_birth_cue_wording_gives_birth_label(text, date):
    assert _type_at(text, date) == {"DATE_OF_BIRTH"}


@pytest.mark.parametrize(
    ("text", "date"),
    [
        ("นัดประชุมวันที่ 12 March 2026", "12 March 2026"),
        ("ส่งของวันที่ 3 พ.ค. 2569", "3 พ.ค. 2569"),
        ("วันครบกำหนดชำระ 15/01/2569", "15/01/2569"),
        ("เกิดเหตุเมื่อ 4 June 2024", "4 June 2024"),
        ("ไฟดับเกิดขึ้นเมื่อ 14/02/2569", "14/02/2569"),
        ("ลูกเกด 2 ถุง สั่งวันที่ 01/02/2569", "01/02/2569"),
        ("a stubborn fault since 5 May 2025", "5 May 2025"),
    ],
)
def test_other_dates_keep_the_generic_label(text, date):
    assert _type_at(text, date) == {"DATE"}


@pytest.mark.parametrize(
    "text",
    [
        "เริ่มงานวันที่ 3 พ.ค. 15.00 น.",
        "ส่งรายงาน 7 ก.ย. 68 ครั้ง",
        "you may 2024 times retry",
        "ขนาด 12 March 99999 units",
    ],
)
def test_non_date_shapes_are_not_dates(text):
    found = {e.data_type for e in detect_fp(text)}
    assert not found & {"DATE", "DATE_OF_BIRTH"}


# ── DRIVER_LICENSE: cue a clause away, wider wording ───────────────────────


@pytest.mark.parametrize(
    ("text", "number"),
    [
        ("ใบอนุญาตขับรถจักรยานยนต์ส่วนบุคคล ฉบับที่ 51482260", "51482260"),
        ("ใบขับขี่ถ่ายมาเบลอมากเลย เห็นเลขน่าจะเป็น 46120937 นะ", "46120937"),
        ("ใบขับขี่เลขที่ 60031875", "60031875"),
        ("เลขที่ใบอนุญาตขับรถ 47730018", "47730018"),
        ("Driving licence no. 52219046", "52219046"),
        ("driver’s license # 61102457", "61102457"),
        ("Driver's licence no. 61234567", "61234567"),
        ("Driver Somchai, licence no. 43318820", "43318820"),
        ("ใบขับขี่เลขที่ 61234567", "61234567"),
        ("ใบอนุญาตขับรถยนต์ส่วนบุคคล ฉบับที่ 61234567", "61234567"),
    ],
)
def test_cued_licence_number_is_found(text, number):
    assert _of(text, "DRIVER_LICENSE") == {number}


@pytest.mark.parametrize(
    ("text", "number"),
    [
        ("หมายเลขคำสั่งซื้อ 58120034", "58120034"),
        ("ใบขับขี่หมดอายุแล้วนะคะ ส่วนใบเสร็จรับเงินเลขที่ 58120035 แนบมาด้วย", "58120035"),
        ("ใบขับขี่ออกให้เมื่อปี 2565 ที่สำนักงานขนส่งสาขา 3 รหัสอ้างอิง 51200347", "51200347"),
        ("ใบขับขี่ของลูกค้าอยู่ในแฟ้ม\nรายการที่ต้องตรวจมีดังนี้ 51200348", "51200348"),
        ("Software license no. 40021188", "40021188"),
        ("ใบอนุญาตประกอบกิจการโรงงานเลขที่ 51200349", "51200349"),
        # A bare "licence no." with no driving word is some other licence.
        ("Licence No. 43318820", "43318820"),
        ("Liquor license number 44556677", "44556677"),
        ("Building license no 20251234", "20251234"),
        ("License No. 55667788 for the fishing vessel", "55667788"),
        # A far cue is cut off by a word that starts another kind of number.
        ("ใบขับขี่ของผมหาย แจ้งความไว้แล้ว เลขรับแจ้ง 66012345", "66012345"),
        (
            "ใบขับขี่ต้องพกติดตัวเสมอ ส่วนค่าปรับจ่ายได้ที่ตู้ จำนวน 20000000 ด่ง",
            "20000000",
        ),
    ],
)
def test_uncued_eight_digits_are_not_a_licence(text, number):
    assert "DRIVER_LICENSE" not in _type_at(text, number)
    assert _type_at(text, number) == {"ID_NUMBER"}


# ── BANK_ACCOUNT: 3-6-1 layout and the short cue ───────────────────────────


@pytest.mark.parametrize(
    ("text", "account"),
    [
        ("ในระบบเงินเดือนเป็น 417-052936-8 ค่ะ", "417-052936-8"),
        ("ช่างแอร์ บช.502-771340-6", "502-771340-6"),
        ("โอนเข้า บช. 0891234567 ได้เลย", "0891234567"),
    ],
)
def test_account_layouts_get_the_account_label(text, account):
    assert _type_at(text, account) == {"BANK_ACCOUNT"}


def test_document_number_layout_keeps_the_generic_label():
    assert _type_at("ใบรับเลขที่ 2569-004512", "2569-004512") == {"ID_NUMBER"}


def test_police_bureau_abbreviation_is_not_a_bank_cue():
    assert _type_at("แจ้ง บช.น. 0891234567", "0891234567") == {"PHONE"}


# ── PHONE glued in front of an e-mail address ──────────────────────────────


@pytest.mark.parametrize(
    ("text", "phone", "email"),
    [
        ("ผู้ติดต่อ0957713046wipada.s@example.org", "0957713046", "wipada.s@example.org"),
        ("โทร 038-442917t.manee@example.com", "038-442917", "t.manee@example.com"),
        ("fax 02-613-4480office@example.co.th", "02-613-4480", "office@example.co.th"),
    ],
)
def test_phone_glued_to_email_is_split(text, phone, email):
    assert _found(text) >= {("PHONE", phone), ("EMAIL", email)}


@pytest.mark.parametrize(
    "email",
    ["0957713046@example.org", "user0957713046@example.org", "a0957713046b@example.org"],
)
def test_digits_inside_a_plain_address_stay_one_email(email):
    assert _found(f"อีเมล {email}") == {("EMAIL", email)}
