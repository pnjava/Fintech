# ADR 0002: CI/CD Pipeline Strategy

## Status
Accepted

## Context
To support continuous delivery and quality gates, the project requires a deterministic pipeline covering linting, typing, testing, container builds, and release validation. The previous CI workflow only executed basic linting and pytest runs.

## Decision
- Consolidate CI into a GitHub Actions workflow that:
  - installs dependencies once,
  - runs Ruff/Black/Isort linting and MyPy type checks,
  - executes unit tests with coverage and integration tests after a `docker compose up`,
  - builds the production container image, and
  - performs a Helm `template --dry-run` validation using the repository chart.
- Enforce `pytest --cov=app --cov-report=term-missing` with a minimum 80% threshold.
- Provide Helm and Terraform stubs in `infra/` with documentation to unblock platform automation.

## Consequences
- CI runtime increases slightly due to container builds and Helm checks but provides higher confidence.
- Local developers can mirror CI by invoking the documented Makefile commands.
- Helm chart and Terraform modules must remain syntactically valid to keep CI green.
