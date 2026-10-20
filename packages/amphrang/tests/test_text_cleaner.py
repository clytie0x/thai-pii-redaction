"""text_cleaner tests, extracted from the retired step-1 ingest suite.

`clean` and `clean_length_preserving` are the only ingest-era modules still on
the runtime path (detect/anonymize/analyze all pass through them).
"""

from amphrang.engine.ingest.text_cleaner import CleanResult, clean


def test_clean_whitespace_normalization():
    text = "Hello   World\n\n\n\nParagraph"
    result = clean(text)
    assert "   " not in result.text  # no triple spaces
    assert "\n\n\n" not in result.text  # no triple newlines
    assert isinstance(result, CleanResult)


def test_clean_unicode_normalization():
    # NFC normalization: combine base + combining char into precomposed
    import unicodedata

    # Thai text should remain valid after NFC
    text = "สวัสดี"
    result = clean(text)
    assert unicodedata.is_normalized("NFC", result.text)


def test_clean_removes_zero_width():
    text = "Hello​World"  # zero-width space between
    result = clean(text)
    assert "​" not in result.text


def test_clean_thai_digits():
    text = "มี ๑๒๓ คน"
    result = clean(text)
    assert "123" in result.text
    assert "๑" not in result.text


def test_clean_returns_clean_result():
    result = clean("test text")
    assert hasattr(result, "text")
    assert hasattr(result, "post_clean_warnings")


def test_clean_dropped_the_dead_stage_outputs():
    """Stages 4/5/6 were removed (kill-list, verified): stage 4 never changed
    real text yet loaded the whole Thai dictionary, stage 5 flagged every word
    containing B or Z, stage 6's interactive branch was unreachable (no caller
    passes interactive=True) — and nothing consumed any of their outputs."""
    result = clean("test text")
    for dead in ("skipped_sentence_review", "ocr_error_flags", "broken_sentence_candidates"):
        assert not hasattr(result, dead), f"{dead} should have been removed with its stage"


def test_clean_does_not_depend_on_the_thai_tokenizer(monkeypatch):
    """Stage 4 tokenized every input through PyThaiNLP just to rejoin it
    unchanged. Cleaning must no longer touch the tokenizer at all."""
    import pythainlp

    def _boom(*a, **k):
        raise AssertionError("clean() must not tokenize (stage 4 is gone)")

    monkeypatch.setattr(pythainlp, "word_tokenize", _boom)
    result = clean("ผมชื่อสมชาย ใจดี เบอร์ 081-234-5678")
    assert "สมชาย" in result.text


def test_clean_preserves_text_it_used_to_rewrite():
    """Regression: the removed merge step could concatenate adjacent Thai
    tokens. Cleaning now only normalizes — Thai content passes through."""
    text = "ผู้ป่วยมีอาการปวดศีรษะ และได้รับการวินิจฉัยว่าเป็นไมเกรน"
    assert clean(text).text == text


def test_clean_empty_text():
    result = clean("")
    assert result.text == ""


def test_clean_sample_thai():
    from pathlib import Path

    text = Path("tests/sample_thai.txt").read_text(encoding="utf-8")
    result = clean(text, interactive=False)
    assert "วิทยา" in result.text
    assert "1101200012345" in result.text  # Thai ID preserved


# ---------------------------------------------------------------------------
# text_cleaner: clean_length_preserving
# ---------------------------------------------------------------------------


def test_clean_length_preserving_converts_thai_digits_without_moving_offsets():
    """The detection path needs Thai numerals converted but offsets intact,
    because entity spans must map back into the caller's original text."""
    from amphrang.engine.ingest.text_cleaner import clean_length_preserving

    raw = "โทร ๐๘๑-๒๓๔-๕๖๗๘  ครับ​"
    out = clean_length_preserving(raw)

    assert len(out) == len(raw), "offsets moved; spans would misalign"
    assert "081-234-5678" in out
    assert "  " in out, "whitespace must NOT be collapsed on this tier"
    assert "​" in out, "zero-width must NOT be stripped on this tier"


def test_thai_numeral_phone_is_detected_after_length_preserving_clean():
    from amphrang.engine.detectors.fp_detector import detect_fp
    from amphrang.engine.ingest.text_cleaner import clean_length_preserving

    cleaned = clean_length_preserving("ติดต่อ ๐๘๑-๒๓๔-๕๖๗๘")
    assert [e for e in detect_fp(cleaned) if e.data_type == "PHONE"]
