"""MCP server exposing mock operational data (deploys, logs, metrics, docs) for one scenario.

Run over stdio (default; the agent spawns it as a subprocess):
    uv run mcp-server --scenario checkout_bad_config
Run over Streamable HTTP (networked, e.g. in Docker):
    uv run mcp-server --scenario checkout_bad_config --transport http --port 8000
"""

import argparse
import json
import os
from collections.abc import Callable
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError, ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from incident_agent.mcp_server.world import World, WorldError, available_scenarios

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


def _call(fn: Callable[[], Any]) -> str:
    """Run a World query and serialise it. Bad arguments become ToolError, which MCP returns to the
    model as `is_error=True` with our message so it can correct itself; anything else is a crash
    and the SDK hides its details from the client."""
    try:
        return json.dumps(fn(), separators=(",", ":"))
    except WorldError as e:
        raise ToolError(str(e)) from e


def build_server(world: World) -> MCPServer:
    server = MCPServer(
        name="ops-data",
        log_level="WARNING",
        instructions="Read-only access to deployments, logs, metrics and runbooks for incident "
        "investigation. All timestamps are UTC ISO 8601.",
    )

    @server.tool(annotations=READ_ONLY)
    def list_services() -> str:
        """List known services with owner, tier and upstream dependencies."""
        return _call(world.list_services)

    @server.tool(annotations=READ_ONLY)
    def get_recent_deployments(
        service: Annotated[
            str | None, Field(description="Service name; omit for all services")
        ] = None,
        limit: Annotated[int, Field(ge=1, le=20)] = 5,
    ) -> str:
        """Most recent deployments (newest first) with id, version, time, author and summary."""
        return _call(lambda: world.get_recent_deployments(service, limit))

    @server.tool(annotations=READ_ONLY)
    def get_deployment_diff(deploy_id: Annotated[str, Field(description="e.g. dep-7715")]) -> str:
        """Commits, changed files, config changes and pipeline steps of one deployment."""
        return _call(lambda: world.get_deployment_diff(deploy_id))

    @server.tool(annotations=READ_ONLY)
    def search_logs(
        service: str,
        query: Annotated[
            str, Field(description="Space-separated terms, all must match; '' for any")
        ] = "",
        level: Annotated[str | None, Field(description="INFO, WARN or ERROR")] = None,
        since: Annotated[str | None, Field(description="ISO 8601 lower bound")] = None,
        until: Annotated[str | None, Field(description="ISO 8601 upper bound")] = None,
        limit: Annotated[int, Field(ge=1, le=50)] = 20,
    ) -> str:
        """Search a service's logs. Returns newest matches first plus total count and first match time."""
        return _call(lambda: world.search_logs(service, query, level, since, until, limit))

    @server.tool(annotations=READ_ONLY)
    def get_error_summary(
        service: str,
        around: Annotated[
            str | None, Field(description="Pivot time; defaults to the service's latest deploy")
        ] = None,
    ) -> str:
        """Group WARN/ERROR logs by signature with counts before vs after a pivot time."""
        return _call(lambda: world.get_error_summary(service, around))

    @server.tool(annotations=READ_ONLY)
    def get_metrics(
        service: str,
        metric: Annotated[
            str,
            Field(description="error_rate, latency_p99_ms, memory_mb, cpu_pct, restarts, ..."),
        ],
    ) -> str:
        """Time series (10 min resolution) with baseline, latest, max and first significant change."""
        return _call(lambda: world.get_metrics(service, metric))

    @server.tool(annotations=READ_ONLY)
    def search_docs(query: str) -> str:
        """Keyword search over runbooks and architecture docs. Returns the best matching documents."""
        return _call(lambda: world.search_docs(query))

    @server.resource("runbook://{name}", mime_type="text/markdown")
    def runbook(name: str) -> str:
        """A runbook or architecture doc by name."""
        try:
            return world.read_doc(name)
        except WorldError as e:
            raise ResourceNotFoundError(str(e)) from e

    @server.resource("incident://report", mime_type="text/plain")
    def incident_report() -> str:
        """The incident report filed for this scenario."""
        return world.incident

    return server


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--scenario",
        default=os.environ.get("SCENARIO", "checkout_bad_config"),
        choices=available_scenarios(),
    )
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default=os.environ.get("MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "8000")))
    args = parser.parse_args()

    server = build_server(World.load(args.scenario))
    if args.transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
