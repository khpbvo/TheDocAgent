"""DOCX document analysis and modification tools.

Wraps existing skills/docx/ utilities for use with OpenAI Agents SDK.
"""

import json
import sys
import tempfile
import zipfile
from pathlib import Path

from agents import function_tool

from .output_utils import truncate_json_output, truncate_output

# Try to import pypandoc (handles pandoc binary location automatically)
try:
    import pypandoc

    PYPANDOC_AVAILABLE = True
except ImportError:
    PYPANDOC_AVAILABLE = False

# Add skills directory to path for imports
SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"
sys.path.insert(0, str(SKILLS_DIR / "docx" / "scripts"))
sys.path.insert(0, str(SKILLS_DIR / "docx" / "ooxml" / "scripts"))


@function_tool
def extract_docx_text(
    file_path: str,
    start_paragraph: int | None = None,
    max_paragraphs: int | None = None,
) -> str:
    """Extract plain text from a DOCX file using pandoc.

    Args:
        file_path: Path to the DOCX file.
        start_paragraph: Optional starting paragraph number (1-indexed) for
                         paginated extraction.
        max_paragraphs: Optional maximum number of paragraphs to return.

    Returns:
        Extracted text from the document.
        - If no paragraph range is provided, returns markdown via pandoc.
        - If range parameters are provided, returns paragraph-targeted plain text.
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    if path.suffix.lower() != ".docx":
        return f"Error: Not a DOCX file: {file_path}"

    try:
        # Paragraph-level extraction path for targeted retrieval in large documents
        if start_paragraph is not None or max_paragraphs is not None:
            from defusedxml import ElementTree as ET

            with zipfile.ZipFile(file_path, "r") as zf:
                document_xml = zf.read("word/document.xml")

            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            root = ET.fromstring(document_xml)

            paragraphs = []
            for para in root.findall(".//w:p", ns):
                text_elements = para.findall(".//w:t", ns)
                para_text = "".join(t.text or "" for t in text_elements).strip()
                if para_text:
                    paragraphs.append(para_text)

            if not paragraphs:
                return "No text content found in document."

            start = start_paragraph if start_paragraph and start_paragraph > 0 else 1
            if start > len(paragraphs):
                return f"Error: start_paragraph {start} is beyond document length ({len(paragraphs)} paragraphs)."

            if max_paragraphs is not None and max_paragraphs <= 0:
                return "Error: max_paragraphs must be a positive integer."

            end = len(paragraphs) + 1
            if max_paragraphs:
                end = min(start + max_paragraphs, len(paragraphs) + 1)

            selected = []
            for para_num in range(start, end):
                para_text = paragraphs[para_num - 1]
                selected.append(f"=== Paragraph {para_num} ===\n{para_text}")

            pagination_info = (
                f"[Showing paragraphs {start}-{end - 1} of {len(paragraphs)} total]"
            )
            return truncate_output(f"{pagination_info}\n\n" + "\n\n".join(selected))

        if PYPANDOC_AVAILABLE:
            # Use pypandoc which handles finding pandoc automatically
            content = pypandoc.convert_file(str(path), "markdown")
            if content.strip():
                return truncate_output(content)
            return "No text content found in document."
        return "Error: pypandoc not installed. Run: pip install pypandoc_binary"
    except Exception as e:
        return f"Error extracting DOCX text: {e!s}"


@function_tool
def extract_docx_with_changes(file_path: str) -> str:
    """Extract text from a DOCX file including tracked changes (insertions and deletions).

    Uses pandoc with --track-changes=all to show changes inline.

    Args:
        file_path: Path to the DOCX file.

    Returns:
        Markdown text showing tracked changes:
        - Insertions marked with {++text++}
        - Deletions marked with {--text--}
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    try:
        if PYPANDOC_AVAILABLE:
            # Use pypandoc with track-changes option
            content = pypandoc.convert_file(
                str(path), "markdown", extra_args=["--track-changes=all"]
            )
            if content.strip():
                return truncate_output(content)
            return "No text content found in document."
        return "Error: pypandoc not installed. Run: pip install pypandoc_binary"
    except Exception as e:
        return f"Error extracting DOCX with tracked changes: {e!s}"


@function_tool
def get_docx_comments(file_path: str) -> str:
    """Extract comments from a DOCX file.

    Args:
        file_path: Path to the DOCX file.

    Returns:
        JSON string containing comments with id, author, date, and text.
    """
    from defusedxml import ElementTree as ET

    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            if "word/comments.xml" not in zf.namelist():
                return "No comments found in document."

            comments_xml = zf.read("word/comments.xml")

        # Parse XML
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        root = ET.fromstring(comments_xml)

        comments = []
        for comment in root.findall(".//w:comment", ns):
            comment_id = comment.get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id"
            )
            author = comment.get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}author"
            )
            date = comment.get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}date"
            )

            # Extract text from all w:t elements
            text_elements = comment.findall(".//w:t", ns)
            text = "".join(t.text or "" for t in text_elements)

            comments.append(
                {"id": comment_id, "author": author, "date": date, "text": text}
            )

        if not comments:
            return "No comments found in document."

        return json.dumps(comments, indent=2)
    except Exception as e:
        return f"Error extracting comments: {e!s}"


@function_tool
def get_docx_structure(file_path: str) -> str:
    """Get the structure of a DOCX file (headings and sections outline).

    Args:
        file_path: Path to the DOCX file.

    Returns:
        Outline of the document structure showing headings with their levels.
    """
    from defusedxml import ElementTree as ET

    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            document_xml = zf.read("word/document.xml")

        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        root = ET.fromstring(document_xml)

        structure = []
        for para in root.findall(".//w:p", ns):
            # Check for heading style
            pPr = para.find("w:pPr", ns)
            if pPr is not None:
                pStyle = pPr.find("w:pStyle", ns)
                if pStyle is not None:
                    style = pStyle.get(
                        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val",
                        "",
                    )
                    if style.startswith("Heading"):
                        # Extract text
                        text_elements = para.findall(".//w:t", ns)
                        text = "".join(t.text or "" for t in text_elements)
                        if text.strip():
                            level = style.replace("Heading", "")
                            indent = "  " * (int(level) - 1 if level.isdigit() else 0)
                            structure.append(f"{indent}{style}: {text}")

        if not structure:
            return "No heading structure found in document."

        return "\n".join(structure)
    except Exception as e:
        return f"Error getting document structure: {e!s}"


@function_tool
def add_docx_comment(
    file_path: str, search_text: str, comment_text: str, output_path: str
) -> str:
    """Add a comment to text in a Word document.

    Uses skills/docx/scripts/document.py Document class.

    Args:
        file_path: Path to the DOCX file.
        search_text: Text to search for and attach the comment to.
        comment_text: The comment text to add.
        output_path: Where to save the modified document.

    Returns:
        Success message or error.
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    try:
        # Import existing skill classes
        from document import Document
        from unpack import unpack_file

        # Create temp directory for unpacked content
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Unpack the docx
            unpack_file(file_path, tmp_dir)

            # Create Document instance
            doc = Document(tmp_dir, track_revisions=True, author="Document Analyzer")

            # Find the text node
            editor = doc["word/document.xml"]
            node = editor.get_node(contains=search_text)

            if node is None:
                return f"Error: Could not find text '{search_text}' in document."

            # Add comment
            comment_id = doc.add_comment(node, node, comment_text)

            # Save
            doc.save()

            # Pack back to docx
            from pack import pack_file

            pack_file(tmp_dir, output_path)

        return f"Successfully added comment (ID: {comment_id}) to document. Saved to: {output_path}"
    except ImportError as e:
        return f"Error: Required skill module not found: {e}. Make sure skills/docx/ is properly set up."
    except Exception as e:
        return f"Error adding comment: {e!s}"


@function_tool
def create_docx(content: str, output_path: str, title: str | None = None) -> str:
    """Create a new Word document with the given content.

    Creates a simple document with the provided text content.
    For complex formatting, use the docx-js approach from skills/docx/docx-js.md.

    Args:
        content: Text content to put in the document (can include markdown-style headers with #).
        output_path: Where to save the new document.
        title: Optional document title.

    Returns:
        Success message or error.
    """
    try:
        if not PYPANDOC_AVAILABLE:
            return "Error: pypandoc not installed. Run: pip install pypandoc_binary"

        # Prepare content with optional title
        full_content = content
        if title:
            full_content = f"# {title}\n\n{content}"

        # Use pypandoc to convert markdown to docx
        pypandoc.convert_text(
            full_content, "docx", format="markdown", outputfile=output_path
        )

        return f"Successfully created document at: {output_path}"
    except Exception as e:
        return f"Error creating DOCX: {e!s}"


@function_tool
def apply_tracked_changes(
    file_path: str, search_text: str, replacement_text: str, output_path: str
) -> str:
    """Apply a tracked change (redline edit) to a Word document.

    Uses skills/docx/scripts/document.py for tracked changes workflow.

    Args:
        file_path: Path to the DOCX file.
        search_text: Text to find and mark for deletion.
        replacement_text: New text to insert (as tracked insertion).
        output_path: Where to save the modified document.

    Returns:
        Success message or error.
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    try:
        # Import existing skill classes
        from document import Document
        from unpack import unpack_file

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Unpack
            unpack_file(file_path, tmp_dir)

            # Create Document with tracked revisions enabled
            doc = Document(tmp_dir, track_revisions=True, author="Document Analyzer")

            # Find the text node
            editor = doc["word/document.xml"]
            node = editor.get_node(contains=search_text)

            if node is None:
                return f"Error: Could not find text '{search_text}' in document."

            # Apply tracked deletion and insertion
            editor.suggest_deletion(node)

            # Create insertion with new text
            new_xml = f'<w:ins w:author="Document Analyzer"><w:r><w:t>{replacement_text}</w:t></w:r></w:ins>'
            editor.insert_after(node, new_xml)

            # Save
            doc.save()

            # Pack
            from pack import pack_file

            pack_file(tmp_dir, output_path)

        return f"Successfully applied tracked change. '{search_text}' → '{replacement_text}'. Saved to: {output_path}"
    except ImportError as e:
        return f"Error: Required skill module not found: {e}."
    except Exception as e:
        return f"Error applying tracked changes: {e!s}"


@function_tool
def search_docx_text(
    file_path: str,
    query: str,
    case_sensitive: bool = False,
    context_chars: int = 100,
    max_results: int = 20,
) -> str:
    """Search for text within a DOCX document and return matching paragraphs with context.

    Use this to find specific content in large documents before extracting full text.
    Returns paragraph numbers and surrounding context for each match.

    Args:
        file_path: Path to the DOCX file to search.
        query: Text to search for in the document.
        case_sensitive: Whether the search should be case-sensitive (default: False).
        context_chars: Number of characters to show around each match (default: 100).
        max_results: Maximum number of results to return (default: 20).

    Returns:
        JSON with matching paragraphs, match counts, and context snippets.
    """
    from defusedxml import ElementTree as ET

    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    if path.suffix.lower() != ".docx":
        return f"Error: Not a DOCX file: {file_path}"

    if not query or not query.strip():
        return "Error: Search query cannot be empty."

    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            document_xml = zf.read("word/document.xml")

        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        root = ET.fromstring(document_xml)

        results = []
        total_matches = 0
        search_query = query if case_sensitive else query.lower()

        # Extract all paragraphs
        paragraphs = []
        for para in root.findall(".//w:p", ns):
            text_elements = para.findall(".//w:t", ns)
            para_text = "".join(t.text or "" for t in text_elements)
            if para_text.strip():
                paragraphs.append(para_text)

        # Search through paragraphs
        for para_num, para_text in enumerate(paragraphs, 1):
            search_text = para_text if case_sensitive else para_text.lower()

            # Find all matches in this paragraph
            start_pos = 0
            para_matches = []
            while True:
                pos = search_text.find(search_query, start_pos)
                if pos == -1:
                    break

                total_matches += 1

                # Extract context around the match
                context_start = max(0, pos - context_chars)
                context_end = min(len(para_text), pos + len(query) + context_chars)
                context = para_text[context_start:context_end]

                # Add ellipsis if truncated
                if context_start > 0:
                    context = "..." + context
                if context_end < len(para_text):
                    context = context + "..."

                para_matches.append(
                    {
                        "position": pos,
                        "context": context.replace("\n", " ").strip(),
                    }
                )

                start_pos = pos + 1

            if para_matches and len(results) < max_results:
                results.append(
                    {
                        "paragraph": para_num,
                        "match_count": len(para_matches),
                        "matches": para_matches[:5],  # Limit matches per paragraph
                    }
                )

        if not results:
            return f"No matches found for '{query}' in the document ({len(paragraphs)} paragraphs searched)."

        output = {
            "query": query,
            "total_matches": total_matches,
            "paragraphs_with_matches": len(results),
            "total_paragraphs": len(paragraphs),
            "results": results,
            "tip": "Use extract_docx_text(start_paragraph=N, max_paragraphs=M) for targeted retrieval, or use retrieve_document_segments() with selectors from directed_search_document().",
        }

        return truncate_json_output(json.dumps(output, indent=2))
    except Exception as e:
        return f"Error searching DOCX: {e!s}"
