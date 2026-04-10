# observability-mcp

> Read-only MCP server exposing Telegraf/InfluxDB lab metrics as no-input recipe tools. Built for [Hermes Agent](https://github.com/nousresearch/hermes-agent) and any MCP-compatible client (Claude Code, Cursor, Goose, Continue.dev, etc).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-1.0+-purple.svg)](https://modelcontextprotocol.io/)

## Why this exists

If you run a homelab or small infrastructure setup with Telegraf + InfluxDB, you already have rich metrics. But asking your AI agent "what's the current load on my server?" usually means one of these:

1. The agent doesn't know how to query InfluxDB at all
2. The agent tries to compose a Flux query from scratch and gets the syntax wrong
3. The agent calls a generic `query_database` tool and dumps raw CSV at you
4. You give up and check Grafana yourself

**observability-mcp** solves this with the **no-input recipe pattern**: instead of asking the agent to compose a Flux query, you give it a menu of pre-written recipe tools. Each tool takes no arguments, runs a known-good query internally, and returns a clean human-readable answer. The agent just picks the right recipe by name.

Recipe tools currently shipped:

- `get_lab_load1` — Current 1-minute system load average
- `get_lab_memory_pct` — Current memory used percentage
- `get_top_cpu_containers` — Top 10 Docker containers by mean CPU% over the last 15 minutes

More coming. Adding a recipe is ~30 lines of Python.

## Why "no-input" recipes

We learned this the hard way. When you give a local LLM (qwen2.5, llama3.1, even larger ones) a tool that requires a complex string input (like a Flux query), it will either:

- Generate empty output (the model can't format the input correctly in ReAct text)
- Hallucinate a different tool's output
- Repeat the prompt back to you

Local models are good at **selecting** from a menu but weak at **composing** structured inputs. Recipe tools play to that strength: each tool is a single named capability with no arguments. The agent picks the right one and reads the result.

This pattern works equally well with Anthropic Claude, OpenAI GPT, and any local model with tool-calling support.

## Quick start

### Install

```bash
pip install observability-mcp
# OR
pipx install observability-mcp
```

### Configure

Set environment variables (or copy `.env.example` and source it):

```bash
export INFLUXDB_URL=http://localhost:8086
export INFLUXDB_TOKEN_FILE=/path/to/your/influxdb-readonly-token
export INFLUXDB_ORG=your-org-id
export INFLUXDB_BUCKET_METRICS=telegraf
export INFLUXDB_BUCKET_LLM=llm_usage  # optional
```

The token must be **read-only** and scoped to the buckets you want exposed. Create one with:

```bash
influx auth create \
  --read-bucket <your-telegraf-bucket-id> \
  --description "observability-mcp readonly" \
  --org-id <your-org-id>
```

### Run

```bash
observability-mcp
```

This starts a stdio MCP server. Connect it to your MCP client.

### Connect to Hermes Agent

Add to your Hermes config (`~/.hermes/config.toml` or via `hermes mcp add`):

```toml
[mcp.observability]
command = "observability-mcp"
env = { INFLUXDB_URL = "http://host.docker.internal:8086", ... }
```

Then in any Hermes conversation:

> "What's my Mac Mini load?"

Hermes calls `get_lab_load1` and returns the current value.

### Connect to Claude Code

Add to `~/.config/claude/claude.json`:

```json
{
  "mcpServers": {
    "observability": {
      "command": "observability-mcp",
      "env": {
        "INFLUXDB_URL": "http://localhost:8086",
        "INFLUXDB_TOKEN_FILE": "/path/to/token",
        "INFLUXDB_ORG": "your-org-id",
        "INFLUXDB_BUCKET_METRICS": "telegraf"
      }
    }
  }
}
```

### Connect to any other MCP client

This server speaks standard stdio MCP. It works with Cursor, Goose, Continue.dev, and any other client that supports the protocol.

## What it deliberately does NOT do

- **No write capability.** This server is read-only by design. It cannot create, update, or delete anything in InfluxDB. The token should be scoped read-only too, defense in depth.
- **No arbitrary Flux queries.** Each recipe runs a hardcoded query. If you want to expose ad-hoc Flux, that's a separate tool with separate safety considerations.
- **No mutation of the host or containers.** This server reads metrics. It doesn't restart services, delete files, or call out to anything other than your InfluxDB instance.

## Adding a new recipe

Each recipe is one Python file in `src/observability_mcp/recipes/`. The contract:

```python
from observability_mcp.influx import query

async def get_my_metric() -> str:
    """Returns the current foo metric. No input."""
    flux = '''
    from(bucket: "telegraf")
      |> range(start: -5m)
      |> filter(fn: (r) => r._measurement == "foo" and r._field == "bar")
      |> last()
      |> keep(columns: ["_value"])
    '''
    result = await query(flux)
    # Parse the CSV result and return a clean string
    return f"Current foo: {result}"
```

Then register it in `server.py`:

```python
mcp.tool()(get_my_metric)
```

That's it. PRs welcome — see CONTRIBUTING.md.

## Architecture

```
┌─────────────────────────┐
│  MCP Client (Hermes,    │
│  Claude Code, Cursor)   │
└────────────┬────────────┘
             │ stdio (MCP)
┌────────────▼────────────┐
│  observability-mcp      │
│  ├── server.py (FastMCP)│
│  ├── influx.py (HTTP)   │
│  └── recipes/           │
└────────────┬────────────┘
             │ HTTPS
┌────────────▼────────────┐
│  InfluxDB v2            │
│  (your lab metrics)     │
└─────────────────────────┘
```

## License

MIT — see [LICENSE](LICENSE).

## Built by

**[Charlie Seay](https://charlieseay.com)** — solo developer, homelab operator, and founder of [Seaynic Labs](https://seayniclabs.com). Building the tools I want to use, then sharing them.

- **Personal site & blog:** [charlieseay.com](https://charlieseay.com)
- **GitHub:** [github.com/charlieseay](https://github.com/charlieseay)

## Part of the Seaynic Labs ecosystem

[Seaynic Labs](https://seayniclabs.com) ships homelab tools, MCP servers, and self-hosted infrastructure for solo operators and small teams.

- **Store:** [store.seayniclabs.com](https://store.seayniclabs.com) — paid products: incident management, MCP server bundles, monitoring packs
- **Learn:** [hone.academy](https://hone.academy) — courses on self-hosted infrastructure, MCP servers, AI agents, and the second-brain workflow
- **Org on GitHub:** [github.com/seayniclabs](https://github.com/seayniclabs)

## Related projects

- [Hermes Agent](https://github.com/nousresearch/hermes-agent) — the open-source self-hosted AI agent this server is designed to extend
- [seayniclabs/vault-cortex-mcp](https://github.com/seayniclabs/vault-cortex-mcp) — _(coming soon)_ exposes an Obsidian vault as queryable memory
- [seayniclabs/n8n-mcp](https://github.com/seayniclabs/n8n-mcp) — _(coming soon)_ read-only n8n workflow status and execution logs
- [seayniclabs/docker-mcp](https://github.com/seayniclabs/docker-mcp) — _(coming soon)_ Docker container observation and control
- [seayniclabs/hermes-homelab](https://github.com/seayniclabs/hermes-homelab) — _(coming soon)_ one-command Docker Compose distribution that bundles Hermes + the seayniclabs MCPs into a complete homelab AI nervous system
