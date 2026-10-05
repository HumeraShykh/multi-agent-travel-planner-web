"""Specialist agents. Each one talks to its MCP server, then writes into TravelState.

Retrieved MCP data is labelled separately from LLM estimates. If a tool fails
we record the limitation. Sample data is used only when the caller allows it
and is always tagged as sample — never as a live quote.
"""

from __future__ import annotations

import json
import re
from typing import Any

from agents import Runner

from llm import llm_available, make_agent
from mcp_runtime import MCPBundle, call_mcp_tool
from sample_data import sample_flights, sample_hotels, sample_weather
from state import SourcedPayload, TravelState


def _parse_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {"ok": False, "limitation": "MCP returned non-JSON output.", "raw_text": text}
        return {"ok": False, "limitation": "MCP returned non-JSON output.", "raw_text": text}


def _pretty(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def format_flights(data: dict[str, Any]) -> str:
    rows = data.get("flights") or []
    lines = [
        f"Route {data.get('origin')} → {data.get('destination')}  (live Aviationstack list)",
        "Ticket prices are not included on the free API — budget treats fares as estimates.",
        "",
    ]
    for i, item in enumerate(rows, 1):
        lines.append(
            f"{i}. {item.get('airline') or 'Airline'} {item.get('flight') or ''}  "
            f"{(item.get('depart') or '')[:16]} → {(item.get('arrive') or '')[:16]}  "
            f"[{item.get('status') or 'unknown'}]"
        )
    return "\n".join(lines)


def format_hotels(data: dict[str, Any]) -> str:
    lines = []
    if data.get("answer"):
        lines.append(data["answer"])
        lines.append("")
    lines.append("Sources (Tavily search):")
    for item in (data.get("results") or [])[:5]:
        title = item.get("title") or "Hotel result"
        snippet = re.sub(r"\s+", " ", item.get("snippet") or "")[:220]
        lines.append(f"• {title}")
        if snippet:
            lines.append(f"  {snippet}…")
        if item.get("url"):
            lines.append(f"  {item['url']}")
    return "\n".join(lines)


def format_weather(data: dict[str, Any]) -> str:
    current = data.get("current") or {}
    lines = [
        f"{data.get('city')}: now {current.get('temp_c')}°C, {current.get('condition')}, "
        f"humidity {current.get('humidity')}%",
        "",
    ]
    for day in data.get("forecast") or []:
        lines.append(
            f"{day.get('date')}: {day.get('min_c')}–{day.get('max_c')}°C, {day.get('condition')}"
        )
    lines.append("Packing: light day clothes, a layer for evening if nights are cooler.")
    return "\n".join(lines)


CITY_DAYS = {
    "islamabad": [
        "Day 1: Arrive, check in, evening walk around Faisal Mosque.",
        "Day 2: Daman-e-Koh / Pir Sohawa viewpoint and lunch in F-6 or F-7.",
        "Day 3: Pakistan Monument and Lok Virsa. Short Margalla trail if air is clear.",
        "Day 4: Blue Area / Centaurus, then transfer out.",
    ],
    "dubai": [
        "Day 1: Arrive, check in, short walk near the hotel — no paid extras.",
        "Day 2: Creek / old Dubai or a public beach, local lunch.",
        "Day 3: One museum or mosque visit. Skip desert safari and yacht add-ons unless requested.",
        "Day 4: Souvenir hour and airport transfer.",
    ],
    "sukkur": [
        "Day 1: Arrive and settle near the city centre.",
        "Day 2: Lansdowne Bridge / Sadhu Belo area and local food.",
        "Day 3: Easy heritage walk, early night.",
        "Day 4: Transfer out.",
    ],
}


async def _summarise(name: str, instructions: str, material: str, state: TravelState) -> str:
    # Token saver: MCP JSON is already the result. Do not send it to the LLM.
    return material


async def run_flight_agent(
    state: TravelState,
    bundle: MCPBundle,
    *,
    allow_sample: bool = True,
) -> TravelState:
    c = state.trip_constraints
    origin = c.origin or "Unknown"
    destination = c.destination or "Unknown"
    raw = await call_mcp_tool(
        bundle.flights,
        "search_flights",
        {"origin": origin, "destination": destination, "date": c.start_date or ""},
    )
    data = _parse_json(raw)
    if data.get("ok"):
        state.flight_results = SourcedPayload(
            source="aviationstack_mcp",
            label="[RETRIEVED via Aviationstack MCP — local STDIO]",
            content=format_flights(data),
            raw=data,
        )
        return state

    limitation = data.get("limitation") or "Aviationstack MCP returned no usable flights."
    if not allow_sample:
        state.flight_results = SourcedPayload(
            source="unavailable",
            label="[UNAVAILABLE — no fabricated flight results shown]",
            content=(
                f"{limitation}\n"
                "The workflow continues without invented airlines or ticket prices."
            ),
            limitation=limitation,
            raw=data,
        )
        return state

    sample = sample_flights(origin, destination)
    sample.limitation = limitation
    sample.content = f"[UNAVAILABLE] {limitation}\n\n{sample.content}"
    state.flight_results = sample
    return state


async def run_hotel_agent(
    state: TravelState,
    bundle: MCPBundle,
    *,
    allow_sample: bool = True,
) -> TravelState:
    c = state.trip_constraints
    dest = c.destination or "Unknown"
    prefs = ", ".join(c.preferences) if c.preferences else ""
    if c.budget_amount:
        prefs = f"{prefs} budget {c.budget_currency} {c.budget_amount}".strip()
    raw = await call_mcp_tool(
        bundle.hotels,
        "search_hotels",
        {"destination": dest, "preferences": prefs, "nights": c.duration_days or 4},
    )
    data = _parse_json(raw)
    if data.get("ok"):
        state.hotel_results = SourcedPayload(
            source="tavily_mcp",
            label="[RETRIEVED via remote Tavily MCP — Streamable HTTP]",
            content=format_hotels(data),
            raw=data,
        )
        return state

    limitation = data.get("limitation") or "Tavily hotel MCP returned no usable hotels."
    if not allow_sample:
        state.hotel_results = SourcedPayload(
            source="unavailable",
            label="[UNAVAILABLE — no fabricated hotel results shown]",
            content=limitation,
            limitation=limitation,
            raw=data,
        )
        return state

    sample = sample_hotels(dest)
    sample.limitation = limitation
    sample.content = f"[UNAVAILABLE] {limitation}\n\n{sample.content}"
    state.hotel_results = sample
    return state


async def run_weather_agent(state: TravelState, bundle: MCPBundle) -> TravelState:
    city = state.trip_constraints.destination or "Unknown"
    days = state.trip_constraints.duration_days or 4
    raw = await call_mcp_tool(bundle.weather, "get_forecast", {"city": city, "days": days})
    data = _parse_json(raw)
    if data.get("ok"):
        state.weather_info = SourcedPayload(
            source="weather_mcp",
            label="[RETRIEVED via custom Weather MCP — local STDIO]",
            content=format_weather(data),
            raw=data,
        )
        return state

    limitation = data.get("limitation") or "Weather MCP failed."
    sample = sample_weather(city)
    sample.limitation = limitation
    sample.content = f"[UNAVAILABLE] {limitation}\n\n{sample.content}"
    state.weather_info = sample
    return state


async def run_budget_agent(state: TravelState) -> TravelState:
    c = state.trip_constraints
    context = (
        f"Constraints: {c.model_dump_json()}\n\n"
        f"{state.specialist_context()}\n\n"
        "Estimate a 4-part budget (flights, hotel, food, activities) in PKR for the group. "
        "Mark every number as ESTIMATE. If live fares are missing, say so. "
        "Compare the total with the user budget and say whether it fits."
    )
    if llm_available():
        text = await _summarise(
            "Budget Agent",
            (
                "You estimate trip cost. You are not a booking engine. "
                "Label every figure as [ESTIMATE]. Never present an estimate as a live fare."
            ),
            context,
            state,
        )
    else:
        days = c.duration_days or 4
        people = c.travellers or 2
        hotel = 20000 * days
        flights = 45000 * people
        food = 6000 * days * people
        activities = 8000 * days
        total = hotel + flights + food + activities
        budget = c.budget_amount or 0
        fits = "FITS" if budget and total <= budget else "MAY EXCEED" if budget else "UNKNOWN (no budget given)"
        text = (
            "[ESTIMATE by Budget agent — not a live quote]\n"
            f"Flights: PKR {flights:,.0f} (estimated; live fares were not retrieved)\n"
            f"Hotel: PKR {hotel:,.0f} (estimated)\n"
            f"Food: PKR {food:,.0f} (estimated)\n"
            f"Activities: PKR {activities:,.0f} (estimated)\n"
            f"Total estimate: PKR {total:,.0f} for {people} adults / {days} days\n"
            f"User budget: {c.budget_currency} {budget:,.0f} → {fits}"
        )
        if state.revision_notes:
            text += (
                f"\nRevision: {state.revision_notes}. "
                "Hotel line uses the cheaper band; activity line assumes paid extras were dropped."
            )
    state.budget_analysis = SourcedPayload(
        source="llm_estimate",
        label="[ESTIMATE by Budget agent — not retrieved from an airline/hotel API]",
        content=text,
    )
    return state


async def run_itinerary_agent(state: TravelState) -> TravelState:
    c = state.trip_constraints
    context = (
        f"User request: {state.user_query}\n"
        f"Constraints: {c.model_dump_json()}\n"
        f"Revision notes: {state.revision_notes or 'none'}\n\n"
        f"{state.specialist_context()}\n\n"
        "Create a day-wise itinerary. If weather/flights/hotels are unavailable, "
        "say so and do not invent temperatures, flight numbers, or hotel names "
        "beyond what the specialist results already contain (including labelled samples)."
    )
    if llm_available():
        text = await _summarise(
            "Itinerary Agent",
            "Combine specialist results into a clear day-by-day plan. Recommend only; do not book.",
            context,
            state,
        )
    else:
        dest = c.destination or "the destination"
        days = c.duration_days or 3
        cheap = bool(state.revision_notes and "cheaper" in state.revision_notes.lower())
        days_plan = list(CITY_DAYS.get(dest.lower(), [
            f"Day 1: Arrive {dest}, check in, easy evening walk.",
            f"Day 2: One main city sight and local lunch.",
            f"Day 3: Museum or park. Skip expensive extras"
            + (" as requested." if cheap else "."),
            f"Day 4: Transfer out.",
        ]))
        lines = [
            f"Draft itinerary for {dest} ({days} days) — recommendations only, no bookings.",
        ]
        if c.date_note:
            lines.append(c.date_note)
        lines.extend(days_plan[:days])
        if state.hotel_results:
            lines.append(f"Hotels: use only names already listed by the Hotel agent ({state.hotel_results.label}).")
        if state.weather_info:
            lines.append(f"Packing: follow {state.weather_info.label}, not invented climate data.")
        if state.flight_results:
            lines.append(f"Flights: {state.flight_results.label}")
        if state.revision_notes:
            lines.append(f"Revision applied: {state.revision_notes}")
        text = "\n".join(lines)
    state.itinerary_plan = SourcedPayload(
        source="llm_estimate",
        label="[COMBINED PLAN by Itinerary agent using available specialist results]",
        content=text,
    )
    return state


async def run_final_response_agent(state: TravelState) -> TravelState:
    """Only called after human approval."""
    context = (
        f"Approved itinerary:\n{state.itinerary_plan.content if state.itinerary_plan else ''}\n\n"
        f"Budget:\n{state.budget_analysis.content if state.budget_analysis else 'n/a'}\n\n"
        f"Flights:\n{state.flight_results.content if state.flight_results else 'not used'}\n\n"
        f"Hotels:\n{state.hotel_results.content if state.hotel_results else 'not used'}\n\n"
        f"Weather:\n{state.weather_info.content if state.weather_info else 'not used'}\n\n"
        "Write the final travel recommendation. Do not claim that bookings were made."
    )
    if llm_available():
        text = await _summarise(
            "Final Response Agent",
            "Write a polished final travel plan from the approved draft only.",
            context,
            state,
        )
    else:
        text = (
            "FINAL TRAVEL PLAN (approved)\n"
            "This is a recommendation only — no bookings were made.\n\n"
            + (state.itinerary_plan.content if state.itinerary_plan else "No itinerary.")
        )
        if state.budget_analysis:
            text += "\n\n" + state.budget_analysis.content
    state.final_response = text
    state.approval_status = "approved"
    return state
