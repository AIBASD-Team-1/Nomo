import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

EXPECTED_DOM_ELEMENT_IDS = [
    "chat-form",
    "prompt-input",
    "send-btn",
    "chat-messages",
    "tab-table",
    "tab-raw",
    "json-table-view",
    "json-raw-view",
    "table-placeholder",
    "table-results",
    "json-table-body",
    "json-raw-code",
    "copy-json-btn",
    "json-status-indicator",
]


def test_index_page_loads_and_contains_expected_panels():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Chat Window" in response.text
    assert "Output Panel" in response.text
    assert "JSON Table" in response.text


def test_index_contains_all_frontend_contract_element_ids():
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    for element_id in EXPECTED_DOM_ELEMENT_IDS:
        assert f'id="{element_id}"' in html, (
            f"Missing required element id: {element_id}"
        )


@pytest.mark.parametrize(
    "path, expected_mime",
    [
        ("/static/style.css", "text/css"),
        ("/static/app.js", "javascript"),
    ],
)
def test_static_files_delivery(path: str, expected_mime: str):
    response = client.get(path)
    assert response.status_code == 200
    assert expected_mime in response.headers.get("content-type", "")


def test_prompt_endpoint_returns_valid_json_contract(monkeypatch):
    """
    Verifies that the prompt endpoint accepts a valid prompt and adheres to the
    response contract schema.
    """
    prompt_text = "Kitchen table 160 x 90 cm"
    monkeypatch.setattr(
        main,
        "call_llm",
        lambda system_prompt, user_prompt, config_path: (
            '{"reply": "Mock reply", "model": []}'
        ),
    )
    response = client.post("/api/prompt", json={"prompt": prompt_text})

    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")

    data = response.json()
    assert isinstance(data, dict)
    assert data["status"] == "ok"
    assert data["prompt"] == prompt_text
    assert data["message"] == "Mock reply"
    assert data["schema-version"] == "1.00"
    assert data["type"] == "response"
    assert data["reply"] == "Mock reply"
    assert data["result"] == []


def test_prompt_endpoint_retries_invalid_answer_with_validation_error(monkeypatch):
    prompt_text = "Kitchen table"
    user_prompts = []
    answers = iter(
        [
            '{"reply": "invalid", "model": [{"id": "table"}]}',
            '{"reply": "Corrected answer", "model": []}',
        ]
    )

    def mock_call_llm(system_prompt, user_prompt, config_path):
        user_prompts.append(user_prompt)
        return next(answers)

    monkeypatch.setattr(main, "call_llm", mock_call_llm)
    response = client.post("/api/prompt", json={"prompt": prompt_text})

    assert response.status_code == 200
    assert response.json()["reply"] == "Corrected answer"
    assert response.json()["result"] == []
    assert len(user_prompts) == 2
    assert prompt_text in user_prompts[1]
    assert "Previous invalid response" in user_prompts[1]
    assert "Validation error" in user_prompts[1]
    assert "id" in user_prompts[1]


def test_prompt_endpoint_returns_error_after_ten_invalid_answers(monkeypatch):
    invalid_responses = []

    def mock_call_llm(system_prompt, user_prompt, config_path):
        invalid_responses.append(user_prompt)
        return "Invalid response that must not reach the user"

    monkeypatch.setattr(main, "call_llm", mock_call_llm)
    response = client.post("/api/prompt", json={"prompt": "Make a table"})

    assert response.status_code == 200
    data = response.json()
    assert len(invalid_responses) == main.MAX_LLM_ATTEMPTS
    assert data["status"] == "error"
    assert data["reply"] == main.INVALID_RESPONSE_MESSAGE
    assert data["result"] is None
    assert "Invalid response that must not reach the user" not in response.text


def test_prompt_endpoint_rejects_missing_payload():
    """
    Verifies that the endpoint validates the request body and returns 422
    when required fields are missing.
    """
    response = client.post("/api/prompt", json={})
    assert response.status_code == 422
