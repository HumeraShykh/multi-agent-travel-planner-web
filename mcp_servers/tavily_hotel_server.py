"""Remote-style Tavily hotel MCP server (Streamable HTTP).

Lecture mapping:
  Pattern 2 — Remote MCP, transport = Streamable HTTP.
  The hotel agent connects over HTTP, not STDIO. The server then calls Tavily.

This process is started by the workflow and exposed at http://127.0.0.1:<port>/mcp.
If TAVILY_API_KEY is missing or Tavily errors, the tool reports a limitation
instead of inventing hotel prices.
"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mcp.server.fastmcp import FastMCP

PORT = int(os.getenv("HOTEL_MCP_PORT", "8765"))
mcp = FastMCP(
    "tavily-hotels",
    host="127.0.0.1",
    port=PORT,
    stateless_http=True,
    log_level="ERROR",
)


def _tavily_search(query: str) -> dict:
    key = os.getenv("TAVILY_API_KEY", "")
    if not key:
        raise RuntimeError(
            "TAVILY_API_KEY is missing. Remote Tavily hotel search cannot run."
        )
    body = json.dumps(
        {
            "api_key": key,
            "query": query,
            "search_depth": "basic",
            "include_answer": True,
            "max_results": 6,
        }
    ).encode("utf-8")
    req = Request(
        "https://api.tavily.com/search",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


@mcp.tool()
def search_hotels(destination: str, preferences: str = "", nights: int = 4) -> str:
    """Search hotels via Tavily for a destination. preferences can mention budget or area."""
    query = (
        f"best hotels in {destination} for a {nights}-night stay "
        f"{preferences} prices amenities reviews"
    ).strip()
    try:
        data = _tavily_search(query)
        results = []
        for item in data.get("results") or []:
            results.append(
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "snippet": item.get("content"),
                }
            )
        return json.dumps(
            {
                "ok": True,
                "source": "retrieved",
                "provider": "tavily",
                "destination": destination,
                "query": query,
                "answer": data.get("answer"),
                "results": results,
            }
        )
    except (HTTPError, URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
        return json.dumps(
            {
                "ok": False,
                "source": "unavailable",
                "destination": destination,
                "limitation": f"Tavily remote hotel search failed: {exc}",
            }
        )


if __name__ == "__main__":
    # Streamable HTTP — this is the remote transport from Week 7.
    mcp.run(transport="streamable-http")
