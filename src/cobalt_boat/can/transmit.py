"""SocketCAN transmit (lab / gated production use)."""

from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


class SocketCanTransmitter:
    """Sends extended frames on a SocketCAN interface (lazy ``python-can`` bus open)."""

    def __init__(self, interface: str) -> None:
        self._interface = interface
        self._bus: Any = None

    def send_extended(self, arbitration_id: int, data: bytes) -> None:
        """Send one extended-ID data frame (DLC 0..8)."""

        if len(data) > 8:
            raise ValueError("CAN classic data payload must be at most 8 bytes")
        try:
            import can
        except ImportError as exc:
            raise RuntimeError("python-can is required for CAN transmit") from exc

        if self._bus is None:
            self._bus = can.Bus(interface="socketcan", channel=self._interface)
            LOGGER.info("socketcan_transmitter_opened interface=%s", self._interface)

        msg = can.Message(
            arbitration_id=arbitration_id & 0x1FFFFFFF,
            data=data,
            is_extended_id=True,
        )
        self._bus.send(msg)

    def close(self) -> None:
        if self._bus is not None:
            try:
                self._bus.shutdown()
            except Exception:
                LOGGER.debug("socketcan_transmitter_shutdown_failed", exc_info=True)
            self._bus = None
