"""LLM access behind a tiny interface.

`OpenAICompatLLM` talks to any OpenAI-compatible Chat Completions endpoint: local Ollama, Groq,
Gemini's OpenAI endpoint, OpenAI itself. `FakeLLM` replays scripted responses so the whole
pipeline is testable without a model.
"""

import asyncio
import json
import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from openai import APIStatusError, AsyncOpenAI, BadRequestError, RateLimitError

from incident_agent.config import Settings


class QuotaExhaustedError(RuntimeError):
    """The provider's daily quota is used up. Retrying within this run cannot help, so callers
    should stop rather than record the failure as the model's."""


class RequestTooLargeError(RuntimeError):
    """The provider rejected the request as too large (HTTP 413, e.g. a per-minute input-token
    cap smaller than one prompt). Resending the same request cannot help; send less."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    argument_error: str | None = None  # set when the model emitted unparseable arguments


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    latency_s: float = 0.0


class LLM(Protocol):
    model: str

    async def complete(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> LLMResponse: ...


def _parse_tool_call(tc) -> ToolCall:
    raw = tc.function.arguments or "{}"
    try:
        args = json.loads(raw)
        if not isinstance(args, dict):
            raise ValueError("arguments must be a JSON object")
        return ToolCall(tc.id, tc.function.name, args)
    except ValueError as e:
        return ToolCall(tc.id, tc.function.name, {}, argument_error=f"{e}: {raw[:200]}")


def _recover_rejected_generation(error: BadRequestError, tools: list[dict] | None):
    """Salvage a generation the provider rejected for an invalid tool call.

    gpt-oss on Groq sometimes emits its final JSON answer as a call to a made-up tool named
    "JSON". Groq rejects that with 400 `tool_use_failed` but returns the generation in
    `failed_generation`. A call to a tool we did not offer is the model answering, so its
    arguments become the content; a call to a real tool with bad arguments is passed on so the
    agent loop reports the problem to the model. Returns None for any other 400.
    """
    body = error.body if isinstance(error.body, dict) else {}
    body = body.get("error", body)
    if body.get("code") != "tool_use_failed" or "failed_generation" not in body:
        return None
    raw = body["failed_generation"]
    try:
        call = json.loads(raw)
        name, args = call["name"], call.get("arguments", {})
    except (ValueError, TypeError, KeyError):
        return LLMResponse(content=raw)
    offered = {t["function"]["name"] for t in tools or []}
    if name in offered:
        if isinstance(args, dict):
            return LLMResponse(tool_calls=[ToolCall("rejected-0", name, args)])
        return LLMResponse(
            tool_calls=[ToolCall("rejected-0", name, {}, argument_error=f"not an object: {args}")]
        )
    return LLMResponse(content=args if isinstance(args, str) else json.dumps(args))


def _suggested_wait_s(error: RateLimitError) -> float | None:
    """How long the provider says to wait: Retry-After, else "try again in 1m4.5s" in the body."""
    header = error.response.headers.get("retry-after") if error.response is not None else None
    try:
        if header is not None:
            return float(header)
    except ValueError:
        pass
    if m := re.search(r"try again in (?:(\d+)m)?([\d.]+)s", str(error)):
        return int(m.group(1) or 0) * 60 + float(m.group(2))
    return None


class OpenAICompatLLM:
    def __init__(self, settings: Settings):
        self.model = settings.llm_model
        self.reasoning_effort = settings.llm_reasoning_effort
        self._slots = asyncio.Semaphore(settings.llm_max_concurrency)
        self.rate_limit_wait_s = settings.llm_rate_limit_wait_s
        # The SDK retries connection errors, 408/409/429 and 5xx with exponential backoff.
        self.client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
        )

    async def complete(self, messages, tools=None) -> LLMResponse:
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": 0.2}
        if tools:
            kwargs["tools"] = tools
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        async with self._slots:  # wait our turn here so the timeout only covers real work
            start = time.perf_counter()
            try:
                resp = await self._create(kwargs)
            except BadRequestError as e:
                if (recovered := _recover_rejected_generation(e, tools)) is None:
                    raise
                recovered.latency_s = time.perf_counter() - start
                return recovered
        msg = resp.choices[0].message
        usage = {}
        if resp.usage:
            usage = {"prompt": resp.usage.prompt_tokens, "completion": resp.usage.completion_tokens}
        return LLMResponse(
            content=msg.content or "",
            tool_calls=[_parse_tool_call(tc) for tc in (msg.tool_calls or [])],
            usage=usage,
            latency_s=time.perf_counter() - start,
        )

    async def _create(self, kwargs: dict):
        """Create a completion, waiting out per-minute rate limits within a time budget.

        The SDK's fixed retry count is not enough when parallel agents share a small
        tokens-per-minute quota: they keep colliding and one gives up, which silently drops a
        specialist's evidence. A daily quota cannot be waited out, so it raises immediately.
        """
        deadline = time.monotonic() + self.rate_limit_wait_s
        while True:
            try:
                return await self.client.chat.completions.create(**kwargs)
            except RateLimitError as e:
                if "per day" in str(e).lower():
                    raise QuotaExhaustedError(str(e)) from e
                wait = (_suggested_wait_s(e) or 5.0) + random.uniform(0.5, 2.0)  # de-synchronise
                if time.monotonic() + wait > deadline:
                    raise
                await asyncio.sleep(wait)
            except APIStatusError as e:
                if e.status_code == 413:
                    raise RequestTooLargeError(str(e)) from e
                raise


Handler = Callable[[list[dict], list[dict] | None], LLMResponse]


class FakeLLM:
    """Deterministic stand-in. `handler` sees the conversation and returns the next response,
    so tests can route by agent (system prompt) and by how far the conversation has progressed."""

    model = "fake"

    def __init__(self, handler: Handler):
        self.handler = handler
        self.calls: list[list[dict]] = []

    async def complete(self, messages, tools=None) -> LLMResponse:
        self.calls.append(list(messages))
        return self.handler(messages, tools)


def make_llm(settings: Settings) -> LLM:
    return OpenAICompatLLM(settings)
