"""Document Analyzer Agent package.

An interactive agent for analyzing and modifying PDF, DOCX, and XLSX documents
using the OpenAI Agents SDK.

Usage:
    python -m agent.main
"""

from .config import create_agent, create_reasoning_agent
from .repl import run_document_analyzer_repl

__all__ = [
    "create_agent",
    "create_reasoning_agent",
    "run_document_analyzer_repl",
]
