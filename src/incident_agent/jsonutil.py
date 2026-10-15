"""Recover a JSON object from LLM output.

Small models wrap JSON in prose, markdown fences or <think> blocks. We strip those and scan for the
first balanced, parseable top-level object instead of trusting the raw string.
"""

import json
import re

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def _balanced_objects(text: str):
    """Yield every substring that starts at a '{' and ends at its matching '}' (string-aware)."""
    for start in (i for i, ch in enumerate(text) if ch == "{"):
        depth, in_string, escaped = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    yield text[start : i + 1]
                    break


def extract_json(text: str) -> dict:
    cleaned = _THINK.sub("", text or "").strip()
    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    for candidate in _balanced_objects(cleaned):
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("No JSON object found in model output")
