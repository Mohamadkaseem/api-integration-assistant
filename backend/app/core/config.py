"""Application settings.

All configuration comes from environment variables (or a local .env file).
Secrets such as API keys will be added here later - they must NEVER be
hard-coded in source code.
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "My API Integration Assistant"
    environment: str = "development"
    version: str = "0.8.0"
    # Stored as a comma-separated string, e.g. "http://localhost:3000,https://app.example.com"
    cors_origins: str = "http://localhost:3000"
    # SQLite = the whole database is one file. "./data/app.db" is relative to the backend folder.
    database_url: str = "sqlite:///./data/app.db"

    # Request Builder: allow calls to localhost / private network addresses (e.g. a local test server).
    allow_private_network_requests: bool = False

    # Key that encrypts saved credentials. Leave empty to auto-create data/credentials.key on first start.
    credentials_key: SecretStr = SecretStr("")
    credentials_key_file: str = "./data/credentials.key"
    # Where the browser comes back after "Sign in with ..." (register this URL in the app's OAuth settings)
    oauth_redirect_uri: str = "http://localhost:8000/api/oauth/callback"
    frontend_url: str = "http://localhost:3000"

    # --- AI ---
    # SecretStr hides the value if settings are ever printed or logged.
    anthropic_api_key: SecretStr = SecretStr("")
    ai_model: str = "claude-opus-5-5"
    ai_effort: str = "high"

    @property
    def ai_configured(self) -> bool:
        return bool(self.anthropic_api_key.get_secret_value().strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Load settings once and reuse them everywhere."""
    return Settings()
