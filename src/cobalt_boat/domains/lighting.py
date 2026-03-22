"""Lighting domain placeholder (read/query abstractions only for Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LightingState:
    """Observed lighting state from telemetry."""

    brightness: int | None = None
    color_rgb: tuple[int, int, int] | None = None
