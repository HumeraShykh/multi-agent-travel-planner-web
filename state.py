"""Shared TravelState — the cross-agent context from the lecture architecture."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

AgentName = Literal["flight", "hotel", "weather", "budget", "itinerary"]
ApprovalStatus = Literal["pending", "approved", "changes_requested", "blocked"]
DataSource = Literal[
    "aviationstack_mcp",
    "tavily_mcp",
    "weather_mcp",
    "llm_estimate",
    "unavailable",
    "sample_labelled",
]


class TripConstraints(BaseModel):
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


class SourcedPayload(BaseModel):
    """Every specialist result must say whether it was retrieved, estimated, or unavailable."""

    source: DataSource
    label: str
    content: str
    raw: dict[str, Any] = Field(default_factory=dict)
    limitation: str | None = None


class Message(BaseModel):
    role: str
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TravelState(BaseModel):
    thread_id: str = Field(default_factory=lambda: f"thread-{uuid4().hex[:12]}")
    user_query: str = ""
    trip_constraints: TripConstraints = Field(default_factory=TripConstraints)
    selected_agents: list[AgentName] = Field(default_factory=list)
    selection_rationale: str = ""
    flight_results: SourcedPayload | None = None
    hotel_results: SourcedPayload | None = None
    weather_info: SourcedPayload | None = None
    budget_analysis: SourcedPayload | None = None
    itinerary_plan: SourcedPayload | None = None
    final_response: str | None = None
    messages: list[Message] = Field(default_factory=list)
    llm_calls: int = 0
    approval_status: ApprovalStatus = "pending"
    revision_notes: str | None = None
    guardrail_reason: str | None = None

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(Message(role=role, content=content))

    def bump_llm(self, n: int = 1) -> None:
        self.llm_calls += n

    def to_checkpoint_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_checkpoint_json(cls, payload: str | dict[str, Any]) -> "TravelState":
        if isinstance(payload, str):
            payload = json.loads(payload)
        return cls.model_validate(payload)

    def specialist_context(self) -> str:
        """Compact view of retrieved specialist output for later agents."""
        blocks: list[str] = []
        if self.flight_results:
            blocks.append(f"FLIGHTS ({self.flight_results.label}):\n{self.flight_results.content}")
        if self.hotel_results:
            blocks.append(f"HOTELS ({self.hotel_results.label}):\n{self.hotel_results.content}")
        if self.weather_info:
            blocks.append(f"WEATHER ({self.weather_info.label}):\n{self.weather_info.content}")
        if self.budget_analysis:
            blocks.append(f"BUDGET ({self.budget_analysis.label}):\n{self.budget_analysis.content}")
        return "\n\n".join(blocks) if blocks else "No specialist results yet."
