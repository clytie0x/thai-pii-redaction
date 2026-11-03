"""Canonical context policy and streamed restoration privacy contracts."""

import pytest

from pii_redactor.restore_context import GuardedStreamRestorer, machine_context_spans

TOKEN = "[Sensitive_1]"
ORIGINAL = "synthetic-original"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (TOKEN, ORIGINAL),
        (f"hello {TOKEN}!", f"hello {ORIGINAL}!"),
        (f"[{TOKEN}]", f"[{ORIGINAL}]"),
        (f"{TOKEN}{TOKEN}", ORIGINAL + ORIGINAL),
        (f"{TOKEN} https://example.invalid/{TOKEN}", f"{ORIGINAL} https://example.invalid/{TOKEN}"),
        (f"https://example.invalid/?q={TOKEN}", f"https://example.invalid/?q={TOKEN}"),
        (f"https://example.invalid/a'{TOKEN}", f"https://example.invalid/a'{TOKEN}"),
        (f"https://example.invalid/?q=a'{TOKEN}", f"https://example.invalid/?q=a'{TOKEN}"),
        (f"mailto:{TOKEN}", f"mailto:{TOKEN}"),
        (f"www.example.invalid/{TOKEN}", f"www.example.invalid/{TOKEN}"),
        (f"//example.invalid/{TOKEN}", f"//example.invalid/{TOKEN}"),
        (f"[{TOKEN}](relative/{TOKEN})", f"[{ORIGINAL}](relative/{TOKEN})"),
        (f"![image](relative(a/{TOKEN})) {TOKEN}", f"![image](relative(a/{TOKEN})) {ORIGINAL}"),
        (f"[label](<relative)/{TOKEN}>)", f"[label](<relative)/{TOKEN}>)"),
        (f"[label](<relative)/{TOKEN}", f"[label](<relative)/{TOKEN}"),
        (f"[label]: relative/{TOKEN}", f"[label]: relative/{TOKEN}"),
        (f"> [label]: /relative/{TOKEN}\n", f"> [label]: /relative/{TOKEN}\n"),
        (f"- [label]: /relative/{TOKEN}\n", f"- [label]: /relative/{TOKEN}\n"),
        (f"1. [label]: /relative/{TOKEN}\n", f"1. [label]: /relative/{TOKEN}\n"),
        (f"> {TOKEN}: /relative\n", f"> {TOKEN}: /relative\n"),
        (f"> [label]:\n> /relative/{TOKEN}\n", f"> [label]:\n> /relative/{TOKEN}\n"),
        (f"ordinary\r[label]: /relative/{TOKEN}\r", f"ordinary\r[label]: /relative/{TOKEN}\r"),
        (f"ordinary\r{TOKEN}: /relative\r", f"ordinary\r{TOKEN}: /relative\r"),
        (f"[label]:\r\n relative/{TOKEN}\r\n", f"[label]:\r\n relative/{TOKEN}\r\n"),
        (f"> [label]:\r\n> /relative/{TOKEN}\r\n", f"> [label]:\r\n> /relative/{TOKEN}\r\n"),
        (f"[label]:\n relative/{TOKEN}", f"[label]:\n relative/{TOKEN}"),
        (f"[foo\nbar]: /relative/{TOKEN}\n", f"[foo\nbar]: /relative/{TOKEN}\n"),
        (f"[foo\r\nbar]: /relative/{TOKEN}\r\n", f"[foo\r\nbar]: /relative/{TOKEN}\r\n"),
        (f"> [foo\n> bar]: /relative/{TOKEN}\n", f"> [foo\n> bar]: /relative/{TOKEN}\n"),
        (
            f'[label]: relative "first\n{TOKEN} second"\n',
            f'[label]: relative "first\n{TOKEN} second"\n',
        ),
        (
            f"[label]: relative (first\r\n{TOKEN} second)\r\n",
            f"[label]: relative (first\r\n{TOKEN} second)\r\n",
        ),
        (
            f'[label]: relative\n "first\nsecond {TOKEN}"\n',
            f'[label]: relative\n "first\nsecond {TOKEN}"\n',
        ),
        (
            f'> [label]: relative "first\n> {TOKEN} second"\n',
            f'> [label]: relative "first\n> {TOKEN} second"\n',
        ),
        (f'[label]: relative\n "title {TOKEN}"', f'[label]: relative\n "title {TOKEN}"'),
        (f"[label]: relative\n{TOKEN}", f"[label]: relative\n{ORIGINAL}"),
        (f"{TOKEN}: https://example.invalid/", f"{TOKEN}: https://example.invalid/"),
        (f"{TOKEN}  : relative", f"{TOKEN}  : relative"),
        (f"[outer {TOKEN}]: relative", f"[outer {TOKEN}]: relative"),
        (f"[unfinished {TOKEN}", f"[unfinished {TOKEN}"),
        (f'<a title=">" href="{TOKEN}">{TOKEN}</a>', f'<a title=">" href="{TOKEN}">{ORIGINAL}</a>'),
        (f'<a href="{TOKEN}', f'<a href="{TOKEN}'),
        (f"<!-- > {TOKEN} --> {TOKEN}", f"<!-- > {TOKEN} --> {ORIGINAL}"),
        (f"<![CDATA[ > {TOKEN} ]]> {TOKEN}", f"<![CDATA[ > {TOKEN} ]]> {ORIGINAL}"),
        (
            f"<script>const x='{TOKEN}';</script> {TOKEN}",
            f"<script>const x='{TOKEN}';</script> {ORIGINAL}",
        ),
        (f"<script>< /script>{TOKEN}", f"<script>< /script>{TOKEN}"),
        (f"<style></ style>{TOKEN}", f"<style></ style>{TOKEN}"),
        (
            f"<style>x{{content:'{TOKEN}'}}</style> {TOKEN}",
            f"<style>x{{content:'{TOKEN}'}}</style> {ORIGINAL}",
        ),
        (f"[x](nested(one/{TOKEN})", f"[x](nested(one/{TOKEN})"),
        (f'<a <b value="{TOKEN}"> {TOKEN}', f'<a <b value="{TOKEN}"> {TOKEN}'),
    ],
)
def test_stream_is_partition_independent_without_transient_disclosure(text, expected):
    for split in range(len(text) + 1):
        restorer = GuardedStreamRestorer({TOKEN: ORIGINAL})
        emitted = [restorer.feed(text[:split]), restorer.feed(text[split:]), restorer.flush()]
        assert "".join(emitted) == expected
        if ORIGINAL not in expected:
            assert all(ORIGINAL not in part for part in emitted)
    restorer = GuardedStreamRestorer({TOKEN: ORIGINAL})
    assert "".join(restorer.feed(char) for char in text) + restorer.flush() == expected


@pytest.mark.parametrize(
    "text",
    [
        f"https://example.invalid/a'{TOKEN}",
        f"> [label]: /relative/{TOKEN}\n",
        f"- [label]: /relative/{TOKEN}\n",
        f"1. [label]: /relative/{TOKEN}\n",
        f"> {TOKEN}: /relative\n",
        f"> [label]:\n> /relative/{TOKEN}\n",
        f"ordinary\r[label]: /relative/{TOKEN}\r",
        f"ordinary\r{TOKEN}: /relative\r",
        f"[label]:\r\n relative/{TOKEN}\r\n",
    ],
)
def test_bulk_protects_uri_delimiters_and_logical_definition_starts(text):
    start = text.index(TOKEN)
    assert any(
        left <= start and start + len(TOKEN) <= right for left, right in machine_context_spans(text)
    )


@pytest.mark.parametrize("pseudonym", ["0891234567", "089-123-4567"])
def test_numeric_surrogate_reference_continuation_is_protected(pseudonym):
    text = f"[label]:\n{pseudonym}\n"
    start = text.index(pseudonym)
    assert any(
        left <= start and start + len(pseudonym) <= right
        for left, right in machine_context_spans(text)
    )
    plain = f"[label]: /destination\n{pseudonym}\n"
    start = plain.index(pseudonym)
    assert not any(
        left < start + len(pseudonym) and start < right
        for left, right in machine_context_spans(plain)
    )


@pytest.mark.parametrize(
    "text",
    [
        f"[label]: <my 'url'>\n \"title {TOKEN}\"\n",
        f"[label]: <my \"url\">\n 'title {TOKEN}'\n",
    ],
)
def test_angle_destination_quotes_do_not_consume_the_real_reference_title(text):
    start = text.index(TOKEN)
    assert any(
        left <= start and start + len(TOKEN) <= right for left, right in machine_context_spans(text)
    )
    for split in range(len(text) + 1):
        restorer = GuardedStreamRestorer({TOKEN: ORIGINAL})
        emitted = [restorer.feed(text[:split]), restorer.feed(text[split:]), restorer.flush()]
        assert "".join(emitted) == text
        assert all(ORIGINAL not in part for part in emitted)


def test_stream_complete_line_start_token_waits_for_reference_suffix_and_discard():
    restorer = GuardedStreamRestorer({TOKEN: ORIGINAL})
    assert ORIGINAL not in restorer.feed(TOKEN)
    assert ORIGINAL not in restorer.feed(": relative")
    assert ORIGINAL not in restorer.flush()

    restorer = GuardedStreamRestorer({TOKEN: ORIGINAL})
    assert restorer.feed(TOKEN) == ""
    restorer.discard()
    assert restorer.flush() == ""
    assert restorer.feed(f"hello {TOKEN}") + restorer.flush() == f"hello {TOKEN}"


def test_stream_delivers_incrementally_and_keeps_bounded_ambiguous_state():
    restorer = GuardedStreamRestorer({TOKEN: ORIGINAL})
    assert restorer.feed("hello ") == "hello "
    text = "[" + "x" * 100_000 + TOKEN + ": relative"
    output = []
    for start in range(0, len(text), 127):
        output.append(restorer.feed(text[start : start + 127]))
        assert len(restorer._buffer) <= 512
    output.append(restorer.flush())
    assert "".join(output) == text
    assert ORIGINAL not in "".join(output)


def test_stream_token_matching_preserves_unknown_inner_and_max_length():
    restorer = GuardedStreamRestorer({TOKEN: ORIGINAL, "plain": "not-stream-matched"})
    text = "prefix [unknown [Sensitive_1]] plain [unknown]"
    assert (
        restorer.feed(text) + restorer.flush()
        == "prefix [unknown synthetic-original] plain [unknown]"
    )


def test_stream_does_not_commit_a_multiline_candidate_before_its_context_is_known():
    unusual = "[outer\n[Sensitive_1]"
    restorer = GuardedStreamRestorer({unusual: ORIGINAL})
    first = restorer.feed("prefix " + unusual)
    assert ORIGINAL not in first
    assert ORIGINAL not in restorer.feed(": relative")
    assert ORIGINAL not in restorer.flush()


@pytest.mark.parametrize("prefix", ["[label](" + "(" * 1024, "<a " + "<a " * 1024])
def test_stream_nesting_bound_never_restores_after_ambiguous_overflow(prefix):
    text = prefix + ")>" * 1025 + TOKEN
    restorer = GuardedStreamRestorer({TOKEN: ORIGINAL})
    assert restorer.feed(text) + restorer.flush() == text
    assert len(restorer._buffer) == 0


def test_stream_reference_whitespace_bound_keeps_token_opaque_until_newline():
    text = TOKEN + " " * 4096 + "ordinary\n" + TOKEN
    restorer = GuardedStreamRestorer({TOKEN: ORIGINAL})
    emitted = []
    for char in text:
        emitted.append(restorer.feed(char))
        assert len(restorer._buffer) <= 386
    emitted.append(restorer.flush())
    assert "".join(emitted) == TOKEN + " " * 4096 + "ordinary\n" + ORIGINAL


def test_context_spans_protect_url_prefix_and_quoted_tag_tail():
    text = 'synthetic://example.invalid/x <a title=">" value="x">visible'
    spans = machine_context_spans(text)
    assert any(start == 0 and end >= len("synthetic://example.invalid/x") for start, end in spans)
    inside = text.index('value="x"')
    assert any(start <= inside < end for start, end in spans)
    assert not any(start <= text.index("visible") < end for start, end in spans)


@pytest.mark.parametrize("mac", ["82:40:32:e4:61:23", "aa:bb:cc:dd:ee:ff", "82:40:32:44:61:23"])
@pytest.mark.parametrize("delimiter", [", ", "; ", ")", ". "])
def test_stream_known_mac_atom_keeps_bracket_only_matching_and_chunk_parity(mac, delimiter):
    text = f"MAC {mac}{delimiter}{TOKEN}"
    expected = f"MAC {mac}{delimiter}{ORIGINAL}"
    mapping = {mac: "02:00:00:00:00:01", TOKEN: ORIGINAL}
    for split in range(len(text) + 1):
        restorer = GuardedStreamRestorer(mapping)
        emitted = [restorer.feed(text[:split]), restorer.feed(text[split:]), restorer.flush()]
        assert "".join(emitted) == expected
        assert all("02:00:00:00:00:01" not in part for part in emitted)
    restorer = GuardedStreamRestorer(mapping)
    assert "".join(restorer.feed(char) for char in text) + restorer.flush() == expected


@pytest.mark.parametrize(
    "wrapper",
    [
        "https://example.invalid/{}?q=" + TOKEN,
        "custom:{}?q=" + TOKEN,
        '<a href="{}' + TOKEN + '">',
        "[label]({}/" + TOKEN + ")",
        "[label]:\n{}/" + TOKEN,
        "<script>'{}" + TOKEN + "';</script>",
        "{}/" + TOKEN,
        "{}?" + TOKEN,
        "{}#" + TOKEN,
    ],
)
def test_stream_mac_classification_never_clears_external_machine_context(wrapper):
    mac = "82:40:32:e4:61:23"
    text = wrapper.format(mac)
    mapping = {mac: "02:00:00:00:00:01", TOKEN: ORIGINAL}
    for split in range(len(text) + 1):
        restorer = GuardedStreamRestorer(mapping)
        emitted = [restorer.feed(text[:split]), restorer.feed(text[split:]), restorer.flush()]
        assert "".join(emitted) == text
        assert all(ORIGINAL not in part and "02:00:00:00:00:01" not in part for part in emitted)
    restorer = GuardedStreamRestorer(mapping)
    emitted = []
    for char in text:
        emitted.append(restorer.feed(char))
        assert len(restorer._buffer) <= 386
    emitted.append(restorer.flush())
    assert "".join(emitted) == text
    assert all(ORIGINAL not in part and "02:00:00:00:00:01" not in part for part in emitted)


def test_stream_mac_context_cancellation_discards_pending_bracket_and_mapping():
    mac = "82:40:32:e4:61:23"
    restorer = GuardedStreamRestorer({mac: "02:00:00:00:00:01", TOKEN: ORIGINAL})
    emitted = restorer.feed(f'custom:{mac}/"<a href="[Sensitive_1')
    assert ORIGINAL not in emitted
    restorer.discard()
    assert restorer.flush() == ""
    assert restorer._mapping == {}


def test_stream_unknown_mac_and_unknown_uri_scheme_keep_the_strict_default():
    for text in [f"aa:bb:cc:dd:ee:ff){TOKEN}", f"bespoke+v1:{TOKEN}"]:
        for split in range(len(text) + 1):
            restorer = GuardedStreamRestorer({TOKEN: ORIGINAL})
            emitted = [restorer.feed(text[:split]), restorer.feed(text[split:]), restorer.flush()]
            assert "".join(emitted) == text
            assert all(ORIGINAL not in part for part in emitted)


@pytest.mark.parametrize("mac", ["82:40:32:e4:61:23", "aa:bb:cc:dd:ee:ff", "82:40:32:44:61:23"])
@pytest.mark.parametrize("prefix", ["opaque.", "opaque+", "opaque-", "opaque.+"])
@pytest.mark.parametrize(
    "wrapper",
    [
        "{}",
        "[ref]: /destination\n{}",
        "[ref]:\n{}",
        '[ref]: /destination\n "{}"',
        "> [ref]: /destination\n> {}",
    ],
)
def test_stream_mac_atom_never_erases_a_pending_uri_scheme(mac, prefix, wrapper):
    text = wrapper.format(prefix + mac + TOKEN)
    mapping = {mac: "02:00:00:00:00:01", TOKEN: ORIGINAL}
    for split in range(len(text) + 1):
        restorer = GuardedStreamRestorer(mapping)
        emitted = [restorer.feed(text[:split]), restorer.feed(text[split:]), restorer.flush()]
        assert "".join(emitted) == text
        assert all(ORIGINAL not in part and "02:00:00:00:00:01" not in part for part in emitted)
    restorer = GuardedStreamRestorer(mapping)
    emitted = [restorer.feed(char) for char in text]
    emitted.append(restorer.flush())
    assert "".join(emitted) == text
    assert all(ORIGINAL not in part and "02:00:00:00:00:01" not in part for part in emitted)
