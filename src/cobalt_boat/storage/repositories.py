"""Repository interfaces backed by SQLite."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cobalt_boat.can.models import CanEvent
from cobalt_boat.storage.db import Database


@dataclass(frozen=True)
class CommandAuditEntry:
    """Audit record for command attempts."""

    timestamp: datetime
    domain: str
    command_name: str
    parameters: dict[str, Any]
    approved: bool
    reason: str
    correlation_id: str | None = None


class AuditLogRepository:
    """Persistence for command audit records."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def log_command(self, entry: CommandAuditEntry) -> None:
        with self._db.connect() as connection:
            connection.execute(
                """
                INSERT INTO command_audit (
                    timestamp, domain, command_name, parameters_json,
                    approved, reason, correlation_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.timestamp.isoformat(),
                    entry.domain,
                    entry.command_name,
                    json.dumps(entry.parameters, sort_keys=True),
                    1 if entry.approved else 0,
                    entry.reason,
                    entry.correlation_id,
                ),
            )


class MessageCatalogRepository:
    """Tracks observed PGNs and representative sample messages."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def record_event(self, event: CanEvent) -> None:
        if event.pgn is None:
            return

        now = event.frame.timestamp.astimezone(timezone.utc).isoformat()
        with self._db.connect() as connection:
            connection.execute(
                """
                INSERT INTO message_catalog (
                    pgn, source_address, destination_address,
                    first_seen, last_seen, sample_can_id,
                    sample_data_hex, count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT DO UPDATE SET
                    last_seen=excluded.last_seen,
                    sample_can_id=excluded.sample_can_id,
                    sample_data_hex=excluded.sample_data_hex,
                    count=message_catalog.count + 1
                """,
                (
                    event.pgn,
                    event.source_address,
                    event.destination_address,
                    now,
                    now,
                    event.frame.can_id,
                    event.frame.data_hex,
                ),
            )

    def list_recent(
        self,
        *,
        limit: int = 200,
        pgn: int | None = None,
        watch_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Return most recently seen catalog entries."""

        where_clauses: list[str] = []
        params: list[Any] = []
        if pgn is not None:
            where_clauses.append("mc.pgn = ?")
            params.append(pgn)
        if watch_only:
            where_clauses.append("wl.pgn IS NOT NULL")

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        with self._db.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT mc.pgn, mc.source_address, mc.destination_address,
                       mc.first_seen, mc.last_seen, mc.sample_can_id,
                       mc.sample_data_hex, mc.count,
                       wl.tag AS watch_tag, wl.note AS watch_note
                FROM message_catalog mc
                LEFT JOIN pgn_watchlist wl ON wl.pgn = mc.pgn
                {where_sql}
                ORDER BY mc.last_seen DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [dict(row) for row in rows]


class SystemEventRepository:
    """Stores non-command system-level events."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def log_event(self, event_type: str, details: dict[str, Any]) -> None:
        with self._db.connect() as connection:
            connection.execute(
                """
                INSERT INTO system_events (timestamp, event_type, details_json)
                VALUES (?, ?, ?)
                """,
                (
                    datetime.now(tz=timezone.utc).isoformat(),
                    event_type,
                    json.dumps(details, sort_keys=True),
                ),
            )

    def list_recent(self, limit: int = 200) -> list[dict[str, Any]]:
        """Return recent system events in reverse chronological order."""

        with self._db.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, timestamp, event_type, details_json
                FROM system_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]


class PgnWatchlistRepository:
    """CRUD operations for PGN watchlist tags used by debug tooling."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def upsert(self, *, pgn: int, tag: str, note: str) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        with self._db.connect() as connection:
            connection.execute(
                """
                INSERT INTO pgn_watchlist (pgn, tag, note, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(pgn) DO UPDATE SET
                    tag=excluded.tag,
                    note=excluded.note,
                    updated_at=excluded.updated_at
                """,
                (pgn, tag, note, now, now),
            )

    def delete(self, *, pgn: int) -> None:
        with self._db.connect() as connection:
            connection.execute("DELETE FROM pgn_watchlist WHERE pgn = ?", (pgn,))

    def list_all(self) -> list[dict[str, Any]]:
        with self._db.connect() as connection:
            rows = connection.execute(
                """
                SELECT pgn, tag, note, created_at, updated_at
                FROM pgn_watchlist
                ORDER BY pgn ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]


@dataclass(frozen=True)
class CaptureAnnotationEntry:
    """Operator annotation bound to a capture session timestamp."""

    session_id: str
    action_at: datetime
    action_label: str
    note: str
    operator: str


class CaptureAnnotationRepository:
    """CRUD repository for capture annotations."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, entry: CaptureAnnotationEntry) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        with self._db.connect() as connection:
            connection.execute(
                """
                INSERT INTO capture_annotations (
                    session_id, action_at, action_label, note, operator, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.session_id,
                    entry.action_at.astimezone(timezone.utc).isoformat(),
                    entry.action_label,
                    entry.note,
                    entry.operator,
                    now,
                ),
            )

    def list_by_session(self, session_id: str) -> list[dict[str, Any]]:
        with self._db.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, session_id, action_at, action_label, note, operator, created_at
                FROM capture_annotations
                WHERE session_id = ?
                ORDER BY action_at ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]


class GarminSwitchBankRepository:
    """Persistence for editable Garmin switch-bank simulation profile."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def get_profile(self) -> dict[str, Any] | None:
        with self._db.connect() as connection:
            row = connection.execute(
                """
                SELECT profile_json
                FROM garmin_switch_bank_config
                WHERE id = 1
                """
            ).fetchone()
        if row is None:
            return None
        parsed = json.loads(str(row["profile_json"]))
        if not isinstance(parsed, dict):
            return None
        return parsed

    def upsert_profile(self, profile: dict[str, Any]) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        with self._db.connect() as connection:
            connection.execute(
                """
                INSERT INTO garmin_switch_bank_config (id, profile_json, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    profile_json=excluded.profile_json,
                    updated_at=excluded.updated_at
                """,
                (json.dumps(profile, sort_keys=True), now),
            )
