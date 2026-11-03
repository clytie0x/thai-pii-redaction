"""Shared bounded policy for machine-context restoration.

This is a conservative context guard, not a renderer or HTML sanitizer. Unknown
or overlong syntax keeps tokens opaque. Streaming buffers one bracket token or
a fixed reference-label lookahead; context state never retains response text.
"""

from __future__ import annotations

from collections.abc import Iterable
from copy import copy

from pii_redactor.anonymizer.token_generator import _TOKEN_MAX_LENGTH
from pii_redactor.detectors.fp_detector import _RE_MAC

_LOOKAHEAD = 256
_NEST_LIMIT = 1024
_URL_END = frozenset('<>"`')
_CONTAINER_PREFIX = frozenset(">-+*0123456789.)")
_URI_ATTACHMENT = frozenset(":/?#@\\")


def _scheme_char(char: str) -> bool:
    return char.isascii() and (char.isalnum() or char in "+.-")


class _ContextPolicy:
    """Consume untouched source characters; defer only uncertain line labels."""

    def __init__(self, known_pseudonyms: Iterable[str] = ()) -> None:
        self._known_macs = frozenset(
            value for value in known_pseudonyms if _RE_MAC.fullmatch(value)
        )
        self._mac_starts = frozenset(value[0] for value in self._known_macs)
        self._scalar_left = 0
        self._last_char = ""
        self._line_start = True
        self._after_cr = False
        self._ref_line = False
        self._ref_left = 0
        self._ref_destination = False
        self._ref_followup = ""
        self._ref_next = ""
        self._ref_space = False
        self._ref_angle = False
        self._ref_title = ""
        self._ref_escape = False
        self._ref_title_done = False
        self._url = False
        self._scheme_length = 0
        self._scheme_prefix = ""
        self._previous_slash = False
        self._after_label = False
        self._md_depth = 0
        self._md_angle = False
        self._md_quote = ""
        self._md_escape = False
        self._tag_depth = 0
        self._tag_prefix = ""
        self._tag_tail = ""
        self._tag_quote = ""
        self._tag_kind = ""
        self._tag_name = ""
        self._tag_name_done = False
        self._tag_closing = False
        self._raw = ""
        self._stuck = False
        self.retroactive = 0

    @staticmethod
    def _reference(text: str, start: int, *, final: bool) -> tuple[bool | None, int]:
        depth = 0
        escaped = False
        limit = min(len(text), start + _LOOKAHEAD)
        for index in range(start, limit):
            char = text[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    index += 1
                    while index < limit and text[index] in " \t":
                        index += 1
                    if index < limit:
                        return text[index] == ":", index - start
                    if limit == start + _LOOKAHEAD:
                        return True, -1
                    return (False if final else None), -1
        if limit == start + _LOOKAHEAD or final:
            return True, -2  # An unclosed label may continue after a newline.
        return None, -1

    def _finish(self, char: str, guarded: bool) -> bool:
        self._last_char = char
        if self._ref_line:
            if self._ref_left > 0:
                self._ref_left -= 1
            elif self._ref_title:
                if self._ref_escape:
                    self._ref_escape = False
                elif char == "\\":
                    self._ref_escape = True
                elif char == self._ref_title:
                    self._ref_title = ""
                    self._ref_title_done = True
            elif self._ref_angle:
                if self._ref_escape:
                    self._ref_escape = False
                elif char == "\\":
                    self._ref_escape = True
                elif char == ">":
                    self._ref_angle = False
            elif not self._ref_destination:
                if char != ":" and not char.isspace():
                    self._ref_destination = True
                    self._ref_angle = char == "<"
            elif char.isspace():
                self._ref_space = True
            elif self._ref_space and char in "\"'(":
                self._ref_title = ")" if char == "(" else char
                self._ref_space = False
            else:
                self._ref_space = False
        if char in "\r\n":
            self._line_start = True
            if not (self._ref_left > 0 or self._ref_title or self._ref_angle):
                if (
                    self._ref_line
                    and not self._ref_title_done
                    and self._ref_followup in {"definition", "destination"}
                ):
                    self._ref_next = "title" if self._ref_destination else "destination"
                self._ref_line = False
        elif char not in " \t" and not (
            self._line_start and not guarded and char in _CONTAINER_PREFIX
        ):
            self._line_start = False
        return guarded

    def _mac_atom(self, text: str, index: int, *, final: bool) -> bool | None:
        """Suppress only a known scalar's internal colons, never its context."""
        if self._scheme_length:
            # A scalar cannot erase a valid scheme prefix before its colon.
            return False
        if text[index] not in self._mac_starts:
            return False
        tail = text[index : index + 18]
        if len(tail) < 17:
            if not final and any(value.startswith(tail) for value in self._known_macs):
                return None
            return False
        value = tail[:17]
        if value not in self._known_macs:
            return False
        if len(tail) == 17 and not final:
            return None
        surrounding = self._last_char + tail
        match = _RE_MAC.match(surrounding, len(self._last_char))
        attached = (
            self._last_char in _URI_ATTACHMENT or tail[17:18] in _URI_ATTACHMENT or match is None
        )
        self._scheme_length = 0
        self._scheme_prefix = ""
        self._previous_slash = False
        self._after_label = False
        if attached:
            self._url = True
        else:
            self._scalar_left = 16
        return True

    def _start_tag(self) -> None:
        self._tag_depth = 1
        self._tag_prefix = "<"
        self._tag_tail = "<"
        self._tag_quote = ""
        self._tag_kind = ""
        self._tag_name = ""
        self._tag_name_done = False
        self._tag_closing = False

    def _tag(self, char: str) -> None:
        self._tag_prefix = (self._tag_prefix + char)[:9]
        self._tag_tail = (self._tag_tail + char)[-3:]
        if self._tag_prefix == "<!--":
            self._tag_kind = "comment"
        elif self._tag_prefix == "<![CDATA[":
            self._tag_kind = "cdata"
        if self._tag_kind:
            end = "-->" if self._tag_kind == "comment" else "]]>"
            if self._tag_tail == end:
                self._tag_depth = 0
            return
        if self._tag_quote:
            if char == self._tag_quote:
                self._tag_quote = ""
            return
        if not self._tag_name_done:
            if char == "/" and not self._tag_name:
                self._tag_closing = True
            elif char.isspace() and not self._tag_name:
                pass
            elif char.isascii() and (char.isalnum() or char in ":_-"):
                self._tag_name = (self._tag_name + char.lower())[:8]
            else:
                self._tag_name_done = True
        if char in "\"'":
            self._tag_quote = char
        elif char == "<":
            self._tag_depth += 1
            if self._tag_depth >= _NEST_LIMIT:
                self._stuck = True
        elif char == ">":
            self._tag_depth -= 1
            if not self._tag_depth:
                raw_close = f"</{self._raw}"
                if (
                    self._tag_closing
                    and self._tag_name == self._raw
                    and self._tag_prefix.lower().startswith(raw_close)
                    and self._tag_prefix[len(raw_close) : len(raw_close) + 1] in " \t\r\n/>"
                ):
                    self._raw = ""
                elif not self._tag_closing and self._tag_name in {"script", "style"}:
                    self._raw = self._tag_name

    def step(self, text: str, index: int, *, final: bool) -> bool | None:
        """Return protection for one char, or await bounded reference lookahead.

        A URL scheme contains no bracket tokens. Its prefix can therefore be
        marked retroactively in bulk without exposing a streaming original.
        """
        self.retroactive = 0
        char = text[index]
        after_cr = self._after_cr
        self._after_cr = char == "\r"
        if char == "\n" and after_cr:
            # CRLF is one logical newline, including reference continuations.
            if self._ref_line and self._ref_left > 0:
                self._ref_left -= 1
            return bool(
                self._stuck or self._tag_depth or self._raw or self._md_depth or self._ref_line
            )
        if self._stuck:
            return self._finish(char, True)
        if self._scalar_left:
            self._scalar_left -= 1
            return self._finish(char, False)
        if self._tag_depth:
            self._tag(char)
            return self._finish(char, True)
        if self._raw:
            if char == "<":
                self._start_tag()
            return self._finish(char, True)
        if self._md_depth:
            if self._md_escape:
                self._md_escape = False
            elif char == "\\":
                self._md_escape = True
            elif self._md_angle:
                if char == ">":
                    self._md_angle = False
            elif self._md_quote:
                if char == self._md_quote:
                    self._md_quote = ""
            elif char in "\"'":
                self._md_quote = char
            elif char == "<":
                self._md_angle = True
            elif char == ")":
                self._md_depth -= 1
            elif char == "(":
                self._md_depth += 1
                if self._md_depth >= _NEST_LIMIT:
                    self._stuck = True
            return self._finish(char, True)
        if self._ref_line:
            return self._finish(char, True)
        if self._ref_next:
            if self._ref_next == "title":
                scalar = self._mac_atom(text, index, final=final)
                if scalar is None:
                    return None
                if scalar:
                    self._ref_next = ""
                    return self._finish(char, self._url)
            if char in " \t" or (self._line_start and char in _CONTAINER_PREFIX):
                guarded = self._ref_next == "destination"
                if guarded and not char.isspace():
                    self._ref_destination = True
                self._finish(char, False)
                return guarded
            if char in "\r\n":
                self._ref_next = (
                    "title" if self._ref_next == "destination" and self._ref_destination else ""
                )
                return self._finish(char, False)
            followup = self._ref_next
            self._ref_next = ""
            if char != "\n" and (followup == "destination" or char in "\"'("):
                self._ref_line = True
                self._ref_followup = followup
                self._ref_left = 0
                self._ref_destination = followup == "title"
                self._ref_space = followup == "title"
                self._ref_title_done = False
                return self._finish(char, True)
        if self._url:
            if not char.isspace() and char not in _URL_END:
                return self._finish(char, True)
            self._url = False
            self._scheme_length = 0
            self._scheme_prefix = ""
        if char == "<":
            self._start_tag()
            self._after_label = False
            self._scheme_length = 0
            return self._finish(char, True)
        if self._after_label and char == "(":
            self._md_depth = 1
            self._after_label = False
            self._scheme_length = 0
            return self._finish(char, True)
        if self._line_start and char == "[":
            reference, colon = self._reference(text, index, final=final)
            if reference is None:
                return None
            if reference:
                if colon == -2:
                    self._stuck = True
                self._ref_line = True
                self._ref_left = colon
                self._ref_destination = False
                self._ref_followup = "definition" if colon >= 0 else ""
                self._ref_space = False
                self._ref_title_done = False
                return self._finish(char, True)
        scalar = self._mac_atom(text, index, final=final)
        if scalar is None:
            return None
        if scalar:
            return self._finish(char, self._url)
        self._after_label = char == "]" or (self._after_label and char in " \t")
        guarded = False
        if char == ":" and self._scheme_length:
            self._url = guarded = True
            self.retroactive = self._scheme_length
        elif char == "/" and self._previous_slash:
            self._url = guarded = True
            self.retroactive = 1
        elif _scheme_char(char):
            if self._scheme_length or (char.isascii() and char.isalpha()):
                self._scheme_length += 1
                self._scheme_prefix = (self._scheme_prefix + char.lower())[:4]
                if self._scheme_prefix == "www." or self._scheme_length >= _LOOKAHEAD:
                    self._url = guarded = True
                    self.retroactive = self._scheme_length - 1
        else:
            self._scheme_length = 0
            self._scheme_prefix = ""
        self._previous_slash = char == "/"
        return self._finish(char, guarded)


def machine_context_spans(
    text: str, *, _known_pseudonyms: Iterable[str] = ()
) -> list[tuple[int, int]]:
    """Return merged half-open protected spans on untouched Unicode text."""
    policy = _ContextPolicy(_known_pseudonyms)
    spans: list[tuple[int, int]] = []
    for index in range(len(text)):
        if policy.step(text, index, final=True):
            start = max(0, index - policy.retroactive)
            if spans and start <= spans[-1][1]:
                spans[-1] = (min(start, spans[-1][0]), index + 1)
            else:
                spans.append((start, index + 1))
    return spans


class GuardedStreamRestorer:
    """Restore known bracket tokens incrementally under the canonical policy.

    ``flush`` is successful EOF, including a final standalone line-start token.
    Failed/cancelled transports must call ``discard`` instead. Unknown brackets
    release only their opening bracket so an inner known token still matches.
    """

    def __init__(self, mapping: dict[str, str]):
        self._mapping = dict(mapping)
        self._buffer = ""
        self._policy = _ContextPolicy(self._mapping)

    def feed(self, chunk: str) -> str:
        self._buffer += chunk
        return self._drain(final=False)

    def flush(self) -> str:
        return self._drain(final=True)

    def discard(self) -> None:
        self._buffer = ""
        self._mapping.clear()
        self._policy = _ContextPolicy()

    def _drain(self, *, final: bool) -> str:
        text = self._buffer
        out: list[str] = []
        index = 0
        while index < len(text):
            end = index + 1
            candidate = ""
            if text[index] == "[":
                close = text.find("]", index + 1, index + _TOKEN_MAX_LENGTH)
                if close < 0 and len(text) - index <= _TOKEN_MAX_LENGTH and not final:
                    break
                if close >= 0:
                    value = text[index : close + 1]
                    if value in self._mapping:
                        candidate = value
                        end = close + 1
            policy = copy(self._policy) if candidate else self._policy
            guarded = policy.step(text, index, final=final)
            if guarded is None:
                break
            if candidate:
                for position in range(index + 1, end):
                    decision = policy.step(text, position, final=final)
                    if decision is None:
                        break
                    guarded = decision or guarded
                else:
                    self._policy = policy
                    out.append(candidate if guarded else self._mapping[candidate])
                    index = end
                    continue
                break
            else:
                out.append(text[index])
            index = end
        self._buffer = text[index:]
        return "".join(out)
