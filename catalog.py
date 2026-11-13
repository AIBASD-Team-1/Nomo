"""Template catalog and the prompt/response format the AI uses to build models from it."""

import json
from typing import Any

TEMPLATES = [
    {
        "id": "box",
        "description": "Cuboid, e.g. for panels, legs, battens",
        "parameters": {
            "length": {"unit": "mm", "min": 1, "max": 10000, "default": 100},
            "width": {"unit": "mm", "min": 1, "max": 10000, "default": 100},
            "height": {"unit": "mm", "min": 1, "max": 10000, "default": 100},
        },
        "rules": [],
        "origin": "centre of the bottom face; length along X, width along Y, height along Z",
    },
    {
        "id": "sphere",
        "description": "Full sphere, e.g. for knobs, balls, ball feet",
        "parameters": {
            "diameter": {"unit": "mm", "min": 1, "max": 10000, "default": 100},
        },
        "rules": [],
        "origin": "lowest point of the sphere; centre at height diameter / 2",
    },
    {
        "id": "cylinder",
        "description": "Solid circular cylinder, e.g. for round legs, rods, pins, dowels",
        "parameters": {
            "diameter": {"unit": "mm", "min": 1, "max": 10000, "default": 100},
            "height": {"unit": "mm", "min": 1, "max": 10000, "default": 100},
        },
        "rules": [],
        "origin": "centre of the bottom face; axis along Z",
    },
]

INSTRUCTIONS = """\
Build the product the user describes ONLY from the templates in this catalog:
{catalog}

Conventions:
- All dimensions in mm. Z points up. Parts stand on the XY plane (z = 0) by default.
- Each instance is rotated about its template origin by `rotation` (degrees, about fixed X, then Y,
  then Z, right-hand rule), then moved so its origin sits at `position`.
- Every parameter value must be a number within the template's min/max. Omitted parameters use the default.

Answer with ONE JSON object and nothing else:
{{"reply": "<short message to the user>",
  "model": [{{"id": "<unique instance id>", "template": "<template id>",
             "parameters": {{"<name>": <number>}},
             "position": {{"x": 0, "y": 0, "z": 0}}, "rotation": {{"x": 0, "y": 0, "z": 0}}}}]}}
If no template fits the request, say so in "reply" and return "model": [].
"""


def build_system_prompt(base_prompt: str) -> str:
    """Append the template catalog and the answer format to the configured system prompt."""
    catalog_json = json.dumps(TEMPLATES, indent=2)
    instructions = INSTRUCTIONS.format(catalog=catalog_json)
    return f"{base_prompt}\n\n{instructions}"


def parse_reply(answer_text: str) -> tuple[str, list[dict[str, Any]] | None]:
    """
    Split the AI answer into the message for the user and the model.

    The model is None when the answer is not the expected JSON object,
    in that case the whole answer text is used as the message.
    """
    # The JSON object is taken from the first "{" to the last "}".
    # This removes ```json fences and any text the AI writes around the object.
    # ponytail: switch to the provider's JSON mode if answers still fail to parse
    json_start = answer_text.find("{")
    json_end = answer_text.rfind("}") + 1
    json_text = answer_text[json_start:json_end]

    try:
        answer_data = json.loads(json_text)
    except ValueError:
        return answer_text, None

    if not isinstance(answer_data, dict):
        return answer_text, None

    model = answer_data.get("model")
    if not isinstance(model, list):
        return answer_text, None

    reply = str(answer_data.get("reply", ""))
    return reply, model
