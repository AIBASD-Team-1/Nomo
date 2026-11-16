import os

import pytest


@pytest.fixture(autouse=True)
def ignore_developer_ai_choice(monkeypatch):
    """A developer's own NOMO_* variables (shell or .env) must not change the tests."""
    for variable in list(os.environ):
        is_ai_choice = variable.startswith("NOMO_") or variable == "OPENROUTER_MODEL"
        if is_ai_choice and variable != "NOMO_LIVE_PROVIDER":
            monkeypatch.delenv(variable, raising=False)
