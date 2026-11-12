# Nomo
A Project as part of a University Course

FastAPI backend with a static HTML, CSS and JavaScript web interface.

## Requirements

- Python 3.13 (the shared development and CI version, recorded in `.python-version`).
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for dependency
  management (validated with uv 0.13.7).

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

For a runtime-only environment (for example, the later Docker image):

```powershell
uv sync --locked --no-dev
```

## Start the application

```powershell
uv run --locked uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Open <http://127.0.0.1:8000>. Static files are served directly; there is no
frontend compilation step.

## Tests and Python quality checks

```powershell
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Ruff and its project-level rules are included as preparation for the
static-analysis CI job. Existing Python lint and formatting issues will be
addressed with the CI workflow, along with frontend quality checks. These
quality commands do not yet pass on the current source files.

## Update dependencies

```powershell
uv lock --upgrade
uv sync --locked
uv run --locked pytest
```

Review and commit the resulting lockfile changes. Normal installation uses
`--locked` so an outdated lockfile causes an error rather than an implicit update.
