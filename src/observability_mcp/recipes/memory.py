"""Memory usage recipes."""

from __future__ import annotations

import os

from observability_mcp.influx import InfluxQueryError, parse_single_value, query


async def get_lab_memory_pct() -> str:
    """Get the current memory used percentage on the lab host.

    Returns the most recent `mem.used_percent` value from Telegraf within
    the last 5 minutes.

    No input required.
    """
    bucket = os.environ.get("INFLUXDB_BUCKET_METRICS", "telegraf")
    flux = (
        f'from(bucket: "{bucket}")\n'
        f'  |> range(start: -5m)\n'
        f'  |> filter(fn: (r) => r._measurement == "mem" and r._field == "used_percent")\n'
        f'  |> last()\n'
        f'  |> keep(columns: ["_value", "host"])\n'
    )

    try:
        csv_text = await query(flux)
    except InfluxQueryError as e:
        return f"Error: could not fetch memory % from InfluxDB ({e})"

    value = parse_single_value(csv_text)
    if value is None:
        return "No memory data found in the last 5 minutes — is Telegraf running?"

    try:
        pct = float(value)
    except ValueError:
        return f"Unexpected response from InfluxDB: {value}"

    if pct < 50:
        hint = "low"
    elif pct < 75:
        hint = "normal"
    elif pct < 90:
        hint = "elevated"
    else:
        hint = "critical — investigate"

    return f"Lab memory used: {pct:.1f}% ({hint})"
