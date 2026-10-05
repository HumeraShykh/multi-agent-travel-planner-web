# multi-agent-travel-planner-web

<p align="center">
  <strong>SAFAR</strong> — a trip planner that uses separate AI agents, not one chatbot that calls every API at once.
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#what-it-does">What it does</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#run-the-web-app">Web app</a> ·
  <a href="#run-the-tests">Tests</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="Flask" src="https://img.shields.io/badge/Flask-web%20UI-000000?logo=flask">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-local%20%2B%20remote-0F6B5C">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/use-recommend%20only-c56a1a">
</p>

A web app that plans trips with **separate AI agents** for flights, hotels, and weather. It first checks that the request is valid, then runs **only the agents that are needed**. You review and approve the plan. Progress is saved in PostgreSQL. It suggests itineraries. **It does not book anything.**

---

## Table of contents

- [What it does](#what-it-does)
- [Why it is built this way](#why-it-is-built-this-way)
- [How it works](#how-it-works)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Quick start](#quick-start)
- [Run the web app](#run-the-web-app)
- [Run from the terminal](#run-from-the-terminal)
- [Run the tests](#run-the-tests)
- [Environment variables](#environment-variables)
- [Example prompts](#example-prompts)
- [Safety notes](#safety-notes)

---

## What it does

Type a trip in normal English, for example:

> Plan a four-day trip from Karachi to Dubai next month for two adults. My budget is PKR 300,000.

The app then:

1. **Checks the request** — travel plans go through; homework or harmful asks are blocked.
2. **Picks agents** — a supervisor decides who should run (not always all five).
3. **Fetches live data** where possible — flights, hotels, weather through MCP servers.
4. **Builds a draft** — day-by-day plan plus a labelled cost estimate.
5. **Waits for you** — approve, or ask for a change such as a cheaper hotel.
6. **Remembers the chat** — same `thread_id` can be opened again from PostgreSQL.

Open the UI after setup: [http://127.0.0.1:5055](http://127.0.0.1:5055)

---

## Why it is built this way

Many “AI travel” demos attach every tool to one prompt. That wastes money, mixes hotel search into a flights-only question, and can look confident when an API actually failed.

This project is closer to how a real agent product should behave:

| Rule | What you see |
| --- | --- |
| Least work | Hotel-only request → flight and weather agents stay off |
| Named tools | Agents call MCP tools, not raw URLs inside the prompt |
| Honest data | Live results are labelled **retrieved**; costs are labelled **estimate** |
| No fake tickets | If Aviationstack is down, the UI says unavailable — it does not invent a fare |
| Human last | Final plan is written only after **Approve** |
| Memory | Conversations + checkpoints in PostgreSQL |

---

## How it works

```mermaid
flowchart TD
  A[User types a trip] --> B[Input guardrail]
  B -->|blocked| X[Stop and show reason]
  B -->|pass| C[Supervisor]
  C --> D{Which agents?}
  D -->|needed| E[Flight MCP]
  D -->|needed| F[Hotel MCP]
  D -->|needed| G[Weather MCP]
  E --> H[Shared TravelState]
  F --> H
  G --> H
  H --> I[Budget + itinerary]
  I --> J[You approve or request changes]
  J -->|changes| C
  J -->|approve| K[Final recommendation]
  K --> L[(PostgreSQL)]
```

**Guardrail** — keyword check (optional LLM is off by default to save tokens). Tripwire means: do not start specialists.

**Supervisor** — three simple cases:

- full trip → flight, hotel, weather, budget, itinerary  
- hotel-only → hotel (+ budget if a spend limit is given)  
- revision (“cheaper hotel…”) → hotel, budget, itinerary only  

**MCP (hybrid)**

| Agent | Server | Where it runs |
| --- | --- | --- |
| Flights | Aviationstack | Local MCP, STDIO |
| Hotels | Tavily | Remote-style MCP, Streamable HTTP |
| Weather | Custom wrapper | Local custom MCP, STDIO |

---

## Tech stack

- **Python 3.12**
- **OpenAI Agents SDK** + **Pydantic**
- **MCP** (`mcp` 1.x) — STDIO and Streamable HTTP
- **Flask** web UI
- **PostgreSQL 16** via `psycopg`
- Optional LLM: OpenAI `gpt-4o-mini` or Groq (kept off by `MINIMAL_TOKENS=1`)

---

## Project structure

```text
travel_planner/
├── app.py                 # Web UI
├── main.py                # CLI + 6 demos
├── workflow.py            # Guardrail → supervisor → agents → HITL
├── guardrails.py
├── supervisor.py
├── specialists.py
├── state.py               # Shared TravelState
├── db.py                  # PostgreSQL save / resume
├── mcp_runtime.py
├── mcp_servers/
│   ├── aviationstack_server.py
│   ├── tavily_hotel_server.py
│   └── weather_server.py
├── templates/index.html
├── static/
├── sql/init.sql
├── .env.example
└── requirements.txt
```

---

## Quick start

### 1. Install Python 3.12+

```bash
python3.12 --version
```

### 2. Open the project folder

```bash
cd travel_planner
```

### 3. Create a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Create your env file

```bash
cp .env.example .env
```

Open `.env` and add keys you have. **Never commit `.env`.**

Weather works without a key (`wttr.in`). Flights need Aviationstack. Hotels need Tavily. PostgreSQL is required.

### 5. Start PostgreSQL

**Option A — Docker (recommended for a clean setup)**

```bash
docker compose up -d
```

Then in `.env`:

```text
DATABASE_URL=postgresql://travel:travel@localhost:5433/travel_planner
```

**Option B — local Postgres**

```bash
createdb travel_planner
```

Then set `DATABASE_URL` to your user, for example:

```text
DATABASE_URL=postgresql://YOUR_USERNAME@localhost:5432/travel_planner
```

### 6. Run the website

```bash
python app.py
```

Open **[http://127.0.0.1:5055](http://127.0.0.1:5055)** → type a trip → **Design my journey**.

<details>
<summary><strong>First-run checklist</strong></summary>

- [ ] `.venv` is activated (`which python` points inside `.venv`)
- [ ] `.env` exists (not only `.env.example`)
- [ ] Postgres accepts connections
- [ ] Browser is on port **5055**, not 5000
- [ ] If plan is slow, hotel MCP is starting on port 8765 — wait a few seconds

</details>

---

## Run the web app

```bash
source .venv/bin/activate
python app.py
```

| You type | You should see |
| --- | --- |
| A real trip | Flights / hotels / weather cards, then **Approve** or **Revise** |
| `Write my OS assignment` | Blocked. No agents run |
| `Find 3 hotels in Dubai. Hotel-only, no flights.` | Hotel (+ budget). Flight and weather **off** |

After approve, the page shows the final recommendation only. Nothing is booked.

---

## Run from the terminal

Same engine, no browser:

```bash
source .venv/bin/activate
python main.py
```

Press Enter for the Karachi → Dubai example, or type your own request.  
`a` = approve · `c` = request changes · `q` = quit  

Resume later:

```bash
python main.py --resume thread-xxxxxxxxxxxx
```

---

## Run the tests

These six demos match the product behaviour you should be able to show:

```bash
python main.py --demo all
```

Or one at a time:

```bash
python main.py --demo blocked        # unrelated request stopped
python main.py --demo hotel-only     # no flight / weather
python main.py --demo valid          # full trip + resume check
python main.py --demo multi          # several specialists
python main.py --demo revision       # change, then approve
python main.py --demo api-failure    # no invented live fares
```

---

## Environment variables

Copy from [`.env.example`](.env.example).

| Variable | Required? | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Yes | PostgreSQL connection |
| `AVIATIONSTACK_API_KEY` | For live flights | Local flight MCP |
| `TAVILY_API_KEY` | For live hotels | Hotel MCP → Tavily |
| `OPENAI_API_KEY` or `GROQ_API_KEY` | Optional | Writing/summaries |
| `MINIMAL_TOKENS` | Default `1` | `1` = almost no LLM spend; APIs still run |
| `OPENAI_MODEL` | Default `gpt-4o-mini` | Cheap model if LLM is on |
| `HOTEL_MCP_PORT` | Default `8765` | HTTP MCP for hotels |

If a live key is missing, that specialist reports **unavailable**. Labelled sample data may appear for a demo, except `--demo api-failure`, which shows the failure without fabricated live results.

---

## Example prompts

Copy any of these into the web box:

```text
Plan a four-day trip from Karachi to Dubai next month for two adults. My budget is PKR 300,000. Suggest hotels, activities, and suitable travel arrangements.
```

```text
Make a plan for a tour from Sukkur to Islamabad.
```

```text
Find 3 hotels in Dubai under PKR 25,000 per night. Hotel-only, no flights.
```

```text
Write my operating-system assignment and include Python code for a scheduler.
```

Then, after a draft:

```text
Choose a cheaper hotel and remove expensive activities.
```

---

## Safety notes

- This repository **recommends** travel plans. It does **not** place bookings or take payment.
- Do not publish `.env`, API keys, or database passwords.
- Keyword guardrails are not perfect: they can miss a valid request that never says “travel”, or pass a bad request that happens to contain “trip”. That limitation is intentional to document, not a hidden bug.

---

<p align="center">
  <sub>SAFAR · recommend only · never books</sub>
</p>
