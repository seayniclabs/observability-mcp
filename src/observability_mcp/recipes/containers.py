"""Docker container recipes."""

from __future__ import annotations

import os

from observability_mcp.influx import InfluxQueryError, parse_table, query


async def get_top_cpu_containers() -> str:
    """Get the top 10 Docker containers by mean CPU usage over the last 15 minutes.

    Returns a sorted list of container names with their mean CPU percentage,
    most-CPU-hungry first. Useful for finding the cause of system load spikes.

    No input required.
    """
    bucket = os.environ.get("INFLUXDB_BUCKET_METRICS", "telegraf")
    # Important: after group(columns:[...]), each container_name is its own
    # table — sort and limit operate per-table, so we'd get 10 entries for
    # EACH container instead of the global top 10. The empty group() call
    # ungroups everything back into a single table where sort + limit work
    # globally.
    flux = (
        f'from(bucket: "{bucket}")\n'
        f'  |> range(start: -15m)\n'
        f'  |> filter(fn: (r) => r._measurement == "docker_container_cpu" '
        f'and r._field == "usage_percent")\n'
        f'  |> group(columns: ["container_name"])\n'
        f'  |> mean()\n'
        f'  |> group()\n'
        f'  |> sort(columns: ["_value"], desc: true)\n'
        f'  |> limit(n: 10)\n'
        f'  |> keep(columns: ["container_name", "_value"])\n'
    )

    try:
        csv_text = await query(flux)
    except InfluxQueryError as e:
        return f"Error: could not fetch container CPU stats from InfluxDB ({e})"

    rows = parse_table(csv_text)
    if not rows:
        return "No Docker container CPU data found in the last 15 minutes."

    # Build a clean ranked list
    lines = ["Top containers by mean CPU% (last 15 min):"]
    for i, row in enumerate(rows, 1):
        name = row.get("container_name", "?")
        try:
            pct = float(row.get("_value", "0"))
        except ValueError:
            pct = 0.0
        lines.append(f"  {i:2d}. {name:30s} {pct:6.2f}%")

    return "\n".join(lines)
