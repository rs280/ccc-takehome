# Runbook: Latency regression

1. Check p99 latency and CPU over time; find the step change.
2. Correlate with deploys and config changes (cache settings, timeouts, pool sizes, feature flags).
3. Look for slow query / cache miss logs. Removing or disabling a cache shifts all load to the
   backing store and typically multiplies latency.
4. Mitigate by rolling back or re-enabling the cache, then investigate.
