# Eval results 20261017T023044

Model `incident-qwen3`, k=3, critic=on.

| scenario | pass | root cause category | deploy attribution | key fact recall | citation grounding | tool coverage | next step relevance | calibration | avg s | tools |
|---|---|---|---|---|---|---|---|---|---|---|
| ambiguous_low_signal | 0/3 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 223 | 7.0 |
| auth_cert_expiry | 2/3 | 1.00 | 1.00 | 1.00 | 0.92 | 1.00 | 1.00 | 1.00 | 331 | 8.0 |
| checkout_bad_config | 3/3 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 297 | 9.0 |
| checkout_upstream_contract | 3/3 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 550 | 12.0 |
| inventory_memory_leak | 0/3 | 0.67 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.33 | 572 | 11.0 |
| orders_upstream_dependency | 2/3 | 0.67 | 1.00 | 0.83 | 0.94 | 1.00 | 1.00 | 0.67 | 662 | 11.3 |
| payments_missing_migration | 3/3 | 1.00 | 1.00 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 | 457 | 10.0 |
| search_disk_watermark | 2/3 | 1.00 | 0.67 | 1.00 | 0.93 | 1.00 | 1.00 | 1.00 | 566 | 8.0 |
| search_latency_regression | 3/3 | 1.00 | 1.00 | 0.83 | 1.00 | 1.00 | 1.00 | 1.00 | 564 | 9.3 |
| worker_oom_crashloop | 3/3 | 1.00 | 1.00 | 0.83 | 1.00 | 1.00 | 1.00 | 1.00 | 440 | 8.0 |
| **overall** | **21/30** | 0.83 | 0.97 | 0.80 | 0.98 | 1.00 | 0.90 | 0.90 | 466 | 9.4 |

Pass rate: 70% of runs. Scenarios passing on all 3 attempts (pass^k): 5/10.

## Failures

### ambiguous_low_signal #1
- said: [dependency_failure, 0.40] The connection resets and timeouts in the profile-api service are caused by the avatar-cdn dependency, which has a known issue with connection resets and timeouts.
- caused_by_latest_deploy: False
- failing: root_cause_category (got dependency_failure, expected unknown)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T023044/traces/ambiguous_low_signal-1.jsonl`
### ambiguous_low_signal #2
- said: [dependency_failure, 0.40] The errors in the profile-api service are caused by the avatar-cdn dependency, which is known to occasionally cause connection resets and timeouts, rather than the latest deploy.
- caused_by_latest_deploy: False
- failing: root_cause_category (got dependency_failure, expected unknown)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T023044/traces/ambiguous_low_signal-2.jsonl`
### ambiguous_low_signal #3
- said: [dependency_failure, 0.40] The errors in the profile-api service are likely due to the avatar-cdn dependency experiencing connection resets and timeouts, which are within its known behavior.
- caused_by_latest_deploy: False
- failing: root_cause_category (got dependency_failure, expected unknown)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T023044/traces/ambiguous_low_signal-3.jsonl`
### auth_cert_expiry #2
- said: [certificate_expiry, 0.90] The TLS certificate for the client 'auth-api-idp-mtls' expired, and the renewal process failed, causing a TLS handshake failure with the identity-provider, which led to 500 errors in the auth-api service.
- caused_by_latest_deploy: False
- failing: citation_grounding (E7: unsupported ['500'])
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T023044/traces/auth_cert_expiry-2.jsonl`
### inventory_memory_leak #1
- said: [unknown, 0.40] The OOMKilled errors are likely due to an existing memory configuration issue or an external factor, not the latest deploy. The memory limit may have been exceeded due to increased load or a misconfiguration.
- caused_by_latest_deploy: False
- failing: root_cause_category (got unknown, expected resource_exhaustion); key_fact_recall (missing ['cache', 'v3.1.0']); next_step_relevance (no match)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T023044/traces/inventory_memory_leak-1.jsonl`
### inventory_memory_leak #2
- said: [resource_exhaustion, 0.40] The OOMKilled errors are likely due to the container exceeding its memory limit, possibly due to an existing configuration or resource constraint that was not previously causing the issue.
- caused_by_latest_deploy: False
- failing: key_fact_recall (missing ['cache', 'v3.1.0']); next_step_relevance (no match); calibration (confidence 0.40, want >= 0.5 when correct)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T023044/traces/inventory_memory_leak-2.jsonl`
### inventory_memory_leak #3
- said: [resource_exhaustion, 0.40] The inventory-service is being OOMKilled due to memory limits being exceeded, possibly due to an increase in workload or a memory leak, which started before the latest deploy.
- caused_by_latest_deploy: False
- failing: key_fact_recall (missing ['cache', 'v3.1.0']); next_step_relevance (no match); calibration (confidence 0.40, want >= 0.5 when correct)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T023044/traces/inventory_memory_leak-3.jsonl`
### orders_upstream_dependency #1
- said: [resource_exhaustion, 0.90] The inventory-service is experiencing database connection pool exhaustion, which is causing upstream timeouts in the orders-api, resulting in HTTP 500 errors.
- caused_by_latest_deploy: False
- failing: root_cause_category (got resource_exhaustion, expected dependency_failure); calibration (confidence 0.90, want < 0.7 when wrong)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T023044/traces/orders_upstream_dependency-1.jsonl`
### search_disk_watermark #3
- said: [dependency_failure, 0.80] The deployment of search-api version v5.2.1 triggered an increase in error rate due to Elasticsearch shards being unassigned, caused by disk usage exceeding flood stage thresholds on node es-data-2.
- caused_by_latest_deploy: True
- failing: deploy_attribution (got True, expected False); safe_next_steps ('Roll back the latest deployment (dep-7699) to restore Elasticsearch functionality and reduce 500 errors.' (roll back))
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T023044/traces/search_disk_watermark-3.jsonl`
