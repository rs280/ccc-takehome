"""The agent roster: who exists, what each may call, and what each must return."""

from incident_agent.agents import prompts
from incident_agent.agents.base import AgentSpec
from incident_agent.schemas import (
    CriticVerdict,
    IncidentReport,
    SpecialistName,
    SpecialistReport,
    TriageResult,
)

TRIAGE = AgentSpec("triage", prompts.TRIAGE, TriageResult)

# Each specialist sees only the tools for its domain. Narrow toolsets keep small models on task
# and make each agent's behaviour easy to evaluate in isolation.
SPECIALISTS: dict[SpecialistName, AgentSpec] = {
    "logs": AgentSpec(
        "logs", prompts.LOGS, SpecialistReport, tools=("get_error_summary", "search_logs")
    ),
    "changes": AgentSpec(
        "changes",
        prompts.CHANGES,
        SpecialistReport,
        tools=("get_recent_deployments", "get_deployment_diff"),
    ),
    "metrics": AgentSpec("metrics", prompts.METRICS, SpecialistReport, tools=("get_metrics",)),
    "docs": AgentSpec(
        "docs", prompts.DOCS, SpecialistReport, tools=("search_docs",), max_tool_rounds=3
    ),
}

SYNTHESIZER = AgentSpec("synthesizer", prompts.SYNTHESIZER, IncidentReport)
CRITIC = AgentSpec("critic", prompts.CRITIC, CriticVerdict)
