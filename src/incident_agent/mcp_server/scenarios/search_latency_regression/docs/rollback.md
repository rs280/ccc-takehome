# Runbook: Rolling back a deployment

- Use `deployctl rollback <service> --to <previous-version>`. Rollbacks take about 3 minutes.
- Rolling back is safe for stateless changes. If the release included a database migration that
  already ran, check the migration is backward compatible before rolling back code.
- After rollback, confirm the error rate returns to baseline within 10 minutes, then open an
  incident ticket with the failing deploy id.
- Rolling back a service that is failing because of a dependency does not help and wastes time.
