import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StrictStr

from catalog import (
    ModelValidationError,
    ResponseFormatError,
    build_system_prompt,
    instantiate_model,
    parse_reply_with_code,
)
from layout import (
    FreeGeometryError,
    FreeGeometryLayout,
    ModelLayout,
    execute_build123d_code,
    generate_layout,
)
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
MAX_LLM_ATTEMPTS = 10
INVALID_RESPONSE_MESSAGE = (
    f"The AI could not produce a valid response after {MAX_LLM_ATTEMPTS} attempts. "
    "Please try again."
)

logger = logging.getLogger("nomo")


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    yield
    # An AI CLI still answering a prompt runs in its own process group and would
    # outlive the server
    stop_running_tools()


app = FastAPI(title="Nomo CAD Web Interface", lifespan=lifespan)


@app.middleware("http")
async def add_no_cache_headers_for_static(request: Request, call_next: Any) -> Response:
    response: Response = await call_next(request)
    request_path = request.url.path
    is_root_path = request_path == "/"
    is_static_path = request_path.startswith("/static/")
    if is_root_path or is_static_path:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    role: Literal["user", "assistant"]
    content: StrictStr


class PromptRequest(BaseModel):
    prompt: str
    conversation: list[ConversationMessage] = Field(default_factory=list)
    current_model: list[dict[str, Any]] = Field(default_factory=list)
    free_geometry: bool = Field(
        default=False,
        validation_alias=AliasChoices("free_geometry", "free-geometry"),
    )
    language: Literal["en", "ar"] = "en"


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
    layout: dict[str, Any] | None = None
    build123d_code: str | None = None


active_layout: ModelLayout | FreeGeometryLayout | None = None


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


def create_invalid_response_prompt(
    original_prompt: str, invalid_response: str, validation_error: str
) -> str:
    """Build a correction request containing the last invalid answer and its errors."""
    return (
        "Your previous response did not match the required JSON response schema. "
        "Correct it and return only a valid JSON object.\n\n"
        f"Original user request:\n{original_prompt}\n\n"
        f"Previous invalid response:\n{invalid_response}\n\n"
        f"Validation error:\n{validation_error}"
    )


def create_contextual_user_prompt(
    prompt: str,
    conversation: list[ConversationMessage],
    current_model: list[dict[str, Any]],
) -> str:
    """Include the prior chat and current design when asking the AI to refine a model."""
    if not conversation and not current_model:
        return prompt

    context = {
        "conversation": [message.model_dump(mode="json") for message in conversation],
        "current_model": current_model,
    }
    return (
        "Use this prior conversation and current model as context for the new request. "
        "The current model is the complete design to refine.\n\n"
        f"{json.dumps(context, indent=2, ensure_ascii=False)}\n\n"
        f"New user request:\n{prompt}"
    )


@app.post("/api/prompt", response_model=PromptResponse, response_model_by_alias=True)
async def process_prompt(request: PromptRequest) -> PromptResponse:
    global active_layout

    try:
        current_model_instances = instantiate_model(request.current_model)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    current_model = [
        instance.model_dump(mode="json") for instance in current_model_instances
    ]

    config_path = BASE_DIR / "config.json"
    with config_path.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)
    default_system_prompt = config.get("system-prompt") or config.get(
        "system_prompt", "You are Nomo CAD assistant."
    )
    if request.free_geometry:
        system_prompt = (
            config.get("free-geometry-system-prompt")
            or config.get("free_geometry_system_prompt")
            or default_system_prompt
        )
    else:
        system_prompt = default_system_prompt
    full_system_prompt = build_system_prompt(
        system_prompt, free_geometry=request.free_geometry, language=request.language
    )
    original_user_prompt = create_contextual_user_prompt(
        request.prompt, request.conversation, current_model
    )
    current_user_prompt = original_user_prompt

    for attempt_number in range(MAX_LLM_ATTEMPTS):
        try:
            answer_text = await asyncio.to_thread(
                call_llm, full_system_prompt, current_user_prompt, str(config_path)
            )
        except (RuntimeError, ValueError, OSError) as error:
            # A missing or failing AI (not installed, not signed in, timeout, unknown
            # provider, missing key) is shown to the user instead of a bare HTTP 500
            logger.warning("The AI provider failed: %s", error)
            return create_provider_error_response(request.prompt, error)
        try:
            reply, raw_model, build123d_code = parse_reply_with_code(
                answer_text,
                allow_free_geometry=request.free_geometry,
            )
            if build123d_code is not None and not raw_model:
                current_layout: (
                    ModelLayout | FreeGeometryLayout | None
                ) = await asyncio.to_thread(execute_build123d_code, build123d_code)
                instantiated_instances = []
                model_result = []
            else:
                build123d_code = None
                instantiated_instances = instantiate_model(raw_model)
                model_result = [
                    instance.model_dump(mode="json")
                    for instance in instantiated_instances
                ]
                current_layout = (
                    generate_layout(instantiated_instances)
                    if instantiated_instances
                    else None
                )
        except (
            ResponseFormatError,
            ModelValidationError,
            FreeGeometryError,
        ) as error:
            if attempt_number < MAX_LLM_ATTEMPTS - 1:
                current_user_prompt = create_invalid_response_prompt(
                    original_user_prompt, answer_text, str(error)
                )
            continue

        if current_layout is not None and current_layout.solids:
            active_layout = current_layout
            layout_details = {
                "solid_count": len(current_layout.solids),
                "bounding_box": current_layout.bounding_box.to_dict(),
                "stl_url": "/api/model/stl",
                "step_url": "/api/model/step",
                "free_geometry": build123d_code is not None,
            }
        else:
            active_layout = None
            layout_details = None

        return PromptResponse(
            status="ok",
            message=reply,
            prompt=request.prompt,
            schema_version=SCHEMA_VERSION,
            type=RESPONSE_TYPE,
            reply=reply,
            result=model_result,
            layout=layout_details,
            build123d_code=build123d_code,
        )

    return PromptResponse(
        status="error",
        message=INVALID_RESPONSE_MESSAGE,
        prompt=request.prompt,
        schema_version=SCHEMA_VERSION,
        type=RESPONSE_TYPE,
        reply=INVALID_RESPONSE_MESSAGE,
        result=None,
        layout=None,
    )


@app.get("/api/model/stl")
async def download_model_stl() -> Response:
    """Download the current layout as an ASCII STL file."""
    if active_layout is None or not active_layout.solids:
        raise HTTPException(status_code=404, detail="No 3D model layout generated yet.")
    stl_content = active_layout.to_stl()
    return Response(
        content=stl_content,
        media_type="model/stl",
        headers={"Content-Disposition": 'attachment; filename="model.stl"'},
    )


@app.get("/api/model/step")
async def download_model_step() -> Response:
    """Download the current layout as an ISO 10303-21 STEP file."""
    if active_layout is None or not active_layout.solids:
        raise HTTPException(status_code=404, detail="No 3D model layout generated yet.")
    step_content = active_layout.to_step()
    return Response(
        content=step_content,
        media_type="model/step",
        headers={"Content-Disposition": 'attachment; filename="model.step"'},
    )


@app.post("/api/model/stl")
async def export_stl_from_instances(
    instances: list[dict[str, Any]],
) -> Response:
    """Export arbitrary model instances directly to an STL file."""
    instantiated_instances = instantiate_model(instances)
    model_layout = generate_layout(instantiated_instances)
    stl_content = model_layout.to_stl()
    return Response(
        content=stl_content,
        media_type="model/stl",
        headers={"Content-Disposition": 'attachment; filename="model.stl"'},
    )


@app.post("/api/model/step")
async def export_step_from_instances(
    instances: list[dict[str, Any]],
) -> Response:
    """Export arbitrary model instances directly to an ISO 10303-21 STEP file."""
    instantiated_instances = instantiate_model(instances)
    model_layout = generate_layout(instantiated_instances)
    step_content = model_layout.to_step()
    return Response(
        content=step_content,
        media_type="model/step",
        headers={"Content-Disposition": 'attachment; filename="model.step"'},
    )


# Serve static web assets (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def get_index():
    return FileResponse(INDEX_HTML_PATH)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
