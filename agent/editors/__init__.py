"""Document editors with diff preview and approval flow.

Provides ApplyPatchTool-style approval workflow for DOCX and XLSX modifications.
"""

from .base import ApprovalTracker, DocumentOperation, DocumentEditor
from .docx_editor import DocxEditor, DocxOperation
from .xlsx_editor import XlsxEditor, XlsxOperation
from .diff_display import render_diff

__all__ = [
    "ApprovalTracker",
    "DocumentOperation", 
    "DocumentEditor",
    "DocxEditor",
    "DocxOperation",
    "XlsxEditor", 
    "XlsxOperation",
    "render_diff",
]
