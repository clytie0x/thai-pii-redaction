"""Map obscured digits back to the characters the detectors already know.

Zero-width characters are dropped. Thai and Arabic-Indic digits become ASCII.
A space that sits between two digits is dropped, so a number written one
character at a time is visible again. Spans are mapped back onto the original
text, including the characters that were skipped.
"""

from __future__ import annotations

_ZERO_WIDTH = frozenset("\u200b\u200c\ufeff\u2060")
_DIGIT_FOLD = {ord("๐") + offset: ord("0") + offset for offset in range(10)}
_DIGIT_FOLD.update({0x0660 + offset: ord("0") + offset for offset in range(10)})


def _fold(char: str) -> str:
    folded = _DIGIT_FOLD.get(ord(char))
    if folded is None:
        return char
    return chr(folded)


def normalize_surface(text: str) -> tuple[str, list[int]]:
    """Return folded text and the original index of each folded character."""
    kept: list[tuple[str, int]] = []
    for index, char in enumerate(text):
        if char in _ZERO_WIDTH:
            continue
        folded = _fold(char)
        if folded == " " and _space_is_digit_padding(kept, text, index):
            continue
        kept.append((folded, index))
    if not kept:
        return "", []
    return "".join(char for char, _index in kept), [index for _char, index in kept]


def map_span(origins: list[int], start: int, end: int) -> tuple[int, int]:
    return origins[start], origins[end - 1] + 1


def _next_kept_char(text: str, start: int) -> str:
    for index in range(start, len(text)):
        char = text[index]
        if char in _ZERO_WIDTH or char == " ":
            continue
        return _fold(char)
    return ""


def _space_is_digit_padding(kept: list[tuple[str, int]], text: str, index: int) -> bool:
    """Drop a space that only separates digits, including spaces around a hyphen."""
    if not kept:
        return False
    previous = kept[-1][0]
    nxt = _next_kept_char(text, index + 1)
    if previous.isdigit() and (nxt.isdigit() or nxt == "-"):
        return True
    return previous == "-" and nxt.isdigit()


def _is_thai_letter(char: str) -> bool:
    return bool(char) and "\u0e00" <= char <= "\u0e7f"


def _is_isolated_thai(text: str, index: int) -> bool:
    """A Thai letter with no Thai letter on either side, ignoring zero-width marks."""
    if index < 0 or index >= len(text) or not _is_thai_letter(text[index]):
        return False
    prev = index - 1
    while prev >= 0 and text[prev] in _ZERO_WIDTH:
        prev -= 1
    nxt = index + 1
    while nxt < len(text) and text[nxt] in _ZERO_WIDTH:
        nxt += 1
    prev_thai = prev >= 0 and _is_thai_letter(text[prev])
    next_thai = nxt < len(text) and _is_thai_letter(text[nxt])
    return not prev_thai and not next_thai


def _visible_index(text: str, start: int, step: int) -> int | None:
    index = start
    while 0 <= index < len(text):
        if text[index] not in _ZERO_WIDTH and text[index] != " ":
            return index
        index += step
    return None


def _space_is_isolated_thai_padding(text: str, index: int) -> bool:
    """Drop a space that sits between two single Thai letters, not between words."""
    prev = _visible_index(text, index - 1, -1)
    nxt = _visible_index(text, index + 1, 1)
    if prev is None or nxt is None:
        return False
    return _is_isolated_thai(text, prev) and _is_isolated_thai(text, nxt)


def normalize_prose(text: str) -> tuple[str, list[int] | None]:
    """Fold zero-width marks and per-character Thai spacing for the NER pass.

    Returns the original text and ``None`` when nothing was removed, so the
    common path does not remap spans. Origins, when present, point at the
    source index of each kept character.
    """
    if not text:
        return text, None
    kept: list[tuple[str, int]] = []
    changed = False
    for index, char in enumerate(text):
        if char in _ZERO_WIDTH:
            changed = True
            continue
        if char == " " and _space_is_isolated_thai_padding(text, index):
            changed = True
            continue
        kept.append((char, index))
    if not changed:
        return text, None
    if not kept:
        return "", []
    return "".join(char for char, _index in kept), [index for _char, index in kept]
