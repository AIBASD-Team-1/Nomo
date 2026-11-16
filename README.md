# Nomo
A Project as part of a University Course

FastAPI backend with a static HTML, CSS and JavaScript web interface.

## Requirements

- Python 3.13 (the shared development and CI version, recorded in `.python-version`).
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for dependency
  management (validated with uv 0.13.7).
- Node.js 24 (recorded in `.node-version`) and npm for frontend formatting checks.
- Docker for building and running the application image.

Run all commands from the repository root. No API keys or external services are
needed for the current application and tests.

## Install dependencies

```powershell
uv sync --locked
```

This creates `.venv` and installs runtime and development dependencies from
`uv.lock`. `pyproject.toml` declares the direct dependencies; `uv.lock` records
the exact resolved versions. Commit both files when changing dependencies.

If an existing `.venv` uses a different Python version, uv may recreate it.
Keep any unrelated tools in a separate environment.

For a runtime-only environment:

```powershell
uv sync --locked --no-dev
```

## Start the application

```powershell
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Open <http://127.0.0.1:8000>. Static files are served directly; there is no
frontend compilation step.

## Tests and quality checks

Run code coverage and create a HTML report.

```powershell
uv run --locked tools/coverage.py
```

Run automatic tests.

```powershell
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Install the frontend quality tools and check HTML, CSS and JavaScript formatting:

```powershell
npm ci
npm run format:check
```

To apply formatting locally:

```powershell
uv run --locked ruff format .
npm run format
```

`package-lock.json` pins the frontend tool dependencies. Commit it together with
`package.json` when updating these tools. Node.js is only needed for quality
checks; it is not part of the application runtime.

## Docker

```powershell
docker build --tag nomo:local .
docker run --rm --publish 127.0.0.1:8000:8000 nomo:local
```

Open <http://127.0.0.1:8000>. The image installs only locked runtime dependencies,
includes the static files and runs Uvicorn without development reload as a
non-root user. The Docker build context excludes local environments, secrets,
tests and documentation.

## Continuous integration

GitHub Actions runs `.github/workflows/ci.yml` automatically on every push and
on pull requests when opened, reopened or updated with new commits. A branch
with an open pull request therefore gets both a push and a pull-request run.

The jobs run sequentially on clean GitHub-hosted Ubuntu runners:

1. **Build** builds the Docker image and verifies that the container serves the
   application and static files.
2. **Static analysis** runs Ruff lint and formatting checks and Prettier
   formatting checks for HTML, CSS and JavaScript.
3. **Tests** runs pytest and uploads `test-results.xml` as an artifact, including
   when tests fail.

Failures are not ignored: a failed job fails the workflow and prevents later
dependent jobs from running. Results are visible in the pull request's checks.
There is no automatic deployment or image publishing.

To block merging unless CI succeeds, a repository administrator must configure
the **Build**, **Static analysis** and **Tests** checks as required status checks
in the target branch's protection rules or ruleset. This is a GitHub setting,
not something the workflow file enables by itself.

GitHub may require a paid plan to enable these protections for a private
repository. Without required status checks, CI results remain visible but
do not technically prevent merging failed changes.

## Update dependencies

```powershell
uv lock --upgrade
uv sync --locked
uv run --locked pytest
```

Review and commit the resulting lockfile changes. Normal installation uses
`--locked` so an outdated lockfile causes an error rather than an implicit update.

## Choose your AI provider

Nomo runs with whichever AI you have: an AI CLI subscription or an OpenRouter key.
You pick it in your own `.env`, so nobody has to edit the shared `config.json`.

| Provider | Type | What you need |
|---|---|---|
| `claude` | CLI | [Claude Code](https://claude.com/claude-code) installed and signed in |
| `codex` | CLI | [Codex CLI](https://github.com/openai/codex) installed and signed in |
| `copilot` | CLI | [GitHub Copilot CLI](https://github.com/github/copilot-cli) installed and signed in |
| `antigravity` | CLI | Antigravity CLI (`agy`) installed and signed in |
| `openrouter` | API | `OPENROUTER_API_KEY` in `.env` (free models only) |
| `mock` | offline | nothing; returns an empty model, for development |

1. Create your local environment file (git-ignored, never commit it):

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

2. Set `NOMO_PROVIDER` to one of the names above, and add `OPENROUTER_API_KEY` if you
   use OpenRouter. Each provider has a default `model` and `effort` in `config.json`;
   `NOMO_MODEL` and `NOMO_EFFORT` override them (e.g. `NOMO_EFFORT=high`).
3. Start the app or the CLI:

   ```powershell
   uv run --locked uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   uv run --locked python cli.py "Describe a design"
   ```

Instead of `NOMO_PROVIDER` in `.env` you can pick a committed preset:

```powershell
uv run --locked python cli.py --env-file .env.claude "Describe a design"
uv run --locked uvicorn main:app --env-file .env.claude --reload
```

Variables set in the terminal win over the preset, and the preset wins over `.env`.

**OpenRouter key:** sign in at [OpenRouter](https://openrouter.ai), open
[API Keys](https://openrouter.ai/settings/keys), create a key and put it into
`.env` as `OPENROUTER_API_KEY`.

### Add another AI CLI

No code change needed, only a new entry under `providers` in `config.json`
(plus a one-line `.env.<name>` preset and a `!.env.<name>` line in `.gitignore`
if you want one):

```json
"mycli": {
  "type": "cli",
  "model": "some-model",
  "effort": "medium",
  "command": ["mycli", "--print", "{prompt}"],
  "effort-arguments": ["--effort", "{effort}"]
}
```

- The prompt goes to stdin, or into the `{prompt}` argument if the command has one.
- `--model <model>` is appended automatically; `effort-arguments` are appended with
  `{effort}` replaced, because every CLI names its effort flag differently.
- The command runs in an empty temporary folder, so it cannot touch the project.

### Live test

Tests never call an AI. To check your provider for real:

```powershell
$env:NOMO_LIVE_TEST = "1"; uv run --locked pytest -m integration
```
