"""Generate the mock "worlds" the MCP server serves, one directory per eval scenario.

Logs and metrics are synthetic, so they are generated deterministically from a compact spec per
scenario instead of being hand-written. Each world contains realistic noise (unrelated warnings,
deploys of other services) so agents have to separate signal from noise.

Run: uv run python scripts/gen_scenarios.py
"""

import json
import random
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src/incident_agent/mcp_server/scenarios"
DOCS_SRC = Path(__file__).resolve().parent / "docs"

START = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)
END = datetime(2026, 10, 14, 11, 0, tzinfo=UTC)
METRIC_STEP = timedelta(minutes=10)


def at(hhmm: str, day: int = 14) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 10, day, h, m, tzinfo=UTC)


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class World:
    name: str
    incident: str
    services: list[dict]
    deployments: list[dict]
    expected: dict
    docs: list[str]
    logs: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    rng: random.Random = field(default_factory=lambda: random.Random(7))

    def log(self, t: datetime, service: str, level: str, message: str, **extra) -> None:
        self.logs.append(
            {"ts": iso(t), "service": service, "level": level, "message": message} | extra
        )

    def stream(self, service, start, end, every_s, level, messages, jitter=0.5, **extra):
        """Emit log lines at a roughly fixed rate between start and end, cycling through messages."""
        t, i = start, 0
        while t < end:
            msg = messages[i % len(messages)]
            msg = msg.format(n=self.rng.randint(1000, 9999), ms=self.rng.randint(40, 180))
            self.log(t, service, level, msg, **extra)
            t += timedelta(seconds=every_s * (1 + self.rng.uniform(-jitter, jitter)))
            i += 1

    def series(self, service, metric, base, changes=(), noise=0.05, unit=""):
        """Step-function time series: `changes` is [(time, new_value)], with multiplicative noise."""
        points, t = [], START
        while t <= END:
            value = base
            for when, new in changes:
                if t >= when:
                    value = new
            value = value * (1 + self.rng.uniform(-noise, noise))
            points.append({"ts": iso(t), "value": round(value, 3)})
            t += METRIC_STEP
        self.metrics.setdefault(service, {})[metric] = {"unit": unit, "points": points}

    def baseline_metrics(self, service, error_rate=0.2, p99=150, mem=400, cpu=35):
        self.series(service, "error_rate", error_rate, unit="% of requests")
        self.series(service, "latency_p99_ms", p99, unit="ms")
        self.series(service, "memory_mb", mem, unit="MB")
        self.series(service, "cpu_pct", cpu, unit="%")
        self.series(service, "restarts", 0, noise=0, unit="count per 10m")

    def background(self, service, path):
        """Healthy traffic and the usual harmless warnings every service has."""
        self.stream(service, START, END, 240, "INFO", [f"GET {path} 200 in {{ms}}ms"])
        self.stream(
            service,
            START,
            END,
            1500,
            "WARN",
            [
                "Slow request GET /healthz took 1{n}ms",
                "Retrying metrics push to collector (attempt 1)",
            ],
        )


def deploy(
    dep_id,
    service,
    version,
    t,
    author,
    summary,
    commits,
    files,
    config_changes=(),
    pipeline=None,
    status="succeeded",
):
    return {
        "id": dep_id,
        "service": service,
        "version": version,
        "deployed_at": iso(t),
        "author": author,
        "status": status,
        "summary": summary,
        "diff": {
            "commits": commits,
            "files_changed": files,
            "config_changes": list(config_changes),
            "pipeline_steps": pipeline
            or [
                {"name": "build", "status": "passed"},
                {"name": "unit-tests", "status": "passed"},
                {"name": "deploy", "status": "passed"},
            ],
        },
    }


SERVICES = [
    {
        "name": "checkout-api",
        "owner": "team-payments",
        "tier": 1,
        "depends_on": ["payments-api", "inventory-service", "postgres-checkout"],
    },
    {
        "name": "payments-api",
        "owner": "team-payments",
        "tier": 1,
        "depends_on": ["postgres-payments"],
    },
    {
        "name": "orders-api",
        "owner": "team-fulfilment",
        "tier": 1,
        "depends_on": ["inventory-service"],
    },
    {
        "name": "inventory-service",
        "owner": "team-fulfilment",
        "tier": 1,
        "depends_on": ["postgres-inventory"],
    },
    {
        "name": "search-api",
        "owner": "team-discovery",
        "tier": 2,
        "depends_on": ["elasticsearch", "redis-search-cache"],
    },
    {
        "name": "report-worker",
        "owner": "team-data",
        "tier": 3,
        "depends_on": ["postgres-analytics"],
    },
    {"name": "auth-api", "owner": "team-identity", "tier": 0, "depends_on": ["identity-provider"]},
    {
        "name": "profile-api",
        "owner": "team-identity",
        "tier": 2,
        "depends_on": ["postgres-profile", "avatar-cdn"],
    },
    {"name": "frontend-web", "owner": "team-web", "tier": 1, "depends_on": ["checkout-api"]},
]

NOISE_DEPLOY = deploy(
    "dep-7710",
    "frontend-web",
    "v9.3.0",
    at("09:30"),
    "lena.k",
    "Update footer links and analytics snippet",
    ["chore: update footer links", "feat: add consent banner analytics"],
    ["web/components/Footer.tsx", "web/analytics.ts"],
)


def checkout_bad_config() -> World:
    w = World(
        "checkout_bad_config",
        "My service checkout-api started returning HTTP 500 errors after the latest deployment. "
        "Help me investigate the issue and recommend the next steps.",
        SERVICES,
        [
            deploy(
                "dep-7702",
                "checkout-api",
                "v2.4.0",
                at("15:10", day=9),
                "sam.o",
                "Add gift card support",
                ["feat: gift card redemption"],
                ["app/giftcards.py", "tests/test_giftcards.py"],
            ),
            NOISE_DEPLOY,
            deploy(
                "dep-7715",
                "checkout-api",
                "v2.4.1",
                at("10:02"),
                "sam.o",
                "Refactor config loading",
                [
                    "refactor: unify database settings under DATABASE_ prefix",
                    "chore: read DATABASE_POOL_SIZE instead of DB_POOL_SIZE",
                ],
                ["app/config/settings.py", "app/db/pool.py"],
                config_changes=[],
            ),
        ],
        {
            "category": "bad_config",
            "acceptable_categories": ["bad_config", "code_bug"],
            "caused_by_latest_deploy": True,
            "key_facts": ["v2.4.1", "DATABASE_POOL_SIZE"],
            "expected_tools": [
                "get_recent_deployments",
                "get_deployment_diff",
                "search_logs|get_error_summary",
            ],
            "next_step_keywords": ["roll back", "rollback", "revert", "DATABASE_POOL_SIZE"],
            "reference_answer": "v2.4.1 (dep-7715, 10:02) changed code to read DATABASE_POOL_SIZE but the deployment still only sets DB_POOL_SIZE, so POST /api/checkout raises KeyError and returns 500. Roll back to v2.4.0 or set DATABASE_POOL_SIZE, then add config validation at startup.",
        },
        ["http-5xx-triage", "rollback", "config-management", "checkout-architecture"],
    )
    for s, p in [
        ("checkout-api", "/api/cart"),
        ("frontend-web", "/"),
        ("payments-api", "/v1/payments"),
    ]:
        w.background(s, p)
    w.log(at("10:02"), "checkout-api", "INFO", "Starting checkout-api v2.4.1 (pid 1)")
    w.stream(
        "checkout-api",
        at("10:03"),
        END,
        25,
        "ERROR",
        [
            "Unhandled exception in POST /api/checkout: KeyError: 'DATABASE_POOL_SIZE' "
            "(app/config/settings.py:41 in get_pool_settings) -> 500",
        ],
    )
    w.stream(
        "frontend-web",
        at("10:04"),
        END,
        90,
        "WARN",
        ["Upstream checkout-api returned 500 for POST /api/checkout"],
    )
    w.baseline_metrics("frontend-web")
    w.baseline_metrics("payments-api")
    w.series("checkout-api", "error_rate", 0.2, [(at("10:10"), 38.0)], unit="% of requests")
    w.series("checkout-api", "latency_p99_ms", 180, unit="ms")
    w.series("checkout-api", "memory_mb", 520, unit="MB")
    w.series("checkout-api", "cpu_pct", 30, unit="%")
    w.series("checkout-api", "restarts", 0, noise=0, unit="count per 10m")
    return w


def payments_missing_migration() -> World:
    w = World(
        "payments_missing_migration",
        "payments-api is throwing 500s since this morning's release, only for refunds as far as "
        "we can tell. What is going on?",
        SERVICES,
        [
            deploy(
                "dep-7690",
                "payments-api",
                "v3.7.2",
                at("11:00", day=7),
                "ari.m",
                "Fix currency rounding",
                ["fix: round JPY amounts"],
                ["payments/currency.py"],
            ),
            NOISE_DEPLOY,
            deploy(
                "dep-7712",
                "payments-api",
                "v3.8.0",
                at("09:40"),
                "ari.m",
                "Store refund reasons",
                [
                    "feat: capture refund_reason on refunds",
                    "db: add migration 0042_add_refund_reason",
                ],
                [
                    "payments/models/refund.py",
                    "payments/api/refunds.py",
                    "migrations/0042_add_refund_reason.py",
                ],
                pipeline=[
                    {"name": "build", "status": "passed"},
                    {"name": "unit-tests", "status": "passed"},
                    {
                        "name": "db-migrate",
                        "status": "skipped",
                        "note": "requires manual approval; not approved",
                    },
                    {"name": "deploy", "status": "passed"},
                ],
            ),
        ],
        {
            "category": "schema_migration",
            "acceptable_categories": ["schema_migration"],
            "caused_by_latest_deploy": True,
            "key_facts": ["refund_reason", "0042"],
            "expected_tools": [
                "get_recent_deployments",
                "get_deployment_diff",
                "search_logs|get_error_summary",
            ],
            "next_step_keywords": ["migration", "migrate", "roll back", "rollback"],
            "reference_answer": "v3.8.0 (dep-7712, 09:40) ships code writing refunds.refund_reason, but the db-migrate step (0042_add_refund_reason) was skipped pending approval, so POST /v1/refunds fails with UndefinedColumn. Approve and run the migration (or roll back), and make skipped migrations block deploys.",
        },
        ["http-5xx-triage", "rollback", "database-migrations"],
    )
    for s, p in [("payments-api", "/v1/payments"), ("checkout-api", "/api/cart")]:
        w.background(s, p)
    w.log(at("09:40"), "payments-api", "INFO", "Starting payments-api v3.8.0 (pid 1)")
    w.stream(
        "payments-api",
        at("09:41"),
        END,
        70,
        "ERROR",
        [
            'POST /v1/refunds failed: psycopg.errors.UndefinedColumn: column "refund_reason" of '
            'relation "refunds" does not exist -> 500',
        ],
    )
    w.stream(
        "payments-api", START, END, 2400, "WARN", ["Card network latency elevated for issuer 4{n}"]
    )
    w.baseline_metrics("checkout-api")
    w.series("payments-api", "error_rate", 0.1, [(at("09:50"), 6.5)], unit="% of requests")
    w.series("payments-api", "latency_p99_ms", 210, unit="ms")
    w.series("payments-api", "memory_mb", 610, unit="MB")
    w.series("payments-api", "cpu_pct", 40, unit="%")
    w.series("payments-api", "restarts", 0, noise=0, unit="count per 10m")
    return w


def search_latency_regression() -> World:
    w = World(
        "search_latency_regression",
        "Search has been really slow since this morning and some requests are timing out. "
        "Can you figure out why?",
        SERVICES,
        [
            deploy(
                "dep-7680",
                "search-api",
                "v5.1.4",
                at("16:20", day=6),
                "noor.b",
                "Tune synonym dictionary",
                ["chore: update synonyms"],
                ["search/synonyms.txt"],
            ),
            deploy(
                "dep-7709",
                "search-api",
                "v5.2.0",
                at("09:15"),
                "noor.b",
                "Remove legacy result cache",
                ["chore: remove legacy redis result cache", "refactor: query path simplification"],
                ["search/cache.py (deleted)", "search/query.py"],
                config_changes=[{"key": "REDIS_CACHE_ENABLED", "old": "true", "new": "false"}],
            ),
            NOISE_DEPLOY,
        ],
        {
            "category": "performance_regression",
            "acceptable_categories": ["performance_regression"],
            "caused_by_latest_deploy": True,
            "key_facts": ["v5.2.0", "cache"],
            "expected_tools": ["get_metrics", "get_recent_deployments", "get_deployment_diff"],
            "next_step_keywords": ["roll back", "rollback", "revert", "cache"],
            "reference_answer": "v5.2.0 (dep-7709, 09:15) removed the Redis result cache (REDIS_CACHE_ENABLED=false); all queries now hit elasticsearch, p99 went from ~120ms to ~2400ms with 504 timeouts. Roll back or re-enable the cache; load-test before removing caches.",
        },
        ["latency-triage", "rollback", "search-architecture"],
    )
    w.background("search-api", "/search")
    w.background("frontend-web", "/")
    w.log(
        at("09:15"),
        "search-api",
        "INFO",
        "Starting search-api v5.2.0 (pid 1); result cache: disabled",
    )
    w.stream(
        "search-api",
        at("09:16"),
        END,
        60,
        "WARN",
        ["Slow query: elasticsearch took 2{n}ms for q='...' (cache miss)"],
    )
    w.stream(
        "search-api", at("09:30"), END, 200, "ERROR", ["GET /search timed out after 3000ms -> 504"]
    )
    w.baseline_metrics("frontend-web")
    w.series("search-api", "latency_p99_ms", 120, [(at("09:20"), 2400)], unit="ms")
    w.series("search-api", "error_rate", 0.1, [(at("09:30"), 3.2)], unit="% of requests")
    w.series("search-api", "cpu_pct", 25, [(at("09:20"), 70)], unit="%")
    w.series("search-api", "memory_mb", 900, [(at("09:20"), 700)], unit="MB")
    w.series("search-api", "restarts", 0, noise=0, unit="count per 10m")
    return w


def orders_upstream_dependency() -> World:
    w = World(
        "orders_upstream_dependency",
        "orders-api started returning HTTP 500 errors after the latest deployment. "
        "Please investigate and tell us whether we should roll back.",
        SERVICES,
        [
            deploy(
                "dep-7685",
                "orders-api",
                "v1.9.2",
                at("13:00", day=8),
                "kai.r",
                "Add order notes",
                ["feat: order notes"],
                ["orders/notes.py"],
            ),
            deploy(
                "dep-7716",
                "orders-api",
                "v1.9.3",
                at("10:10"),
                "kai.r",
                "Bump logging library",
                ["chore(deps): bump structlog 24.1 -> 24.4"],
                ["pyproject.toml", "uv.lock"],
            ),
            NOISE_DEPLOY,
        ],
        {
            "category": "dependency_failure",
            "acceptable_categories": ["dependency_failure"],
            "caused_by_latest_deploy": False,
            "key_facts": ["inventory-service", "pool"],
            "expected_tools": [
                "search_logs|get_error_summary",
                "get_recent_deployments",
                "get_metrics",
            ],
            "next_step_keywords": ["inventory"],
            "reference_answer": "inventory-service exhausted its database connection pool from 09:18, so orders-api calls to it time out (5000ms) and return 500 from 09:20. The orders-api v1.9.3 deploy at 10:10 came after the errors began and only bumped a logging library; do not roll back. Escalate to team-fulfilment for inventory-service, add a circuit breaker/fallback in orders-api.",
        },
        ["http-5xx-triage", "rollback", "dependency-failures", "orders-architecture"],
    )
    for s, p in [("orders-api", "/orders"), ("inventory-service", "/stock")]:
        w.background(s, p)
    w.stream(
        "inventory-service",
        at("09:18"),
        END,
        45,
        "ERROR",
        [
            "Database connection pool exhausted (max=20, waiting=57); request aborted after 5000ms",
        ],
    )
    w.stream(
        "orders-api",
        at("09:20"),
        END,
        30,
        "ERROR",
        [
            "GET /orders/{n} failed: upstream inventory-service timeout after 5000ms -> 500",
        ],
    )
    w.log(at("10:10"), "orders-api", "INFO", "Starting orders-api v1.9.3 (pid 1)")
    w.series("orders-api", "error_rate", 0.2, [(at("09:20"), 22.0)], unit="% of requests")
    w.series("orders-api", "latency_p99_ms", 200, [(at("09:20"), 5100)], unit="ms")
    w.series("orders-api", "memory_mb", 450, unit="MB")
    w.series("orders-api", "cpu_pct", 20, unit="%")
    w.series("orders-api", "restarts", 0, noise=0, unit="count per 10m")
    w.series("inventory-service", "error_rate", 0.1, [(at("09:20"), 31.0)], unit="% of requests")
    w.series("inventory-service", "latency_p99_ms", 90, [(at("09:20"), 5000)], unit="ms")
    w.series(
        "inventory-service", "db_connections_in_use", 8, [(at("09:20"), 20)], noise=0, unit="conns"
    )
    w.series("inventory-service", "cpu_pct", 30, unit="%")
    w.series("inventory-service", "restarts", 0, noise=0, unit="count per 10m")
    return w


def worker_oom_crashloop() -> World:
    w = World(
        "worker_oom_crashloop",
        "Report generation jobs keep failing and the report-worker pod keeps restarting since "
        "this morning. Can you investigate?",
        SERVICES,
        [
            deploy(
                "dep-7660",
                "report-worker",
                "v0.13.5",
                at("10:00", day=1),
                "mei.l",
                "CSV export tweaks",
                ["fix: csv quoting"],
                ["worker/export.py"],
            ),
            deploy(
                "dep-7711",
                "report-worker",
                "v0.14.0",
                at("09:50"),
                "mei.l",
                "Right-size worker resources",
                ["chore: right-size worker resources", "feat: larger default batch size"],
                ["deploy/values.yaml", "worker/config.py"],
                config_changes=[
                    {"key": "resources.limits.memory", "old": "1024Mi", "new": "512Mi"},
                    {"key": "BATCH_SIZE", "old": "2000", "new": "5000"},
                ],
            ),
            NOISE_DEPLOY,
        ],
        {
            "category": "resource_exhaustion",
            "acceptable_categories": ["resource_exhaustion", "bad_config"],
            "caused_by_latest_deploy": True,
            "key_facts": ["512Mi", "OOMKilled"],
            "expected_tools": ["get_recent_deployments", "get_deployment_diff", "get_metrics"],
            "next_step_keywords": ["memory", "1024", "roll back", "rollback", "revert"],
            "reference_answer": "v0.14.0 (dep-7711, 09:50) lowered the memory limit from 1024Mi to 512Mi while raising BATCH_SIZE from 2000 to 5000; the worker is OOMKilled (exit 137) and crash-loops. Restore the 1024Mi limit (or roll back / reduce batch size), then right-size from observed peak.",
        },
        ["crashloop-triage", "rollback", "kubernetes-resources"],
    )
    w.stream(
        "report-worker", START, at("09:50"), 300, "INFO", ["Processed batch of 2000 rows in {ms}s"]
    )
    t = at("09:51")
    while t < END:
        w.log(t, "report-worker", "INFO", "Starting report-worker v0.14.0; BATCH_SIZE=5000")
        w.log(
            t + timedelta(seconds=40),
            "report-worker",
            "INFO",
            "Loading batch of 5000 rows into memory",
        )
        w.log(
            t + timedelta(minutes=3),
            "report-worker",
            "ERROR",
            "Container report-worker terminated: OOMKilled (exit code 137), memory limit 512Mi",
        )
        w.log(
            t + timedelta(minutes=3, seconds=5),
            "report-worker",
            "WARN",
            "Back-off restarting failed container report-worker (CrashLoopBackOff)",
        )
        t += timedelta(minutes=7)
    w.series("report-worker", "memory_mb", 610, [(at("09:50"), 508)], noise=0.02, unit="MB")
    w.series("report-worker", "restarts", 0, [(at("10:00"), 3)], noise=0, unit="count per 10m")
    w.series("report-worker", "cpu_pct", 45, unit="%")
    w.series("report-worker", "error_rate", 0.0, [(at("10:00"), 100.0)], noise=0, unit="% of jobs")
    return w


def auth_cert_expiry() -> World:
    w = World(
        "auth_cert_expiry",
        "Login is failing for everyone, users are getting 500 errors from auth-api. "
        "Did something get deployed?",
        SERVICES,
        [
            deploy(
                "dep-7701",
                "auth-api",
                "v4.2.0",
                at("14:30", day=8),
                "jo.p",
                "Add WebAuthn support",
                ["feat: webauthn registration"],
                ["auth/webauthn.py"],
            ),
            NOISE_DEPLOY,
        ],
        {
            "category": "certificate_expiry",
            "acceptable_categories": ["certificate_expiry"],
            "caused_by_latest_deploy": False,
            "key_facts": ["expired", "certificate"],
            "expected_tools": ["search_logs|get_error_summary", "get_recent_deployments"],
            "next_step_keywords": ["renew", "rotate", "certificate", "cert"],
            "reference_answer": "The auth-api mTLS client certificate auth-api-idp-mtls expired at 10:00 because cert-manager renewal failed (issuer internal-ca unreachable); TLS to identity-provider fails and login returns 500. No deploy since Oct 8. Restore issuer connectivity, force renewal, restart pods, add expiry alerting.",
        },
        ["http-5xx-triage", "certificate-rotation", "auth-architecture"],
    )
    w.background("auth-api", "/session")
    w.log(
        at("08:00"),
        "auth-api",
        "WARN",
        "cert-manager: client certificate 'auth-api-idp-mtls' expires at 2026-10-14T10:00:00Z "
        "(renewal failed: issuer 'internal-ca' unreachable)",
    )
    w.log(
        at("09:00"),
        "auth-api",
        "WARN",
        "cert-manager: client certificate 'auth-api-idp-mtls' expires in 60m; renewal still failing",
    )
    w.stream(
        "auth-api",
        at("10:00"),
        END,
        15,
        "ERROR",
        [
            "POST /login failed: identity-provider TLS handshake error: "
            "SSL: CERTIFICATE_VERIFY_FAILED certificate has expired (client cert auth-api-idp-mtls) -> 500",
        ],
    )
    w.series("auth-api", "error_rate", 0.3, [(at("10:00"), 97.0)], unit="% of requests")
    w.series("auth-api", "latency_p99_ms", 140, unit="ms")
    w.series("auth-api", "memory_mb", 380, unit="MB")
    w.series("auth-api", "cpu_pct", 22, unit="%")
    w.series("auth-api", "restarts", 0, noise=0, unit="count per 10m")
    return w


def ambiguous_low_signal() -> World:
    w = World(
        "ambiguous_low_signal",
        "Some users say they occasionally see an error on the profile page. Can you check "
        "profile-api?",
        SERVICES,
        [
            deploy(
                "dep-7698",
                "profile-api",
                "v2.0.7",
                at("12:00", day=12),
                "dev.s",
                "Copy changes",
                ["chore: update copy"],
                ["profile/strings.py"],
            ),
            NOISE_DEPLOY,
        ],
        {
            "category": "unknown",
            "acceptable_categories": ["unknown"],
            "caused_by_latest_deploy": None,
            "key_facts": ["ConnectionResetError"],
            "expected_tools": ["search_logs|get_error_summary", "get_metrics"],
            "next_step_keywords": ["monitor", "trac", "more data", "investigate", "reproduce"],
            "reference_answer": "There is no clear incident: sporadic ConnectionResetError/ReadTimeout errors from avatar-cdn at a steady background rate (~0.4%, documented as known and normally below 1%), no recent deploy, no metric change. Root cause undetermined; gather more data (affected users, traces), monitor, and possibly add retries for avatar fetches.",
            "max_confidence": 0.5,
        },
        ["http-5xx-triage", "profile-architecture"],
    )
    w.background("profile-api", "/profile")
    w.stream(
        "profile-api",
        START,
        END,
        1100,
        "ERROR",
        [
            "GET /profile/{n} failed: ConnectionResetError: [Errno 54] Connection reset by peer -> 502",
            "GET /profile/{n}/avatar failed: ReadTimeout after 2000ms -> 504",
        ],
        jitter=0.9,
    )
    w.series("profile-api", "error_rate", 0.4, noise=0.6, unit="% of requests")
    w.series("profile-api", "latency_p99_ms", 260, noise=0.25, unit="ms")
    w.series("profile-api", "memory_mb", 300, unit="MB")
    w.series("profile-api", "cpu_pct", 18, unit="%")
    w.series("profile-api", "restarts", 0, noise=0, unit="count per 10m")
    return w


SCENARIOS = [
    checkout_bad_config,
    payments_missing_migration,
    search_latency_regression,
    orders_upstream_dependency,
    worker_oom_crashloop,
    auth_cert_expiry,
    ambiguous_low_signal,
]


def write(w: World) -> None:
    d = OUT / w.name
    if d.exists():
        shutil.rmtree(d)
    (d / "docs").mkdir(parents=True)
    (d / "incident.txt").write_text(w.incident + "\n")
    (d / "services.json").write_text(json.dumps(w.services, indent=2))
    (d / "deployments.json").write_text(json.dumps(w.deployments, indent=2))
    (d / "metrics.json").write_text(json.dumps(w.metrics, indent=1))
    (d / "expected.json").write_text(json.dumps(w.expected, indent=2))
    w.logs.sort(key=lambda r: r["ts"])
    (d / "logs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in w.logs))
    for doc in w.docs:
        shutil.copy(DOCS_SRC / f"{doc}.md", d / "docs" / f"{doc}.md")


if __name__ == "__main__":
    for make in SCENARIOS:
        world = make()
        write(world)
        print(f"{world.name}: {len(world.logs)} log lines, {len(world.deployments)} deploys")
