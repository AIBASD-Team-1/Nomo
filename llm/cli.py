import shutil
import subprocess
import tempfile

from .base import LLMProvider

PROMPT_PLACEHOLDER = "{prompt}"
EFFORT_PLACEHOLDER = "{effort}"
TIMEOUT_SECONDS = 300


class CliProvider(LLMProvider):
    """
    Runs an AI command line tool (e.g. `claude -p`) and returns what it prints.

    The prompt goes to stdin, or into the argument "{prompt}" if the command has one.
    The model is appended as `--model <model>`, the effort as the CLI's own
    effort arguments with "{effort}" replaced (e.g. `--effort {effort}`).
    """

    def __init__(
        self,
        command: list[str],
        model: str = "",
        effort: str = "",
        effort_arguments: list[str] | None = None,
    ):
        self.command = command
        self.model = model
        self.effort = effort
        self.effort_arguments = effort_arguments or []

    def call(self, system_prompt: str, user_prompt: str) -> str:
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        prompt_in_argument = PROMPT_PLACEHOLDER in self.command

        arguments = []
        for argument in self.command:
            arguments.append(argument.replace(PROMPT_PLACEHOLDER, full_prompt))
        if self.model:
            arguments.extend(["--model", self.model])
        if self.effort:
            for argument in self.effort_arguments:
                arguments.append(argument.replace(EFFORT_PLACEHOLDER, self.effort))

        # which() also finds `claude.cmd` on Windows, which subprocess alone does not
        executable = shutil.which(arguments[0])
        if executable is None:
            raise RuntimeError(
                f"AI command '{arguments[0]}' was not found. Is it installed and on PATH?"
            )
        arguments[0] = executable

        # Empty stdin when the prompt is an argument; an inherited terminal would block the CLI
        if prompt_in_argument:
            stdin_text = ""
        else:
            stdin_text = full_prompt

        # An empty folder, so agentic CLIs can neither read nor change the project
        with tempfile.TemporaryDirectory() as empty_folder:
            try:
                result = subprocess.run(
                    arguments,
                    input=stdin_text,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    cwd=empty_folder,
                    timeout=TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired as error:
                raise RuntimeError(
                    f"AI command '{self.command[0]}' did not answer within "
                    f"{TIMEOUT_SECONDS} seconds."
                ) from error

        if result.returncode != 0:
            raise RuntimeError(
                f"AI command '{self.command[0]}' failed "
                f"(exit code {result.returncode}): {result.stderr.strip()}"
            )
        return result.stdout
