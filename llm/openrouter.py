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

    def __init__(self, model: str = "recursive/flint-v1.0:free", api_key: str = "", base_url: str = ""):
        self.model = model
        # Resolve key: check if api_key points to an env var, or is a raw key (sk-...), or fallback to OPENROUTER_API_KEY
        resolved_key = ""
        if api_key:
            resolved_key = os.getenv(api_key, "")
            if not resolved_key and api_key.startswith("sk-"):
                resolved_key = api_key
        if not resolved_key:
            resolved_key = os.getenv("OPENROUTER_API_KEY", "")

        clean_key = resolved_key.strip().strip('"').strip("'")
        if clean_key.startswith("Bearer "):
            clean_key = clean_key[7:].strip()
        self.api_key = clean_key
        self.base_url = base_url.rstrip("/") if base_url else "https://openrouter.ai/api/v1"

    def call(self, system_prompt: str, user_prompt: str) -> str:
        if self.model.upper() == "MOCK":
            return (
                f"[OpenRouter Mock Response - model: {self.model}]\n"
                f"System Prompt: {system_prompt}\n"
                f"User Prompt: {user_prompt}"
            )

        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is not set!\n"
                "Please run this in your terminal first:\n"
                "  export OPENROUTER_API_KEY=\"sk-or-v1-...\"\n"
                "Or insert your key directly in config.json under providers.openrouter.api_key."
            )

        # Print masked key info for debugging
        masked = self.api_key[:11] + "..." + self.api_key[-4:] if len(self.api_key) > 15 else "***"
        print(f"Using OpenRouter Key: {masked} (length: {len(self.api_key)})")

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
