import json
import os
from pathlib import Path

import pytest
from dotenv import dotenv_values

from llm.call import get_provider

LIVE_PROVIDER = os.getenv("NOMO_LIVE_PROVIDER")


@pytest.mark.integration
@pytest.mark.skipif(
    not LIVE_PROVIDER,
    reason="Set NOMO_LIVE_PROVIDER (e.g. claude-code) to call a real AI.",
)
def test_live_provider_answers(monkeypatch):
    config_path = Path(__file__).resolve().parents[1] / "config.json"
    config_text = config_path.read_text(encoding="utf-8")
    config = json.loads(config_text)
    # Keys come from .env as in the app; its NOMO_* choices are left out so the
    # provider under test runs with its own defaults from config.json
    personal_env_file = config_path.parent / ".env"
    personal_values = dotenv_values(personal_env_file)
    for name, value in personal_values.items():
        is_ai_choice = name.startswith("NOMO_")
        if value is None or is_ai_choice or name in os.environ:
            continue
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("NOMO_PROVIDER", LIVE_PROVIDER)
    provider = get_provider(config)

    response = provider.call(
        "Respond with exactly the requested marker and nothing else.",
        "Reply exactly: NOMO_PROVIDER_OK",
    )

    assert "NOMO_PROVIDER_OK" in response
