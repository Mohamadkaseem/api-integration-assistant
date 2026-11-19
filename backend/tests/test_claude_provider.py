"""Tests the real ClaudeProvider code against a *mock* Claude server.

No network and no API key needed: httpx2.MockTransport answers exactly like
the Claude API would, so we can check the request we send and how we handle
the answer.
"""

import json

import anthropic
import httpx2
import pytest

from app.ai.claude import ClaudeProvider
from app.ai.provider import AIError
from app.ai.requirement_analyzer import RequirementAnalysis, analyze_requirement
from tests.sample_analysis import SAMPLE_ANALYSIS


def claude_reply(text: str | None, stop_reason: str = "end_turn") -> httpx2.Response:
    """A streamed (Server-Sent Events) reply, exactly the shape the Claude API sends."""
    events = [
        ("message_start", {"type": "message_start", "message": {
            "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 100, "output_tokens": 1}}}),
    ]
    if text is not None:
        events += [
            ("content_block_start", {"type": "content_block_start", "index": 0,
                                     "content_block": {"type": "text", "text": ""}}),
            ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                     "delta": {"type": "text_delta", "text": text}}),
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ]
    events += [
        ("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                           "usage": {"output_tokens": 200}}),
        ("message_stop", {"type": "message_stop"}),
    ]
    body = "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)
    return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())


def make_provider(handler) -> ClaudeProvider:
    client = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    return ClaudeProvider(api_key="test-key", model="claude-opus-5-5", effort="high", client=client)


def test_sends_structured_request_and_parses_answer():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["body"] = json.loads(request.content)
        seen["headers"] = request.headers
        return claude_reply(SAMPLE_ANALYSIS.model_dump_json())

    result = analyze_requirement(make_provider(handler), "Sync HubSpot companies into Zoho CRM accounts.")

    assert isinstance(result, RequirementAnalysis)
    assert result == SAMPLE_ANALYSIS
    body = seen["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"]["effort"] == "high"
    assert body["output_config"]["format"]["type"] == "json_schema"  # structured output requested
    assert body["fallbacks"] == "default"
    assert body["stream"] is True
    assert "server-side-fallback-2026-07-01" in seen["headers"]["anthropic-beta"]
    assert "Do NOT name or guess API endpoints" in body["system"]
    assert "temperature" not in body


def test_bad_api_key_gives_friendly_error():
    def handler(request):
        return httpx2.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})

    with pytest.raises(AIError) as err:
        analyze_requirement(make_provider(handler), "Sync HubSpot companies into Zoho CRM accounts.")
    assert "rejected the API key" in err.value.message
    assert "test-key" not in err.value.message  # never leak the key


def test_refusal_without_text_is_reported():
    def handler(request):
        return claude_reply(None, stop_reason="refusal")

    with pytest.raises(AIError) as err:
        analyze_requirement(make_provider(handler), "Sync HubSpot companies into Zoho CRM accounts.")
    assert err.value.status_code == 422
    assert "declined" in err.value.message


def test_refusal_with_partial_text_is_reported_clearly():
    def handler(request):
        return claude_reply('{"summary": "half', stop_reason="refusal")

    with pytest.raises(AIError) as err:
        analyze_requirement(make_provider(handler), "Sync HubSpot companies into Zoho CRM accounts.")
    assert "incomplete" in err.value.message


def test_rate_limit_is_reported():
    def handler(request):
        return httpx2.Response(429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}})

    with pytest.raises(AIError) as err:
        analyze_requirement(make_provider(handler), "Sync HubSpot companies into Zoho CRM accounts.")
    assert err.value.status_code == 429
