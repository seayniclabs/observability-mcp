"""System load recipes."""

from __future__ import annotations

import os

from observability_mcp.influx import InfluxQueryError, parse_single_value, query


async def get_lab_load1() -> str:
    """Get the current 1-minute system load average from the lab host.

    Returns the most recent `system.load1` value from Telegraf within the
    last 5 minutes. If multiple hosts are reporting, returns the highest
    value seen.

    No input required.
    """
    bucket = os.environ.get("INFLUXDB_BUCKET_METRICS", "telegraf")
    flux = (
        f'from(bucket: "{bucket}")\n'
        f'  |> range(start: -5m)\n'
        f'  |> filter(fn: (r) => r._measurement == "system" and r._field == "load1")\n'
        f'  |> last()\n'
        f'  |> keep(columns: ["_value", "host"])\n'
    )

    try:
        csv_text = await query(flux)
    except InfluxQueryError as e:
        return f"Error: could not fetch load1 from InfluxDB ({e})"

    value = parse_single_value(csv_text)
    if value is None:
        return "No load1 data found in the last 5 minutes — is Telegraf running?"

    try:
        load = float(value)
    except ValueError:
        return f"Unexpected response from InfluxDB: {value}"

    # Add interpretation hint based on common thresholds.
    # These are heuristics, not absolutes — agents should treat them as
    # rough guidance, not authoritative.
    if load < 2.0:
        hint = "low"
    elif load < 5.0:
        hint = "normal"
    elif load < 8.0:
        hint = "moderate"
    else:
        hint = "high — investigate"

    return f"Lab load1: {load:.2f} ({hint})"


async def get_lab_load_history_24h() -> str:
    """Get the 24-hour load1 history aggregated to 5-minute windows.

    Returns the mean, min, and max load1 over the last 24 hours, plus
    the current value. Useful for spotting anomalies and understanding
    whether the current load is unusual.

    No input required.
    """
    bucket = os.environ.get("INFLUXDB_BUCKET_METRICS", "telegraf")
    flux = (
        f'from(bucket: "{bucket}")\n'
        f'  |> range(start: -24h)\n'
        f'  |> filter(fn: (r) => r._measurement == "system" and r._field == "load1")\n'
        f'  |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)\n'
        f'  |> keep(columns: ["_time", "_value"])\n'
    )

    try:
        csv_text = await query(flux)
    except InfluxQueryError as e:
        return f"Error: could not fetch load history from InfluxDB ({e})"

    # Parse all values — use splitlines() to handle CRLF
    lines = [line for line in csv_text.splitlines() if line.strip()]
    if len(lines) < 2:
        return "No load history available in the last 24 hours."

    header = lines[0].split(",")
    if "_value" not in header:
        return "Unexpected response format from InfluxDB"
    value_idx = header.index("_value")

    values: list[float] = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) <= value_idx:
            continue
        try:
            values.append(float(parts[value_idx]))
        except ValueError:
            continue

    if not values:
        return "No numeric load values parsed from the response."

    mean = sum(values) / len(values)
    return (
        f"24h load1 history ({len(values)} samples, 5m windows): "
        f"mean={mean:.2f}, min={min(values):.2f}, max={max(values):.2f}, "
        f"current={values[-1]:.2f}"
    )
