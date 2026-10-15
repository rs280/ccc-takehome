# Runbook: Certificate rotation

- Service mTLS client certificates are issued by cert-manager from issuer `internal-ca` and renew
  automatically 72h before expiry.
- If renewal fails, cert-manager logs warnings. Once expired, TLS handshakes fail with
  `CERTIFICATE_VERIFY_FAILED certificate has expired`.
- Fix: restore issuer connectivity and force renewal with
  `cmctl renew <certificate-name> -n <namespace>`, then restart the service pods to reload.
- Add alerting on certificate expiry under 7 days.
