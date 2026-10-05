"""Local custom Weather MCP server (STDIO).

Lecture mapping:
  Pattern 1 — Local MCP, transport = STDIO.
  Custom because we wrap an external weather service behind named tools
  instead of giving the agent a raw HTTP client.

Backend: wttr.in (no API key). Optional OpenWeatherMap if OPENWEATHER_API_KEY is set.
"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("custom-weather", log_level="ERROR")


def _http_json(url: str, timeout: int = 20) -> dict:
    req = Request(url, headers={"User-Agent": "travel-planner-weather-mcp/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _from_wttr(city: str, days: int = 3) -> dict:
    data = _http_json(f"https://wttr.in/{quote(city)}?format=j1")
    current = data.get("current_condition", [{}])[0]
    forecast = []
    for day in data.get("weather", [])[:days]:
        forecast.append(
            {
                "date": day.get("date"),
                "max_c": day.get("maxtempC"),
                "min_c": day.get("mintempC"),
                "condition": (day.get("hourly") or [{}])[4].get("weatherDesc", [{}])[0].get("value")
                if day.get("hourly")
                else None,
            }
        )
    return {
        "provider": "wttr.in",
        "city": city,
        "current": {
            "temp_c": current.get("temp_C"),
            "feels_like_c": current.get("FeelsLikeC"),
            "humidity": current.get("humidity"),
            "condition": (current.get("weatherDesc") or [{}])[0].get("value"),
        },
        "forecast": forecast,
    }


def _from_openweather(city: str) -> dict:
    key = os.getenv("OPENWEATHER_API_KEY", "")
    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={quote(city)}&appid={quote(key)}&units=metric"
    )
    data = _http_json(url)
    return {
        "provider": "openweathermap",
        "city": city,
        "current": {
            "temp_c": data.get("main", {}).get("temp"),
            "feels_like_c": data.get("main", {}).get("feels_like"),
            "humidity": data.get("main", {}).get("humidity"),
            "condition": (data.get("weather") or [{}])[0].get("description"),
        },
        "forecast": [],
    }


@mcp.tool()
def get_current_weather(city: str) -> str:
    """Retrieve current weather for a city. city example: Dubai"""
    try:
        if os.getenv("OPENWEATHER_API_KEY"):
            payload = _from_openweather(city)
        else:
            payload = _from_wttr(city, days=1)
        return json.dumps({"ok": True, "source": "retrieved", **payload})
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return json.dumps(
            {
                "ok": False,
                "source": "unavailable",
                "city": city,
                "limitation": f"Weather backend failed: {exc}",
            }
        )


@mcp.tool()
def get_forecast(city: str, days: int = 4) -> str:
    """Retrieve a short daily forecast. days is clamped to 1-7."""
    days = max(1, min(int(days or 4), 7))
    try:
        payload = _from_wttr(city, days=days)
        return json.dumps({"ok": True, "source": "retrieved", **payload})
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return json.dumps(
            {
                "ok": False,
                "source": "unavailable",
                "city": city,
                "limitation": f"Forecast backend failed: {exc}",
            }
        )


if __name__ == "__main__":
    mcp.run(transport="stdio")
