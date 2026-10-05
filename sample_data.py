"""Clearly labelled sample payloads used ONLY when an MCP/API is unavailable.

Assignment rule: sample data is allowed for demonstration if it is labelled.
Fabricated results presented as live retrieval are not allowed.
"""

from state import SourcedPayload


def sample_flights(origin: str, destination: str) -> SourcedPayload:
    return SourcedPayload(
        source="sample_labelled",
        label="[SAMPLE DATA — labelled for demo only | not a live Aviationstack quote]",
        limitation=(
            "Live Aviationstack results were unavailable. The rows below are "
            "illustrative sample data for demonstrating the flight agent only."
        ),
        content=(
            f"[SAMPLE DATA — labelled for demo only]\n"
            f"Route {origin} → {destination} (illustrative, not bookable):\n"
            f"1) PK-211 Pakistan International · morning departure · fare unknown\n"
            f"2) EK-603 Emirates · afternoon departure · fare unknown\n"
            f"3) QR-611 Qatar Airways via DOH · evening departure · fare unknown\n"
            f"Ticket prices are NOT retrieved. Budget agent must treat fares as estimates."
        ),
        raw={"sample": True, "origin": origin, "destination": destination},
    )


def sample_hotels(destination: str) -> SourcedPayload:
    return SourcedPayload(
        source="sample_labelled",
        label="[SAMPLE DATA — labelled for demo only | not a live Tavily result]",
        limitation=(
            "Remote Tavily MCP/API was unavailable. The hotels below are "
            "labelled sample data for demonstrating the hotel agent only."
        ),
        content=(
            f"[SAMPLE DATA — labelled for demo only]\n"
            f"Stay options in {destination} (illustrative):\n"
            f"1) City Centre Hotel — 3★, metro access — sample nightly range PKR 18,000–22,000\n"
            f"2) Marina View Suites — 4★, family rooms — sample nightly range PKR 28,000–35,000\n"
            f"3) Budget Stay Deira — 3★, breakfast included — sample nightly range PKR 12,000–16,000\n"
            f"These are not live availability or booking prices."
        ),
        raw={"sample": True, "destination": destination},
    )


def sample_weather(city: str) -> SourcedPayload:
    return SourcedPayload(
        source="sample_labelled",
        label="[SAMPLE DATA — labelled for demo only | not a live weather reading]",
        limitation="Custom weather MCP could not reach its backend.",
        content=(
            f"[SAMPLE DATA — labelled for demo only]\n"
            f"{city}: typical late-year daytime warmth; pack light layers, "
            f"sunscreen, and a light evening covering. Not a live forecast."
        ),
        raw={"sample": True, "city": city},
    )
