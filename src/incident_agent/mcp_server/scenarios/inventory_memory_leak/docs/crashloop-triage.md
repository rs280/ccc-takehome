# Runbook: CrashLoopBackOff

1. Check container termination reason. `OOMKilled` / exit code 137 means the container exceeded its
   memory limit.
2. Compare memory usage against the limit and check for recent changes to resource limits or
   workload size (batch sizes, concurrency).
3. Mitigate by restoring the previous memory limit or reducing batch size, then right-size based on
   observed peak usage plus headroom.
