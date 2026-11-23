import pytest

from catalog import (
    FREE_GEOMETRY_INSTRUCTIONS,
    INSTRUCTIONS,
    ResponseFormatError,
    build_free_geometry_system_prompt,
    build_system_prompt,
    load_templates,
    parse_reply,
    parse_reply_with_code,
)


def test_prompt_lists_all_templates():
    prompt = build_system_prompt("BASE")
    assert prompt.startswith("BASE")
    for template_id in ("box", "sphere", "cylinder"):
        assert f'"id": "{template_id}"' in prompt
    assert "ONLY from the templates in this catalog" in prompt
    assert "build123d_code" not in prompt


def test_free_geometry_system_prompt_differs_from_standard_prompt():
    standard_prompt = build_system_prompt("BASE", free_geometry=False)
    free_prompt = build_system_prompt("BASE", free_geometry=True)
    helper_free_prompt = build_free_geometry_system_prompt("BASE")

    assert free_prompt == helper_free_prompt
    assert free_prompt != standard_prompt
    assert FREE_GEOMETRY_INSTRUCTIONS != INSTRUCTIONS
    assert "Free geometry fallback (ENABLED)" in free_prompt
    assert "build123d_code" in free_prompt
    assert "from build123d import *" in free_prompt
    for template_id in ("box", "sphere", "cylinder"):
        assert f'"id": "{template_id}"' in free_prompt


def test_parse_reply_extracts_fenced_json():
    text = (
        '```json\n{"reply": "A ball", "model": [{"id": "b1", "template": "sphere", '
        '"parameters": {}, "position": {"x": 0, "y": 0, "z": 0}, '
        '"rotation": {"x": 0, "y": 0, "z": 0}}]}\n```'
    )
    assert parse_reply(text) == (
        "A ball",
        [
            {
                "id": "b1",
                "template": "sphere",
                "parameters": {},
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
            }
        ],
    )


@pytest.mark.parametrize(
    "answer_text",
    [
        "Sorry, no idea.",
        '{"reply": "no model key"}',
        '{"reply": "bad model", "model": [{"id": "b1", "template": "sphere"}]}',
        ('Here is the answer: {"reply": "not just JSON", "model": []}'),
        ('{"reply": "bad vector", "model": [], "unexpected": true}'),
        (
            '{"reply": "bad vector", "model": [{"id": "b1", "template": "sphere", '
            '"parameters": {}, "position": {"x": "0", "y": 0, "z": 0}, '
            '"rotation": {"x": 0, "y": 0, "z": 0}}]}'
        ),
        (
            '{"reply": "duplicate ids", "model": ['
            '{"id": "b1", "template": "box", "parameters": {}, '
            '"position": {"x": 0, "y": 0, "z": 0}, '
            '"rotation": {"x": 0, "y": 0, "z": 0}}, '
            '{"id": "b1", "template": "sphere", "parameters": {}, '
            '"position": {"x": 0, "y": 0, "z": 0}, '
            '"rotation": {"x": 0, "y": 0, "z": 0}}]}'
        ),
    ],
)
def test_parse_reply_rejects_invalid_json_or_schema(answer_text):
    with pytest.raises(ResponseFormatError):
        parse_reply(answer_text)


def test_load_templates_rejects_file_name_that_does_not_match_id(tmp_path):
    template_path = tmp_path / "box.json"
    template_path.write_text('{"id": "cube"}', encoding="utf-8")

    with pytest.raises(ValueError, match="id must be 'box'"):
        load_templates(tmp_path)


def test_parse_reply_with_code_accepts_build123d_fallback_when_enabled():
    answer_text = (
        '{"reply": "Generated cone via free geometry", '
        '"model": [], '
        '"build123d_code": "from build123d import *\\nresult = Cone(40, 0, 80)"}'
    )
    reply, model, code = parse_reply_with_code(answer_text, allow_free_geometry=True)
    assert reply == "Generated cone via free geometry"
    assert model == []
    assert code == "from build123d import *\nresult = Cone(40, 0, 80)"


def test_parse_reply_with_code_rejects_build123d_when_disabled():
    answer_text = (
        '{"reply": "Generated cone via free geometry", '
        '"model": [], '
        '"build123d_code": "result = Cone(40, 0, 80)"}'
    )
    with pytest.raises(ResponseFormatError, match="not allowed"):
        parse_reply_with_code(answer_text, allow_free_geometry=False)


def test_parse_reply_with_code_rejects_empty_build123d_code():
    answer_text = '{"reply": "Empty code", "model": [], "build123d_code": "   "}'
    with pytest.raises(ResponseFormatError, match="must not be empty"):
        parse_reply_with_code(answer_text, allow_free_geometry=True)
