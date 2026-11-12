import asyncio

from copilot import CopilotClient

from .base import LLMProvider


class CopilotProvider(LLMProvider):
    def __init__(self, model: str = "auto"):
        self.model = model

    def call(self, system_prompt: str, user_prompt: str) -> str:
        return asyncio.run(self._call(system_prompt, user_prompt))

    async def _call(self, system_prompt: str, user_prompt: str) -> str:
        async with CopilotClient() as client:
            async with await client.create_session(
                model=self.model,
                system_message={"mode": "append", "content": system_prompt},
            ) as session:
                response = await session.send_and_wait(user_prompt)

        if response is None:
            raise RuntimeError("GitHub Copilot returned no response.")
        return response.data.content
