import json
import os
import urllib.error
import urllib.request

from .base import LLMProvider


class ClaudeProvider(LLMProvider):
    """
    Anthropic Claude LLM provider.
    """

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        api_key: str = "",
        base_url: str = "",
    ):
        self.model = model
        # Resolve API key from environment variable if it points to an env var name
        resolved_key = os.getenv(api_key, api_key) if api_key else ""
        if not resolved_key and "ANTHROPIC_API_KEY" in os.environ:
            resolved_key = os.environ["ANTHROPIC_API_KEY"]
        self.api_key = resolved_key
        self.base_url = (
            base_url.rstrip("/") if base_url else "https://api.anthropic.com/v1"
        )
        if not self.base_url.startswith("http"):
            self.base_url = f"https://{self.base_url}"

    def call(self, system_prompt: str, user_prompt: str) -> str:
        """
        Execute Anthropic Claude API call with system prompt and user prompt.
        """
        # If explicitly configured as MOCK or without an active key, return simulated response
        if (
            self.model.upper() == "MOCK"
            or not self.api_key
            or self.api_key == "CLAUDE_TOKEN"
        ):
            return (
                f"[Claude Mock Response - model: {self.model}]\n"
                f"System Prompt: {system_prompt}\n"
                f"User Prompt: {user_prompt}\n"
                f"Generated CAD model description: Box and table structure configured according to company rules."
            )

        endpoint = (
            f"{self.base_url}/messages"
            if not self.base_url.endswith("/messages")
            else self.base_url
        )
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": 1024,
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                # Extract text content from Anthropic response structure
                contents = result.get("content", [])
                text_parts = [
                    item.get("text", "")
                    for item in contents
                    if item.get("type") == "text"
                ]
                return "\n".join(text_parts) if text_parts else str(result)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Claude API error (HTTP {e.code}): {error_body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Claude network connection error: {e.reason}") from e
