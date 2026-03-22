"""Safety policy domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

ALLOWED_DOMAINS = {"audio", "lighting"}
DENIED_DOMAINS = {"engine", "propulsion", "steering", "surf", "ballast", "trim"}


@dataclass(frozen=True)
class CommandRequest:
    """Typed command request entering safety policy evaluation."""

    domain: str
    command_name: str
    parameters: dict[str, Any]
    timestamp: datetime
    correlation_id: str | None = None


@dataclass(frozen=True)
class PolicyDecision:
    """Decision returned by the safety policy engine."""

    approved: bool
    reason: str
