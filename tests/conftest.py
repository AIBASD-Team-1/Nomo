import json
import os

import pytest


@pytest.fixture(autouse=True)
def ignore_developer_ai_choice(monkeypatch):
    """A developer's own NOMO_* variables (shell or .env) must not change the tests."""
    for variable in list(os.environ):
        is_ai_choice = variable.startswith("NOMO_") or variable == "OPENROUTER_MODEL"
        if is_ai_choice and variable != "NOMO_LIVE_PROVIDER":
            monkeypatch.delenv(variable, raising=False)


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.body).encode("utf-8")


class FakeUrlopen:
    """Stands in for urllib.request.urlopen: set `body` or `error` before the call."""

    def __init__(self):
        self.body = {}
        self.error = None
        self.sent_requests = []

    def __call__(self, request, timeout):
        self.sent_requests.append(request)
        if self.error:
            raise self.error
        return FakeResponse(self.body)


@pytest.fixture
def fake_urlopen(monkeypatch):
    fake = FakeUrlopen()
    monkeypatch.setattr("urllib.request.urlopen", fake)
    return fake
