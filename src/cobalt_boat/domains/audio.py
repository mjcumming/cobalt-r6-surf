"""Audio domain placeholder (read/query abstractions only for Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AudioState:
    """Observed audio state from telemetry."""

    source: str | None = None
    volume: int | None = None
