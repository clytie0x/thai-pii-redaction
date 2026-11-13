"""Seeded value generators for the YRSS evaluation v2 corpus.

Every value is fabricated. Each kind has several surface forms so that
variants of one template differ in more than digits. The pools here are
separate from the ones in ``benchmark/blind_v2`` on purpose.
"""

from __future__ import annotations

import random

_GIVEN = (
    ("กิตติพงษ์", "kittipong"),
    ("ณัฐวุฒิ", "nattawut"),
    ("ธนากร", "thanakorn"),
    ("ปิยะพงศ์", "piyapong"),
    ("วรเชษฐ์", "worachet"),
    ("ศุภชัย", "supachai"),
    ("อนุชา", "anucha"),
    ("เอกชัย", "ekkachai"),
    ("จักรพันธ์", "chakkraphan"),
    ("ภานุวัฒน์", "panuwat"),
    ("สิทธิชัย", "sitthichai"),
    ("วีรยุทธ", "weerayut"),
    ("ชัยวัฒน์", "chaiwat"),
    ("ธีรพล", "teerapon"),
    ("พงศกร", "pongsakorn"),
    ("รัฐพล", "rattapon"),
    ("สมศักดิ์", "somsak"),
    ("บุญเลิศ", "boonlert"),
    ("ประเสริฐ", "prasert"),
    ("มานพ", "manop"),
    ("กนกวรรณ", "kanokwan"),
    ("จิราพร", "jiraporn"),
    ("ณัฐธิดา", "nattida"),
    ("ธิดารัตน์", "thidarat"),
    ("นันทนา", "nanthana"),
    ("ปวีณา", "paweena"),
    ("พรทิพย์", "porntip"),
    ("รัตนาภรณ์", "rattanaporn"),
    ("วิไลวรรณ", "wilaiwan"),
    ("ศิริพร", "siriporn"),
    ("สุนิสา", "sunisa"),
    ("อรอุมา", "onuma"),
    ("กัลยา", "kanlaya"),
    ("ชุติมา", "chutima"),
    ("เบญจมาศ", "benjamas"),
    ("มณีรัตน์", "maneerat"),
    ("ลัดดาวัลย์", "laddawan"),
    ("สายสุนีย์", "saisunee"),
    ("อัญชลี", "anchalee"),
    ("ดวงใจ", "duangjai"),
)
_SURNAME = (
    ("แก้วมณี", "kaewmanee"),
    ("ศรีสวัสดิ์", "srisawat"),
    ("ทองประเสริฐ", "thongprasert"),
    ("บุญมา", "boonma"),
    ("จันทร์หอม", "chanhom"),
    ("วงศ์ใหญ่", "wongyai"),
    ("สุขเกษม", "sukkasem"),
    ("พรหมมา", "promma"),
    ("อินทรสุวรรณ", "intharasuwan"),
    ("รุ่งเรืองศรี", "rungrueangsri"),
    ("ชัยมงคล", "chaimongkol"),
    ("นาคสวัสดิ์", "naksawat"),
    ("เพชรรัตน์", "phetcharat"),
    ("มั่นคง", "mankhong"),
    ("ใจดี", "jaidee"),
    ("สายทอง", "saithong"),
    ("ปัญญาดี", "panyadee"),
    ("คงเจริญ", "khongcharoen"),
    ("ทรัพย์สมบูรณ์", "sapsomboon"),
    ("วัฒนกุล", "wattanakul"),
    ("ศักดิ์สิทธิ์", "saksit"),
    ("เรืองฤทธิ์", "rueangrit"),
    ("พูลสวัสดิ์", "poonsawat"),
    ("หอมจันทร์", "homchan"),
    ("ดวงแก้ว", "duangkaew"),
    ("สมบัติทอง", "sombatthong"),
    ("กาญจนวงศ์", "kanchanawong"),
    ("ประทุมทอง", "prathumthong"),
    ("อ่อนละมัย", "onlamai"),
    ("ยิ้มแย้ม", "yimyaem"),
    ("บัวขาว", "buakhao"),
    ("ธรรมรักษ์", "thammarak"),
    ("สิงห์ทอง", "singthong"),
    ("มหาวงศ์", "mahawong"),
    ("ไชยวงค์", "chaiyawong"),
    ("นิลวงศ์", "ninlawong"),
)
_MONTHS = (
    ("มกราคม", "ม.ค.", "January"),
    ("กุมภาพันธ์", "ก.พ.", "February"),
    ("มีนาคม", "มี.ค.", "March"),
    ("เมษายน", "เม.ย.", "April"),
    ("พฤษภาคม", "พ.ค.", "May"),
    ("มิถุนายน", "มิ.ย.", "June"),
    ("กรกฎาคม", "ก.ค.", "July"),
    ("สิงหาคม", "ส.ค.", "August"),
    ("กันยายน", "ก.ย.", "September"),
    ("ตุลาคม", "ต.ค.", "October"),
    ("พฤศจิกายน", "พ.ย.", "November"),
    ("ธันวาคม", "ธ.ค.", "December"),
)
# road, khwaeng, khet, postal code
_BANGKOK = (
    ("ลาดพร้าว", "จอมพล", "จตุจักร", "10900"),
    ("พหลโยธิน", "สามเสนใน", "พญาไท", "10400"),
    ("สุขุมวิท", "คลองตันเหนือ", "วัฒนา", "10110"),
    ("รามคำแหง", "หัวหมาก", "บางกะปิ", "10240"),
    ("เพชรเกษม", "บางหว้า", "ภาษีเจริญ", "10160"),
    ("พระราม 2", "แสมดำ", "บางขุนเทียน", "10150"),
    ("จรัญสนิทวงศ์", "บางอ้อ", "บางพลัด", "10700"),
    ("สาทรใต้", "ทุ่งมหาเมฆ", "สาทร", "10120"),
    ("ศรีนครินทร์", "หนองบอน", "ประเวศ", "10250"),
    ("รัชดาภิเษก", "ดินแดง", "ดินแดง", "10400"),
    ("แจ้งวัฒนะ", "ทุ่งสองห้อง", "หลักสี่", "10210"),
    ("อ่อนนุช", "สวนหลวง", "สวนหลวง", "10250"),
)
# road, tambon, amphoe, province, postal code
_PROVINCIAL = (
    ("ห้วยแก้ว", "สุเทพ", "เมืองเชียงใหม่", "เชียงใหม่", "50200"),
    ("มิตรภาพ", "ในเมือง", "เมืองขอนแก่น", "ขอนแก่น", "40000"),
    ("กาญจนวณิชย์", "คอหงส์", "หาดใหญ่", "สงขลา", "90110"),
    ("สุขุมวิท", "แสนสุข", "เมืองชลบุรี", "ชลบุรี", "20130"),
    ("เทพกระษัตรี", "รัษฎา", "เมืองภูเก็ต", "ภูเก็ต", "83000"),
    ("มิตรภาพ", "ในเมือง", "เมืองนครราชสีมา", "นครราชสีมา", "30000"),
    ("พหลโยธิน", "เวียง", "เมืองเชียงราย", "เชียงราย", "57000"),
    ("ราชดำเนิน", "ในเมือง", "เมืองนครศรีธรรมราช", "นครศรีธรรมราช", "80000"),
    ("ชยางกูร", "ในเมือง", "เมืองอุบลราชธานี", "อุบลราชธานี", "34000"),
    ("สิงหวัฒน์", "ในเมือง", "เมืองพิษณุโลก", "พิษณุโลก", "65000"),
    ("ติวานนท์", "ตลาดขวัญ", "เมืองนนทบุรี", "นนทบุรี", "11000"),
    ("เทพารักษ์", "บางเมือง", "เมืองสมุทรปราการ", "สมุทรปราการ", "10270"),
    ("โพศรี", "หมากแข้ง", "เมืองอุดรธานี", "อุดรธานี", "41000"),
    ("ตลาดใหม่", "ตลาด", "เมืองสุราษฎร์ธานี", "สุราษฎร์ธานี", "84000"),
    ("สุขุมวิท", "เนินพระ", "เมืองระยอง", "ระยอง", "21000"),
    ("แสงชูโต", "บ้านเหนือ", "เมืองกาญจนบุรี", "กาญจนบุรี", "71000"),
)
_BUILDINGS = ("ศุภาลัยวิลล์", "ลุมพินีเพลส", "เดอะทรีคอนโด", "บ้านสวนธน", "พฤกษาวิลเลจ")
_EMAIL_DOMAINS = ("example.com", "example.co.th", "example.org", "mail.example.net")
_ORGS = (
    "บริษัท สยามนวกิจ จำกัด",
    "บริษัท ทักษิณโลจิสติกส์ จำกัด (มหาชน)",
    "ห้างหุ้นส่วนจำกัด รุ่งอรุณการช่าง",
    "บริษัท เอเชียดาต้าเวิร์กส์ จำกัด",
    "สำนักงานเทศบาลตำบลบ้านสวน",
    "โรงพยาบาลเมืองทองเวชการ",
    "บริษัท กรีนลีฟ ประกันภัย จำกัด",
    "Northern Star Trading Co., Ltd.",
)
_PLATE_LETTERS = "กขฆงจฉชฌญฎฐฒณดตถทธนบผพภมยรลวศษสฬอฮ"
_THAI_DIGITS = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")


def digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())


def _number(rng: random.Random, length: int) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(length))


def thai_id_valid(number: str) -> bool:
    if len(number) != 13 or not number.isdigit():
        return False
    total = sum(int(number[i]) * (13 - i) for i in range(12))
    return (11 - total % 11) % 10 == int(number[12])


def luhn_valid(number: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(number)):
        digit = int(char)
        if index % 2 == 1:
            digit = digit * 2 - 9 if digit > 4 else digit * 2
        total += digit
    return bool(number) and total % 10 == 0


def _thai_id_digits(rng: random.Random) -> str:
    body = str(rng.randint(1, 8)) + _number(rng, 11)
    total = sum(int(body[i]) * (13 - i) for i in range(12))
    return body + str((11 - total % 11) % 10)


def thai_id(rng: random.Random) -> str:
    d = _thai_id_digits(rng)
    form = rng.random()
    if form < 0.5:
        return d
    sep = "-" if form < 0.85 else " "
    return sep.join((d[0], d[1:5], d[5:10], d[10:12], d[12]))


def bad_id13(rng: random.Random) -> str:
    d = _thai_id_digits(rng)
    return d[:12] + str((int(d[12]) + rng.randint(1, 9)) % 10)


def phone(rng: random.Random) -> str:
    form = rng.random()
    if form < 0.2:
        area = rng.choice(("02", "053", "043", "074", "038", "076"))
        rest = _number(rng, 9 - len(area))
        return f"{area}-{rest[:3]}-{rest[3:]}" if area == "02" else f"{area}-{rest}"
    d = "0" + rng.choice("689") + _number(rng, 8)
    if form < 0.5:
        return f"{d[:3]}-{d[3:6]}-{d[6:]}"
    if form < 0.75:
        return d
    if form < 0.9:
        return f"{d[:3]} {d[3:6]} {d[6:]}"
    return f"+66 {d[1:3]} {d[3:6]} {d[6:]}"


def bank(rng: random.Random) -> str:
    d = str(rng.randint(1, 9)) + _number(rng, 9)
    form = rng.random()
    if form < 0.5:
        return f"{d[:3]}-{d[3]}-{d[4:9]}-{d[9]}"
    if form < 0.8:
        return d
    return f"{d[:3]}-{d[3:9]}-{d[9]}"


def card(rng: random.Random) -> str:
    while True:
        body = rng.choice(("4", "51", "52", "55")) + _number(rng, 14)
        body = body[:15]
        check = next(c for c in "0123456789" if luhn_valid(body + c))
        d = body + check
        form = rng.random()
        if form < 0.45:
            return "-".join(d[i : i + 4] for i in range(0, 16, 4))
        if form < 0.8:
            return " ".join(d[i : i + 4] for i in range(0, 16, 4))
        return d


def passport(rng: random.Random) -> str:
    letters = "".join(rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(2))
    return letters + _number(rng, 7)


def plate(rng: random.Random) -> str:
    letters = "".join(rng.choice(_PLATE_LETTERS) for _ in range(2))
    number = rng.randint(1, 9999)
    lead = str(rng.randint(1, 9)) if rng.random() < 0.5 else ""
    sep = " " if rng.random() < 0.8 else "-"
    return f"{lead}{letters}{sep}{number}"


def licence(rng: random.Random) -> str:
    """Eight digits. See the format addendum in the pre-registration."""
    return str(rng.randint(4, 6)) + _number(rng, 7)


def dob(rng: random.Random) -> str:
    day, month, year = rng.randint(1, 28), rng.randint(1, 12), rng.randint(2500, 2550)
    full, short, english = _MONTHS[month - 1]
    form = rng.random()
    if form < 0.3:
        return f"{day:02d}/{month:02d}/{year}"
    if form < 0.55:
        return f"{day} {full} {year}"
    if form < 0.7:
        return f"{day} {short} {year}"
    if form < 0.8:
        return f"{day} {full} พ.ศ. {year}"
    if form < 0.9:
        return f"{day:02d}-{month:02d}-{year - 543}"
    return f"{day} {english} {year - 543}"


def date(rng: random.Random) -> str:
    day, month, year = rng.randint(1, 28), rng.randint(1, 12), rng.randint(2566, 2569)
    full, short, _english = _MONTHS[month - 1]
    form = rng.random()
    if form < 0.4:
        return f"{day:02d}/{month:02d}/{year}"
    if form < 0.75:
        return f"{day} {full} {year}"
    return f"{day} {short} {str(year)[2:]}"


def address(rng: random.Random) -> str:
    house = (
        f"{rng.randint(1, 499)}/{rng.randint(1, 99)}"
        if rng.random() < 0.6
        else str(rng.randint(1, 499))
    )
    soi = rng.randint(1, 89)
    short = rng.random() < 0.3
    extra = f"หมู่บ้าน{rng.choice(_BUILDINGS)} " if rng.random() < 0.2 else ""
    if rng.random() < 0.45:
        road, khwaeng, khet, postal = rng.choice(_BANGKOK)
        if short:
            return f"{house} {extra}ซ.{road} {soi} ถ.{road} แขวง{khwaeng} เขต{khet} กทม. {postal}"
        return (
            f"{house} {extra}ซอย{road} {soi} ถนน{road} แขวง{khwaeng} "
            f"เขต{khet} กรุงเทพมหานคร {postal}"
        )
    road, tambon, amphoe, province, postal = rng.choice(_PROVINCIAL)
    moo = rng.randint(1, 14)
    if short:
        return f"{house} {extra}ม.{moo} ถ.{road} ต.{tambon} อ.{amphoe} จ.{province} {postal}"
    return f"{house} {extra}หมู่ {moo} ถนน{road} ตำบล{tambon} อำเภอ{amphoe} จังหวัด{province} {postal}"


def person(rng: random.Random) -> tuple[str, str]:
    """Return one person's Thai and English full names."""
    given, en_given = rng.choice(_GIVEN)
    surname, en_surname = rng.choice(_SURNAME)
    return f"{given} {surname}", f"{en_given.title()} {en_surname.title()}"


def email(rng: random.Random) -> str:
    _thai, english = person(rng)
    given, surname = english.lower().split()
    form = rng.random()
    if form < 0.4:
        local = f"{given}.{surname}"
    elif form < 0.7:
        local = f"{given}{rng.randint(1, 99)}"
    else:
        local = f"{given[0]}.{surname}{rng.randint(10, 99)}"
    return f"{local}@{rng.choice(_EMAIL_DOMAINS)}"


def amount(rng: random.Random) -> str:
    value = rng.randint(120, 480_000)
    return f"{value:,}.{rng.choice(('00', '50', '75'))}" if rng.random() < 0.6 else f"{value:,}"


def order_code(rng: random.Random) -> str:
    prefix = rng.choice(("ORD", "SO", "TK", "INV", "REQ"))
    return f"{prefix}-{rng.randint(2566, 2569)}-{_number(rng, 5)}"


def ref_no(rng: random.Random) -> str:
    """All digits, at a length no scored identifier uses, and never Luhn-valid."""
    while True:
        value = str(rng.randint(1, 9)) + _number(rng, rng.choice((11, 12, 14)) - 1)
        if not luhn_valid(value):
            return value


def tracking(rng: random.Random) -> str:
    return f"{rng.choice(('EX', 'RG', 'KE', 'TP'))}{_number(rng, 9)}TH"


def org(rng: random.Random) -> str:
    return rng.choice(_ORGS)


def thai_digits(text: str) -> str:
    return text.translate(_THAI_DIGITS)


FACTORIES = {
    "address": address,
    "dob": dob,
    "thai_id": thai_id,
    "phone": phone,
    "email": email,
    "bank": bank,
    "card": card,
    "passport": passport,
    "plate": plate,
    "licence": licence,
    "date": date,
    "amount": amount,
    "order_code": order_code,
    "ref_no": ref_no,
    "bad_id13": bad_id13,
    "tracking": tracking,
    "org": org,
}
