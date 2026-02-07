"""Document analysis and modification tools for the Document Analyzer Agent.

Exports all tools from pdf_tools, docx_tools, and xlsx_tools modules.
Also exports approval-enabled tools that show diffs before applying changes.
"""

# PDF tools
# Approval-enabled tools (show diff + Y/N prompt before changes)
from .approval_tools import (
    APPROVAL_TOOLS,
    add_xlsx_formula,
    delete_docx_text,
    insert_docx_text,
    replace_docx_text,
    reset_approval_state,
    set_workspace_root,
    update_xlsx_cell,
    update_xlsx_range,
)

# DOCX tools
from .docx_tools import (
    add_docx_comment,
    apply_tracked_changes,
    create_docx,
    extract_docx_text,
    extract_docx_with_changes,
    get_docx_comments,
    get_docx_structure,
    search_docx_text,
)
from .directed_search_tools import directed_search_document, retrieve_document_segments
from .pdf_tools import (
    extract_pdf_tables,
    extract_pdf_text,
    fill_pdf_form,
    get_pdf_form_fields,
    get_pdf_metadata,
    merge_pdfs,
    search_pdf_text,
    split_pdf,
)

# XLSX tools
from .xlsx_tools import (
    add_formula,
    analyze_data,
    get_formulas,
    get_sheet_names,
    read_sheet,
    recalculate_formulas,
    search_sheet,
    write_cell,
)

# All tools for easy import (read-only + direct write)
ALL_TOOLS = [
    # PDF (8 tools + directed search retrieval)
    extract_pdf_text,
    extract_pdf_tables,
    get_pdf_metadata,
    get_pdf_form_fields,
    fill_pdf_form,
    merge_pdfs,
    split_pdf,
    search_pdf_text,
    directed_search_document,
    retrieve_document_segments,
    # DOCX (8 tools)
    extract_docx_text,
    extract_docx_with_changes,
    get_docx_comments,
    get_docx_structure,
    add_docx_comment,
    create_docx,
    apply_tracked_changes,
    search_docx_text,
    # XLSX (8 tools)
    get_sheet_names,
    read_sheet,
    get_formulas,
    analyze_data,
    write_cell,
    add_formula,
    recalculate_formulas,
    search_sheet,
]

# Tools with approval flow (diff preview + Y/N confirmation)
# Use these instead of direct write tools when user control is needed
ALL_TOOLS_WITH_APPROVAL = [
    # PDF (8 tools + directed search retrieval) - read-only, no approval needed
    extract_pdf_text,
    extract_pdf_tables,
    get_pdf_metadata,
    get_pdf_form_fields,
    fill_pdf_form,
    merge_pdfs,
    split_pdf,
    search_pdf_text,
    directed_search_document,
    retrieve_document_segments,
    # DOCX read (5 tools)
    extract_docx_text,
    extract_docx_with_changes,
    get_docx_comments,
    get_docx_structure,
    search_docx_text,
    # DOCX write with approval (3 tools)
    replace_docx_text,
    insert_docx_text,
    delete_docx_text,
    # XLSX read (5 tools)
    get_sheet_names,
    read_sheet,
    get_formulas,
    analyze_data,
    search_sheet,
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
    "search_pdf_text",
    "directed_search_document",
    "retrieve_document_segments",
    # DOCX
    "extract_docx_text",
    "extract_docx_with_changes",
    "get_docx_comments",
    "get_docx_structure",
    "add_docx_comment",
    "create_docx",
    "apply_tracked_changes",
    "search_docx_text",
    # XLSX
    "get_sheet_names",
    "read_sheet",
    "get_formulas",
    "analyze_data",
    "write_cell",
    "add_formula",
    "recalculate_formulas",
    "search_sheet",
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
