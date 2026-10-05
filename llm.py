"""OpenAI Agents SDK model wiring (OpenAI or Groq/Llama-3)."""

from __future__ import annotations

from functools import lru_cache

from agents import (
    Agent,
    ModelSettings,
    OpenAIChatCompletionsModel,
    set_default_openai_client,
    set_tracing_disabled,
)
from openai import AsyncOpenAI

from config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    HAS_LLM,
    MINIMAL_TOKENS,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    USE_GROQ,
)

set_tracing_disabled(True)


@lru_cache(maxsize=1)
def configure_client() -> AsyncOpenAI | None:
    if USE_GROQ:
        client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)
        set_default_openai_client(client)
        return client
    if OPENAI_API_KEY:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        set_default_openai_client(client)
        return client
    return None


def model_for_agents():
    """Return a model object/string the Agents SDK can use."""
    client = configure_client()
    if USE_GROQ and client is not None:
        return OpenAIChatCompletionsModel(model=GROQ_MODEL, openai_client=client)
    if client is not None:
        return OPENAI_MODEL
    return OPENAI_MODEL


def make_agent(name: str, instructions: str, output_type=None, mcp_servers=None) -> Agent:
    kwargs = {
        "name": name,
        "instructions": instructions,
        "model": model_for_agents(),
        # Short answers = fewer tokens.
        "model_settings": ModelSettings(temperature=0, max_tokens=250),
    }
    if output_type is not None:
        kwargs["output_type"] = output_type
    if mcp_servers:
        kwargs["mcp_servers"] = mcp_servers
    return Agent(**kwargs)


def llm_available() -> bool:
    """True only when we are allowed to spend tokens on writing."""
    return HAS_LLM and not MINIMAL_TOKENS
