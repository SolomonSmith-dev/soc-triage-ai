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
    nextauth_secret: str = Field(default="dev-secret-change-in-production")

    def model_post_init(self, __context) -> None:
        if self.environment not in {"local", "test"}:
            if (
                not self.nextauth_secret
                or not self.nextauth_secret.strip()
                or self.nextauth_secret == "dev-secret-change-in-production"
            ):
                raise ValueError(
                    "NEXTAUTH_SECRET must be set to a non-default value when environment "
                    "is not 'local' or 'test'."
                )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
