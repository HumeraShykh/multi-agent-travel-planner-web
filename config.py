"""Load environment settings for the travel-planning system."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


_PLACEHOLDERS = {
    "",
    "sk-your-openai-api-key-here",
    "gsk-your-groq-api-key-here",
    "your-aviationstack-api-key-here",
    "your-tavily-api-key-here",
}


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    if value in _PLACEHOLDERS:
        # Keep child MCP processes from sending dummy keys to live APIs.
        if name in os.environ and os.environ[name].strip() in _PLACEHOLDERS:
            os.environ.pop(name, None)
        return ""
    return value


OPENAI_API_KEY = _env("OPENAI_API_KEY")
GROQ_API_KEY = _env("GROQ_API_KEY")
# Cheapest OpenAI chat model. Do not use gpt-4o — it burns tokens.
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini"
GROQ_MODEL = _env("GROQ_MODEL", "llama-3.1-8b-instant") or "llama-3.1-8b-instant"

# 1 = APIs (Tavily / Aviationstack / weather) run, LLM calls almost none.
# 0 = also write itinerary/final with gpt-4o-mini (still no extra summaries).
MINIMAL_TOKENS = _env("MINIMAL_TOKENS", "1") != "0"

AVIATIONSTACK_API_KEY = _env("AVIATIONSTACK_API_KEY")
TAVILY_API_KEY = _env("TAVILY_API_KEY")
TAVILY_MCP_URL = _env("TAVILY_MCP_URL", "https://mcp.tavily.com/mcp/")
OPENWEATHER_API_KEY = _env("OPENWEATHER_API_KEY")

DATABASE_URL = _env(
    "DATABASE_URL",
    "postgresql://humerashaikh@localhost:5432/travel_planner",
)
HOTEL_MCP_PORT = int(_env("HOTEL_MCP_PORT", "8765"))

# Prefer Groq/Llama-3 when the lecture-style key is present; otherwise OpenAI.
USE_GROQ = bool(GROQ_API_KEY)
HAS_LLM = bool(GROQ_API_KEY or OPENAI_API_KEY)


def llm_label() -> str:
    if USE_GROQ:
        return f"Groq/{GROQ_MODEL}"
    if OPENAI_API_KEY:
        return f"OpenAI/{OPENAI_MODEL}"
    return "no-llm-fallback"
