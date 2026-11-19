"""AI provider abstraction.

The rest of the app only talks to `AIProvider`. Today the only implementation is
Claude (`ClaudeProvider`); another provider can be added later as a new class
without changing any agent code.
"""

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AIError(Exception):
    """A problem talking to the AI, with a message that is safe to show the user."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AIProvider(Protocol):
    name: str
    model: str

    def generate_structured(self, *, system: str, user: str, schema: type[T], max_tokens: int = 16000) -> T:
        """Ask the AI a question and get back a validated `schema` object.

        `max_tokens` caps how long the answer may be (long documents need more)."""
        ...
