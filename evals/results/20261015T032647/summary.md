# Eval results 20261015T032647

Model `openai/gpt-oss-20b`, k=1, critic=on.

| scenario | pass | root cause category | deploy attribution | key fact recall | citation grounding | tool coverage | next step relevance | calibration | avg s | tools |
|---|---|---|---|---|---|---|---|---|---|---|
| ambiguous_low_signal | 0/1 | 1.00 | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 175 | 10.0 |
| auth_cert_expiry | 0/1 | 0.00 | 1.00 | 0.50 | 1.00 | 0.50 | 0.00 | 0.00 | 171 | 9.0 |
| checkout_bad_config | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 123 | 8.0 |
| orders_upstream_dependency | 0/1 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 216 | 12.0 |
| payments_missing_migration | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 213 | 11.0 |
| search_latency_regression | 0/1 | 0.00 | 1.00 | 1.00 | 0.80 | 1.00 | 1.00 | 0.00 | 167 | 11.0 |
| worker_oom_crashloop | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 171 | 11.0 |
| **overall** | **3/7** | 0.57 | 1.00 | 0.79 | 0.97 | 0.93 | 0.86 | 0.57 | 177 | 10.3 |

Pass rate: 43% of runs. Scenarios passing on all 1 attempts (pass^k): 3/7.

## Failures

### ambiguous_low_signal #1
- said: [unknown, 0.30] Intermittent avatar‑cdn timeouts or another external dependency causing occasional 502/504 responses
- caused_by_latest_deploy: False
- failing: key_fact_recall (missing ['ConnectionResetError'])
- failed specialists: logs
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T032647/traces/ambiguous_low_signal-1.jsonl`
### auth_cert_expiry #1
- said: [dependency_failure, 0.75] The identity‑provider dependency became unhealthy or returned errors, causing auth‑api to fail all login requests.
- caused_by_latest_deploy: False
- failing: root_cause_category (got dependency_failure, expected certificate_expiry); tool_coverage (missing ['search_logs|get_error_summary']); next_step_relevance (no match); calibration (confidence 0.75, want < 0.7 when wrong)
- failed specialists: logs
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T032647/traces/auth_cert_expiry-1.jsonl`
### orders_upstream_dependency #1
- said: [resource_exhaustion, 0.90] inventory‑service’s database connection pool was exhausted, causing timeouts that propagated to orders‑api and produced 500 errors.
- caused_by_latest_deploy: False
- failing: root_cause_category (got resource_exhaustion, expected dependency_failure); calibration (confidence 0.90, want < 0.7 when wrong)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T032647/traces/orders_upstream_dependency-1.jsonl`
### search_latency_regression #1
- said: [bad_config, 0.90] The deployment disabled the Redis result cache (REDIS_CACHE_ENABLED=false), causing every search request to bypass the cache and hit Elasticsearch. The sudden 100% load on Elasticsearch produced slow queries and timeouts, raising error rate and p99 latency.
- caused_by_latest_deploy: True
- failing: root_cause_category (got bad_config, expected performance_regression); calibration (confidence 0.90, want < 0.7 when wrong)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261015T032647/traces/search_latency_regression-1.jsonl`
