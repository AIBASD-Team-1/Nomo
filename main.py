import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from llm import call_llm

# Base paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_HTML_PATH = STATIC_DIR / "index.html"

# Response contract defaults
SCHEMA_VERSION = "1.00"
STATUS_AI_NOT_IMPLEMENTED = "ai_not_implemented"
RESPONSE_TYPE = "response"
DEFAULT_UNIMPLEMENTED_MESSAGE = "The AI does not exist yet."

app = FastAPI(title="Nomo CAD Web Interface")


class PromptRequest(BaseModel):
    prompt: str


class PromptResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    message: str
    prompt: str
    schema_version: str = Field(
        default=SCHEMA_VERSION,
        serialization_alias="schema-version",
        validation_alias=AliasChoices("schema-version", "schema_version"),
    )
    type: str
    reply: str
    result: Any | None = None


def create_unimplemented_prompt_response(prompt: str) -> PromptResponse:
    """Builds the placeholder response contract for an unconfigured/unimplemented AI."""
    return PromptResponse(
        status=STATUS_AI_NOT_IMPLEMENTED,
        message=DEFAULT_UNIMPLEMENTED_MESSAGE,
        prompt=prompt,
        schema_version=SCHEMA_VERSION,
        type=RESPONSE_TYPE,
        reply=f"{DEFAULT_UNIMPLEMENTED_MESSAGE} Got prompt: {prompt}",
        result=None,
    )


@app.post("/api/prompt", response_model=PromptResponse, response_model_by_alias=True)
async def process_prompt(request: PromptRequest) -> PromptResponse:
    config_path = BASE_DIR / "config.json"
    with config_path.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)
    system_prompt = config.get("system-prompt") or config.get(
        "system_prompt", "You are Nomo CAD assistant."
    )
    reply = await asyncio.to_thread(
        call_llm, system_prompt, request.prompt, str(config_path)
    )
    return PromptResponse(
        status="ok",
        message=reply,
        prompt=request.prompt,
        schema_version=SCHEMA_VERSION,
        type=RESPONSE_TYPE,
        reply=reply,
        result=None,
    )


# Serve static web assets (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def get_index():
    return FileResponse(INDEX_HTML_PATH)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
