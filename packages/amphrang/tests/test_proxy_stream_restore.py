"""StreamRestorer: restore bracket tokens in a stream without full buffering.

The hardest proxy component per the design doc — a token may be split across
arbitrary chunk boundaries, and text that merely looks like a token must pass
through verbatim. Context and token lookahead stay bounded.
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


@pytest.mark.parametrize(
    "template",
    [
        "https://example.test/?contact={token}",
        "mailto:{token}",
        "//example.test/{token}",
        "[contact](https://example.test/{token})",
        "![contact]({token})",
        "[contact]: https://example.test/{token}\n",
        "{token}: https://example.test/\n",
        '<a title="{token}" href="/contact">',
        "<item value='{token}'/>",
        "<!-- {token} -->",
        "<script>const contact = '{token}';</script>",
        "<style>contact: {token};</style>",
    ],
    ids=[
        "https",
        "mailto",
        "network-path",
        "markdown-link",
        "markdown-image",
        "reference-destination",
        "reference-token-label",
        "html-attribute",
        "xml-attribute",
        "comment",
        "script",
        "style",
    ],
)
def test_protected_context_never_emits_original_at_any_chunk_split(template):
    text = template.format(token=TOKEN)
    for split in range(len(text) + 1):
        restorer = StreamRestorer(MAPPING)
        emissions = [restorer.feed(text[:split]), restorer.feed(text[split:]), restorer.flush()]
        assert all(MAPPING[TOKEN] not in piece for piece in emissions), split
        assert "".join(emissions) == text, split


@pytest.mark.parametrize(
    "prefix",
    ["https://example.test/", "[contact](", '<a title="', "<!-- ", "<script>"],
    ids=["url", "markdown", "attribute", "comment", "script"],
)
def test_incomplete_context_at_successful_eof_stays_protected(prefix):
    text = prefix + TOKEN
    restorer = StreamRestorer(MAPPING)
    emissions = [restorer.feed(char) for char in text] + [restorer.flush()]
    assert all(MAPPING[TOKEN] not in piece for piece in emissions)
    assert "".join(emissions) == text


def test_complete_line_start_token_waits_for_reference_colon_or_successful_eof():
    restorer = StreamRestorer(MAPPING)
    assert restorer.feed(TOKEN) == ""
    assert restorer.feed(" \t") == ""
    assert restorer.feed(": https://example.test/\n") == TOKEN + " \t: https://example.test/\n"
    assert restorer.flush() == ""
    assert _run([TOKEN]) == MAPPING[TOKEN]


def test_discard_before_reference_decision_drops_complete_token_and_mapping():
    restorer = StreamRestorer(MAPPING)
    assert restorer.feed(TOKEN) == ""
    restorer.discard()
    assert restorer.flush() == ""
    assert restorer._buffer == "" and restorer._mapping == {}


def test_plain_text_restores_incrementally_between_guarded_occurrences():
    restorer = StreamRestorer(MAPPING)
    assert restorer.feed("prefix ") == "prefix "
    assert restorer.feed(TOKEN + " ") == MAPPING[TOKEN] + " "
    text = "https://example.test/" + TOKEN + " "
    assert restorer.feed(text) == text
    assert restorer.feed(PHONE_TOKEN + " suffix") == MAPPING[PHONE_TOKEN] + " suffix"
    assert restorer.flush() == ""


def test_legacy_adjacent_unknown_and_unicode_tokens_keep_matching_grammar():
    legacy = "[Sensitive_1]"
    unknown = "[ชื่อ_ต่างระบบ_2]"
    mapping = {**MAPPING, legacy: "synthetic-sensitive"}
    text = "ข้อความ " + TOKEN + PHONE_TOKEN + legacy + unknown + " 😀"
    expected = "ข้อความ " + MAPPING[TOKEN] + MAPPING[PHONE_TOKEN] + mapping[legacy] + unknown + " 😀"
    assert _run(list(text), mapping=mapping) == expected


def test_non_bracket_surrogates_and_token_at_names_remain_unsupported_in_stream():
    mapping = {"Token@known": "synthetic-original", "ชื่อสมมติ": "synthetic-name"}
    text = "plain Token@known ชื่อสมมติ https://example.test/Token@known"
    assert _run(list(text), mapping=mapping) == text


def test_ambiguous_reference_lookahead_remains_bounded_and_protected():
    restorer = StreamRestorer(MAPPING)
    text = TOKEN + " " * 4000 + ": " + TOKEN + "\n"
    emissions = []
    for char in text:
        emissions.append(restorer.feed(char))
        assert len(restorer._buffer) <= 256
    emissions.append(restorer.flush())
    assert all(MAPPING[TOKEN] not in piece for piece in emissions)
    assert "".join(emissions) == text
