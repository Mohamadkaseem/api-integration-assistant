"""FastAPI dependencies that hand routes the configured AI provider.

Tests replace this with a fake provider, so they never call the real API.
"""

from collections.abc import Callable

from fastapi import Request

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


def get_ai_provider_factory(request: Request) -> Callable[[], AIProvider]:
    """For routes that need the AI only sometimes (e.g. a PDF needs it, an OpenAPI file does not).

    Returns a function that creates the provider on demand, so no API key is needed
    unless the AI is really used. It honours test overrides of `get_ai_provider`.
    """
    return request.app.dependency_overrides.get(get_ai_provider, get_ai_provider)
