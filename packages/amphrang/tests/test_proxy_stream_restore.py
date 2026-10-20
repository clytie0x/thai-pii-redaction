"""StreamRestorer: restore bracket tokens in a stream without full buffering.

The hardest proxy component per the design doc — a token may be split across
arbitrary chunk boundaries, and text that merely looks like a token must pass
through verbatim. Holdback is bounded by the token max length.
"""

import pytest

from amphrang.proxy.stream_restore import StreamRestorer

TOKEN = "[ชื่อ_afffacdccdcebdfbdfeeebaae_qkulookzwtpmgmddkcfe_1]"
PHONE_TOKEN = "[โทรศัพท์_afffacdccdcebdfbdfeeebaae_nypbbxihzeteozvxojjg_1]"
MAPPING = {TOKEN: "นายสมชาย ใจดี", PHONE_TOKEN: "081-234-5678"}


def _run(chunks, mapping=MAPPING):
    restorer = StreamRestorer(mapping)
    out = "".join(restorer.feed(chunk) for chunk in chunks)
    return out + restorer.flush()


def test_plain_text_passes_through_unchanged():
    assert _run(["สวัสดีครับ ", "วันนี้อากาศดี"]) == "สวัสดีครับ วันนี้อากาศดี"


def test_token_inside_one_chunk_is_restored():
    assert _run([f"เรียน {TOKEN} ครับ"]) == "เรียน นายสมชาย ใจดี ครับ"


@pytest.mark.parametrize("split", range(1, len(TOKEN)))
def test_token_split_at_every_boundary_is_restored(split):
    text = f"ก่อน {TOKEN} หลัง"
    start = text.index("[")
    cut = start + split
    assert _run([text[:cut], text[cut:]]) == "ก่อน นายสมชาย ใจดี หลัง"


def test_token_split_across_three_chunks():
    third = len(TOKEN) // 3
    chunks = ["x ", TOKEN[:third], TOKEN[third : 2 * third], TOKEN[2 * third :], " y"]
    assert _run(chunks) == "x นายสมชาย ใจดี y"


def test_two_tokens_in_one_stream():
    assert _run([f"{TOKEN} โทร ", PHONE_TOKEN]) == "นายสมชาย ใจดี โทร 081-234-5678"


def test_bracketed_text_that_is_not_a_token_is_verbatim():
    assert _run(["ดูข้อ [1] และ [หมายเหตุ] ด้วย"]) == "ดูข้อ [1] และ [หมายเหตุ] ด้วย"


def test_unknown_foreign_token_is_left_verbatim():
    foreign = "[ชื่อ_aaaaaaaaaaaaaaaaaaaaaaaaa_zzzzzzzzzzzzzzzzzzzz_9]"
    assert _run([foreign]) == foreign


def test_token_wrapped_in_brackets_is_still_found():
    # An outer '[' opens before the real token; the inner token must restore.
    assert _run([f"[{TOKEN}]"]) == "[นายสมชาย ใจดี]"


def test_open_bracket_at_stream_end_flushes_verbatim():
    assert _run(["ค้างไว้ ["]) == "ค้างไว้ ["


def test_partial_token_at_stream_end_flushes_verbatim():
    partial = TOKEN[:20]
    assert _run([f"จบด้วย {partial}"]) == f"จบด้วย {partial}"


def test_holdback_is_bounded_by_token_max_length():
    # A '[' followed by far more than a token's worth of text with no ']'
    # must not buffer forever: everything comes out while streaming.
    long_tail = "x" * 500
    restorer = StreamRestorer(MAPPING)
    emitted = restorer.feed("[" + long_tail)
    assert long_tail[: len(long_tail) - 200] in emitted  # bulk already emitted
    assert emitted + restorer.flush() == "[" + long_tail


def test_feed_never_emits_a_restorable_token_late():
    # After flush, nothing remains buffered.
    restorer = StreamRestorer(MAPPING)
    out = restorer.feed(TOKEN)
    out += restorer.flush()
    assert out == "นายสมชาย ใจดี"
    assert restorer.flush() == ""
