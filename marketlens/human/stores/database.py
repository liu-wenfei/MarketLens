from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL,
    request_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    current_step INTEGER NOT NULL DEFAULT 0 CHECK (current_step >= 0),
    current_date TEXT,
    experiment_status TEXT NOT NULL DEFAULT 'active',
    completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1))
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    step INTEGER NOT NULL CHECK (step >= 0),
    stock_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('BUY', 'HOLD', 'SELL')),
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
    evidence_sources TEXT NOT NULL,
    rationale TEXT,
    submitted_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    UNIQUE (session_id, request_id),
    UNIQUE (session_id, step)
);

CREATE TABLE IF NOT EXISTS round_completions (
    completion_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    step INTEGER NOT NULL CHECK (step >= 0),
    next_step INTEGER NOT NULL CHECK (next_step > step),
    completed_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    UNIQUE (session_id, request_id),
    UNIQUE (session_id, step)
);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
