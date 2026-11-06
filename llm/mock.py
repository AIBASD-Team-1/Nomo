from .base import LLMProvider


class MockProvider(LLMProvider):
    """
    Mock LLM provider for testing and development without live API keys.
    """

    def __init__(self, model_name: str = "mock-model"):
        self.model_name = model_name

    def call(self, system_prompt: str, user_prompt: str) -> str:
        """
        Simulate an LLM response incorporating both system and user prompts.
        """
        return (
            f"[Mock LLM Response ({self.model_name})]\n"
            f"System Prompt: {system_prompt}\n"
            f"Received Prompt: '{user_prompt}'\n"
            f"Result: Design generated successfully based on your specifications."
        )
