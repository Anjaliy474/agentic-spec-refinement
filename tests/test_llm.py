import pytest

from reqhq.llm import FakeLLM, make_llm, parse_json


def test_parse_json_plain_and_fenced():
    assert parse_json('{"a": 1}') == {"a": 1}
    assert parse_json('Here you go:\n```json\n{"a": [1, 2]}\n```') == {"a": [1, 2]}
    assert parse_json('Sure! {"a": 2} hope that helps') == {"a": 2}


def test_parse_json_rejects_prose():
    with pytest.raises(ValueError):
        parse_json("no json here")


def test_complete_json_retries_once_then_succeeds():
    replies = iter(["not json", '{"ok": true}'])
    llm = FakeLLM(lambda s, p: next(replies))
    assert llm.complete_json("q", tag="t") == {"ok": True}
    assert [c.tag for c in llm.usage.calls] == ["t", "t:retry"]


def test_usage_is_recorded():
    llm = FakeLLM(lambda s, p: "one two three")
    llm.complete("a b", system="c")
    assert llm.usage.summary()["completion_tokens"] == 3
    assert llm.usage.prompt_tokens == 3


def test_make_llm_rejects_unknown_backend():
    with pytest.raises(ValueError):
        make_llm({"backend": "nope", "model": "x"})
