"""Utilities for managing tool output sizes.

Provides truncation functionality to prevent context window overflow
when tools return large amounts of data (e.g., full PDF text, large tables).
"""

# Maximum characters for tool output to prevent context window overflow
# This leaves room for conversation history and model responses
MAX_TOOL_OUTPUT_CHARS = 50_000


def truncate_output(
    output: str,
    max_chars: int = MAX_TOOL_OUTPUT_CHARS,
    suffix: str | None = None,
) -> str:
    """Truncate tool output to prevent context window overflow.

    Args:
        output: The output string to potentially truncate.
        max_chars: Maximum number of characters allowed.
        suffix: Custom suffix to append when truncating. If None, uses a default
                that shows the truncation info.

    Returns:
        The original output if within limits, or truncated with suffix.

    Example:
        >>> text = "a" * 60000
        >>> result = truncate_output(text)
        >>> len(result) < 60000
        True
        >>> "TRUNCATED" in result
        True
    """
    if len(output) <= max_chars:
        return output

    truncated_chars = len(output) - max_chars
    if suffix is None:
        suffix = (
            f"\n\n... [OUTPUT TRUNCATED: {truncated_chars:,} more characters. "
            f"Total was {len(output):,} chars, showing first {max_chars:,}. "
            "Use specific page/row filters to reduce output size.]"
        )

    # Reserve space for the suffix, ensuring at least 100 chars of content
    content_limit = max(max_chars - len(suffix), 100)

    return output[:content_limit] + suffix


def truncate_json_output(
    json_str: str,
    max_chars: int = MAX_TOOL_OUTPUT_CHARS,
) -> str:
    """Truncate JSON output while keeping it valid if possible.

    For large JSON arrays, tries to truncate cleanly at array boundaries.
    Falls back to simple truncation if JSON structure can't be preserved.

    Args:
        json_str: JSON string to potentially truncate.
        max_chars: Maximum number of characters allowed.

    Returns:
        The original JSON if within limits, or truncated with note.
    """
    import json

    if len(json_str) <= max_chars:
        return json_str

    # Try to parse and truncate intelligently
    try:
        data = json.loads(json_str)

        # If it's a list, truncate the list
        if isinstance(data, list):
            original_count = len(data)
            # Binary search for how many items fit
            lo, hi = 0, len(data)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                test = json.dumps(data[:mid], indent=2)
                if len(test) <= max_chars - 100:  # Leave room for note
                    lo = mid
                else:
                    hi = mid - 1

            if lo > 0:
                truncated = data[:lo]
                note = f"\n... [Showing {lo} of {original_count} items. Use filters to see more.]"
                return json.dumps(truncated, indent=2) + note

        # If it's a dict with a 'data' key that's a list
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            original_count = len(data["data"])
            lo, hi = 0, len(data["data"])
            while lo < hi:
                mid = (lo + hi + 1) // 2
                test_data = dict(data)
                test_data["data"] = data["data"][:mid]
                test_data["truncated"] = True
                test_data["showing"] = mid
                test_data["total"] = original_count
                test = json.dumps(test_data, indent=2)
                if len(test) <= max_chars:
                    lo = mid
                else:
                    hi = mid - 1

            if lo > 0:
                truncated_data = dict(data)
                truncated_data["data"] = data["data"][:lo]
                truncated_data["truncated"] = True
                truncated_data["showing"] = lo
                truncated_data["total"] = original_count
                return json.dumps(truncated_data, indent=2)

    except (json.JSONDecodeError, TypeError, KeyError):
        pass

    # Fallback to simple truncation
    return truncate_output(json_str, max_chars)
