# Eval results 20261015T034931

**Incomplete.** Stopped before payments_missing_migration #1: provider quota exhausted (Error code: 429 - {'error': {'message': 'Rate limit reached for model `qwen/qwen3.8-27b` in organization `org_01m4ymab7ge61a6xhdb3h0xnp2` service tier `on_demand` on tokens per day (TPD): Limit 200000, Used 196737, Requested 4404. Please try again in 8m12.912s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}})

Model `qwen/qwen3.8-27b`, k=1, critic=on.

| scenario | pass | root cause category | deploy attribution | key fact recall | citation grounding | tool coverage | next step relevance | calibration | avg s | tools |
|---|---|---|---|---|---|---|---|---|---|---|
| ambiguous_low_signal | 0/1 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 335 | 25.0 |
| auth_cert_expiry | 0/1 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 282 | 16.0 |
| checkout_bad_config | 0/1 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 266 | 23.0 |
| orders_upstream_dependency | 0/1 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 410 | 27.0 |
| **overall** | **0/4** | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 323 | 22.8 |

Pass rate: 0% of runs. Scenarios passing on all 1 attempts (pass^k): 0/4.

## Failures

### ambiguous_low_signal #1
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T034931/traces/ambiguous_low_signal-1.jsonl`
### auth_cert_expiry #1
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T034931/traces/auth_cert_expiry-1.jsonl`
### checkout_bad_config #1
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T034931/traces/checkout_bad_config-1.jsonl`
### orders_upstream_dependency #1
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T034931/traces/orders_upstream_dependency-1.jsonl`
