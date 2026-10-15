# Eval results 20261014T204757

Model `incident-qwen3`, k=1, critic=on.

| scenario | pass | root cause category | deploy attribution | key fact recall | citation grounding | tool coverage | next step relevance | calibration | avg s | tools |
|---|---|---|---|---|---|---|---|---|---|---|
| ambiguous_low_signal | 0/1 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 220 | 8.0 |
| auth_cert_expiry | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 231 | 8.0 |
| checkout_bad_config | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 255 | 9.0 |
| orders_upstream_dependency | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 330 | 12.0 |
| payments_missing_migration | 1/1 | 1.00 | 1.00 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 | 253 | 10.0 |
| search_latency_regression | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 285 | 9.0 |
| worker_oom_crashloop | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 192 | 8.0 |
| **overall** | **6/7** | 0.86 | 1.00 | 0.93 | 1.00 | 1.00 | 1.00 | 1.00 | 252 | 9.1 |

Pass rate: 86% of runs. Scenarios passing on all 1 attempts (pass^k): 6/7.

## Failures

### ambiguous_low_signal #1
- said: [dependency_failure, 0.40] The errors are caused by the avatar-cdn dependency, which is known to have a small rate of connection resets and timeouts, and the timing of the errors aligns with the deployment of profile-api.
- caused_by_latest_deploy: None
- failing: root_cause_category (got dependency_failure, expected unknown)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261014T204757/traces/ambiguous_low_signal-1.jsonl`
