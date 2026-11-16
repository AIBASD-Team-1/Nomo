import json
import os
import sys
import time
from pathlib import Path

import pytest

from llm import call as llm_call
from llm.cli_provider import CliProvider

# A stand-in for an AI CLI: answers with what it received on stdin and as arguments
ECHO_SCRIPT = (
    "import json, sys; "
    "print(json.dumps({'stdin': sys.stdin.read(), 'arguments': sys.argv[1:]}))"
)


def run_echo_provider(command_arguments: list[str], model: str = "") -> dict:
    command = [sys.executable, "-c", ECHO_SCRIPT, *command_arguments]
    provider = CliProvider(command=command, model=model)
    answer = provider.call("System rules", "Build a box")
    return json.loads(answer)


def test_prompt_goes_to_stdin_without_placeholder():
    received = run_echo_provider([])

    assert received["stdin"] == "System rules\n\nBuild a box"
    assert received["arguments"] == []


def test_prompt_replaces_placeholder_argument():
    received = run_echo_provider(["-p={prompt}"])

    assert received["stdin"] == ""
    assert received["arguments"] == ["-p=System rules\n\nBuild a box"]


def test_model_is_passed_as_flag():
    received = run_echo_provider([], model="some-model")

    assert received["arguments"] == ["--model", "some-model"]


def test_failing_tool_raises_with_its_error_output():
    command = [sys.executable, "-c", "import sys; sys.exit('not signed in')"]
    provider = CliProvider(command=command)

    with pytest.raises(RuntimeError, match="not signed in"):
        provider.call("system", "prompt")


def test_missing_tool_raises():
    provider = CliProvider(command=["nomo-tool-that-does-not-exist"])

    with pytest.raises(RuntimeError, match="was not found"):
        provider.call("system", "prompt")


def test_prompt_argument_is_refused_for_windows_script(monkeypatch):
    def find_windows_script(tool_name):
        return "C:\\npm\\copilot.cmd"

    monkeypatch.setattr("llm.cli_provider.shutil.which", find_windows_script)
    provider = CliProvider(command=["copilot", "-p", "{prompt}"])

    with pytest.raises(RuntimeError, match="Windows script"):
        provider.call("system", "prompt")


def test_output_that_is_not_utf8_does_not_crash():
    write_cp1252_bytes = "import sys; sys.stdout.buffer.write(b'gr\\xfc\\xdf dich')"
    provider = CliProvider(command=[sys.executable, "-c", write_cp1252_bytes])

    answer = provider.call("system", "prompt")

    assert answer.endswith("dich")


CONFIG = {
    "provider": "mock",
    "providers": {
        "mock": {"model": "MOCK"},
        "codex": {"type": "cli", "command": ["codex", "exec", "-"]},
    },
}


def test_get_provider_builds_cli_provider_from_config():
    config = dict(CONFIG, provider="codex")

    provider = llm_call.get_provider(config)

    assert isinstance(provider, CliProvider)
    assert provider.command == ["codex", "exec", "-"]
    assert provider.model == ""


def test_provider_and_model_from_environment_override_config(monkeypatch):
    monkeypatch.setenv("NOMO_PROVIDER", "codex")
    monkeypatch.setenv("NOMO_CODEX_MODEL", "environment-model")

    provider = llm_call.get_provider(CONFIG)

    assert isinstance(provider, CliProvider)
    assert provider.model == "environment-model"


def test_unknown_provider_raises_instead_of_using_the_mock(monkeypatch):
    monkeypatch.setenv("NOMO_PROVIDER", "claude")

    with pytest.raises(ValueError, match="Unknown AI provider 'claude'"):
        llm_call.get_provider(CONFIG)


def test_empty_provider_in_environment_uses_config(monkeypatch):
    monkeypatch.setenv("NOMO_PROVIDER", "")
    config = dict(CONFIG, provider="codex")

    provider = llm_call.get_provider(config)

    assert isinstance(provider, CliProvider)


def test_missing_env_file_raises(tmp_path):
    config_path = tmp_path / "config.json"
    missing_env_file = tmp_path / ".env.codx"

    with pytest.raises(FileNotFoundError, match=".env.codx"):
        llm_call.load_environment(str(config_path), str(missing_env_file))


def test_env_file_wins_over_personal_env_which_still_supplies_keys(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("NOMO_TEST_KEY", raising=False)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(CONFIG), encoding="utf-8")
    (tmp_path / ".env").write_text(
        "NOMO_PROVIDER=mock\nNOMO_TEST_KEY=key-from-personal-env\n", encoding="utf-8"
    )
    preset_file = tmp_path / ".env.codex"
    preset_file.write_text("NOMO_PROVIDER=codex\n", encoding="utf-8")

    llm_call.load_environment(str(config_path), str(preset_file))
    provider = llm_call.get_provider(CONFIG)

    assert isinstance(provider, CliProvider)
    assert os.environ["NOMO_TEST_KEY"] == "key-from-personal-env"
    monkeypatch.delenv("NOMO_TEST_KEY")


def test_model_for_one_provider_does_not_leak_into_preset_provider(
    tmp_path, monkeypatch
):
    config = {
        "provider": "mock",
        "providers": {
            "claude-code": {"type": "cli", "command": ["claude", "-p"]},
            "codex": {
                "type": "cli",
                "command": ["codex", "exec", "-"],
                "model": "codex-default",
                "effort": "low",
            },
        },
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    (tmp_path / ".env").write_text(
        "NOMO_PROVIDER=claude-code\n"
        "NOMO_CLAUDE_CODE_MODEL=opus\n"
        "NOMO_CLAUDE_CODE_EFFORT=max\n",
        encoding="utf-8",
    )
    preset_file = tmp_path / ".env.codex"
    preset_file.write_text("NOMO_PROVIDER=codex\n", encoding="utf-8")

    llm_call.load_environment(str(config_path), str(preset_file))
    provider = llm_call.get_provider(config)

    assert provider.command == ["codex", "exec", "-"]
    assert provider.model == "codex-default"
    assert provider.effort == "low"


def test_provider_variable_name_uses_capitals_and_underscores():
    model_variable = llm_call.provider_variable_name("claude-code", "model")
    effort_variable = llm_call.provider_variable_name("codex", "effort")

    assert model_variable == "NOMO_CLAUDE_CODE_MODEL"
    assert effort_variable == "NOMO_CODEX_EFFORT"


def test_effort_is_passed_through_effort_arguments():
    command = [sys.executable, "-c", ECHO_SCRIPT]
    provider = CliProvider(
        command=command,
        effort="low",
        effort_arguments=["-c", "model_reasoning_effort={effort}"],
    )

    received = json.loads(provider.call("system", "prompt"))

    assert received["arguments"] == ["-c", "model_reasoning_effort=low"]


def test_effort_comes_from_config_and_environment_overrides_it(monkeypatch):
    config = {
        "provider": "claude-code",
        "providers": {
            "claude-code": {
                "type": "cli",
                "command": ["claude", "-p"],
                "model": "sonnet",
                "effort": "low",
                "effort-arguments": ["--effort", "{effort}"],
            }
        },
    }

    provider_with_defaults = llm_call.get_provider(config)
    assert provider_with_defaults.model == "sonnet"
    assert provider_with_defaults.effort == "low"
    assert provider_with_defaults.effort_arguments == ["--effort", "{effort}"]

    monkeypatch.setenv("NOMO_CLAUDE_CODE_EFFORT", "high")
    provider_with_override = llm_call.get_provider(config)
    assert provider_with_override.effort == "high"


def test_codex_in_config_has_no_tools_that_reach_the_computer():
    """The web app passes untrusted prompts to the AI, so codex must not run commands."""
    config_path = Path(__file__).resolve().parent.parent / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    codex_command = config["providers"]["codex"]["command"]
    disabled_features = []
    for index, part in enumerate(codex_command):
        if part == "--disable":
            disabled_features.append(codex_command[index + 1])

    for feature in ("shell_tool", "unified_exec", "view_image", "browser_use"):
        assert feature in disabled_features
    assert "--ignore-user-config" in codex_command


# A stand-in for an npm launcher: starts the real tool as a child, which writes a
# marker file if it is still running after two seconds, then both hang
LAUNCHER_SCRIPT = (
    "import subprocess, sys, time; "
    "child_code = 'import sys, time; time.sleep(2); open(sys.argv[1], \"w\").close()'; "
    "subprocess.Popen([sys.executable, '-c', child_code, sys.argv[1]]); "
    "time.sleep(30)"
)


@pytest.mark.skipif(os.name == "nt", reason="uses POSIX process groups")
def test_timeout_also_stops_the_processes_the_tool_started(tmp_path):
    marker_file = tmp_path / "child-still-running"
    command = [sys.executable, "-c", LAUNCHER_SCRIPT, str(marker_file)]
    provider = CliProvider(command=command, timeout=0.5)

    with pytest.raises(RuntimeError, match="did not answer within"):
        provider.call("system", "prompt")

    time.sleep(2.5)
    assert not marker_file.exists()


@pytest.mark.skipif(os.name == "nt", reason="runs a script through its #! line")
def test_relative_command_path_still_works_in_the_empty_folder(tmp_path, monkeypatch):
    tools_folder = tmp_path / "tools"
    tools_folder.mkdir()
    fake_tool = tools_folder / "fake-ai"
    fake_tool.write_text(f"#!{sys.executable}\nprint('answer')\n", encoding="utf-8")
    fake_tool.chmod(0o755)
    monkeypatch.chdir(tmp_path)
    provider = CliProvider(command=["./tools/fake-ai"])

    answer = provider.call("system", "prompt")

    assert answer == "answer"


def test_edited_personal_env_counts_without_restart(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    personal_env_file = tmp_path / ".env"
    personal_env_file.write_text(
        "NOMO_PROVIDER=mock\nNOMO_TEST_REMOVED=old\n", encoding="utf-8"
    )
    llm_call.load_environment(str(config_path))
    assert os.environ["NOMO_PROVIDER"] == "mock"

    personal_env_file.write_text("NOMO_PROVIDER=codex\n", encoding="utf-8")
    llm_call.load_environment(str(config_path))

    assert os.environ["NOMO_PROVIDER"] == "codex"
    assert "NOMO_TEST_REMOVED" not in os.environ


def test_shell_variable_wins_over_env_files_on_every_load(tmp_path, monkeypatch):
    monkeypatch.setenv("NOMO_PROVIDER", "copilot")
    config_path = tmp_path / "config.json"
    (tmp_path / ".env").write_text("NOMO_PROVIDER=mock\n", encoding="utf-8")

    llm_call.load_environment(str(config_path))
    llm_call.load_environment(str(config_path))

    assert os.environ["NOMO_PROVIDER"] == "copilot"
