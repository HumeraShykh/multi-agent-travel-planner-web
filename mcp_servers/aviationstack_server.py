"""Local Aviationstack MCP server (STDIO).

Lecture mapping:
  Pattern 1 — Local MCP, transport = STDIO.
  The agent discovers search_flights instead of embedding Aviationstack URLs.

Free Aviationstack plans often restrict flight/route endpoints. When that
happens we return a structured limitation — we never silently invent fares.
"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("aviationstack-flights", log_level="ERROR")

IATA = {
    "karachi": "KHI",
    "dubai": "DXB",
    "islamabad": "ISB",
    "lahore": "LHE",
    "sukkur": "SKZ",
    "london": "LHR",
    "new york": "JFK",
    "istanbul": "IST",
    "doha": "DOH",
    "abu dhabi": "AUH",
}


def to_iata(value: str) -> str:
    raw = (value or "").strip()
    if len(raw) == 3 and raw.isalpha():
        return raw.upper()
    return IATA.get(raw.lower(), raw.upper()[:3])


def _get(path: str, params: dict) -> dict:
    if os.getenv("SIMULATE_FLIGHT_API_FAILURE") == "1":
        raise RuntimeError("Simulated Aviationstack outage (SIMULATE_FLIGHT_API_FAILURE=1).")
    key = os.getenv("AVIATIONSTACK_API_KEY", "")
    if not key:
        raise RuntimeError(
            "AVIATIONSTACK_API_KEY is missing. The flight MCP cannot call the live API."
        )

    query = urlencode({"access_key": key, **params})
    url = f"https://api.aviationstack.com/v1/{path}?{query}"
    with urlopen(url, timeout=25) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("error"):
        err = payload["error"]
        raise RuntimeError(err.get("info") or err.get("message") or str(err))
    return payload


@mcp.tool()
def search_flights(origin: str, destination: str, date: str = "") -> str:
    """Search flights between two cities or IATA codes. date is YYYY-MM-DD if known."""
    dep = to_iata(origin)
    arr = to_iata(destination)
    try:
        params = {"dep_iata": dep, "arr_iata": arr, "limit": 8}
        if date:
            params["flight_date"] = date
        payload = _get("flights", params)
        rows = []
        for item in payload.get("data") or []:
            dep_info = item.get("departure") or {}
            arr_info = item.get("arrival") or {}
            airline = (item.get("airline") or {}).get("name")
            flight_no = (item.get("flight") or {}).get("iata")
            rows.append(
                {
                    "airline": airline,
                    "flight": flight_no,
                    "from": dep_info.get("iata"),
                    "to": arr_info.get("iata"),
                    "depart": dep_info.get("scheduled"),
                    "arrive": arr_info.get("scheduled"),
                    "status": item.get("flight_status"),
                    "fare": None,
                    "fare_note": "Aviationstack free/standard flight listing does not include ticket prices.",
                }
            )
        if not rows:
            return json.dumps(
                {
                    "ok": False,
                    "source": "unavailable",
                    "origin": dep,
                    "destination": arr,
                    "limitation": (
                        "Aviationstack returned no rows for this route. "
                        "The free plan often omits scheduled future-date search."
                    ),
                }
            )
        return json.dumps(
            {
                "ok": True,
                "source": "retrieved",
                "origin": dep,
                "destination": arr,
                "date": date or None,
                "flights": rows,
            }
        )
    except (HTTPError, URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
        return json.dumps(
            {
                "ok": False,
                "source": "unavailable",
                "origin": dep,
                "destination": arr,
                "limitation": f"Aviationstack MCP could not retrieve flights: {exc}",
            }
        )


if __name__ == "__main__":
    mcp.run(transport="stdio")
