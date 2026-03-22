"""In-process event bus primitives."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class EventEnvelope:
    """Wrapper for events moving through the internal pub/sub bus."""

    event_type: str
    payload: Any
    occurred_at: datetime


EventHandler = Callable[[EventEnvelope], None]


class EventBus:
    """Simple synchronous pub/sub event bus.

    Synchronous dispatch keeps behavior explicit and predictable for Phase 1.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event_type: str, payload: Any) -> EventEnvelope:
        envelope = EventEnvelope(
            event_type=event_type,
            payload=payload,
            occurred_at=datetime.now(tz=timezone.utc),
        )
        for handler in self._subscribers.get(event_type, []):
            handler(envelope)
        return envelope
