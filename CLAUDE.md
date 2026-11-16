# CLAUDE.md

Nomo is a university project: text prompt → 3D CAD model built only from parametric **templates**
(the AI picks templates + parameters, never writes geometry). See `docs/Spec.md` for the target
design (templates, instances, validation, build123d geometry, STEP export). The AI now
returns a model (list of instances) in `result`; validation and geometry are not implemented yet.

## Commands

Use uv (Python 3.13, `.python-version`). Always pass `--locked`.

```sh
uv sync --locked                                   # install
uv run --locked uvicorn main:app --reload          # web app at http://127.0.0.1:8000
uv run --locked python cli.py "Describe a design"  # CLI, writes reply to output/response.text
uv run --locked pytest                             # tests
uv run --locked pytest tests/test_api.py::test_prompt_endpoint_returns_valid_json_contract
uv run --locked ruff check . && uv run --locked ruff format --check .
npm ci && npm run format:check                     # Prettier for static/ (npm run format to fix)
```

CI (`.github/workflows/ci.yml`) runs Docker build + smoke test, ruff + Prettier, then pytest.
All must pass. Run ruff format and Prettier before committing.

## Code style

Write readable Python: full descriptive names (no abbreviations like `cfg`, `s`, `e`), no
one-liners that pack several steps (tuple assignments, nested calls, dense comprehensions) —
use one named intermediate variable per step.

## Layout

- `main.py` — FastAPI app. `POST /api/prompt` reads `config.json` per request, calls `call_llm`
  in a thread, returns `PromptResponse`. Serves `static/` and `/` → `static/index.html`.
- `templates/` — one JSON file per template (`box`, `sphere`, `cylinder`); file name = `id`.
  Add a template by adding a file, no code change.
- `catalog.py` — loads `templates/`, builds the system prompt from it, and `parse_reply`
  which turns the AI's JSON answer into `reply` + `model` (→ `result`).
- `cli.py` — argparse CLI over the same `call_llm` (prints the raw answer).
- `llm/` — providers behind `LLMProvider.call(system_prompt, user_prompt) -> str`:
  `cli.py` (`CliProvider`: runs an AI CLI like `claude -p` in an empty temp folder),
  `openrouter.py` (raw `urllib`, sends `reasoning.effort`), `mock.py` (offline, valid
  empty answer). `llm/call.py:get_provider` builds one by its `type`; unknown names/types raise.
- `static/` — plain HTML/CSS/JS, no build step. `app.js` posts to `/api/prompt`.
- `docs/` — spec, proposal, stories, presentation, wireframes. Not shipped in Docker.

## Config (`config.json`)

- `provider` selects the default provider; `providers.<name>` has a `type` (`cli`, `openrouter`,
  `mock`). Every non-mock provider has a default `model` and `effort`.
  `cli`: `command` list with optional `{prompt}` (else prompt on stdin); `--model <model>` is
  appended, then `effort-arguments` with `{effort}` replaced. A new AI CLI is a config entry, never code.
  `openrouter`: `model`, `effort`, `api_key`, `base-url`. OpenRouter is the only API.
- `NOMO_PROVIDER` / `NOMO_MODEL` / `NOMO_EFFORT` (env or `.env`) override provider, model, effort. Committed
  presets `.env.<provider>` contain only `NOMO_PROVIDER` (never keys); pick one with
  `cli.py --env-file` or `uvicorn --env-file`. Each preset needs a `!.env.<name>` in `.gitignore`.
- Keys accept both `kebab-case` and `snake_case` (`system-prompt` / `system_prompt`) — keep both
  lookups when touching config reads.
- `api_key` is an **env var name** (e.g. `OPENROUTER_API_KEY`), resolved via `os.getenv`.
  Keys live in `.env` next to `config.json` (git-ignored, loaded by `call_llm` via python-dotenv;
  shell variables win). Copy `.env.example` to start. Never commit real keys.
- OpenRouter: free models only.

## API contract

`PromptResponse` serializes `schema_version` as **`schema-version`** (alias, `"1.00"`).
Tests in `tests/test_api.py` pin the response fields and the DOM element ids in `index.html` —
update `EXPECTED_DOM_ELEMENT_IDS` if you rename/remove ids the frontend depends on.

## Tests

- Tests must not call an AI: monkeypatch `main.call_llm`, use the mock provider, or a
  `python -c` script as fake CLI (see `tests/test_cli_provider.py`). `tests/conftest.py` clears
  `NOMO_PROVIDER`/`NOMO_MODEL`/`NOMO_EFFORT` so a developer's shell cannot switch tests to a real AI.
- Live test of the configured provider is opt-in: `NOMO_LIVE_TEST=1 uv run --locked pytest -m integration`.

## Dependencies

Declare in `pyproject.toml`, lock with `uv lock`, commit `uv.lock`. `requirements.txt` exists only
for the pip-based Copilot setup in the README — keep it in sync if you add runtime deps.
