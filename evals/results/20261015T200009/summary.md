# Eval results 20261015T200009

Model `incident-qwen3`, k=1, critic=on.

| scenario | pass | root cause category | deploy attribution | key fact recall | citation grounding | tool coverage | next step relevance | calibration | avg s | tools |
|---|---|---|---|---|---|---|---|---|---|---|
| ambiguous_low_signal | 0/1 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 314 | 8.0 |
| auth_cert_expiry | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 325 | 8.0 |
| checkout_bad_config | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 372 | 9.0 |
| orders_upstream_dependency | 0/1 | 1.00 | 0.00 | 1.00 | 0.67 | 1.00 | 1.00 | 1.00 | 522 | 11.0 |
| payments_missing_migration | 1/1 | 1.00 | 1.00 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 | 348 | 10.0 |
| search_latency_regression | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 356 | 9.0 |
| worker_oom_crashloop | 1/1 | 1.00 | 1.00 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 | 281 | 8.0 |
| **overall** | **5/7** | 0.86 | 0.86 | 0.86 | 0.95 | 1.00 | 1.00 | 1.00 | 360 | 9.0 |

Pass rate: 71% of runs. Scenarios passing on all 1 attempts (pass^k): 5/7.

## Failures

### ambiguous_low_signal #1
- said: [dependency_failure, 0.40] The connection resets and timeouts observed in the profile-api service are due to the dependency, avatar-cdn, experiencing network issues or instability.
- caused_by_latest_deploy: False
- failing: root_cause_category (got dependency_failure, expected unknown)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T200009/traces/ambiguous_low_signal-1.jsonl`
### orders_upstream_dependency #1
- said: [dependency_failure, 0.90] The inventory-service's database connection pool exhaustion caused upstream timeouts, which led to the HTTP 500 errors in the orders-api after the latest deployment.
- caused_by_latest_deploy: True
- failing: deploy_attribution (got True, expected False); citation_grounding (E5: unsupported ['201.68ms', '5081.27ms']; E12: unsupported ['5024.13ms', '90.14ms'])
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T200009/traces/orders_upstream_dependency-1.jsonl`
