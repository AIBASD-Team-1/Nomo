import json
import os
import urllib.error
import urllib.request

from .base import LLMProvider


class OpenRouterProvider(LLMProvider):
    """
    OpenRouter (OpenAI-compatible chat completions). Free models only.
    """

    def __init__(
        self, model: str, api_key: str = "", base_url: str = "", effort: str = ""
    ):
        self.model = model
        self.effort = effort
        self.api_key_variable = api_key
        # api_key is the name of an env var (keys live in .env); a raw sk-... key still works
        resolved_key = os.getenv(api_key, "") if api_key else ""
        if not resolved_key and api_key.startswith("sk-"):
            resolved_key = api_key

        clean_key = resolved_key.strip().strip('"').strip("'")
        if clean_key.startswith("Bearer "):
            clean_key = clean_key[7:].strip()
        self.api_key = clean_key
        self.base_url = base_url.rstrip("/")

    def call(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise ValueError(
                f"API key {self.api_key_variable or '(api_key not configured)'} "
                "is not set. Put it into .env next to config.json."
            )
        if not self.base_url:
            raise ValueError("base-url is not configured for this provider.")

        endpoint = (
            f"{self.base_url}/chat/completions"
            if not self.base_url.endswith("/chat/completions")
            else self.base_url
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/AIBASD-Team-1/Nomo",
            "X-Title": "Nomo",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self.effort:
            payload["reasoning"] = {"effort": self.effort}

        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                result = json.loads(response.read().decode("utf-8"))
                choices = result.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "")
                return json.dumps(result, indent=2)
        except urllib.error.HTTPError as error:
            error_message = error.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"API error (HTTP {error.code}) from {self.base_url}: {error_message}"
            ) from error
        except urllib.error.URLError as error:
            raise RuntimeError(
                f"Network error calling {self.base_url}: {error.reason}"
            ) from error
