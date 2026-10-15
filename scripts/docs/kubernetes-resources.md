# Kubernetes resource requests and limits

Limits are set in `deploy/values.yaml` under `resources.limits`. Memory limits are hard: exceeding
them kills the container. Peak usage for batch workloads scales with batch size. Keep at least 30%
headroom over observed peak.
