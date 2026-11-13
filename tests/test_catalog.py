from catalog import build_system_prompt, parse_reply


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
