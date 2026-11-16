import json
import os
import sys
from pathlib import Path

import pytest

from catalog import parse_reply
from llm import call as llm_call
from llm.call import get_provider
from llm.mock import MockProvider

PRINT_TEST_KEY_SCRIPT = "import os; print(os.environ['NOMO_TEST_API_KEY'])"
PRINT_ARGUMENTS_SCRIPT = "import json, sys; print(json.dumps(sys.argv[1:]))"


def create_marker_cli(marker):
    return {"type": "cli", "command": [sys.executable, "-c", f"print('{marker}')"]}


def test_call_llm_loads_env_file_next_to_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config = {
        "provider": "key-printer",
        "providers": {
            "key-printer": {
                "type": "cli",
                "command": [sys.executable, "-c", PRINT_TEST_KEY_SCRIPT],
            },
        },
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")
    (tmp_path / ".env").write_text(
        "NOMO_TEST_API_KEY=test-key-from-env-file\n", encoding="utf-8"
    )
    monkeypatch.delenv("NOMO_TEST_API_KEY", raising=False)

    result = llm_call.call_llm("system", "prompt", str(config_path))

    assert result.strip() == "test-key-from-env-file"


def test_nomo_provider_from_environment_overrides_config(monkeypatch):
    config = {
        "provider": "first",
        "providers": {
            "first": create_marker_cli("FIRST_PROVIDER"),
            "second": create_marker_cli("SECOND_PROVIDER"),
        },
    }

    provider_without_override = get_provider(config)
    assert "FIRST_PROVIDER" in provider_without_override.call("system", "prompt")

    monkeypatch.setenv("NOMO_PROVIDER", "second")
    provider_with_override = get_provider(config)
    assert "SECOND_PROVIDER" in provider_with_override.call("system", "prompt")


def test_nomo_model_from_environment_overrides_config_model(monkeypatch):
    config = {
        "provider": "openrouter",
        "providers": {
            "openrouter": {"type": "openrouter", "model": "config/model:free"},
        },
    }

    provider_without_override = get_provider(config)
    assert provider_without_override.model == "config/model:free"

    monkeypatch.setenv("NOMO_MODEL", "environment/model:free")
    provider_with_override = get_provider(config)
    assert provider_with_override.model == "environment/model:free"


def test_nomo_effort_from_environment_overrides_config_effort(monkeypatch):
    config = {
        "provider": "fake-cli",
        "providers": {
            "fake-cli": {
                "type": "cli",
                "command": [sys.executable, "-c", PRINT_ARGUMENTS_SCRIPT],
                "effort": "low",
                "effort-arguments": ["--effort", "{effort}"],
            },
        },
    }

    provider_without_override = get_provider(config)
    answer_without_override = provider_without_override.call("system", "prompt")
    assert json.loads(answer_without_override) == ["--effort", "low"]

    monkeypatch.setenv("NOMO_EFFORT", "high")
    provider_with_override = get_provider(config)
    answer_with_override = provider_with_override.call("system", "prompt")
    assert json.loads(answer_with_override) == ["--effort", "high"]


def test_openrouter_sends_model_and_reasoning_effort(monkeypatch):
    sent_requests = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exception_type, exception, traceback):
            return False

        def read(self):
            answer = {"choices": [{"message": {"content": "OpenRouter reply"}}]}
            return json.dumps(answer).encode("utf-8")

    def fake_urlopen(request, timeout):
        sent_requests.append(request)
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setenv("NOMO_TEST_API_KEY", "test-key")
    config = {
        "provider": "openrouter",
        "providers": {
            "openrouter": {
                "type": "openrouter",
                "model": "test/model:free",
                "effort": "high",
                "api_key": "NOMO_TEST_API_KEY",
                "base-url": "https://openrouter.example/api/v1",
            },
        },
    }

    answer = get_provider(config).call("system", "Build a table")

    assert answer == "OpenRouter reply"
    sent_request = sent_requests[0]
    payload = json.loads(sent_request.data)
    assert sent_request.full_url == "https://openrouter.example/api/v1/chat/completions"
    assert sent_request.get_header("Authorization") == "Bearer test-key"
    assert payload["model"] == "test/model:free"
    assert payload["reasoning"] == {"effort": "high"}


def test_mock_type_returns_valid_response_containing_user_prompt():
    config = {"provider": "offline", "providers": {"offline": {"type": "mock"}}}
    provider = get_provider(config)

    answer = provider.call("system", "Build a table")

    assert isinstance(provider, MockProvider)
    reply, model = parse_reply(answer)
    assert "Build a table" in reply
    assert model == []


def test_unknown_provider_name_raises_error(monkeypatch):
    config = {"provider": "mock", "providers": {"mock": {"type": "mock"}}}
    monkeypatch.setenv("NOMO_PROVIDER", "clade")

    with pytest.raises(ValueError, match="clade"):
        get_provider(config)


def test_unknown_provider_type_raises_error():
    config = {
        "provider": "pigeon",
        "providers": {"pigeon": {"type": "carrier-pigeon"}},
    }

    with pytest.raises(ValueError, match="carrier-pigeon"):
        get_provider(config)


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("NOMO_LIVE_TEST") != "1",
    reason="Set NOMO_LIVE_TEST=1 to call the configured AI provider.",
)
def test_configured_provider_live():
    config_path = Path(__file__).resolve().parents[1] / "config.json"

    answer = llm_call.call_llm(
        "Respond with exactly the requested marker and nothing else.",
        "Reply exactly: NOMO_PROVIDER_OK",
        str(config_path),
    )

    assert "NOMO_PROVIDER_OK" in answer
