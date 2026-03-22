from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from cobalt_boat.can.models import CanEvent, RawCanFrame
from cobalt_boat.storage.db import Database
from cobalt_boat.storage.repositories import MessageCatalogRepository


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


def test_message_catalog_upserts_and_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "catalog.db"
    db = Database(db_path)
    db.initialize()
    repo = MessageCatalogRepository(db)

    event = make_event()
    repo.record_event(event)
    repo.record_event(event)

    with db.connect() as connection:
        row = connection.execute(
            "SELECT pgn, source_address, destination_address, count FROM message_catalog"
        ).fetchone()

    assert row is not None
    assert row["pgn"] == 127489
    assert row["source_address"] == 0x20
    assert row["destination_address"] is None
    assert row["count"] == 2
