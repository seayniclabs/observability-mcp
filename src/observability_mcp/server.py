"""observability-mcp FastMCP server entrypoint.

Exposes Telegraf/InfluxDB recipe tools as a stdio MCP server. Designed to be
launched by an MCP client (Hermes Agent, Claude Code, Cursor, etc.) and
spoken to over stdin/stdout.

Configuration via environment variables — see README.md for details.
"""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

from observability_mcp import __version__
from observability_mcp.influx import InfluxConfigError, _config
from observability_mcp.recipes.containers import get_top_cpu_containers
from observability_mcp.recipes.disk import get_lab_disk_pct
from observability_mcp.recipes.docker import get_container_count, get_top_memory_containers
from observability_mcp.recipes.load import get_lab_load1, get_lab_load_history_24h
from observability_mcp.recipes.memory import get_lab_memory_pct

# FastMCP instance — name shows up in client tool listings
mcp = FastMCP("observability-mcp")

# Register recipes as MCP tools.
# Each tool is a no-input async function that runs a hardcoded Flux query.
# To add a new recipe: write the function in src/observability_mcp/recipes/,
# then register it here with mcp.tool()(your_function).
mcp.tool()(get_lab_load1)
mcp.tool()(get_lab_load_history_24h)
mcp.tool()(get_lab_memory_pct)
mcp.tool()(get_top_cpu_containers)
mcp.tool()(get_lab_disk_pct)
mcp.tool()(get_container_count)
mcp.tool()(get_top_memory_containers)


def main() -> None:
    """Entrypoint for the `observability-mcp` console script.

    Validates configuration before starting the MCP server, so that
    misconfiguration produces a clear error rather than a runtime tool
    failure during the first query.
    """
    # Validate config eagerly so errors are visible at startup, not at
    # first tool call.
    try:
        _config()
    except InfluxConfigError as e:
        print(f"observability-mcp v{__version__} — startup failed:", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Required environment variables:", file=sys.stderr)
        print("  INFLUXDB_URL          (default: http://localhost:8086)", file=sys.stderr)
        print("  INFLUXDB_ORG          (required: organization ID)", file=sys.stderr)
        print("  INFLUXDB_TOKEN_FILE   (preferred: path to read-only token)", file=sys.stderr)
        print("  INFLUXDB_TOKEN        (alternative: token as env var)", file=sys.stderr)
        print("  INFLUXDB_BUCKET_METRICS (default: telegraf)", file=sys.stderr)
        sys.exit(2)

    # Run the stdio MCP server (blocks until client disconnects)
    mcp.run()


if __name__ == "__main__":
    main()
