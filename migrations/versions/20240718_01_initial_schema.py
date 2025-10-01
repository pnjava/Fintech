"""Initial schema for core entities."""
from __future__ import annotations

from collections.abc import Iterable

import sqlalchemy as sa
from alembic import op

revision = "20240718_01"
down_revision = None
branch_labels = None
depends_on: Iterable[str] | None = None


def _drop_enum(name: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text(f"DROP TYPE IF EXISTS {name}"))


def upgrade() -> None:  # noqa: D401
    """Create initial tables and constraints."""

    tenant_type = sa.Enum("ISSUER", "SPONSOR", name="tenant_type")
    tenant_status = sa.Enum("ACTIVE", "SUSPENDED", "INACTIVE", name="tenant_status")
    user_role = sa.Enum("ADMIN", "EMPLOYEE", "COMPLIANCE", "OPS", name="user_role")
    user_status = sa.Enum("ACTIVE", "INVITED", "DISABLED", name="user_status")
    shareholder_type = sa.Enum("INDIVIDUAL", "INSTITUTION", name="shareholder_type")
    plan_type = sa.Enum("ESPP", "RSU", "401K", "PENSION", name="plan_type")
    employee_plan_status = sa.Enum("ACTIVE", "SUSPENDED", "CLOSED", name="employee_plan_status")
    transaction_type = sa.Enum("DIVIDEND", "DISBURSE", "CONTRIBUTION", "VESTING", name="transaction_type")
    transaction_status = sa.Enum("PENDING", "SENT", "SETTLED", "FAILED", name="transaction_status")

    tenant_type.create(op.get_bind(), checkfirst=True)
    tenant_status.create(op.get_bind(), checkfirst=True)
    user_role.create(op.get_bind(), checkfirst=True)
    user_status.create(op.get_bind(), checkfirst=True)
    shareholder_type.create(op.get_bind(), checkfirst=True)
    plan_type.create(op.get_bind(), checkfirst=True)
    employee_plan_status.create(op.get_bind(), checkfirst=True)
    transaction_type.create(op.get_bind(), checkfirst=True)
    transaction_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("type", tenant_type, nullable=False),
        sa.Column(
            "status",
            tenant_status,
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("status", user_status, nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "shareholders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("external_ref", sa.String(length=128), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320)),
        sa.Column("phone_number", sa.String(length=32)),
        sa.Column("type", shareholder_type, nullable=False, server_default="INDIVIDUAL"),
        sa.Column("total_shares", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("profile", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id", "external_ref", name="uq_shareholders_tenant_external_ref"
        ),
    )
    op.create_index("ix_shareholders_tenant_id", "shareholders", ["tenant_id"])

    op.create_table(
        "employee_plans",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("shareholder_id", sa.String(length=36)),
        sa.Column("employee_id", sa.String(length=128), nullable=False),
        sa.Column("plan_type", plan_type, nullable=False),
        sa.Column(
            "status",
            employee_plan_status,
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("contribution_total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("vesting_schedule", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shareholder_id"], ["shareholders.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "tenant_id", "employee_id", "plan_type", name="uq_employee_plans_tenant_employee_plan"
        ),
    )
    op.create_index("ix_employee_plans_tenant_id", "employee_plans", ["tenant_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("shareholder_id", sa.String(length=36)),
        sa.Column("plan_id", sa.String(length=36)),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("type", transaction_type, nullable=False),
        sa.Column(
            "status",
            transaction_status,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("reference", sa.String(length=128)),
        sa.Column("details", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shareholder_id"], ["shareholders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_id"], ["employee_plans.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_transactions_tenant_id", "transactions", ["tenant_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=36)),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("resource_type", sa.String(length=128), nullable=False),
        sa.Column("resource_id", sa.String(length=128)),
        sa.Column("payload", sa.JSON()),
        sa.Column("ip_address", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])

    op.create_table(
        "proxy_ballots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("meeting_id", sa.String(length=64), nullable=False),
        sa.Column("shareholder_id", sa.String(length=36), nullable=False),
        sa.Column("ballot_choices", sa.JSON(), nullable=False),
        sa.Column("submitted_by", sa.String(length=128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shareholder_id"], ["shareholders.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id", "meeting_id", "shareholder_id", name="uq_proxy_ballots_meeting_shareholder"
        ),
    )
    op.create_index("ix_proxy_ballots_tenant_id", "proxy_ballots", ["tenant_id"])


def downgrade() -> None:  # noqa: D401
    """Drop all tenant-scoped tables."""

    op.drop_index("ix_proxy_ballots_tenant_id", table_name="proxy_ballots")
    op.drop_table("proxy_ballots")

    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_transactions_tenant_id", table_name="transactions")
    op.drop_table("transactions")

    op.drop_index("ix_employee_plans_tenant_id", table_name="employee_plans")
    op.drop_table("employee_plans")

    op.drop_index("ix_shareholders_tenant_id", table_name="shareholders")
    op.drop_table("shareholders")

    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_table("users")

    op.drop_table("tenants")

    for enum_name in [
        "transaction_status",
        "transaction_type",
        "employee_plan_status",
        "plan_type",
        "shareholder_type",
        "user_status",
        "user_role",
        "tenant_status",
        "tenant_type",
    ]:
        _drop_enum(enum_name)
