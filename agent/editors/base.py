"""Base classes for document editing with approval workflow.

Follows the ApplyPatchTool pattern from OpenAI Agents SDK.
"""

import hashlib
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class OperationType(str, Enum):
    """Types of document operations."""
    
    # DOCX operations
    DOCX_REPLACE_TEXT = "docx_replace_text"
    DOCX_INSERT_TEXT = "docx_insert_text"
    DOCX_DELETE_TEXT = "docx_delete_text"
    DOCX_ADD_COMMENT = "docx_add_comment"
    DOCX_ACCEPT_CHANGES = "docx_accept_changes"
    
    # XLSX operations
    XLSX_WRITE_CELL = "xlsx_write_cell"
    XLSX_WRITE_RANGE = "xlsx_write_range"
    XLSX_ADD_FORMULA = "xlsx_add_formula"
    XLSX_DELETE_ROW = "xlsx_delete_row"
    XLSX_DELETE_COLUMN = "xlsx_delete_column"
    XLSX_INSERT_ROW = "xlsx_insert_row"
    XLSX_INSERT_COLUMN = "xlsx_insert_column"


@dataclass
class DocumentOperation:
    """Represents a proposed document modification."""
    
    type: OperationType
    path: str
    description: str = ""
    
    # For text-based changes (DOCX)
    old_text: str | None = None
    new_text: str | None = None
    context_before: str | None = None
    context_after: str | None = None
    location: str | None = None  # e.g., "Paragraph 3", "Section 2.1"
    
    # For cell-based changes (XLSX)
    sheet: str | None = None
    cell: str | None = None
    cell_range: str | None = None
    old_value: Any = None
    new_value: Any = None
    
    # Additional metadata
    metadata: dict = field(default_factory=dict)


@dataclass
class OperationResult:
    """Result of applying a document operation."""
    
    success: bool
    output: str
    path: str | None = None
    error: str | None = None


class ApprovalTracker:
    """Tracks which operations have been approved by the user.
    
    Uses fingerprinting to avoid re-prompting for identical operations.
    """
    
    def __init__(self) -> None:
        self._approved: set[str] = set()
        self._rejected: set[str] = set()
    
    def fingerprint(self, operation: DocumentOperation) -> str:
        """Create a unique fingerprint for an operation."""
        hasher = hashlib.sha256()
        hasher.update(operation.type.value.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(operation.path.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update((operation.old_text or "").encode("utf-8"))
        hasher.update(b"\0")
        hasher.update((operation.new_text or "").encode("utf-8"))
        hasher.update(b"\0")
        hasher.update((operation.cell or "").encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(str(operation.old_value or "").encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(str(operation.new_value or "").encode("utf-8"))
        return hasher.hexdigest()
    
    def remember_approved(self, fingerprint: str) -> None:
        """Mark an operation as approved."""
        self._approved.add(fingerprint)
        self._rejected.discard(fingerprint)
    
    def remember_rejected(self, fingerprint: str) -> None:
        """Mark an operation as rejected."""
        self._rejected.add(fingerprint)
        self._approved.discard(fingerprint)
    
    def is_approved(self, fingerprint: str) -> bool:
        """Check if an operation was previously approved."""
        return fingerprint in self._approved
    
    def is_rejected(self, fingerprint: str) -> bool:
        """Check if an operation was previously rejected."""
        return fingerprint in self._rejected
    
    def clear(self) -> None:
        """Clear all approval history."""
        self._approved.clear()
        self._rejected.clear()


class DocumentEditor(ABC):
    """Base class for document editors with approval workflow.
    
    Subclasses implement format-specific diff display and modification logic.
    """
    
    def __init__(
        self,
        root: Path,
        approvals: ApprovalTracker,
        auto_approve: bool = False,
    ) -> None:
        self._root = root.resolve()
        self._approvals = approvals
        self._auto_approve = auto_approve or os.environ.get("DOCUMENT_EDIT_AUTO_APPROVE") == "1"
    
    @abstractmethod
    def render_diff(self, operation: DocumentOperation) -> str:
        """Render a human-readable diff for the operation.
        
        Should use ANSI colors: red for deletions, green for additions.
        """
        pass
    
    @abstractmethod
    def apply_operation(self, operation: DocumentOperation) -> OperationResult:
        """Apply the operation to the document.
        
        Called only after approval is granted.
        """
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> list[str]:
        """Return list of supported file extensions (e.g., ['.docx'])."""
        pass
    
    def execute(self, operation: DocumentOperation) -> OperationResult:
        """Execute an operation with approval flow.
        
        1. Render diff preview
        2. Ask for approval (unless auto-approve)
        3. Apply the operation
        4. Return result
        """
        relative_path = self._relative_path(operation.path)
        fingerprint = self._approvals.fingerprint(operation)
        
        # Check for previous rejection
        if self._approvals.is_rejected(fingerprint):
            return OperationResult(
                success=False,
                output="Operation was previously rejected.",
                path=relative_path,
            )
        
        # Check for auto-approve or previous approval
        if not self._auto_approve and not self._approvals.is_approved(fingerprint):
            approved = self._request_approval(operation, relative_path)
            if approved:
                self._approvals.remember_approved(fingerprint)
            else:
                self._approvals.remember_rejected(fingerprint)
                return OperationResult(
                    success=False,
                    output="Operation rejected by user.",
                    path=relative_path,
                )
        else:
            self._approvals.remember_approved(fingerprint)
        
        # Apply the operation
        try:
            result = self.apply_operation(operation)
            result.path = relative_path
            return result
        except Exception as e:
            return OperationResult(
                success=False,
                output=f"Failed to apply operation: {e}",
                path=relative_path,
                error=str(e),
            )
    
    def _request_approval(self, operation: DocumentOperation, display_path: str) -> bool:
        """Display diff and ask user for approval.

        If a UI approval callback is registered (e.g., from Textual app),
        use that instead of stdin input.
        """
        from .diff_display import render_diff_panel

        # Check for UI approval callback (e.g., Textual modal dialog)
        try:
            from ..approval_dialog import get_approval_callback
            callback = get_approval_callback()
            if callback is not None:
                # Use the UI callback
                diff_text = self.render_diff(operation)
                op_type = operation.type.value.replace("_", " ").title()
                return callback(
                    file_path=display_path,
                    description=operation.description or "",
                    diff_text=diff_text,
                    operation_type=op_type,
                )
        except ImportError:
            pass

        # Fall back to terminal input
        print()
        render_diff_panel(operation, display_path, self.render_diff(operation))

        try:
            answer = input("Apply changes? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False

        return answer in {"y", "yes"}
    
    def _relative_path(self, value: str) -> str:
        """Convert path to relative path from root."""
        resolved = self._resolve(value)
        try:
            return resolved.relative_to(self._root).as_posix()
        except ValueError:
            return value
    
    def _resolve(self, relative: str, ensure_parent: bool = False) -> Path:
        """Resolve a path relative to the workspace root."""
        candidate = Path(relative)
        target = candidate if candidate.is_absolute() else (self._root / candidate)
        target = target.resolve()
        
        # Security check: ensure path is within workspace
        try:
            target.relative_to(self._root)
        except ValueError:
            raise RuntimeError(f"Operation outside workspace: {relative}") from None
        
        if ensure_parent:
            target.parent.mkdir(parents=True, exist_ok=True)
        
        return target
