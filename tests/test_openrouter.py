import io
import json
import urllib.error

import pytest

from llm.openrouter import OpenRouterProvider


def test_openrouter_provider_resolves_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("MY_OPENROUTER_KEY", "secret-key")

    provider = OpenRouterProvider(api_key="MY_OPENROUTER_KEY")

    assert provider.api_key == "secret-key"


def test_openrouter_provider_accepts_raw_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    provider = OpenRouterProvider(api_key="sk-raw-key")

    assert provider.api_key == "sk-raw-key"


def test_openrouter_provider_cleans_quotes_and_bearer_prefix(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", '"Bearer token-123"')

    provider = OpenRouterProvider()

    assert provider.api_key == "token-123"


def test_openrouter_provider_returns_mock_reply_for_mock_model():
    provider = OpenRouterProvider(model="MOCK")

    reply = provider.call("system", "Build a box")

    assert "OpenRouter Mock Response" in reply
    assert "Build a box" in reply


def test_openrouter_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = OpenRouterProvider(model="test/model:free")

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        provider.call("system", "prompt")


def test_openrouter_provider_sends_request_and_returns_message(fake_urlopen):
    fake_urlopen.body = {"choices": [{"message": {"content": "Model reply"}}]}
    provider = OpenRouterProvider(model="test/model:free", api_key="sk-test-key")

    reply = provider.call("System prompt", "User prompt")

    request = fake_urlopen.sent_requests[0]
    payload = json.loads(request.data)
    assert reply == "Model reply"
    assert request.full_url == "https://openrouter.ai/api/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer sk-test-key"
    assert payload["model"] == "test/model:free"
    assert payload["messages"] == [
        {"role": "system", "content": "System prompt"},
        {"role": "user", "content": "User prompt"},
    ]


def test_openrouter_provider_returns_raw_json_without_choices(fake_urlopen):
    fake_urlopen.body = {"error": "no choices"}
    provider = OpenRouterProvider(model="test/model:free", api_key="sk-test-key")

    reply = provider.call("system", "prompt")

    assert json.loads(reply) == fake_urlopen.body


def test_openrouter_provider_raises_runtime_error_for_http_error(fake_urlopen):
    fake_urlopen.error = urllib.error.HTTPError(
        "https://openrouter.ai",
        429,
        "Too Many Requests",
        {},
        io.BytesIO(b"rate limited"),
    )
    provider = OpenRouterProvider(model="test/model:free", api_key="sk-test-key")

    with pytest.raises(RuntimeError, match="HTTP 429"):
        provider.call("system", "prompt")


def test_openrouter_provider_raises_runtime_error_for_network_error(fake_urlopen):
    fake_urlopen.error = urllib.error.URLError("no connection")
    provider = OpenRouterProvider(model="test/model:free", api_key="sk-test-key")

    with pytest.raises(RuntimeError, match="no connection"):
        provider.call("system", "prompt")
