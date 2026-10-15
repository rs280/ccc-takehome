# Eval results 20261015T200006

**Incomplete.** Stopped before payments_missing_migration #1: provider quota exhausted (Error code: 429 - {'error': {'message': 'Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01m4ymab7ge61a6xhdb3h0xnp2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 197939, Requested 4703. Please try again in 19m1.344s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}})

Model `openai/gpt-oss-120b`, k=1, critic=on.

| scenario | pass | root cause category | deploy attribution | key fact recall | citation grounding | tool coverage | next step relevance | calibration | avg s | tools |
|---|---|---|---|---|---|---|---|---|---|---|
| ambiguous_low_signal | 0/1 | 0.00 | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 218 | 12.0 |
| auth_cert_expiry | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 211 | 12.0 |
| checkout_bad_config | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 228 | 11.0 |
| orders_upstream_dependency | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 235 | 13.0 |
| **overall** | **3/4** | 0.75 | 1.00 | 0.75 | 1.00 | 1.00 | 1.00 | 1.00 | 223 | 12.0 |

Pass rate: 75% of runs. Scenarios passing on all 1 attempts (pass^k): 3/4.

## Failures

### ambiguous_low_signal #1
- said: [dependency_failure, 0.40] Transient failures in the avatar‑cdn service cause connection resets and read timeouts when profile‑api proxies avatar images, resulting in intermittent 502/504 responses.
- caused_by_latest_deploy: False
- failing: root_cause_category (got dependency_failure, expected unknown); key_fact_recall (missing ['ConnectionResetError'])
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T200006/traces/ambiguous_low_signal-1.jsonl`
