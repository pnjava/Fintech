# Shareholder & Plan Sponsor Financial Product Platform (Equiniti)

> **Epic**: Build a cloud‑native, multi‑tenant SaaS platform for **Issuer Central** and **Employee Plan Sponsor** use cases — covering shareholder records, plan enrollment, contributions, vesting, distributions, proxy voting, reporting, and compliance.

This README is designed to be **Codex/Copilot/Amazon Q friendly**: every story includes *clear acceptance criteria* and *ready‑to‑paste prompts* to generate code in Python (FastAPI) or Rust (Axum).

---

## 1) Problem Statement & Goals

**Problems we solve**
- Fragmented shareholder and plan data across systems.
- Manual calculations for dividends, vesting, and distributions.
- Slow onboarding and error‑prone bulk uploads.
- Limited observability, compliance, and auditability.

**Goals**
- Multi‑tenant platform (Issuer vs Plan Sponsor) with strong RBAC and SSO.
- Async pipelines for data ingestion/validation and reporting.
- Bank/ACH integrations for secure, auditable disbursements.
- First‑class observability, logging, and compliance by design.

**Non‑Goals (Phase‑1)**
- Real money movement to production processors (use mock ACH in Phase‑1).
- Real proxy tabulation for national elections (Phase‑1 will support basic proxy capture).

---

## 2) Architecture (Reference)

- **API Services:** FastAPI (Python) or Axum (Rust) for multi‑tenant REST/gRPC.
- **AuthN/Z:** JWT + RBAC; SAML/OIDC integration (Okta/Azure AD) behind an adapter.
- **Data:** Postgres (OLTP), S3 (raw uploads & audit), optional Redshift for reporting.
- **Async:** SQS/Kafka for ingestion and fan‑out; workers (Celery/Redis or Rust tokio).
- **Observability:** OpenTelemetry traces, Prometheus metrics, ELK/Grafana dashboards.
- **Infra:** Terraform + Helm on EKS; GitHub Actions CI/CD; blue/green deploys.

```
[Client/UI] -> [API Gateway] -> [Auth] -> [IssuerCentral API] -> [Postgres]
                                         \-> [PlanSponsor API] -> [Postgres]
Uploads -> [S3] -> [Queue/Kafka] -> [Validator Worker] -> [OLTP/Reporting]
Disburse -> [Disburse API] -> [Mock ACH Adapter] -> [Audit Log + Events]
```

---

## 3) Tech Stack

- **Languages:** Python 3.11+ (FastAPI, Pydantic, SQLAlchemy), Rust 1.79+ (Axum, sqlx).
- **Data Stores:** Postgres 15, S3, optional Redis for queues/caching.
- **Messaging:** SQS/Kafka, EventBridge (optional).
- **Infra:** Terraform, Helm, EKS, GitHub Actions.
- **Obs:** OpenTelemetry, Prometheus, Grafana, ELK.

---

## 4) Domain Model (Phase‑1)

- **Tenant**(id, name, type: `ISSUER|SPONSOR`, status)
- **User**(id, tenant_id, email, role: `ADMIN|EMPLOYEE|COMPLIANCE|OPS`)
- **Shareholder**(id, tenant_id, external_ref, name, contact, holdings)
- **EmployeePlan**(id, tenant_id, employee_id, plan_type, contributions, vesting_schedule)
- **Transaction**(id, tenant_id, amount, currency, type:`DIVIDEND|DISBURSE|CONTRIBUTION`, status, created_at)
- **AuditLog**(id, tenant_id, actor_id, action, resource, payload, ts)

---

## 5) API Sketch (selected)

```
POST   /auth/login
POST   /tenants
POST   /users
POST   /shareholders
GET    /shareholders/{id}
POST   /dividends/schedule
POST   /plans/enroll
POST   /plans/{id}/contributions
POST   /transactions/disburse
POST   /uploads/shareholders (multipart -> S3 -> queue)
GET    /reports/holdings
```

---

## 6) Backlog — Stories & Tasks (Codex‑ready)

Each story lists **Acceptance Criteria (AC)** and **Prompts** you can paste into Copilot/Q.

### A. Identity & Multitenancy

**A1. JWT Auth with Refresh Tokens**
- **AC**
  - `/auth/login` issues access+refresh tokens (RS256).
  - Tokens embed `tenant_id`, `role`, `sub`.
  - Refresh flow rotates tokens; revocation list supported.
- **Prompt (FastAPI)**
  - Create FastAPI endpoints for `/auth/login` and `/auth/refresh` using `python-jose` RS256 JWTs. Include Pydantic models, password hashing, and a token blacklist table in Postgres via SQLAlchemy.

**A2. RBAC Middleware**
- **AC**
  - Decorator/guard enforces role per route.
  - Unit tests for ADMIN vs EMPLOYEE access.
- **Prompt (Rust/Axum)**
  - Implement an Axum middleware that extracts a JWT from `Authorization: Bearer`, validates RS256, and denies requests lacking required roles. Provide unit tests with a mock JWKS.

**A3. Tenant Isolation**
- **AC**
  - All queries filter by `tenant_id`.
  - Migrations add `tenant_id` and FKs; unique `(tenant_id, external_ref)`.
- **Prompt**
  - Write SQLAlchemy models for Tenant, User, Shareholder with `tenant_id` column and alembic migration enforcing FK/unique constraints.

---

### B. Shareholder Management

**B1. CRUD Shareholder**
- **AC**
  - `POST /shareholders` validates payload, sets `tenant_id`.
  - `GET /shareholders/{id}` returns 404 if cross‑tenant.
  - Unit tests serialize/deserialize with Pydantic.
- **Prompt**
  - Implement FastAPI routes for Shareholder CRUD with SQLAlchemy models and Pydantic schemas; include tests with `pytest` and an in‑memory Postgres (pytest‑postgres).

**B2. Dividend Calculation & Scheduling**
- **AC**
  - Pure function `calculate_dividend(holdings, rate)`.
  - `POST /dividends/schedule` enqueues per‑holder events.
  - Worker writes `Transaction` rows with status `PENDING`.
- **Prompt**
  - Create a Celery worker that consumes dividend schedule messages from SQS and creates Transaction rows. Provide retry/backoff, idempotency key, and structured logs.

**B3. Proxy Voting (Basic)**
- **AC**
  - Create `ProxyBallot(meeting_id, shareholder_id, choices)`.
  - `POST /proxy/votes` persists ballot; one vote per holder per meeting.
- **Prompt**
  - Design a FastAPI endpoint and SQLAlchemy models for proxy ballots with unique composite constraint. Add an admin report endpoint summarizing counts per choice.

---

### C. Plan Sponsor Module

**C1. Employee Plan Enrollment**
- **AC**
  - `POST /plans/enroll` validates employee/tenant and creates `EmployeePlan`.
- **Prompt**
  - Implement enrollment API with Pydantic validation and alembic migration for EmployeePlan. Include 3 example cURL requests in README.

**C2. Contribution Tracking**
- **AC**
  - `POST /plans/{id}/contributions` appends contribution with timestamp; updates running balance atomically.
- **Prompt**
  - Add contribution endpoint using SQLAlchemy transaction with SERIALIZABLE isolation; include unit tests for concurrent updates.

**C3. Vesting Schedule Computation**
- **AC**
  - Support cliff + graded schedules.
  - Scheduled job updates `vested_balance` monthly.
- **Prompt (Rust)**
  - Write a Rust module to compute vested balances given cliff/graded rules. Include doc tests and examples.

---

### D. Financial Transactions

**D1. Disbursement API + Mock ACH Adapter**
- **AC**
  - `POST /transactions/disburse` validates KYC flag, creates txn, calls adapter, writes `AuditLog`.
  - Status transitions: `PENDING->SENT->SETTLED|FAILED`.
- **Prompt**
  - Create a disbursement service layer in FastAPI that calls a mock ACH adapter (HTTP). Implement a state machine and persist transitions with optimistic locking.

**D2. Audit Logging Middleware**
- **AC**
  - Logs actor, action, resource, request id; JSON structured logs.
  - PII masked; stored in append‑only S3 key (daily partitioned).
- **Prompt**
  - Add a Starlette middleware to write structured JSON logs to file and S3. Include sampling and correlation ids via `X-Request-ID`.

---

### E. Data Pipelines

**E1. Upload → S3 → Queue → Validator**
- **AC**
  - `POST /uploads/shareholders` accepts CSV/JSON, stores to S3, enqueues message.
  - Worker validates rows against JSON Schema; bad rows to dead‑letter.
- **Prompt**
  - Implement an async worker (Python asyncio) that pulls messages from SQS, downloads file from S3, validates with `jsonschema`, and writes valid rows to Postgres.

**E2. Event Bus & Reporting Sync**
- **AC**
  - Emit Kafka/SNS events for `Transaction` changes.
  - Consumer populates reporting tables.
- **Prompt**
  - Write a Kafka producer for transaction events and a consumer that upserts into a reporting table. Provide docker-compose for local Kafka.

---

### F. Observability & Compliance

**F1. Metrics & Tracing**
- **AC**
  - Prometheus metrics for latency, rate, errors, queue depth.
  - OpenTelemetry traces across API and workers (traceparent propagation).
- **Prompt**
  - Instrument FastAPI with Prometheus and OpenTelemetry. Expose `/metrics` and export traces to OTLP collector.

**F2. Data Retention Job**
- **AC**
  - Daily job purges PII per policy; audit log kept N years in Glacier.
- **Prompt**
  - Create a scheduled job (K8s CronJob) that applies data retention rules in Postgres and lifecycles S3 objects to Glacier.

---

## 7) Data Contracts (JSON Schema — sample)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ShareholderUpload",
  "type": "object",
  "properties": {
    "external_ref": {"type":"string"},
    "name": {"type":"string"},
    "email": {"type":"string","format":"email"},
    "holdings": {"type":"number","minimum":0}
  },
  "required": ["external_ref","name","holdings"]
}
```

---

## 8) Local Dev (Quickstart)

```bash
# Python
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn[standard] sqlalchemy psycopg2-binary pydantic[dotenv] alembic
uvicorn app.main:app --reload

# Rust
cargo new issuer-central-api && cd issuer-central-api
cargo add axum tokio serde serde_json jsonwebtoken sqlx --features runtime-tokio
cargo run
```

---

## 9) Example Prompts (copy/paste)

- Generate a FastAPI router for `/shareholders` with Pydantic models and SQLAlchemy, including unit tests using pytest.
- Write a Celery task that processes dividend events from SQS and persists Transaction rows with idempotency keys.
- Implement an Axum middleware to enforce RBAC using roles in a JWT and return 403 for insufficient privileges.

---

## 10) Definition of Done (DoD)

- All acceptance criteria pass.
- Unit tests ≥ 80% for service modules; integration tests for critical flows.
- Linting/formatting clean; CI green.
- Traces/metrics visible in Grafana; logs searchable in ELK.
- Security review (JWT, PII masking, RBAC) completed.

---

## 11) Future Work (Phase‑2)

- Real ACH/Payments gateway integration.
- Proxy tabulation vendor integration.
- Advanced analytics pipelines (Redshift/EMR).
- Fine‑grained data entitlements per field/object.
