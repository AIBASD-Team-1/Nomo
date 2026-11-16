import pytest


@pytest.fixture(autouse=True)
def clear_provider_overrides(request, monkeypatch):
    # NOMO_* from the developer's shell would make tests call a real AI or change arguments.
    if request.node.get_closest_marker("integration"):
        return
    monkeypatch.delenv("NOMO_PROVIDER", raising=False)
    monkeypatch.delenv("NOMO_MODEL", raising=False)
    monkeypatch.delenv("NOMO_EFFORT", raising=False)
