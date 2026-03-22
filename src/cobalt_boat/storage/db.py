"""SQLite lifecycle and schema setup."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS command_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    domain TEXT NOT NULL,
    command_name TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    approved INTEGER NOT NULL,
    reason TEXT NOT NULL,
    correlation_id TEXT
);

CREATE TABLE IF NOT EXISTS message_catalog (
    pgn INTEGER NOT NULL,
    source_address INTEGER,
    destination_address INTEGER,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    sample_can_id INTEGER NOT NULL,
    sample_data_hex TEXT NOT NULL,
    count INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_message_catalog_key
ON message_catalog (
    pgn,
    COALESCE(source_address, -1),
    COALESCE(destination_address, -1)
);

CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pgn_watchlist (
    pgn INTEGER PRIMARY KEY,
    tag TEXT NOT NULL,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS capture_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    action_at TEXT NOT NULL,
    action_label TEXT NOT NULL,
    note TEXT NOT NULL,
    operator TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS garmin_switch_bank_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    profile_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class Database:
    """SQLite helper that initializes schema and yields connections."""

    def __init__(self, sqlite_path: Path) -> None:
        self._sqlite_path = sqlite_path
        self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        with sqlite3.connect(self._sqlite_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON;")
            connection.executescript(SCHEMA_SQL)
            connection.commit()

    def ping(self) -> bool:
        """Return true when database is reachable and queryable."""

        try:
            with sqlite3.connect(self._sqlite_path) as connection:
                connection.execute("SELECT 1;").fetchone()
            return True
        except sqlite3.Error:
            return False

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._sqlite_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()
