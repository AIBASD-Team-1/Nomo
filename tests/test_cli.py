import subprocess
from pathlib import Path


def test_cli_execution_with_mock(tmp_path):
    # Create temporary mock config
    mock_config = tmp_path / "mock_config.json"
    mock_config.write_text(
        '{\n'
        '  "provider": "mock",\n'
        '  "output-file": "output/response.text",\n'
        '  "system-prompt": "DUMMY",\n'
        '  "providers": { "mock": { "model": "MOCK" } }\n'
        '}\n',
        encoding="utf-8"
    )

    prompt = "Test table 200 x 100 cm"
    result = subprocess.run(
        ["python3", "cli.py", prompt, "--config", str(mock_config)],
        capture_output=True,
        text=True,
        check=True
    )

    # Check CLI output
    assert "Calling LLM..." in result.stdout
    assert "--- LLM Response ---" in result.stdout
    assert "Mock LLM Response" in result.stdout
    assert prompt in result.stdout

    # Check output file
    output_file = Path("output/response.text")
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert prompt in content
