"""Deterministic scorers. Each takes the run outcome and the scenario's ground truth.

They are intentionally simple and transparent (substring and set checks) so a failure can be
explained by reading one function. Their known blind spots are documented in the README.
"""

import re
from dataclasses import dataclass

from incident_agent.evidence import EvidenceLedger
from incident_agent.schemas import IncidentReport

# Pass/fail thresholds for a run (see `passed`).
MIN_KEY_FACT_RECALL = 0.5
MIN_GROUNDING = 0.8


@dataclass
class Score:
    name: str
    value: float  # 0..1
    passed: bool
    detail: str = ""


def root_cause_category(report: IncidentReport, expected: dict) -> Score:
    ok = report.root_cause.category in expected.get("acceptable_categories", [expected["category"]])
    return Score(
        "root_cause_category",
        float(ok),
        ok,
        f"got {report.root_cause.category}, expected {expected['category']}",
    )


def deploy_attribution(report: IncidentReport, expected: dict) -> Score:
    want, got = expected["caused_by_latest_deploy"], report.caused_by_latest_deploy
    # When the truth is "undetermined", saying "not deploy related" is acceptable; blaming it is not.
    ok = got is not True if want is None else got is want
    return Score("deploy_attribution", float(ok), ok, f"got {got}, expected {want}")


def key_fact_recall(report: IncidentReport, expected: dict) -> Score:
    text = report.model_dump_json().lower()
    facts = expected["key_facts"]
    found = [f for f in facts if f.lower() in text]
    value = len(found) / len(facts)
    missing = sorted(set(facts) - set(found))
    return Score(
        "key_fact_recall",
        value,
        value >= MIN_KEY_FACT_RECALL,
        f"missing {missing}" if missing else "all found",
    )


def _distinctive_tokens(text: str) -> set[str]:
    """Tokens that are facts rather than prose: identifiers and numbers (versions, deploy ids,
    env vars, file names, timestamps, error codes). Ordinary words are excluded because a
    faithful paraphrase ("deployment", "configuration") must not count as unsupported."""
    out = set()
    for raw in re.findall(r"[A-Za-z0-9_.:\-]+", text):
        t = raw.strip(".:-").lower()
        # "201.68ms" is the number 201.68 with a unit; raw tool output keeps units in field names.
        t = re.sub(r"^(\d[\d.]*)(ms|s|min|h|ki|mi|gi|kb|mb|gb)$", r"\1", t)
        is_identifier = re.search(r"\d", t) or "_" in t or (raw.isupper() and len(raw) >= 4)
        if len(t) >= 3 and is_identifier:
            out.add(t)
    return out


def citation_grounding(report: IncidentReport, ledger: EvidenceLedger) -> Score:
    """Each evidence item must cite a real ledger entry, and its distinctive tokens must mostly
    appear in that entry's raw output. Catches invented IDs and invented facts."""
    if not report.evidence:
        return Score("citation_grounding", 0.0, False, "no evidence cited")
    grounded, problems = 0, []
    for item in report.evidence:
        source = ledger.get(item.evidence_id)
        if source is None:
            problems.append(f"{item.evidence_id}: no such evidence")
            continue
        tokens = _distinctive_tokens(item.detail)
        haystack = source.output.lower()
        hits = [t for t in tokens if t in haystack]
        if not tokens or len(hits) / len(tokens) >= 0.5:
            grounded += 1
        else:
            problems.append(
                f"{item.evidence_id}: unsupported {sorted(set(tokens) - set(hits))[:4]}"
            )
    value = grounded / len(report.evidence)
    return Score("citation_grounding", value, value >= MIN_GROUNDING, "; ".join(problems))


def tool_coverage(ledger: EvidenceLedger, expected: dict) -> Score:
    """Expected tools are given as 'a|b' alternatives; each group must have been called."""
    called = {e.tool for e in ledger if not e.is_error}
    groups = expected.get("expected_tools", [])
    missing = [g for g in groups if not set(g.split("|")) & called]
    value = 1 - len(missing) / len(groups) if groups else 1.0
    return Score("tool_coverage", value, not missing, f"missing {missing}" if missing else "")


def next_step_relevance(report: IncidentReport, expected: dict) -> Score:
    text = " ".join(f"{s.action} {s.rationale}" for s in report.next_steps).lower()
    hits = [k for k in expected.get("next_step_keywords", []) if k.lower() in text]
    ok = bool(hits)
    return Score("next_step_relevance", float(ok), ok, f"matched {hits}" if hits else "no match")


def calibration(report: IncidentReport, expected: dict, category_correct: bool) -> Score:
    conf = report.root_cause.confidence
    if "max_confidence" in expected:
        ok, rule = conf <= expected["max_confidence"], f"<= {expected['max_confidence']}"
    elif category_correct:
        ok, rule = conf >= 0.5, ">= 0.5 when correct"
    else:
        ok, rule = conf < 0.7, "< 0.7 when wrong"
    return Score("calibration", float(ok), ok, f"confidence {conf:.2f}, want {rule}")


def score_run(
    report: IncidentReport | None, ledger: EvidenceLedger | None, expected: dict
) -> list[Score]:
    if report is None or ledger is None:
        return [Score("schema_valid", 0.0, False, "no valid report produced")]
    category = root_cause_category(report, expected)
    return [
        Score("schema_valid", 1.0, True),
        category,
        deploy_attribution(report, expected),
        key_fact_recall(report, expected),
        citation_grounding(report, ledger),
        tool_coverage(ledger, expected),
        next_step_relevance(report, expected),
        calibration(report, expected, category.passed),
    ]


GATING = (
    "schema_valid",
    "root_cause_category",
    "deploy_attribution",
    "key_fact_recall",
    "citation_grounding",
)


def passed(scores: list[Score]) -> bool:
    """A run passes when the answer is right and grounded. Tool coverage, next steps and
    calibration are tracked as quality signals but do not gate."""
    by_name = {s.name: s for s in scores}
    return all(by_name.get(n) is not None and by_name[n].passed for n in GATING)
