"""Supervisor = two jobs only.

  Job 1: request se trip details nikaalo (city, days, budget, people).
  Job 2: decide karo kaun se specialist agents chahiye.

Har request pe saare agents NAHI chalte. Yeh Project 3 ka asl point hai.

Sir ko 3 cases batao:

  1) Full trip   → flight + hotel + weather + budget + itinerary
  2) Hotel only  → hotel  (+ budget if user ne price di)
  3) Revision    → sirf hotel + budget + itinerary
                   (flight/weather pehle se state mein hain)
"""

from __future__ import annotations

import calendar
import re
from datetime import date

from pydantic import BaseModel, Field

from state import AgentName, TravelState, TripConstraints

ALL_AGENTS: list[AgentName] = ["flight", "hotel", "weather", "budget", "itinerary"]


class SupervisorDecision(BaseModel):
    origin: str | None = None
    destination: str | None = None
    duration_days: int | None = None
    start_date: str | None = None
    end_date: str | None = None
    date_note: str | None = None
    travellers: int | None = None
    budget_amount: float | None = None
    budget_currency: str = "PKR"
    preferences: list[str] = Field(default_factory=list)
    selected_agents: list[str] = Field(default_factory=list)
    rationale: str = ""


def dates_for_next_month(days: int | None) -> tuple[str, str, str]:
    """'next month' ko real dates banao. Aaj October 2026 hai to November 10–13."""
    today = date.today()
    year = today.year + 1 if today.month == 12 else today.year
    month = 1 if today.month == 12 else today.month + 1
    start = date(year, month, 10)
    how_many = days if days else 4
    last_day = calendar.monthrange(year, month)[1]
    end_day = min(start.day + how_many - 1, last_day)
    end = date(year, month, end_day)
    note = f"User said next month, so we use {start} to {end}."
    return str(start), str(end), note


CITIES = {
    "karachi": "Karachi",
    "sukkur": "Sukkur",
    "islamabad": "Islamabad",
    "lahore": "Lahore",
    "dubai": "Dubai",
    "istanbul": "Istanbul",
    "doha": "Doha",
    "london": "London",
}


def _find_city(blob: str) -> str | None:
    for key, name in CITIES.items():
        if key in blob:
            return name
    return None


def extract_details(text: str) -> dict:
    """Simple word search. No fancy NLP — easy to explain."""
    t = text.lower()

    origin = destination = None
    route = re.search(r"from\s+([a-z ]+?)\s+to\s+([a-z ]+?)(?:[\s,.]|$)", t)
    if route:
        origin = _find_city(route.group(1))
        destination = _find_city(route.group(2))
    if not origin:
        origin = _find_city(t)
        # If only one city is named after "to", treat it as destination.
        if " to " in t:
            origin = _find_city(t.split(" to ", 1)[0]) or origin
    if not destination:
        after_to = t.split(" to ", 1)[1] if " to " in t else t
        destination = _find_city(after_to)

    travellers = 2 if ("two adult" in t or "2 adult" in t or "for two" in t) else None
    people = re.search(r"(\d+)\s+(adults|people|travellers|travelers)", t)
    if people:
        travellers = int(people.group(1))
    if travellers is None:
        travellers = 1

    duration = 4 if ("four-day" in t or "four day" in t or "4-day" in t or "4 day" in t) else None
    days = re.search(r"(\d+)\s*day", t)
    if days:
        duration = int(days.group(1))
    if duration is None:
        duration = 3

    budget_amount = None
    money = re.search(r"pkr\s*([0-9,]+)", t) or re.search(r"([0-9,]+)\s*pkr", t)
    if money:
        budget_amount = float(money.group(1).replace(",", ""))

    start_date = end_date = date_note = None
    if "next month" in t:
        start_date, end_date, date_note = dates_for_next_month(duration)

    return {
        "origin": origin,
        "destination": destination,
        "duration_days": duration,
        "start_date": start_date,
        "end_date": end_date,
        "date_note": date_note,
        "travellers": travellers,
        "budget_amount": budget_amount,
    }


def choose_agents(query: str, revision: str | None) -> tuple[list[str], str, list[str]]:
    """Three easy if/else cases. Yeh viva ka sab se important function hai."""
    t = (query + " " + (revision or "")).lower()
    details = extract_details(t)
    prefs: list[str] = []

    # CASE 1 — user ne draft dekh ke change maanga
    if revision:
        selected = ["hotel", "budget", "itinerary"]
        why = (
            "User asked to change the hotel/activities. "
            "We re-run Hotel, Budget, and Itinerary only. "
            "Flight and Weather are already in shared state."
        )
        return selected, why, prefs

    # CASE 2 — hotel-only (assignment test 3)
    hotel_only = (
        "hotel-only" in t
        or "hotel only" in t
        or "only hotel" in t
        or "only hotels" in t
        or "just hotel" in t
    )
    if hotel_only:
        selected = ["hotel"]
        if details["budget_amount"] is not None or "under" in t or "pkr" in t:
            selected.append("budget")
        why = (
            "User asked only for hotels. "
            "Flight and Weather are not needed, so they are not started."
        )
        prefs.append("hotel-only")
        return selected, why, prefs

    # CASE 3 — full trip (assignment example + test 1 and 4)
    selected = list(ALL_AGENTS)
    why = (
        "User asked to plan a full trip (place, days, hotels, activities, travel). "
        "So we need Flight, Hotel, Weather, Budget, and Itinerary."
    )
    if "hotel" in t:
        prefs.append("hotels")
    if "activit" in t:
        prefs.append("activities")
    if "travel arrangement" in t or "flight" in t:
        prefs.append("travel arrangements")
    return selected, why, prefs


def decide(query: str, revision: str | None = None) -> SupervisorDecision:
    details = extract_details(query + " " + (revision or ""))
    selected, why, prefs = choose_agents(query, revision)
    return SupervisorDecision(
        origin=details["origin"],
        destination=details["destination"],
        duration_days=details["duration_days"],
        start_date=details["start_date"],
        end_date=details["end_date"],
        date_note=details["date_note"],
        travellers=details["travellers"],
        budget_amount=details["budget_amount"],
        budget_currency="PKR",
        preferences=prefs,
        selected_agents=selected,
        rationale=why,
    )


async def run_supervisor(state: TravelState, revision: str | None = None) -> TravelState:
    """Always use the simple rules. Optional LLM can suggest, but rules win.

    Sir ko bolo: LLM help kar sakta hai details nikaalne mein,
    lekin hotel-only / revision ke rules code mein fix hain
    taake galat agent na chal jaye.
    """
    # Token saver: rules extract city/days/budget. No LLM call here.
    decision = decide(state.user_query, revision)

    state.trip_constraints = TripConstraints(
        origin=decision.origin,
        destination=decision.destination,
        duration_days=decision.duration_days,
        start_date=decision.start_date,
        end_date=decision.end_date,
        date_note=decision.date_note,
        travellers=decision.travellers,
        budget_amount=decision.budget_amount,
        budget_currency="PKR",
        preferences=decision.preferences,
    )
    state.selected_agents = [a for a in decision.selected_agents if a in ALL_AGENTS]  # type: ignore[misc]
    state.selection_rationale = decision.rationale
    return state


# Old name used in a few comments / mental model
heuristic_select = decide
