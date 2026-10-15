"""Runtime configuration, read from the environment."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "incident-qwen3"
    llm_api_key: str = "ollama"
    llm_timeout_s: float = 180.0
    # Qwen3 "thinking" multiplies output tokens ~8x; off by default for local speed. Set to ""
    # for providers that reject the parameter, or low/medium/high for reasoning models.
    llm_reasoning_effort: str | None = "none"
    # Local Ollama serves one request at a time; queueing in Ollama would count against our
    # timeout. Raise for hosted APIs to get real parallelism between specialists.
    llm_max_concurrency: int = 1
    # Hosted free tiers rate-limit (429); the SDK backs off and honours Retry-After.
    llm_max_retries: int = 3
    # Total time to keep waiting out per-minute rate limits (429) for one call.
    llm_rate_limit_wait_s: float = 300.0
    mcp_url: str | None = None  # if set, connect over Streamable HTTP instead of spawning stdio
    max_tool_rounds: int = 6
    runs_dir: str = "runs"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()  # a local .env, if present; real environment variables take precedence
        env = os.environ
        return cls(
            llm_base_url=env.get("LLM_BASE_URL", cls.llm_base_url),
            llm_model=env.get("LLM_MODEL", cls.llm_model),
            llm_api_key=env.get("LLM_API_KEY", cls.llm_api_key),
            llm_timeout_s=float(env.get("LLM_TIMEOUT_S", cls.llm_timeout_s)),
            llm_reasoning_effort=env.get("LLM_REASONING_EFFORT", cls.llm_reasoning_effort) or None,
            llm_max_concurrency=int(env.get("LLM_MAX_CONCURRENCY", cls.llm_max_concurrency)),
            llm_max_retries=int(env.get("LLM_MAX_RETRIES", cls.llm_max_retries)),
            llm_rate_limit_wait_s=float(
                env.get("LLM_RATE_LIMIT_WAIT_S", cls.llm_rate_limit_wait_s)
            ),
            mcp_url=env.get("MCP_URL") or None,
            max_tool_rounds=int(env.get("MAX_TOOL_ROUNDS", cls.max_tool_rounds)),
            runs_dir=env.get("RUNS_DIR", cls.runs_dir),
        )
