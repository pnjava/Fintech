# Implementation Checklist

## Step 0: Read Spec
- [x] Read repository root README.md.
- [ ] Extract features A–G details into tasks.

## Step 1: Project Scaffold
- [ ] Create project structure directories and files as specified.
- [ ] Add pyproject.toml with dependencies.
- [ ] Add Makefile with required targets.
- [ ] Add docker-compose.yml with services.
- [ ] Add pre-commit configuration.

## Step 2: Database & Models
- [ ] Implement SQLAlchemy models for Tenant, User, Shareholder, EmployeePlan, Transaction, AuditLog, ProxyBallot.
- [ ] Create Alembic migrations enforcing tenant isolation and constraints.
- [ ] Add seed script for demo tenant and users.

## Step 3: Auth & RBAC
- [ ] Implement /auth/login and /auth/refresh with RS256 JWT.
- [ ] Add token revocation list and refresh rotation.
- [ ] Implement RBAC guard/decorator with tests.
- [ ] Ensure all queries enforce tenant isolation.

## Step 4: Shareholder Management
- [ ] CRUD endpoints for Shareholder with tests.
- [ ] Dividend calculation and scheduling with worker queue.
- [ ] Proxy voting module with reporting.

## Step 5: Plan Sponsor Module
- [x] Enrollment and contribution endpoints with SERIALIZABLE isolation.
- [x] Rust vesting service with client wrapper.
- [x] Monthly job to update vested balances.

## Step 6: Financial Transactions
- [ ] Disbursement API with state machine and mock ACH adapter.
- [ ] Audit logging middleware writing to structured logs and S3.

## Step 7: Data Pipelines
- [ ] Upload API storing files to S3 and enqueue messages.
- [ ] Async validator worker with schema validation and dead-letter.
- [ ] Kafka event producer/consumer with reporting tables.

## Step 8: Observability & Compliance
- [ ] Prometheus metrics and /metrics endpoint.
- [ ] OpenTelemetry tracing across API and workers.
- [ ] Data retention job and Terraform/S3 lifecycle stubs.
- [ ] Grafana dashboards and runbooks.

## Step 9: DevOps & Delivery
- [ ] Terraform stubs (VPC, RDS, EKS) with docs.
- [ ] Helm chart skeleton with blue/green toggle.
- [ ] GitHub Actions workflow covering lint/typecheck/tests/build/helm dry-run.

## Step 10: APIs & Docs
- [ ] OpenAPI schema exposure and Swagger UI.
- [ ] Health/readiness endpoints.
- [ ] ADRs, diagrams, runbooks.

## Step 11: Test Strategy
- [ ] Unit tests with >=80% coverage.
- [ ] Integration tests for auth, CRUD, disbursement, uploads.
- [ ] Load test stubs and notes.

## Step 12: Final Polish
- [ ] Update checklist reflecting completed tasks.
- [ ] Update root README with run instructions.
- [ ] Create CHANGELOG.md and CONTRIBUTING.md.
- [ ] Ensure pre-commit and CI succeed.
