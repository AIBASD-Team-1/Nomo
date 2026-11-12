import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

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


def test_prompt_endpoint_returns_valid_json_contract():
    """
    Verifies that the prompt endpoint accepts a valid prompt and adheres to the
    response contract schema.
    """
    prompt_text = "Kitchen table 160 x 90 cm"
    response = client.post("/api/prompt", json={"prompt": prompt_text})

    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")

    data = response.json()
    assert isinstance(data, dict)
    assert data["status"] == "ai_not_implemented"
    assert data["prompt"] == prompt_text
    assert "The AI does not exist yet" in data["message"]
    assert data["schema-version"] == "1.00"
    assert data["type"] == "response"
    assert "reply" in data
    assert data["result"] is None


def test_prompt_endpoint_rejects_missing_payload():
    """
    Verifies that the endpoint validates the request body and returns 422
    when required fields are missing.
    """
    response = client.post("/api/prompt", json={})
    assert response.status_code == 422
