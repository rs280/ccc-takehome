"""Read-only access to one scenario's mock operational data.

Kept free of MCP concerns so it can be unit-tested directly. Every public method returns plain
JSON-serialisable data; the MCP layer only wraps these.
"""

import json
import re
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path

SCENARIOS_DIR = Path(__file__).parent / "scenarios"
MAX_MESSAGE_CHARS = 300
BASELINE_POINTS = 4  # first 40 minutes of each series
MIN_SEGMENT = 3  # a level change must hold for at least 30 minutes


class WorldError(ValueError):
    """A bad tool argument. The message is shown to the calling agent so it can correct itself."""


def _parse_ts(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise WorldError(
            f"Invalid timestamp {value!r}; use ISO 8601 like 2026-10-14T09:30:00Z"
        ) from e


def _fmt(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _relative(ts: datetime, deploy: dict) -> str:
    """Timing relative to a deploy, in words. Models compare ISO timestamps unreliably."""
    delta = (ts - _parse_ts(deploy["deployed_at"])).total_seconds() / 60
    side = "AFTER" if delta >= 0 else "BEFORE"
    minutes = abs(delta)
    if minutes < 120:
        amount = f"{minutes:.0f} min"
    elif minutes < 48 * 60:
        amount = f"{minutes / 60:.1f} hours"
    else:
        amount = f"{minutes / 1440:.1f} days"
    return f"{amount} {side} latest deploy {deploy['id']} ({deploy['version']})"


def _change_point(points: list[dict]) -> dict | None:
    """Single change-point detection: locate by least squares, judge by medians.

    The split that minimises squared error around each segment's mean lands exactly on a step.
    The change counts only if the segment medians differ by at least 2x, so noisy-but-flat
    series and single outliers (which medians ignore) are not reported as changes.
    """
    values = [p["value"] for p in points]

    def sse(xs: list[float]) -> float:
        mean = statistics.fmean(xs)
        return sum((x - mean) ** 2 for x in xs)

    splits = range(MIN_SEGMENT, len(values) - MIN_SEGMENT + 1)
    if not splits:
        return None
    i = min(splits, key=lambda k: sse(values[:k]) + sse(values[k:]))
    before, after = statistics.median(values[:i]), statistics.median(values[i:])
    ratio = after / before if before else (float("inf") if after > 0 else 1.0)
    if 0.5 < ratio < 2:
        return None
    return {
        "at": points[i]["ts"],
        "median_before": round(before, 2),
        "median_after": round(after, 2),
    }


def _signature(message: str) -> str:
    """Collapse variable parts (ids, numbers) so identical errors group together."""
    return re.sub(r"\d+", "N", message)


class World:
    def __init__(self, root: Path):
        self.root = root
        self.services = json.loads((root / "services.json").read_text())
        self.deployments = json.loads((root / "deployments.json").read_text())
        self.metrics = json.loads((root / "metrics.json").read_text())
        self.logs = [json.loads(line) for line in (root / "logs.jsonl").read_text().splitlines()]
        self.docs = {p.stem: p.read_text() for p in sorted((root / "docs").glob("*.md"))}
        self.incident = (root / "incident.txt").read_text().strip()
        # The world's clock: the mock data covers a fixed window, and "now" is its end.
        stamps = [r["ts"] for r in self.logs] + [
            p["ts"] for svc in self.metrics.values() for m in svc.values() for p in m["points"]
        ]
        self.window_start, self.now = _parse_ts(min(stamps)), _parse_ts(max(stamps))

    @classmethod
    def load(cls, scenario: str) -> "World":
        root = SCENARIOS_DIR / scenario
        if not root.is_dir():
            available = ", ".join(available_scenarios())
            raise WorldError(f"Unknown scenario {scenario!r}. Available: {available}")
        return cls(root)

    def _check_service(self, service: str) -> None:
        names = [s["name"] for s in self.services]
        if service not in names:
            raise WorldError(f"Unknown service {service!r}. Known services: {', '.join(names)}")

    def list_services(self) -> list[dict]:
        return self.services

    def get_recent_deployments(self, service: str | None = None, limit: int = 5) -> list[dict]:
        if service:
            self._check_service(service)
        deps = [d for d in self.deployments if not service or d["service"] == service]
        deps.sort(key=lambda d: d["deployed_at"], reverse=True)
        return [
            {k: v for k, v in d.items() if k != "diff"}
            | {
                "hours_before_now": round(
                    (self.now - _parse_ts(d["deployed_at"])).total_seconds() / 3600, 1
                )
            }
            for d in deps[:limit]
        ]

    def get_deployment_diff(self, deploy_id: str) -> dict:
        for d in self.deployments:
            if d["id"] == deploy_id:
                return {
                    "id": d["id"],
                    "service": d["service"],
                    "version": d["version"],
                    **d["diff"],
                }
        ids = ", ".join(d["id"] for d in self.deployments)
        raise WorldError(f"Unknown deploy_id {deploy_id!r}. Known: {ids}")

    def search_logs(
        self,
        service: str,
        query: str = "",
        level: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 20,
    ) -> dict:
        """All whitespace-separated query terms must appear (case-insensitive) in the message."""
        self._check_service(service)
        terms = query.lower().split()
        lo = _parse_ts(since) if since else None
        hi = _parse_ts(until) if until else None
        matches = []
        for r in self.logs:
            if r["service"] != service:
                continue
            if level and r["level"] != level.upper():
                continue
            ts = _parse_ts(r["ts"])
            if (lo and ts < lo) or (hi and ts > hi):
                continue
            if any(t not in r["message"].lower() for t in terms):
                continue
            matches.append(r)
        limit = max(1, min(limit, 50))
        # Most recent first: during an incident the latest lines matter most.
        shown = matches[::-1][:limit]
        return {
            "total_matches": len(matches),
            "returned": len(shown),
            "first_match_ts": matches[0]["ts"] if matches else None,
            "lines": [
                {"ts": r["ts"], "level": r["level"], "message": r["message"][:MAX_MESSAGE_CHARS]}
                for r in shown
            ],
        }

    def get_error_summary(self, service: str, around: str | None = None) -> dict:
        """Group WARN/ERROR lines by signature, with counts before/after a pivot time.

        The pivot defaults to the service's latest deploy: did these errors exist before it? If
        that deploy predates the available logs, a before/after split would put every error
        "after the deploy" and falsely implicate it, so we report plain counts and say why.
        """
        self._check_service(service)
        lines = [
            r for r in self.logs if r["service"] == service and r["level"] in ("WARN", "ERROR")
        ]
        pivot, note = None, None
        deps = self.get_recent_deployments(service, limit=1)
        if around:
            pivot = _parse_ts(around)
        elif deps:
            deployed = _parse_ts(deps[0]["deployed_at"])
            if deployed >= self.window_start:
                pivot, note = (
                    deployed,
                    f"Split on latest deploy {deps[0]['id']} ({deps[0]['version']}).",
                )
            else:
                note = (
                    f"Latest deploy {deps[0]['id']} at {deps[0]['deployed_at']} is before the "
                    f"earliest available log ({_fmt(self.window_start)}), so logs cannot show "
                    "whether these errors predate it. Use first_seen to date each error."
                )
        else:
            note = "No deployments recorded for this service."

        groups: dict[str, dict] = {}
        for r in lines:
            sig = _signature(r["message"])[:MAX_MESSAGE_CHARS]
            g = groups.setdefault(
                sig,
                {
                    "level": r["level"],
                    "example": r["message"][:MAX_MESSAGE_CHARS],
                    "count": 0,
                    "first_seen": r["ts"],
                    "last_seen": r["ts"],
                },
            )
            g["count"] += 1
            g["last_seen"] = r["ts"]
            if deps and g["count"] == 1:
                g["first_seen_vs_latest_deploy"] = _relative(_parse_ts(r["ts"]), deps[0])
            if pivot is not None:
                key = "after_pivot" if _parse_ts(r["ts"]) >= pivot else "before_pivot"
                g[key] = g.get(key, 0) + 1
        ordered = sorted(groups.values(), key=lambda g: (g["level"] != "ERROR", -g["count"]))
        return {
            "pivot": _fmt(pivot) if pivot else None,
            "note": note,
            "log_window": [_fmt(self.window_start), _fmt(self.now)],
            "groups": ordered[:10],
        }

    def get_metrics(self, service: str, metric: str) -> dict:
        self._check_service(service)
        available = sorted(self.metrics.get(service, {}))
        if metric not in available:
            raise WorldError(
                f"No metric {metric!r} for {service}. Available: {', '.join(available) or 'none'}"
            )
        series = self.metrics[service][metric]
        values = [p["value"] for p in series["points"]]
        change = _change_point(series["points"])
        if change and (deps := self.get_recent_deployments(service, limit=1)):
            change["vs_latest_deploy"] = _relative(_parse_ts(change["at"]), deps[0])
        # No "baseline vs latest" fields: two hand-picked points invite reading noise as a trend.
        return {
            "service": service,
            "metric": metric,
            "unit": series["unit"],
            "change": change or "no significant change in level (variation is within normal noise)",
            "summary": {
                "min": min(values),
                "median": round(statistics.median(values), 3),
                "max": max(values),
            },
            "points": series["points"],
        }

    def search_docs(self, query: str, limit: int = 3) -> list[dict]:
        terms = [t for t in re.findall(r"[a-z0-9_]+", query.lower()) if len(t) > 2]
        if not terms:
            raise WorldError("Query must contain at least one word of 3+ characters")
        scored = []
        for name, text in self.docs.items():
            hay = (name + " " + text).lower()
            counts = Counter(t for t in terms if t in hay)
            score = sum(1 + hay.count(t) * 0.1 for t in counts)
            if score:
                scored.append((score, name, text))
        scored.sort(reverse=True)
        return [{"doc": name, "content": text} for _, name, text in scored[:limit]]

    def read_doc(self, name: str) -> str:
        if name not in self.docs:
            raise WorldError(f"Unknown doc {name!r}. Known: {', '.join(self.docs)}")
        return self.docs[name]


def available_scenarios() -> list[str]:
    return sorted(p.name for p in SCENARIOS_DIR.iterdir() if (p / "logs.jsonl").exists())
