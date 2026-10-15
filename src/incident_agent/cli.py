"""Command line entry point.

uv run investigate --scenario checkout_bad_config
uv run investigate "orders-api returns 500s since the deploy" --scenario orders_upstream_dependency
"""

import argparse
import asyncio
import json
import sys

from incident_agent import mcp_client
from incident_agent.config import Settings
from incident_agent.llm import QuotaExhaustedError, make_llm
from incident_agent.mcp_server.world import World, available_scenarios
from incident_agent.orchestrator import InvestigationError, investigate
from incident_agent.render import to_markdown
from incident_agent.tracing import Tracer


def main() -> None:
    parser = argparse.ArgumentParser(description="Investigate a production incident.")
    parser.add_argument("report", nargs="?", help="Incident report (defaults to the scenario's)")
    parser.add_argument(
        "--scenario",
        default="checkout_bad_config",
        choices=available_scenarios(),
        help="Mock world the MCP server serves (ignored with MCP_URL)",
    )
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    parser.add_argument("--no-critic", action="store_true", help="Skip the critic/revision step")
    parser.add_argument("-q", "--quiet", action="store_true", help="Hide the live agent trace")
    args = parser.parse_args()

    settings = Settings.from_env()
    report = args.report or World.load(args.scenario).incident
    print(
        f"Incident: {report}\nModel: {settings.llm_model} @ {settings.llm_base_url}\n",
        file=sys.stderr,
    )
    try:
        result = asyncio.run(run(report, args.scenario, settings, args))
    except (InvestigationError, QuotaExhaustedError) as e:
        print(f"Investigation failed: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(result.report.model_dump(), indent=2))
    else:
        print(to_markdown(result))


async def run(report, scenario, settings, args):
    tracer = Tracer(settings.runs_dir, verbose=not args.quiet)
    async with mcp_client.connect(scenario=scenario, url=settings.mcp_url) as toolbox:
        return await investigate(
            report,
            llm=make_llm(settings),
            toolbox=toolbox,
            tracer=tracer,
            use_critic=not args.no_critic,
            max_tool_rounds=settings.max_tool_rounds,
        )


if __name__ == "__main__":
    main()
