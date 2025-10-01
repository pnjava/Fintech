"""Seed script for demo tenant and users."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.models import Base, Tenant, TenantStatus, TenantType, User, UserRole, UserStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed(session: Session) -> None:
    """Seed demo tenant and admin/employee users."""

    settings = get_settings()
    tenant_id = settings.default_tenant_id

    tenant = session.query(Tenant).filter(Tenant.id == tenant_id).one_or_none()
    if tenant is None:
        tenant = Tenant(
            id=tenant_id,
            name="Demo Tenant",
            type=TenantType.ISSUER,
            status=TenantStatus.ACTIVE,
        )
        session.add(tenant)
        logger.info("Created tenant %s", tenant_id)
    else:
        logger.info("Tenant %s already exists", tenant_id)

    existing_users = {user.email for user in session.query(User).filter(User.tenant_id == tenant_id)}

    seed_users = [
        (
            "admin@demo.local",
            UserRole.ADMIN,
            settings.default_user_hashed_password,
        ),
        (
            "employee@demo.local",
            UserRole.EMPLOYEE,
            settings.default_user_hashed_password,
        ),
    ]

    for email, role, password in seed_users:
        if email in existing_users:
            logger.info("User %s already exists", email)
            continue
        session.add(
            User(
                tenant_id=tenant_id,
                email=email,
                role=role,
                status=UserStatus.ACTIVE,
                hashed_password=password,
            )
        )
        logger.info("Added user %s", email)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed(session)
        session.commit()


if __name__ == "__main__":
    main()
