# Sir ko aise explain karo (simple)

Yeh Project 3 hai: supervisor + guardrail + hybrid MCP + human-in-the-loop.

## 1 minute picture

```
User request
    → Input guardrail (galat? STOP)
    → Supervisor (kaun se agents?)
    → Sirf selected agents + unke MCP
    → Shared TravelState
    → Human: Approve / Change
    → Final response (approval ke baad hi)
    → PostgreSQL (conversation + checkpoint)
```

## Guardrail — 1 mark

File: `guardrails.py`

Tripwire ka matlab: **aage mat jao**.

1. Harmful words → block  
2. Homework/code aur travel words nahi → block  
3. Travel words (trip, hotel, Dubai…) → pass  

**Limitation (yeh poochhein ge):**  
Keyword list meaning nahi samajhti.  
“I need four days in Dubai” travel hai lekin “travel” word missing ho sakta hai.  
“hack this trip” mein “trip” hai lekin request kharab hai.  
Isliye keyword guardrail perfect nahi.

## Supervisor — 1 mark

File: `supervisor.py` → function `choose_agents`

Teen cases, koi hidden magic nahi:

| Case | Agents | Kyun |
|---|---|---|
| Full trip (Karachi→Dubai example) | flight, hotel, weather, budget, itinerary | user ne poora plan maanga |
| Hotel-only | hotel (+ budget if PKR) | flight/weather bekaar hain |
| “cheaper hotel, remove expensive activities” | hotel, budget, itinerary | flight/weather pehle se state mein hain |

**Line jo sir ko bolni hai:**  
“Supervisor execute nahi karta. Woh sirf select karta hai. Workflow phir `if agent in selected` se chalta hai.”

## MCP — 5 marks

| Agent | MCP type | Transport | File |
|---|---|---|---|
| Flight | local Aviationstack | STDIO | `mcp_servers/aviationstack_server.py` |
| Hotel | remote Tavily | Streamable HTTP | `mcp_servers/tavily_hotel_server.py` |
| Weather | local custom | STDIO | `mcp_servers/weather_server.py` |
| Budget | LLM estimate | — | labelled **ESTIMATE** |
| Itinerary | combines results | — | day-wise plan |

Hybrid = local + remote + custom, Week 7 slide 40.

Retrieved vs estimate:

- `[RETRIEVED via … MCP]` = tool se aaya  
- `[ESTIMATE]` = budget guess, ticket price nahi  
- `[UNAVAILABLE]` = API fail, fake fare nahi  
- `[SAMPLE DATA — labelled]` = demo only, live quote nahi

## Shared state + PostgreSQL — 1 mark

`TravelState` = ek hi box jisme query, constraints, results, messages, llm_calls.

Do tables:

- `conversations` = baat ka log  
- `state_checkpoints` = us thread ka snapshot  

**Resume:** same `thread_id` se last checkpoint wapas.

**Checkpoint vs preference (yeh poochhein ge):**

- Checkpoint = *is* trip / *is* thread ka moment (draft itinerary).  
- Long-term preference = har trip pe “vegetarian / window seat”. Yeh assignment mein alag profile nahi.

## Human review — 1 mark

Draft dikhao → user **Approve** ya **Change**.  
Change pe supervisor phir se choose karta hai.  
Final agent **sirf approve ke baad**. Booking nahi.

## Tests — 1 mark

```bash
python main.py --demo blocked      # guardrail
python main.py --demo hotel-only   # flight/weather skip
python main.py --demo valid        # full request + resume
python main.py --demo multi        # 5 agents
python main.py --demo revision     # change then approve
python main.py --demo api-failure  # no fake flights
```
