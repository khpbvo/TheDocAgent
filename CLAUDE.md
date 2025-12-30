# Document Analyzer Agent

## Overview

An interactive Document Analyzer Agent built with the OpenAI Agents SDK. Provides comprehensive analysis and modification capabilities for PDF, DOCX, and XLSX documents through a command-line REPL interface with streaming output, visible tool calls, and conversation memory.

## Architecture

```
TheDocAgent/
├── agent/                    # Main agent package
│   ├── main.py              # Entry point (python -m agent.main)
│   ├── config.py            # Agent configuration (gpt-5.1, reasoning=high)
│   ├── repl.py              # Custom REPL with streaming
│   └── tools/               # Tool wrappers
│       ├── pdf_tools.py     # 7 PDF tools (wraps skills/pdf/)
│       ├── docx_tools.py    # 7 DOCX tools (wraps skills/docx/)
│       └── xlsx_tools.py    # 7 XLSX tools (wraps skills/xlsx/)
│       # + WebSearchTool (hosted on OpenAI) = 22 total tools
├── skills/                   # Existing document processing skills
│   ├── pdf/                 # PDF utilities (pypdf, pdfplumber)
│   ├── docx/                # DOCX utilities (Document class, pandoc)
│   └── xlsx/                # XLSX utilities (openpyxl, recalc.py)
├── data/                     # Session storage (SQLite)
└── Docs/                     # OpenAI Agents SDK documentation
```

## Running the Agent

```bash
# Start new session
python -m agent.main

# Resume existing session
python -m agent.main --session-id my_session

# Custom database path
python -m agent.main --db-path /path/to/sessions.db

# Disable tool call visibility
python -m agent.main --no-tool-calls
```

## Tool Capabilities

### PDF Tools (7 total)
| Tool | Type | Description |
|------|------|-------------|
| `extract_pdf_text` | Read | Extract text from PDF pages |
| `extract_pdf_tables` | Read | Extract tables as JSON |
| `get_pdf_metadata` | Read | Get title, author, page count |
| `get_pdf_form_fields` | Read | List fillable form fields |
| `fill_pdf_form` | Write | Fill form fields with values |
| `merge_pdfs` | Write | Combine multiple PDFs |
| `split_pdf` | Write | Split PDF into pages |

### DOCX Tools (7 total)
| Tool | Type | Description |
|------|------|-------------|
| `extract_docx_text` | Read | Extract plain text via pandoc |
| `extract_docx_with_changes` | Read | Text with tracked changes visible |
| `get_docx_comments` | Read | Extract comments with authors |
| `get_docx_structure` | Read | Get heading outline |
| `add_docx_comment` | Write | Add comment to document |
| `create_docx` | Write | Create new Word document |
| `apply_tracked_changes` | Write | Apply redline edits |

### XLSX Tools (7 total)
| Tool | Type | Description |
|------|------|-------------|
| `get_sheet_names` | Read | List all sheets |
| `read_sheet` | Read | Read sheet data |
| `get_formulas` | Read | Extract formulas |
| `analyze_data` | Read | Pandas statistical analysis |
| `write_cell` | Write | Write value to cell |
| `add_formula` | Write | Add Excel formula |
| `recalculate_formulas` | Write | Recalc via LibreOffice |

### Hosted Tools (OpenAI)
| Tool | Type | Description |
|------|------|-------------|
| `WebSearchTool` | Read | Search the internet for current info, pricing, regulations |

## Skills → Tools Mapping

The agent tools are thin wrappers around existing skill scripts:

```python
# skills/pdf/scripts/fill_fillable_fields.py → @function_tool fill_pdf_form()
# skills/docx/scripts/document.py (Document) → @function_tool add_docx_comment()
# skills/xlsx/recalc.py (recalc)             → @function_tool recalculate_formulas()
```

## Development Guidelines

### Adding New Tools

1. Create wrapper function with `@function_tool` decorator
2. Import from existing skill scripts when available
3. Include comprehensive docstring with Args and Returns
4. Return strings (errors should be returned, not raised)
5. Register in `agent/tools/__init__.py` and `agent/config.py`

```python
from agents import function_tool

@function_tool
def my_new_tool(file_path: str, optional_param: int = 10) -> str:
    """Brief description for the LLM.

    Args:
        file_path: Path to the document.
        optional_param: Optional parameter description.

    Returns:
        Result description.
    """
    try:
        # Import and call existing skill
        from skills.module import utility
        result = utility(file_path)
        return f"Success: {result}"
    except Exception as e:
        return f"Error: {str(e)}"
```

### REPL Features

The custom REPL (`agent/repl.py`) provides:
- **Streaming text**: Token-by-token output via `ResponseTextDeltaEvent`
- **Tool visibility**: Shows tool calls with timestamps
- **Reasoning highlights**: Detects and colors "thinking" text
- **Commands**: `help`, `clear`, `history`, `exit`

### Session Persistence

Sessions stored in SQLite (`data/sessions.db`):
- Auto-generated session IDs with timestamps
- Resume with `--session-id`
- Automatic conversation history management

## Dependencies

```
openai-agents>=0.2.0    # Agent framework
pypdf>=4.0.0            # PDF reading/writing
pdfplumber>=0.10.0      # PDF text/table extraction
openpyxl>=3.1.0         # Excel files
pandas>=2.0.0           # Data analysis
defusedxml>=0.7.0       # Secure XML parsing
```

**External tools:**
- `pandoc` - DOCX text extraction
- `LibreOffice` - Excel formula recalculation (optional)

## Key Files Reference

| File | Purpose |
|------|---------|
| `Docs/streaming.md` | Streaming event patterns |
| `Docs/tools-2.md` | @function_tool usage |
| `Docs/running_agents.md` | SQLiteSession, Runner |
| `skills/pdf/SKILL.md` | PDF processing patterns |
| `skills/docx/SKILL.md` | DOCX processing patterns |
| `skills/xlsx/SKILL.md` | XLSX processing patterns |

## Model Configuration

The agent uses:
- **Model**: gpt-5.1
- **Reasoning**: high effort
- **Verbosity**: medium

Configured in `agent/config.py` via `ModelSettings`.
