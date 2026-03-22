"""Read-only SocketCAN listener."""

from __future__ import annotations

import logging
from threading import Event, Thread
from typing import Protocol

from cobalt_boat.can.capture import CaptureManager
from cobalt_boat.can.models import CanEvent, RawCanFrame
from cobalt_boat.can.nmea2000 import parse_nmea2000_id

LOGGER = logging.getLogger(__name__)


class CanEventSink(Protocol):
    """Consumer interface for CAN events."""

    def __call__(self, event: CanEvent) -> None: ...


class SocketCanListener:
    """Background SocketCAN listener that emits structured read-only events."""

    def __init__(
        self,
        interface: str,
        event_sink: CanEventSink,
        capture_manager: CaptureManager | None = None,
    ) -> None:
        self._interface = interface
        self._event_sink = event_sink
        self._capture_manager = capture_manager
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._running = False

    def start(self) -> None:
        """Start background listener thread."""

        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, name="socketcan-listener", daemon=True)
        self._thread.start()

    def stop(self, timeout_sec: float = 2.0) -> None:
        """Stop listener thread."""

        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout_sec)

    def _run(self) -> None:
        try:
            import can
        except ImportError:
            LOGGER.exception("python-can is required for SocketCAN integration")
            return

        try:
            bus = can.Bus(interface="socketcan", channel=self._interface)
        except Exception:
            LOGGER.exception("failed_to_open_socketcan interface=%s", self._interface)
            return

        self._running = True
        LOGGER.info("socketcan_listener_started interface=%s", self._interface)
        try:
            while not self._stop_event.is_set():
                message = bus.recv(timeout=0.25)
                if message is None:
                    continue

                frame = RawCanFrame.from_python_can(
                    timestamp_s=message.timestamp,
                    arbitration_id=message.arbitration_id,
                    is_extended_id=message.is_extended_id,
                    dlc=message.dlc,
                    data=bytes(message.data),
                    channel=str(message.channel or self._interface),
                )
                parsed = parse_nmea2000_id(frame.can_id, frame.is_extended_id)
                event = CanEvent(
                    frame=frame,
                    pgn=parsed.pgn if parsed else None,
                    source_address=parsed.source_address if parsed else None,
                    destination_address=parsed.destination_address if parsed else None,
                    priority=parsed.priority if parsed else None,
                )
                if self._capture_manager is not None:
                    self._capture_manager.write_frame(frame)
                try:
                    self._event_sink(event)
                except Exception:
                    LOGGER.exception("can_event_sink_failed interface=%s", self._interface)
        finally:
            try:
                bus.shutdown()
            except Exception:
                LOGGER.debug("socketcan_bus_shutdown_failed interface=%s", self._interface)
            self._running = False
            LOGGER.info("socketcan_listener_stopped interface=%s", self._interface)

    @property
    def is_running(self) -> bool:
        """Return whether the listener loop is currently active."""

        return self._running
