# Configuration management

- Service configuration is provided as environment variables via `deploy/values.yaml` per
  environment. Code changes that rename or add required env vars must be shipped together with the
  matching values change, otherwise the new version fails at runtime.
- Required settings are read lazily on first use, so a missing variable usually surfaces as a
  `KeyError` on the first request that needs it rather than at startup.
- To hotfix, add the variable with `deployctl env set <service> KEY=VALUE` and restart, or roll back.
