-- Workflow conversation log (long-term conversation memory for a thread).
CREATE TABLE IF NOT EXISTS conversations (
    id          BIGSERIAL PRIMARY KEY,
    thread_id   TEXT        NOT NULL,
    role        TEXT        NOT NULL,
    content     TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_thread
    ON conversations (thread_id, created_at);

-- Workflow checkpoints: a snapshot of TravelState at a moment in this thread.
-- This is NOT the same as long-term user preferences (see README).
CREATE TABLE IF NOT EXISTS state_checkpoints (
    id          BIGSERIAL PRIMARY KEY,
    thread_id   TEXT        NOT NULL,
    state_json  JSONB       NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_thread
    ON state_checkpoints (thread_id, created_at DESC);
