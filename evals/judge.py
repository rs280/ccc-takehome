"""Optional LLM-as-judge: grades the report against the scenario's reference answer.

Off by default. Deterministic scorers measure correctness cheaply and reproducibly; the judge adds
a softer signal on whether the explanation and next steps are actually useful. A small local
judge is noisy and shares blind spots with the model under test, so treat its scores as a trend
indicator and prefer a stronger, different model as the judge when available.
"""

from pydantic import BaseModel, Field

from incident_agent.agents.base import AgentSpec, run_agent
from incident_agent.llm import LLM
from incident_agent.schemas import IncidentReport
from incident_agent.tracing import Tracer

JUDGE_PROMPT = """\
You grade incident investigation reports against a reference answer written by the engineer who
knows the true cause.

Score each from 1 (wrong or useless) to 5 (matches the reference, specific and actionable):
- root_cause: does the report identify the same underlying cause as the reference?
- next_steps: would the recommended steps mitigate the incident quickly and safely? Penalise
  harmful steps, such as rolling back a deploy that did not cause the problem.

Reply with only this JSON:
{"root_cause": 1, "next_steps": 1, "reasoning": "<one or two sentences>"}"""


class JudgeScore(BaseModel):
    root_cause: int = Field(ge=1, le=5)
    next_steps: int = Field(ge=1, le=5)
    reasoning: str = ""


JUDGE = AgentSpec("judge", JUDGE_PROMPT, JudgeScore)


async def judge(report: IncidentReport, incident: str, reference: str, llm: LLM) -> JudgeScore:
    message = (
        f"## Incident report from the user\n{incident}\n\n## Reference answer\n{reference}\n\n"
        f"## Report to grade\n{report.model_dump_json(indent=1)}"
    )
    return await run_agent(JUDGE, message, llm=llm, tracer=Tracer(runs_dir=None))
