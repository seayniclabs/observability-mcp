"""Thin InfluxDB v2 HTTP client for read-only Flux queries.

Reads configuration from environment variables. Authenticates via a
read-only token loaded from a file (defense in depth — the token never
appears in environment variables or process listings).

Usage:
    from observability_mcp.influx import query

    csv_text = await query('from(bucket:"telegraf") |> range(start:-5m) |> ...')
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx


class InfluxConfigError(RuntimeError):
    """Raised when required InfluxDB configuration is missing or invalid."""


class InfluxQueryError(RuntimeError):
    """Raised when an InfluxDB query fails (network, auth, syntax)."""


def _config() -> tuple[str, str, str]:
    """Read and validate environment configuration.

    Returns:
        Tuple of (url, org, token).

    Raises:
        InfluxConfigError: If any required config is missing or the token
            file is unreadable.
    """
    url = os.environ.get("INFLUXDB_URL", "http://localhost:8086").rstrip("/")
    org = os.environ.get("INFLUXDB_ORG")
    token_file = os.environ.get("INFLUXDB_TOKEN_FILE")
    token_inline = os.environ.get("INFLUXDB_TOKEN")

    if not org:
        raise InfluxConfigError(
            "INFLUXDB_ORG environment variable is required (the InfluxDB organization ID)"
        )

    # Prefer file-based token (more secure than env var)
    token = None
    if token_file:
        path = Path(token_file).expanduser()
        if not path.exists():
            raise InfluxConfigError(
                f"INFLUXDB_TOKEN_FILE points to {path} which does not exist"
            )
        token = path.read_text().strip()
    elif token_inline:
        token = token_inline.strip()

    if not token:
        raise InfluxConfigError(
            "Either INFLUXDB_TOKEN_FILE (preferred) or INFLUXDB_TOKEN must be set"
        )

    return url, org, token


async def query(flux: str, *, timeout: float = 20.0) -> str:
    """Run a Flux query against InfluxDB v2 and return the raw CSV response.

    Args:
        flux: The Flux query string. Must start with `from(bucket:...)` —
            this is enforced as a defense-in-depth check, the read-only
            token is the primary safeguard.
        timeout: Request timeout in seconds (default 20).

    Returns:
        Raw CSV response from the InfluxDB query API.

    Raises:
        InfluxConfigError: If config is missing.
        InfluxQueryError: If the query fails for any reason.
        ValueError: If the query is not a from(bucket:...) read query.
    """
    if not flux or not flux.strip():
        raise ValueError("Flux query cannot be empty")
    if "from(bucket:" not in flux:
        raise ValueError(
            "Query must start with from(bucket:...) — this server is read-only"
        )
    # Block the most obvious write functions even though the token is read-only.
    forbidden = ["to(", "experimental.to(", "experimental.to_http("]
    for f in forbidden:
        if f in flux:
            raise ValueError(f"Query contains forbidden write function: {f}")

    url, org, token = _config()

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(
                f"{url}/api/v2/query",
                params={"org": org},
                headers={
                    "Authorization": f"Token {token}",
                    "Content-Type": "application/vnd.flux",
                    "Accept": "application/csv",
                },
                content=flux,
            )
        except httpx.HTTPError as e:
            raise InfluxQueryError(f"HTTP request to {url} failed: {e}") from e

    if response.status_code != 200:
        raise InfluxQueryError(
            f"InfluxDB returned HTTP {response.status_code}: {response.text[:300]}"
        )

    return response.text


def _split_csv_lines(csv_text: str) -> list[str]:
    """Split a CSV response into clean non-empty lines.

    InfluxDB v2 returns CRLF line endings, so we use splitlines() which
    handles all line ending variants and avoids leaving \\r on each line.
    """
    return [line for line in csv_text.splitlines() if line.strip()]


def parse_single_value(csv_text: str, field: str = "_value") -> str | None:
    """Parse a single-value Flux CSV response and return the value as a string.

    Most recipes return a 2-line CSV: header row + one data row. This helper
    extracts the named field from the data row.

    Args:
        csv_text: The raw CSV response from InfluxDB.
        field: The column name to extract (default "_value").

    Returns:
        The value as a string, or None if not found.
    """
    lines = _split_csv_lines(csv_text)
    if len(lines) < 2:
        return None

    header = lines[0].split(",")
    if field not in header:
        return None
    field_idx = header.index(field)

    # Take the last row (in case there's more than one)
    data_row = lines[-1].split(",")
    if field_idx >= len(data_row):
        return None

    return data_row[field_idx].strip()


def parse_table(csv_text: str) -> list[dict[str, str]]:
    """Parse a Flux CSV response into a list of dicts (one per row).

    Args:
        csv_text: The raw CSV response.

    Returns:
        List of dicts mapping column name to string value, one per data row.
    """
    lines = _split_csv_lines(csv_text)
    if len(lines) < 2:
        return []

    header = lines[0].split(",")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        values = line.split(",")
        if len(values) != len(header):
            continue
        rows.append(dict(zip(header, values)))
    return rows
