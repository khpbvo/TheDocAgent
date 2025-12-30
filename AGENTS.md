# Repository Guidelines

## Project Structure & Module Organization

- `agent/`: core runtime and REPL entrypoints (`agent/main.py`, `agent/repl.py`).
- `agent/tools/`: thin wrappers around skills; each tool module is `*_tools.py`.
- `skills/`: document-processing utilities grouped by format (`pdf/`, `docx/`, `xlsx/`).
- `data/`: SQLite session storage (`data/sessions.db` by default).
- `Docs/`: reference docs for the OpenAI Agents SDK.
- `requirements.txt`: Python dependencies for the agent and skills.

## Build, Test, and Development Commands

- Create and activate a venv:
  - `python -m venv .venv`
  - `source .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Run the agent:
  - `python -m agent.main` (new session)
  - `python -m agent.main --session-id my_session` (resume)
  - `python -m agent.main --db-path data/sessions.db` (custom DB path)
- External tools: `pandoc` is required for DOCX text extraction; LibreOffice is required for XLSX formula recalc.

## Coding Style & Naming Conventions

- Python, 4-space indentation, keep modules small and focused.
- Functions and variables use `snake_case`; tool functions should be concise verbs (`extract_pdf_text`).
- No formatter or linter is configured; follow PEP 8 and keep imports grouped.
- Tool wrappers should use `@function_tool`, return strings, and register in `agent/tools/__init__.py` and `agent/config.py`.

## Testing Guidelines

- Tests are minimal and use `unittest`. Example:
  - `python -m unittest skills/pdf/scripts/check_bounding_boxes_test.py`
- Keep tests next to scripts and name files `*_test.py`.
- Tests are not currently run in CI; run relevant tests manually before changing logic.

## Commit & Pull Request Guidelines

- Commit history uses short, imperative summaries (e.g., "Add xlsx skill for comprehensive spreadsheet handling").
- PRs should include: what changed, how to run or test, and any new external dependencies.
- If adding tools, update the skills mapping docs or inline references in `CLAUDE.md`.

## Configuration Notes

- Model settings live in `agent/config.py`.
- The agent expects `OPENAI_API_KEY` in the environment when running.
