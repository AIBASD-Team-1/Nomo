import json
import os
from typing import Optional, Dict, Any
from .base import LLMProvider
from .claude import ClaudeProvider
from .openrouter import OpenRouterProvider
from .mock import MockProvider


def get_provider(config: Dict[str, Any]) -> LLMProvider:
    """
    Factory function to instantiate the selected LLM provider based on config.
    """
    provider_name = config.get("provider", "mock").lower()
    providers_cfg = config.get("providers", {})
    provider_cfg = providers_cfg.get(provider_name, {})

    if provider_name == "openrouter":
        return OpenRouterProvider(
            model=provider_cfg.get("model", "meta-llama/llama-3.3-70b-instruct:free"),
            api_key=provider_cfg.get("api_key", "OPENROUTER_API_KEY"),
            base_url=provider_cfg.get("base-url", "https://openrouter.ai/api/v1")
        )
    elif provider_name == "claude":
        return ClaudeProvider(
            model=provider_cfg.get("model", "MOCK"),
            api_key=provider_cfg.get("api_key", ""),
            base_url=provider_cfg.get("base-url", "")
        )
    else:
        model_name = provider_cfg.get("model", "mock-default")
        return MockProvider(model_name=model_name)


def call_llm(system_prompt: str, user_prompt: str, config_path: str = "config.json", provider: Optional[LLMProvider] = None) -> str:
    """
    Execute LLM call passing system prompt and user prompt.
    """
    if provider is None:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {"provider": "mock"}
        provider = get_provider(config)

    return provider.call(system_prompt=system_prompt, user_prompt=user_prompt)
