"""Orchestration: a fixed, explicit pipeline with model-driven steps inside it.

    catalog (deterministic) -> triage -> specialists (parallel) -> synthesizer -> critic
                                                                       ^            |
                                                                       +-- revise --+  (max 1)

The control flow is plain Python, not decided by an LLM. Models decide *what to look at* inside
their step; the orchestrator decides *which steps run*. That keeps runs predictable, debuggable
and cheap to evaluate, at the cost of not adapting the plan mid-run (see README trade-offs).
"""

import asyncio
import json
from dataclasses import dataclass, field, replace

from incident_agent.agents import specs
from incident_agent.agents.base import AgentOutputError, run_agent
from incident_agent.evidence import EvidenceLedger
from incident_agent.llm import LLM, QuotaExhaustedError, RequestTooLargeError
from incident_agent.mcp_client import ToolBox
from incident_agent.schemas import (
    CriticVerdict,
    IncidentReport,
    SpecialistReport,
    TriageResult,
)
from incident_agent.tracing import Tracer

EVIDENCE_EXCERPT_CHARS = 1500
BRIEF_EXCERPT_CHARS = 800  # per evidence item in the synthesis brief
# Total raw-excerpt budget for the synthesis brief (~3k tokens). Without a cap the prompt grows
# with every tool call; a chatty model hit a provider's per-request input limit this way.
BRIEF_EXCERPT_BUDGET = 12_000
REQUIRED_SPECIALISTS = ("logs", "changes")  # always worth running for a service incident
WEAK_SIGNAL_MAX_CONFIDENCE = 0.4


class InvestigationError(RuntimeError):
    pass


@dataclass
class InvestigationResult:
    report: IncidentReport
    triage: TriageResult
    specialist_reports: dict[str, SpecialistReport]
    failed_specialists: dict[str, str]
    critic_verdicts: list[CriticVerdict]
    revised: bool
    ledger: EvidenceLedger
    trace: dict = field(default_factory=dict)


async def investigate(
    incident: str,
    *,
    llm: LLM,
    toolbox: ToolBox,
    tracer: Tracer,
    use_critic: bool = True,
    max_tool_rounds: int | None = None,
) -> InvestigationResult:
    ledger = EvidenceLedger()

    tracer.event("stage", stage="catalog")
    catalog_text, catalog = await _service_catalog(toolbox, ledger)

    tracer.event("stage", stage="triage")
    triage = await _triage(incident, catalog_text, catalog, llm, tracer)

    tracer.event("stage", stage="specialists", specialists=triage.specialists)
    reports, failures = await _run_specialists(
        incident, triage, catalog, llm, toolbox, ledger, tracer, max_tool_rounds
    )
    if not reports:
        raise InvestigationError(f"All specialists failed: {failures}")

    tracer.event("stage", stage="synthesis")
    weak_signal = _weak_signal(ledger)
    brief = _synthesis_brief(incident, triage, reports, failures, ledger, weak_signal)
    try:
        report = await _synthesize(brief, llm, tracer)
    except RequestTooLargeError as e:
        # Some providers cap input tokens per request/minute below a full brief. The findings
        # already quote the facts, so retry once without the raw excerpts.
        tracer.event("brief_too_large", error=str(e))
        compact = _synthesis_brief(
            incident, triage, reports, failures, ledger, weak_signal, excerpt_budget=0
        )
        try:
            report = await _synthesize(compact, llm, tracer)
        except RequestTooLargeError as e2:
            raise InvestigationError(f"Synthesis request too large for the provider: {e2}") from e2

    verdicts: list[CriticVerdict] = []
    revised = False
    if use_critic:
        tracer.event("stage", stage="critic")
        verdict = await _review(report, ledger, llm, tracer)
        verdicts.append(verdict)
        if not verdict.approved:
            tracer.event("stage", stage="revision", issues=verdict.issues)
            revision = (
                f"{brief}\n\n## Your previous report\n{report.model_dump_json()}\n\n"
                "## Reviewer issues to fix\n"
                + "\n".join(f"- {i}" for i in verdict.issues)
                + "\n\nProduce the corrected report."
            )
            try:
                report = await _synthesize(revision, llm, tracer)
                revised = True
                verdicts.append(_citation_check(report, ledger))
            except (
                InvestigationError,
                RequestTooLargeError,
            ) as e:  # keep the original report rather than fail the run
                tracer.event("revision_failed", error=str(e))

    if weak_signal:
        report = _cap_confidence(report, tracer)
    tracer.event("report", report=report.model_dump())
    return InvestigationResult(
        report=report,
        triage=triage,
        specialist_reports=reports,
        failed_specialists=failures,
        critic_verdicts=verdicts,
        revised=revised,
        ledger=ledger,
        trace=tracer.summary(),
    )


async def _service_catalog(toolbox: ToolBox, ledger: EvidenceLedger) -> tuple[str, list[dict]]:
    """Fetched by the orchestrator itself: every investigation needs it, so no LLM call is spent."""
    result = await toolbox.call("list_services", {})
    eid = ledger.add("orchestrator", "list_services", {}, result.text, result.is_error)
    try:
        catalog = json.loads(result.text)
    except json.JSONDecodeError:
        catalog = []
    return f"[{eid}] {result.text}", catalog


async def _triage(incident, catalog_text, catalog, llm, tracer) -> TriageResult:
    names = [s["name"] for s in catalog]
    try:
        triage = await run_agent(
            specs.TRIAGE,
            f"## Incident report\n{incident}\n\n## Service catalog\n{catalog_text}",
            llm=llm,
            tracer=tracer,
        )
    except (AgentOutputError, RequestTooLargeError) as e:
        tracer.event("triage_fallback", error=str(e))
        triage = TriageResult(incident_type="unknown", service="", rationale="triage failed")

    if triage.service not in names:
        # Deterministic fallback: a service name mentioned verbatim in the report.
        mentioned = [n for n in names if n in incident]
        if mentioned:
            tracer.event("triage_service_corrected", old=triage.service, new=mentioned[0])
            triage.service = mentioned[0]
    for required in REQUIRED_SPECIALISTS:
        if required not in triage.specialists:
            triage.specialists.append(required)
    return triage


async def _run_specialists(incident, triage, catalog, llm, toolbox, ledger, tracer, max_rounds):
    deps = next((s.get("depends_on", []) for s in catalog if s["name"] == triage.service), [])
    task = (
        f"## Incident report\n{incident}\n\n"
        f"## Triage\nAffected service: {triage.service}\nIncident type: {triage.incident_type}\n"
        f"Reported start: {triage.time_hint or 'not stated'}\n"
        f"Dependencies of {triage.service}: {', '.join(deps) or 'none'}\n\n"
        "Investigate using your tools, then report your findings."
    )
    names = list(dict.fromkeys(triage.specialists))  # dedupe, keep order

    async def run_one(name):
        spec = specs.SPECIALISTS[name]
        if max_rounds:
            spec = replace(spec, max_tool_rounds=max_rounds)
        return await run_agent(spec, task, llm=llm, toolbox=toolbox, ledger=ledger, tracer=tracer)

    results = await asyncio.gather(*(run_one(n) for n in names), return_exceptions=True)
    if quota := next((r for r in results if isinstance(r, QuotaExhaustedError)), None):
        raise quota  # not a specialist failure: nothing can run until the quota resets
    reports, failures = {}, {}
    for name, result in zip(names, results, strict=True):
        if isinstance(result, BaseException):
            failures[name] = f"{type(result).__name__}: {result}"
            tracer.event("specialist_failed", name, error=failures[name])
        else:
            reports[name] = result
    return reports, failures


def _weak_signal(ledger: EvidenceLedger) -> bool:
    """True when metrics were checked and none changed level.

    Decided in code, not by the model: in evals the model stayed confident about background noise
    even when every metric said "no significant change". Without any metrics evidence (specialist
    skipped or failed) we cannot tell, so this returns False.
    """
    changes = []
    for e in ledger:
        if e.tool != "get_metrics" or e.is_error:
            continue
        try:
            changes.append(isinstance(json.loads(e.output).get("change"), dict))
        except (json.JSONDecodeError, AttributeError):
            changes.append('"change":{' in e.output.replace(" ", ""))
    return bool(changes) and not any(changes)


def _cap_confidence(report: IncidentReport, tracer: Tracer) -> IncidentReport:
    if report.root_cause.confidence <= WEAK_SIGNAL_MAX_CONFIDENCE:
        return report
    tracer.event(
        "confidence_capped", old=report.root_cause.confidence, new=WEAK_SIGNAL_MAX_CONFIDENCE
    )
    root_cause = report.root_cause.model_copy(update={"confidence": WEAK_SIGNAL_MAX_CONFIDENCE})
    return report.model_copy(update={"root_cause": root_cause})


def _synthesis_brief(
    incident,
    triage,
    reports,
    failures,
    ledger,
    weak_signal=False,
    excerpt_budget=BRIEF_EXCERPT_BUDGET,
) -> str:
    parts = [
        f"## Incident report\n{incident}",
        f"## Triage\n{triage.model_dump_json()}",
        "## Specialist findings",
    ]
    for name, rep in reports.items():
        parts.append(f"### {name}\n{rep.model_dump_json()}")
    if failures:
        parts.append(
            "## Specialists that FAILED (their evidence is missing; lower your confidence)\n"
            + "\n".join(f"- {n}: {err}" for n, err in failures.items())
        )
    if weak_signal:
        parts.append(
            "## Signal assessment (computed from the metrics, not an opinion)\n"
            "WEAK: no metric changed level during the window; errors are within normal "
            "background. Unless a specific error is explained by a specific change, use "
            f'category "unknown", confidence <= {WEAK_SIGNAL_MAX_CONFIDENCE}, and list in '
            "open_questions what data would resolve it."
        )
    parts.append("## Evidence index (cite only these IDs)\n" + ledger.index())
    cited = [eid for rep in reports.values() for f in rep.findings for eid in f.evidence_ids]
    ids, omitted = _within_budget(ledger, cited + [e.id for e in ledger], excerpt_budget)
    excerpts = _excerpts(ledger, ids, BRIEF_EXCERPT_CHARS)
    if omitted:
        excerpts += f"\n\n(Excerpts omitted for space, see the index: {', '.join(omitted)})"
    parts.append("## Raw evidence excerpts\n" + excerpts)
    return "\n\n".join(parts)


async def _synthesize(brief: str, llm, tracer) -> IncidentReport:
    try:
        return await run_agent(specs.SYNTHESIZER, brief, llm=llm, tracer=tracer)
    except AgentOutputError as e:
        raise InvestigationError(str(e)) from e


def _citation_check(report: IncidentReport, ledger: EvidenceLedger) -> CriticVerdict:
    """Deterministic grounding check: every cited evidence ID must exist."""
    issues = [
        f"Evidence item cites {item.evidence_id}, which does not exist. Cite only IDs from the "
        "evidence index."
        for item in report.evidence
        if item.evidence_id not in ledger
    ]
    if not report.evidence:
        issues.append("The report cites no evidence.")
    return CriticVerdict(approved=not issues, issues=issues)


async def _review(report, ledger, llm, tracer) -> CriticVerdict:
    mechanical = _citation_check(report, ledger)
    cited = [i.evidence_id for i in report.evidence if i.evidence_id in ledger]
    message = (
        f"## Report\n{report.model_dump_json()}\n\n"
        f"## Raw evidence cited by the report\n{_excerpts(ledger, cited, EVIDENCE_EXCERPT_CHARS)}"
    )
    try:
        verdict = await run_agent(specs.CRITIC, message, llm=llm, tracer=tracer)
    except (AgentOutputError, RequestTooLargeError) as e:
        tracer.event("critic_failed", error=str(e))
        return mechanical
    issues = mechanical.issues + ([] if verdict.approved else verdict.issues)
    return CriticVerdict(approved=not issues, issues=issues)


def _within_budget(ledger: EvidenceLedger, ids: list[str], budget: int):
    """Pick evidence IDs in priority order until the excerpt budget is spent."""
    chosen, omitted, used = [], [], 0
    for eid in dict.fromkeys(i for i in ids if i in ledger):
        size = min(len(ledger.get(eid).output), BRIEF_EXCERPT_CHARS)
        if used + size <= budget:
            chosen.append(eid)
            used += size
        else:
            omitted.append(eid)
    return chosen, omitted


def _excerpts(ledger: EvidenceLedger, ids: list[str], limit: int) -> str:
    out = []
    for eid in dict.fromkeys(ids):
        e = ledger.get(eid)
        text = e.output if len(e.output) <= limit else e.output[:limit] + " ...[truncated]"
        out.append(f"[{e.id}] {e.label()}:\n{text}")
    return "\n\n".join(out)
