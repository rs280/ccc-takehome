# Runbook: Dependency failures

- Upstream timeouts in your service logs usually mean the dependency is degraded. Check the
  dependency's own logs and metrics.
- Check whether the failure began before or after your own most recent deploy.
- Escalate to the owning team (see service catalog) and share the start time and error signature.
- Mitigations: circuit breakers, serving cached or degraded responses, shedding load.
- Common causes: database connection pool exhaustion, slow queries, failed replicas.
