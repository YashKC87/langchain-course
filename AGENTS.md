# AGENTS.md

## Cursor Cloud specific instructions

This is a small `uv`-managed Python 3.13 project ("langchain-course"). It is a terminal/CLI learning scaffold, not a web or GUI app.

### Environment
- Dependencies and the Python 3.13 toolchain are managed by [`uv`](https://docs.astral.sh/uv/). The startup update script runs `uv sync` to keep `.venv` current.
- `uv` is installed at `~/.local/bin`, which is added to `PATH` via `~/.bashrc` for interactive shells. In non-interactive contexts, invoke it as `~/.local/bin/uv` if it is not found on `PATH`.

### Run / lint / test
- Run the app: `uv run python main.py` (prints a greeting and the value of `OPENAI_API_KEY`, which is `None` when unset).
- Format check: `uv run black --check .`
- Import-order check: `uv run isort --check-only .`
- There is currently no test suite in this repo.

### Notes
- `main.py` reads `OPENAI_API_KEY` via `python-dotenv` (`load_dotenv()`), so a local `.env` file or a `OPENAI_API_KEY` environment variable is required for any actual OpenAI/langchain model calls. Without it the script still runs but prints `None`. `langchain-ollama` usage additionally requires a reachable Ollama server.
