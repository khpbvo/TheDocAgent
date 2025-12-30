"""Rich diff display for document operations.

Renders diffs with red/green coloring like git diff.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import DocumentOperation

# ANSI color codes
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Try to use Rich if available
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def render_text_diff(old_text: str | None, new_text: str | None, context_lines: int = 2) -> str:
    """Render a text diff with +/- prefixes and colors.
    
    Args:
        old_text: Original text (None for insertions)
        new_text: New text (None for deletions)
        context_lines: Number of context lines to show
        
    Returns:
        Colored diff string
    """
    lines = []
    
    if old_text is None and new_text is None:
        return f"{DIM}(no changes){RESET}"
    
    if old_text is None:
        # Pure insertion
        for line in (new_text or "").splitlines():
            lines.append(f"{GREEN}+ {line}{RESET}")
    elif new_text is None:
        # Pure deletion
        for line in (old_text or "").splitlines():
            lines.append(f"{RED}- {line}{RESET}")
    else:
        # Replacement - show old and new
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        
        for line in old_lines:
            lines.append(f"{RED}- {line}{RESET}")
        for line in new_lines:
            lines.append(f"{GREEN}+ {line}{RESET}")
    
    return "\n".join(lines)


def render_cell_diff(
    cell: str,
    old_value: str | None,
    new_value: str | None,
    sheet: str | None = None,
) -> str:
    """Render a cell value change.
    
    Args:
        cell: Cell reference (e.g., "A1")
        old_value: Original value
        new_value: New value
        sheet: Optional sheet name
        
    Returns:
        Colored diff string
    """
    location = f"{sheet}!{cell}" if sheet else cell
    
    if old_value is None:
        return f"{CYAN}{location}{RESET}: {GREEN}+ {new_value}{RESET}"
    elif new_value is None:
        return f"{CYAN}{location}{RESET}: {RED}- {old_value}{RESET}"
    else:
        return (
            f"{CYAN}{location}{RESET}:\n"
            f"  {RED}- {old_value}{RESET}\n"
            f"  {GREEN}+ {new_value}{RESET}"
        )


def render_diff(operation: "DocumentOperation") -> str:
    """Render a diff for any document operation.
    
    Dispatches to appropriate renderer based on operation type.
    """
    op_type = operation.type.value
    
    if op_type.startswith("xlsx_"):
        return render_cell_diff(
            cell=operation.cell or "?",
            old_value=operation.old_value,
            new_value=operation.new_value,
            sheet=operation.sheet,
        )
    elif op_type.startswith("docx_"):
        diff = render_text_diff(operation.old_text, operation.new_text)
        
        # Add location context if available
        if operation.location:
            return f"{DIM}@ {operation.location}{RESET}\n{diff}"
        
        # Add surrounding context if available
        result_parts = []
        if operation.context_before:
            for line in operation.context_before.splitlines():
                result_parts.append(f"{DIM}  {line}{RESET}")
        result_parts.append(diff)
        if operation.context_after:
            for line in operation.context_after.splitlines():
                result_parts.append(f"{DIM}  {line}{RESET}")
        
        return "\n".join(result_parts)
    else:
        return f"{DIM}(unknown operation type: {op_type}){RESET}"


def render_diff_panel(
    operation: "DocumentOperation",
    display_path: str,
    diff_content: str,
) -> None:
    """Render a diff panel to the console.
    
    Uses Rich if available, falls back to plain ANSI.
    """
    op_type = operation.type.value.replace("_", " ").title()
    
    if RICH_AVAILABLE:
        console = Console()
        
        # Build the content
        content = Text()
        content.append(f"Operation: ", style="bold")
        content.append(f"{op_type}\n", style="yellow")
        content.append(f"File: ", style="bold")
        content.append(f"{display_path}\n\n", style="cyan")
        
        if operation.description:
            content.append(f"{operation.description}\n\n", style="dim")
        
        # Parse the diff content and add colors
        for line in diff_content.splitlines():
            if line.startswith("\033[91m") or line.lstrip().startswith("-"):
                # Red line (deletion)
                clean = line.replace("\033[91m", "").replace("\033[0m", "")
                content.append(clean + "\n", style="red")
            elif line.startswith("\033[92m") or line.lstrip().startswith("+"):
                # Green line (addition)
                clean = line.replace("\033[92m", "").replace("\033[0m", "")
                content.append(clean + "\n", style="green")
            elif line.startswith("\033[2m"):
                # Dim line (context)
                clean = line.replace("\033[2m", "").replace("\033[0m", "")
                content.append(clean + "\n", style="dim")
            else:
                # Strip any remaining ANSI codes
                clean = line
                for code in ["\033[91m", "\033[92m", "\033[93m", "\033[96m", "\033[2m", "\033[1m", "\033[0m"]:
                    clean = clean.replace(code, "")
                content.append(clean + "\n")
        
        panel = Panel(
            content,
            title="[bold yellow]Proposed Edit[/]",
            border_style="yellow",
            box=box.ROUNDED,
        )
        console.print(panel)
    else:
        # Plain ANSI fallback
        print()
        print(f"{YELLOW}{'─' * 60}{RESET}")
        print(f"{BOLD}{YELLOW} Proposed Edit{RESET}")
        print(f"{YELLOW}{'─' * 60}{RESET}")
        print(f"{BOLD}Operation:{RESET} {op_type}")
        print(f"{BOLD}File:{RESET} {CYAN}{display_path}{RESET}")
        if operation.description:
            print(f"{DIM}{operation.description}{RESET}")
        print()
        print(diff_content)
        print(f"{YELLOW}{'─' * 60}{RESET}")
