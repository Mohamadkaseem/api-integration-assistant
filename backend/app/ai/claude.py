"""Claude implementation of the AIProvider interface.

Uses the official `anthropic` SDK with *structured outputs*: we hand Claude a
Pydantic schema and the API guarantees the answer matches it, so we never have
to guess-parse free text.
"""

import logging

import anthropic
import pydantic

from app.ai.provider import AIError, T

logger = logging.getLogger(__name__)

# If Claude's safety system declines a request, let the API retry it automatically
# on a suitable fallback model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeProvider:
    name = "claude"

    def __init__(self, api_key: str, model: str, effort: str = "high", client: anthropic.Anthropic | None = None):
        self.model = model
        self.effort = effort
        # `client` can be injected in tests; normally we build the real one.
        self._client = client or anthropic.Anthropic(api_key=api_key, timeout=300.0, max_retries=2)

    def generate_structured(self, *, system: str, user: str, schema: type[T], max_tokens: int = 16000) -> T:
        try:
            # Streaming keeps long answers (e.g. many endpoints from a big document)
            # from hitting HTTP timeouts. We simply wait for the final message.
            with self._client.beta.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                output_config={"effort": self.effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            ) as stream:
                response = stream.get_final_message()
        # Most specific errors first. Messages never include the API key.
        except anthropic.AuthenticationError as exc:
            raise AIError(
                "Claude rejected the API key. Check ANTHROPIC_API_KEY in backend/.env, then restart the backend.",
                502,
            ) from exc
        except anthropic.PermissionDeniedError as exc:
            raise AIError("This API key is not allowed to use this model. Check your Anthropic Console settings.", 502) from exc
        except anthropic.RateLimitError as exc:
            raise AIError("Claude is rate-limiting requests. Wait a minute and try again.", 429) from exc
        except anthropic.BadRequestError as exc:
            message = getattr(exc, "message", "") or ""
            if "credit" in message.lower() or "billing" in message.lower():
                raise AIError("Your Anthropic account has no credit left. Add credit under Billing in the Anthropic Console.", 402) from exc
            logger.warning("Claude bad request: %s", message)
            raise AIError(f"Claude could not process the request: {message}", 400) from exc
        except anthropic.APIConnectionError as exc:
            raise AIError("Cannot reach the Claude API. Check your internet connection.", 503) from exc
        except anthropic.APIStatusError as exc:
            logger.warning("Claude API error %s", exc.status_code)
            raise AIError(f"Claude API error ({exc.status_code}). Please try again shortly.", 502) from exc
        except pydantic.ValidationError as exc:
            # The SDK could not read the answer as our schema - e.g. Claude stopped early
            # (declined, or ran out of space) and sent back empty or partial text.
            raise AIError(
                "Claude's answer was incomplete (it may have declined or been cut off). "
                "Try again, or rephrase the requirement.",
                502,
            ) from exc

        if response.stop_reason == "refusal":
            raise AIError("Claude declined to analyze this text. Try rephrasing the requirement.", 422)
        if response.stop_reason == "max_tokens":
            raise AIError("The AI answer was too long and got cut off. Try a shorter input.", 422)
        if response.parsed_output is None:
            raise AIError("Claude returned an answer that did not match the expected format. Please try again.", 502)

        logger.info(
            "Claude call ok: model=%s input_tokens=%s output_tokens=%s",
            response.model, response.usage.input_tokens, response.usage.output_tokens,
        )
        return response.parsed_output
