"""Travel-site UI for the planner.

Run:
    python app.py
Then open http://127.0.0.1:5055
"""

from __future__ import annotations

import asyncio

from flask import Flask, redirect, render_template, request, url_for

from db import init_db, load_latest_checkpoint
from state import TravelState
from workflow import approve_and_finalize, plan_trip

app = Flask(__name__)
THREADS: dict[str, TravelState] = {}

DEST_FILES = {
    "islamabad": "photos/islamabad.jpg",
    "dubai": "photos/dubai.jpg",
    "karachi": "photos/karachi.jpg",
    "sukkur": "photos/desert.jpg",
    "lahore": "photos/islamabad.jpg",
    "istanbul": "photos/dubai.jpg",
    "london": "photos/hero.jpg",
    "doha": "photos/desert.jpg",
}
HERO_FILE = "photos/hero.jpg"
HOTEL_FILES = [
    "photos/hotel1.jpg",
    "photos/hotel2.jpg",
    "photos/hotel3.jpg",
    "photos/hotel1.jpg",
    "photos/hotel2.jpg",
]


def _run(coro):
    return asyncio.run(coro)


def _photo(path: str) -> str:
    return url_for("static", filename=path)


def _photo_for(city: str | None) -> str:
    if not city:
        return _photo(HERO_FILE)
    return _photo(DEST_FILES.get(city.lower(), HERO_FILE))


def _itinerary_parts(text: str) -> tuple[list[str], list[str]]:
    days, notes = [], []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("day "):
            days.append(line)
        else:
            notes.append(line)
    return days, notes


def _view(state: TravelState | None, error: str | None = None):
    dest = state.trip_constraints.destination if state else None
    origin = state.trip_constraints.origin if state else None
    flights = ((state.flight_results.raw or {}).get("flights") if state and state.flight_results else None) or []
    hotels = ((state.hotel_results.raw or {}).get("results") if state and state.hotel_results else None) or []
    hotel_answer = (state.hotel_results.raw or {}).get("answer") if state and state.hotel_results else None
    weather = state.weather_info.raw if state and state.weather_info else None
    days, notes = _itinerary_parts(state.itinerary_plan.content if state and state.itinerary_plan else "")
    return render_template(
        "index.html",
        state=state,
        error=error,
        hero=_photo(HERO_FILE),
        dest_photo=_photo_for(dest),
        origin_photo=_photo_for(origin),
        flights=flights,
        hotels=hotels,
        hotel_photos=[_photo(p) for p in HOTEL_FILES],
        hotel_answer=hotel_answer,
        weather=weather,
        itin_days=days,
        itin_notes=notes,
    )


@app.get("/")
def home():
    thread_id = request.args.get("thread")
    state = THREADS.get(thread_id) if thread_id else None
    if thread_id and state is None:
        state = load_latest_checkpoint(thread_id)
        if state:
            THREADS[state.thread_id] = state
    return _view(state)


@app.post("/plan")
def plan():
    query = (request.form.get("query") or "").strip()
    if not query:
        return _view(None, "Please type a travel request.")
    try:
        init_db()
        state = _run(plan_trip(query))
    except Exception as exc:  # noqa: BLE001
        return _view(None, f"Could not run the planner: {exc}")
    THREADS[state.thread_id] = state
    return redirect(url_for("home", thread=state.thread_id))


@app.post("/revise")
def revise():
    thread_id = request.form.get("thread_id") or ""
    notes = (request.form.get("notes") or "").strip()
    state = THREADS.get(thread_id)
    if state is None:
        return _view(None, "Draft not found. Plan the trip again.")
    if not notes:
        return redirect(url_for("home", thread=thread_id))
    state = _run(plan_trip(state.user_query, existing=state, revision=notes))
    THREADS[state.thread_id] = state
    return redirect(url_for("home", thread=state.thread_id))


@app.post("/approve")
def approve():
    thread_id = request.form.get("thread_id") or ""
    state = THREADS.get(thread_id)
    if state is None:
        return _view(None, "Draft not found. Plan the trip again.")
    state = _run(approve_and_finalize(state))
    THREADS[state.thread_id] = state
    return redirect(url_for("home", thread=state.thread_id))


if __name__ == "__main__":
    init_db()
    print("Open http://127.0.0.1:5055")
    app.run(host="127.0.0.1", port=5055, debug=False)
