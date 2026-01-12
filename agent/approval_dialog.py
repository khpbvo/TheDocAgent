"""Document edit approval dialogs.

Provides both Textual modal dialogs and terminal-based approval prompts
with colored diff display for approving document modifications.
"""

import re
import threading
from dataclasses import dataclass
from typing import Any

# Rich is optional but preferred for terminal approval
try:
    from rich.console import Console  # noqa: F401

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Textual is optional for modal dialogs
try:
    from textual.app import ComposeResult
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.screen import ModalScreen
    from textual.widgets import Button, Label, Static

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False


@dataclass
class ApprovalRequest:
    """A pending approval request."""

    file_path: str
    description: str
    diff_text: str
    operation_type: str
    result: bool | None = None
    event: threading.Event = None

    def __post_init__(self):
        if self.event is None:
            self.event = threading.Event()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_pattern.sub("", text)


if TEXTUAL_AVAILABLE:

    class ApprovalDialog(ModalScreen[bool]):
        """Modal dialog for approving document edits.

        Shows a diff preview and asks for user confirmation.
        Returns True if approved, False if rejected.
        """

        CSS = """
        ApprovalDialog {
            align: center middle;
        }

        #approval-dialog {
            width: 80%;
            height: 80%;
            border: thick $warning;
            background: $surface;
            padding: 1 2;
        }

        #approval-header {
            height: auto;
            margin-bottom: 1;
        }

        #approval-title {
            text-style: bold;
            color: $warning;
        }

        #approval-path {
            color: $primary-lighten-2;
        }

        #approval-description {
            color: $text;
            margin-top: 1;
        }

        #diff-container {
            height: 1fr;
            border: solid $primary-muted;
            background: $surface-darken-1;
            margin: 1 0;
        }

        #diff-content {
            padding: 1;
        }

        #approval-buttons {
            height: auto;
            align: center middle;
            margin-top: 1;
        }

        #approval-buttons Button {
            margin: 0 2;
            min-width: 16;
        }
        """

        BINDINGS = [
            ("y", "approve", "Approve"),
            ("n", "reject", "Reject"),
            ("escape", "reject", "Cancel"),
        ]

        def __init__(
            self,
            file_path: str,
            description: str,
            diff_text: str,
            operation_type: str = "Edit",
        ) -> None:
            """Initialize the approval dialog.

            Args:
                file_path: Path to the file being modified.
                description: Description of the change.
                diff_text: The diff to display (ANSI codes will be stripped).
                operation_type: Type of operation (e.g., "Replace", "Insert", "Delete").
            """
            super().__init__()
            self.file_path = file_path
            self.description = description
            # Strip ANSI codes and format for display
            self.diff_text = self._format_diff(strip_ansi(diff_text))
            self.operation_type = operation_type

        def _format_diff(self, diff: str) -> str:
            """Format diff text with Rich markup for display."""
            lines = []
            for line in diff.splitlines():
                stripped = line.lstrip()
                if stripped.startswith("+ "):
                    lines.append(f"[green]{line}[/green]")
                elif stripped.startswith("- "):
                    lines.append(f"[red]{line}[/red]")
                elif stripped.startswith("@ "):
                    lines.append(f"[cyan]{line}[/cyan]")
                else:
                    lines.append(f"[dim]{line}[/dim]")
            return "\n".join(lines)

        def compose(self) -> ComposeResult:
            with Vertical(id="approval-dialog"):
                with Vertical(id="approval-header"):
                    yield Label(f" {self.operation_type}", id="approval-title")
                    yield Label(f"File: {self.file_path}", id="approval-path")
                    if self.description:
                        yield Label(self.description, id="approval-description")

                with VerticalScroll(id="diff-container"):
                    yield Static(self.diff_text, id="diff-content", markup=True)

                with Horizontal(id="approval-buttons"):
                    yield Button("Approve (Y)", variant="success", id="approve")
                    yield Button("Reject (N)", variant="error", id="reject")

        def on_button_pressed(self, event: Button.Pressed) -> None:
            """Handle button presses."""
            event.stop()  # Prevent event bubbling
            if event.button.id == "approve":
                self.dismiss(True)
            elif event.button.id == "reject":
                self.dismiss(False)

        def action_approve(self) -> None:
            """Approve the change."""
            self.dismiss(True)

        def action_reject(self) -> None:
            """Reject the change."""
            self.dismiss(False)


# Global state for approval requests
_pending_request: ApprovalRequest | None = None
_request_lock = threading.Lock()
_app_reference = None


def set_app_reference(app):
    """Set reference to the Textual app for showing dialogs."""
    global _app_reference
    _app_reference = app


def get_app_reference():
    """Get the Textual app reference."""
    return _app_reference


def clear_app_reference():
    """Clear the app reference."""
    global _app_reference
    _app_reference = None


def request_approval(
    file_path: str,
    description: str,
    diff_text: str,
    operation_type: str,
) -> bool:
    """Request approval for a document edit.

    This function is called from the tool execution (sync context).
    It signals the UI to show a dialog and waits for the result.

    Supports three modes:
    1. Textual modal dialog (when Textual app is registered)
    2. Rich terminal diff (when terminal console is registered)
    3. Plain terminal fallback

    Args:
        file_path: Path to the file being modified.
        description: Description of the change.
        diff_text: The diff to display.
        operation_type: Type of operation.

    Returns:
        True if approved, False if rejected.
    """
    global _pending_request

    # Check for terminal approval mode first (Rich + Prompt Toolkit REPL)
    terminal_console = get_terminal_console()
    if terminal_console is not None:
        return terminal_diff_approval(
            file_path, description, diff_text, operation_type, terminal_console
        )

    # Check for Textual app
    app = get_app_reference()
    if app is None:
        # No app registered - fall back to plain terminal
        return _terminal_approval(file_path, description, diff_text, operation_type)

    # Create the request
    request = ApprovalRequest(
        file_path=file_path,
        description=description,
        diff_text=diff_text,
        operation_type=operation_type,
    )

    with _request_lock:
        _pending_request = request

    # Signal the app to show the dialog
    try:
        app.call_from_thread(app.show_approval_dialog, request)
    except Exception:
        # If call_from_thread fails, fall back to terminal
        with _request_lock:
            _pending_request = None
        return _terminal_approval(file_path, description, diff_text, operation_type)

    # Wait for the result (with timeout)
    request.event.wait(timeout=300)  # 5 minute timeout

    with _request_lock:
        _pending_request = None

    return request.result if request.result is not None else False


def _terminal_approval(
    file_path: str,
    description: str,
    diff_text: str,
    operation_type: str,
) -> bool:
    """Fall back to terminal-based approval."""
    print(f"\n{'=' * 60}")
    print(f"Proposed Edit: {operation_type}")
    print(f"File: {file_path}")
    if description:
        print(f"Description: {description}")
    print(f"{'=' * 60}")
    print(diff_text)
    print(f"{'=' * 60}")

    try:
        answer = input("Apply changes? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False

    return answer in {"y", "yes"}


def get_pending_request() -> ApprovalRequest | None:
    """Get the current pending approval request."""
    with _request_lock:
        return _pending_request


# Callback wrapper for DocumentEditor
def _approval_callback(
    file_path: str,
    description: str,
    diff_text: str,
    operation_type: str,
) -> bool:
    """Callback for DocumentEditor to request approval."""
    return request_approval(file_path, description, diff_text, operation_type)


# Global approval callback for use by DocumentEditor
_approval_callback_enabled = False


def enable_ui_approval():
    """Enable UI-based approval dialogs."""
    global _approval_callback_enabled
    _approval_callback_enabled = True


def disable_ui_approval():
    """Disable UI-based approval dialogs."""
    global _approval_callback_enabled
    _approval_callback_enabled = False


def get_approval_callback():
    """Get the approval callback if UI approval is enabled."""
    if _approval_callback_enabled:
        return _approval_callback
    return None


def set_approval_callback(callback):
    """Set a custom approval callback (for backwards compatibility)."""
    global _approval_callback_enabled
    _approval_callback_enabled = callback is not None


def clear_approval_callback():
    """Clear the approval callback."""
    global _approval_callback_enabled
    _approval_callback_enabled = False


# Terminal-based approval mode (for Rich + Prompt Toolkit REPL)
_terminal_console: Any = None


def set_terminal_approval_mode(console: Any) -> None:
    """Set terminal approval mode with the given Rich console.

    When set, approval requests will use colored terminal output
    instead of Textual modal dialogs.

    Args:
        console: A Rich Console instance for output.
    """
    global _terminal_console
    _terminal_console = console


def clear_terminal_approval_mode() -> None:
    """Clear terminal approval mode."""
    global _terminal_console
    _terminal_console = None


def get_terminal_console() -> Any:
    """Get the terminal console if terminal approval mode is active."""
    return _terminal_console


def terminal_diff_approval(
    file_path: str,
    description: str,
    diff_text: str,
    operation_type: str,
    console: Any = None,
) -> bool:
    """Display colored diff and prompt for approval in terminal.

    Shows a diff with:
    - Green (+) for added lines
    - Red (-) for deleted lines
    - Cyan (@) for hunk headers
    - Dim for context lines

    Args:
        file_path: Path to the file being modified.
        description: Description of the change.
        diff_text: The diff to display.
        operation_type: Type of operation.
        console: Optional Rich Console instance.

    Returns:
        True if approved, False if rejected.
    """
    # Use provided console or try to get global terminal console
    if console is None:
        console = get_terminal_console()

    # If Rich is available and we have a console, use rich output
    if RICH_AVAILABLE and console is not None:
        return _terminal_diff_approval_rich(
            file_path, description, diff_text, operation_type, console
        )

    # Fall back to plain terminal approval
    return _terminal_approval(file_path, description, diff_text, operation_type)


def _terminal_diff_approval_rich(
    file_path: str,
    description: str,
    diff_text: str,
    operation_type: str,
    console: Any,
) -> bool:
    """Rich-formatted terminal diff approval."""
    # Clean diff text
    clean_diff = strip_ansi(diff_text)

    # Header
    console.print()
    console.print("=" * 60, style="yellow")
    console.print(f"[bold yellow]Proposed Edit: {operation_type}[/bold yellow]")
    console.print(f"[cyan]File: {file_path}[/cyan]")
    if description:
        console.print(f"[dim]{description}[/dim]")
    console.print("=" * 60, style="yellow")
    console.print()

    # Colored diff
    for line in clean_diff.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("+ "):
            console.print(f"[green]{line}[/green]")
        elif stripped.startswith("- "):
            console.print(f"[red]{line}[/red]")
        elif stripped.startswith("@"):
            console.print(f"[cyan]{line}[/cyan]")
        else:
            console.print(f"[dim]{line}[/dim]")

    console.print()
    console.print("=" * 60, style="yellow")

    # Prompt
    try:
        answer = console.input("[bold]Apply changes? [y/N] [/bold]").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print()
        return False

    return answer in {"y", "yes"}
