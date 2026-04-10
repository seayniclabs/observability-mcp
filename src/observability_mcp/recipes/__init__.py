"""Recipe modules — each one exposes one or more no-input MCP tools.

A recipe is a Python async function that takes no arguments, runs a hardcoded
Flux query against InfluxDB, and returns a clean human-readable string. The
no-input convention is critical: local LLMs (qwen, llama) cannot reliably
format structured tool inputs in ReAct text prompting, so we give them a menu
of named recipes instead of a generic query tool.

To add a recipe:
1. Create a new module in this directory (or add to an existing one)
2. Define an `async def get_*` function that takes no arguments
3. Register it in `observability_mcp.server` via `mcp.tool()(your_function)`
"""
