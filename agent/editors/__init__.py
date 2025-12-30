"""Document editors with diff preview and approval flow.

Provides ApplyPatchTool-style approval workflow for DOCX and XLSX modifications.
"""

from .base import ApprovalTracker, DocumentEditor, DocumentOperation
from .diff_display import render_diff
from .docx_editor import DocxEditor, DocxOperation
from .xlsx_editor import XlsxEditor, XlsxOperation

__all__ = [
    "ApprovalTracker",
    "DocumentEditor",
    "DocumentOperation",
    "DocxEditor",
    "DocxOperation",
    "XlsxEditor",
    "XlsxOperation",
    "render_diff",
]
