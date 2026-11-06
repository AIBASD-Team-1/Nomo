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
    assert ":root" in css_res.text

    js_res = client.get("/static/app.js")
    assert js_res.status_code == 200
    assert "renderJsonTable" in js_res.text

def test_dummy_ai_prompt_endpoint():
    prompt_text = "Kitchen table 160 x 90 cm"
    response = client.post("/api/prompt", json={"prompt": prompt_text})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ai_not_implemented"
    assert "not exist yet" in data["message"].lower()
    assert data["prompt"] == prompt_text
