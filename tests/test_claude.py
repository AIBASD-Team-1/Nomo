import io
import json
import urllib.error

import pytest

from llm.claude import ClaudeProvider


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.body).encode("utf-8")


def fake_urlopen_returning(body, sent_requests):
    def fake_urlopen(request, timeout):
        sent_requests.append(request)
        return FakeResponse(body)

    return fake_urlopen


def fake_urlopen_raising(error):
    def fake_urlopen(request, timeout):
        raise error

    return fake_urlopen


def test_claude_provider_resolves_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("MY_CLAUDE_KEY", "secret-key")

    provider = ClaudeProvider(api_key="MY_CLAUDE_KEY")

    assert provider.api_key == "secret-key"


def test_claude_provider_normalizes_base_url():
    provider = ClaudeProvider(api_key="key", base_url="example.com/v1/")

    assert provider.base_url == "https://example.com/v1"


def test_claude_provider_returns_mock_reply_for_mock_model():
    provider = ClaudeProvider(model="MOCK", api_key="key")

    reply = provider.call("system", "Build a box")

    assert "Claude Mock Response" in reply
    assert "Build a box" in reply


def test_claude_provider_returns_mock_reply_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    provider = ClaudeProvider(model="claude-test")

    reply = provider.call("system", "Build a box")

    assert "Claude Mock Response" in reply


def test_claude_provider_sends_request_and_joins_text_parts(monkeypatch):
    sent_requests = []
    response_body = {
        "content": [
            {"type": "text", "text": "First"},
            {"type": "tool_use"},
            {"type": "text", "text": "Second"},
        ]
    }
    monkeypatch.setattr(
        "urllib.request.urlopen", fake_urlopen_returning(response_body, sent_requests)
    )
    provider = ClaudeProvider(model="claude-test", api_key="key")

    reply = provider.call("System prompt", "User prompt")

    request = sent_requests[0]
    payload = json.loads(request.data)
    assert reply == "First\nSecond"
    assert request.full_url == "https://api.anthropic.com/v1/messages"
    assert request.get_header("X-api-key") == "key"
    assert payload["model"] == "claude-test"
    assert payload["system"] == "System prompt"
    assert payload["messages"] == [{"role": "user", "content": "User prompt"}]


def test_claude_provider_returns_raw_result_without_text_parts(monkeypatch):
    response_body = {"content": []}
    monkeypatch.setattr(
        "urllib.request.urlopen", fake_urlopen_returning(response_body, [])
    )
    provider = ClaudeProvider(model="claude-test", api_key="key")

    reply = provider.call("system", "prompt")

    assert reply == str(response_body)


def test_claude_provider_raises_runtime_error_for_http_error(monkeypatch):
    http_error = urllib.error.HTTPError(
        "https://api.anthropic.com", 401, "Unauthorized", {}, io.BytesIO(b"bad key")
    )
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen_raising(http_error))
    provider = ClaudeProvider(model="claude-test", api_key="key")

    with pytest.raises(RuntimeError, match="HTTP 401"):
        provider.call("system", "prompt")


def test_claude_provider_raises_runtime_error_for_network_error(monkeypatch):
    network_error = urllib.error.URLError("no connection")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen_raising(network_error))
    provider = ClaudeProvider(model="claude-test", api_key="key")

    with pytest.raises(RuntimeError, match="no connection"):
        provider.call("system", "prompt")
