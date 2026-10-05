"""PostgreSQL persistence: conversations + workflow checkpoints.

A checkpoint is a snapshot of THIS thread's workflow (selected agents, draft
itinerary, approval status). That is different from long-term user preferences
such as 'always book window seats', which would live across many trips.
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from config import DATABASE_URL
from state import TravelState

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id          BIGSERIAL PRIMARY KEY,
    thread_id   TEXT        NOT NULL,
    role        TEXT        NOT NULL,
    content     TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conversations_thread
    ON conversations (thread_id, created_at);

CREATE TABLE IF NOT EXISTS state_checkpoints (
    id          BIGSERIAL PRIMARY KEY,
    thread_id   TEXT        NOT NULL,
    state_json  JSONB       NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_thread
    ON state_checkpoints (thread_id, created_at DESC);
"""


def connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db() -> None:
    with connect() as conn:
        conn.execute(SCHEMA_SQL)
        conn.commit()


def save_message(thread_id: str, role: str, content: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO conversations (thread_id, role, content) VALUES (%s, %s, %s)",
            (thread_id, role, content),
        )
        conn.commit()


def load_messages(thread_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content, created_at
            FROM conversations
            WHERE thread_id = %s
            ORDER BY created_at
            """,
            (thread_id,),
        ).fetchall()
    return list(rows)


def save_checkpoint(state: TravelState) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO state_checkpoints (thread_id, state_json) VALUES (%s, %s)",
            (state.thread_id, Json(state.model_dump())),
        )
        conn.commit()


def load_latest_checkpoint(thread_id: str) -> TravelState | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT state_json
            FROM state_checkpoints
            WHERE thread_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (thread_id,),
        ).fetchone()
    if not row:
        return None
    return TravelState.from_checkpoint_json(row["state_json"])


def persist_turn(state: TravelState, role: str | None = None, content: str | None = None) -> None:
    """Save an optional conversation line plus a full workflow checkpoint."""
    if role and content:
        state.add_message(role, content)
        save_message(state.thread_id, role, content)
    save_checkpoint(state)
