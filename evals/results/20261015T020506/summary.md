# Eval results 20261015T020506

Model `openai/gpt-oss-120b`, k=3, critic=on.

| scenario | pass | root cause category | deploy attribution | key fact recall | citation grounding | tool coverage | next step relevance | calibration | avg s | tools |
|---|---|---|---|---|---|---|---|---|---|---|
| ambiguous_low_signal | 0/3 | 0.00 | 1.00 | 0.67 | 1.00 | 1.00 | 0.67 | 1.00 | 211 | 12.0 |
| auth_cert_expiry | 2/3 | 0.67 | 0.67 | 0.67 | 0.67 | 0.67 | 0.67 | 0.67 | 163 | 11.7 |
| checkout_bad_config | 0/3 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 30 | 0.0 |
| orders_upstream_dependency | 0/3 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0 | 0.0 |
| payments_missing_migration | 0/3 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0 | 0.0 |
| search_latency_regression | 0/3 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0 | 0.0 |
| worker_oom_crashloop | 0/3 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0 | 0.0 |
| **overall** | **2/21** | 0.10 | 0.24 | 0.19 | 0.24 | 0.24 | 0.19 | 0.24 | 58 | 3.4 |

Pass rate: 10% of runs. Scenarios passing on all 3 attempts (pass^k): 0/7.

## Failures

### ambiguous_low_signal #1
- said: [dependency_failure, 0.40] Avatar‑cdn is intermittently failing to deliver images, causing profile‑api to return 502/504 errors when proxying avatar requests.
- caused_by_latest_deploy: False
- failing: root_cause_category (got dependency_failure, expected unknown); key_fact_recall (missing ['ConnectionResetError'])
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/ambiguous_low_signal-1.jsonl`
### ambiguous_low_signal #2
- said: [dependency_failure, 0.40] Upstream avatar‑cdn service is intermittently failing, producing connection resets and read timeouts that surface as 5xx errors in profile‑api.
- caused_by_latest_deploy: False
- failing: root_cause_category (got dependency_failure, expected unknown); next_step_relevance (no match)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/ambiguous_low_signal-2.jsonl`
### ambiguous_low_signal #3
- said: [dependency_failure, 0.40] Transient failures in the avatar‑cdn service (connection resets and read timeouts) cause profile‑api to return 502/504 errors when proxying avatar images.
- caused_by_latest_deploy: False
- failing: root_cause_category (got dependency_failure, expected unknown)
- failed specialists: logs
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/ambiguous_low_signal-3.jsonl`
### auth_cert_expiry #3
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/auth_cert_expiry-3.jsonl`
### checkout_bad_config #1
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/checkout_bad_config-1.jsonl`
### checkout_bad_config #2
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/checkout_bad_config-2.jsonl`
### checkout_bad_config #3
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/checkout_bad_config-3.jsonl`
### orders_upstream_dependency #1
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/orders_upstream_dependency-1.jsonl`
### orders_upstream_dependency #2
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/orders_upstream_dependency-2.jsonl`
### orders_upstream_dependency #3
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/orders_upstream_dependency-3.jsonl`
### payments_missing_migration #1
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/payments_missing_migration-1.jsonl`
### payments_missing_migration #2
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/payments_missing_migration-2.jsonl`
### payments_missing_migration #3
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/payments_missing_migration-3.jsonl`
### search_latency_regression #1
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/search_latency_regression-1.jsonl`
### search_latency_regression #2
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/search_latency_regression-2.jsonl`
### search_latency_regression #3
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/search_latency_regression-3.jsonl`
### worker_oom_crashloop #1
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/worker_oom_crashloop-1.jsonl`
### worker_oom_crashloop #2
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/worker_oom_crashloop-2.jsonl`
### worker_oom_crashloop #3
- error: `ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)`
- failing: schema_valid (no valid report produced)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T020506/traces/worker_oom_crashloop-3.jsonl`
