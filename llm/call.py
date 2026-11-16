import json
import os
import re
import threading
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from .base import LLMProvider
from .cli_provider import DEFAULT_TIMEOUT_SECONDS, CliProvider
from .mock import MockProvider
from .openrouter import OpenRouterProvider

# The variables load_environment put into os.environ from env files, with their values.
# Anything else in os.environ came from the shell and wins over the files.
variables_from_env_files: dict[str, str] = {}
# The web app handles prompts in parallel threads
environment_lock = threading.Lock()


def provider_variable_name(provider_name: str, setting: str) -> str:
    """
    The environment variable for one provider's setting, e.g. NOMO_CLAUDE_CODE_MODEL.
    It names the provider, so a model meant for one AI never reaches another one
    when a .env.<provider> preset switches the provider.
    """
    upper_provider_name = provider_name.upper()
    variable_provider_name = re.sub(r"[^A-Z0-9]", "_", upper_provider_name)
    upper_setting = setting.upper()
    return f"NOMO_{variable_provider_name}_{upper_setting}"


def resolve_setting(
    provider_config: dict[str, Any],
    setting: str,
    environment_variables: list[str],
) -> str:
    """
    The first set environment variable (from the shell or .env) wins over the
    provider's entry in config.json. An empty variable counts as not set.
    """
    for environment_variable in environment_variables:
        environment_value = os.getenv(environment_variable)
        if environment_value:
            return environment_value
    return provider_config.get(setting, "")


def get_provider(config: dict[str, Any]) -> LLMProvider:
    """
    Factory function to instantiate the selected LLM provider based on config.
    NOMO_PROVIDER from the environment or .env overrides config["provider"].
    """
    configured_name = config.get("provider", "mock")
    # an empty NOMO_PROVIDER counts as not set
    environment_name = os.getenv("NOMO_PROVIDER")
    provider_name = (environment_name or configured_name).lower()
    providers_config = config.get("providers", {})
    provider_config = providers_config.get(provider_name, {})
    model_variables = [provider_variable_name(provider_name, "model")]
    if provider_name == "openrouter":
        # OPENROUTER_MODEL is the older name of NOMO_OPENROUTER_MODEL
        model_variables.append("OPENROUTER_MODEL")
    effort_variables = [provider_variable_name(provider_name, "effort")]
    model = resolve_setting(provider_config, "model", model_variables)
    effort = resolve_setting(provider_config, "effort", effort_variables)

    if provider_config.get("type") == "cli":
        snake_case_effort_arguments = provider_config.get("effort_arguments", [])
        effort_arguments = provider_config.get(
            "effort-arguments", snake_case_effort_arguments
        )
        return CliProvider(
            command=provider_config.get("command", []),
            model=model,
            effort=effort,
            effort_arguments=effort_arguments,
            timeout=provider_config.get("timeout", DEFAULT_TIMEOUT_SECONDS),
        )
    if provider_name == "openrouter":
        snake_case_api_key = provider_config.get("api_key", "")
        api_key = provider_config.get("api-key", snake_case_api_key)
        return OpenRouterProvider(
            model=model or "recursive/flint-v1.0:free",
            effort=effort,
            api_key=api_key,
            base_url=provider_config.get("base-url")
            or provider_config.get("base_url", ""),
        )

    if provider_name == "mock":
        return MockProvider(model_name=model or "mock-default")

    raise ValueError(
        f"Unknown AI provider '{provider_name}'. Use mock, openrouter, or an entry "
        'under providers in config.json that has "type": "cli".'
    )


def load_environment(config_path: str, env_file: str | None = None) -> None:
    """
    Loads env_file (e.g. .env.codex), then .env next to config.json for the keys.
    The first value wins: shell variables, then env_file, then .env.
    A given env_file must exist; .env is optional.

    It runs for every prompt, so an edited .env counts without a restart: the variables
    the last call took from the files are replaced, and the ones no longer in the files
    are removed. Variables from the shell are never changed.
    """
    file_values: dict[str, str] = {}
    if env_file:
        env_file_path = Path(env_file)
        if not env_file_path.is_file():
            raise FileNotFoundError(f"The env file '{env_file}' does not exist.")
        add_missing_values(file_values, dotenv_values(env_file_path))
    personal_env_file = Path(config_path).resolve().parent / ".env"
    add_missing_values(file_values, dotenv_values(personal_env_file))

    with environment_lock:
        # A variable still holding the value loaded from a file came from the files;
        # one set or changed since then by the shell or the program is kept as it is
        loaded_names = list(variables_from_env_files)
        for name in loaded_names:
            loaded_value = variables_from_env_files.pop(name)
            is_unchanged = os.environ.get(name) == loaded_value
            if is_unchanged and name not in file_values:
                del os.environ[name]
            elif is_unchanged:
                variables_from_env_files[name] = loaded_value
        for name, value in file_values.items():
            is_from_shell = name in os.environ and name not in variables_from_env_files
            if is_from_shell:
                continue
            os.environ[name] = value
            variables_from_env_files[name] = value


def add_missing_values(
    file_values: dict[str, str], new_values: dict[str, str | None]
) -> None:
    """Adds the variables that file_values does not have yet (the first file wins)."""
    for name, value in new_values.items():
        if value is None or name in file_values:
            continue
        file_values[name] = value


def call_llm(
    system_prompt: str,
    user_prompt: str,
    config_path: str = "config.json",
    provider: LLMProvider | None = None,
) -> str:
    """
    Execute LLM call passing system prompt and user prompt.
    Without a provider it loads .env and picks one from config_path, for every call,
    so edits to .env count. A caller that passes a provider has loaded them itself.
    """
    if provider is None:
        load_environment(config_path)
        if os.path.exists(config_path):
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
        else:
            config = {"provider": "mock"}
        provider = get_provider(config)

    return provider.call(system_prompt=system_prompt, user_prompt=user_prompt)
