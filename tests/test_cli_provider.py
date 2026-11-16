import json
import sys
from pathlib import Path

import pytest

from llm.call import get_provider

# Small Python scripts stand in for AI CLIs like `claude` or `codex`.
PRINT_STDIN_SCRIPT = "import sys; print('stdin:' + sys.stdin.read())"
PRINT_ARGUMENT_AND_STDIN_SCRIPT = (
    "import sys; print(sys.argv[1] + '|stdin:' + sys.stdin.read())"
)
PRINT_ARGUMENTS_SCRIPT = "import json, sys; print(json.dumps(sys.argv[1:]))"
PRINT_WORKING_FOLDER_SCRIPT = (
    "import json, os; print(json.dumps({'folder': os.getcwd(), 'files': os.listdir()}))"
)
FAILING_SCRIPT = "import sys; sys.stderr.write('cli broke'); sys.exit(1)"


def create_cli_provider(command, model="", effort="", effort_arguments=None):
    provider_settings = {
        "type": "cli",
        "command": command,
        "model": model,
        "effort": effort,
        "effort-arguments": effort_arguments or [],
    }
    config = {"provider": "fake-cli", "providers": {"fake-cli": provider_settings}}
    return get_provider(config)


def test_cli_provider_sends_system_and_user_prompt_via_stdin():
    provider = create_cli_provider([sys.executable, "-c", PRINT_STDIN_SCRIPT])

    answer = provider.call("Nomo system prompt", "Build a table")

    assert answer.startswith("stdin:")
    assert "Nomo system prompt" in answer
    assert "Build a table" in answer
    assert answer.index("Nomo system prompt") < answer.index("Build a table")


def test_cli_provider_puts_prompt_into_argument_placeholder_instead_of_stdin():
    command = [sys.executable, "-c", PRINT_ARGUMENT_AND_STDIN_SCRIPT, "{prompt}"]
    provider = create_cli_provider(command)

    answer = provider.call("Nomo system prompt", "Build a table")

    argument_text, stdin_text = answer.split("|stdin:")
    assert "Nomo system prompt" in argument_text
    assert "Build a table" in argument_text
    assert stdin_text.strip() == ""


def test_cli_provider_passes_model_with_model_flag():
    command = [sys.executable, "-c", PRINT_ARGUMENTS_SCRIPT]
    provider = create_cli_provider(command, model="sonnet")

    answer = provider.call("system", "prompt")

    assert json.loads(answer) == ["--model", "sonnet"]


def test_cli_provider_passes_effort_with_configured_effort_arguments():
    command = [sys.executable, "-c", PRINT_ARGUMENTS_SCRIPT]
    effort_arguments = ["-c", "model_reasoning_effort={effort}"]
    provider = create_cli_provider(
        command, effort="high", effort_arguments=effort_arguments
    )

    answer = provider.call("system", "prompt")

    assert json.loads(answer) == ["-c", "model_reasoning_effort=high"]


def test_cli_provider_adds_no_arguments_without_model_and_effort():
    command = [sys.executable, "-c", PRINT_ARGUMENTS_SCRIPT]
    effort_arguments = ["--effort", "{effort}"]
    provider = create_cli_provider(command, effort_arguments=effort_arguments)

    answer = provider.call("system", "prompt")

    assert json.loads(answer) == []


def test_cli_provider_runs_in_empty_temporary_folder():
    # Agentic CLIs must not see or change the project files.
    provider = create_cli_provider([sys.executable, "-c", PRINT_WORKING_FOLDER_SCRIPT])

    answer = provider.call("system", "prompt")

    working_folder = json.loads(answer)
    working_folder_path = Path(working_folder["folder"])
    assert working_folder["files"] == []
    assert working_folder_path != Path.cwd()
    assert not working_folder_path.exists()


def test_cli_provider_raises_error_with_cli_message_when_command_fails():
    provider = create_cli_provider([sys.executable, "-c", FAILING_SCRIPT])

    with pytest.raises(RuntimeError, match="cli broke"):
        provider.call("system", "prompt")


def test_cli_provider_raises_clear_error_when_cli_is_not_installed():
    provider = create_cli_provider(["nomo-cli-that-does-not-exist"])

    with pytest.raises(RuntimeError, match="nomo-cli-that-does-not-exist"):
        provider.call("system", "prompt")
