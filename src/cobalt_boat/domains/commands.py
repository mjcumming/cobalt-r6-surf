"""Typed command preview models for shadow-mode control workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CommandPreviewResult:
    """Result for command validation/preview in no-transmit mode."""

    domain: str
    command_name: str
    parameters: dict[str, Any]
    correlation_id: str | None
    approved: bool
    reason: str
    mode: str = "shadow_no_transmit"
    write_transmitted: bool = False
