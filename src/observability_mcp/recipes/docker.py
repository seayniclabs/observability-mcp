"""Docker-level recipes — container count and memory."""

from __future__ import annotations

import os

from observability_mcp.influx import InfluxQueryError, parse_single_value, parse_table, query


async def get_container_count() -> str:
    """Get the number of running Docker containers.

    Returns the current `docker.n_containers_running` value from Telegraf.
    Compare against expected count (~49 on the Seaynic Labs Mac Mini) to
    detect unexpected exits.

    No input required.
    """
    bucket = os.environ.get("INFLUXDB_BUCKET_METRICS", "telegraf")
    flux = (
        f'from(bucket: "{bucket}")\n'
        f'  |> range(start: -5m)\n'
        f'  |> filter(fn: (r) => r._measurement == "docker" '
        f'and r._field == "n_containers_running")\n'
        f'  |> last()\n'
        f'  |> keep(columns: ["_value", "host"])\n'
    )

    try:
        csv_text = await query(flux)
    except InfluxQueryError as e:
        return f"Error: could not fetch container count from InfluxDB ({e})"

    value = parse_single_value(csv_text)
    if value is None:
        return "No Docker data found in the last 5 minutes — is Telegraf's Docker input enabled?"

    try:
        count = int(float(value))
    except ValueError:
        return f"Unexpected response from InfluxDB: {value}"

    if count < 45:
        hint = "below expected — something may have exited"
    elif count > 55:
        hint = "above expected — check for unexpected new containers"
    else:
        hint = "normal"

    return f"Docker containers running: {count} ({hint})"


async def get_top_memory_containers() -> str:
    """Get the top 10 Docker containers by mean memory usage over the last 15 minutes.

    Returns a sorted list of container names with their mean memory percentage,
    most-memory-hungry first. Useful for finding memory hogs.

    No input required.
    """
    bucket = os.environ.get("INFLUXDB_BUCKET_METRICS", "telegraf")
    flux = (
        f'from(bucket: "{bucket}")\n'
        f'  |> range(start: -15m)\n'
        f'  |> filter(fn: (r) => r._measurement == "docker_container_mem" '
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
        return f"Error: could not fetch container memory stats from InfluxDB ({e})"

    rows = parse_table(csv_text)
    if not rows:
        return "No Docker container memory data found in the last 15 minutes."

    lines = ["Top containers by mean memory% (last 15 min):"]
    for i, row in enumerate(rows, 1):
        name = row.get("container_name", "?")
        try:
            pct = float(row.get("_value", "0"))
        except ValueError:
            pct = 0.0
        lines.append(f"  {i:2d}. {name:30s} {pct:6.2f}%")

    return "\n".join(lines)
