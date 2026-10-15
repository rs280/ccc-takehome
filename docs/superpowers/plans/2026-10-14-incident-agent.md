# Incident Investigator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Multi-agent incident investigator over an MCP server of mock ops data, with evals.

**Architecture:** FastMCP server serves one scenario "world" per process. A custom asyncio
orchestrator runs Triage -> parallel specialists (each a tool-calling loop over an MCP tool
subset) -> Synthesizer -> Critic, with a shared evidence ledger for grounding.

**Tech Stack:** Python 3.12+, uv, `mcp`, `openai`, `pydantic`, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-10-14-incident-agent-design.md`

Note: the user asked to start building right away, so this plan lists tasks, interfaces and
tests compactly instead of inlining all code; the implementer is the same session that wrote
the spec.

## Global Constraints

- OpenAI-compatible LLM via env `LLM_BASE_URL` (default `http://localhost:11434/v1`), `LLM_MODEL` (default `qwen3:8b`), `LLM_API_KEY` (default `ollama`); `LLM_PROVIDER=fake` for FakeLLM.
- Tests and CI never need network or a model.
- `expected.json` is never exposed through MCP tools.
- No em dashes in prose.

## Review Focus

1. Model emits malformed JSON / `<think>` blocks / code fences -> extractor recovers or one repair round, never crash.
2. Model calls a tool not in its allowlist or with bad args -> error string returned to model, loop continues.
3. Model never stops calling tools -> iteration cap forces final answer.
4. Specialist raises -> pipeline still produces a report, marked with reduced evidence.
5. Report cites nonexistent evidence ID -> critic flags it, scorer fails grounding.

---

### Task 1: Project scaffold + schemas
**Files:** `pyproject.toml`, `src/incident_agent/__init__.py`, `src/incident_agent/schemas.py`, `src/incident_agent/config.py`, `tests/test_schemas.py`
**Produces:** Pydantic models `TriageResult`, `Finding`, `SpecialistReport`, `EvidenceItem`, `RootCause`, `NextStep`, `IncidentReport`, `CriticVerdict`; `RootCauseCategory` Literal; `Settings.from_env()`.
- [ ] Test: IncidentReport validates sample; rejects bad category; confidence bounded 0-1.
- [ ] Implement, run, commit.

### Task 2: Scenario data (7 worlds)
**Files:** `src/incident_agent/mcp_server/scenarios/<id>/{services.json,deployments.json,logs.jsonl,metrics.json,docs/*.md,incident.txt,expected.json}`; generator `scripts/gen_scenarios.py` (logs/metrics are synthetic, so generated deterministically from a compact per-scenario spec).
**Produces:** `expected.json` keys: `category`, `deploy_related`, `key_facts[]`, `expected_tools[]`, `next_step_keywords[]`, `max_confidence?`.
- [ ] Test (`tests/test_scenarios.py`): every scenario dir has all files, valid JSON, expected keys.

### Task 3: MCP server
**Files:** `src/incident_agent/mcp_server/world.py` (pure data access, testable), `src/incident_agent/mcp_server/server.py` (FastMCP wrappers + resources + CLI), `tests/test_world.py`, `tests/test_mcp_integration.py`
**Produces:** `World.load(scenario)`, methods matching tool names; console script `mcp-server`.
- [ ] Unit tests on World (search filters, error summary before/after, diff lookup, unknown id error).
- [ ] Integration: spawn over stdio, list_tools has 7 tools, call search_logs, read resource.

### Task 4: LLM client + JSON extraction
**Files:** `src/incident_agent/llm.py`, `src/incident_agent/jsonutil.py`, `tests/test_jsonutil.py`
**Produces:** `LLM` protocol `async complete(messages, tools=None, tool_choice=None) -> LLMResponse(content, tool_calls, usage)`; `OpenAICompatLLM`; `FakeLLM(script: Callable)`; `extract_json(text) -> dict`.
- [ ] Tests: think tags, fences, trailing prose, nested braces, invalid -> ValueError.

### Task 5: MCP client + agent loop + tracing
**Files:** `src/incident_agent/mcp_client.py`, `src/incident_agent/agents/base.py`, `src/incident_agent/tracing.py`, `src/incident_agent/evidence.py`, `tests/test_agent_loop.py`
**Produces:** `ToolBox` (async ctx; `list_tools()`, `call(name,args)->str`); `EvidenceLedger.add(tool,args,output)->id`; `run_agent(spec, user_msg, llm, toolbox, ledger, tracer) -> BaseModel`.
- [ ] Tests with FakeLLM + stub toolbox: tool call recorded with ID; disallowed tool -> error message; iteration cap; repair round on invalid JSON.

### Task 6: Agents + orchestrator + CLI
**Files:** `src/incident_agent/agents/{prompts.py,specs.py}`, `src/incident_agent/orchestrator.py`, `src/incident_agent/render.py`, `src/incident_agent/cli.py`, `tests/test_orchestrator.py`
**Produces:** `investigate(report, llm, toolbox, tracer) -> InvestigationResult(report, ledger, triage, specialists, critic, trace_path)`; console script `investigate`.
- [ ] Test: FakeLLM scripted full pipeline; specialist exception path; critic rejection triggers one revision.

### Task 7: Evals
**Files:** `evals/__init__.py`, `evals/scorers.py`, `evals/runner.py`, `evals/judge.py`, `tests/test_scorers.py`, `tests/test_eval_smoke.py`
- [ ] Scorer unit tests on hand-built reports; smoke run of runner with FakeLLM on one scenario.
- [ ] Run real evals against Ollama, record results, analyze failures, iterate prompts.

### Task 8: Infra + docs
**Files:** `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `README.md`, `.gitignore`
- [ ] docker build succeeds; README covers architecture, framework choice, MCP, evals, production notes, results.
