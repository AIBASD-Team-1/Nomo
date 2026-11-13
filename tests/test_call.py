import json
import os

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
