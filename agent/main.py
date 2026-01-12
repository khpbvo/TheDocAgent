#!/usr/bin/env python3
"""Document Analyzer Agent - Main Entry Point.

An interactive agent for analyzing and modifying PDF, DOCX, and XLSX documents
using the OpenAI Agents SDK.

Usage:
    python -m agent.main                    # Start new session
    python -m agent.main --session-id ID    # Resume existing session
    python -m agent.main --model gpt-4o     # Use specific model
    python -m agent.main --no-tool-calls    # Hide tool call notifications
"""

import argparse
import asyncio
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from agents import SQLiteSession
from agents.mcp import MCPServerStdio

from .config import create_agent, create_reasoning_agent
from .repl import run_document_analyzer_repl


def get_default_db_path() -> Path:
    """Get the default database path for session storage."""
    repo_root = Path(__file__).parent.parent
    data_dir = repo_root / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir / "sessions.db"


def generate_session_id() -> str:
    """Generate a unique session ID with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"doc_analyzer_{timestamp}_{short_uuid}"


def get_repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).parent.parent


def build_filesystem_mcp_server(root_dir: Path) -> MCPServerStdio | None:
    """Create a filesystem MCP server if the required executable is available."""
    if not shutil.which("npx"):
        print("MCP filesystem server disabled: 'npx' not found in PATH.")
        return None

    return MCPServerStdio(
        name="Filesystem MCP Server",
        params={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", str(root_dir)],
        },
        cache_tools_list=True,
    )


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Document Analyzer Agent - Interactive REPL for document analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agent.main                          # Start new session with default model
  python -m agent.main --model gpt-4o           # Use GPT-4o model
  python -m agent.main --model o1               # Use o1 reasoning model
  python -m agent.main --session-id my_session  # Resume existing session
  python -m agent.main --no-tool-calls          # Hide tool call output
  python -m agent.main --auto-approve           # Skip Y/N prompts for document edits
        """,
    )
    parser.add_argument(
        "--session-id",
        type=str,
        help="Session ID to resume (creates new session if not provided)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        help="Path to SQLite database for session storage",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5.1",
        help="LLM model to use (default: gpt-5.1). Use o1, o3, or gpt-5.1 for reasoning models.",
    )
    parser.add_argument(
        "--no-tool-calls",
        action="store_true",
        help="Hide tool call notifications",
    )
    parser.add_argument(
        "--no-reasoning",
        action="store_true",
        help="Don't highlight reasoning text",
    )
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Use simple REPL without streaming (for debugging)",
    )
    parser.add_argument(
        "--no-mcp-filesystem",
        action="store_true",
        help="Disable local filesystem MCP server integration",
    )
    parser.add_argument(
        "--mcp-filesystem-root",
        type=str,
        help="Root path for filesystem MCP server (default: repository root)",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip Y/N approval prompts for document edits (auto-accept all changes)",
    )
    parser.add_argument(
        "--no-approval",
        action="store_true",
        help="Disable approval mode entirely (use direct write tools instead of diff preview)",
    )
    parser.add_argument(
        "--ui",
        type=str,
        choices=["textual", "rich", "plain", "auto"],
        default="auto",
        help="UI mode: textual (full TUI), rich (copy-paste friendly), plain (minimal), auto (best available)",
    )
    return parser.parse_args()


async def main():
    """Main entry point for the Document Analyzer Agent."""
    args = parse_args()

    # Determine database path
    db_path = args.db_path or str(get_default_db_path())

    # Create or resume session
    if args.session_id:
        session_id = args.session_id
        print(f"Resuming session: {session_id}")
    else:
        session_id = generate_session_id()
        print(f"Created new session: {session_id}")

    session = SQLiteSession(session_id, db_path)

    # Create MCP servers (optional)
    mcp_servers = []
    filesystem_root = None
    if not args.no_mcp_filesystem:
        filesystem_root = (
            Path(args.mcp_filesystem_root).resolve()
            if args.mcp_filesystem_root
            else get_repo_root()
        )
        filesystem_server = build_filesystem_mcp_server(filesystem_root)
        if filesystem_server:
            mcp_servers = [filesystem_server]
            print(f"MCP filesystem root: {filesystem_root}")

    # Configure document editor approval mode
    approval_mode = not args.no_approval
    if approval_mode:
        from .tools import set_workspace_root

        workspace_root = filesystem_root or get_repo_root()
        set_workspace_root(workspace_root)

        if args.auto_approve:
            import os

            os.environ["DOCUMENT_EDIT_AUTO_APPROVE"] = "1"
            print("Document edits: auto-approve enabled")
        else:
            print("Document edits: diff preview + Y/N approval")
    else:
        print("Document edits: direct write (no approval)")

    # Create the agent with appropriate config
    model = args.model.lower()
    if model in ("o1", "o3", "gpt-5.1", "gpt-5"):
        # Use reasoning model config
        agent = create_reasoning_agent(
            model=args.model,
            mcp_servers=mcp_servers,
            approval_mode=approval_mode,
        )
        print(f"Using reasoning model: {args.model}")
    else:
        agent = create_agent(
            model=args.model,
            mcp_servers=mcp_servers,
            approval_mode=approval_mode,
        )
        print(f"Using model: {args.model}")

    print(f"Session stored at: {db_path}")

    # Run the REPL
    if mcp_servers:
        async with mcp_servers[0]:
            if args.simple:
                from .repl import run_simple_repl

                await run_simple_repl(agent, session)
            else:
                await run_document_analyzer_repl(
                    agent=agent,
                    session=session,
                    show_reasoning=not args.no_reasoning,
                    show_tool_calls=not args.no_tool_calls,
                    ui_mode=args.ui,
                )
    elif args.simple:
        from .repl import run_simple_repl

        await run_simple_repl(agent, session)
    else:
        await run_document_analyzer_repl(
            agent=agent,
            session=session,
            show_reasoning=not args.no_reasoning,
            show_tool_calls=not args.no_tool_calls,
            ui_mode=args.ui,
        )


def run():
    """Synchronous entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
