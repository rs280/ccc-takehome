# Runbook: Elevated HTTP 5xx errors

1. Confirm scope: which endpoints, which services, since when. Compare error rate against the
   previous 1-2 hours of baseline.
2. Correlate the start time with recent deployments of the service AND its dependencies. A deploy
   is only a suspect if errors started at or after it. Errors that start before a deploy point
   elsewhere.
3. Group errors by signature (exception type and message). A single new signature that appears at
   deploy time usually means a code or config change. Timeouts against a dependency usually mean
   the dependency is unhealthy.
4. If a recent deploy is the likely cause and customer impact is high, roll back first and debug
   after (see rollback runbook).
5. If a dependency is failing, page the owning team and consider enabling degraded mode or
   circuit breakers instead of rolling back your own service.
