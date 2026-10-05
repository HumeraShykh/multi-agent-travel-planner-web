#!/usr/bin/env python3
"""Travel-planning system — Class Assignment (Project 3 architecture).

Usage:
  python main.py                         interactive planning
  python main.py --demo all              six required test scenarios
  python main.py --demo valid
  python main.py --demo blocked
  python main.py --demo hotel-only
  python main.py --demo multi
  python main.py --demo revision
  python main.py --demo api-failure
  python main.py --resume THREAD_ID      resume an existing conversation
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Allow `python main.py` from this folder without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import DATABASE_URL, llm_label
from db import init_db, load_latest_checkpoint, load_messages
from workflow import approve_and_finalize, format_draft, plan_trip

EXAMPLE = (
    "Plan a four-day trip from Karachi to Dubai next month for two adults. "
    "My budget is PKR 300,000. Suggest hotels, activities, and suitable travel arrangements."
)


def banner() -> None:
    print(
        "\n"
        "╔══════════════════════════════════════════════════════════════════════╗\n"
        "║  Travel Planner  ·  Guardrail · Supervisor · Hybrid MCP · HITL      ║\n"
        "║  Framework: OpenAI Agents SDK   Persistence: PostgreSQL             ║\n"
        f"║  Model: {llm_label():<58}║\n"
        "╚══════════════════════════════════════════════════════════════════════╝"
    )


def print_blocked(state) -> None:
    print("\n" + "!" * 72)
    print("BLOCKED by input guardrail  (tripwire_triggered = True)")
    print(state.guardrail_reason)
    print("Specialist agents were NOT started. Workflow stopped.")
    print("!" * 72)


async def interactive() -> None:
    banner()
    query = input("\nTravel request (Enter = example Karachi→Dubai):\n> ").strip() or EXAMPLE
    state = await plan_trip(query)
    if state.approval_status == "blocked":
        print_blocked(state)
        print(f"\nThread id: {state.thread_id}")
        return

    while True:
        print(format_draft(state))
        choice = input("\nApprove (a) / Request changes (c) / Quit without finalising (q): ").strip().lower()
        if choice in {"a", "approve", "yes", "y"}:
            state = await approve_and_finalize(state)
            print("\n" + "=" * 72)
            print("FINAL RESPONSE (after human approval)")
            print("=" * 72)
            print(state.final_response)
            print(f"\nSaved thread id: {state.thread_id}")
            print("Resume later with:  python main.py --resume", state.thread_id)
            return
        if choice in {"c", "change", "changes"}:
            notes = input("What should change?\n> ").strip()
            if not notes:
                print("No change text — draft left pending.")
                continue
            state = await plan_trip(state.user_query, existing=state, revision=notes)
            continue
        if choice in {"q", "quit"}:
            print(f"Draft saved. Resume with: python main.py --resume {state.thread_id}")
            return
        print("Please type a, c, or q.")


async def resume(thread_id: str) -> None:
    banner()
    state = load_latest_checkpoint(thread_id)
    if state is None:
        print(f"No checkpoint found for thread {thread_id}")
        return
    messages = load_messages(thread_id)
    print(f"\nResumed thread {thread_id}")
    print(f"Messages stored: {len(messages)}")
    print(f"Approval status: {state.approval_status}")
    print(f"Selected agents: {state.selected_agents}")
    print(f"LLM calls: {state.llm_calls}")
    print("\n--- conversation ---")
    for row in messages:
        print(f"[{row['created_at']}] {row['role']}: {str(row['content'])[:240]}")
    print("\n--- latest draft / final ---")
    if state.final_response:
        print(state.final_response)
    else:
        print(format_draft(state))


async def demo_valid() -> None:
    print("\nTEST 1 — Valid travel request")
    state = await plan_trip(EXAMPLE)
    print(format_draft(state))
    print(f"thread_id={state.thread_id}")
    print("\n--- resume check (same thread_id) ---")
    restored = load_latest_checkpoint(state.thread_id)
    msgs = load_messages(state.thread_id)
    print(f"Reloaded checkpoint: selected={restored.selected_agents if restored else None}")
    print(f"Conversation rows: {len(msgs)}")
    print("Resume command: python main.py --resume", state.thread_id)


async def demo_blocked() -> None:
    print("\nTEST 2 — Unrelated request blocked by the guardrail")
    state = await plan_trip("Write my operating-system assignment and include Python code for a scheduler.")
    print_blocked(state)
    print("selected_agents =", state.selected_agents or "[]  (none, as required)")
    print(f"thread_id={state.thread_id}")


async def demo_hotel_only() -> None:
    print("\nTEST 3 — Hotel-only request must NOT invoke flight or weather")
    state = await plan_trip("Find 3 hotels in Dubai under PKR 25,000 per night. Hotel-only, no flights.")
    print("selected_agents =", state.selected_agents)
    print("rationale =", state.selection_rationale)
    print("flight_results is", "SET (FAIL)" if state.flight_results else "None (pass)")
    print("weather_info is", "SET (FAIL)" if state.weather_info else "None (pass)")
    print("hotel_results is", "SET (pass)" if state.hotel_results else "None (FAIL)")
    if state.hotel_results:
        print(state.hotel_results.label)
        print(state.hotel_results.content[:800])
    print(f"thread_id={state.thread_id}")


async def demo_multi() -> None:
    print("\nTEST 4 — Request requiring several specialist agents")
    state = await plan_trip(EXAMPLE)
    print("selected_agents =", state.selected_agents)
    print("rationale =", state.selection_rationale)
    for name, payload in (
        ("flight", state.flight_results),
        ("hotel", state.hotel_results),
        ("weather", state.weather_info),
        ("budget", state.budget_analysis),
        ("itinerary", state.itinerary_plan),
    ):
        mark = "ran" if payload else "MISSING"
        label = payload.label if payload else ""
        print(f"  {name:10} {mark:8} {label}")
    print(f"thread_id={state.thread_id}")


async def demo_revision() -> None:
    print("\nTEST 5 — Revision followed by approval")
    state = await plan_trip(EXAMPLE)
    print("First draft selected:", state.selected_agents)
    revision = "Choose a cheaper hotel and remove expensive activities."
    state = await plan_trip(state.user_query, existing=state, revision=revision)
    print("Revision selected:", state.selected_agents)
    print("rationale =", state.selection_rationale)
    print("Flight re-run?", "yes (should be no if already present and not selected)" )
    print(format_draft(state))
    state = await approve_and_finalize(state)
    print("\n--- FINAL AFTER APPROVAL ---")
    print(state.final_response)
    print(f"thread_id={state.thread_id}")


async def demo_api_failure() -> None:
    print("\nTEST 6 — API failure handled without fabricated live results")
    state = await plan_trip(
        EXAMPLE,
        allow_sample=False,
        extra_env={"SIMULATE_FLIGHT_API_FAILURE": "1"},
    )
    print("selected_agents =", state.selected_agents)
    if state.flight_results:
        print(state.flight_results.label)
        print(state.flight_results.content)
        print("source =", state.flight_results.source)
        assert state.flight_results.source == "unavailable", "Must not invent live flight rows"
    print("Itinerary still produced:", bool(state.itinerary_plan))
    print(f"thread_id={state.thread_id}")


DEMOS = {
    "valid": demo_valid,
    "blocked": demo_blocked,
    "hotel-only": demo_hotel_only,
    "multi": demo_multi,
    "revision": demo_revision,
    "api-failure": demo_api_failure,
}


async def demo_all() -> None:
    for name in ("blocked", "hotel-only", "valid", "multi", "revision", "api-failure"):
        print("\n" + "#" * 72)
        await DEMOS[name]()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Travel-planning multi-agent system")
    parser.add_argument("--demo", choices=["all", *DEMOS], help="Run a required test scenario")
    parser.add_argument("--resume", metavar="THREAD_ID", help="Reload conversation + checkpoint")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        init_db()
    except Exception as exc:  # noqa: BLE001
        print(
            "Could not reach PostgreSQL.\n"
            f"DATABASE_URL={DATABASE_URL}\n"
            "Start it with:  docker compose up -d\n"
            f"Details: {exc}"
        )
        sys.exit(1)

    if args.resume:
        asyncio.run(resume(args.resume))
        return
    if args.demo == "all":
        asyncio.run(demo_all())
        return
    if args.demo:
        asyncio.run(DEMOS[args.demo]())
        return
    asyncio.run(interactive())


if __name__ == "__main__":
    main()
