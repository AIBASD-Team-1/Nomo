import json
import os
import urllib.error
import urllib.request

from .base import LLMProvider

DEFAULT_API_KEY_VARIABLE = "OPENROUTER_API_KEY"


class OpenRouterProvider(LLMProvider):
    """
    OpenRouter chat completions (free models only).
    api_key is the name of the environment variable holding the key.
    """

    def __init__(
        self,
        model: str = "recursive/flint-v1.0:free",
        effort: str = "",
        api_key: str | None = "",
        base_url: str = "",
    ):
        self.model = model
        self.effort = effort
        # api_key names an environment variable (or is a raw key starting with sk-);
        # it may be null in config.json
        configured_key = api_key or ""
        if configured_key.startswith("sk-"):
            self.api_key_name = "api_key in config.json"
            resolved_key = configured_key
        else:
            self.api_key_name = configured_key or DEFAULT_API_KEY_VARIABLE
            resolved_key = os.getenv(self.api_key_name, "")
        if not resolved_key:
            # A named variable that is not set falls back to OPENROUTER_API_KEY
            self.api_key_name = DEFAULT_API_KEY_VARIABLE
            resolved_key = os.getenv(DEFAULT_API_KEY_VARIABLE, "")

        clean_key = resolved_key.strip().strip('"').strip("'")
        if clean_key.startswith("Bearer "):
            clean_key = clean_key[7:].strip()
        self.api_key = clean_key
        self.base_url = (
            base_url.rstrip("/") if base_url else "https://openrouter.ai/api/v1"
        )

    def call(self, system_prompt: str, user_prompt: str) -> str:
        if self.model.upper() == "MOCK":
            return (
                f"[OpenRouter Mock Response - model: {self.model}]\n"
                f"System Prompt: {system_prompt}\n"
                f"User Prompt: {user_prompt}"
            )

        if not self.api_key:
            # The configured api_key is not shown: it may be a real key put there by mistake
            raise ValueError(
                "The OpenRouter API key is not set. Add OPENROUTER_API_KEY=... to your "
                ".env file (or the variable that api_key in config.json names)."
            )

        # Print masked key info for debugging
        masked = (
            self.api_key[:11] + "..." + self.api_key[-4:]
            if len(self.api_key) > 15
            else "***"
        )
        print(f"Using {self.api_key_name}: {masked} (length: {len(self.api_key)})")

        endpoint = (
            f"{self.base_url}/chat/completions"
            if not self.base_url.endswith("/chat/completions")
            else self.base_url
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/TUGraz/Nomo",
            "X-Title": "Nomo CAD CLI",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if self.effort:
            # OpenRouter's reasoning setting; models without reasoning ignore it
            payload["reasoning"] = {"effort": self.effort}

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
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
            raise RuntimeError(
                f"OpenRouter API error (HTTP {e.code}): {err_msg}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"OpenRouter network error: {e.reason}") from e
