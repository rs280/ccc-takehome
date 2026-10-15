"""Provider-quirk handling in the OpenAI-compatible client."""

import asyncio
import json
from types import SimpleNamespace

import httpx2
import pytest
from openai import APIStatusError, BadRequestError, RateLimitError

from incident_agent.config import Settings
from incident_agent.llm import (
    OpenAICompatLLM,
    QuotaExhaustedError,
    RequestTooLargeError,
    _recover_rejected_generation,
)

TOOLS = [{"type": "function", "function": {"name": "search_logs", "parameters": {}}}]


def rejected(failed_generation: str, code: str = "tool_use_failed") -> BadRequestError:
    body = {"error": {"code": code, "failed_generation": failed_generation}}
    response = httpx2.Response(400, request=httpx2.Request("POST", "http://x"), json=body)
    return BadRequestError("rejected", response=response, body=body)


def test_answer_sent_as_unknown_tool_becomes_content():
    answer = {"summary": "s", "findings": []}
    gen = json.dumps({"name": "JSON", "arguments": answer})
    out = _recover_rejected_generation(rejected(gen), TOOLS)
    assert json.loads(out.content) == answer and not out.tool_calls


def test_real_tool_with_rejected_args_is_passed_to_the_loop():
    gen = json.dumps({"name": "search_logs", "arguments": {"service": 3}})
    out = _recover_rejected_generation(rejected(gen), TOOLS)
    assert out.tool_calls[0].name == "search_logs"


def test_unparseable_generation_is_returned_as_text():
    out = _recover_rejected_generation(rejected('{"summary": "s"} trailing'), TOOLS)
    assert out.content.startswith('{"summary"')


def test_other_bad_requests_are_not_swallowed():
    assert _recover_rejected_generation(rejected("{}", code="context_length"), TOOLS) is None


def rate_limited(message: str) -> RateLimitError:
    body = {"error": {"message": message}}
    response = httpx2.Response(429, request=httpx2.Request("POST", "http://x"), json=body)
    return RateLimitError(message, response=response, body=body)


def llm_raising(*errors):
    llm = OpenAICompatLLM(Settings(llm_max_retries=0))
    queue = list(errors)

    async def create(**kwargs):
        if queue:
            raise queue.pop(0)
        message = SimpleNamespace(content='{"ok": true}', tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    llm.client.chat.completions.create = create
    return llm


async def test_per_minute_rate_limit_is_waited_out(monkeypatch):
    slept = []

    async def fake_sleep(s):
        slept.append(s)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    llm = llm_raising(rate_limited("tokens per minute (TPM): Please try again in 1m2.5s."))
    out = await llm.complete([{"role": "user", "content": "hi"}])
    assert out.content == '{"ok": true}'
    assert 63 <= slept[0] <= 64.5  # 62.5s suggested plus 0.5-2s jitter


async def test_daily_quota_raises_immediately():
    llm = llm_raising(rate_limited("on tokens per day (TPD): try again in 28m1.3s"))
    with pytest.raises(QuotaExhaustedError):
        await llm.complete([{"role": "user", "content": "hi"}])


def too_large() -> APIStatusError:
    body = {"error": {"message": "Request too large: input tokens per minute (ITPM): Limit 7000"}}
    response = httpx2.Response(413, request=httpx2.Request("POST", "http://x"), json=body)
    return APIStatusError("Request too large", response=response, body=body)


async def test_request_too_large_raises_a_typed_error():
    llm = llm_raising(too_large())
    with pytest.raises(RequestTooLargeError):
        await llm.complete([{"role": "user", "content": "hi"}])
