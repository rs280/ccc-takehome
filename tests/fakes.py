"""Shared test doubles."""

import json

from incident_agent.llm import LLMResponse, ToolCall
from incident_agent.mcp_client import ToolResult


class StubToolBox:
    """In-memory tool box: `responses` maps tool name to output text (or a callable of args)."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def openai_schemas(self, names):
        return [
            {
                "type": "function",
                "function": {"name": n, "description": "", "parameters": {"type": "object"}},
            }
            for n in names
        ]

    async def call(self, name, args):
        self.calls.append((name, args))
        value = self.responses.get(name)
        if value is None:
            return ToolResult(f"Unknown tool {name}", is_error=True)
        if isinstance(value, Exception):
            raise value
        return ToolResult(value(args) if callable(value) else value)


def tool_call(name: str, call_id: str = "c1", **args) -> LLMResponse:
    return LLMResponse(tool_calls=[ToolCall(call_id, name, args)])


def final(obj: dict) -> LLMResponse:
    return LLMResponse(content=json.dumps(obj))
