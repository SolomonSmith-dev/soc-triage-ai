"""Environment-driven configuration."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="local")
    database_url: str = Field(
        default="postgresql+asyncpg://soc:soc@localhost:5432/soc_triage"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")
    cors_origins: list[str] = Field(default=["http://localhost:3000"])
    anthropic_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
