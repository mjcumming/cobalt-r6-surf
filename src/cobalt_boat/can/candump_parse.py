"""Parse candump-style log lines into ``RawCanFrame`` for offline testing."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from cobalt_boat.can.models import CanEvent, RawCanFrame
from cobalt_boat.can.nmea2000 import parse_nmea2000_id

# (timestamp) channel 19F20120#0102030405060708
_RE_HASH = re.compile(
    r"^\((?P<ts>[-\d.]+)\)\s+(?P<ch>\S+)\s+(?P<cid>[0-9A-Fa-f]+)#(?P<data>[0-9A-Fa-f]*)\s*$"
)

# (timestamp) channel 19F20120 [8] 01 02 03 04 05 06 07 08
_RE_BRACKET = re.compile(
    r"^\((?P<ts>[-\d.]+)\)\s+(?P<ch>\S+)\s+(?P<cid>[0-9A-Fa-f]+)\s+"
    r"\[(?P<dlc>\d+)\]\s+(?P<bytes>(?:[0-9A-Fa-f]{2}\s*)+)\s*$"
)


def parse_candump_line(line: str) -> RawCanFrame | None:
    """Parse one line from a typical ``candump -ta`` or analyzer-style log.

    Returns ``None`` for blank lines, comments, or unrecognized formats.
    """

    text = line.strip()
    if not text or text.startswith("#"):
        return None

    if (m := _RE_HASH.match(text)) is not None:
        ts = float(m.group("ts"))
        data_hex = m.group("data").upper()
        dlc = len(data_hex) // 2 if data_hex else 0
        return _frame_from_parts(
            ts_s=ts,
            channel=m.group("ch"),
            can_id_hex=m.group("cid"),
            dlc=dlc,
            data_hex=data_hex,
        )

    if (m := _RE_BRACKET.match(text)) is not None:
        ts = float(m.group("ts"))
        byte_part = m.group("bytes")
        data_hex = "".join(byte_part.split()).upper()
        dlc_decl = int(m.group("dlc"), 10)
        dlc = dlc_decl if 0 <= dlc_decl <= 8 else len(data_hex) // 2
        return _frame_from_parts(
            ts_s=ts,
            channel=m.group("ch"),
            can_id_hex=m.group("cid"),
            dlc=dlc,
            data_hex=data_hex[: dlc * 2],
        )

    return None


def candump_line_to_can_event(line: str) -> CanEvent | None:
    """Parse a candump line and attach NMEA 2000 metadata when applicable."""

    frame = parse_candump_line(line)
    if frame is None:
        return None
    parsed = parse_nmea2000_id(frame.can_id, frame.is_extended_id)
    return CanEvent(
        frame=frame,
        pgn=parsed.pgn if parsed else None,
        source_address=parsed.source_address if parsed else None,
        destination_address=parsed.destination_address if parsed else None,
        priority=parsed.priority if parsed else None,
    )


def _frame_from_parts(
    *,
    ts_s: float,
    channel: str,
    can_id_hex: str,
    dlc: int,
    data_hex: str,
) -> RawCanFrame:
    cid = can_id_hex.strip()
    can_id = int(cid, 16)
    is_extended = len(cid) > 3
    return RawCanFrame(
        timestamp=datetime.fromtimestamp(ts_s, tz=timezone.utc),
        can_id=can_id,
        is_extended_id=is_extended,
        dlc=dlc,
        data_hex=data_hex,
        channel=channel,
    )
