"""Spawns the real MCP server over stdio and talks to it with the SDK client."""

import json
import sys

import pytest
from mcp import Client, StdioServerParameters

EXPECTED_TOOLS = {
    "list_services",
    "get_recent_deployments",
    "get_deployment_diff",
    "search_logs",
    "get_error_summary",
    "get_metrics",
    "search_docs",
}


def server_params(scenario="checkout_bad_config"):
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "incident_agent.mcp_server.server", "--scenario", scenario],
    )


async def test_stdio_roundtrip():
    async with Client(server_params()) as client:
        tools = (await client.list_tools()).tools
        assert {t.name for t in tools} == EXPECTED_TOOLS
        assert all(t.input_schema["type"] == "object" for t in tools)

        result = await client.call_tool(
            "search_logs", {"service": "checkout-api", "level": "ERROR"}
        )
        assert not result.is_error
        payload = json.loads(result.content[0].text)
        assert payload["total_matches"] > 0

        bad = await client.call_tool("get_deployment_diff", {"deploy_id": "dep-0000"})
        assert bad.is_error
        assert "Unknown deploy_id" in bad.content[0].text

        doc = await client.read_resource("runbook://rollback")
        assert "Rolling back" in doc.contents[0].text


async def test_streamable_http_roundtrip():
    import socket
    import subprocess
    import time

    from incident_agent import mcp_client

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "incident_agent.mcp_server.server",
            "--scenario",
            "auth_cert_expiry",
            "--transport",
            "http",
            "--port",
            str(port),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        async with mcp_client.connect(url=f"http://127.0.0.1:{port}/mcp") as toolbox:
            assert set(toolbox.tools) == EXPECTED_TOOLS
            result = await toolbox.call("get_recent_deployments", {"service": "auth-api"})
            assert json.loads(result.text)[0]["version"] == "v4.2.0"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


async def test_errors_inside_connect_propagate_unwrapped():
    # The SDK's task group wraps errors raised in the `async with` body in an ExceptionGroup,
    # which defeated callers' `except InvestigationError`.
    from incident_agent import mcp_client

    with pytest.raises(ValueError, match="boom"):
        async with mcp_client.connect(scenario="checkout_bad_config"):
            raise ValueError("boom")
