from __future__ import annotations

from datetime import datetime, timezone

from cobalt_boat.can.models import DecodedCanMessage
from cobalt_boat.domains.telemetry import BoatTelemetryStore


def test_telemetry_maps_engine_and_speed_pgns() -> None:
    store = BoatTelemetryStore()
    ts = datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc)

    store.record(
        ts,
        DecodedCanMessage(
            decoder_backend="canboat",
            pgn=127488,
            source_address=0,
            destination_address=None,
            priority=2,
            payload_hex="",
            fields={"Speed": 2800.0},
        ),
    )
    store.record(
        ts,
        DecodedCanMessage(
            decoder_backend="canboat",
            pgn=128259,
            source_address=0,
            destination_address=None,
            priority=2,
            payload_hex="",
            fields={"Speed Water Referenced": 5.14},
        ),
    )
    store.record(
        ts,
        DecodedCanMessage(
            decoder_backend="canboat",
            pgn=129025,
            source_address=0,
            destination_address=None,
            priority=2,
            payload_hex="",
            fields={"Latitude": 44.95, "Longitude": -93.09},
        ),
    )

    out = store.as_dict()
    assert out["engine_rpm"]["value"] == 2800.0
    assert out["speed_water_mps"]["value"] == 5.14
    assert out["latitude"]["value"] == 44.95
    assert out["longitude"]["value"] == -93.09
