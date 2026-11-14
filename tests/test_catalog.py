import pytest

from catalog import build_system_prompt, load_templates, parse_reply


def test_prompt_lists_all_templates():
    prompt = build_system_prompt("BASE")
    assert prompt.startswith("BASE")
    for template_id in ("box", "sphere", "cylinder"):
        assert f'"id": "{template_id}"' in prompt


def test_parse_reply_extracts_fenced_json():
    text = '```json\n{"reply": "A ball", "model": [{"id": "b1", "template": "sphere"}]}\n```'
    assert parse_reply(text) == ("A ball", [{"id": "b1", "template": "sphere"}])


def test_parse_reply_falls_back_to_plain_text():
    assert parse_reply("Sorry, no idea.") == ("Sorry, no idea.", None)
    assert parse_reply('{"reply": "no model key"}') == (
        '{"reply": "no model key"}',
        None,
    )


def test_load_templates_rejects_file_name_that_does_not_match_id(tmp_path):
    template_path = tmp_path / "box.json"
    template_path.write_text('{"id": "cube"}', encoding="utf-8")

    with pytest.raises(ValueError, match="id must be 'box'"):
        load_templates(tmp_path)
