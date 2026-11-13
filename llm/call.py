import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .base import LLMProvider
from .claude import ClaudeProvider
from .github_copilot import CopilotProvider
from .mock import MockProvider
from .openrouter import OpenRouterProvider


def get_provider(config: dict[str, Any]) -> LLMProvider:
    """
    Factory function to instantiate the selected LLM provider based on config.
    """
    provider_name = config.get("provider", "mock").lower()
    providers_cfg = config.get("providers", {})
    provider_cfg = providers_cfg.get(provider_name, {})

    if provider_name == "openrouter":
        # OPENROUTER_MODEL from the environment or .env overrides the model in config.json
        configured_model = provider_cfg.get("model", "google/gemma-4-31b-it:free")
        environment_model = os.getenv("OPENROUTER_MODEL")
        if environment_model:
            model_name = environment_model
        else:
            model_name = configured_model
        return OpenRouterProvider(
            model=model_name,
            api_key=provider_cfg.get("api_key", "OPENROUTER_API_KEY"),
            base_url=provider_cfg.get("base-url", "https://openrouter.ai/api/v1"),
        )
    elif provider_name == "claude":
        return ClaudeProvider(
            model=provider_cfg.get("model", "MOCK"),
            api_key=provider_cfg.get("api_key", ""),
            base_url=provider_cfg.get("base-url", ""),
        )
    elif provider_name == "copilot":
        return CopilotProvider(model=provider_cfg.get("model", "auto"))
    else:
        model_name = provider_cfg.get("model", "mock-default")
        return MockProvider(model_name=model_name)


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
            config = {"provider": "mock"}
        provider = get_provider(config)

    return provider.call(system_prompt=system_prompt, user_prompt=user_prompt)
