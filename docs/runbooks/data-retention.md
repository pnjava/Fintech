# Data Retention Runbook

## Overview
The data retention worker purges aged audit logs and financial transactions from Postgres and applies S3 lifecycle policies for uploaded shareholder artifacts. Metrics are emitted through Prometheus counters and tracing is forwarded via OpenTelemetry.

## Dashboards & Alerts
- **Grafana**: `docs/dashboards/data-retention-dashboard.json` visualises hourly deletions and job duration.
- **Alerts**: Configure warning when `data_retention_transactions_deleted_total` remains flat for 24h or the worker stops reporting traces.

## Run Procedure
1. **Validate configuration**
   - Retention windows are set via environment variables: `AUDIT_LOG_RETENTION_DAYS`, `TRANSACTION_RETENTION_DAYS`, `UPLOAD_RETENTION_DAYS`.
   - Ensure the OTLP endpoint (`OTEL_EXPORTER_ENDPOINT`) matches the collector deployment.
2. **Start the worker**
   ```bash
   python -m workers.data_retention.main
   ```
   The worker logs summary statistics every cycle and exports metrics at `/metrics` on the main API service.
3. **Verify impact**
   - Check Prometheus counters `data_retention_audit_logs_deleted_total` and `data_retention_transactions_deleted_total` incrementing.
   - Inspect spans in the tracing backend for `data_retention.cycle` to ensure context propagation.

## Failure Recovery
- If the worker crashes, restart the process and review logs for database connectivity errors.
- For S3 lifecycle issues, apply the generated policy from `DataRetentionService.build_s3_lifecycle_policy()` using Terraform or the AWS CLI.
- Re-run the worker in catch-up mode by temporarily lowering `DATA_RETENTION_INTERVAL_SECONDS` to 300 seconds.

## Escalation
- If deletions stall for more than one cycle despite backlog, escalate to the database administrator with the latest job logs and metrics snapshot.
