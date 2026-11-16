import pytest

from catalog import (
    ResponseFormatError,
    build_system_prompt,
    load_templates,
    parse_reply,
)


def test_prompt_lists_all_templates():
    prompt = build_system_prompt("BASE")
    assert prompt.startswith("BASE")
    for template_id in ("box", "sphere", "cylinder"):
        assert f'"id": "{template_id}"' in prompt


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
