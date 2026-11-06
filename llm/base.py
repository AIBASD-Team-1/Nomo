from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    """

    @abstractmethod
    def call(self, system_prompt: str, user_prompt: str) -> str:
        """
        Execute the LLM call passing system prompt and user prompt.

        Args:
            system_prompt: Instructions defining the behavior and persona of the LLM.
            user_prompt: The prompt / design description provided by the user.

        Returns:
            Text response from the LLM.
        """
        pass
