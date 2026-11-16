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
- `llm/` — providers behind `LLMProvider.call(system_prompt, user_prompt) -> str`, picked in
  `llm/call.py:get_provider`: entries with `"type": "cli"` → `cli_provider.py` (runs an AI CLI
  like `claude -p` / `codex exec` / `copilot -p` in an empty temp dir, prompt on
  stdin or in place of `{prompt}`, `--model`, `effort-arguments`); `openrouter` →
  `openrouter.py` (raw `urllib`, no SDK; the only API); `mock` → mock; any other name raises.
- `static/` — plain HTML/CSS/JS, no build step. `app.js` posts to `/api/prompt`.
- `docs/` — spec, proposal, stories, presentation, wireframes. Not shipped in Docker.

## Config (`config.json`)

- `provider` selects the active provider; `providers.<name>` holds `model`, `effort`, and
  `type: cli` + `command` + `effort-arguments` (CLIs) or `api_key` + `base-url` (OpenRouter).
  `NOMO_PROVIDER` and the per-provider `NOMO_<PROVIDER>_MODEL` / `NOMO_<PROVIDER>_EFFORT`
  (e.g. `NOMO_CLAUDE_CODE_MODEL`, see `llm/call.py:provider_variable_name`) in env/`.env`
  override them. They name the provider so a preset switch never leaks another AI's model.
- Keys accept both `kebab-case` and `snake_case` (`system-prompt` / `system_prompt`) — keep both
  lookups when touching config reads.
- `api_key` is an **env var name** (e.g. `OPENROUTER_API_KEY`), resolved via `os.getenv`.
  Keys live in `.env` next to `config.json` (git-ignored, loaded by `call_llm` via python-dotenv;
  shell variables win). Committed `.env.<provider>` presets only set `NOMO_PROVIDER`; pick one
  with `cli.py --env-file` / `uvicorn --env-file` (it wins over `.env`, `.env` still supplies
  keys). Add a new preset to the `!.env.<name>` list in `.gitignore`. Never commit real keys.
- `OPENROUTER_MODEL` (env/`.env`) is the older name of `NOMO_OPENROUTER_MODEL`.
- `model: "MOCK"` on openrouter returns a canned reply without a network call.
- OpenRouter: free models only.
- AI CLIs (`claude-code`, `codex`, `copilot`) must be installed, on `PATH` and
  signed in; no key.

## API contract

`PromptResponse` serializes `schema_version` as **`schema-version`** (alias, `"1.00"`).
Tests in `tests/test_api.py` pin the response fields and the DOM element ids in `index.html` —
update `EXPECTED_DOM_ELEMENT_IDS` if you rename/remove ids the frontend depends on.

## Tests

- Tests must not hit the network: monkeypatch `main.call_llm`, use a fake CLI (see
  `tests/test_cli_provider.py`), or the mock provider via a temp config.
- Live test against a real provider is opt-in:
  `NOMO_LIVE_PROVIDER=claude-code uv run --locked pytest -m integration`.

## Dependencies

Declare in `pyproject.toml`, lock with `uv lock`, commit `uv.lock`.
