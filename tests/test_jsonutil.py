import pytest

from incident_agent.jsonutil import extract_json


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1}',
        '<think>let me think {"no": "this"}</think>\n{"a": 1}',
        'Here you go:\n```json\n{"a": 1}\n```\nHope that helps',
        'Sure! {"a": 1} is the answer.',
        '```\n{"a": 1}\n```',
    ],
)
def test_extracts_object(text):
    assert extract_json(text) == {"a": 1}


def test_nested_and_braces_in_strings():
    text = 'result: {"x": {"y": "has } brace"}, "z": [1, {"k": "{"}]} trailing'
    assert extract_json(text) == {"x": {"y": "has } brace"}, "z": [1, {"k": "{"}]}


def test_skips_invalid_candidate_and_finds_later_object():
    assert extract_json('{not json} then {"ok": true}') == {"ok": True}


@pytest.mark.parametrize("text", ["", "no json here", '{"unterminated": ', "[1, 2]"])
def test_raises_when_no_object(text):
    with pytest.raises(ValueError):
        extract_json(text)
