"""Application settings.

All configuration comes from environment variables (or a local .env file).
Secrets such as API keys will be added here later - they must NEVER be
hard-coded in source code.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "My API Integration Assistant"
    environment: str = "development"
    version: str = "0.2.0"
    # Stored as a comma-separated string, e.g. "http://localhost:3000,https://app.example.com"
    cors_origins: str = "http://localhost:3000"
    # SQLite = the whole database is one file. "./data/app.db" is relative to the backend folder.
    database_url: str = "sqlite:///./data/app.db"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Load settings once and reuse them everywhere."""
    return Settings()
