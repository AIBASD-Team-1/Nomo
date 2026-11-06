import json
import os
from types import SimpleNamespace
from pathlib import Path

import pytest
from llm.call import get_provider
from llm.github_copilot import CopilotProvider


def test_copilot_provider_sends_prompts_to_sdk(monkeypatch):
    calls = {}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

        async def send_and_wait(self, prompt):
            calls["prompt"] = prompt
            return SimpleNamespace(data=SimpleNamespace(content="Copilot reply"))

    class FakeClient:
        def __init__(self):
            calls["client_created"] = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

        async def create_session(self, **kwargs):
            calls["session"] = kwargs
            return FakeSession()

    monkeypatch.setattr("llm.github_copilot.CopilotClient", FakeClient)
    provider = get_provider(
        {"provider": "copilot", "providers": {"copilot": {"model": "gpt-4o"}}}
    )

    assert isinstance(provider, CopilotProvider)
    assert provider.call("Nomo system prompt", "Build a table") == "Copilot reply"
    assert calls["client_created"]
    assert calls["prompt"] == "Build a table"
    assert calls["session"] == {
        "model": "gpt-4o",
        "system_message": {"mode": "append", "content": "Nomo system prompt"},
    }


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("NOMO_COPILOT_INTEGRATION") != "1",
    reason="Set NOMO_COPILOT_INTEGRATION=1 to call GitHub Copilot.",
)
def test_copilot_provider_live():
    config_path = Path(__file__).resolve().parents[1] / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    model = config.get("providers", {}).get("copilot", {}).get("model", "auto")
    provider = CopilotProvider(model=model)

    response = provider.call(
        "Respond with exactly the requested marker and nothing else.",
        "Reply exactly: COPILOT_PROVIDER_OK",
    )

    assert response.strip()
    assert "COPILOT_PROVIDER_OK" in response