"""Disk usage recipes."""

from __future__ import annotations

import os

from observability_mcp.influx import InfluxQueryError, parse_table, query


async def get_lab_disk_pct() -> str:
    """Get current disk usage percentages for all mounted volumes.

    Returns the used percentage for each mount point reported by Telegraf.
    Useful for "are we running out of space?" questions.

    No input required.
    """
    bucket = os.environ.get("INFLUXDB_BUCKET_METRICS", "telegraf")
    flux = (
        f'from(bucket: "{bucket}")\n'
        f'  |> range(start: -5m)\n'
        f'  |> filter(fn: (r) => r._measurement == "disk" and r._field == "used_percent")\n'
        f'  |> group(columns: ["path"])\n'
        f'  |> last()\n'
        f'  |> keep(columns: ["path", "_value"])\n'
    )

    try:
        csv_text = await query(flux)
    except InfluxQueryError as e:
        return f"Error: could not fetch disk usage from InfluxDB ({e})"

    rows = parse_table(csv_text)
    if not rows:
        return "No disk data found in the last 5 minutes."

    lines = ["Disk usage by mount point:"]
    for row in rows:
        path = row.get("path", "?")
        try:
            pct = float(row.get("_value", "0"))
        except ValueError:
            pct = 0.0
        hint = "critical" if pct > 90 else "elevated" if pct > 80 else "ok"
        lines.append(f"  {path:40s} {pct:5.1f}% ({hint})")

    return "\n".join(lines)
