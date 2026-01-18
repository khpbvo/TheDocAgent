"""PDF document analysis and modification tools.

Wraps existing skills/pdf/ utilities for use with OpenAI Agents SDK.
"""

import json
import sys
import tempfile
from pathlib import Path

from agents import function_tool

from .output_utils import truncate_json_output, truncate_output

# Add skills directory to path for imports
SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"
sys.path.insert(0, str(SKILLS_DIR / "pdf" / "scripts"))


@function_tool
def extract_pdf_text(
    file_path: str,
    page_numbers_json: str | None = None,
    start_page: int | None = None,
    max_pages: int | None = None,
) -> str:
    """Extract text content from a PDF file.

    For large PDFs, use start_page and max_pages for pagination, or use
    search_pdf_text() to find specific content first.

    Args:
        file_path: Path to the PDF file to analyze.
        page_numbers_json: Optional JSON array of specific page numbers to extract (1-indexed).
                           Example: '[1, 2, 5]'. If not provided, extracts sequentially.
        start_page: Starting page number for pagination (1-indexed, default: 1).
                    Use this with max_pages to paginate through large documents.
        max_pages: Maximum number of pages to extract (default: all).
                   Useful for limiting output size on large documents.

    Returns:
        Extracted text content from the PDF, organized by page.
    """
    import pdfplumber

    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    if path.suffix.lower() != ".pdf":
        return f"Error: Not a PDF file: {file_path}"

    # Parse page numbers if provided
    page_numbers = None
    if page_numbers_json:
        try:
            page_numbers = json.loads(page_numbers_json)
        except json.JSONDecodeError:
            return f"Error: Invalid JSON for page_numbers: {page_numbers_json}"

    try:
        text_content = []
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

            # Determine which pages to process
            if page_numbers:
                # Explicit page list takes priority
                pages_to_process = page_numbers
            else:
                # Use pagination parameters
                start = start_page if start_page else 1
                end = total_pages + 1
                if max_pages:
                    end = min(start + max_pages, total_pages + 1)
                pages_to_process = list(range(start, end))

            for page_num in pages_to_process:
                if 1 <= page_num <= total_pages:
                    page = pdf.pages[page_num - 1]
                    text = page.extract_text()
                    if text:
                        text_content.append(f"=== Page {page_num} ===\n{text}")
                else:
                    text_content.append(
                        f"=== Page {page_num} === (invalid page number)"
                    )

        # Add pagination info to help agent navigate
        pagination_info = (
            f"[Showing pages {pages_to_process[0]}-{pages_to_process[-1]} of {total_pages} total]"
            if pages_to_process
            else ""
        )

        result = (
            f"{pagination_info}\n\n" + "\n\n".join(text_content)
            if text_content
            else "No text content found in PDF."
        )
        return truncate_output(result)
    except Exception as e:
        return f"Error extracting PDF text: {e!s}"


@function_tool
def extract_pdf_tables(file_path: str, page_number: int | None = None) -> str:
    """Extract tables from a PDF file as structured data.

    Args:
        file_path: Path to the PDF file.
        page_number: Optional specific page number to extract tables from (1-indexed).
                     If not provided, extracts tables from all pages.

    Returns:
        JSON string containing extracted tables with their page numbers.
    """
    import pdfplumber

    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    try:
        all_tables = []
        with pdfplumber.open(file_path) as pdf:
            pages_to_process = (
                [page_number] if page_number else list(range(1, len(pdf.pages) + 1))
            )

            for page_num in pages_to_process:
                if 1 <= page_num <= len(pdf.pages):
                    page = pdf.pages[page_num - 1]
                    tables = page.extract_tables()
                    for i, table in enumerate(tables):
                        if table:
                            all_tables.append(
                                {
                                    "page": page_num,
                                    "table_index": i + 1,
                                    "rows": len(table),
                                    "columns": len(table[0]) if table else 0,
                                    "data": table,
                                }
                            )

        if not all_tables:
            return "No tables found in PDF."

        return truncate_json_output(json.dumps(all_tables, indent=2))
    except Exception as e:
        return f"Error extracting PDF tables: {e!s}"


@function_tool
def get_pdf_metadata(file_path: str) -> str:
    """Get metadata from a PDF file (title, author, creation date, page count).

    Args:
        file_path: Path to the PDF file.

    Returns:
        JSON string containing PDF metadata.
    """
    from pypdf import PdfReader

    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    try:
        reader = PdfReader(file_path)
        meta = reader.metadata

        metadata = {
            "title": meta.title if meta else None,
            "author": meta.author if meta else None,
            "subject": meta.subject if meta else None,
            "creator": meta.creator if meta else None,
            "producer": meta.producer if meta else None,
            "creation_date": (
                str(meta.creation_date) if meta and meta.creation_date else None
            ),
            "modification_date": (
                str(meta.modification_date) if meta and meta.modification_date else None
            ),
            "page_count": len(reader.pages),
        }

        return json.dumps(metadata, indent=2, default=str)
    except Exception as e:
        return f"Error getting PDF metadata: {e!s}"


@function_tool
def get_pdf_form_fields(file_path: str) -> str:
    """Extract fillable form field information from a PDF.

    Uses skills/pdf/scripts/extract_form_field_info.py

    Args:
        file_path: Path to the PDF file.

    Returns:
        JSON string containing form field definitions (field names, types, pages, values).
    """
    from pypdf import PdfReader

    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    try:
        # Import from existing skill
        from extract_form_field_info import get_field_info

        reader = PdfReader(file_path)
        fields = get_field_info(reader)

        if not fields:
            return "No fillable form fields found in PDF."

        return json.dumps(fields, indent=2)
    except ImportError:
        # Fallback if skill not available
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        fields = reader.get_fields()

        if not fields:
            return "No fillable form fields found in PDF."

        field_info = []
        for field_name, field_data in fields.items():
            info = {
                "name": field_name,
                "type": str(field_data.get("/FT", "unknown")),
                "value": str(field_data.get("/V", "")),
            }
            field_info.append(info)

        return json.dumps(field_info, indent=2)
    except Exception as e:
        return f"Error extracting form fields: {e!s}"


@function_tool
def fill_pdf_form(file_path: str, field_values_json: str, output_path: str) -> str:
    """Fill PDF form fields with specified values.

    Uses skills/pdf/scripts/fill_fillable_fields.py

    Args:
        file_path: Path to the PDF with form fields.
        field_values_json: JSON string mapping field_id to value.
                           Example: '{"name": "John", "date": "2024-01-01"}'
        output_path: Where to save the filled PDF.

    Returns:
        Success message with output path, or error message.
    """
    from pypdf import PdfReader

    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    try:
        # Parse the JSON string
        field_values = json.loads(field_values_json)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON for field_values: {e!s}"

    try:
        # Get field info to map field names to pages
        from extract_form_field_info import get_field_info

        reader = PdfReader(file_path)
        existing_fields = get_field_info(reader)
        fields_by_id = {f["field_id"]: f for f in existing_fields}

        # Validate field IDs
        invalid_fields = [fid for fid in field_values.keys() if fid not in fields_by_id]
        if invalid_fields:
            return f"Error: Invalid field IDs: {invalid_fields}. Valid IDs: {list(fields_by_id.keys())}"

        # Create fields list with page info
        fields_to_fill = []
        for field_id, value in field_values.items():
            field_info = fields_by_id[field_id]
            fields_to_fill.append(
                {
                    "field_id": field_id,
                    "page": field_info["page"],
                    "value": value,
                }
            )

        # Write to temp JSON file and use existing skill
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(fields_to_fill, tmp)
            tmp_path = tmp.name

        try:
            # Apply monkeypatch for pypdf bug
            from fill_fillable_fields import fill_pdf_fields, monkeypatch_pydpf_method

            monkeypatch_pydpf_method()
            fill_pdf_fields(file_path, tmp_path, output_path)
        finally:
            Path(tmp_path).unlink()

        return f"Successfully filled PDF form. Output saved to: {output_path}"
    except Exception as e:
        return f"Error filling PDF form: {e!s}"


@function_tool
def merge_pdfs(file_paths_json: str, output_path: str) -> str:
    """Merge multiple PDF files into one.

    Args:
        file_paths_json: JSON array of paths to PDF files to merge (in order).
                         Example: '["/path/to/file1.pdf", "/path/to/file2.pdf"]'
        output_path: Where to save the merged PDF.

    Returns:
        Success message with page counts, or error message.
    """
    from pypdf import PdfReader, PdfWriter

    try:
        file_paths = json.loads(file_paths_json)
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON for file_paths: {e!s}"

    # Validate all files exist
    for fp in file_paths:
        if not Path(fp).exists():
            return f"Error: File not found: {fp}"

    try:
        writer = PdfWriter()
        page_counts = []

        for pdf_file in file_paths:
            reader = PdfReader(pdf_file)
            page_counts.append(len(reader.pages))
            for page in reader.pages:
                writer.add_page(page)

        with open(output_path, "wb") as output:
            writer.write(output)

        total_pages = sum(page_counts)
        details = ", ".join(
            f"{Path(fp).name}: {pc} pages" for fp, pc in zip(file_paths, page_counts)
        )
        return f"Successfully merged {len(file_paths)} PDFs ({total_pages} total pages). {details}. Output: {output_path}"
    except Exception as e:
        return f"Error merging PDFs: {e!s}"


@function_tool
def split_pdf(file_path: str, output_dir: str) -> str:
    """Split a PDF into individual page files.

    Args:
        file_path: Path to the PDF to split.
        output_dir: Directory to save individual page PDFs.

    Returns:
        Success message with number of pages created, or error message.
    """
    from pypdf import PdfReader, PdfWriter

    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        reader = PdfReader(file_path)
        base_name = path.stem
        created_files = []

        for i, page in enumerate(reader.pages):
            writer = PdfWriter()
            writer.add_page(page)
            output_file = out_dir / f"{base_name}_page_{i + 1}.pdf"
            with open(output_file, "wb") as output:
                writer.write(output)
            created_files.append(str(output_file))

        return f"Successfully split PDF into {len(created_files)} pages in {output_dir}"
    except Exception as e:
        return f"Error splitting PDF: {e!s}"


@function_tool
def search_pdf_text(
    file_path: str,
    query: str,
    case_sensitive: bool = False,
    context_chars: int = 100,
    max_results: int = 20,
) -> str:
    """Search for text within a PDF and return matching pages with context.

    Use this to find specific content in large PDFs before extracting full pages.
    Returns page numbers and surrounding context for each match.

    Args:
        file_path: Path to the PDF file to search.
        query: Text to search for in the PDF.
        case_sensitive: Whether the search should be case-sensitive (default: False).
        context_chars: Number of characters to show around each match (default: 100).
        max_results: Maximum number of results to return (default: 20).

    Returns:
        JSON with matching pages, match counts, and context snippets.
        Use the page numbers with extract_pdf_text(page_numbers_json='[...]') to get full content.
    """
    import pdfplumber

    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    if path.suffix.lower() != ".pdf":
        return f"Error: Not a PDF file: {file_path}"

    if not query or not query.strip():
        return "Error: Search query cannot be empty."

    try:
        results = []
        total_matches = 0
        pages_with_matches = set()

        search_query = query if case_sensitive else query.lower()

        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    continue

                search_text = text if case_sensitive else text.lower()

                # Find all matches on this page
                start_pos = 0
                page_matches = []
                while True:
                    pos = search_text.find(search_query, start_pos)
                    if pos == -1:
                        break

                    total_matches += 1
                    pages_with_matches.add(page_num)

                    # Extract context around the match
                    context_start = max(0, pos - context_chars)
                    context_end = min(len(text), pos + len(query) + context_chars)
                    context = text[context_start:context_end]

                    # Add ellipsis if truncated
                    if context_start > 0:
                        context = "..." + context
                    if context_end < len(text):
                        context = context + "..."

                    if len(results) < max_results:
                        page_matches.append(
                            {
                                "position": pos,
                                "context": context.replace("\n", " ").strip(),
                            }
                        )

                    start_pos = pos + 1

                if page_matches:
                    results.append(
                        {
                            "page": page_num,
                            "match_count": len(page_matches),
                            "matches": page_matches[:5],  # Limit matches per page
                        }
                    )

        if not results:
            return f"No matches found for '{query}' in the PDF ({total_pages} pages searched)."

        output = {
            "query": query,
            "total_matches": total_matches,
            "pages_with_matches": sorted(pages_with_matches),
            "total_pages": total_pages,
            "results": results[:max_results],
            "tip": "Use extract_pdf_text(page_numbers_json='[...]') with these page numbers to get full content.",
        }

        return json.dumps(output, indent=2)
    except Exception as e:
        return f"Error searching PDF: {e!s}"
