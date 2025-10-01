"""Schema integrity tests for core models."""
from __future__ import annotations

from pathlib import Path

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
alembic = pytest.importorskip("alembic")
alembic_command = pytest.importorskip("alembic.command")
alembic_config_module = pytest.importorskip("alembic.config")

sa = sqlalchemy
command = alembic_command
Config = alembic_config_module.Config


@pytest.fixture(scope="session")
def alembic_config(tmp_path_factory: pytest.TempPathFactory) -> Config:
    """Provide Alembic config bound to a temporary SQLite database."""

    project_root = Path(__file__).resolve().parents[2]
    db_path = tmp_path_factory.mktemp("db") / "test.db"

    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    config.set_main_option("script_location", str(project_root / "migrations"))
    return config


@pytest.fixture(scope="session")
def migrated_engine(alembic_config: Config):
    """Run migrations against SQLite and yield an engine."""

    command.upgrade(alembic_config, "head")
    engine = sa.create_engine(alembic_config.get_main_option("sqlalchemy.url"))
    try:
        yield engine
    finally:
        engine.dispose()


def test_tables_exist(migrated_engine: sa.Engine) -> None:
    inspector = sa.inspect(migrated_engine)
    tables = set(inspector.get_table_names())
    expected = {
        "tenants",
        "users",
        "shareholders",
        "employee_plans",
        "transactions",
        "audit_logs",
        "proxy_ballots",
    }
    assert expected.issubset(tables)


@pytest.mark.parametrize(
    "table_name",
    [
        "users",
        "shareholders",
        "employee_plans",
        "transactions",
        "audit_logs",
        "proxy_ballots",
    ],
)
def test_tenant_id_present(table_name: str, migrated_engine: sa.Engine) -> None:
    inspector = sa.inspect(migrated_engine)
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    assert "tenant_id" in columns


def test_foreign_keys_enforced(migrated_engine: sa.Engine) -> None:
    inspector = sa.inspect(migrated_engine)
    fk_expectations = {
        "users": {"tenant_id": "tenants"},
        "shareholders": {"tenant_id": "tenants"},
        "employee_plans": {"tenant_id": "tenants", "shareholder_id": "shareholders"},
        "transactions": {
            "tenant_id": "tenants",
            "shareholder_id": "shareholders",
            "plan_id": "employee_plans",
        },
        "audit_logs": {"tenant_id": "tenants", "actor_id": "users"},
        "proxy_ballots": {"tenant_id": "tenants", "shareholder_id": "shareholders"},
    }

    for table, expected in fk_expectations.items():
        foreign_keys = inspector.get_foreign_keys(table)
        fk_map = {tuple(fk["constrained_columns"]): fk["referred_table"] for fk in foreign_keys}
        for column, target in expected.items():
            assert (column,) in fk_map
            assert fk_map[(column,)] == target


def test_unique_constraints(migrated_engine: sa.Engine) -> None:
    inspector = sa.inspect(migrated_engine)
    unique_expectations = {
        "users": {"uq_users_tenant_email": {"tenant_id", "email"}},
        "shareholders": {"uq_shareholders_tenant_external_ref": {"tenant_id", "external_ref"}},
        "employee_plans": {
            "uq_employee_plans_tenant_employee_plan": {"tenant_id", "employee_id", "plan_type"}
        },
        "proxy_ballots": {
            "uq_proxy_ballots_meeting_shareholder": {"tenant_id", "meeting_id", "shareholder_id"}
        },
    }

    for table, expected in unique_expectations.items():
        constraints = inspector.get_unique_constraints(table)
        found = {constraint["name"]: set(constraint["column_names"]) for constraint in constraints}
        for name, columns in expected.items():
            assert name in found
            assert found[name] == columns


def test_tenant_indexes(migrated_engine: sa.Engine) -> None:
    inspector = sa.inspect(migrated_engine)
    index_expectations = {
        "users": "ix_users_tenant_id",
        "shareholders": "ix_shareholders_tenant_id",
        "employee_plans": "ix_employee_plans_tenant_id",
        "transactions": "ix_transactions_tenant_id",
        "audit_logs": "ix_audit_logs_tenant_id",
        "proxy_ballots": "ix_proxy_ballots_tenant_id",
    }

    for table, index_name in index_expectations.items():
        indexes = {index["name"] for index in inspector.get_indexes(table)}
        assert index_name in indexes
