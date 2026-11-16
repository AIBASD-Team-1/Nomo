import os
import shutil
import signal
import subprocess
import tempfile
import threading
from typing import Any

from .base import LLMProvider

PROMPT_PLACEHOLDER = "{prompt}"
EFFORT_PLACEHOLDER = "{effort}"
DEFAULT_TIMEOUT_SECONDS = 300
# How long to wait for the output pipes to close after the tool was killed
STOP_TIMEOUT_SECONDS = 5

# Tools that are answering a prompt right now, see stop_running_tools
running_processes: set[subprocess.Popen] = set()
running_processes_lock = threading.Lock()
# Windows runs these through cmd.exe, which cuts an argument at a line break and
# treats characters like & and | in it as shell syntax
WINDOWS_SCRIPT_SUFFIXES = (".cmd", ".bat")


class CliProvider(LLMProvider):
    """
    Runs an AI command line tool (Claude Code, Codex, Copilot CLI, ...) once per prompt.

    The system prompt and the user prompt are sent as one text: in place of "{prompt}" in the
    command, or on stdin when the command has no "{prompt}". The tool's stdout is the answer.
    The tool runs in an empty temporary folder, so it does not pick up the project's files
    or settings by accident. That is not a sandbox: a tool that may read files or run
    commands can still reach the rest of the computer, so restrict it in its command.
    A model is passed as --model <model>; an effort through effort_arguments, in which
    "{effort}" is replaced (e.g. ["--effort", "{effort}"]).
    """

    def __init__(
        self,
        command: list[str],
        model: str = "",
        effort: str = "",
        effort_arguments: list[str] | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        if not command:
            raise ValueError("A CLI provider needs a command in config.json.")
        self.command = command
        self.model = model
        self.effort = effort
        self.effort_arguments = effort_arguments or []
        self.timeout = timeout

    def prompt_is_argument(self) -> bool:
        """True when the command has "{prompt}", otherwise the prompt goes to stdin."""
        for part in self.command:
            if PROMPT_PLACEHOLDER in part:
                return True
        return False

    def build_arguments(self, prompt_text: str) -> list[str]:
        """Returns the command line with the prompt, model and effort filled in."""
        arguments = []
        for part in self.command:
            arguments.append(part.replace(PROMPT_PLACEHOLDER, prompt_text))
        if self.model:
            arguments.extend(["--model", self.model])
        if self.effort:
            for part in self.effort_arguments:
                arguments.append(part.replace(EFFORT_PLACEHOLDER, self.effort))
        return arguments

    def call(self, system_prompt: str, user_prompt: str) -> str:
        tool_name = self.command[0]
        # shutil.which also finds npm's .cmd launchers on Windows
        found_executable = shutil.which(tool_name)
        if found_executable is None:
            raise RuntimeError(
                f"'{tool_name}' was not found. Install it and sign in, or put it on PATH."
            )
        # A relative path like ./tools/my-ai is found from Nomo's folder, but the
        # tool starts in an empty temporary folder, where it would not be found
        executable = os.path.abspath(found_executable)

        prompt_text = f"{system_prompt}\n\n{user_prompt}"
        arguments = self.build_arguments(prompt_text)
        arguments[0] = executable

        if self.prompt_is_argument():
            stdin_text = None
        else:
            stdin_text = prompt_text

        if stdin_text is None:
            is_windows_script = executable.lower().endswith(WINDOWS_SCRIPT_SUFFIXES)
            if is_windows_script:
                raise RuntimeError(
                    f"'{tool_name}' is a Windows script ({executable}), which cannot "
                    f"safely receive the prompt as an argument. Remove '{PROMPT_PLACEHOLDER}' "
                    "from its command in config.json so the prompt goes to stdin, "
                    "or point the command at the tool's .exe."
                )
            # Without this the tool would read the terminal (or pipe) Nomo was started from
            stdin_source = subprocess.DEVNULL
        else:
            stdin_source = subprocess.PIPE

        # The folder may still be in use by a process that could not be stopped;
        # leaving it behind is better than hiding the real error
        with tempfile.TemporaryDirectory(
            prefix="nomo-", ignore_cleanup_errors=True
        ) as empty_folder:
            process = subprocess.Popen(
                arguments,
                stdin=stdin_source,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                # a tool may answer in the Windows console encoding instead of UTF-8
                errors="replace",
                cwd=empty_folder,
                **process_group_options(),
            )
            with running_processes_lock:
                running_processes.add(process)
            try:
                outputs = process.communicate(input=stdin_text, timeout=self.timeout)
            except subprocess.TimeoutExpired as error:
                stop_process_tree(process)
                raise RuntimeError(
                    f"'{tool_name}' did not answer within {self.timeout} seconds."
                ) from error
            except BaseException:
                # e.g. Ctrl+C: the tool has its own process group, so it would keep running
                stop_process_tree(process)
                raise
            finally:
                with running_processes_lock:
                    running_processes.discard(process)

        standard_output = outputs[0]
        error_output = outputs[1]
        if process.returncode != 0:
            failure_output = error_output or standard_output
            last_lines = failure_output.strip()[-500:]
            raise RuntimeError(
                f"'{tool_name}' failed (exit code {process.returncode}): {last_lines}"
            )
        return standard_output.strip()


def process_group_options() -> dict[str, Any]:
    """
    On Linux and macOS the tool gets its own process group, so a timeout can stop it
    together with the processes it starts: npm launchers (claude, codex, copilot) run the
    real tool as a child. Windows needs none, taskkill /T follows the parent processes.
    """
    if os.name == "nt":
        return {}
    return {"start_new_session": True}


def kill_process_tree(process: subprocess.Popen) -> None:
    """Kills the tool and every process it started."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            capture_output=True,
        )
        return
    try:
        # start_new_session made the tool's process id its process group id
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def stop_process_tree(process: subprocess.Popen) -> None:
    """Kills the tool and every process it started, then collects the leftover output."""
    kill_process_tree(process)
    try:
        process.communicate(timeout=STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        # a process that left the group still holds the output pipes
        process.kill()


def stop_running_tools() -> None:
    """
    Kills every tool that is still answering a prompt, e.g. when the web server stops.
    Ctrl+C in the terminal does not reach them: they run in their own process group
    and the web app calls them from a worker thread.
    """
    with running_processes_lock:
        processes = list(running_processes)
    for process in processes:
        kill_process_tree(process)
