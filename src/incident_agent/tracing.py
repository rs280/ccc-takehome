"""Structured run traces: one JSONL file per investigation, plus an optional live console view.

Locally this is enough to debug any run after the fact. In production these events map directly
onto OpenTelemetry spans (see README).
"""

import json
import sys
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


class Tracer:
    def __init__(
        self, runs_dir: str | Path | None = "runs", run_id: str | None = None, verbose: bool = False
    ):
        self.run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%S-") + uuid.uuid4().hex[:6]
        self.path = Path(runs_dir) / f"{self.run_id}.jsonl" if runs_dir else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        self.counts: Counter = Counter()
        self.tokens: Counter = Counter()
        self.started = time.perf_counter()

    def event(self, kind: str, agent: str = "", **data) -> None:
        self.counts[kind] += 1
        if kind == "llm_call":
            self.tokens.update(data.get("usage") or {})
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "run_id": self.run_id,
            "kind": kind,
            "agent": agent,
            **data,
        }
        if self.path:
            with self.path.open("a") as f:
                f.write(json.dumps(record, default=str) + "\n")
        if self.verbose:
            self._print(kind, agent, data)

    def _print(self, kind: str, agent: str, data: dict) -> None:
        if kind == "tool_call":
            status = "ERR" if data.get("is_error") else data.get("evidence_id", "")
            line = f"  [{agent}] -> {data['tool']}({_short(data.get('args'))}) {status}"
        elif kind == "llm_call":
            line = f"  [{agent}] llm {data.get('latency_s', 0):.1f}s"
        elif kind in ("agent_start", "agent_end", "agent_error", "stage"):
            line = f"[{agent or 'orchestrator'}] {kind} {_short(data)}"
        else:
            line = f"  [{agent}] {kind} {_short(data)}"
        print(line, file=sys.stderr)

    def summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "elapsed_s": round(time.perf_counter() - self.started, 2),
            "llm_calls": self.counts["llm_call"],
            "tool_calls": self.counts["tool_call"],
            "tokens": dict(self.tokens),
            "trace_file": str(self.path) if self.path else None,
        }


def _short(value, limit: int = 140) -> str:
    text = json.dumps(value, default=str) if not isinstance(value, str) else value
    return text if len(text) <= limit else text[: limit - 3] + "..."
