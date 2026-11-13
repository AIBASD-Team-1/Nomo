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

## OpenRouter setup

1. Create an account or sign in at [OpenRouter](https://openrouter.ai).
2. Open [API Keys](https://openrouter.ai/settings/keys), create a key and copy it.
3. In `config.json`, set `provider` to `openrouter` and choose an available
   free model. Leave `providers.openrouter.api_key` empty or omit it;
   the provider reads the key from `OPENROUTER_API_KEY`.
4. From the repository root, create your local environment file in PowerShell:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   Replace the example value with your key and save the file. The application
   and CLI load `.env` automatically from the same directory as `config.json`.
   The `.env` file is ignored by Git; do not commit or share it.
5. Start the application:

   ```powershell
   uv run --locked uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

An `OPENROUTER_API_KEY` already set in the terminal takes precedence over the
value in `.env`. Never commit the actual key or include it in issues or
documentation.

## GitHub Copilot

Install the project dependencies and download the SDK runtime:

```powershell
python -m pip install -r requirements.txt
python -m copilot download-runtime
```

The active provider is selected in `config.json`. For Copilot, keep `provider` set to `copilot`; the SDK uses the credentials from your signed-in Copilot CLI and does not need an API key or base URL. Start `copilot` and complete the GitHub sign-in if prompted, then start the web app with `python main.py` or use the CLI with `python cli.py "Describe a design"`.

The configured model is `gpt-4o`; change `providers.copilot.model` in `config.json` if your Copilot plan or organization uses a different available model.
