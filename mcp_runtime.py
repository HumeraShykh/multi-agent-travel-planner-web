"""Start and talk to MCP servers using the OpenAI Agents SDK clients.

Hybrid deployment (Week 7 slide 40):
  - Weather      = local custom MCP, STDIO
  - Aviationstack = local MCP, STDIO
  - Tavily hotels = remote-style MCP, Streamable HTTP
"""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

from agents.mcp import MCPServerStdio, MCPServerStreamableHttp

from config import HOTEL_MCP_PORT, ROOT

PYTHON = sys.executable


def _stdio(name: str, script: str, extra_env: dict[str, str] | None = None) -> MCPServerStdio:
    env = {**os.environ, **(extra_env or {})}
    return MCPServerStdio(
        name=name,
        cache_tools_list=True,
        client_session_timeout_seconds=30,
        params={
            "command": PYTHON,
            "args": [str(ROOT / "mcp_servers" / script)],
            "env": env,
        },
    )


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def start_hotel_http_server() -> subprocess.Popen:
    """Launch the Streamable HTTP hotel MCP so the hotel agent can connect remotely."""
    if _port_open(HOTEL_MCP_PORT):
        return None  # type: ignore[return-value]
    proc = subprocess.Popen(
        [PYTHON, str(ROOT / "mcp_servers" / "tavily_hotel_server.py")],
        cwd=str(ROOT),
        env={**os.environ, "HOTEL_MCP_PORT": str(HOTEL_MCP_PORT)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        if _port_open(HOTEL_MCP_PORT):
            return proc
        time.sleep(0.15)
        if proc.poll() is not None:
            break
    raise RuntimeError(
        f"Hotel MCP HTTP server failed to start on port {HOTEL_MCP_PORT}. "
        "Check that the port is free and dependencies are installed."
    )


@dataclass
class MCPBundle:
    weather: MCPServerStdio | None = None
    flights: MCPServerStdio | None = None
    hotels: MCPServerStreamableHttp | None = None
    hotel_proc: subprocess.Popen | None = None
    stack: AsyncExitStack = field(default_factory=AsyncExitStack)

    async def aclose(self) -> None:
        await self.stack.aclose()
        if self.hotel_proc and self.hotel_proc.poll() is None:
            self.hotel_proc.terminate()
            try:
                self.hotel_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.hotel_proc.kill()


async def open_mcp_bundle(need: set[str], extra_env: dict[str, str] | None = None) -> MCPBundle:
    bundle = MCPBundle()
    extra_env = extra_env or {}

    if "hotel" in need:
        bundle.hotel_proc = start_hotel_http_server()
        bundle.hotels = MCPServerStreamableHttp(
            name="tavily-hotels-remote",
            cache_tools_list=True,
            client_session_timeout_seconds=30,
            params={"url": f"http://127.0.0.1:{HOTEL_MCP_PORT}/mcp"},
        )
        await bundle.stack.enter_async_context(bundle.hotels)

    if "weather" in need:
        bundle.weather = _stdio("custom-weather", "weather_server.py", extra_env)
        await bundle.stack.enter_async_context(bundle.weather)

    if "flight" in need:
        bundle.flights = _stdio("aviationstack-flights", "aviationstack_server.py", extra_env)
        await bundle.stack.enter_async_context(bundle.flights)

    return bundle


def _tool_text(result: Any) -> str:
    if result is None:
        return ""
    content = getattr(result, "content", None)
    if not content:
        return str(result)
    parts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts) or str(result)


async def call_mcp_tool(server: Any, tool_name: str, arguments: dict[str, Any]) -> str:
    """Call a discovered MCP tool and return its text payload."""
    result = await server.call_tool(tool_name, arguments)
    return _tool_text(result)
