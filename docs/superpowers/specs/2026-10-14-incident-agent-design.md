# Mini Agentic Incident Investigator - Design

Date: 2026-10-14

## Goal

A small multi-agent system that investigates a production incident report (e.g. "my service
started returning HTTP 500s after the latest deployment") using tools exposed by an MCP server,
and returns a structured report: evidence, probable root cause, and recommended next steps.

It is a take-home exercise. Reviewers value the engineering thought process over polish, so the
code must be easy to read and explain, and the README must document decisions and trade-offs.

The system is general-purpose for service incidents (errors, latency, crash loops, expired
certs, upstream failures), not specific to HTTP 500s.

## Decisions

| Decision | Choice | Why | Alternatives |
|---|---|---|---|
| Language | Python 3.12+, `uv` | Best MCP + LLM SDK support | TypeScript |
| LLM access | `openai` SDK against any OpenAI-compatible endpoint | One client works for Ollama (local, free), Groq/Gemini free tiers, OpenAI | Anthropic SDK, LiteLLM |
| Default model | Ollama `qwen3:8b` locally | Free, no key, offline, decent tool calling | Groq Llama 3.3 70B (free key) |
| Orchestration | Custom asyncio orchestrator | Every step explicit and explainable; full control of prompts for small models; no framework magic | LangGraph (best framework option; future path), OpenAI Agents SDK, CrewAI |
| Tools | MCP server (official `mcp` SDK, FastMCP) | Required; decouples tools from agents | Direct function calls |
| Transport | stdio (default, subprocess) + Streamable HTTP (Docker) | stdio is simplest locally; HTTP for networked deployment | SSE (deprecated) |

Config via env: `LLM_BASE_URL` (default `http://localhost:11434/v1`), `LLM_MODEL`
(default `incident-qwen3`, i.e. qwen3:8b with a 16k context via `ollama/Modelfile`, because
Ollama's 4k default silently truncates agent conversations), `LLM_API_KEY` (default `ollama`),
`LLM_REASONING_EFFORT` (default `none`), `LLM_MAX_CONCURRENCY` (default 1). The scripted FakeLLM
is test-only and injected directly, not selected by env.

## Architecture

```
user report
   │
   ▼
Triage agent ── classifies incident type, extracts service + time hint,
   │            chooses which specialists to run (may call list_services)
   ▼  asyncio.gather (parallel)
┌────────────┬──────────────────┬──────────────┬─────────────┐
│ Logs agent │ Change agent     │ Metrics agent│ Docs agent  │
│ search_logs│ get_recent_deploy│ get_metrics  │ search_docs │
│ get_error_ │ get_deployment_  │              │             │
│ summary    │ diff             │              │             │
└────────────┴──────────────────┴──────────────┴─────────────┘
   │  each returns Findings JSON (claims citing evidence IDs)
   ▼
Synthesizer ── merges findings into IncidentReport
   ▼
Critic ── checks report vs evidence ledger; on failure, 1 revision round of Synthesizer
   ▼
IncidentReport (JSON + rendered markdown) + trace file
```

### Agent primitive

An agent = system prompt + tool allowlist + output Pydantic model, run by a shared loop in
`agents/base.py`:

1. Send messages + allowed tool schemas (converted from MCP `list_tools`) to the LLM.
2. If the model returns tool calls, execute them via the MCP client session, record each
   result in the **evidence ledger** with an ID (`E1`, `E2`, ...), append the result (prefixed
   with its ID) as a tool message, loop.
3. When the model returns final content, parse JSON into the output model. On validation error,
   send the error back once for repair.
4. Hard cap on iterations (default 6 tool rounds). On cap, force a final answer with
   `tool_choice="none"`.

Triage, Synthesizer and Critic have no tools (pure reasoning over provided context).

### Evidence ledger and grounding

The orchestrator owns a shared `EvidenceLedger` (id -> tool name, args, output text).
Specialists cite evidence IDs in their findings. The final report's evidence items must cite
IDs. Grounding is checkable mechanically: cited ID exists, and the critic plus the eval scorer
verify that key tokens of the claim appear in the cited output.

### Schemas (`schemas.py`)

- `TriageResult`: incident_type, service, time_hint, specialists[], rationale
- `Finding`: claim, evidence_ids[], significance (high/medium/low)
- `SpecialistReport`: agent, findings[], summary
- `IncidentReport`:
  - summary
  - incident_type
  - affected_services[]
  - evidence[]: {evidence_id, source, detail}
  - root_cause: {hypothesis, category, confidence 0-1}
  - category enum: `bad_config`, `schema_migration`, `code_bug`, `performance_regression`,
    `resource_exhaustion`, `dependency_failure`, `certificate_expiry`, `unknown`
  - caused_by_latest_deploy: bool | null
  - alternatives_ruled_out[]
  - next_steps[]: {action, priority P0-P2, rationale}
  - open_questions[]
- `CriticVerdict`: approved, issues[]

## MCP server

`mcp_server/server.py`, FastMCP. Loads one scenario world from
`mcp_server/scenarios/<SCENARIO>/` (env `SCENARIO` or `--scenario`).

Scenario files: `services.json`, `deployments.json` (with diffs: commits, files, config
changes), `logs.jsonl`, `metrics.json` (time series per service/metric), `docs/*.md`,
`incident.txt` (the user report), `expected.json` (ground truth, never exposed via tools).

Tools:
- `list_services()`
- `get_recent_deployments(service, limit=5)`
- `get_deployment_diff(deploy_id)`
- `search_logs(service, query="", level=None, since=None, until=None, limit=50)`
- `get_error_summary(service, around=None)` - error signatures with counts before/after a
  timestamp (defaults to latest deploy time)
- `get_metrics(service, metric)` - error_rate, latency_p99_ms, memory_mb, restarts, cpu
- `search_docs(query)` - keyword-ranked runbook/architecture snippets

Resources: `runbook://{name}` exposing each doc.

Transports: stdio default; `--transport http --port 8000` for Streamable HTTP.
Client side (`mcp_client.py`) supports both: spawn via `stdio_client` or connect via
`streamablehttp_client` when `MCP_URL` is set.

## Scenarios (eval dataset)

| id | service | truth category | caused_by_latest_deploy | key facts |
|---|---|---|---|---|
| checkout_bad_config | checkout-api | bad_config | true | v2.4.1, env var renamed `DB_POOL_SIZE` -> `DATABASE_POOL_SIZE`, KeyError |
| payments_missing_migration | payments-api | schema_migration | true | column `refund_reason` does not exist, migration not run |
| search_latency_regression | search-api | performance_regression | true | cache removed, p99 latency 120ms -> 2400ms |
| orders_upstream_dependency | orders-api | dependency_failure | false | inventory-service timeouts began before deploy |
| worker_oom_crashloop | report-worker | resource_exhaustion | true | memory limit 1024Mi -> 512Mi, OOMKilled |
| auth_cert_expiry | auth-api | certificate_expiry | false | no recent deploy, TLS cert expired |
| ambiguous_low_signal | profile-api | unknown | null | sparse transient errors; expect low confidence, open questions |

Each has its own `incident.txt`; not all say "500".

## Evals

`evals/runner.py`: for each scenario, run the full pipeline k times (`--k`), each against an
MCP server bound to that scenario. Scorers (`evals/scorers.py`), each returning pass/fail
or a 0-1 score:

1. `schema_valid` - output parsed into IncidentReport
2. `root_cause_category` - matches expected
3. `deploy_attribution` - caused_by_latest_deploy matches expected (null scenario: must not be true)
4. `key_fact_recall` - fraction of expected key facts (case-insensitive substrings) mentioned
5. `citation_grounding` - all cited evidence IDs exist in the ledger and at least one key token
   of each evidence detail appears in the cited output
6. `tool_coverage` - expected tools were called
7. `next_step_relevance` - any expected action keyword present in next_steps
8. `calibration` - ambiguous scenario: confidence <= 0.5; others: confidence >= 0.5 when correct

A run passes if 1-3 pass, recall >= 0.5, and grounding >= 0.8. Report: per-scenario pass rate
over k (pass^k style reliability), mean scores, latency, tool calls, and a list of failures with
the failing scorer and the report excerpt. Output to `evals/results/<timestamp>.{json,md}`.

Optional `--judge`: an LLM judge scores next-step quality 1-5 against the expected rubric.
Off by default since a small local judge is noisy; documented as such.

## Error handling

- LLM calls: retry with exponential backoff (3 attempts) on connection/5xx/rate-limit errors.
- JSON output: strip think tags / code fences, extract JSON, validate; one repair round.
- Tool calls: per-call timeout; tool errors are returned to the model as error text (not
  raised) so it can adapt.
- Specialist failure: caught; recorded as failed in context passed to the synthesizer, which
  must reflect reduced confidence.
- Iteration caps on every loop.

## Observability

`tracing.py`: every run writes `runs/<run_id>.jsonl` with events (agent start/end, LLM call
with latency and token usage, tool call with args/latency/size, validation errors). CLI prints
a compact live view. README describes the production path: OpenTelemetry spans (GenAI
semantic conventions) to a backend such as Langfuse/Phoenix/Honeycomb.

## Testing

- Unit: MCP tool functions against a fixture scenario; JSON extraction/repair; scorers.
- Orchestrator: FakeLLM with scripted responses (tool calls then final JSON) exercises the full
  pipeline deterministically, including a failing-specialist path and critic revision.
- Integration: real MCP server over stdio, list tools, call each.
- CI runs all of the above without network or model.

## Infrastructure

- `Dockerfile` (uv-based, slim), `docker-compose.yml`: `mcp-server` (Streamable HTTP) and
  `agent` (connects via `MCP_URL`, LLM at host Ollama via `host.docker.internal`).
- `.github/workflows/ci.yml`: uv sync, ruff, pytest (includes a FakeLLM end-to-end smoke run
  through the eval runner to validate the harness). The real-model eval suite needs an LLM, so it
  runs manually or on a nightly/`workflow_dispatch` job pointed at a hosted endpoint via secrets.

## CLI

- `uv run investigate "<report>" --scenario checkout_bad_config [--json]`
  (report defaults to the scenario's `incident.txt`)
- `uv run evals [--k 3] [--scenarios a,b] [--judge]`
- `uv run mcp-server --scenario X [--transport http]`

## Out of scope

Real integrations, auth, UI, persistence across runs, human-in-the-loop.
