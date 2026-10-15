"""Bridges the MCP server's tools to the agents.

The agents never import tool code. They see tool schemas discovered from the MCP server at runtime
(`tools/list`) and invoke them via `tools/call`, over stdio (spawned subprocess) or Streamable HTTP.
"""

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol

from mcp import Client, StdioServerParameters
from mcp.types import Tool


@dataclass
class ToolResult:
    text: str
    is_error: bool = False


class ToolBox(Protocol):
    def openai_schemas(self, names: tuple[str, ...]) -> list[dict]: ...

    async def call(self, name: str, args: dict) -> ToolResult: ...


def to_openai_schema(tool: Tool) -> dict:
    """MCP tool definitions are JSON Schema already; OpenAI function calling wraps the same thing."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


class MCPToolBox:
    def __init__(self, client: Client, tools: list[Tool], call_timeout_s: float = 30.0):
        self.client = client
        self.tools = {t.name: t for t in tools}
        self.call_timeout_s = call_timeout_s

    def openai_schemas(self, names: tuple[str, ...]) -> list[dict]:
        missing = set(names) - self.tools.keys()
        if missing:
            raise ValueError(f"MCP server does not expose tools: {sorted(missing)}")
        return [to_openai_schema(self.tools[n]) for n in names]

    async def call(self, name: str, args: dict) -> ToolResult:
        try:
            result = await asyncio.wait_for(
                self.client.call_tool(name, args), timeout=self.call_timeout_s
            )
        except TimeoutError:
            return ToolResult(f"Tool {name} timed out after {self.call_timeout_s}s", is_error=True)
        text = "\n".join(c.text for c in result.content if getattr(c, "text", None))
        return ToolResult(text, is_error=bool(result.is_error))


@asynccontextmanager
async def connect(scenario: str | None = None, url: str | None = None) -> AsyncIterator[MCPToolBox]:
    """Connect over Streamable HTTP if `url` is given, else spawn the server over stdio."""
    if url:
        target = url
    else:
        args = ["-m", "incident_agent.mcp_server.server"]
        if scenario:
            args += ["--scenario", scenario]
        target = StdioServerParameters(command=sys.executable, args=args)
    try:
        async with Client(target) as client:
            tools = (await client.list_tools()).tools
            yield MCPToolBox(client, tools)
    except BaseExceptionGroup as group:
        # The SDK's task group wraps whatever the `async with` body raised. Re-raise the
        # original so callers can catch their own exception types.
        raise _sole_exception(group) from None


def _sole_exception(error: BaseException) -> BaseException:
    while isinstance(error, BaseExceptionGroup) and len(error.exceptions) == 1:
        error = error.exceptions[0]
    return error
