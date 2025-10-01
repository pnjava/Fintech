"""Application configuration settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Base configuration for the Fintech API service."""

    app_name: str = Field(
        default="Fintech API",
        description="Human readable application name.",
        alias="APP_NAME",
    )
    environment: str = Field(
        default="development",
        description="Deployment environment name.",
        alias="ENVIRONMENT",
    )
    debug: bool = Field(default=False, description="Whether to enable debug mode.", alias="DEBUG")
    version: str = Field(default="0.1.0", description="Application semantic version.", alias="VERSION")

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@db:5432/postgres",
        description="SQLAlchemy-compatible database connection string.",
        alias="DATABASE_URL",
    )
    aws_region: str = Field(
        default="us-east-1",
        description="Default AWS region for LocalStack integration.",
        alias="AWS_REGION",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", populate_by_name=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of the application settings."""

    return Settings()


__all__ = ["Settings", "get_settings"]
