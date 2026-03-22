"""NMEA 2000 parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Nmea2000Id:
    """Parsed fields from a 29-bit NMEA 2000 CAN ID."""

    priority: int
    pgn: int
    source_address: int
    destination_address: int | None


def parse_nmea2000_id(can_id: int, is_extended_id: bool) -> Nmea2000Id | None:
    """Parse a CAN arbitration ID into NMEA 2000 fields.

    Returns ``None`` when frame is not an extended 29-bit identifier.
    """

    if not is_extended_id:
        return None

    priority = (can_id >> 26) & 0x7
    data_page = (can_id >> 24) & 0x1
    pdu_format = (can_id >> 16) & 0xFF
    pdu_specific = (can_id >> 8) & 0xFF
    source_address = can_id & 0xFF

    if pdu_format < 240:
        pgn = (data_page << 16) | (pdu_format << 8)
        destination_address: int | None = pdu_specific
    else:
        pgn = (data_page << 16) | (pdu_format << 8) | pdu_specific
        destination_address = None

    return Nmea2000Id(
        priority=priority,
        pgn=pgn,
        source_address=source_address,
        destination_address=destination_address,
    )
