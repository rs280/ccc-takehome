# Runbook: Database migrations

- Migrations live in `migrations/` and run in the `db-migrate` pipeline step before deploy.
- Production migrations require manual approval. If approval is not granted the step is skipped
  and the deploy still proceeds, which can ship code that expects schema that does not exist yet.
- Symptom: `UndefinedColumn` / `relation does not exist` errors right after a deploy.
- Fix: run the pending migration with `deployctl migrate <service> --env prod` (after approval),
  or roll back the code. Prefer expand/contract migrations so code and schema can deploy
  independently.
