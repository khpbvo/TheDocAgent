"""Document Analyzer Agent configuration.

Configures the agent with instructions, model settings, and tools.
"""

from agents import Agent, ModelSettings, WebSearchTool
from agents.model_settings import Reasoning

from .tools import ALL_TOOLS, ALL_TOOLS_WITH_APPROVAL

# Tool sets with hosted tools (web search runs on OpenAI servers)
AGENT_TOOLS = [WebSearchTool(search_context_size="high")] + ALL_TOOLS
AGENT_TOOLS_WITH_APPROVAL = [WebSearchTool(search_context_size="high")] + ALL_TOOLS_WITH_APPROVAL

# Agent instructions
AGENT_INSTRUCTIONS = """You are a Document Analyzer Agent specialized in analyzing and modifying PDF, DOCX, and XLSX files.

## Your Capabilities

### PDF Documents (.pdf)
- Extract text from all or specific pages
- Extract tables as structured data
- Get metadata (title, author, page count)
- Read and fill form fields
- Merge multiple PDFs into one
- Split PDFs into individual pages

### Word Documents (.docx)
- Extract plain text
- Extract text with tracked changes visible
- Read comments with authors and dates
- Get document structure (heading outline)
- Add comments to specific text
- Create new documents
- Apply tracked changes (redlines)

### Excel Spreadsheets (.xlsx, .xlsm)
- List all sheets in a workbook
- Read sheet data
- Extract formulas
- Perform statistical analysis
- Write values to cells
- Add formulas
- Recalculate all formulas

### Filesystem (MCP)
- Browse directories and read/write files within the configured MCP filesystem root
- Ask before destructive actions like delete or move

### Web Search
- Search the internet for current information, pricing, regulations, company details
- Look up technical specifications, product information, or tender requirements
- Research market rates and compare against document contents

## Behavior Guidelines

1. **Explain your reasoning** before calling tools. Share what you're looking for and why.

2. **Announce tool calls** clearly - say which tool you're about to use and what you expect.

3. **Summarize findings** after extracting information. Don't just dump raw output.

4. **Handle errors gracefully** - if a tool fails, explain the issue and suggest alternatives.

5. **Ask clarifying questions** when the user's intent is unclear.

6. **Confirm output paths** when modifying documents - always tell the user where files will be saved.

## Response Format

When analyzing documents:
1. First, explain your analysis approach
2. Call the appropriate tools
3. Summarize the key findings
4. Offer relevant follow-up analyses or actions

When modifying documents:
1. Confirm what changes will be made
2. Use the approval-enabled tools (replace_docx_text, update_xlsx_cell, etc.)
3. The user will see a diff preview and can approve (Y) or reject (N)
4. Summarize what was changed after approval
"""


def create_agent(
    model: str = "gpt-4o",
    mcp_servers: list | None = None,
    approval_mode: bool = True,
) -> Agent:
    """Create and configure the Document Analyzer Agent.

    Args:
        model: The LLM model to use. Defaults to gpt-4o.
               For reasoning models like o1/o3, pass the model name directly.
        mcp_servers: Optional list of MCP servers to connect.
        approval_mode: If True, use tools that show diffs and ask for confirmation
                      before modifying documents. Default True.

    Returns:
        Configured Agent instance.
    """
    # Configure model settings
    model_settings = ModelSettings(
        temperature=0.7,  # Balanced creativity and consistency
    )
    
    tools = AGENT_TOOLS_WITH_APPROVAL if approval_mode else AGENT_TOOLS

    return Agent(
        name="Document Analyzer",
        instructions=AGENT_INSTRUCTIONS,
        model=model,
        model_settings=model_settings,
        tools=tools,
        mcp_servers=mcp_servers or [],
    )


def create_reasoning_agent(
    model: str = "gpt-5.1",
    mcp_servers: list | None = None,
    approval_mode: bool = True,
) -> Agent:
    """Create agent configured for reasoning models (o1, o3, gpt-5.1).

    Reasoning models have different parameter support and are better
    for complex multi-step document analysis.

    Args:
        model: The reasoning model to use (o1, o3, gpt-5.1).
        mcp_servers: Optional list of MCP servers to connect.
        approval_mode: If True, use tools that show diffs and ask for confirmation
                      before modifying documents. Default True.

    Returns:
        Configured Agent instance optimized for reasoning.
    """
    # Reasoning models typically don't use temperature
    # and have their own reasoning effort settings
    model_settings = ModelSettings(
        reasoning=Reasoning(effort="high", summary="concise"),
        verbosity="medium",
    )
    
    tools = AGENT_TOOLS_WITH_APPROVAL if approval_mode else AGENT_TOOLS
    
    return Agent(
        name="Document Analyzer",
        instructions=AGENT_INSTRUCTIONS,
        model=model,
        model_settings=model_settings,
        tools=tools,
        mcp_servers=mcp_servers or [],
    )
