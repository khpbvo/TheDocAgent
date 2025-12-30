"""DOCX document analysis and modification tools.

Wraps existing skills/docx/ utilities for use with OpenAI Agents SDK.
"""

import json
import sys
import tempfile
import zipfile
from pathlib import Path

from agents import function_tool

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
def extract_docx_text(file_path: str) -> str:
    """Extract plain text from a DOCX file using pandoc.

    Args:
        file_path: Path to the DOCX file.

    Returns:
        Extracted text content from the document as markdown.
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    if path.suffix.lower() != ".docx":
        return f"Error: Not a DOCX file: {file_path}"

    try:
        if PYPANDOC_AVAILABLE:
            # Use pypandoc which handles finding pandoc automatically
            content = pypandoc.convert_file(str(path), "markdown")
            return content if content.strip() else "No text content found in document."
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
            return content if content.strip() else "No text content found in document."
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
