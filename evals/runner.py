"""Run the eval suite: every scenario, k times, scored against ground truth.

    uv run evals                      # all scenarios, k=1
    uv run evals --k 3                # reliability: pass rate over 3 runs each
    uv run evals --scenarios auth_cert_expiry,orders_upstream_dependency
    uv run evals --no-critic          # ablation: measure what the critic adds
    uv run evals --judge              # add LLM-as-judge scores

Writes evals/results/<timestamp>/results.json (everything), summary.md (table + failures)
and traces/ (one JSONL trace per run).
"""

import argparse
import asyncio
import json
import statistics
import time
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from evals.judge import judge
from evals.scorers import passed, score_run
from incident_agent import mcp_client
from incident_agent.config import Settings
from incident_agent.llm import LLM, QuotaExhaustedError, make_llm
from incident_agent.mcp_server.world import World, available_scenarios
from incident_agent.orchestrator import investigate
from incident_agent.tracing import Tracer

RESULTS_DIR = Path(__file__).parent / "results"


@dataclass
class RunRecord:
    scenario: str
    attempt: int
    passed: bool
    scores: dict[str, dict]
    elapsed_s: float
    llm_calls: int = 0
    tool_calls: int = 0
    tokens: dict = field(default_factory=dict)
    report: dict | None = None
    failed_specialists: dict = field(default_factory=dict)
    revised: bool = False
    judge: dict | None = None
    error: str | None = None
    trace_file: str | None = None
    evidence: list[dict] = field(default_factory=list)  # the ledger, so runs can be re-scored


async def run_one(
    scenario: str,
    attempt: int,
    llm: LLM,
    settings: Settings,
    traces_dir: Path,
    use_critic: bool,
    use_judge: bool,
) -> RunRecord:
    world = World.load(scenario)
    expected = json.loads((world.root / "expected.json").read_text())
    tracer = Tracer(traces_dir, run_id=f"{scenario}-{attempt}")
    start = time.perf_counter()
    report = ledger = result = None
    error = None
    try:
        async with mcp_client.connect(scenario=scenario, url=settings.mcp_url) as toolbox:
            result = await investigate(
                world.incident,
                llm=llm,
                toolbox=toolbox,
                tracer=tracer,
                use_critic=use_critic,
                max_tool_rounds=settings.max_tool_rounds,
            )
        report, ledger = result.report, result.ledger
    except QuotaExhaustedError:
        raise  # an infrastructure limit, not a model failure: don't score it
    except Exception as e:  # a crashed run is a scored failure, not a crashed suite
        error = f"{type(e).__name__}: {e}"
        tracer.event("run_error", error=error, traceback=traceback.format_exc())

    scores = score_run(report, ledger, expected)
    judged = None
    if use_judge and report is not None:
        try:
            judged = (
                await judge(report, world.incident, expected["reference_answer"], llm)
            ).model_dump()
        except Exception as e:
            judged = {"error": str(e)}
    summary = tracer.summary()
    return RunRecord(
        scenario=scenario,
        attempt=attempt,
        passed=passed(scores),
        scores={
            s.name: {"value": round(s.value, 3), "passed": s.passed, "detail": s.detail}
            for s in scores
        },
        elapsed_s=round(time.perf_counter() - start, 1),
        llm_calls=summary["llm_calls"],
        tool_calls=summary["tool_calls"],
        tokens=summary["tokens"],
        report=report.model_dump() if report else None,
        failed_specialists=result.failed_specialists if result else {},
        revised=result.revised if result else False,
        judge=judged,
        error=error,
        trace_file=summary["trace_file"],
        evidence=ledger.to_dict() if ledger else [],
    )


async def run_suite(
    scenarios: list[str],
    k: int,
    llm: LLM,
    settings: Settings,
    out_dir: Path,
    use_critic: bool = True,
    use_judge: bool = False,
    on_record: Callable[[RunRecord], None] | None = None,
    on_stop: Callable[[str], None] | None = None,
) -> list[RunRecord]:
    records = []
    traces = out_dir / "traces"
    for scenario in scenarios:
        for attempt in range(1, k + 1):
            try:
                record = await run_one(
                    scenario, attempt, llm, settings, traces, use_critic, use_judge
                )
            except QuotaExhaustedError as e:
                if on_stop:
                    on_stop(f"Stopped before {scenario} #{attempt}: provider quota exhausted ({e})")
                return records
            records.append(record)
            if on_record:
                on_record(record)
    return records


SCORE_COLUMNS = [
    "root_cause_category",
    "deploy_attribution",
    "key_fact_recall",
    "citation_grounding",
    "tool_coverage",
    "next_step_relevance",
    "calibration",
]


def summarize(records: list[RunRecord], meta: dict) -> str:
    by_scenario: dict[str, list[RunRecord]] = {}
    for r in records:
        by_scenario.setdefault(r.scenario, []).append(r)

    def mean(rs, name):
        return statistics.mean(r.scores.get(name, {}).get("value", 0.0) for r in rs)

    header = (
        ["scenario", "pass"] + [c.replace("_", " ") for c in SCORE_COLUMNS] + ["avg s", "tools"]
    )
    lines = [
        f"# Eval results {meta['timestamp']}",
        "",
        *([f"**Incomplete.** {meta['stopped']}", ""] if meta.get("stopped") else []),
        f"Model `{meta['model']}`, k={meta['k']}, critic={'on' if meta['critic'] else 'off'}"
        f"{', judge on' if meta['judge'] else ''}.",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]
    for scenario, rs in by_scenario.items():
        row = [scenario, f"{sum(r.passed for r in rs)}/{len(rs)}"]
        row += [f"{mean(rs, c):.2f}" for c in SCORE_COLUMNS]
        row += [
            f"{statistics.mean(r.elapsed_s for r in rs):.0f}",
            f"{statistics.mean(r.tool_calls for r in rs):.1f}",
        ]
        lines.append("| " + " | ".join(row) + " |")
    total = len(records)
    all_pass = [all(r.passed for r in rs) for rs in by_scenario.values()]
    row = ["**overall**", f"**{sum(r.passed for r in records)}/{total}**"]
    row += [f"{mean(records, c):.2f}" for c in SCORE_COLUMNS]
    row += [
        f"{statistics.mean(r.elapsed_s for r in records):.0f}",
        f"{statistics.mean(r.tool_calls for r in records):.1f}",
    ]
    lines.append("| " + " | ".join(row) + " |")
    lines += [
        "",
        f"Pass rate: {sum(r.passed for r in records) / total:.0%} of runs. "
        f"Scenarios passing on all {meta['k']} attempts (pass^k): {sum(all_pass)}/{len(all_pass)}.",
    ]
    judged = [r.judge for r in records if r.judge and "error" not in r.judge]
    if judged:
        lines.append(
            f"LLM judge (1-5): root cause {statistics.mean(j['root_cause'] for j in judged):.2f}, "
            f"next steps {statistics.mean(j['next_steps'] for j in judged):.2f}."
        )

    failures = [r for r in records if not r.passed]
    if failures:
        lines += ["", "## Failures", ""]
        for r in failures:
            bad = [f"{n} ({s['detail']})" for n, s in r.scores.items() if not s["passed"]]
            lines.append(f"### {r.scenario} #{r.attempt}")
            if r.error:
                lines.append(f"- error: `{r.error}`")
            if r.report:
                rc = r.report["root_cause"]
                lines.append(
                    f"- said: [{rc['category']}, {rc['confidence']:.2f}] {rc['hypothesis']}"
                )
                lines.append(f"- caused_by_latest_deploy: {r.report['caused_by_latest_deploy']}")
            lines.append(f"- failing: {'; '.join(bad)}")
            if r.failed_specialists:
                lines.append(f"- failed specialists: {', '.join(r.failed_specialists)}")
            lines.append(f"- trace: `{r.trace_file}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--k", type=int, default=1, help="Attempts per scenario")
    parser.add_argument("--scenarios", help="Comma-separated subset (default: all)")
    parser.add_argument("--no-critic", action="store_true")
    parser.add_argument("--judge", action="store_true", help="Add LLM-as-judge scores")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()

    settings = Settings.from_env()
    scenarios = args.scenarios.split(",") if args.scenarios else available_scenarios()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    out_dir = args.out / stamp
    meta = {
        "timestamp": stamp,
        "model": settings.llm_model,
        "base_url": settings.llm_base_url,
        "reasoning_effort": settings.llm_reasoning_effort,
        "k": args.k,
        "critic": not args.no_critic,
        "judge": args.judge,
        "scenarios": scenarios,
    }

    def progress(r: RunRecord) -> None:
        status = "PASS" if r.passed else "FAIL"
        failing = [n for n, s in r.scores.items() if not s["passed"]]
        print(
            f"{status} {r.scenario} #{r.attempt} ({r.elapsed_s:.0f}s) {' '.join(failing)}",
            flush=True,
        )

    out_dir.mkdir(parents=True, exist_ok=True)

    def save(records: list[RunRecord]) -> None:
        (out_dir / "results.json").write_text(
            json.dumps({"meta": meta, "runs": [asdict(r) for r in records]}, indent=2)
        )

    done: list[RunRecord] = []

    def on_record(r: RunRecord) -> None:
        done.append(r)
        save(done)  # an interrupted suite keeps every finished run
        progress(r)

    def on_stop(reason: str) -> None:
        meta["stopped"] = reason
        print(reason, flush=True)

    records = asyncio.run(
        run_suite(
            scenarios,
            args.k,
            make_llm(settings),
            settings,
            out_dir,
            use_critic=not args.no_critic,
            use_judge=args.judge,
            on_record=on_record,
            on_stop=on_stop,
        )
    )
    save(records)
    if not records:
        print("No runs completed.")
        return
    summary = summarize(records, meta)
    (out_dir / "summary.md").write_text(summary)
    print("\n" + summary)
    print(f"Saved to {out_dir}")


if __name__ == "__main__":
    main()
