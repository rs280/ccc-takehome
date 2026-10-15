"""Human-readable rendering of an investigation."""

from incident_agent.orchestrator import InvestigationResult


def to_markdown(result: InvestigationResult) -> str:
    r = result.report
    rc = r.root_cause
    deploy = {True: "yes", False: "no", None: "undetermined"}[r.caused_by_latest_deploy]
    lines = [
        f"# Incident report: {r.incident_type}",
        "",
        r.summary,
        "",
        f"**Affected services:** {', '.join(r.affected_services)}  ",
        f"**Caused by latest deploy:** {deploy}",
        "",
        "## Probable root cause",
        f"{rc.hypothesis}",
        "",
        f"Category: `{rc.category}`, confidence: {rc.confidence:.0%}",
        "",
        "## Evidence",
    ]
    for e in r.evidence:
        source = result.ledger.get(e.evidence_id)
        origin = f" - via `{source.label()}`" if source else " - **citation not found**"
        lines.append(f"- **[{e.evidence_id}]** ({e.source}) {e.detail}{origin}")
    if r.alternatives_ruled_out:
        lines += ["", "## Ruled out"] + [f"- {a}" for a in r.alternatives_ruled_out]
    lines += ["", "## Recommended next steps"]
    for s in r.next_steps:
        lines.append(
            f"- **{s.priority}** {s.action}" + (f" - {s.rationale}" if s.rationale else "")
        )
    if r.open_questions:
        lines += ["", "## Open questions"] + [f"- {q}" for q in r.open_questions]

    t = result.trace
    notes = []
    if result.failed_specialists:
        notes.append(f"failed specialists: {', '.join(result.failed_specialists)}")
    if result.revised:
        notes.append("revised after critic review")
    lines += [
        "",
        "---",
        f"_Run {t.get('run_id')}: {t.get('elapsed_s')}s, {t.get('llm_calls')} LLM calls, "
        f"{t.get('tool_calls')} tool calls, {len(result.ledger)} evidence items"
        + (f"; {'; '.join(notes)}" if notes else "")
        + f". Trace: {t.get('trace_file')}_",
    ]
    return "\n".join(lines)
