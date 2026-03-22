from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from cobalt_boat.config import Settings
from cobalt_boat.safety.models import CommandRequest
from cobalt_boat.safety.policy import PolicyEngine
from cobalt_boat.storage.db import Database
from cobalt_boat.storage.repositories import AuditLogRepository


def make_engine(tmp_path: Path, *, read_only: bool = True, write_enable: bool = False) -> PolicyEngine:
    db = Database(tmp_path / "policy.db")
    db.initialize()
    settings = Settings(
        sqlite_path=tmp_path / "policy.db",
        read_only_mode=read_only,
        write_enable=write_enable,
        emergency_disable=False,
    )
    return PolicyEngine(settings=settings, audit_log_repository=AuditLogRepository(db))


def test_policy_denies_when_read_only_enabled(tmp_path: Path) -> None:
    engine = make_engine(tmp_path, read_only=True, write_enable=False)
    request = CommandRequest(
        domain="audio",
        command_name="set_volume",
        parameters={"zone": "cockpit", "level": 10},
        timestamp=datetime.now(tz=timezone.utc),
    )

    decision = engine.evaluate(request)

    assert decision.approved is False
    assert decision.reason == "read_only_mode_enabled"


def test_policy_denies_non_whitelisted_command(tmp_path: Path) -> None:
    engine = make_engine(tmp_path, read_only=False, write_enable=True)
    request = CommandRequest(
        domain="audio",
        command_name="factory_reset",
        parameters={},
        timestamp=datetime.now(tz=timezone.utc),
    )

    decision = engine.evaluate(request)

    assert decision.approved is False
    assert decision.reason == "command_not_whitelisted"


def test_policy_approves_allowed_command(tmp_path: Path) -> None:
    engine = make_engine(tmp_path, read_only=False, write_enable=True)
    request = CommandRequest(
        domain="lighting",
        command_name="set_brightness",
        parameters={"zone": "underwater", "level": 50},
        timestamp=datetime.now(tz=timezone.utc),
    )

    decision = engine.evaluate(request)

    assert decision.approved is True
    assert decision.reason == "approved"
