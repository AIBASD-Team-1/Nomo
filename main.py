from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Nomo CAD Web Interface")


class PromptRequest(BaseModel):
    prompt: str


@app.post("/api/prompt")
async def process_prompt(request: PromptRequest) -> dict[str, Any]:
    """
    Dummy AI endpoint: Returns a JSON response indicating that the AI does not exist yet.
    """
    return {
        "status": "ai_not_implemented",
        "message": "The AI does not exist yet.",
        "prompt": request.prompt,
        "schema-version": "1.00",
        "type": "response",
        "reply": "The AI does not exist yet. Got prompt: " + request.prompt,
        "result": None,
    }


# Serve static web files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def get_index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
