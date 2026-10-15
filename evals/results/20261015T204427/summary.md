# Eval results 20261015T204427

Model `incident-qwen3`, k=1, critic=on.

| scenario | pass | root cause category | deploy attribution | key fact recall | citation grounding | tool coverage | next step relevance | calibration | avg s | tools |
|---|---|---|---|---|---|---|---|---|---|---|
| ambiguous_low_signal | 0/1 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 223 | 7.0 |
| auth_cert_expiry | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 270 | 8.0 |
| checkout_bad_config | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 304 | 9.0 |
| orders_upstream_dependency | 1/1 | 1.00 | 1.00 | 1.00 | 0.83 | 1.00 | 1.00 | 1.00 | 398 | 12.0 |
| payments_missing_migration | 1/1 | 1.00 | 1.00 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 | 288 | 10.0 |
| search_latency_regression | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 309 | 10.0 |
| worker_oom_crashloop | 1/1 | 1.00 | 1.00 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 | 283 | 8.0 |
| **overall** | **6/7** | 0.86 | 1.00 | 0.86 | 0.98 | 1.00 | 1.00 | 1.00 | 296 | 9.1 |

Pass rate: 86% of runs. Scenarios passing on all 1 attempts (pass^k): 6/7.

## Failures

### ambiguous_low_signal #1
- said: [dependency_failure, 0.40] The connection resets and timeouts are likely due to an issue with the avatar-cdn dependency, which the profile-api service proxies for avatar images.
- caused_by_latest_deploy: False
- failing: root_cause_category (got dependency_failure, expected unknown)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T204427/traces/ambiguous_low_signal-1.jsonl`
