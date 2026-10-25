"""Roster tables: the header names what each column holds.

Recall campaign, 2026-10-24: in pipe- or tab-separated rosters the cue
("เลขประจำตัวนักเรียน", "เลขที่บัญชี", "วันเดือนปีเกิด") sits once in the header
row, so cells in that column carry no cue of their own. Five-digit pupil
numbers and uncued 14-digit accounts were left readable.
"""

import pytest

from pii_redactor.detectors.fp_detector import detect_fp

PIPE_TABLE = (
    "ลำดับ | เลขประจำตัวนักเรียน | ชื่อ-สกุล | วันเดือนปีเกิด | เลขที่บัญชี | เลขประจำตัวประชาชน\n"
    "1 | 62678 | เด็กหญิงอรุณี ใจดี | 13/02/2555 | 25986056263335 | 1-2345-67890-12-4\n"
    "2 | 62841 | เด็กชายภูมิ สินมณี | 5 ก.พ. 2556 | 10120499276380 | 3-1007-00234-56-1\n"
)
TAB_TABLE = "ที่\tรหัสนักศึกษา\tชื่อ\n1\t6845-531-166\tนายชัยณรงค์ ดีงาม\n2\t6846-830-632\tนางสาวพร สุขใจ\n"


def _types_over(text: str, value: str) -> set[str]:
    start = text.index(value)
    end = start + len(value)
    return {e.data_type for e in detect_fp(text) if e.span[0] <= start and end <= e.span[1]}


def test_student_column_cells_are_student_ids():
    assert "STUDENT_ID" in _types_over(PIPE_TABLE, "62678")
    assert "STUDENT_ID" in _types_over(PIPE_TABLE, "62841")
    assert "STUDENT_ID" in _types_over(TAB_TABLE, "6845-531-166")


def test_account_column_cells_are_bank_accounts():
    assert "BANK_ACCOUNT" in _types_over(PIPE_TABLE, "25986056263335")


def test_birth_date_column_cells_are_birth_dates():
    assert "DATE_OF_BIRTH" in _types_over(PIPE_TABLE, "13/02/2555")
    assert "DATE_OF_BIRTH" in _types_over(PIPE_TABLE, "5 ก.พ. 2556")


def test_id_column_masks_a_mistyped_national_id():
    assert "THAI_ID" in _types_over(PIPE_TABLE, "1-2345-67890-12-4")


def test_space_aligned_tables_copied_from_pdf_are_read_too():
    text = (
        "ลำดับ  เลขประจำตัวนักเรียน  ชื่อ-สกุล  วันเดือนปีเกิด\n"
        "1  62678  เด็กหญิงอรุณี ใจดี  13/02/2555\n"
        "2  62841  เด็กชายภูมิ สินมณี  5 ก.พ. 2556\n"
    )
    assert "STUDENT_ID" in _types_over(text, "62678")
    assert "DATE_OF_BIRTH" in _types_over(text, "5 ก.พ. 2556")


def test_data_row_without_a_four_digit_run_keeps_the_header():
    # "66-208-147-39" has no four digits in a row; the row used to be read
    # as a new header and dropped the column types.
    text = (
        "Student number     Name                Course     Grade\n"
        "66-208-147-39     Siriporn Lertsiri    ECO 312    A\n"
        "66-208-147-52     Kritsada Boonmee     ECO 312    B+\n"
    )
    assert "STUDENT_ID" in _types_over(text, "66-208-147-39")
    assert "STUDENT_ID" in _types_over(text, "66-208-147-52")


def test_abbreviated_student_header_types_spaced_ids():
    text = (
        "ลำดับ  รหัส นศ.  ชื่อ  สถานประกอบการ\n"
        "01  66 09 781001  นายภาคิน เสริมศรี  บริษัท ขอบฟ้าดิจิทัล จำกัด\n"
        "02  66 09 781002  นางสาวนลินทิพย์ หาญชนะ  โรงแรมสวนบุหงา\n"
    )
    assert "STUDENT_ID" in _types_over(text, "66 09 781001")


def test_bare_id_number_header_in_a_school_roster_types_pupil_numbers():
    text = (
        "ที่ | เลขประจำตัว | ชื่อ-สกุล | สถานะ\n"
        "1 | 68130218 | ด.ญ.กมลชนก วงศ์สะหวัน | มา\n"
        "2 | 68130223 | ด.ช.ปกรณ์ นาคสวัสดิ์ | ลาป่วย\n"
    )
    assert "STUDENT_ID" in _types_over(text, "68130218")


def test_bare_id_number_header_without_school_context_is_not_a_student_column():
    text = "ที่ | เลขประจำตัว | ชื่อ-สกุล | แผนก\n1 | 68130218 | นายปกรณ์ นาคสวัสดิ์ | บัญชี\n"
    assert "STUDENT_ID" not in _types_over(text, "68130218")


@pytest.mark.parametrize(
    ("text", "value"),
    [
        (
            "แบบบันทึกการใช้ห้องปฏิบัติการ คณะวิทยาศาสตร์ มหาวิทยาลัยแห่งหนึ่ง\n"
            "ลำดับ | ผู้เข้าใช้ | คณะ | รหัส | เวลาออก\n"
            "01 | นายสิรวิชญ์ เจริญกิจ | วิศวกรรมศาสตร์ | 6810427 | 15.20\n",
            "6810427",
        ),
        (
            "ทุนการศึกษาสำหรับนักศึกษา ปีการศึกษา 2569\n"
            "ลำดับ | รหัสผู้สมัคร | ผู้ได้รับทุน | ยอดอนุมัติ\n"
            "1 | 651201034822 | นางสาวญาดา ภูมิสิงห์ | 8,000\n",
            "651201034822",
        ),
        (
            "ห้องสมุดวิทยาลัยเวียงแก้ว\nเวลา   เลขประจำตัว   ผู้ใช้บริการ   กำหนดคืน\n"
            "09.15   661234567   นางสาวคำหล้า ปันแก้ว   10 ต.ค. 2569\n",
            "661234567",
        ),
        (
            "No. | Enrolment code | Student | Status\n1 | 67124-10583 | Narin Chaiyapruk | Cleared\n",
            "67124-10583",
        ),
    ],
)
def test_bare_code_headers_in_student_rosters_type_student_ids(text, value):
    # A bare รหัส / เลขประจำตัว / ID column is a student code only in a school
    # document whose rows name a person by title.
    assert "STUDENT_ID" in _types_over(text, value)


def test_a_bare_code_column_in_a_course_list_is_not_a_student_column():
    text = (
        "หลักสูตรวิทยาศาสตรบัณฑิต มหาวิทยาลัยแห่งหนึ่ง ภาคเรียนที่ 1\n"
        "รหัส | ชื่อวิชา | หน่วยกิต\n01418211 | การเขียนโปรแกรม | 3\n01418212 | โครงสร้างข้อมูล | 3\n"
    )
    assert "STUDENT_ID" not in _types_over(text, "01418211")


def test_rows_split_by_spaces_under_a_pipe_header_are_read():
    text = (
        "ลำดับ | ชื่อและสกุล | เลขประจำตัวประชาชน | วัน/เดือน/ปีเกิด | จำนวนเงิน\n"
        "1   นาย สิทธิชัย ศรีบุญเรือง   1255262103169   13-07-2512   1,000.00\n"
        "2   นาง ประนอม โพธิ์แก้ว   5382860291430   16-08-2516   1,000.00\n"
    )
    assert "DATE_OF_BIRTH" in _types_over(text, "13-07-2512")


def test_a_row_wrapped_onto_the_next_line_keeps_its_column_types():
    text = (
        "ลำดับ | ชื่อ-สกุล | วัน/เดือน/ปีเกิด | อายุ | ที่อยู่ | เบอร์โทร\n"
        "1 | นายประยูร นาคจันทร์ | 20-12-2493 | 75 | 88/2 หมู่ 6 | 089 430 3603\n"
        "2 | นายชูศักดิ์ เพชรดี | 24.08.2482 | 86 |\n"
        "    100/6 หมู่ 1 ต.ปากแพรก | 0812345670\n"
    )
    assert "DATE_OF_BIRTH" in _types_over(text, "24.08.2482")


@pytest.mark.parametrize(
    ("header", "cell", "etype"),
    [
        ("เบอร์โทร", "66930072377", "PHONE"),
        ("หนังสือเดินทาง", "G19549439", "PASSPORT"),
        ("ทะเบียนรถ", "กต 2700 กรุงเทพมหานคร", "VEHICLE_PLATE"),
    ],
)
def test_phone_passport_and_plate_columns_type_their_cells(header, cell, etype):
    text = f"ลำดับ | ชื่อ-สกุล | {header} | หมายเหตุ\n1 | นายสมบัติ อินทร์แก้ว | {cell} | -\n"
    assert etype in _types_over(text, cell) or etype in _types_over(text, cell.split()[0])


def test_columns_without_a_known_header_stay_untouched():
    text = "ลำดับ | รายการ | จำนวน\n1 | 62678 | 5\n"
    assert not any(e.data_type == "STUDENT_ID" for e in detect_fp(text))
