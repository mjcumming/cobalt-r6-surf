"""Fusion / entertainment lab transmit helpers (placeholder payloads).

Real Fusion-Link control on NMEA 2000 typically flows through PGN 126208 and related
fast-packet traffic. The byte patterns here are **distinct placeholders** so you can
verify the transmit path on ``vcan`` with ``candump``; replace with capture-derived
frames after on-vessel validation (see ``docs/fusion-ms-ra600-nmea-guide.md``).
"""

from __future__ import annotations

from typing import Literal

from cobalt_boat.can.nmea2000 import build_nmea2000_can_id
from cobalt_boat.config import Settings

# NMEA 2000 PGN 126208 — NMEA Command / Request / Acknowledge Group Function
PGN_NMEA_COMMAND = 126208

FusionLabKind = Literal["volume_up", "volume_down", "mute_on", "mute_off"]

# Placeholder single-frame payloads (8 bytes). Not valid full 126208 sequences.
_PAYLOADS: dict[FusionLabKind, bytes] = {
    "volume_up": bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    "volume_down": bytes([0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    "mute_on": bytes([0x03, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    "mute_off": bytes([0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
}


def fusion_lab_command_frame(settings: Settings, kind: FusionLabKind) -> tuple[int, bytes]:
    """Return ``(can_id, data)`` for a lab Fusion control stub."""

    can_id = build_nmea2000_can_id(
        priority=settings.lab_transmit_priority,
        pgn=PGN_NMEA_COMMAND,
        source_address=settings.lab_transmit_source_address,
        destination_address=settings.lab_fusion_destination_address,
    )
    return can_id, _PAYLOADS[kind]
