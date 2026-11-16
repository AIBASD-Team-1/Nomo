import json
from pathlib import Path

from dotenv import dotenv_values

PROJECT_FOLDER = Path(__file__).resolve().parents[1]
KNOWN_PROVIDER_TYPES = {"cli", "openrouter", "mock"}
REQUIRED_PROVIDERS = [
    "claude",
    "codex",
    "copilot",
    "antigravity",
    "openrouter",
    "mock",
]


def load_configured_providers():
    config_text = (PROJECT_FOLDER / "config.json").read_text(encoding="utf-8")
    config = json.loads(config_text)
    return config["providers"]


def find_env_presets():
    preset_paths = sorted(PROJECT_FOLDER.glob(".env.*"))
    return [path for path in preset_paths if path.name != ".env.example"]


def test_config_contains_all_supported_ai_providers():
    providers = load_configured_providers()

    for provider_name in REQUIRED_PROVIDERS:
        assert provider_name in providers, provider_name


def test_every_configured_provider_has_known_type():
    providers = load_configured_providers()

    for provider_name, provider_settings in providers.items():
        provider_type = provider_settings.get("type")
        assert provider_type in KNOWN_PROVIDER_TYPES, provider_name
        if provider_type == "cli":
            command = provider_settings.get("command")
            assert isinstance(command, list), provider_name
            assert command, provider_name


def test_every_ai_provider_has_default_model_and_effort():
    providers = load_configured_providers()

    for provider_name, provider_settings in providers.items():
        if provider_settings.get("type") == "mock":
            continue
        assert provider_settings.get("model"), provider_name
        assert provider_settings.get("effort"), provider_name
        if provider_settings.get("type") == "cli":
            effort_arguments = provider_settings.get("effort-arguments", [])
            assert any("{effort}" in argument for argument in effort_arguments), (
                provider_name
            )


def test_every_env_preset_selects_a_configured_provider():
    providers = load_configured_providers()
    preset_paths = find_env_presets()

    assert preset_paths, "No .env.<provider> presets found"
    for preset_path in preset_paths:
        preset_values = dotenv_values(preset_path)
        assert preset_values.get("NOMO_PROVIDER") in providers, preset_path.name


def test_env_presets_contain_no_api_keys():
    # Presets are committed; keys belong in the git-ignored .env only.
    for preset_path in find_env_presets():
        preset_values = dotenv_values(preset_path)
        for variable_name in preset_values:
            assert "KEY" not in variable_name.upper(), preset_path.name
