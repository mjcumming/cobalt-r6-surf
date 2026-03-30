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


def build_nmea2000_can_id(
    *,
    priority: int,
    pgn: int,
    source_address: int,
    destination_address: int | None = None,
) -> int:
    """Build a 29-bit NMEA 2000 extended CAN identifier.

    For PDU1 (PF < 240), ``pgn`` must have its low byte zero; ``destination_address``
    is the PDU specific byte (use ``255`` for global when omitted). For PDU2
    (PF >= 240), ``destination_address`` must be ``None``; the low byte of ``pgn``
    supplies PDU specific.
    """

    if not 0 <= priority <= 7:
        raise ValueError("priority must be 0..7")
    if not 0 <= source_address <= 255:
        raise ValueError("source_address must be 0..255")

    data_page = (pgn >> 16) & 0x1
    pdu_format = (pgn >> 8) & 0xFF

    if pdu_format < 240:
        if (pgn & 0xFF) != 0:
            raise ValueError("PDU1-style PGN must have low byte 0")
        dest = destination_address if destination_address is not None else 255
        if not 0 <= dest <= 255:
            raise ValueError("destination_address must be 0..255")
        pdu_specific = dest
    else:
        if destination_address is not None:
            raise ValueError("PDU2-style PGN must not set destination_address")
        pdu_specific = pgn & 0xFF

    return (
        ((priority & 0x7) << 26)
        | ((data_page & 0x1) << 24)
        | ((pdu_format & 0xFF) << 16)
        | ((pdu_specific & 0xFF) << 8)
        | (source_address & 0xFF)
    )
