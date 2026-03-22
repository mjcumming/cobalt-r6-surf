"""Shared system state projections for query operations (CQRS read side)."""

from __future__ import annotations

from dataclasses import dataclass

from cobalt_boat.can.capture import CaptureSession


@dataclass(frozen=True)
class SystemStatus:
    """System status exposed by services/API."""

    read_only_mode: bool
    write_enable: bool
    emergency_disable: bool
    can_interface: str
    capture_active: bool
    capture_session_id: str | None


@dataclass(frozen=True)
class HealthStatus:
    """High-level health status."""

    ok: bool
    database_ready: bool
    can_listener_running: bool
    decoder_ready: bool


def capture_session_id(session: CaptureSession | None) -> str | None:
    """Convert optional capture session to API-safe identifier."""

    return session.session_id if session is not None else None
