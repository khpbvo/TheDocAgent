"""Custom REPL for the Document Analyzer Agent.

Features:
- Streaming text output (token-by-token)
- Visible tool calls with timestamps
- Reasoning summaries (highlighted thinking)
- Conversation memory via SQLiteSession
- ANSI color formatting
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any

from openai.types.responses import ResponseTextDeltaEvent
from agents import (
    Agent,
    Runner,
    SQLiteSession,
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    AgentUpdatedStreamEvent,
)

try:
    from rich import box
    from rich.console import Console, Group
    from rich.layout import Layout
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except Exception:
    RICH_AVAILABLE = False

try:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Button, DataTable, Footer, Header, Input, RichLog, Static

    TEXTUAL_AVAILABLE = True
except Exception:
    TEXTUAL_AVAILABLE = False


class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"

    # Colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background
    BG_BLACK = "\033[40m"
    BG_GRAY = "\033[100m"


HELP_TEXT = """
Available Commands:
  help     - Show this help message
  clear    - Clear conversation history (start fresh)
  history  - Show conversation summary
  exit     - Exit the REPL (also: quit, Ctrl+C, Ctrl+D)

Document Analysis Examples:
  > Extract the text from /path/to/document.pdf
  > What tables are in /path/to/spreadsheet.xlsx?
  > Show me the comments in /path/to/contract.docx
  > Fill the form fields in /path/to/form.pdf with name="John"
  > Merge these PDFs: file1.pdf, file2.pdf into combined.pdf

Tips:
  - Provide full file paths for best results
  - The agent will ask clarifying questions if needed
  - Tool calls are shown with timestamps in yellow
"""


def print_header():
    """Print the REPL header."""
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}       Document Analyzer Agent - Interactive REPL{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.DIM}Type 'help' for commands, 'exit' or 'quit' to leave{Colors.RESET}")
    print()


def print_tool_call(tool_name: str, args: str = ""):
    """Print a visible tool call notification."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n{Colors.BG_GRAY}{Colors.YELLOW} [{timestamp}] TOOL: {tool_name} {Colors.RESET}")
    if args:
        # Truncate long arguments for display
        display_args = args[:300] + "..." if len(args) > 300 else args
        # Clean up the display
        display_args = display_args.replace("\n", " ").strip()
        print(f"{Colors.DIM}  Args: {display_args}{Colors.RESET}")


def print_tool_output(output: str):
    """Print tool output with truncation."""
    # Truncate very long outputs
    if len(output) > 500:
        display_output = output[:500] + f"... ({len(output) - 500} more chars)"
    else:
        display_output = output
    # Clean up newlines for display
    display_output = display_output.replace("\n", "\n  ")
    print(f"{Colors.GREEN}  Output: {display_output}{Colors.RESET}")


def print_reasoning(text: str):
    """Print reasoning/thinking text in a distinct style."""
    print(f"{Colors.MAGENTA}{Colors.ITALIC}{text}{Colors.RESET}", end="", flush=True)


def print_help():
    """Print help information."""
    print(HELP_TEXT)


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


async def run_document_analyzer_repl(
    agent: Agent[Any],
    session: SQLiteSession,
    show_reasoning: bool = True,
    show_tool_calls: bool = True,
) -> None:
    """Run the Document Analyzer REPL with Textual if available."""
    if TEXTUAL_AVAILABLE:
        await run_document_analyzer_repl_textual(
            agent=agent,
            session=session,
            show_reasoning=show_reasoning,
            show_tool_calls=show_tool_calls,
        )
    else:
        await run_document_analyzer_repl_plain(
            agent=agent,
            session=session,
            show_reasoning=show_reasoning,
            show_tool_calls=show_tool_calls,
        )


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=True)
    except Exception:
        return str(value)


def _shorten(text: str, limit: int = 160) -> str:
    if not text:
        return ""
    cleaned = text.replace("\n", " ").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _tail_lines(text: str, max_lines: int) -> str:
    if max_lines <= 0 or not text:
        return text
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[-max_lines:])


def _close_markdown_fences(text: str) -> str:
    if text.count("```") % 2 == 1:
        return text + "\n```"
    return text


class KnightRiderIndicator:
    def __init__(self, width: int = 12, speed: float = 8.0, idle_threshold: float = 0.4) -> None:
        self.width = max(1, width)
        self.speed = speed
        self.idle_threshold = idle_threshold
        self.active = False
        self.last_activity = time.monotonic()

    def start(self) -> None:
        self.active = True
        self.last_activity = time.monotonic()

    def stop(self) -> None:
        self.active = False

    def touch(self) -> None:
        self.last_activity = time.monotonic()

    def render(self) -> Any:
        if not self.active:
            return Text("Status: idle", style="dim")

        idle = (time.monotonic() - self.last_activity) >= self.idle_threshold
        if not idle:
            return Text("Status: streaming", style="dim")

        if self.width == 1:
            bar = "#"
        else:
            period = (self.width - 1) * 2
            step = int(time.monotonic() * self.speed) % period
            pos = step if step < self.width else (period - step)
            cells = ["-"] * self.width
            cells[pos] = "#"
            bar = "".join(cells)

        return Text(f"Thinking: [{bar}]", style="yellow")

    def __rich__(self) -> Any:
        return self.render()


def _get_tool_call_meta(raw_item: Any) -> tuple[str, str | None, str, str | None]:
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
        tool_name = tool_name or raw_item.get("name") or raw_item.get("tool") or raw_item.get("type")
        server_label = server_label or raw_item.get("server_label")
        call_id = call_id or raw_item.get("call_id") or raw_item.get("id")
        args = args if args is not None else raw_item.get("arguments")

    return tool_name or "unknown", server_label, _stringify(args), call_id


def _get_tool_output_call_id(raw_item: Any) -> str | None:
    if isinstance(raw_item, dict):
        return raw_item.get("call_id") or raw_item.get("id")
    return getattr(raw_item, "call_id", None) or getattr(raw_item, "id", None)


def _render_tool_table(tool_events: list[dict[str, str]]) -> Table | Text:
    if not tool_events:
        return Text("No tool activity yet.", style="dim")

    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.SIMPLE,
        pad_edge=False,
    )
    table.add_column("Event", style="bold", width=7, no_wrap=True)
    table.add_column("Tool", style="green", overflow="fold")
    table.add_column("Preview", overflow="fold")

    for event in tool_events:
        table.add_row(event["event"], event["tool"], event["preview"])

    return table


def _build_layout(
    response_text: str,
    tool_events: list[dict[str, str]],
    show_tool_calls: bool,
    status_renderable: Any | None = None,
) -> Layout:
    layout = Layout()
    layout.split_row(
        Layout(name="response", ratio=3),
        Layout(name="tools", ratio=1),
    )

    response_renderable = Markdown(response_text or " ")
    layout["response"].update(Panel(response_renderable, title="Response", border_style="cyan"))

    if show_tool_calls:
        tool_renderable = _render_tool_table(tool_events)
    else:
        tool_renderable = Text("Tool calls hidden.", style="dim")

    if status_renderable is not None:
        tool_renderable = Group(status_renderable, tool_renderable)

    layout["tools"].update(Panel(tool_renderable, title="Tools", border_style="yellow"))
    return layout


def _print_header_rich(console: Console) -> None:
    console.print()
    console.print("=" * 60, style="bold cyan")
    console.print("       Document Analyzer Agent - Interactive REPL", style="bold cyan")
    console.print("=" * 60, style="bold cyan")
    console.print("Type 'help' for commands, 'exit' or 'quit' to leave", style="dim")
    console.print()


def _print_help_rich(console: Console) -> None:
    console.print(Markdown(HELP_TEXT))


class DocumentAnalyzerApp(App):
    CSS = """
    #main {
        height: 1fr;
    }
    #left {
        width: 3fr;
        height: 1fr;
    }
    #right {
        width: 1fr;
        height: 1fr;
    }
    #response_log {
        height: 1fr;
    }
    #status {
        height: auto;
        padding: 0 1;
    }
    #tools {
        height: 1fr;
    }
    #prompt_bar {
        dock: bottom;
        height: auto;
    }
    #prompt {
        width: 1fr;
    }
    #send {
        width: 10;
    }
    """

    BINDINGS = [("ctrl+c", "quit", "Quit")]

    def __init__(
        self,
        agent: Agent[Any],
        session: SQLiteSession,
        show_reasoning: bool = True,
        show_tool_calls: bool = True,
    ) -> None:
        super().__init__()
        self.agent = agent
        self.session = session
        self.show_reasoning = show_reasoning
        self.show_tool_calls = show_tool_calls

        self._running = False
        # Debug: will show in on_mount since notify isn't available in __init__
        self._indicator = KnightRiderIndicator()
        self._history_entries: list[str] = []
        self._current_response = ""
        self._reasoning_summary = ""
        self._tool_events: list[dict[str, str]] = []
        self._call_id_map: dict[str, str] = {}
        self._max_tool_events = 100
        self._last_render = 0.0

        self._response_log: RichLog | None = None
        self._status: Static | None = None
        self._tools: DataTable | None = None
        self._prompt: Input | None = None
        self._send_button: Button | None = None
        self._run_task = None  # Worker instance

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield RichLog(id="response_log", wrap=True, highlight=False, markup=False)
            with Vertical(id="right"):
                yield Static(id="status")
                yield DataTable(id="tools")
        with Horizontal(id="prompt_bar"):
            yield Input(placeholder="Type a message...", id="prompt")
            yield Button("Send", id="send", variant="primary")
        yield Footer()

    async def on_mount(self) -> None:
        self._response_log = self.query_one("#response_log", RichLog)
        self._status = self.query_one("#status", Static)
        self._tools = self.query_one("#tools", DataTable)
        self._prompt = self.query_one("#prompt", Input)
        self._send_button = self.query_one("#send", Button)

        self._tools.add_columns("Event", "Tool", "Preview")
        self._refresh_status()
        self.set_interval(0.1, self._refresh_status)
        self.notify(f"App mounted! _running={self._running}", severity="information")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        self.notify(f"[INPUT] submitted: {event.value[:30]}...", severity="information")
        await self._handle_submit(event.value)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        self.notify(f"[BUTTON] pressed: {event.button.id}", severity="warning")
        if event.button.id != "send":
            return
        # Don't process if input already triggered it
        if self._running:
            self.notify("[BUTTON] Skipping - already running from input", severity="warning")
            return
        prompt = self._prompt.value if self._prompt else ""
        await self._handle_submit(prompt)

    async def _handle_submit(self, raw_prompt: str) -> None:
        prompt = raw_prompt.strip()
        self.notify(f"_handle_submit: prompt='{prompt[:20]}', running={self._running}", severity="information")
        if self._prompt:
            self._prompt.value = ""

        if not prompt:
            self.notify("Empty prompt - ignoring", severity="warning")
            return

        cmd = prompt.lower()
        if cmd in {"exit", "quit"}:
            self.exit()
            return

        if cmd == "help":
            self._append_system_message(HELP_TEXT.strip())
            return

        if cmd == "clear":
            await self.session.clear_session()
            self._history_entries = []
            self._current_response = ""
            self._tool_events = []
            self._call_id_map = {}
            self._reasoning_summary = ""
            self._clear_tools()
            self._render_transcript()
            return

        if cmd == "history":
            items = await self.session.get_items()
            msg_count = len([i for i in items if isinstance(i, dict) and i.get("role") == "user"])
            self._append_system_message(
                f"Conversation has {msg_count} user messages and {len(items)} total items."
            )
            return

        if self._running:
            self.notify("Already running - ignoring", severity="warning")
            return

        self.notify("About to start run...", severity="information")
        await self._start_run(prompt)

    def on_unmount(self) -> None:
        if self._run_task and self._run_task.is_running:
            self._run_task.cancel()

    def on_worker_state_changed(self, event) -> None:
        self.notify(f"Worker state: {event.state}", severity="information")

    async def _start_run(self, prompt: str) -> None:
        self.notify("_start_run entered", severity="information")
        self._running = True
        self._indicator.start()
        self._reasoning_summary = ""
        self._current_response = ""
        self._tool_events = []
        self._call_id_map = {}

        self._history_entries.append(f"**You:** {prompt}")
        self._clear_tools()
        self._render_transcript()
        self._set_input_enabled(False)

        self.notify("Creating worker...", severity="information")
        self._run_task = self.run_worker(self._run_agent(prompt), exclusive=True, exit_on_error=False)
        self.notify("Worker created!", severity="information")

    def _set_input_enabled(self, enabled: bool) -> None:
        if self._prompt:
            self._prompt.disabled = not enabled
        if self._send_button:
            self._send_button.disabled = not enabled

    def _render_transcript(self) -> None:
        if not self._response_log:
            return

        parts = list(self._history_entries)
        if self._current_response:
            parts.append(f"**Assistant:**\n{self._current_response}")

        text = "\n\n".join(parts) if parts else " "
        text = _close_markdown_fences(text)

        self._response_log.clear()
        self._response_log.write(Markdown(text))
        try:
            self._response_log.scroll_end()
        except Exception:
            pass

    def _append_system_message(self, message: str) -> None:
        self._history_entries.append(f"**System:** {message}")
        self._render_transcript()

    def _refresh_status(self) -> None:
        if not self._status:
            return

        status_lines = [self._indicator.render()]
        if self.show_reasoning and self._reasoning_summary:
            status_lines.append(Text(f"Reasoning: {self._reasoning_summary}", style="magenta"))
        self._status.update(Group(*status_lines))

    def _clear_tools(self) -> None:
        if not self._tools:
            return
        try:
            self._tools.clear()
        except Exception:
            self._tools = self.query_one("#tools", DataTable)
            self._tools.clear()
            self._tools.add_columns("Event", "Tool", "Preview")

    def _add_tool_event(self, event_type: str, tool: str, preview: str) -> None:
        if not self.show_tool_calls or not self._tools:
            return

        self._tool_events.append({"event": event_type, "tool": tool, "preview": preview})
        if len(self._tool_events) > self._max_tool_events:
            self._tool_events = self._tool_events[-self._max_tool_events :]

        self._clear_tools()
        for entry in self._tool_events:
            self._tools.add_row(entry["event"], entry["tool"], entry["preview"])

    async def _run_agent(self, prompt: str) -> None:
        event_count = 0
        try:
            self.notify(f"Starting agent with prompt: {prompt[:50]}...", severity="information")
            result = Runner.run_streamed(
                self.agent,
                input=prompt,
                session=self.session,
            )

            async for event in result.stream_events():
                event_count += 1
                updated = False

                if isinstance(event, RawResponsesStreamEvent):
                    if isinstance(event.data, ResponseTextDeltaEvent):
                        self._current_response += event.data.delta
                        self._indicator.touch()
                        updated = True

                elif isinstance(event, RunItemStreamEvent):
                    if event.item.type == "tool_call_item":
                        raw_item = event.item.raw_item
                        tool_name, server_label, args, call_id = _get_tool_call_meta(raw_item)
                        display_name = f"{tool_name} ({server_label})" if server_label else tool_name
                        preview = _shorten(args, 140) or "-"
                        self._add_tool_event("call", display_name, preview)
                        if call_id:
                            self._call_id_map[call_id] = display_name
                        self._indicator.touch()
                        updated = True

                    elif event.item.type == "tool_call_output_item":
                        raw_item = event.item.raw_item
                        call_id = _get_tool_output_call_id(raw_item)
                        display_name = self._call_id_map.get(call_id, "unknown")
                        output_text = _stringify(event.item.output)
                        preview = _shorten(output_text, 160) or "-"
                        self._add_tool_event("output", display_name, preview)
                        self._indicator.touch()
                        updated = True

                    elif event.item.type == "reasoning_item" and self.show_reasoning:
                        raw_item = event.item.raw_item
                        summary_items = getattr(raw_item, "summary", None) or []
                        summary_text = " ".join(getattr(item, "text", "") for item in summary_items).strip()
                        if summary_text:
                            self._reasoning_summary = _shorten(summary_text, 200)
                            updated = True

                elif isinstance(event, AgentUpdatedStreamEvent):
                    self._add_tool_event("agent", event.new_agent.name, "handoff")
                    updated = True

                if updated:
                    self._render_transcript()
                    self._refresh_status()

        except Exception as e:
            self.notify(f"Agent error: {e}", severity="error")
            self._append_system_message(f"Error: {e}")
        finally:
            self.notify(f"Agent finished. Events: {event_count}, Response len: {len(self._current_response)}", severity="information")
            if self._current_response:
                self._history_entries.append(f"**Assistant:**\n{self._current_response}")
                self._current_response = ""
            self._indicator.stop()
            self._running = False
            self._set_input_enabled(True)
            self._render_transcript()
            self._refresh_status()


async def run_document_analyzer_repl_textual(
    agent: Agent[Any],
    session: SQLiteSession,
    show_reasoning: bool = True,
    show_tool_calls: bool = True,
) -> None:
    if not TEXTUAL_AVAILABLE:
        raise RuntimeError("Textual is not available. Install it with: pip install textual")

    app = DocumentAnalyzerApp(
        agent=agent,
        session=session,
        show_reasoning=show_reasoning,
        show_tool_calls=show_tool_calls,
    )
    await app.run_async()


async def run_document_analyzer_repl_rich(
    agent: Agent[Any],
    session: SQLiteSession,
    show_reasoning: bool = True,
    show_tool_calls: bool = True,
) -> None:
    """Run the Document Analyzer REPL with Rich formatting."""
    console = Console()
    _print_header_rich(console)

    tool_events: list[dict[str, str]] = []
    call_id_map: dict[str, str] = {}
    max_tool_events = 12
    max_response_chars = 20000
    max_response_lines = 200
    reasoning_summary = ""
    indicator = KnightRiderIndicator()

    while True:
        try:
            user_input = console.input("[bold blue] > [/]")
        except (EOFError, KeyboardInterrupt):
            console.print("\nGoodbye!", style="dim")
            break

        cmd = user_input.strip().lower()
        if cmd in {"exit", "quit"}:
            console.print("Goodbye!", style="dim")
            break

        if cmd == "help":
            _print_help_rich(console)
            continue

        if cmd == "clear":
            await session.clear_session()
            tool_events = []
            call_id_map = {}
            console.print("Conversation history cleared.", style="green")
            continue

        if cmd == "history":
            items = await session.get_items()
            msg_count = len([i for i in items if isinstance(i, dict) and i.get("role") == "user"])
            console.print(
                f"Conversation has {msg_count} user messages and {len(items)} total items.",
                style="cyan",
            )
            continue

        if not user_input.strip():
            continue

        tool_events = []
        call_id_map = {}
        accumulated_text = ""
        reasoning_summary = ""

        try:
            result = Runner.run_streamed(
                agent,
                input=user_input,
                session=session,
            )

            indicator.start()
            display_text = _close_markdown_fences(_tail_lines(accumulated_text, max_response_lines))
            status_lines = [indicator]
            if reasoning_summary:
                status_lines.append(Text(f"Reasoning: {reasoning_summary}", style="magenta"))
            status_group = Group(*status_lines)
            layout = _build_layout(display_text, tool_events, show_tool_calls, status_group)
            with Live(layout, console=console, refresh_per_second=12) as live:
                async for event in result.stream_events():
                    updated = False

                    if isinstance(event, RawResponsesStreamEvent):
                        if isinstance(event.data, ResponseTextDeltaEvent):
                            accumulated_text += event.data.delta
                            if len(accumulated_text) > max_response_chars:
                                accumulated_text = accumulated_text[-max_response_chars:]
                            indicator.touch()
                            updated = True

                    elif isinstance(event, RunItemStreamEvent):
                        if event.item.type == "tool_call_item":
                            raw_item = event.item.raw_item
                            tool_name, server_label, args, call_id = _get_tool_call_meta(raw_item)
                            display_name = f"{tool_name} ({server_label})" if server_label else tool_name
                            preview = _shorten(args, 140) or "-"
                            tool_events.append(
                                {
                                    "event": "call",
                                    "tool": display_name,
                                    "preview": preview,
                                }
                            )
                            if call_id:
                                call_id_map[call_id] = display_name
                            indicator.touch()
                            updated = True

                        elif event.item.type == "tool_call_output_item":
                            raw_item = event.item.raw_item
                            call_id = _get_tool_output_call_id(raw_item)
                            display_name = call_id_map.get(call_id, "unknown")
                            output_text = _stringify(event.item.output)
                            preview = _shorten(output_text, 160) or "-"
                            tool_events.append(
                                {
                                    "event": "output",
                                    "tool": display_name,
                                    "preview": preview,
                                }
                            )
                            indicator.touch()
                            updated = True

                        elif event.item.type == "reasoning_item" and show_reasoning:
                            raw_item = event.item.raw_item
                            summary_items = getattr(raw_item, "summary", None) or []
                            summary_text = " ".join(getattr(item, "text", "") for item in summary_items).strip()
                            if summary_text:
                                reasoning_summary = _shorten(summary_text, 200)
                                updated = True

                    elif isinstance(event, AgentUpdatedStreamEvent):
                        tool_events.append(
                            {
                                "event": "agent",
                                "tool": event.new_agent.name,
                                "preview": "handoff",
                            }
                        )
                        updated = True

                    if updated:
                        if len(tool_events) > max_tool_events:
                            tool_events = tool_events[-max_tool_events:]
                        display_text = _close_markdown_fences(_tail_lines(accumulated_text, max_response_lines))
                        status_lines = [indicator]
                        if reasoning_summary:
                            status_lines.append(Text(f"Reasoning: {reasoning_summary}", style="magenta"))
                        status_group = Group(*status_lines)
                        layout = _build_layout(display_text, tool_events, show_tool_calls, status_group)
                        live.update(layout, refresh=True)

        except Exception as e:
            console.print(f"Error: {e}", style="red")
        finally:
            indicator.stop()


async def run_document_analyzer_repl_plain(
    agent: Agent[Any],
    session: SQLiteSession,
    show_reasoning: bool = True,
    show_tool_calls: bool = True,
) -> None:
    """Run the Document Analyzer REPL with streaming and tool visibility.

    Args:
        agent: The document analyzer agent to run.
        session: SQLiteSession for conversation persistence.
        show_reasoning: Whether to highlight reasoning text (default True).
        show_tool_calls: Whether to show tool call notifications (default True).
    """
    print_header()

    in_reasoning = False
    accumulated_text = ""

    while True:
        try:
            user_input = input(f"{Colors.BOLD}{Colors.BLUE} > {Colors.RESET}")
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.DIM}Goodbye!{Colors.RESET}")
            break

        # Handle special commands
        cmd = user_input.strip().lower()
        if cmd in {"exit", "quit"}:
            print(f"{Colors.DIM}Goodbye!{Colors.RESET}")
            break

        if cmd == "help":
            print_help()
            continue

        if cmd == "clear":
            await session.clear_session()
            print(f"{Colors.GREEN}Conversation history cleared.{Colors.RESET}")
            continue

        if cmd == "history":
            items = await session.get_items()
            msg_count = len([i for i in items if isinstance(i, dict) and i.get("role") == "user"])
            print(f"{Colors.CYAN}Conversation has {msg_count} user messages and {len(items)} total items.{Colors.RESET}")
            continue

        if not user_input.strip():
            continue

        print()  # Add spacing before response

        try:
            # Run agent with streaming
            result = Runner.run_streamed(
                agent,
                input=user_input,
                session=session,
            )

            accumulated_text = ""
            in_reasoning = False

            async for event in result.stream_events():
                # Handle raw LLM response events (streaming text)
                if isinstance(event, RawResponsesStreamEvent):
                    if isinstance(event.data, ResponseTextDeltaEvent):
                        delta = event.data.delta
                        accumulated_text += delta

                        # Check if this looks like reasoning at the start
                        if show_reasoning and len(accumulated_text) < 150:
                            if any(accumulated_text.strip().startswith(ind) for ind in REASONING_INDICATORS):
                                if not in_reasoning:
                                    print(f"{Colors.MAGENTA}{Colors.ITALIC}", end="", flush=True)
                                    in_reasoning = True

                        # Check if we should end reasoning mode (e.g., tool call coming)
                        if in_reasoning and len(accumulated_text) > 150:
                            # Look for transition phrases that indicate reasoning is done
                            transition_phrases = ["Now I'll", "Let me call", "I'll use the", "Using the"]
                            for phrase in transition_phrases:
                                if phrase in accumulated_text[-100:]:
                                    print(f"{Colors.RESET}", end="", flush=True)
                                    in_reasoning = False
                                    break

                        print(delta, end="", flush=True)

                # Handle run item events (tool calls, outputs, messages)
                elif isinstance(event, RunItemStreamEvent):
                    if event.item.type == "tool_call_item":
                        # Reset any reasoning formatting
                        if in_reasoning:
                            print(f"{Colors.RESET}", end="")
                            in_reasoning = False

                        if show_tool_calls:
                            tool_name, server_label, args, _ = _get_tool_call_meta(event.item.raw_item)
                            display_name = f"{tool_name} ({server_label})" if server_label else tool_name
                            print_tool_call(display_name, args)

                    elif event.item.type == "tool_call_output_item":
                        if show_tool_calls:
                            output = str(event.item.output) if event.item.output else ""
                            print_tool_output(output)
                            print()  # Add spacing after tool output

                    elif event.item.type == "message_output_item":
                        # Final message output - already streamed above
                        pass

                # Handle agent updates (if using handoffs)
                elif isinstance(event, AgentUpdatedStreamEvent):
                    print(f"\n{Colors.CYAN}[Agent changed to: {event.new_agent.name}]{Colors.RESET}")

            # Reset formatting at end of response
            if in_reasoning:
                print(f"{Colors.RESET}", end="")
                in_reasoning = False

            print("\n")  # Add spacing after response

        except Exception as e:
            # Reset formatting on error
            if in_reasoning:
                print(f"{Colors.RESET}", end="")
            print(f"\n{Colors.RED}Error: {str(e)}{Colors.RESET}\n")


async def run_simple_repl(agent: Agent[Any], session: SQLiteSession) -> None:
    """Run a simpler REPL without streaming (for debugging).

    Args:
        agent: The agent to run.
        session: SQLiteSession for conversation persistence.
    """
    print_header()

    while True:
        try:
            user_input = input(f"{Colors.BOLD}{Colors.BLUE} > {Colors.RESET}")
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.DIM}Goodbye!{Colors.RESET}")
            break

        if user_input.strip().lower() in {"exit", "quit"}:
            break

        if not user_input.strip():
            continue

        try:
            result = await Runner.run(agent, user_input, session=session)
            print(f"\n{result.final_output}\n")
        except Exception as e:
            print(f"\n{Colors.RED}Error: {str(e)}{Colors.RESET}\n")
