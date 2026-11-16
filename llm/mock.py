import json

from .base import LLMProvider


class MockProvider(LLMProvider):
    """
    Offline provider for development and tests: answers without calling any AI.
    """

    def __init__(self, model_name: str = "mock-model"):
        self.model_name = model_name

    def call(self, system_prompt: str, user_prompt: str) -> str:
        """Return a valid, empty answer in the format the app expects."""
        answer = {"reply": f"Mock reply to: {user_prompt}", "model": []}
        return json.dumps(answer)
