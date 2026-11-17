import json
import subprocess
import sys
from pathlib import Path

import pytest

import cli


def write_mock_config(tmp_path, output_file):
    config_path = tmp_path / "config.json"
    config = {
        "provider": "mock",
        "system-prompt": "DUMMY",
        "output-file": str(output_file),
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


def test_load_config_returns_defaults_when_file_is_missing(tmp_path):
    config = cli.load_config(str(tmp_path / "missing.json"))

    assert config["provider"] == "mock"
    assert config["output-file"] == "output/response.text"


def test_load_config_reads_existing_file(tmp_path):
    config_path = write_mock_config(tmp_path, tmp_path / "response.text")

    config = cli.load_config(str(config_path))

    assert config["provider"] == "mock"
    assert config["system-prompt"] == "DUMMY"


def test_save_response_creates_missing_parent_directory(tmp_path):
    output_path = tmp_path / "nested" / "response.text"

    cli.save_response("Saved text", str(output_path))

    assert output_path.read_text(encoding="utf-8") == "Saved text"


def test_main_writes_response_to_output_file(tmp_path, monkeypatch):
    output_path = tmp_path / "response.text"
    config_path = write_mock_config(tmp_path, output_path)
    monkeypatch.setattr(
        sys, "argv", ["cli.py", "Build a box", "--config", str(config_path)]
    )

    cli.main()

    assert "Build a box" in output_path.read_text(encoding="utf-8")


def test_main_asks_for_prompt_when_no_argument_is_given(tmp_path, monkeypatch):
    output_path = tmp_path / "response.text"
    config_path = write_mock_config(tmp_path, output_path)
    monkeypatch.setattr(sys, "argv", ["cli.py", "--config", str(config_path)])
    monkeypatch.setattr("builtins.input", lambda message: "Interactive box")

    cli.main()

    assert "Interactive box" in output_path.read_text(encoding="utf-8")


def test_main_exits_with_error_for_empty_prompt(tmp_path, monkeypatch):
    config_path = write_mock_config(tmp_path, tmp_path / "response.text")
    monkeypatch.setattr(sys, "argv", ["cli.py", "--config", str(config_path)])
    monkeypatch.setattr("builtins.input", lambda message: "   ")

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 1


def test_main_exits_quietly_when_input_is_aborted(tmp_path, monkeypatch):
    config_path = write_mock_config(tmp_path, tmp_path / "response.text")
    monkeypatch.setattr(sys, "argv", ["cli.py", "--config", str(config_path)])

    def abort_input(message):
        raise EOFError

    monkeypatch.setattr("builtins.input", abort_input)

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 0


def test_main_rejects_missing_env_file(tmp_path, monkeypatch):
    config_path = write_mock_config(tmp_path, tmp_path / "response.text")
    missing_env_file = tmp_path / ".env.missing"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli.py",
            "A box",
            "--config",
            str(config_path),
            "--env-file",
            str(missing_env_file),
        ],
    )

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 2


def test_main_shows_provider_error_and_exits(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "config.json"
    config_path.write_text('{"provider": "missing-ai"}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["cli.py", "A box", "--config", str(config_path)])

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 1
    assert "Unknown AI provider 'missing-ai'" in capsys.readouterr().err


def test_main_exits_with_130_when_interrupted_during_call(tmp_path, monkeypatch):
    config_path = write_mock_config(tmp_path, tmp_path / "response.text")
    monkeypatch.setattr(sys, "argv", ["cli.py", "A box", "--config", str(config_path)])

    def interrupted_call(system_prompt, user_prompt, provider):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "call_llm", interrupted_call)

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 130


def test_main_does_not_save_when_output_file_is_empty(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"provider": "mock", "system-prompt": "DUMMY", "output_file": ""}',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["cli.py", "A box", "--config", str(config_path)])

    cli.main()

    assert not (tmp_path / "output").exists()


def test_cli_execution_with_mock(tmp_path):
    # Create temporary mock config
    mock_config = tmp_path / "mock_config.json"
    mock_config.write_text(
        "{\n"
        '  "provider": "mock",\n'
        '  "output-file": "output/response.text",\n'
        '  "system-prompt": "DUMMY",\n'
        '  "providers": { "mock": { "model": "MOCK" } }\n'
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
    assert "Mock LLM Response" in result.stdout
    assert prompt in result.stdout

    # Check output file
    output_file = Path("output/response.text")
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert prompt in content


def test_cli_shows_provider_error_without_traceback(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"provider": "missing-ai", "output-file": "", "providers": {}}',
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "cli.py", "A box", "--config", str(config_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: Unknown AI provider 'missing-ai'" in result.stderr
    assert "Traceback" not in result.stderr
