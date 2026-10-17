# Eval results 20261017T020733

Model `openai/gpt-oss-120b`, k=1, critic=on.

| scenario | pass | root cause category | deploy attribution | key fact recall | citation grounding | tool coverage | next step relevance | calibration | avg s | tools |
|---|---|---|---|---|---|---|---|---|---|---|
| checkout_upstream_contract | 0/1 | 0.00 | 1.00 | 0.50 | 1.00 | 1.00 | 1.00 | 0.00 | 208 | 15.0 |
| inventory_memory_leak | 1/1 | 1.00 | 1.00 | 0.50 | 1.00 | 1.00 | 0.00 | 0.00 | 220 | 14.0 |
| search_disk_watermark | 1/1 | 1.00 | 1.00 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 | 224 | 12.0 |
| **overall** | **2/3** | 0.67 | 1.00 | 0.50 | 1.00 | 1.00 | 0.67 | 0.33 | 217 | 13.7 |

Pass rate: 67% of runs. Scenarios passing on all 1 attempts (pass^k): 2/3.

## Failures

### checkout_upstream_contract #1
- said: [bad_config, 0.92] A payments‑api deployment renamed the field 'amount_cents' to 'amount' in its JSON response. checkout‑api still expects 'amount_cents', causing a KeyError and HTTP 500 responses.
- caused_by_latest_deploy: False
- failing: root_cause_category (got bad_config, expected code_bug); calibration (confidence 0.92, want < 0.7 when wrong)
- trace: `/Users/rishabh/dev/ccc-takehome/evals/results/20261017T020733/traces/checkout_upstream_contract-1.jsonl`
