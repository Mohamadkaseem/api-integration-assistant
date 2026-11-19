"""FastAPI dependency that hands routes the configured AI provider.

Tests replace this with a fake provider, so they never call the real API.
"""

from app.ai.claude import ClaudeProvider
from app.ai.provider import AIError, AIProvider
from app.core.config import get_settings


def get_ai_provider() -> AIProvider:
    settings = get_settings()
    if not settings.ai_configured:
        raise AIError(
            "No Claude API key configured. Add ANTHROPIC_API_KEY to backend/.env and restart the backend.",
            503,
        )
    return ClaudeProvider(
        api_key=settings.anthropic_api_key.get_secret_value().strip(),
        model=settings.ai_model,
        effort=settings.ai_effort,
    )
