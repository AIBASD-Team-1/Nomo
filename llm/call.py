import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .base import LLMProvider
from .cli import CliProvider
from .mock import MockProvider
from .openrouter import OpenRouterProvider


def get_provider(config: dict[str, Any]) -> LLMProvider:
    """
    Build the provider selected in config, by its `type` (cli, openrouter or mock).

    NOMO_PROVIDER, NOMO_MODEL and NOMO_EFFORT (environment or .env) override
    `provider`, the model and the effort.
    """
    provider_name = os.getenv("NOMO_PROVIDER") or config.get("provider", "mock")
    providers = config.get("providers", {})
    if provider_name not in providers:
        known_names = ", ".join(providers)
        raise ValueError(
            f"Unknown provider '{provider_name}'. Configured providers: {known_names}"
        )

    provider_settings = providers[provider_name]
    provider_type = provider_settings.get("type")
    model = os.getenv("NOMO_MODEL") or provider_settings.get("model", "")
    effort = os.getenv("NOMO_EFFORT") or provider_settings.get("effort", "")

    if provider_type == "cli":
        return CliProvider(
            command=provider_settings["command"],
            model=model,
            effort=effort,
            effort_arguments=provider_settings.get("effort-arguments", []),
        )
    if provider_type == "openrouter":
        return OpenRouterProvider(
            model=model,
            api_key=provider_settings.get("api_key", ""),
            base_url=provider_settings.get("base-url", ""),
            effort=effort,
        )
    if provider_type == "mock":
        return MockProvider(model_name=model or "mock")
    raise ValueError(
        f"Unknown type '{provider_type}' for provider '{provider_name}'. "
        "Use cli, openrouter or mock."
    )


def call_llm(
    system_prompt: str,
    user_prompt: str,
    config_path: str = "config.json",
    provider: LLMProvider | None = None,
) -> str:
    """
    Execute LLM call passing system prompt and user prompt.
    """
    load_dotenv(Path(config_path).resolve().parent / ".env")

    if provider is None:
        if os.path.exists(config_path):
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {"provider": "mock", "providers": {"mock": {"type": "mock"}}}
        provider = get_provider(config)

    return provider.call(system_prompt=system_prompt, user_prompt=user_prompt)
