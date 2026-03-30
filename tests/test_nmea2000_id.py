"""NMEA 2000 CAN ID parsing — validate before any live bus work."""

from __future__ import annotations

import pytest

from cobalt_boat.can.nmea2000 import parse_nmea2000_id


@pytest.mark.parametrize(
    ("can_id", "priority", "pgn", "source", "destination"),
    [
        # Existing regression: PGN 127489 (engine dynamic param), global PDU2, SA 0x20
        (0x19F20120, 6, 127489, 0x20, None),
        # PDU1: PF 0xEA (234) < 240 → PGN 0xEA00 (59904), PS = destination 0xFF
        (0x0CEAFF15, 3, 59904, 0x15, 0xFF),
        # Global PDU2: PGN 127501 switch bank status, SA 0x40
        (0x19F20D40, 6, 127501, 0x40, None),
    ],
)
def test_parse_nmea2000_id_known_frames(
    can_id: int,
    priority: int,
    pgn: int,
    source: int,
    destination: int | None,
) -> None:
    parsed = parse_nmea2000_id(can_id, is_extended_id=True)
    assert parsed is not None
    assert parsed.priority == priority
    assert parsed.pgn == pgn
    assert parsed.source_address == source
    assert parsed.destination_address == destination


def test_parse_nmea2000_id_rejects_standard_11_bit() -> None:
    assert parse_nmea2000_id(0x123, is_extended_id=False) is None
