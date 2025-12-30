# TheDocAgent (Document Analyzer Agent)

Interactive agent for analyzing and modifying **PDF**, **DOCX**, and **XLSX** documents, built on the **OpenAI Agents SDK**.

It runs as a terminal REPL with streaming output, visible tool calls, optional diff-based approvals for edits, and persistent conversation memory stored in SQLite.

## Quickstart

```bash
# 1) Create and activate a virtualenv (Python 3.11+)
python -m venv .venv
source .venv/bin/activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) Provide your API key
export OPENAI_API_KEY="..."

# 4) Run
python -m agent.main
```

## Requirements

- Python **3.11+** (see `pyproject.toml`)
- An OpenAI API key in `OPENAI_API_KEY`

Optional (only needed for specific features):

- **Node.js** (for the optional MCP filesystem server; requires `npx`)
- **LibreOffice** (for Excel formula recalculation via `recalculate_formulas`)

## Install

### Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Key packages include:

- `openai-agents` (agent runtime + sessions)
- `pdfplumber`, `pypdf` (PDF extract/merge/split/forms)
- `python-docx`, `defusedxml`, `pypandoc_binary` (DOCX parsing + safe XML + pandoc conversion)
- `openpyxl`, `pandas` (XLSX read/write/analysis)
- `rich`, `textual` (REPL UI; falls back to plain terminal if Textual is unavailable)

### Environment variables

- `OPENAI_API_KEY` (required): API key for the OpenAI Agents SDK.
- `DOCUMENT_WORKSPACE_ROOT` (optional): Root directory for approval-mode editors (usually set automatically).
- `DOCUMENT_EDIT_AUTO_APPROVE=1` (optional): Auto-approve document edits when approval mode is enabled.

## Running

The main entry point is:

```bash
python -m agent.main
```

### Common CLI examples

```bash
# Start a new session (auto-generates a session id)
python -m agent.main

# Resume an existing session
python -m agent.main --session-id my_session

# Store sessions in a custom SQLite DB
python -m agent.main --db-path data/sessions.db

# Choose a model
python -m agent.main --model gpt-5.1

# Disable tool call notifications in the UI
python -m agent.main --no-tool-calls

# Use a simpler non-streaming REPL (debugging)
python -m agent.main --simple
```

### Model selection

`agent/main.py` treats these as “reasoning model” configs:

- `o1`, `o3`, `gpt-5.1`, `gpt-5`

Other model names use the standard agent config.

### Session persistence

- By default, sessions are stored at `data/sessions.db`.
- Each run creates or resumes a session via `SQLiteSession`.
- Use `--session-id` to continue a previous conversation.

## REPL commands

Inside the REPL:

- `help` — show help
- `clear` — clear conversation history (start fresh)
- `history` — show conversation summary
- `exit` / `quit` — exit

## Capabilities

The agent exposes document tools via `@function_tool` wrappers in `agent/tools/`.

There are two “write modes”:

1) **Approval mode (default)**: certain DOCX/XLSX edits show a diff and require Y/N approval.
2) **Direct write mode**: tools write immediately (no diff/approval).

You can disable approval mode entirely with:

```bash
python -m agent.main --no-approval
```

Or keep approval mode but auto-approve edits:

```bash
python -m agent.main --auto-approve
```

### PDF (.pdf)

Tools (7):

- `extract_pdf_text(file_path, page_numbers_json=None)` — extract text for all or selected pages
- `extract_pdf_tables(file_path, page_number=None)` — extract tables as JSON
- `get_pdf_metadata(file_path)` — title/author/page count/etc.
- `get_pdf_form_fields(file_path)` — list fillable form fields
- `fill_pdf_form(file_path, field_values_json, output_path)` — fill form fields and save a new PDF
- `merge_pdfs(input_files_json, output_path)` — merge PDFs into one
- `split_pdf(file_path, output_dir)` — split a PDF into per-page PDFs

Example prompts you can type in the REPL:

- “Extract the text from `/path/to/document.pdf`”
- “Extract tables from page 3 of `/path/to/report.pdf`”
- “List form fields in `/path/to/form.pdf`, then fill them with name=John and date=2025-01-01”

### Word (.docx)

Read tools:

- `extract_docx_text(file_path)` — convert DOCX to markdown (via pandoc)
- `extract_docx_with_changes(file_path)` — extract text with tracked changes visible
- `get_docx_comments(file_path)` — extract comments (author/date/text) as JSON
- `get_docx_structure(file_path)` — heading outline

Write tools (direct mode):

- `add_docx_comment(file_path, search_text, comment_text, output_path)` — attach a comment to matched text
- `create_docx(content, output_path, title=None)` — create a new DOCX
- `apply_tracked_changes(file_path, output_path)` — apply tracked changes and save

Write tools (approval mode):

- `replace_docx_text(file_path, old_text, new_text, description="")`
- `insert_docx_text(file_path, new_text, paragraph_index=-1, description="")`
- `delete_docx_text(file_path, text_to_delete, description="")`

Notes:

- DOCX text extraction uses `pypandoc`. This repo includes `pypandoc_binary`, which typically provides the pandoc binary without a separate system install.
- If pandoc conversion fails on your machine, installing pandoc system-wide can help.

### Excel (.xlsx / .xlsm)

Read tools:

- `get_sheet_names(file_path)` — list sheets
- `read_sheet(file_path, sheet_name=None, max_rows=100)` — read rows as JSON
- `get_formulas(file_path, sheet_name=None)` — list formula cells
- `analyze_data(file_path, sheet_name=None, analysis_type="summary")` — pandas-based stats/info/head/shape

Write tools (direct mode):

- `write_cell(file_path, sheet_name, cell, value, output_path=None)`
- `add_formula(file_path, sheet_name, cell, formula, output_path=None)`

Write tools (approval mode):

- `update_xlsx_cell(file_path, cell, new_value, sheet="", description="")`
- `add_xlsx_formula(file_path, cell, formula, sheet="", description="")`
- `update_xlsx_range(file_path, range_a1, values_json, sheet="", description="")`

Formula recalculation:

- `recalculate_formulas(file_path, timeout=30)` — recalculates formulas via `skills/xlsx/recalc.py`

This requires **LibreOffice**.

macOS install example:

```bash
brew install --cask libreoffice
```

## Filesystem integration (MCP)

By default the app may enable a local filesystem MCP server (if `npx` is available).
This allows the agent to browse and read/write files within a configured root.

Relevant flags:

- `--no-mcp-filesystem` — disable MCP filesystem integration
- `--mcp-filesystem-root /path` — set the MCP filesystem root (defaults to repository root)

If you see a message like “MCP filesystem server disabled: 'npx' not found”, install Node.js so `npx` is available.

## Project layout

```text
TheDocAgent/
  agent/
    main.py              # CLI entrypoint (python -m agent.main)
    config.py            # Agent model settings + tool registration
    repl.py              # Streaming REPL UI (Textual if available)
    editors/             # Approval-mode diff editors for docx/xlsx
    tools/               # Tool wrappers (pdf/docx/xlsx + approval tools)
  skills/                # Underlying document processing utilities
  data/                  # SQLite session DB (default: data/sessions.db)
  Docs/                  # OpenAI Agents SDK reference docs
```

## Development

### Add a new tool

Tool wrappers live in `agent/tools/` and are registered through `agent/tools/__init__.py` and used in `agent/config.py`.

Guidelines:

- Decorate with `@function_tool`
- Return strings (return error strings instead of raising where practical)
- Prefer wrapping an existing utility from `skills/` rather than rewriting logic

### Tests

Tests are minimal and live next to scripts. Example:

```bash
python -m unittest skills/pdf/scripts/check_bounding_boxes_test.py
```

## Troubleshooting

- **`OPENAI_API_KEY` missing**: set `export OPENAI_API_KEY="..."`.
- **DOCX extraction fails**: `pypandoc_binary` is included, but if conversion still fails, try installing pandoc system-wide.
- **Excel recalculation errors**: install LibreOffice and retry `recalculate_formulas`.
- **MCP filesystem disabled**: install Node.js so `npx` is on PATH, or run with `--no-mcp-filesystem`.
