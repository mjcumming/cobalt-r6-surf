"""Typed models for CAN frames and decoded metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class RawCanFrame:
    """Normalized representation of a CAN frame."""

    timestamp: datetime
    can_id: int
    is_extended_id: bool
    dlc: int
    data_hex: str
    channel: str

    @classmethod
    def from_python_can(
        cls,
        *,
        timestamp_s: float,
        arbitration_id: int,
        is_extended_id: bool,
        dlc: int,
        data: bytes,
        channel: str,
    ) -> "RawCanFrame":
        return cls(
            timestamp=datetime.fromtimestamp(timestamp_s, tz=timezone.utc),
            can_id=arbitration_id,
            is_extended_id=is_extended_id,
            dlc=dlc,
            data_hex=data.hex(),
            channel=channel,
        )


@dataclass(frozen=True)
class CanEvent:
    """Structured CAN event enriched with NMEA 2000 metadata."""

    frame: RawCanFrame
    pgn: int | None
    source_address: int | None
    destination_address: int | None
    priority: int | None


@dataclass(frozen=True)
class DecodedCanMessage:
    """Decoded message representation produced by decoder layer."""

    decoder_backend: str
    pgn: int | None
    source_address: int | None
    destination_address: int | None
    priority: int | None
    payload_hex: str
    fields: dict[str, Any] | None = None
