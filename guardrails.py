"""Input guardrail + tripwire.

Lecture words:
  tripwire_triggered = True  →  do not continue normally.

Simple 3 checks (sir ko yahi order batao):

  1. Harmful words?     → BLOCK
  2. Homework / code, and no travel words? → BLOCK
  3. Travel words?      → PASS
  else                  → BLOCK

Keyword limitation (assignment yeh poochti hai):
  Keywords meaning nahi samajhte.
  'I need four days in Dubai' travel hai lekin word 'travel' missing ho sakta hai.
  'hack this trip server' mein 'trip' hai lekin request harmful hai.
  Isliye yeh list perfect nahi — yeh uski limitation hai.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from state import TravelState

TRAVEL_WORDS = (
    "travel",
    "trip",
    "flight",
    "hotel",
    "itinerary",
    "vacation",
    "dubai",
    "karachi",
    "budget",
    "tour",
    "airport",
    "stay",
)

HOMEWORK_WORDS = (
    "assignment",
    "homework",
    "thesis",
    "python code",
    "write a function",
    "operating system",
    "leetcode",
)

HARMFUL_WORDS = (
    "bomb",
    "malware",
    "hack",
    "steal passport",
    "forge visa",
    "make a weapon",
)


class GuardrailVerdict(BaseModel):
    is_travel_request: bool = Field(description="True if the user wants travel planning help.")
    is_harmful: bool = Field(description="True if the request is unsafe.")
    reason: str


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str
    tripwire_triggered: bool
    layer: str


def _contains(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def keyword_check(text: str) -> GuardrailResult:
    t = text.lower()

    if _contains(t, HARMFUL_WORDS):
        return GuardrailResult(
            allowed=False,
            reason="Blocked: request looks harmful.",
            tripwire_triggered=True,
            layer="keyword",
        )

    if _contains(t, HOMEWORK_WORDS) and not _contains(t, TRAVEL_WORDS):
        return GuardrailResult(
            allowed=False,
            reason="Blocked: this is not a travel request (homework/code).",
            tripwire_triggered=True,
            layer="keyword",
        )

    if _contains(t, TRAVEL_WORDS):
        return GuardrailResult(
            allowed=True,
            reason="Passed: request looks like travel planning.",
            tripwire_triggered=False,
            layer="keyword",
        )

    return GuardrailResult(
        allowed=False,
        reason="Blocked: no travel-planning words found.",
        tripwire_triggered=True,
        layer="keyword",
    )


async def run_input_guardrail(user_text: str, state: TravelState | None = None) -> GuardrailResult:
    """Always run the keyword check. LLM is optional extra, not required."""
    result = keyword_check(user_text)

    # Safety: harmful keyword pe LLM se override mat lo.
    if not result.allowed and _contains(user_text.lower(), HARMFUL_WORDS):
        return result

    # Token saver: keyword tripwire only. No LLM classification call.
    return result
