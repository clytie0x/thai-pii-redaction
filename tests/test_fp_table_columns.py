"""Roster tables: the header names what each column holds.

Recall campaign, 2026-10-24: in pipe- or tab-separated rosters the cue
("เลขประจำตัวนักเรียน", "เลขที่บัญชี", "วันเดือนปีเกิด") sits once in the header
row, so cells in that column carry no cue of their own. Five-digit pupil
numbers and uncued 14-digit accounts were left readable.
"""

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


def test_columns_without_a_known_header_stay_untouched():
    text = "ลำดับ | รายการ | จำนวน\n1 | 62678 | 5\n"
    assert not any(e.data_type == "STUDENT_ID" for e in detect_fp(text))
