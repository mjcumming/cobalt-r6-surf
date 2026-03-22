from __future__ import annotations

import sys
from datetime import datetime, timezone

from cobalt_boat.can.decoder import BasicNmeaDecoder, CanboatProcessDecoder
from cobalt_boat.can.models import CanEvent, RawCanFrame


def make_event() -> CanEvent:
    frame = RawCanFrame(
        timestamp=datetime.now(tz=timezone.utc),
        can_id=0x19F20120,
        is_extended_id=True,
        dlc=8,
        data_hex="0102030405060708",
        channel="can0",
    )
    return CanEvent(
        frame=frame,
        pgn=127489,
        source_address=0x20,
        destination_address=None,
        priority=6,
    )


def test_basic_decoder_maps_event() -> None:
    decoded = BasicNmeaDecoder().decode(make_event())

    assert decoded.decoder_backend == "basic"
    assert decoded.pgn == 127489
    assert decoded.source_address == 0x20


def test_canboat_process_decoder_parses_json_output() -> None:
    script = (
        "import json,sys\n"
        "for line in sys.stdin:\n"
        "  if not line.strip():\n"
        "    continue\n"
        "  print(json.dumps({'pgn':127501,'src':32,'dst':255,'prio':3,'fields':{'name':'Lighting'}}), flush=True)\n"
    )

    decoder = CanboatProcessDecoder(
        command=[sys.executable, "-u", "-c", script],
        response_timeout_sec=1.0,
    )
    try:
        decoded = decoder.decode(make_event())
    finally:
        decoder.close()

    assert decoded.decoder_backend == "canboat"
    assert decoded.pgn == 127501
    assert decoded.source_address == 32
    assert decoded.destination_address == 255
    assert decoded.priority == 3
    assert decoded.fields == {"name": "Lighting"}


def test_canboat_process_decoder_handles_no_output_timeout() -> None:
    script = (
        "import sys,time\n"
        "for _line in sys.stdin:\n"
        "  time.sleep(0.2)\n"
    )
    event = make_event()
    decoder = CanboatProcessDecoder(
        command=[sys.executable, "-u", "-c", script],
        response_timeout_sec=0.05,
    )
    try:
        decoded = decoder.decode(event)
    finally:
        decoder.close()

    assert decoded.decoder_backend == "canboat"
    assert decoded.pgn == event.pgn
    assert decoded.source_address == event.source_address
    assert decoded.fields is None
