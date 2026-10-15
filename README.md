# Mini Agentic Incident Investigator

A small multi-agent system that investigates production incidents ("my service started returning
HTTP 500s after the latest deployment") using tools served by an MCP server, and returns a
structured report: evidence, probable root cause, and recommended next steps.

It is general-purpose for service incidents rather than specific to HTTP 500s. The eval set
includes bad config, missing DB migrations, latency regressions, upstream dependency failures,
OOM crash loops, expired certificates, and an ambiguous low-signal case where the right answer is
"not enough evidence".

```
$ uv run investigate --scenario checkout_bad_config
# Incident report: elevated 5xx errors
...
## Probable root cause
v2.4.1 reads DATABASE_POOL_SIZE but the deployment only sets DB_POOL_SIZE ...
Category: `bad_config`, confidence: 90%
## Evidence
- [E2] (logs) KeyError: 'DATABASE_POOL_SIZE' at settings.py:41, 0 before / 260 after deploy - via `get_error_summary(...)`
...
```

## Quick start

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), and a model. The default is a free
local model through [Ollama](https://ollama.com); any OpenAI-compatible endpoint also works.

```bash
uv sync

# Local model (free, no key). The Modelfile raises Ollama's 4k default context to 16k.
ollama pull qwen3:8b
ollama create incident-qwen3 -f ollama/Modelfile

uv run investigate --scenario checkout_bad_config          # uses the scenario's incident report
uv run investigate "orders-api returns 500s since the deploy" --scenario orders_upstream_dependency
uv run investigate --scenario auth_cert_expiry --json      # machine-readable report

uv run evals                 # eval suite, all 7 scenarios
uv run evals --k 3           # reliability: 3 attempts each
uv run pytest                # tests: no model or network needed
```

Use a hosted free tier instead (much faster than a laptop): copy `.env.example` to `.env` and
uncomment the Groq or Gemini block (`.env` is loaded automatically). See [Configuration](#configuration).

Scenarios: `checkout_bad_config`, `payments_missing_migration`, `search_latency_regression`,
`orders_upstream_dependency`, `worker_oom_crashloop`, `auth_cert_expiry`, `ambiguous_low_signal`.

## 1. Agent architecture

```
incident report
      │
      ▼
 ┌──────────────┐   catalog fetched deterministically by the orchestrator (no LLM call)
 │  Triage      │   → which service, what kind of incident, which specialists to run
 └──────┬───────┘
        ▼   asyncio.gather: specialists run concurrently, each with its own tool allowlist
 ┌────────────┬─────────────────┬──────────────┬─────────────┐
 │ Logs       │ Changes         │ Metrics      │ Docs        │
 │ error_sum- │ recent_deploys  │ get_metrics  │ search_docs │
 │ mary, logs │ deployment_diff │              │             │
 └────────────┴─────────────────┴──────────────┴─────────────┘
        │ findings, each citing evidence IDs (E1, E2, ...)
        ▼
 ┌──────────────┐
 │ Synthesizer  │ → IncidentReport (Pydantic schema)
 └──────┬───────┘
        ▼
 ┌──────────────┐  deterministic checks (citations, deploy timeline) + LLM review
 │ Critic       │──── issues? ──→ Synthesizer revises once
 └──────────────┘
```

**Responsibilities**

| Agent | Tools | Output | Why it exists |
|---|---|---|---|
| Triage | none (catalog in prompt) | `TriageResult` | Maps free text to a real service and a plan. |
| Logs | `get_error_summary`, `search_logs` | `SpecialistReport` | What is failing, since when, before/after deploy. |
| Changes | `get_recent_deployments`, `get_deployment_diff` | `SpecialistReport` | What changed: commits, config, skipped pipeline steps. |
| Metrics | `get_metrics` | `SpecialistReport` | Shape and timing of the impact. |
| Docs | `search_docs` | `SpecialistReport` | Runbook procedures and architecture context. |
| Synthesizer | none | `IncidentReport` | Causal reasoning across findings; owns the final answer. |
| Critic | none | `CriticVerdict` | Catches unsupported claims and timeline errors before the user does. |

**Key design decisions**

- **One agent primitive.** An agent is just `(system prompt, tool allowlist, output schema)`
  ([`agents/base.py`](src/incident_agent/agents/base.py)). A single tool-calling loop runs all of
  them. Adding an agent means writing one prompt and one line in
  [`agents/specs.py`](src/incident_agent/agents/specs.py).
- **Code decides the control flow, models decide what to investigate.** The pipeline order is plain
  Python ([`orchestrator.py`](src/incident_agent/orchestrator.py)). Inside each step, the model
  chooses which tools to call and with what arguments. Runs are predictable and easy to debug and
  evaluate. The cost is that the plan can't change mid-run (for example, a logs finding can't
  trigger a new specialist).
- **Narrow toolsets per specialist.** Small models choose tools much more reliably from 1-2 tools
  than from 7. Each specialist can also be evaluated and improved on its own.
- **Evidence ledger for grounding.** Every tool result gets an ID (`E1`, `E2`, ...) and is stored
  verbatim. Findings and the final report must cite IDs, so whether a claim is grounded can be
  checked mechanically: by the critic before returning, and by the eval scorers afterwards.
  Repeated identical tool calls reuse the existing ID instead of hitting the server again.
- **Structured output everywhere.** Every agent returns JSON validated by Pydantic
  ([`schemas.py`](src/incident_agent/schemas.py)). Invalid output gets exactly one repair round,
  with the validation errors sent back to the model.
- **Graceful degradation.** If a specialist crashes or times out, the synthesizer is told which
  evidence is missing and lowers its confidence. Only "all specialists failed" or "synthesizer
  could not produce a valid report" fails the run.

## 2. Framework selection

**I wrote a small custom orchestrator** (about 150 lines on top of the `openai` and `mcp` SDKs).

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **Custom asyncio** (chosen) | Every prompt, message and retry is visible and controllable; no hidden prompts; easy to explain and debug; tiny dependency footprint; works with any OpenAI-compatible model | Retries, tracing and persistence are mine to write; no built-in checkpointing or human-in-the-loop | Best fit for a small, fixed pipeline where understanding matters most |
| LangGraph | Explicit state graph, checkpointing, interrupts for human approval, LangSmith tracing, MCP adapters | More abstraction and dependencies; LangChain message and tool wrappers sit between my prompts and the model, which makes small-model quirks harder to fix | **What I'd move to next**: once the flow needs loops ("ask logs again"), durable state or human approval |
| OpenAI Agents SDK | Very little code, native MCP, handoffs, tracing | Handoff-driven control flow is decided by the LLM, which is harder to make deterministic and evaluate; leans on OpenAI-specific features | Good for chat-style agents, less so for a fixed investigation pipeline |
| CrewAI / AutoGen | Fast to prototype role-based crews and conversations | Conversation-driven orchestration is costly and non-deterministic; more prompts I don't control | Wrong shape: this task is a pipeline, not a debate |

The structure maps one-to-one onto LangGraph: each stage becomes a node, `asyncio.gather` becomes
fan-out edges, and the critic loop becomes a conditional edge. Migrating would be mechanical.

**Model access** goes through the `openai` SDK against any OpenAI-compatible endpoint, so one code
path covers local Ollama (free, offline), Groq and Gemini free tiers, and OpenAI. I did not use
provider-specific features. The trade-off is that I give up some provider-native features (for
example strict structured outputs), so validation and repair happen client-side.

## 3. MCP integration

The tools live in a separate process, an **MCP server**
([`mcp_server/server.py`](src/incident_agent/mcp_server/server.py)) built on the official Python
SDK (`mcp` 2.x, `MCPServer`). It serves mock operational data for one scenario "world":

| Tool | Purpose |
|---|---|
| `list_services` | Service catalog: owners, tiers, dependencies |
| `get_recent_deployments(service?, limit)` | Newest-first deploys, with `hours_before_now` |
| `get_deployment_diff(deploy_id)` | Commits, changed files, config changes, pipeline steps |
| `search_logs(service, query, level, since, until, limit)` | Filtered log search, newest first, with total count and first-match time |
| `get_error_summary(service, around?)` | WARN/ERROR grouped by signature with first/last seen, counts **before vs after** the latest deploy (only when that deploy falls inside the log window) |
| `get_metrics(service, metric)` | Time series plus baseline, latest, max and a detected level change (least-squares change point, counted only if the medians differ 2x) |
| `search_docs(query)` | Keyword search over runbooks and architecture docs |

It also exposes **resources**: `runbook://{name}` and `incident://report`. All tools are annotated
`readOnlyHint`, since an investigator must never mutate production.

**How the integration works**

1. **Protocol:** MCP is JSON-RPC 2.0. The client connects, negotiates the protocol version and
   capabilities, then calls `tools/list`. Each tool comes with a JSON Schema for its input,
   generated from the Python type hints and `Field` descriptions.
2. **Discovery, not hard-coding:** the agent side
   ([`mcp_client.py`](src/incident_agent/mcp_client.py)) converts each MCP tool schema into an
   OpenAI function-calling schema. Both sides use JSON Schema, so this is a re-wrap, not a
   translation. The agents never import tool code.
3. **Execution:** when a model emits a tool call, the agent loop sends `tools/call` over the MCP
   session. The text result goes back to the model, prefixed with its evidence ID.
4. **Errors are data:** bad arguments (an unknown service, a malformed timestamp) raise `ToolError`
   on the server. MCP returns that as `isError: true` with a helpful message, so the model can
   correct itself. Unexpected exceptions are hidden from the client by the SDK.
5. **Transports:**
   - **stdio** (default): the client spawns `python -m incident_agent.mcp_server.server` as a
     subprocess and exchanges newline-delimited JSON-RPC over stdin/stdout. Zero config and
     process-isolated, which suits local use and evals (each scenario gets its own server).
   - **Streamable HTTP** (`--transport http`, `MCP_URL=...`): a single `/mcp` endpoint, POST for
     requests, optional SSE streaming for responses. This is the networked transport for
     deployment. Docker Compose runs it as its own container. SSE-only transport is deprecated,
     so I didn't use it.

Both transports are covered by integration tests
([`tests/test_mcp_integration.py`](tests/test_mcp_integration.py)).

**Mock data.** Each scenario is a directory of JSON/JSONL/Markdown generated deterministically by
[`scripts/gen_scenarios.py`](scripts/gen_scenarios.py). Every world contains realistic noise:
harmless background warnings, an unrelated `frontend-web` deploy, and healthy traffic. Agents have
to separate signal from noise rather than find the only error in the file. Ground truth
(`expected.json`) sits next to the data but is never exposed by the server.

## 4. Evaluations

### Dataset

Seven scenarios, chosen so that each tests a different reasoning skill, not just a different error
string:

| Scenario | Truth | What it tests |
|---|---|---|
| `checkout_bad_config` | renamed env var in v2.4.1 → `KeyError` | Connecting a log error to a code diff |
| `payments_missing_migration` | `db-migrate` step skipped → `UndefinedColumn` | Reading pipeline metadata, not just commits |
| `search_latency_regression` | cache removed → p99 120ms → 2400ms | Non-error incident; config change in the diff |
| `orders_upstream_dependency` | inventory-service pool exhausted; **deploy is innocent** | Resisting the user's framing; timeline reasoning (errors start 50 min *before* the deploy) |
| `worker_oom_crashloop` | memory limit 1024Mi → 512Mi with a larger batch size | Combining config changes with OOMKilled logs and metrics |
| `auth_cert_expiry` | mTLS cert expired; **no deploy at all** | "Did something get deployed?" when nothing was |
| `ambiguous_low_signal` | background noise, no incident | Calibration: saying "unknown" with low confidence |

### Criteria and scorers

[`evals/scorers.py`](evals/scorers.py) contains deterministic, transparent checks:

| Scorer | Measures | Gates pass? |
|---|---|---|
| `schema_valid` | Produced a valid `IncidentReport` | yes |
| `root_cause_category` | Category matches truth (some scenarios accept two, e.g. bad_config/code_bug) | yes |
| `deploy_attribution` | `caused_by_latest_deploy` matches truth; for "undetermined", anything but blaming the deploy | yes |
| `key_fact_recall` | Fraction of must-mention facts (e.g. `v2.4.1`, `DATABASE_POOL_SIZE`) present, ≥ 0.5 | yes |
| `citation_grounding` | Cited evidence IDs exist **and** the cited raw output contains the claim's distinctive tokens (versions, identifiers, numbers), ≥ 0.8 | yes |
| `tool_coverage` | The tools a human would use were called | tracked |
| `next_step_relevance` | Next steps contain an expected action (roll back, migrate, renew, escalate to inventory) | tracked |
| `calibration` | Confidence ≥ 0.5 when right, < 0.7 when wrong, ≤ 0.5 on the ambiguous case | tracked |

A run **passes** when it is right and grounded. Efficiency (latency, LLM calls, tool calls,
tokens) is recorded for every run. `--judge` adds an LLM-as-judge that grades root cause and next
steps from 1 to 5 against a reference answer written per scenario ([`evals/judge.py`](evals/judge.py)).
It's off by default: a small local judge is noisy and shares blind spots with the model under
test, so I use it as a trend signal and prefer a stronger, different model as judge.

**Reliability:** `--k N` runs each scenario N times and reports the pass rate plus pass^k (the
scenario passes on all N attempts). LLM output varies run to run, so a single pass says little.

**Finding failures:** every run writes a JSONL trace (each LLM call, tool call with arguments,
validation error and critic verdict). `summary.md` lists each failing run with the scorer that
failed, what the model claimed, and the path to its trace. That's usually enough to tell a
prompt problem from a tool problem from a reasoning problem.

**Ablations:** `--no-critic` measures what the critic step actually adds, and
`LLM_REASONING_EFFORT` measures the effect of the model's thinking mode.

### Results and findings

Local `qwen3:8b` (thinking off) on an Apple M3 laptop, k=1 per scenario, about 5 minutes per
investigation. Full tables: [`evals/results/`](evals/results/).

| Iteration | Pass | What changed |
|---|---|---|
| v1 (partial, 3/7 run) | 1/3 | First prompts and tools |
| v2 | 1/7 | Tool fix 1: no before/after deploy split when the deploy predates the logs |
| v3 | 6/7 | The fixes in the first five rows below |
| v3, re-run later | 5/7 | Same design plus the confidence cap; the red herring regressed (row 6) |
| **v4** | **6/7** | Deploy timeline checked in code; `orders_upstream_dependency` then passed 4/4 (k=3 run plus the suite run) |

**What the failures taught me** (each diagnosed from the run traces):

| Failure seen | Root cause | Fix |
|---|---|---|
| Ambiguous case: "errors increased after the deploy", 0.8 confidence | Tools framed the data misleadingly: an error summary split on a deploy 2 days before the logs counted every error as "after"; metrics showed `baseline` vs `latest`, two noisy points the model compared | Tools stopped implying conclusions: no split when the deploy predates the logs; metrics report a change point (least-squares location, counted only if the medians differ 2x) or "no significant change", plus min/median/max |
| Red herring: blamed the deploy and **recommended rolling it back**, even though errors started 50 min earlier | The model wrote "09:20, which is after the latest deployment (10:10)": an 8B model can't reliably compare ISO timestamps, and every agent repeated the reporter's framing | **Deterministic work moved into code**: tools now say "first seen 50 min BEFORE latest deploy dep-7716". Specialists are told the report's explanation is a hypothesis to test |
| Cert expiry: wrote "the deploy did not cause it" and set `deploy_related: true` in the same report; the critic approved | Ambiguous field name, plus a prompt template showing the literal value `true` (small models copy template values) | Renamed to `caused_by_latest_deploy`; templates show `<true \| false \| null>`; the critic checks the report's internal consistency |
| Search: correct explanation, but labelled `code_bug` | `code_bug` acts as a catch-all for anything caused by a change | `code_bug` listed last and defined as the fallback category |
| Checkout and payments failed `citation_grounding` with correct evidence | **Scorer bug**: words like "deployment" and "configuration" counted as facts to match verbatim | Only identifiers and numbers count as checkable facts; regression test added |
| Red herring again, on a later run: all four specialists wrote "after the latest deployment" although every tool output said "50 min BEFORE"; the critic approved | Telling an 8B model the timeline is not enough, it still echoes the reporter. The v3 pass was partly luck | **The verdict moved into code too**: when every metric change on the affected service predates its latest deploy, the synthesis brief says so as a computed fact, and a deterministic critic check rejects a report that still blames the deploy. It fires only on this scenario across all saved runs |
| Orders: `citation_grounding` called "201.68ms" unsupported though the evidence contains 201.68 | **Scorer bug**: a number with a unit was a different token from the bare number | Units are stripped from numbers; regression test; re-scoring every saved run changed no pass/fail result |

Lessons:
1. **Tool design is prompt design.** Most model "reasoning errors" came from tool outputs that
   invited a wrong reading. Fixing the tools generalised; patching the prompts would not have.
2. **Do in code what code does reliably** (time arithmetic, change detection); let the model do
   the judgment.
3. **The evaluator needs testing too.** One failure was the scorer's, not the model's. Each run
   stores its full evidence ledger, so the scorers can be changed and old runs re-scored without
   re-running the model.

**The remaining failure** (`ambiguous_low_signal`): the model now behaves well. Confidence is
0.4, deploy attribution is undetermined, it asks for more data and recommends monitoring. But it
names `dependency_failure` (avatar-cdn) where the label is `unknown`. Arguably either is
defensible. I kept the label strict rather than relax it after seeing the output; changing
labels to match results is how eval sets stop meaning anything.

**Reliability.** An earlier k=3 run (paused partway) had `auth_cert_expiry` 3/3 and
`checkout_bad_config` 1/1, but `ambiguous_low_signal` failed calibration 3/3: the 0.4
confidence in v3 was luck, not a fix. That led to a calibration rule in code (confidence capped
at 0.4 when metrics were checked and none changed level); calibration has passed on every run
since. Likewise the red herring passed in v3, failed on a re-run, and only became reliable once
the timeline verdict moved into code (k=3: 3/3). One run per scenario hides exactly this.

**Hosted models (Groq free tier).** I also ran gpt-oss-120b, gpt-oss-20b and qwen3.8-27b on
Groq's free tier. None of these runs is a clean measurement of the model: they mostly measured
the free tier's limits. Each failure became a fix:

| Run | Result | What actually happened | Fix |
|---|---|---|---|
| gpt-oss-120b, k=1 (after the fixes) | 3/4, then quota | A clean run: no crashes, and the suite stopped at the daily quota instead of scoring the rest. The one failure is the same ambiguous case | - |
| gpt-oss-120b, k=3 | 2/21 | Daily token quota ran out after 5 runs; the other 16 failed in under a second and were scored as model failures | A daily-quota error now stops the suite and leaves the remaining runs unscored |
| gpt-oss-20b, k=1 | 3/7 | Parallel specialists collided on the tokens-per-minute limit, exhausted the SDK's retries, and 3 runs silently lost their logs specialist | Per-minute 429s are waited out (`LLM_RATE_LIMIT_WAIT_S`) |
| qwen3.8-27b, k=1 | 0/4, then quota | The synthesis prompt (8.9k tokens) exceeded a 7k input-tokens-per-minute cap; the 413 crashed every run, hidden inside an `ExceptionGroup` from the MCP client | Raw excerpts in the synthesis brief are capped; a 413 degrades instead of crashing; the MCP client re-raises the original error |

Only 4 of 7 scenarios fit in one day's free quota for a model, so the local qwen3:8b results
above are the ones to judge the system by.

**Caveats.** Seven scenarios is a small set,
and the scenarios were written by the same person who wrote the prompts. Next steps would be
held-out scenarios written by someone else, and sampled real incidents.

## 5. Engineering and production readiness

**Testing (what exists).** 80 tests run in about 3s with no model or network:
- Unit tests for the data layer and tools, JSON extraction from messy model output, and the
  scorers.
- Agent-loop tests: disallowed tool, malformed arguments, tool exceptions, iteration cap, repair
  round, duplicate calls.
- Orchestrator tests with a scripted `FakeLLM`: specialist failure, critic-triggered revision,
  hallucinated citation, triage fallback, provider quota and request-size limits.
- MCP integration over both stdio and HTTP.
- An eval-harness smoke test that runs the real pipeline and real MCP server with a scripted
  model.

Model quality is measured separately by the eval suite, which is the right tool for
non-deterministic behaviour.

**Error handling (what exists).**
- LLM: SDK retries with exponential backoff on connection errors, 429 and 5xx; per-request
  timeout; a concurrency limiter so queueing never counts against the timeout.
- Provider limits: per-minute 429s are waited out using the provider's suggested delay; a
  daily quota stops the eval suite and leaves the remaining runs unscored rather than counting
  them as model failures; a 413 "request too large" retries synthesis once without raw evidence
  excerpts, and triage and the critic fall back to their deterministic defaults.
- Tools: per-call timeout; tool errors are returned to the model as text; a model can't call
  tools outside its allowlist.
- Loops: capped tool rounds, then a forced final answer with tools withheld.
- Output: tolerant JSON extraction, Pydantic validation, one repair round.
- Pipeline: specialist failure degrades confidence instead of failing the run; a failed revision
  keeps the original report.

**Toward production**
- **Observability:** the JSONL trace events already have the shape of spans. Emit them as
  OpenTelemetry spans using the GenAI semantic conventions, to Langfuse, Phoenix or Honeycomb.
  Add dashboards for latency, token cost per investigation, tool error rate, and the critic
  rejection rate (a useful leading indicator of model drift). Sample real investigations into the
  eval set.
- **Docker:** a `Dockerfile` (uv, non-root, cached dependency layer) and `docker-compose.yml` that
  runs the MCP server over Streamable HTTP with the agent connecting over the network:
  `docker compose up -d mcp-server && docker compose run --rm agent investigate`. In production the
  MCP server would front real systems (Datadog/Loki, Argo/Spinnaker, Prometheus, Confluence) with
  auth (MCP's OAuth 2.1 support), rate limits and audit logging, and stay read-only.
- **CI/CD:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs lint, format check,
  tests, a check that the scenario data matches its generator, and a Docker build on every push.
  The model eval suite runs on demand (`workflow_dispatch`) against a hosted model from secrets,
  and uploads results. Next step: run evals nightly and on prompt changes, and block merges that
  lower the pass rate (eval-gated deploys).
- **Safety:** keep tools read-only. Any remediation tool (rollback) should require human approval,
  which is where LangGraph-style interrupts would earn their keep.
- **Scale and cost:** cache tool results per incident, stream partial findings to the user, and
  route triage and docs to a cheap model while the synthesizer gets the strongest one.

## Configuration

All configuration comes from environment variables or a local `.env` file (see
[`.env.example`](.env.example)); real environment variables win over `.env`:

| Variable | Default | Notes |
|---|---|---|
| `LLM_BASE_URL` | `http://localhost:11434/v1` | Any OpenAI-compatible endpoint |
| `LLM_MODEL` | `incident-qwen3` | Created from `ollama/Modelfile` |
| `LLM_API_KEY` | `ollama` | |
| `LLM_REASONING_EFFORT` | `none` | Turns off Qwen3 thinking (about 8x fewer tokens); set empty for providers that reject it |
| `LLM_MAX_CONCURRENCY` | `1` | Local Ollama serves one request at a time; use 4+ for hosted APIs |
| `LLM_TIMEOUT_S` | `180` | Per request |
| `LLM_MAX_RETRIES` | `3` | SDK retries on 429/5xx/timeouts with backoff |
| `LLM_RATE_LIMIT_WAIT_S` | `300` | Per call: keep waiting out per-minute 429s (using the provider's suggested wait) up to this long. A per-day quota stops the run instead |
| `MAX_TOOL_ROUNDS` | `6` | Per specialist |
| `MCP_URL` | unset | Connect over Streamable HTTP instead of spawning stdio |

## Repository layout

```
src/incident_agent/
  mcp_server/   server.py (MCP tools + resources), world.py (data access), scenarios/ (generated)
  agents/       base.py (agent loop), prompts.py, specs.py (roster)
  orchestrator.py  llm.py  mcp_client.py  evidence.py  schemas.py  tracing.py  render.py  cli.py
evals/          runner.py, scorers.py, judge.py, results/
scripts/        gen_scenarios.py, docs/ (runbook sources)
tests/          unit, integration, orchestrator, eval-harness tests
docs/superpowers/  design spec and implementation plan
```
