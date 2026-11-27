import re

import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

EXPECTED_DOM_ELEMENT_IDS = [
    "chat-form",
    "prompt-input",
    "send-btn",
    "chat-messages",
    "free-geometry-toggle",
    "tab-3d",
    "tab-table",
    "tab-raw",
    "three-view",
    "three-placeholder",
    "three-container",
    "three-canvas",
    "three-part-count",
    "reset-cam-btn",
    "toggle-wireframe-btn",
    "download-stl-btn",
    "download-step-btn",
    "json-table-view",
    "json-raw-view",
    "table-placeholder",
    "table-results",
    "json-table-body",
    "json-raw-code",
    "copy-json-btn",
    "json-status-indicator",
    "language-toggle",
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
    "arabic_text",
    [
        "نافذة المحادثة",
        "إرسال",
        "لوحة النتائج",
        "نسخ JSON",
        "جارٍ الإنشاء…",
        "يرجى كتابة وصف التصميم أولًا.",
        "تعذّر إنشاء النموذج. حاول مرة أخرى.",
        "تم النسخ",
    ],
)
def test_app_js_contains_arabic_demo_path_labels(arabic_text: str):
    app_js = client.get("/static/app.js").content.decode("utf-8")
    assert arabic_text in app_js


def test_index_supports_arabic_right_to_left_layout():
    html = client.get("/").content.decode("utf-8")
    assert 'localStorage.getItem("nomo-language")' in html
    assert 'document.documentElement.dir = language === "ar" ? "rtl" : "ltr"' in html
    assert re.search(r'<pre\s+dir="ltr"', html)


def test_index_contains_threejs_script_and_3d_viewer():
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "three.min.js" in html
    assert "3D View" in html
    assert 'id="three-canvas"' in html


def test_index_contains_free_geometry_toggle_and_app_js_sends_flag():
    index_response = client.get("/")
    assert index_response.status_code == 200
    html = index_response.text
    assert 'id="free-geometry-toggle"' in html
    assert 'type="checkbox"' in html
    assert "Free geometry" in html

    app_js_response = client.get("/static/app.js")
    assert app_js_response.status_code == 200
    app_js = app_js_response.text
    assert "free-geometry-toggle" in app_js
    assert "free_geometry" in app_js


def test_prompt_request_accepts_free_geometry_toggle_flag(monkeypatch):
    captured_system_prompts = []

    def mock_call_llm(system_prompt, user_prompt, config_path):
        captured_system_prompts.append(system_prompt)
        return '{"reply": "Mock reply", "model": []}'

    monkeypatch.setattr(main, "call_llm", mock_call_llm)
    response_off = client.post(
        "/api/prompt",
        json={"prompt": "A custom shape", "free_geometry": False},
    )
    assert response_off.status_code == 200
    assert response_off.json()["status"] == "ok"

    response_on = client.post(
        "/api/prompt",
        json={"prompt": "A custom shape", "free_geometry": True},
    )
    assert response_on.status_code == 200
    assert response_on.json()["status"] == "ok"

    assert len(captured_system_prompts) == 2
    prompt_when_off, prompt_when_on = captured_system_prompts
    assert prompt_when_off != prompt_when_on
    assert "ONLY from the templates in this catalog" in prompt_when_off
    assert "build123d_code" not in prompt_when_off
    assert "Free geometry fallback (ENABLED)" in prompt_when_on
    assert "build123d_code" in prompt_when_on


@pytest.mark.parametrize(
    "path, expected_mime",
    [
        ("/static/style.css", "text/css"),
        ("/static/app.js", "javascript"),
        ("/static/three.min.js", "javascript"),
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


def test_prompt_endpoint_includes_conversation_and_current_model(monkeypatch):
    user_prompts = []
    current_model = [
        {
            "id": "box_1",
            "template": "box",
            "parameters": {"length": 100, "width": 100, "height": 100},
            "position": {"x": 0, "y": 0, "z": 0},
            "rotation": {"x": 0, "y": 0, "z": 0},
        }
    ]

    def mock_call_llm(system_prompt, user_prompt, config_path):
        user_prompts.append(user_prompt)
        return '{"reply": "Made it longer", "model": []}'

    monkeypatch.setattr(main, "call_llm", mock_call_llm)
    response = client.post(
        "/api/prompt",
        json={
            "prompt": "Make it longer",
            "conversation": [
                {"role": "user", "content": "Make a 100 mm box"},
                {"role": "assistant", "content": "I made a box"},
            ],
            "current_model": current_model,
        },
    )

    assert response.status_code == 200
    assert "Make a 100 mm box" in user_prompts[0]
    assert "I made a box" in user_prompts[0]
    assert '"length": 100.0' in user_prompts[0]
    assert "New user request:\nMake it longer" in user_prompts[0]


def test_prompt_endpoint_rejects_invalid_current_model_without_calling_ai(monkeypatch):
    def unexpected_call_llm(system_prompt, user_prompt, config_path):
        pytest.fail("The AI should not be called with an invalid current model.")

    monkeypatch.setattr(main, "call_llm", unexpected_call_llm)
    response = client.post(
        "/api/prompt",
        json={
            "prompt": "Make it longer",
            "current_model": [
                {
                    "id": "box_1",
                    "template": "unknown",
                    "parameters": {},
                    "position": {"x": 0, "y": 0, "z": 0},
                    "rotation": {"x": 0, "y": 0, "z": 0},
                }
            ],
        },
    )

    assert response.status_code == 422
    assert "Unknown template 'unknown'" in response.json()["detail"]


def test_prompt_endpoint_clears_previous_layout_when_refinement_removes_model(
    monkeypatch,
):
    main.active_layout = None
    answers = iter(
        [
            (
                '{"reply": "A box", "model": [{"id": "box_1", "template": "box", '
                '"parameters": {}, "position": {"x": 0, "y": 0, "z": 0}, '
                '"rotation": {"x": 0, "y": 0, "z": 0}}]}'
            ),
            '{"reply": "Removed the box", "model": []}',
        ]
    )
    monkeypatch.setattr(
        main, "call_llm", lambda system_prompt, user_prompt, config_path: next(answers)
    )

    first_response = client.post("/api/prompt", json={"prompt": "Make a box"})
    assert first_response.json()["layout"] is not None

    second_response = client.post(
        "/api/prompt",
        json={
            "prompt": "Remove it",
            "current_model": first_response.json()["result"],
        },
    )

    assert second_response.status_code == 200
    assert second_response.json()["result"] == []
    assert second_response.json()["layout"] is None
    assert client.get("/api/model/stl").status_code == 404


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


def test_prompt_endpoint_shows_provider_error_to_the_user(monkeypatch):
    def failing_call_llm(system_prompt, user_prompt, config_path):
        raise RuntimeError("'claude' was not found. Install it and sign in.")

    monkeypatch.setattr(main, "call_llm", failing_call_llm)
    response = client.post("/api/prompt", json={"prompt": "A box"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert data["prompt"] == "A box"
    assert data["schema-version"] == "1.00"
    assert "'claude' was not found" in data["message"]
    assert data["reply"].startswith("Error: ")
    assert data["result"] is None


def test_server_shutdown_stops_running_tools(monkeypatch):
    stop_calls = []
    monkeypatch.setattr(main, "stop_running_tools", lambda: stop_calls.append(True))

    with TestClient(main.app):
        assert stop_calls == []

    assert stop_calls == [True]


def test_prompt_endpoint_rejects_missing_payload():
    """
    Verifies that the endpoint validates the request body and returns 422
    when required fields are missing.
    """
    response = client.post("/api/prompt", json={})
    assert response.status_code == 422


def test_prompt_endpoint_instantiates_templates_and_populates_defaults(monkeypatch):
    monkeypatch.setattr(
        main,
        "call_llm",
        lambda system_prompt, user_prompt, config_path: (
            '{"reply": "A box", "model": [{"id": "box_1", "template": "box", '
            '"parameters": {"length": 250}, '
            '"position": {"x": 10, "y": 20, "z": 0}, "rotation": {"x": 0, "y": 0, "z": 0}}]}'
        ),
    )
    response = client.post("/api/prompt", json={"prompt": "Box 250 mm"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert len(data["result"]) == 1
    instantiated_instance = data["result"][0]
    assert instantiated_instance["id"] == "box_1"
    assert instantiated_instance["template"] == "box"
    assert instantiated_instance["parameters"] == {
        "length": 250.0,
        "width": 100.0,
        "height": 100.0,
    }


def test_prompt_endpoint_retries_on_model_validation_error(monkeypatch):
    user_prompts = []
    answers = iter(
        [
            (
                '{"reply": "bad", "model": [{"id": "box_1", "template": "box", '
                '"parameters": {"unknown_param": 10}, '
                '"position": {"x": 0, "y": 0, "z": 0}, "rotation": {"x": 0, "y": 0, "z": 0}}]}'
            ),
            (
                '{"reply": "fixed", "model": [{"id": "box_1", "template": "box", '
                '"parameters": {"length": 150}, '
                '"position": {"x": 0, "y": 0, "z": 0}, "rotation": {"x": 0, "y": 0, "z": 0}}]}'
            ),
        ]
    )

    def mock_call_llm(system_prompt, user_prompt, config_path):
        user_prompts.append(user_prompt)
        return next(answers)

    monkeypatch.setattr(main, "call_llm", mock_call_llm)
    response = client.post("/api/prompt", json={"prompt": "Box with param"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["reply"] == "fixed"
    assert len(user_prompts) == 2
    assert "Validation error" in user_prompts[1]
    assert "Unknown parameter 'unknown_param'" in user_prompts[1]


def test_download_endpoints_return_404_when_no_model(monkeypatch):
    main.active_layout = None
    stl_response = client.get("/api/model/stl")
    assert stl_response.status_code == 404

    step_response = client.get("/api/model/step")
    assert step_response.status_code == 404


def test_download_stl_and_step_after_prompt(monkeypatch):
    monkeypatch.setattr(
        main,
        "call_llm",
        lambda system_prompt, user_prompt, config_path: (
            '{"reply": "A box", "model": [{"id": "box_1", "template": "box", '
            '"parameters": {"length": 120, "width": 80, "height": 40}, '
            '"position": {"x": 0, "y": 0, "z": 0}, "rotation": {"x": 0, "y": 0, "z": 0}}]}'
        ),
    )
    prompt_response = client.post("/api/prompt", json={"prompt": "Make a box"})
    assert prompt_response.status_code == 200
    data = prompt_response.json()
    assert data["layout"] is not None
    assert data["layout"]["solid_count"] == 1
    assert data["layout"]["stl_url"] == "/api/model/stl"
    assert data["layout"]["step_url"] == "/api/model/step"

    # Test GET STL
    stl_response = client.get("/api/model/stl")
    assert stl_response.status_code == 200
    assert "model/stl" in stl_response.headers.get("content-type", "")
    assert 'attachment; filename="model.stl"' in stl_response.headers.get(
        "content-disposition", ""
    )
    assert "solid nomo_layout" in stl_response.text

    # Test GET STEP
    step_response = client.get("/api/model/step")
    assert step_response.status_code == 200
    assert "model/step" in step_response.headers.get("content-type", "")
    assert 'attachment; filename="model.step"' in step_response.headers.get(
        "content-disposition", ""
    )
    assert "ISO-10303-21;" in step_response.text
    assert "MANIFOLD_SOLID_BREP" in step_response.text


def test_export_endpoints_with_direct_post():
    payload = [
        {
            "id": "direct_box",
            "template": "box",
            "parameters": {"length": 100.0, "width": 50.0, "height": 25.0},
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
        }
    ]
    stl_response = client.post("/api/model/stl", json=payload)
    assert stl_response.status_code == 200
    assert "solid nomo_layout" in stl_response.text

    step_response = client.post("/api/model/step", json=payload)
    assert step_response.status_code == 200
    assert "ISO-10303-21;" in step_response.text
    assert "MANIFOLD_SOLID_BREP('direct_box'" in step_response.text


def test_free_geometry_fallback_runs_build123d_and_exports_stl(monkeypatch):
    main.active_layout = None
    monkeypatch.setattr(
        main,
        "call_llm",
        lambda system_prompt, user_prompt, config_path: (
            '{"reply": "No cone template exists, generated free geometry with build123d.", '
            '"model": [], '
            '"build123d_code": "from build123d import *\\nresult = Cone(bottom_radius=40, top_radius=0, height=80)"}'
        ),
    )

    response = client.post(
        "/api/prompt",
        json={
            "prompt": "Create a cone with base radius 40 mm and height 80 mm",
            "free_geometry": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["result"] == []
    assert "Cone(bottom_radius=40" in data["build123d_code"]
    assert data["layout"] is not None
    assert data["layout"]["free_geometry"] is True
    assert data["layout"]["solid_count"] == 1
    assert data["layout"]["stl_url"] == "/api/model/stl"

    stl_response = client.get("/api/model/stl")
    assert stl_response.status_code == 200
    assert "model/stl" in stl_response.headers.get("content-type", "")
    assert "solid nomo_layout" in stl_response.text
    assert "facet normal" in stl_response.text
    assert "vertex" in stl_response.text


def test_free_geometry_fallback_retries_when_build123d_code_fails(monkeypatch):
    user_prompts = []
    answers = iter(
        [
            (
                '{"reply": "Broken code", "model": [], '
                '"build123d_code": "from build123d import *\\nresult = NonExistentPrimitive(10)"}'
            ),
            (
                '{"reply": "Fixed torus", "model": [], '
                '"build123d_code": "from build123d import *\\nresult = Torus(50, 15)"}'
            ),
        ]
    )

    def mock_call_llm(system_prompt, user_prompt, config_path):
        user_prompts.append(user_prompt)
        return next(answers)

    monkeypatch.setattr(main, "call_llm", mock_call_llm)
    response = client.post(
        "/api/prompt",
        json={
            "prompt": "Create a torus with major radius 50 mm and minor radius 15 mm",
            "free_geometry": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["reply"] == "Fixed torus"
    assert data["layout"]["free_geometry"] is True
    assert len(user_prompts) == 2
    assert "NonExistentPrimitive" in user_prompts[1]
