# Eval results 20261014T201633

Model `incident-qwen3`, k=1, critic=on.

| scenario | pass | root cause category | deploy attribution | key fact recall | citation grounding | tool coverage | next step relevance | calibration | avg s | tools |
|---|---|---|---|---|---|---|---|---|---|---|
| ambiguous_low_signal | 0/1 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 205 | 9.0 |
| auth_cert_expiry | 0/1 | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 221 | 11.0 |
| checkout_bad_config | 0/1 | 1.00 | 1.00 | 1.00 | 0.75 | 1.00 | 1.00 | 1.00 | 293 | 15.0 |
| orders_upstream_dependency | 0/1 | 1.00 | 0.00 | 0.50 | 0.80 | 1.00 | 1.00 | 1.00 | 264 | 11.0 |
| payments_missing_migration | 0/1 | 1.00 | 1.00 | 0.50 | 0.75 | 1.00 | 1.00 | 1.00 | 272 | 12.0 |
| search_latency_regression | 0/1 | 0.00 | 1.00 | 0.50 | 0.83 | 1.00 | 1.00 | 0.00 | 262 | 8.0 |
| worker_oom_crashloop | 1/1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 253 | 13.0 |
| **overall** | **1/7** | 0.71 | 0.71 | 0.79 | 0.88 | 1.00 | 1.00 | 0.71 | 253 | 11.3 |

Pass rate: 14% of runs. Scenarios passing on all 1 attempts (pass^k): 1/7.

## Failures

### ambiguous_low_signal #1
- said: [dependency_failure, 0.80] The recent deployment of profile-api (v2.0.7) did not directly cause the errors, but the errors are likely due to an issue with the avatar-cdn dependency, which the profile-api service proxies images from.
- deploy_related: False
- failing: root_cause_category (got dependency_failure, expected unknown); calibration (confidence 0.80, want <= 0.5)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261014T201633/traces/ambiguous_low_signal-1.jsonl`
### auth_cert_expiry #1
- said: [certificate_expiry, 0.90] The 500 errors in auth-api are caused by an expired certificate 'auth-api-idp-mtls' used for TLS handshake with the identity-provider, which expired at 2026-10-14T10:00:00Z. The certificate renewal failed due to the issuer 'internal-ca' being unreachable.
- deploy_related: True
- failing: deploy_attribution (got True, expected False)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261014T201633/traces/auth_cert_expiry-1.jsonl`
### checkout_bad_config #1
- said: [bad_config, 0.90] The HTTP 500 errors in checkout-api are caused by a missing 'DATABASE_POOL_SIZE' configuration, which was introduced in the deployment of version v2.4.1. The change to config loading in the deployment caused the service to fail to read the required configuration variable, leading to unhandled exceptions.
- deploy_related: True
- failing: citation_grounding (E7: unsupported ['checkout-api', 'configuration', 'deployment', 'experienced'])
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261014T201633/traces/checkout_bad_config-1.jsonl`
### orders_upstream_dependency #1
- said: [dependency_failure, 0.80] The deployment of version v1.9.3 (dep-7716) caused the inventory-service to become unresponsive, leading to timeouts and HTTP 500 errors in the orders-api.
- deploy_related: True
- failing: deploy_attribution (got True, expected False)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261014T201633/traces/orders_upstream_dependency-1.jsonl`
### payments_missing_migration #1
- said: [schema_migration, 0.90] The deployment of version v3.8.0 introduced a new column 'refund_reason' in the 'refunds' table, but the corresponding database migration was skipped, leading to the 'undefined column' error when the code tried to access it.
- deploy_related: True
- failing: citation_grounding (E8: unsupported ['deployment', 'functionality', 'introduced', 'potentially'])
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261014T201633/traces/payments_missing_migration-1.jsonl`
### search_latency_regression #1
- said: [code_bug, 0.90] The removal of the Redis result cache in deployment dep-7709 caused a shift in load to Elasticsearch, leading to slow queries and timeouts.
- deploy_related: True
- failing: root_cause_category (got code_bug, expected performance_regression); calibration (confidence 0.90, want < 0.7 when wrong)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261014T201633/traces/search_latency_regression-1.jsonl`
