"""Template catalog and the prompt/response format the AI uses to build models from it."""

import ast
import json
import operator
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
    model: list[ModelInstance] = Field(default_factory=list)
    build123d_code: StrictStr | None = None

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


SAFE_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

SAFE_UNARY_OPERATORS = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Not: operator.not_,
}

SAFE_COMPARE_OPERATORS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def evaluate_ast_node(node: ast.AST, parameters: dict[str, float]) -> Any:
    if isinstance(node, ast.Expression):
        return evaluate_ast_node(node.body, parameters)

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        variable_name = node.id
        if variable_name not in parameters:
            raise ValueError(f"Unknown variable in rule check: '{variable_name}'")
        return parameters[variable_name]

    if isinstance(node, ast.UnaryOp):
        operator_type = type(node.op)
        if operator_type not in SAFE_UNARY_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {operator_type}")
        unary_operation = SAFE_UNARY_OPERATORS[operator_type]
        operand_value = evaluate_ast_node(node.operand, parameters)
        return unary_operation(operand_value)

    if isinstance(node, ast.BinOp):
        operator_type = type(node.op)
        if operator_type not in SAFE_BINARY_OPERATORS:
            raise ValueError(f"Unsupported binary operator: {operator_type}")
        binary_operation = SAFE_BINARY_OPERATORS[operator_type]
        left_value = evaluate_ast_node(node.left, parameters)
        right_value = evaluate_ast_node(node.right, parameters)
        return binary_operation(left_value, right_value)

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for value_node in node.values:
                branch_result = evaluate_ast_node(value_node, parameters)
                if not branch_result:
                    return False
            return True
        if isinstance(node.op, ast.Or):
            for value_node in node.values:
                branch_result = evaluate_ast_node(value_node, parameters)
                if branch_result:
                    return True
            return False

    if isinstance(node, ast.Compare):
        left_value = evaluate_ast_node(node.left, parameters)
        current_left = left_value
        for comparison_operator, comparator_node in zip(
            node.ops, node.comparators, strict=True
        ):
            operator_type = type(comparison_operator)
            if operator_type not in SAFE_COMPARE_OPERATORS:
                raise ValueError(f"Unsupported comparison operator: {operator_type}")
            comparison_function = SAFE_COMPARE_OPERATORS[operator_type]
            right_value = evaluate_ast_node(comparator_node, parameters)
            if not comparison_function(current_left, right_value):
                return False
            current_left = right_value
        return True

    raise ValueError(f"Unsupported syntax in rule condition: {type(node).__name__}")


def evaluate_rule_condition(condition_text: str, parameters: dict[str, float]) -> bool:
    parsed_ast = ast.parse(condition_text, mode="eval")
    evaluation_result = evaluate_ast_node(parsed_ast, parameters)
    return bool(evaluation_result)


class Violation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance_id: str
    template_id: str
    parameter: str | None = None
    message: str

    def format_message(self) -> str:
        parameter_detail = f", parameter '{self.parameter}'" if self.parameter else ""
        return (
            f"Instance '{self.instance_id}' (template '{self.template_id}'"
            f"{parameter_detail}): {self.message}"
        )


class ModelValidationError(ValueError):
    """Raised when one or more model instances fail template validation."""

    def __init__(self, violations: list[Violation]):
        self.violations = violations
        formatted_messages = [violation.format_message() for violation in violations]
        combined_message = "; ".join(formatted_messages)
        super().__init__(f"Model validation failed: {combined_message}")


class TemplateParameter(BaseModel):
    model_config = ConfigDict(extra="ignore")

    unit: str = "mm"
    min: float
    max: float
    default: float


class TemplateRule(BaseModel):
    model_config = ConfigDict(extra="ignore")

    check: str
    message: str
    parameter: str | None = None


class TemplateInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrictStr = Field(min_length=1)
    template: StrictStr = Field(min_length=1)
    parameters: dict[StrictStr, FiniteFloat]
    position: Vector3
    rotation: Vector3


class Template(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    description: str = ""
    standards: list[StrictStr] = Field(default_factory=list)
    parameters: dict[str, TemplateParameter] = Field(default_factory=dict)
    rules: list[TemplateRule] = Field(default_factory=list)
    origin: str = ""
    base: str | None = None

    def instantiate(
        self,
        instance_id: str,
        parameters: dict[str, float] | None = None,
        position: Vector3 | dict[str, float] | None = None,
        rotation: Vector3 | dict[str, float] | None = None,
    ) -> TemplateInstance:
        parameters_dict = parameters or {}
        position_vector = (
            position
            if isinstance(position, Vector3)
            else Vector3.model_validate(position or {"x": 0.0, "y": 0.0, "z": 0.0})
        )
        rotation_vector = (
            rotation
            if isinstance(rotation, Vector3)
            else Vector3.model_validate(rotation or {"x": 0.0, "y": 0.0, "z": 0.0})
        )
        catalog = {self.id: self}
        instance_item = ModelInstance(
            id=instance_id,
            template=self.id,
            parameters=parameters_dict,
            position=position_vector,
            rotation=rotation_vector,
        )
        instance, violations = instantiate_instance(instance_item, catalog)
        if violations:
            raise ModelValidationError(violations)
        assert instance is not None
        return instance


def load_template_catalog(
    templates_dir: Path = TEMPLATES_DIR,
) -> dict[str, Template]:
    """
    Load every template from JSON and resolve template inheritance (base templates).
    """
    raw_templates: dict[str, Template] = {}
    for template_path in sorted(templates_dir.glob("*.json")):
        template_text = template_path.read_text(encoding="utf-8")
        template_data = json.loads(template_text)
        expected_id = template_path.stem
        template_id = template_data.get("id")
        if template_id != expected_id:
            raise ValueError(
                f"{template_path.name}: id must be '{expected_id}', got '{template_id}'"
            )
        template = Template.model_validate(template_data)
        raw_templates[expected_id] = template

    resolved_templates: dict[str, Template] = {}

    def resolve_template(current_id: str, visited_ids: list[str]) -> Template:
        if current_id in resolved_templates:
            return resolved_templates[current_id]
        if current_id not in raw_templates:
            raise ValueError(f"Unknown template '{current_id}'.")
        if current_id in visited_ids:
            cycle_path = " -> ".join(visited_ids + [current_id])
            raise ValueError(
                f"Circular template base dependency detected: {cycle_path}"
            )

        raw_template = raw_templates[current_id]
        if not raw_template.base:
            resolved_templates[current_id] = raw_template
            return raw_template

        base_template = resolve_template(raw_template.base, visited_ids + [current_id])

        combined_parameters = dict(base_template.parameters)
        for parameter_name, parameter_definition in raw_template.parameters.items():
            combined_parameters[parameter_name] = parameter_definition

        combined_rules = list(base_template.rules) + list(raw_template.rules)
        combined_standards = list(base_template.standards) + list(
            raw_template.standards
        )
        origin = raw_template.origin or base_template.origin

        resolved = Template(
            id=raw_template.id,
            description=raw_template.description or base_template.description,
            standards=combined_standards,
            parameters=combined_parameters,
            rules=combined_rules,
            origin=origin,
            base=raw_template.base,
        )
        resolved_templates[current_id] = resolved
        return resolved

    for template_id in raw_templates:
        resolve_template(template_id, [])

    return resolved_templates


def instantiate_instance(
    instance_data: ModelInstance | dict[str, Any],
    catalog: dict[str, Template],
) -> tuple[TemplateInstance | None, list[Violation]]:
    violations: list[Violation] = []

    if isinstance(instance_data, ModelInstance):
        instance_id = instance_data.id
        template_id = instance_data.template
        raw_parameters = instance_data.parameters
        position = instance_data.position
        rotation = instance_data.rotation
    else:
        instance_id = str(instance_data.get("id", ""))
        template_id = str(instance_data.get("template", ""))
        raw_parameters = instance_data.get("parameters", {})
        position_data = instance_data.get("position", {})
        rotation_data = instance_data.get("rotation", {})
        position = Vector3.model_validate(position_data)
        rotation = Vector3.model_validate(rotation_data)

    if template_id not in catalog:
        violation = Violation(
            instance_id=instance_id,
            template_id=template_id,
            parameter=None,
            message=f"Unknown template '{template_id}'.",
        )
        violations.append(violation)
        return None, violations

    template = catalog[template_id]
    allowed_parameters = template.parameters

    for parameter_name in raw_parameters:
        if parameter_name not in allowed_parameters:
            violation = Violation(
                instance_id=instance_id,
                template_id=template_id,
                parameter=parameter_name,
                message=(
                    f"Unknown parameter '{parameter_name}' for template '{template_id}'."
                ),
            )
            violations.append(violation)

    resolved_parameters: dict[str, float] = {}
    for parameter_name, parameter_definition in allowed_parameters.items():
        if parameter_name in raw_parameters:
            parameter_value = float(raw_parameters[parameter_name])
        else:
            parameter_value = float(parameter_definition.default)

        minimum_value = parameter_definition.min
        maximum_value = parameter_definition.max
        if parameter_value < minimum_value:
            violation = Violation(
                instance_id=instance_id,
                template_id=template_id,
                parameter=parameter_name,
                message=(
                    f"Parameter '{parameter_name}' must be at least "
                    f"{minimum_value}, got {parameter_value}."
                ),
            )
            violations.append(violation)
        elif parameter_value > maximum_value:
            violation = Violation(
                instance_id=instance_id,
                template_id=template_id,
                parameter=parameter_name,
                message=(
                    f"Parameter '{parameter_name}' must be at most "
                    f"{maximum_value}, got {parameter_value}."
                ),
            )
            violations.append(violation)

        resolved_parameters[parameter_name] = parameter_value

    if not violations:
        for rule in template.rules:
            try:
                rule_satisfied = evaluate_rule_condition(
                    rule.check, resolved_parameters
                )
            except Exception as rule_error:
                violation = Violation(
                    instance_id=instance_id,
                    template_id=template_id,
                    parameter=rule.parameter,
                    message=f"Rule evaluation error: {rule_error}",
                )
                violations.append(violation)
                continue

            if not rule_satisfied:
                violation = Violation(
                    instance_id=instance_id,
                    template_id=template_id,
                    parameter=rule.parameter,
                    message=rule.message,
                )
                violations.append(violation)

    if violations:
        return None, violations

    instantiated_instance = TemplateInstance(
        id=instance_id,
        template=template_id,
        parameters=resolved_parameters,
        position=position,
        rotation=rotation,
    )
    return instantiated_instance, []


def instantiate_model(
    model_data: list[ModelInstance] | list[dict[str, Any]],
    catalog: dict[str, Template] | None = None,
) -> list[TemplateInstance]:
    """
    Instantiate and validate every template in a model.

    Resolves parameter defaults, checks parameter ranges and template rules.
    Raises ModelValidationError if any violations occur.
    """
    active_catalog = catalog if catalog is not None else load_template_catalog()
    instantiated_instances: list[TemplateInstance] = []
    collected_violations: list[Violation] = []

    for item in model_data:
        instance, violations = instantiate_instance(item, active_catalog)
        if violations:
            collected_violations.extend(violations)
        elif instance is not None:
            instantiated_instances.append(instance)

    if collected_violations:
        raise ModelValidationError(collected_violations)

    return instantiated_instances


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
- Write `reply` in the language of the user's request (e.g. Arabic for an Arabic request). Read Eastern
  Arabic digits (٠–٩) like Western digits (0–9). Ids, template ids and parameter names stay English.
- Each instance is rotated about its template origin by `rotation` (degrees, about fixed X, then Y,
  then Z, right-hand rule), then moved so its origin sits at `position`.
- Every parameter value must be a number within the template's min/max. Omitted parameters use the default.
- Treat every human-readable `standards` entry in the catalog as mandatory, including standards inherited
  from a template's `base`. Never return model data that violates a standard. If the request conflicts
  with a standard, make a compliant adjustment when feasible and explain the standard and change in
  `reply`. Otherwise return `"model": []` and explain why the request cannot be fulfilled.
- Do not use another template or free geometry to bypass an applicable standard.

Answer with ONE JSON object and nothing else, matching this exact structure. Do not add any other keys:
{{"reply": "<short message to the user>",
  "model": [{{"id": "<unique instance id>", "template": "<template id>",
             "parameters": {{"<name>": <number>}},
             "position": {{"x": 0, "y": 0, "z": 0}}, "rotation": {{"x": 0, "y": 0, "z": 0}}}}]}}
Every instance must contain all five fields shown; `parameters` may be empty. `position` and `rotation`
must each contain numeric `x`, `y`, and `z` values only. `reply` must be a string and `model` must be
an array. No fit is still a valid response: explain it in `reply` and return `"model": []`.
When the user message includes a prior conversation and current model, use them to interpret the new
request and refine that design. Return the complete updated model, including unchanged instances that
should remain in the design. Replace the design only when the user asks to start over.
"""


FREE_GEOMETRY_INSTRUCTIONS = """\
Build the product the user describes. First try to use the templates in this catalog:
{catalog}

Conventions:
- All dimensions in mm. Z points up. Parts stand on the XY plane (z = 0) by default.
- Write `reply` in the language of the user's request (e.g. Arabic for an Arabic request). Read Eastern
  Arabic digits (٠–٩) like Western digits (0–9). Ids, template ids and parameter names stay English.
- Each template instance is rotated about its template origin by `rotation` (degrees, about fixed X,
  then Y, then Z, right-hand rule), then moved so its origin sits at `position`.
- Every template parameter value must be a number within the template's min/max. Omitted parameters
  use the default.
- Treat every human-readable `standards` entry in the catalog as mandatory, including standards inherited
  from a template's `base`. Never return model data that violates a standard. If the request conflicts
  with a standard, make a compliant adjustment when feasible and explain the standard and change in
  `reply`. Otherwise return `"model": []` and explain why the request cannot be fulfilled.
- Do not use free geometry or another template to bypass an applicable standard.

Free geometry fallback (ENABLED):
- If a matching template exists in the catalog, return `"model"` with the template instances and
  do not include `"build123d_code"`.
- ONLY when no matching template exists in the catalog for the user's request, return `"model": []`
  and provide `"build123d_code"` containing valid Python code using `build123d` (`from build123d import *`)
  that builds the requested 3D solid and assigns the final solid or part to a variable named `result`
  (or `part`). Mention in `"reply"` that free geometry was generated because no matching template exists.
- In `build123d`, class names use PascalCase (capitalized), NEVER lowercase:
  - 3D Solids: `Box(length, width, height)`, `Cylinder(radius, height)`, `Sphere(radius)`,
    `Cone(bottom_radius, top_radius, height)`, `Torus(major_radius, minor_radius)`,
    `Wedge(xsize, ysize, zsize, xmin, zmin, xmax, zmax)`.
  - 2D Sketches + Extrude: `with BuildPart() as p: with BuildSketch(): RegularPolygon(radius=20, side_count=6); extrude(amount=12); Cylinder(radius=8, height=12, mode=Mode.SUBTRACT); result = p.part`
  - Positioning & Rotation (Algebra mode): use `Pos(x, y, z) * Rot(rx, ry, rz) * Box(...)` (there is NO `translate()` or `rotate()` function; use `Pos` and `Rot` or `with Locations((x, y, z)):`).
  - Boolean operations: `+` (union), `-` (subtract), `&` (intersect).

Answer with ONE JSON object and nothing else, matching one of these exact structures. Do not add any other keys:
1. Template model (when templates fit):
{{"reply": "<short message to the user>",
  "model": [{{"id": "<unique instance id>", "template": "<template id>",
             "parameters": {{"<name>": <number>}},
             "position": {{"x": 0, "y": 0, "z": 0}}, "rotation": {{"x": 0, "y": 0, "z": 0}}}}]}}
2. Free geometry fallback (when no matching template exists):
{{"reply": "<short message to the user>",
  "model": [],
  "build123d_code": "<valid build123d Python code assigning the 3D shape to `result`>"}}

When the user message includes a prior conversation and current model, use them to interpret the new
request and refine that design.
"""


def build_system_prompt(base_prompt: str, free_geometry: bool = False) -> str:
    """Append the template catalog and the answer format to the configured system prompt."""
    catalog_json = json.dumps(TEMPLATES, indent=2)
    template = FREE_GEOMETRY_INSTRUCTIONS if free_geometry else INSTRUCTIONS
    instructions = template.format(catalog=catalog_json)
    return f"{base_prompt}\n\n{instructions}"


def build_free_geometry_system_prompt(base_prompt: str) -> str:
    """Build the system prompt with free geometry fallback instructions enabled."""
    return build_system_prompt(base_prompt, free_geometry=True)


def parse_reply_with_code(
    answer_text: str,
    allow_free_geometry: bool = False,
) -> tuple[str, list[dict[str, Any]], str | None]:
    """
    Parse and validate the AI answer, returning (reply, model, build123d_code).

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

    if isinstance(answer_data, dict):
        has_model_key = "model" in answer_data
        has_code_key = "build123d_code" in answer_data
        if not has_model_key and not (allow_free_geometry and has_code_key):
            raise ResponseFormatError(
                "Response does not match the required schema: missing required key 'model'."
            )
        if has_code_key and not allow_free_geometry:
            raise ResponseFormatError(
                "Response does not match the required schema: 'build123d_code' is not allowed when free geometry fallback is disabled."
            )

    try:
        response = LLMResponse.model_validate(answer_data)
    except ValidationError as error:
        validation_details = json.dumps(
            error.errors(include_input=False, include_context=False), ensure_ascii=False
        )
        raise ResponseFormatError(
            f"Response does not match the required schema: {validation_details}"
        ) from error

    code_text = (
        response.build123d_code.strip()
        if response.build123d_code and response.build123d_code.strip()
        else None
    )
    if response.build123d_code is not None and code_text is None:
        raise ResponseFormatError(
            "Response does not match the required schema: 'build123d_code' must not be empty."
        )

    model = [instance.model_dump(mode="json") for instance in response.model]
    return response.reply, model, code_text


def parse_reply(answer_text: str) -> tuple[str, list[dict[str, Any]]]:
    """
    Parse and validate the AI answer before exposing any of its content.

    Raises ResponseFormatError when the answer is not valid JSON or does not
    match the required response structure.
    """
    reply, model, _ = parse_reply_with_code(answer_text, allow_free_geometry=False)
    return reply, model
