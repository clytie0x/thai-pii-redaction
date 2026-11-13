"""LLM baseline for the YRSS evaluation v2. No network: every call is mocked."""

from __future__ import annotations

import json

import httpx
import pytest

from benchmark.yrss_v2 import llm_openai
from benchmark.yrss_v2.types import SCHEME_TYPES

FAKE_KEY = "sk-test-not-a-real-key"
KEY_ENV = "YRSS_TEST_LLM_KEY"
STAT_KEYS = {
    "requests",
    "http_errors",
    "parse_failures",
    "items_returned",
    "items_not_found",
    "items_unknown_type",
}


def _reply(content: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})


def _items(*pairs: tuple[str, str]) -> str:
    rows = [{"type": entity_type, "text": text} for entity_type, text in pairs]
    return json.dumps({"items": rows}, ensure_ascii=False)


class _Server:
    """Scripted endpoint. Each call takes the next reply; the last one repeats."""

    def __init__(self, *replies) -> None:
        self.replies = list(replies)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        index = min(len(self.requests), len(self.replies)) - 1
        reply = self.replies[index]
        if isinstance(reply, Exception):
            raise reply
        return reply

    def body(self, index: int = 0) -> dict:
        return json.loads(self.requests[index].content)


def _predictor(server: _Server, *, api_key_env: str | None = None, seed: int = 7):
    sleeps: list[float] = []
    predictor = llm_openai.make_predictor(
        base_url="https://llm.example/v1/",
        model="test-model",
        api_key_env=api_key_env,
        seed=seed,
        _transport=httpx.MockTransport(server),
        _sleep=sleeps.append,
    )
    return predictor, sleeps


def test_request_body_and_bearer_header(monkeypatch):
    monkeypatch.setenv(KEY_ENV, FAKE_KEY)
    server = _Server(_reply(_items()))
    predictor, _ = _predictor(server, api_key_env=KEY_ENV, seed=20261113)

    assert predictor("เอกสารทดสอบ") == []

    request = server.requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://llm.example/v1/chat/completions"
    assert request.headers["Authorization"] == f"Bearer {FAKE_KEY}"
    body = server.body()
    assert body["model"] == "test-model"
    assert body["seed"] == 20261113
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    assert [message["role"] for message in body["messages"]] == ["system", "user"]
    assert body["messages"][0]["content"] == llm_openai.SYSTEM_PROMPT
    assert body["messages"][1]["content"] == "เอกสารทดสอบ"
    assert FAKE_KEY not in request.content.decode("utf-8")
    assert FAKE_KEY not in repr(predictor)


def test_no_authorization_header_without_key_env():
    server = _Server(_reply(_items()))
    predictor, _ = _predictor(server, api_key_env=None)

    predictor("hello")

    assert "authorization" not in server.requests[0].headers


@pytest.mark.parametrize("value", [None, ""])
def test_missing_key_env_raises_at_construction(monkeypatch, value):
    if value is None:
        monkeypatch.delenv(KEY_ENV, raising=False)
    else:
        monkeypatch.setenv(KEY_ENV, value)

    with pytest.raises(llm_openai.LLMConfigError) as caught:
        llm_openai.make_predictor(
            base_url="https://llm.example/v1", model="m", api_key_env=KEY_ENV, seed=1
        )

    assert KEY_ENV in str(caught.value)


def test_stats_start_at_zero_with_the_agreed_keys():
    predictor, _ = _predictor(_Server(_reply(_items())))

    assert STAT_KEYS <= set(predictor.stats)
    assert all(value == 0 for value in predictor.stats.values())


def test_plain_json_reply_maps_to_offsets():
    document = "ติดต่อ คุณสมมติ ตัวอย่าง โทร 080-000-0000"
    server = _Server(_reply(_items(("PHONE", "080-000-0000"), ("NAME", "สมมติ ตัวอย่าง"))))
    predictor, _ = _predictor(server)

    spans = predictor(document)

    assert [(document[start:end], label) for start, end, label in spans] == [
        ("สมมติ ตัวอย่าง", "NAME"),
        ("080-000-0000", "PHONE"),
    ]
    assert predictor.stats["requests"] == 1
    assert predictor.stats["items_returned"] == 2
    assert predictor.stats["items_not_found"] == 0


@pytest.mark.parametrize(
    "content",
    [
        '```json\n{"items": [{"type": "EMAIL", "text": "a@example.invalid"}]}\n```',
        '```\n[{"type": "EMAIL", "text": "a@example.invalid"}]\n```',
        'Here is what I found:\n{"items": [{"type": "EMAIL", "text": "a@example.invalid"}]}\nDone.',
        'I found one item [see below].\n[{"type": "EMAIL", "text": "a@example.invalid"}] Thanks!',
        '<think>maybe {"x": 1} or [1]</think>{"items":[{"type":"EMAIL","text":"a@example.invalid"}]}',
        '[{"type": "EMAIL", "text": "a@example.invalid"}]',
        '{"type": "EMAIL", "text": "a@example.invalid"}',
    ],
)
def test_fenced_and_prose_wrapped_replies(content):
    document = "mail a@example.invalid now"
    predictor, _ = _predictor(_Server(_reply(content)))

    assert predictor(document) == [(5, 22, "EMAIL")]
    assert predictor.stats["parse_failures"] == 0


def test_empty_list_is_a_valid_answer():
    predictor, _ = _predictor(_Server(_reply('{"items": []}')))

    assert predictor("nothing here") == []
    assert predictor.stats["parse_failures"] == 0
    assert predictor.stats["items_returned"] == 0


@pytest.mark.parametrize(
    "response",
    [
        _reply("I could not find anything."),
        _reply('{"items": [{"type": "NAME", "text": '),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"content": None}}]}),
        httpx.Response(200, text="<html>gateway page</html>"),
    ],
)
def test_unreadable_reply_counts_a_parse_failure(response):
    predictor, _ = _predictor(_Server(response))

    assert predictor("some text") == []
    assert predictor.stats["parse_failures"] == 1
    assert predictor.stats["http_errors"] == 0
    assert predictor.stats["requests"] == 1


def test_repeated_text_takes_occurrences_left_to_right():
    document = "AB12 then AB12 and AB12"
    server = _Server(_reply(_items(("PASSPORT", "AB12"), ("PASSPORT", "AB12"))))
    predictor, _ = _predictor(server)

    assert predictor(document) == [(0, 4, "PASSPORT"), (10, 14, "PASSPORT")]


def test_more_items_than_occurrences_drops_the_extra():
    document = "AB12 then AB12"
    reply = _items(("PASSPORT", "AB12"), ("PASSPORT", "AB12"), ("PASSPORT", "AB12"))
    predictor, _ = _predictor(_Server(_reply(reply)))

    assert predictor(document) == [(0, 4, "PASSPORT"), (10, 14, "PASSPORT")]
    assert predictor.stats["items_returned"] == 3
    assert predictor.stats["items_not_found"] == 1


def test_assigned_spans_never_overlap():
    document = "Ann Lee met Ann"
    # "Ann" would match at 0, but that place is taken by "Ann Lee".
    predictor, _ = _predictor(_Server(_reply(_items(("NAME", "Ann Lee"), ("NAME", "Ann")))))

    assert predictor(document) == [(0, 7, "NAME"), (12, 15, "NAME")]

    predictor, _ = _predictor(_Server(_reply(_items(("NAME", "aa"), ("NAME", "aa")))))
    assert predictor("aaa") == [(0, 2, "NAME")]
    assert predictor.stats["items_not_found"] == 1


def test_not_found_and_unknown_type_handling():
    document = "Ann Lee, staff code Z9"
    reply = _items(
        ("NAME", "Ann Lee"),
        ("NAME", "Anne Lee"),  # not in the document
        ("STAFF_CODE", "Z9"),  # unknown type, text found: kept
        ("NICKNAME", "Annie"),  # unknown type, text missing: dropped
    )
    predictor, _ = _predictor(_Server(_reply(reply)))

    assert predictor(document) == [(0, 7, "NAME"), (20, 22, "STAFF_CODE")]
    assert predictor.stats["items_returned"] == 4
    assert predictor.stats["items_not_found"] == 2
    assert predictor.stats["items_unknown_type"] == 1


def test_type_case_is_normalised_to_the_scheme():
    predictor, _ = _predictor(_Server(_reply(_items((" email ", "a@example.invalid")))))

    assert predictor("a@example.invalid") == [(0, 17, "EMAIL")]
    assert predictor.stats["items_unknown_type"] == 0


def test_malformed_items_are_dropped_and_counted():
    content = json.dumps(
        {"items": ["x", {"type": "NAME"}, {"type": 3, "text": "Ann"}, {"text": ""}]}
    )
    predictor, _ = _predictor(_Server(_reply(content)))

    assert predictor("Ann") == []
    assert predictor.stats["items_returned"] == 4
    assert predictor.stats["items_malformed"] == 4
    assert predictor.stats["items_not_found"] == 0


def test_retry_without_response_format_on_400():
    document = "mail a@example.invalid"
    server = _Server(
        httpx.Response(400, json={"error": {"message": "response_format is not supported"}}),
        _reply(_items(("EMAIL", "a@example.invalid"))),
    )
    predictor, sleeps = _predictor(server)

    assert predictor(document) == [(5, 22, "EMAIL")]
    assert "response_format" in server.body(0)
    assert "response_format" not in server.body(1)
    assert sleeps == []
    assert predictor.stats["requests"] == 2
    assert predictor.stats["http_errors"] == 0

    # The server said no once; later documents do not ask again.
    predictor(document)
    assert len(server.requests) == 3
    assert "response_format" not in server.body(2)


def test_400_for_another_reason_fails_the_document_only():
    server = _Server(httpx.Response(400, json={"error": {"message": "context too long"}}))
    predictor, sleeps = _predictor(server)

    assert predictor("a long document") == []
    assert predictor.stats["requests"] == 2
    assert predictor.stats["http_errors"] == 1
    assert sleeps == []

    # Nothing was learned about response_format, so the next document asks again.
    predictor("another document")
    assert "response_format" in server.body(2)


@pytest.mark.parametrize(
    "failure",
    [
        httpx.Response(503, text="busy"),
        httpx.Response(429, text="slow down"),
        httpx.ConnectError("refused"),
        httpx.ReadTimeout("too slow"),
    ],
)
def test_failure_after_retries_returns_empty_and_counts(failure):
    server = _Server(failure)
    predictor, sleeps = _predictor(server)

    assert predictor("some text") == []
    assert len(server.requests) == 3
    assert len(sleeps) == 2
    assert sleeps[1] > sleeps[0] > 0
    assert predictor.stats["requests"] == 3
    assert predictor.stats["http_errors"] == 1
    assert predictor.stats["parse_failures"] == 0


def test_transient_failure_then_success():
    server = _Server(httpx.Response(502, text="bad gateway"), _reply(_items(("NAME", "Ann Lee"))))
    predictor, sleeps = _predictor(server)

    assert predictor("Ann Lee") == [(0, 7, "NAME")]
    assert len(sleeps) == 1
    assert predictor.stats["http_errors"] == 0


def test_auth_failure_is_not_retried():
    server = _Server(httpx.Response(401, json={"error": "bad key"}))
    predictor, sleeps = _predictor(server)

    assert predictor("some text") == []
    assert len(server.requests) == 1
    assert sleeps == []
    assert predictor.stats["http_errors"] == 1


def test_counters_add_up_over_documents_and_hold_no_text():
    document = "Ann Lee 080-000-0000"
    server = _Server(_reply(_items(("NAME", "Ann Lee"), ("PHONE", "080-000-0000"))))
    predictor, _ = _predictor(server)

    predictor(document)
    predictor(document)

    assert predictor.stats["requests"] == 2
    assert predictor.stats["items_returned"] == 4
    assert all(isinstance(value, int) for value in predictor.stats.values())
    assert "Ann Lee" not in repr(vars(predictor))


def test_prompt_names_every_scheme_type_and_is_versioned():
    for entity_type in SCHEME_TYPES:
        assert entity_type in llm_openai.SYSTEM_PROMPT
    assert "JSON" in llm_openai.SYSTEM_PROMPT
    assert isinstance(llm_openai.PROMPT_VERSION, str) and llm_openai.PROMPT_VERSION

    digest = llm_openai.prompt_sha256()
    assert len(digest) == 64
    assert digest == llm_openai.prompt_sha256()
    assert int(digest, 16) >= 0
