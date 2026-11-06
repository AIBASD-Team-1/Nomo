import json
import os
import urllib.request
import urllib.error
from .base import LLMProvider


class OpenRouterProvider(LLMProvider):
    """
    OpenRouter LLM provider (OpenAI-compatible chat completions).
    Supports free models on OpenRouter (e.g. meta-llama/llama-3.3-70b-instruct:free).
    """

    def __init__(self, model: str = "meta-llama/llama-3.3-70b-instruct:free", api_key: str = "", base_url: str = ""):
        self.model = model
        # Resolve key from env var if variable name passed
        resolved_key = os.getenv(api_key, api_key) if api_key else ""
        if not resolved_key and "OPENROUTER_API_KEY" in os.environ:
            resolved_key = os.environ["OPENROUTER_API_KEY"]
        self.api_key = resolved_key
        self.base_url = base_url.rstrip("/") if base_url else "https://openrouter.ai/api/v1"

    def call(self, system_prompt: str, user_prompt: str) -> str:
        if self.model.upper() == "MOCK" or not self.api_key:
            return (
                f"[OpenRouter Mock Response - model: {self.model}]\n"
                f"Note: Set OPENROUTER_API_KEY to execute real calls.\n"
                f"System Prompt: {system_prompt}\n"
                f"User Prompt: {user_prompt}"
            )

        endpoint = f"{self.base_url}/chat/completions" if not self.base_url.endswith("/chat/completions") else self.base_url
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/TUGraz/Nomo",
            "X-Title": "Nomo CAD CLI"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                result = json.loads(response.read().decode("utf-8"))
                choices = result.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "")
                return json.dumps(result, indent=2)
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"OpenRouter API error (HTTP {e.code}): {err_msg}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"OpenRouter network error: {e.reason}") from e
