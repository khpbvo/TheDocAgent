"""Document analysis and modification tools for the Document Analyzer Agent.

Exports all tools from pdf_tools, docx_tools, and xlsx_tools modules.
Also exports approval-enabled tools that show diffs before applying changes.
"""

# PDF tools
from .pdf_tools import (
    extract_pdf_text,
    extract_pdf_tables,
    get_pdf_metadata,
    get_pdf_form_fields,
    fill_pdf_form,
    merge_pdfs,
    split_pdf,
)

# DOCX tools
from .docx_tools import (
    extract_docx_text,
    extract_docx_with_changes,
    get_docx_comments,
    get_docx_structure,
    add_docx_comment,
    create_docx,
    apply_tracked_changes,
)

# XLSX tools
from .xlsx_tools import (
    get_sheet_names,
    read_sheet,
    get_formulas,
    analyze_data,
    write_cell,
    add_formula,
    recalculate_formulas,
)

# Approval-enabled tools (show diff + Y/N prompt before changes)
from .approval_tools import (
    replace_docx_text,
    insert_docx_text,
    delete_docx_text,
    update_xlsx_cell,
    add_xlsx_formula,
    update_xlsx_range,
    APPROVAL_TOOLS,
    reset_approval_state,
    set_workspace_root,
)

# All tools for easy import (read-only + direct write)
ALL_TOOLS = [
    # PDF (7 tools)
    extract_pdf_text,
    extract_pdf_tables,
    get_pdf_metadata,
    get_pdf_form_fields,
    fill_pdf_form,
    merge_pdfs,
    split_pdf,
    # DOCX (7 tools)
    extract_docx_text,
    extract_docx_with_changes,
    get_docx_comments,
    get_docx_structure,
    add_docx_comment,
    create_docx,
    apply_tracked_changes,
    # XLSX (7 tools)
    get_sheet_names,
    read_sheet,
    get_formulas,
    analyze_data,
    write_cell,
    add_formula,
    recalculate_formulas,
]

# Tools with approval flow (diff preview + Y/N confirmation)
# Use these instead of direct write tools when user control is needed
ALL_TOOLS_WITH_APPROVAL = [
    # PDF (7 tools) - read-only, no approval needed
    extract_pdf_text,
    extract_pdf_tables,
    get_pdf_metadata,
    get_pdf_form_fields,
    fill_pdf_form,
    merge_pdfs,
    split_pdf,
    # DOCX read (4 tools)
    extract_docx_text,
    extract_docx_with_changes,
    get_docx_comments,
    get_docx_structure,
    # DOCX write with approval (3 tools)
    replace_docx_text,
    insert_docx_text,
    delete_docx_text,
    # XLSX read (4 tools)
    get_sheet_names,
    read_sheet,
    get_formulas,
    analyze_data,
    # XLSX write with approval (3 tools)
    update_xlsx_cell,
    add_xlsx_formula,
    update_xlsx_range,
]

__all__ = [
    # PDF
    "extract_pdf_text",
    "extract_pdf_tables",
    "get_pdf_metadata",
    "get_pdf_form_fields",
    "fill_pdf_form",
    "merge_pdfs",
    "split_pdf",
    # DOCX
    "extract_docx_text",
    "extract_docx_with_changes",
    "get_docx_comments",
    "get_docx_structure",
    "add_docx_comment",
    "create_docx",
    "apply_tracked_changes",
    # XLSX
    "get_sheet_names",
    "read_sheet",
    "get_formulas",
    "analyze_data",
    "write_cell",
    "add_formula",
    "recalculate_formulas",
    # Approval tools
    "replace_docx_text",
    "insert_docx_text",
    "delete_docx_text",
    "update_xlsx_cell",
    "add_xlsx_formula",
    "update_xlsx_range",
    "APPROVAL_TOOLS",
    "reset_approval_state",
    "set_workspace_root",
    # Collections
    "ALL_TOOLS",
    "ALL_TOOLS_WITH_APPROVAL",
]
