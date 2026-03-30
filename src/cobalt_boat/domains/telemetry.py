"""Live boat telemetry derived from CANboat-decoded NMEA 2000 messages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from cobalt_boat.can.models import DecodedCanMessage


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        # analyzer sometimes appends units: "12.3 °C"
        parts = s.replace("°", " ").split()
        if not parts:
            return None
        try:
            return float(parts[0])
        except ValueError:
            return None
    return None


def _normalize_celsius(raw: float) -> float:
    """Heuristic: CANboat/NMEA often uses Kelvin * 0.01 stored as a large raw value.

    If the value looks like Kelvin (> 200), convert to °C; otherwise assume °C already.
    """

    if raw > 200.0:
        return raw - 273.15
    return raw


@dataclass
class TelemetryValue:
    value: float | None
    updated_at: str | None


class BoatTelemetryStore:
    """Thread-safe last-known values for common navigation/engine PGNs.

    Field names follow CANboat analyzer output for the referenced PGNs (see canboat ``pgn.h``).
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._rpm: float | None = None
        self._rpm_at: datetime | None = None
        self._coolant_c: float | None = None
        self._coolant_at: datetime | None = None
        self._speed_water: float | None = None
        self._speed_water_at: datetime | None = None
        self._sog: float | None = None
        self._sog_at: datetime | None = None
        self._latitude: float | None = None
        self._longitude: float | None = None
        self._position_at: datetime | None = None

    def record(self, observed_at: datetime, msg: DecodedCanMessage) -> None:
        if msg.pgn is None or not msg.fields:
            return
        fields = msg.fields
        with self._lock:
            if msg.pgn == 127488:
                rpm = _to_float(fields.get("Speed"))
                if rpm is not None:
                    self._rpm = rpm
                    self._rpm_at = observed_at

            elif msg.pgn == 127489:
                # CANboat labels the coolant-related temperature field as "Temperature"
                # (after oil temperature) — see Engine Parameters, Dynamic.
                for key in ("Temperature", "Engine Coolant Temperature", "Coolant Temperature"):
                    t_raw = _to_float(fields.get(key))
                    if t_raw is not None:
                        self._coolant_c = _normalize_celsius(t_raw)
                        self._coolant_at = observed_at
                        break

            elif msg.pgn == 128259:
                v = _to_float(fields.get("Speed Water Referenced"))
                if v is not None:
                    self._speed_water = v
                    self._speed_water_at = observed_at

            elif msg.pgn == 129026:
                v = _to_float(fields.get("SOG"))
                if v is not None:
                    self._sog = v
                    self._sog_at = observed_at

            elif msg.pgn in (129025, 129029):
                lat = _to_float(fields.get("Latitude"))
                lon = _to_float(fields.get("Longitude"))
                if lat is not None and lon is not None:
                    self._latitude = lat
                    self._longitude = lon
                    self._position_at = observed_at

    def _tv(self, value: float | None, ts: datetime | None) -> TelemetryValue:
        if value is None or ts is None:
            return TelemetryValue(value=None, updated_at=None)
        return TelemetryValue(
            value=value,
            updated_at=ts.astimezone(timezone.utc).isoformat(),
        )

    def as_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "engine_rpm": self._tv(self._rpm, self._rpm_at).__dict__,
                "engine_coolant_c": self._tv(self._coolant_c, self._coolant_at).__dict__,
                "speed_water_mps": self._tv(self._speed_water, self._speed_water_at).__dict__,
                "speed_over_ground_mps": self._tv(self._sog, self._sog_at).__dict__,
                "latitude": self._tv(self._latitude, self._position_at).__dict__,
                "longitude": self._tv(self._longitude, self._position_at).__dict__,
                "notes": (
                    "Values appear when the bus sends the matching PGNs and CANboat supplies "
                    "`fields` (e.g. 127488 Speed, 127489 Temperature, 128259 Speed Water "
                    "Referenced, 129026 SOG, 129025/129029 Latitude/Longitude)."
                ),
            }
