"""Rich + Prompt Toolkit REPL for the Document Analyzer Agent.

This REPL provides a copy-paste friendly terminal interface using Rich for
formatting and Prompt Toolkit for input handling with history support.

Features:
- Streaming text output (token-by-token) with native copy/paste
- Visible tool calls with timestamps
- Reasoning summaries (highlighted thinking)
- Colored diff display for approval prompts
- Input history persisted to file
- Conversation memory via SQLiteSession
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agents import (
    Agent,
    AgentUpdatedStreamEvent,
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    Runner,
    SQLiteSession,
)
from openai.types.responses import ResponseTextDeltaEvent
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown

# Import approval dialog for terminal-based approval
from .approval_dialog import (
    clear_terminal_approval_mode,
    disable_ui_approval,
    enable_ui_approval,
    set_terminal_approval_mode,
)

HELP_TEXT = """
## Available Commands

| Command | Description |
|---------|-------------|
| `help` | Show this help message |
| `clear` | Clear conversation history (start fresh) |
| `history` | Show conversation summary |
| `exit` | Exit the REPL (also: quit, Ctrl+C, Ctrl+D) |

## Document Analysis Examples

- `Extract the text from /path/to/document.pdf`
- `What tables are in /path/to/spreadsheet.xlsx?`
- `Show me the comments in /path/to/contract.docx`
- `Fill the form fields in /path/to/form.pdf with name="John"`
- `Merge these PDFs: file1.pdf, file2.pdf into combined.pdf`

## Tips

- Provide full file paths for best results
- The agent will ask clarifying questions if needed
- Tool calls are shown with timestamps in yellow
- **Copy/paste works normally in this mode!**
"""

# Indicators that the agent is explaining its reasoning
REASONING_INDICATORS = [
    "I'll ",
    "I will ",
    "Let me ",
    "First, ",
    "First I",
    "To analyze",
    "To extract",
    "To read",
    "I need to",
    "My approach",
    "I'm going to",
    "I should",
    "Looking at",
    "Based on",
    "Since ",
    "Because ",
]


def _stringify(value: Any) -> str:
    """Convert a value to a string representation."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=True)
    except Exception:
        return str(value)


def _shorten(text: str, limit: int = 160) -> str:
    """Shorten text to a maximum length with ellipsis."""
    if not text:
        return ""
    cleaned = text.replace("\n", " ").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _get_tool_call_meta(raw_item: Any) -> tuple[str, str | None, str, str | None]:
    """Extract tool call metadata from a raw item."""
    tool_name = None
    server_label = None
    call_id = None
    args = None

    if hasattr(raw_item, "name"):
        tool_name = getattr(raw_item, "name", None)
    if hasattr(raw_item, "server_label"):
        server_label = getattr(raw_item, "server_label", None)
    if hasattr(raw_item, "call_id"):
        call_id = getattr(raw_item, "call_id", None)
    if hasattr(raw_item, "id") and not call_id:
        call_id = getattr(raw_item, "id", None)
    if hasattr(raw_item, "arguments"):
        args = getattr(raw_item, "arguments", None)

    if isinstance(raw_item, dict):
        tool_name = (
            tool_name
            or raw_item.get("name")
            or raw_item.get("tool")
            or raw_item.get("type")
        )
        server_label = server_label or raw_item.get("server_label")
        call_id = call_id or raw_item.get("call_id") or raw_item.get("id")
        args = args if args is not None else raw_item.get("arguments")

    return tool_name or "unknown", server_label, _stringify(args), call_id


def _get_history_path() -> Path:
    """Get the path for storing command history."""
    history_dir = Path.home() / ".doc_analyzer"
    history_dir.mkdir(exist_ok=True)
    return history_dir / "repl_history"


def _print_header(console: Console) -> None:
    """Print the REPL header."""
    console.print()
    console.print("=" * 60, style="bold cyan")
    console.print(
        "       Document Analyzer Agent - Interactive REPL", style="bold cyan"
    )
    console.print("=" * 60, style="bold cyan")
    console.print("Type 'help' for commands, 'exit' or 'quit' to leave", style="dim")
    console.print("[green]Copy/paste friendly mode (Rich + Prompt Toolkit)[/green]")
    console.print()


def _print_tool_call(console: Console, tool_name: str, args: str = "") -> None:
    """Print a visible tool call notification."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    console.print()
    console.print(
        f"[on grey23][yellow] [{timestamp}] TOOL: {tool_name} [/yellow][/on grey23]"
    )
    if args:
        # Truncate long arguments for display
        display_args = args[:300] + "..." if len(args) > 300 else args
        # Clean up the display
        display_args = display_args.replace("\n", " ").strip()
        console.print(f"[dim]  Args: {display_args}[/dim]")


def _print_tool_output(console: Console, output: str) -> None:
    """Print tool output with truncation."""
    # Truncate very long outputs
    if len(output) > 500:
        display_output = output[:500] + f"... ({len(output) - 500} more chars)"
    else:
        display_output = output
    # Clean up newlines for display
    display_output = display_output.replace("\n", "\n  ")
    console.print(f"[green]  Output: {display_output}[/green]")


async def run_rich_prompt_repl(
    agent: Agent[Any],
    session: SQLiteSession,
    show_reasoning: bool = True,
    show_tool_calls: bool = True,
) -> None:
    """Run the Document Analyzer REPL with Rich formatting and Prompt Toolkit input.

    This REPL mode supports native copy/paste from the terminal.

    Args:
        agent: The document analyzer agent to run.
        session: SQLiteSession for conversation persistence.
        show_reasoning: Whether to highlight reasoning text (default True).
        show_tool_calls: Whether to show tool call notifications (default True).
    """
    console = Console()
    _print_header(console)

    # Set up Prompt Toolkit session with persistent history
    history_path = _get_history_path()
    prompt_session: PromptSession[str] = PromptSession(
        history=FileHistory(str(history_path)),
    )

    # Enable terminal-based approval mode (not Textual modal)
    set_terminal_approval_mode(console)
    enable_ui_approval()

    in_reasoning = False
    call_id_map: dict[str, str] = {}

    try:
        while True:
            try:
                # Use prompt_toolkit for input with history support
                user_input = await prompt_session.prompt_async(" > ")
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Goodbye![/dim]")
                break

            # Handle special commands
            cmd = user_input.strip().lower()
            if cmd in {"exit", "quit"}:
                console.print("[dim]Goodbye![/dim]")
                break

            if cmd == "help":
                console.print(Markdown(HELP_TEXT))
                continue

            if cmd == "clear":
                await session.clear_session()
                console.print("[green]Conversation history cleared.[/green]")
                continue

            if cmd == "history":
                items = await session.get_items()
                msg_count = len(
                    [
                        i
                        for i in items
                        if isinstance(i, dict) and i.get("role") == "user"
                    ]
                )
                console.print(
                    f"[cyan]Conversation has {msg_count} user messages "
                    f"and {len(items)} total items.[/cyan]"
                )
                continue

            if not user_input.strip():
                continue

            console.print()  # Add spacing before response

            try:
                # Run agent with streaming
                result = Runner.run_streamed(
                    agent,
                    input=user_input,
                    session=session,
                    max_turns=99,
                )

                accumulated_text = ""
                in_reasoning = False
                reasoning_summary = ""
                call_id_map = {}

                async for event in result.stream_events():
                    # Handle raw LLM response events (streaming text)
                    if isinstance(event, RawResponsesStreamEvent):
                        if isinstance(event.data, ResponseTextDeltaEvent):
                            delta = event.data.delta
                            accumulated_text += delta

                            # Check if this looks like reasoning at the start
                            if show_reasoning and len(accumulated_text) < 150:
                                if any(
                                    accumulated_text.strip().startswith(ind)
                                    for ind in REASONING_INDICATORS
                                ):
                                    if not in_reasoning:
                                        # Start reasoning mode with magenta italic
                                        console.print("[magenta italic]", end="")
                                        in_reasoning = True

                            # Check if we should end reasoning mode
                            if in_reasoning and len(accumulated_text) > 150:
                                transition_phrases = [
                                    "Now I'll",
                                    "Let me call",
                                    "I'll use the",
                                    "Using the",
                                ]
                                for phrase in transition_phrases:
                                    if phrase in accumulated_text[-100:]:
                                        console.print("[/magenta italic]", end="")
                                        in_reasoning = False
                                        break

                            # Print the delta directly for streaming effect
                            # Use print() for true streaming (Rich doesn't support end="")
                            print(delta, end="", flush=True)

                    # Handle run item events (tool calls, outputs, messages)
                    elif isinstance(event, RunItemStreamEvent):
                        if event.item.type == "tool_call_item":
                            # Reset any reasoning formatting
                            if in_reasoning:
                                console.print("[/magenta italic]", end="")
                                in_reasoning = False

                            if show_tool_calls:
                                tool_name, server_label, args, call_id = (
                                    _get_tool_call_meta(event.item.raw_item)
                                )
                                display_name = (
                                    f"{tool_name} ({server_label})"
                                    if server_label
                                    else tool_name
                                )
                                _print_tool_call(console, display_name, args)
                                if call_id:
                                    call_id_map[call_id] = display_name

                        elif event.item.type == "tool_call_output_item":
                            if show_tool_calls:
                                output = (
                                    str(event.item.output) if event.item.output else ""
                                )
                                _print_tool_output(console, output)
                                console.print()  # Add spacing after tool output

                        elif event.item.type == "reasoning_item" and show_reasoning:
                            raw_item = event.item.raw_item
                            summary_items = getattr(raw_item, "summary", None) or []
                            summary_text = " ".join(
                                getattr(item, "text", "") for item in summary_items
                            ).strip()
                            if summary_text:
                                reasoning_summary = _shorten(summary_text, 200)
                                console.print(
                                    f"\n[magenta]Reasoning: {reasoning_summary}[/magenta]"
                                )

                    # Handle agent updates (if using handoffs)
                    elif isinstance(event, AgentUpdatedStreamEvent):
                        console.print(
                            f"\n[cyan][Agent changed to: {event.new_agent.name}][/cyan]"
                        )

                # Reset formatting at end of response
                if in_reasoning:
                    console.print("[/magenta italic]", end="")
                    in_reasoning = False

                console.print("\n")  # Add spacing after response

            except Exception as e:
                # Reset formatting on error
                if in_reasoning:
                    console.print("[/magenta italic]", end="")
                console.print(f"\n[red]Error: {e!s}[/red]\n")

    finally:
        # Clean up approval mode
        disable_ui_approval()
        clear_terminal_approval_mode()
