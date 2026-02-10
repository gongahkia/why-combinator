"""Tests for extract_json: raw JSON, code-fenced, embedded, invalid."""
from why_combinator.utils.parsing import extract_json


def test_raw_json():
    result = extract_json('{"action": "buy", "amount": 100}')
    assert result is not None
    assert result["action"] == "buy"


def test_code_fenced_json():
    text = 'Here is my response:\n```json\n{"action": "invest", "target": "startup"}\n```\nDone.'
    result = extract_json(text)
    assert result is not None
    assert result["action"] == "invest"


def test_embedded_json_in_text():
    text = 'I think we should do this: {"thought_process": "analyzing", "action_type": "buy"} and that is my answer.'
    result = extract_json(text)
    assert result is not None
    assert result["action_type"] == "buy"


def test_invalid_input():
    result = extract_json("This is not JSON at all, just plain text.")
    assert result is None


def test_empty_string():
    result = extract_json("")
    assert result is None


def test_nested_json():
    text = '{"outer": {"inner": "value"}, "list": [1, 2, 3]}'
    result = extract_json(text)
    assert result is not None
    assert result["outer"]["inner"] == "value"
