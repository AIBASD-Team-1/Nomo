import json
import os

import pytest

from llm import call as llm_call


def test_call_llm_loads_env_file_next_to_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "provider": "openrouter",
                "providers": {"openrouter": {"api_key": "OPENROUTER_API_KEY"}},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "OPENROUTER_API_KEY=test-key-from-env-file\n", encoding="utf-8"
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    class EnvironmentProvider:
        def call(self, system_prompt: str, user_prompt: str) -> str:
            return os.environ["OPENROUTER_API_KEY"]

    monkeypatch.setattr(
        llm_call, "OpenRouterProvider", lambda **kwargs: EnvironmentProvider()
    )

    result = llm_call.call_llm("system", "prompt", str(config_path))

    assert result == "test-key-from-env-file"


def test_openrouter_model_from_environment_overrides_config(monkeypatch):
    config = {
        "provider": "openrouter",
        "providers": {"openrouter": {"model": "config/model:free"}},
    }

    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    provider_without_override = llm_call.get_provider(config)
    assert provider_without_override.model == "config/model:free"

    monkeypatch.setenv("OPENROUTER_MODEL", "environment/model:free")
    provider_with_override = llm_call.get_provider(config)
    assert provider_with_override.model == "environment/model:free"


def test_openrouter_missing_key_error_does_not_show_configured_value(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    config = {
        "provider": "openrouter",
        "providers": {"openrouter": {"api_key": "Bearer raw-secret-in-config"}},
    }
    provider = llm_call.get_provider(config)

    with pytest.raises(ValueError) as raised:
        provider.call("system", "prompt")

    assert "raw-secret-in-config" not in str(raised.value)
    assert "OPENROUTER_API_KEY" in str(raised.value)


def test_openrouter_sends_effort_as_reasoning(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key-1234567890")
    sent_payloads = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            answer = {"choices": [{"message": {"content": "reply"}}]}
            return json.dumps(answer).encode("utf-8")

    def fake_urlopen(request, timeout):
        sent_payloads.append(json.loads(request.data))
        return FakeResponse()

    monkeypatch.setattr("llm.openrouter.urllib.request.urlopen", fake_urlopen)
    config = {
        "provider": "openrouter",
        "providers": {"openrouter": {"model": "some/model:free", "effort": "low"}},
    }
    provider = llm_call.get_provider(config)

    assert provider.call("system", "prompt") == "reply"
    assert sent_payloads[0]["reasoning"] == {"effort": "low"}


def test_openrouter_null_api_key_uses_default_variable(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-default-key")
    config = {"provider": "openrouter", "providers": {"openrouter": {"api_key": None}}}

    provider = llm_call.get_provider(config)

    assert provider.api_key == "sk-or-default-key"


def test_openrouter_unset_named_variable_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("MY_OPENROUTER_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-default-key")
    config = {
        "provider": "openrouter",
        "providers": {"openrouter": {"api_key": "MY_OPENROUTER_KEY"}},
    }

    provider = llm_call.get_provider(config)

    assert provider.api_key == "sk-or-default-key"
    assert provider.api_key_name == "OPENROUTER_API_KEY"


def test_openrouter_named_variable_wins_over_default(monkeypatch):
    monkeypatch.setenv("MY_OPENROUTER_KEY", "sk-or-named-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-default-key")
    config = {
        "provider": "openrouter",
        "providers": {"openrouter": {"api_key": "MY_OPENROUTER_KEY"}},
    }

    provider = llm_call.get_provider(config)

    assert provider.api_key == "sk-or-named-key"


def test_openrouter_api_key_accepts_kebab_case(monkeypatch):
    monkeypatch.setenv("MY_OPENROUTER_KEY", "sk-or-named-key")
    config = {
        "provider": "openrouter",
        "providers": {"openrouter": {"api-key": "MY_OPENROUTER_KEY"}},
    }

    provider = llm_call.get_provider(config)

    assert provider.api_key == "sk-or-named-key"
    assert provider.api_key_name == "MY_OPENROUTER_KEY"
