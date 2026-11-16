import json
import subprocess
import sys
from pathlib import Path


def test_cli_execution_with_mock(tmp_path):
    # Create temporary mock config
    mock_config = tmp_path / "mock_config.json"
    mock_config.write_text(
        "{\n"
        '  "provider": "mock",\n'
        '  "output-file": "output/response.text",\n'
        '  "system-prompt": "DUMMY",\n'
        '  "providers": { "mock": { "type": "mock" } }\n'
        "}\n",
        encoding="utf-8",
    )

    prompt = "Test table 200 x 100 cm"
    result = subprocess.run(
        [sys.executable, "cli.py", prompt, "--config", str(mock_config)],
        capture_output=True,
        text=True,
        check=True,
    )

    # Check CLI output
    assert "Calling LLM..." in result.stdout
    assert "--- LLM Response ---" in result.stdout
    assert prompt in result.stdout

    # Check output file
    output_file = Path("output/response.text")
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert prompt in content


def test_cli_env_file_selects_provider(tmp_path):
    config_path = tmp_path / "config.json"
    config = {
        "provider": "mock",
        "output-file": str(tmp_path / "response.text"),
        "system-prompt": "DUMMY",
        "providers": {
            "mock": {"type": "mock"},
            "marker": {
                "type": "cli",
                "command": [sys.executable, "-c", "print('PROVIDER_FROM_ENV_FILE')"],
            },
        },
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")
    env_file_path = tmp_path / ".env.marker"
    env_file_path.write_text("NOMO_PROVIDER=marker\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "cli.py",
            "Build a table",
            "--config",
            str(config_path),
            "--env-file",
            str(env_file_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "PROVIDER_FROM_ENV_FILE" in result.stdout
