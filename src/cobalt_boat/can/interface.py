"""SocketCAN interface management utilities."""

from __future__ import annotations

import logging
import subprocess

LOGGER = logging.getLogger(__name__)


class SocketCanInterfaceManager:
    """Ensures CAN interface state for passive observation."""

    def __init__(self, interface: str, bitrate: int) -> None:
        self._interface = interface
        self._bitrate = bitrate

    def ensure_up(self) -> bool:
        """Attempt to configure and bring up SocketCAN interface."""

        try:
            subprocess.run(
                ["ip", "link", "set", self._interface, "down"],
                check=False,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "ip",
                    "link",
                    "set",
                    self._interface,
                    "type",
                    "can",
                    "bitrate",
                    str(self._bitrate),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["ip", "link", "set", self._interface, "up"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            LOGGER.warning(
                "socketcan_interface_setup_failed interface=%s bitrate=%d error=%s",
                self._interface,
                self._bitrate,
                exc,
            )
            return False

        LOGGER.info(
            "socketcan_interface_ready interface=%s bitrate=%d",
            self._interface,
            self._bitrate,
        )
        return True
