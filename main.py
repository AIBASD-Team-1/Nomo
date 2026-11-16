import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from catalog import build_system_prompt, parse_reply
from llm import call_llm
from llm.cli_provider import stop_running_tools

# Base paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_HTML_PATH = STATIC_DIR / "index.html"

# Response contract defaults
SCHEMA_VERSION = "1.00"
STATUS_AI_NOT_IMPLEMENTED = "ai_not_implemented"
STATUS_PROVIDER_ERROR = "error"
RESPONSE_TYPE = "response"
DEFAULT_UNIMPLEMENTED_MESSAGE = "The AI does not exist yet."

logger = logging.getLogger("nomo")


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    yield
    # An AI CLI still answering a prompt runs in its own process group and would
    # outlive the server
    stop_running_tools()


app = FastAPI(title="Nomo CAD Web Interface", lifespan=lifespan)


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


def create_provider_error_response(prompt: str, error: Exception) -> PromptResponse:
    """Builds the response for an AI provider that could not answer."""
    error_message = str(error)
    return PromptResponse(
        status=STATUS_PROVIDER_ERROR,
        message=error_message,
        prompt=prompt,
        schema_version=SCHEMA_VERSION,
        type=RESPONSE_TYPE,
        reply=f"Error: {error_message}",
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
    full_system_prompt = build_system_prompt(system_prompt)
    try:
        answer_text = await asyncio.to_thread(
            call_llm, full_system_prompt, request.prompt, str(config_path)
        )
    except (RuntimeError, ValueError, OSError) as error:
        # A missing or failing AI (not installed, not signed in, timeout, unknown
        # provider, missing key) is shown to the user instead of a bare HTTP 500
        logger.warning("The AI provider failed: %s", error)
        return create_provider_error_response(request.prompt, error)
    reply, model = parse_reply(answer_text)
    return PromptResponse(
        status="ok",
        message=reply,
        prompt=request.prompt,
        schema_version=SCHEMA_VERSION,
        type=RESPONSE_TYPE,
        reply=reply,
        result=model,
    )


# Serve static web assets (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def get_index():
    return FileResponse(INDEX_HTML_PATH)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
