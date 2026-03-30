"""Offline candump fixtures → frame → NMEA 2000 metadata."""

from __future__ import annotations

from pathlib import Path

from cobalt_boat.can.candump_parse import candump_line_to_can_event, parse_candump_line
from cobalt_boat.can.decoder import BasicNmeaDecoder

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "office_sample.candump"


def _fixture_lines() -> list[str]:
    return [
        ln
        for ln in FIXTURE.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def test_office_sample_candump_parses() -> None:
    lines = _fixture_lines()
    assert len(lines) == 3
    frames = [parse_candump_line(ln) for ln in lines]
    assert all(f is not None for f in frames)
    assert frames[0] is not None and frames[0].data_hex == "0102030405060708"
    assert frames[0].can_id == 0x19F20120
    assert frames[2] is not None and frames[2].can_id == 0x0CEAFF15


def test_office_sample_can_events_match_pgns() -> None:
    events = [candump_line_to_can_event(ln) for ln in _fixture_lines()]
    assert all(e is not None for e in events)
    assert events[0] is not None and events[0].pgn == 127489
    assert events[0].source_address == 0x20
    assert events[2] is not None
    assert events[2].pgn == 59904
    assert events[2].destination_address == 0xFF
    assert events[2].source_address == 0x15


def test_basic_decoder_accepts_fixture_events() -> None:
    decoder = BasicNmeaDecoder()
    for ln in _fixture_lines():
        event = candump_line_to_can_event(ln)
        assert event is not None
        decoded = decoder.decode(event)
        assert decoded.pgn == event.pgn
        assert decoded.source_address == event.source_address
