from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_index_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "Chat Window" in response.text
    assert "Output Panel" in response.text
    assert "JSON Table" in response.text

def test_static_files():
    css_res = client.get("/static/style.css")
    assert css_res.status_code == 200

    js_res = client.get("/static/app.js")
    assert js_res.status_code == 200

def test_prompt_endpoint_returns_json():
    """
    Ensures the prompt endpoint accepts a prompt and returns a valid JSON response.
    Designed to pass for both dummy and future real AI/CAD implementations.
    """
    prompt_text = "Kitchen table 160 x 90 cm"
    response = client.post("/api/prompt", json={"prompt": prompt_text})
    
    # Must return 200 OK
    assert response.status_code == 200
    
    # Must be valid JSON response
    assert "application/json" in response.headers.get("content-type", "")
    data = response.json()
    assert isinstance(data, dict)
    assert len(data) > 0
    
    # Accepts dummy response as well as future full CAD/model JSON
    has_expected_field = any(
        key in data for key in ["prompt", "reply", "status", "schema-version", "model", "result", "message"]
    )
    assert has_expected_field, f"Response JSON does not contain expected keys: {data}"
