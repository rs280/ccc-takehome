# Eval results 20261017T062424

Model `incident-qwen3`, k=3, critic=off.

| scenario | pass | root cause category | deploy attribution | key fact recall | citation grounding | tool coverage | next step relevance | calibration | avg s | tools |
|---|---|---|---|---|---|---|---|---|---|---|
| ambiguous_low_signal | 0/3 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 431 | 7.7 |
| auth_cert_expiry | 3/3 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 506 | 8.0 |
| checkout_bad_config | 3/3 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 533 | 9.0 |
| checkout_upstream_contract | 2/3 | 0.67 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.67 | 554 | 12.0 |
| inventory_memory_leak | 0/3 | 1.00 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.00 | 543 | 11.0 |
| orders_upstream_dependency | 2/3 | 0.67 | 1.00 | 1.00 | 0.94 | 1.00 | 1.00 | 0.67 | 601 | 11.3 |
| payments_missing_migration | 3/3 | 1.00 | 1.00 | 0.50 | 0.93 | 1.00 | 1.00 | 1.00 | 486 | 10.0 |
| search_disk_watermark | 3/3 | 1.00 | 1.00 | 1.00 | 0.93 | 1.00 | 1.00 | 1.00 | 531 | 8.0 |
| search_latency_regression | 3/3 | 1.00 | 1.00 | 0.83 | 1.00 | 1.00 | 1.00 | 1.00 | 485 | 9.7 |
| worker_oom_crashloop | 3/3 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 403 | 8.0 |
| **overall** | **22/30** | 0.83 | 1.00 | 0.83 | 0.98 | 1.00 | 0.90 | 0.83 | 507 | 9.5 |

Pass rate: 73% of runs. Scenarios passing on all 3 attempts (pass^k): 6/10.

## Failures

### ambiguous_low_signal #1
- said: [dependency_failure, 0.40] The connection resets and timeouts in the profile-api service are likely due to an issue with the avatar-cdn dependency, which is being proxied by the profile-api service.
- caused_by_latest_deploy: False
- failing: root_cause_category (got dependency_failure, expected unknown)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T062424/traces/ambiguous_low_signal-1.jsonl`
### ambiguous_low_signal #2
- said: [dependency_failure, 0.40] The connection resets and timeouts in profile-api are caused by the avatar-cdn dependency, which is known to have a small rate of connection resets and timeouts.
- caused_by_latest_deploy: None
- failing: root_cause_category (got dependency_failure, expected unknown)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T062424/traces/ambiguous_low_signal-2.jsonl`
### ambiguous_low_signal #3
- said: [dependency_failure, 0.40] The errors are due to the avatar-cdn dependency experiencing connection resets and timeouts, which are not directly caused by the latest deploy of profile-api.
- caused_by_latest_deploy: False
- failing: root_cause_category (got dependency_failure, expected unknown)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T062424/traces/ambiguous_low_signal-3.jsonl`
### checkout_upstream_contract #2
- said: [bad_config, 0.80] The KeyError: 'amount_cents' in the payments-api response is due to a change in the expected response schema, possibly caused by a recent deployment to the payments-api or a misconfiguration in the checkout-api's parsing logic.
- caused_by_latest_deploy: False
- failing: root_cause_category (got bad_config, expected code_bug); calibration (confidence 0.80, want < 0.7 when wrong)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T062424/traces/checkout_upstream_contract-2.jsonl`
### inventory_memory_leak #1
- said: [resource_exhaustion, 0.40] The OOMKilled errors are likely due to memory constraints, possibly caused by a recent change in the deployment that increased memory usage or reduced memory limits.
- caused_by_latest_deploy: False
- failing: key_fact_recall (missing ['cache', 'v3.1.0']); next_step_relevance (no match); calibration (confidence 0.40, want >= 0.5 when correct)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T062424/traces/inventory_memory_leak-1.jsonl`
### inventory_memory_leak #2
- said: [resource_exhaustion, 0.40] The inventory-service is being OOMKilled due to memory limits being exceeded, possibly due to an increase in memory usage not captured by the metrics or a configuration issue that was not detected during the deployment.
- caused_by_latest_deploy: False
- failing: key_fact_recall (missing ['cache', 'v3.1.0']); next_step_relevance (no match); calibration (confidence 0.40, want >= 0.5 when correct)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T062424/traces/inventory_memory_leak-2.jsonl`
### inventory_memory_leak #3
- said: [resource_exhaustion, 0.40] The inventory-service is being OOMKilled due to memory limits being exceeded, which may be due to a configuration issue or an increase in workload that was not accounted for in the memory allocation.
- caused_by_latest_deploy: False
- failing: key_fact_recall (missing ['cache', 'v3.1.0']); next_step_relevance (no match); calibration (confidence 0.40, want >= 0.5 when correct)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T062424/traces/inventory_memory_leak-3.jsonl`
### orders_upstream_dependency #1
- said: [resource_exhaustion, 0.90] The inventory-service experienced database connection pool exhaustion, leading to upstream timeouts for the orders-api, which resulted in HTTP 500 errors.
- caused_by_latest_deploy: False
- failing: root_cause_category (got resource_exhaustion, expected dependency_failure); calibration (confidence 0.90, want < 0.7 when wrong)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T062424/traces/orders_upstream_dependency-1.jsonl`
