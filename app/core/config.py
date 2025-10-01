"""Configuration management for the Fintech application."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


def _load_default_private_key() -> str:
    default_path = Path(__file__).resolve().parent / "../.." / "configs" / "dev-jwt.pem"
    if default_path.exists():
        return default_path.read_text(encoding="utf-8")
    raise FileNotFoundError("Default JWT private key not found. Provide JWT_PRIVATE_KEY environment variable.")


class Settings(BaseSettings):
    app_name: str = Field(default="Fintech Platform")
    version: str = Field(default="0.1.0")
    docs_url: str | None = Field(default="/docs")
    redoc_url: str | None = Field(default="/redoc")
    openapi_url: str = Field(default="/openapi.json")

    database_url: str = Field(default="postgresql+psycopg://fintech:fintech@db:5432/fintech")
    redis_url: str = Field(default="redis://redis:6379/0")

    aws_region: str = Field(default="us-east-1")
    s3_endpoint_url: str | None = Field(default=None)
    audit_log_bucket: str = Field(default="fintech-audit-logs")
    audit_log_prefix: str = Field(default="audit/records")
    audit_log_sample_rate: float = Field(default=1.0)

    ach_adapter_url: str = Field(default="http://localhost:9010/ach/disburse")
    ach_adapter_timeout_seconds: float = Field(default=5.0)

    jwt_algorithm: str = Field(default="RS256")
    jwt_private_key: str = Field(default_factory=_load_default_private_key)
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=7)
    default_tenant_id: str = Field(default="tenant-demo")
    default_role: str = Field(default="ADMIN")
    default_user_hashed_password: str = Field(
        default="$2b$12$oyI2qhzyapMI2vlA38nS4uK91tQ8gjVjTgQExlbDGQLHw6/oEFzOG"
    )  # password: changeme
    default_user_password: str = Field(default="changeme")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


__all__ = ["Settings", "get_settings"]
