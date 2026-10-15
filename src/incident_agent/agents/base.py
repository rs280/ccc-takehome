"""The one agent primitive everything is built from.

An agent is (system prompt, tool allowlist, output schema). `run_agent` drives the standard
tool-use loop: ask the model, execute any tool calls through MCP, feed results back with evidence
IDs, and finally parse and validate a JSON answer.
"""

import json
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from incident_agent.evidence import EvidenceLedger
from incident_agent.jsonutil import extract_json
from incident_agent.llm import LLM, LLMResponse, ToolCall
from incident_agent.mcp_client import ToolBox
from incident_agent.tracing import Tracer

MAX_TOOL_OUTPUT_CHARS = 6000


class AgentOutputError(RuntimeError):
    """The model failed to produce valid output even after a repair round."""


@dataclass(frozen=True)
class AgentSpec:
    name: str
    system_prompt: str
    output_model: type[BaseModel]
    tools: tuple[str, ...] = ()
    max_tool_rounds: int = 6


async def run_agent(
    spec: AgentSpec,
    user_message: str,
    *,
    llm: LLM,
    tracer: Tracer,
    toolbox: ToolBox | None = None,
    ledger: EvidenceLedger | None = None,
) -> BaseModel:
    tracer.event("agent_start", spec.name, tools=list(spec.tools))
    result = await _loop(spec, user_message, llm, tracer, toolbox, ledger)
    tracer.event("agent_end", spec.name, output=result.model_dump())
    return result


async def _loop(spec, user_message, llm, tracer, toolbox, ledger) -> BaseModel:
    messages: list[dict] = [
        {"role": "system", "content": spec.system_prompt},
        {"role": "user", "content": user_message},
    ]
    schemas = toolbox.openai_schemas(spec.tools) if spec.tools and toolbox else None

    for _ in range(spec.max_tool_rounds):
        response = await _complete(llm, messages, schemas, spec.name, tracer)
        if not response.tool_calls:
            return await _finish(spec, messages, response, llm, tracer)
        messages.append(_assistant_message(response))
        for call in response.tool_calls:
            content = await _execute(spec, call, toolbox, ledger, tracer)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

    # Tool budget spent: ask for the answer with tools withheld so the model cannot keep looping.
    tracer.event("tool_budget_exhausted", spec.name)
    messages.append(
        {
            "role": "user",
            "content": "You have used your tool budget. Using the evidence gathered so far, reply now "
            "with only the final JSON object.",
        }
    )
    response = await _complete(llm, messages, None, spec.name, tracer)
    return await _finish(spec, messages, response, llm, tracer)


async def _complete(llm, messages, schemas, agent, tracer) -> LLMResponse:
    response = await llm.complete(messages, tools=schemas)
    tracer.event(
        "llm_call",
        agent,
        latency_s=round(response.latency_s, 2),
        usage=response.usage,
        tool_calls=[c.name for c in response.tool_calls],
        content_chars=len(response.content),
    )
    return response


def _assistant_message(response: LLMResponse) -> dict:
    return {
        "role": "assistant",
        "content": response.content or None,
        "tool_calls": [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
            }
            for c in response.tool_calls
        ],
    }


async def _execute(spec, call: ToolCall, toolbox, ledger, tracer) -> str:
    """Run one tool call. Every failure is returned to the model as text so it can adapt."""
    if call.name not in spec.tools or toolbox is None:
        tracer.event("tool_refused", spec.name, tool=call.name)
        return (
            f"Error: tool {call.name!r} is not available to you. Available: {', '.join(spec.tools)}"
        )
    if call.argument_error:
        tracer.event("tool_bad_args", spec.name, tool=call.name, error=call.argument_error)
        return f"Error: could not parse arguments for {call.name}: {call.argument_error}"
    if ledger is not None and (existing := ledger.find(call.name, call.arguments)):
        return f"[{existing}] You already ran this exact call; see evidence {existing} above."

    try:
        result = await toolbox.call(call.name, call.arguments)
        text, is_error = result.text, result.is_error
    except Exception as e:  # a broken connection must not kill the whole investigation
        text, is_error = f"Tool {call.name} failed: {type(e).__name__}: {e}", True

    eid = (
        ledger.add(spec.name, call.name, call.arguments, text, is_error)
        if ledger is not None
        else "E?"
    )
    tracer.event(
        "tool_call",
        spec.name,
        tool=call.name,
        args=call.arguments,
        evidence_id=eid,
        is_error=is_error,
        output_chars=len(text),
    )
    if len(text) > MAX_TOOL_OUTPUT_CHARS:
        text = text[:MAX_TOOL_OUTPUT_CHARS] + " ...[truncated; narrow your query]"
    return f"[{eid}]{' ERROR' if is_error else ''} {text}"


async def _finish(spec, messages, response, llm, tracer) -> BaseModel:
    """Parse the final answer; on failure give the model exactly one chance to repair it."""
    try:
        return _parse(spec, response.content)
    except (ValueError, ValidationError) as first_error:
        tracer.event("output_invalid", spec.name, error=str(first_error)[:500])
        messages.append({"role": "assistant", "content": response.content})
        messages.append(
            {
                "role": "user",
                "content": f"Your reply was not valid: {_brief(first_error)}\n"
                "Reply with only the corrected JSON object, no other text.",
            }
        )
        retry = await _complete(llm, messages, None, spec.name, tracer)
        try:
            return _parse(spec, retry.content)
        except (ValueError, ValidationError) as e:
            tracer.event("agent_error", spec.name, error=str(e)[:500])
            raise AgentOutputError(f"{spec.name}: invalid output after repair: {_brief(e)}") from e


def _parse(spec: AgentSpec, content: str) -> BaseModel:
    return spec.output_model.model_validate(extract_json(content))


def _brief(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()[:8])
    return str(error)
