"""Template catalog and the prompt/response format the AI uses to build models from it."""

import json
import re
from pathlib import Path
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StrictStr,
    ValidationError,
    model_validator,
)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
FENCED_JSON_PATTERN = re.compile(
    r"\A```(?:json)?[ \t]*\r?\n(.*?)\r?\n```[ \t]*\Z",
    re.DOTALL | re.IGNORECASE,
)


class Vector3(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    x: FiniteFloat
    y: FiniteFloat
    z: FiniteFloat


class ModelInstance(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: StrictStr = Field(min_length=1)
    template: StrictStr = Field(min_length=1)
    parameters: dict[StrictStr, FiniteFloat]
    position: Vector3
    rotation: Vector3


class LLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    reply: StrictStr
    model: list[ModelInstance]

    @model_validator(mode="after")
    def validate_unique_instance_ids(self) -> Self:
        instance_ids: set[str] = set()
        for instance in self.model:
            if instance.id in instance_ids:
                raise ValueError(f"Instance id '{instance.id}' must be unique.")
            instance_ids.add(instance.id)
        return self


class ResponseFormatError(ValueError):
    """Raised when an LLM response cannot be parsed or fails its schema."""


def load_templates(templates_dir: Path = TEMPLATES_DIR) -> list[dict[str, Any]]:
    """
    Load every template from its own JSON file in the templates folder.

    The file name must match the template id, e.g. templates/box.json has "id": "box".
    """
    templates = []
    for template_path in sorted(templates_dir.glob("*.json")):
        template_text = template_path.read_text(encoding="utf-8")
        template = json.loads(template_text)
        if template.get("id") != template_path.stem:
            raise ValueError(
                f"{template_path.name}: id must be '{template_path.stem}', "
                f"got '{template.get('id')}'"
            )
        templates.append(template)
    return templates


TEMPLATES = load_templates()

INSTRUCTIONS = """\
Build the product the user describes ONLY from the templates in this catalog:
{catalog}

Conventions:
- All dimensions in mm. Z points up. Parts stand on the XY plane (z = 0) by default.
- Each instance is rotated about its template origin by `rotation` (degrees, about fixed X, then Y,
  then Z, right-hand rule), then moved so its origin sits at `position`.
- Every parameter value must be a number within the template's min/max. Omitted parameters use the default.

Answer with ONE JSON object and nothing else, matching this exact structure. Do not add any other keys:
{{"reply": "<short message to the user>",
  "model": [{{"id": "<unique instance id>", "template": "<template id>",
             "parameters": {{"<name>": <number>}},
             "position": {{"x": 0, "y": 0, "z": 0}}, "rotation": {{"x": 0, "y": 0, "z": 0}}}}]}}
Every instance must contain all five fields shown; `parameters` may be empty. `position` and `rotation`
must each contain numeric `x`, `y`, and `z` values only. `reply` must be a string and `model` must be
an array. No fit is still a valid response: explain it in `reply` and return `"model": []`.
"""


def build_system_prompt(base_prompt: str) -> str:
    """Append the template catalog and the answer format to the configured system prompt."""
    catalog_json = json.dumps(TEMPLATES, indent=2)
    instructions = INSTRUCTIONS.format(catalog=catalog_json)
    return f"{base_prompt}\n\n{instructions}"


def parse_reply(answer_text: str) -> tuple[str, list[dict[str, Any]]]:
    """
    Parse and validate the AI answer before exposing any of its content.

    Raises ResponseFormatError when the answer is not valid JSON or does not
    match the required response structure.
    """
    normalized_answer = answer_text.strip()
    fenced_json = FENCED_JSON_PATTERN.fullmatch(normalized_answer)
    if fenced_json:
        normalized_answer = fenced_json.group(1).strip()

    try:
        answer_data = json.loads(normalized_answer)
    except json.JSONDecodeError as error:
        raise ResponseFormatError(
            f"Response is not valid JSON: {error.msg} "
            f"(line {error.lineno}, column {error.colno})."
        ) from error

    try:
        response = LLMResponse.model_validate(answer_data)
    except ValidationError as error:
        validation_details = json.dumps(
            error.errors(include_input=False, include_context=False), ensure_ascii=False
        )
        raise ResponseFormatError(
            f"Response does not match the required schema: {validation_details}"
        ) from error

    model = [instance.model_dump(mode="json") for instance in response.model]
    return response.reply, model
