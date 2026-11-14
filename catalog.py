"""Template catalog and the prompt/response format the AI uses to build models from it."""

import json
from pathlib import Path
from typing import Any

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


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
