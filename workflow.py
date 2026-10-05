"""Main workflow — 8 simple steps from the lecture diagram.

Sir ko explain karne ke liye yeh socho:

    User
      ↓
    1. Guardrail     (galat request? STOP)
      ↓
    2. Supervisor    (kaun se agents chahiye?)
      ↓
    3. Selected agents only   (hotel-only pe flight NAHI)
      ↓
    4. Shared state + PostgreSQL
      ↓
    5. Human: Approve ya Change
      ↓
    6. Final response   (sirf approval ke baad)

Revision aaye to step 1 skip hota hai (request pehle hi valid thi)
aur supervisor sirf change wale agents dubara chalata hai.
"""

from __future__ import annotations

from db import persist_turn
from guardrails import run_input_guardrail
from mcp_runtime import MCPBundle, open_mcp_bundle
from specialists import (
    run_budget_agent,
    run_final_response_agent,
    run_flight_agent,
    run_hotel_agent,
    run_itinerary_agent,
    run_weather_agent,
)
from state import TravelState
from supervisor import run_supervisor


def format_draft(state: TravelState) -> str:
    """Print the draft so the human can approve or ask for changes."""
    lines = [
        "=" * 72,
        "DRAFT ITINERARY — waiting for human approval",
        "=" * 72,
        f"Thread: {state.thread_id}",
        f"Selected agents: {', '.join(state.selected_agents) or '(none)'}",
        f"Why these agents: {state.selection_rationale}",
        f"LLM calls so far: {state.llm_calls}",
        "",
        (
            "Trip: "
            f"{state.trip_constraints.origin} → {state.trip_constraints.destination}, "
            f"{state.trip_constraints.duration_days} days, "
            f"{state.trip_constraints.travellers} travellers, "
            f"budget {state.trip_constraints.budget_currency} {state.trip_constraints.budget_amount}"
        ),
    ]
    if state.trip_constraints.date_note:
        lines.append(state.trip_constraints.date_note)
    lines.append("")

    # Show only the specialists that actually ran.
    sections = [
        ("Flights", state.flight_results),
        ("Hotels", state.hotel_results),
        ("Weather", state.weather_info),
        ("Budget", state.budget_analysis),
        ("Itinerary", state.itinerary_plan),
    ]
    for title, payload in sections:
        if payload is None:
            continue
        lines.append("-" * 72)
        lines.append(f"{title}  {payload.label}")
        if payload.limitation:
            lines.append(f"Limitation: {payload.limitation}")
        lines.append(payload.content)
        lines.append("")

    lines.append("This application recommends a plan. It does not make bookings.")
    return "\n".join(lines)


async def run_only_selected_agents(
    state: TravelState,
    bundle: MCPBundle,
    allow_sample: bool,
) -> TravelState:
    """Run agents one by one. If the name is not in selected_agents, skip it.

    This is the whole 'dynamic selection' idea:
    hotel-only request → flight and weather are never called.
    """
    selected = state.selected_agents

    if "flight" in selected:
        state = await run_flight_agent(state, bundle, allow_sample=allow_sample)
        persist_turn(state, "assistant", "Flight agent finished.")

    if "hotel" in selected:
        state = await run_hotel_agent(state, bundle, allow_sample=allow_sample)
        persist_turn(state, "assistant", "Hotel agent finished.")

    if "weather" in selected:
        state = await run_weather_agent(state, bundle)
        persist_turn(state, "assistant", "Weather agent finished.")

    if "budget" in selected:
        state = await run_budget_agent(state)
        persist_turn(state, "assistant", "Budget agent finished.")

    if "itinerary" in selected:
        state = await run_itinerary_agent(state)
        persist_turn(state, "assistant", "Itinerary agent finished.")

    return state


async def plan_trip(
    user_query: str,
    *,
    thread_id: str | None = None,
    existing: TravelState | None = None,
    revision: str | None = None,
    allow_sample: bool = True,
    extra_env: dict[str, str] | None = None,
) -> TravelState:
    """One simple path for both a new request and a revision."""

    # ----------------------------------------------------------
    # Step A: start a new state OR keep the old conversation
    # ----------------------------------------------------------
    if existing is None:
        state = TravelState()
        if thread_id:
            state.thread_id = thread_id
        state.user_query = user_query
        persist_turn(state, "user", user_query)
    else:
        state = existing
        if user_query:
            state.user_query = state.user_query or user_query

    # ----------------------------------------------------------
    # Step B: NEW request → guardrail. Revision → skip guardrail.
    # A revision means the first request was already accepted.
    # ----------------------------------------------------------
    if revision:
        state.revision_notes = revision
        state.approval_status = "changes_requested"
        persist_turn(state, "user", f"REVISION: {revision}")
    else:
        guard = await run_input_guardrail(user_query, state)
        if not guard.allowed:
            # Tripwire: do not start any specialist agent.
            state.approval_status = "blocked"
            state.guardrail_reason = guard.reason
            persist_turn(state, "guardrail", f"BLOCKED. {guard.reason}")
            return state
        persist_turn(state, "guardrail", f"PASSED. {guard.reason}")

    # ----------------------------------------------------------
    # Step C: supervisor decides WHICH agents to run
    # ----------------------------------------------------------
    state = await run_supervisor(state, revision=revision)
    persist_turn(state, "supervisor", f"Selected {state.selected_agents}. {state.selection_rationale}")

    # ----------------------------------------------------------
    # Step D: start only the MCP servers those agents need
    #         then run only those agents
    # ----------------------------------------------------------
    bundle = await open_mcp_bundle(set(state.selected_agents), extra_env=extra_env)
    try:
        state = await run_only_selected_agents(state, bundle, allow_sample)
    finally:
        await bundle.aclose()

    # ----------------------------------------------------------
    # Step E: draft is ready — human must approve before final
    # ----------------------------------------------------------
    state.approval_status = "pending"
    persist_turn(state)
    return state


async def approve_and_finalize(state: TravelState) -> TravelState:
    """Final response agent runs ONLY after the human says approve."""
    state.approval_status = "approved"
    persist_turn(state, "user", "APPROVED")
    state = await run_final_response_agent(state)
    persist_turn(state, "assistant", state.final_response or "Final plan ready.")
    return state
