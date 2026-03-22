"""Decoder layer for transforming CAN frames into domain-ready messages."""

from __future__ import annotations

import json
import logging
import queue
import shlex
import subprocess
from threading import Lock, Thread
from typing import Protocol

from cobalt_boat.can.models import CanEvent, DecodedCanMessage

LOGGER = logging.getLogger(__name__)


class CanDecoder(Protocol):
    """Decoder interface for converting raw CAN events into structured messages."""

    def decode(self, event: CanEvent) -> DecodedCanMessage: ...

    def is_ready(self) -> bool: ...

    def close(self) -> None: ...


class BasicNmeaDecoder:
    """Baseline NMEA 2000 decoder used in Phase 1."""

    def decode(self, event: CanEvent) -> DecodedCanMessage:
        return DecodedCanMessage(
            decoder_backend="basic",
            pgn=event.pgn,
            source_address=event.source_address,
            destination_address=event.destination_address,
            priority=event.priority,
            payload_hex=event.frame.data_hex,
            fields=None,
        )

    def is_ready(self) -> bool:
        return True

    def close(self) -> None:
        return


class CanboatProcessDecoder:
    """Canboat analyzer process adapter.

    The adapter writes candump-style lines to analyzer stdin and parses one
    JSON object from stdout per input frame.
    """

    def __init__(
        self,
        command: list[str] | tuple[str, ...],
        response_timeout_sec: float = 1.0,
    ) -> None:
        if len(command) == 0:
            raise ValueError("canboat command must not be empty")
        self._command = list(command)
        self._response_timeout_sec = response_timeout_sec
        self._process: subprocess.Popen[str] | None = None
        self._stdout_queue: queue.Queue[str] = queue.Queue()
        self._write_lock = Lock()

    @classmethod
    def from_command_string(
        cls, command: str, response_timeout_sec: float = 1.0
    ) -> "CanboatProcessDecoder":
        """Build process decoder from shell-like command string."""

        return cls(command=shlex.split(command), response_timeout_sec=response_timeout_sec)

    def decode(self, event: CanEvent) -> DecodedCanMessage:
        self._ensure_process()
        assert self._process is not None
        if self._process.stdin is None:
            raise RuntimeError("canboat process stdin unavailable")

        input_line = self._to_candump_line(event)
        with self._write_lock:
            self._process.stdin.write(input_line)
            self._process.stdin.flush()

        response = self._read_json_line()
        if response is None:
            return DecodedCanMessage(
                decoder_backend="canboat",
                pgn=event.pgn,
                source_address=event.source_address,
                destination_address=event.destination_address,
                priority=event.priority,
                payload_hex=event.frame.data_hex,
                fields=None,
            )
        return DecodedCanMessage(
            decoder_backend="canboat",
            pgn=_as_int(response.get("pgn"), fallback=event.pgn),
            source_address=_as_int(response.get("src"), fallback=event.source_address),
            destination_address=_as_int(response.get("dst"), fallback=event.destination_address),
            priority=_as_int(response.get("prio"), fallback=event.priority),
            payload_hex=event.frame.data_hex,
            fields=response.get("fields") if isinstance(response.get("fields"), dict) else None,
        )

    def is_ready(self) -> bool:
        self._ensure_process(silent_fail=True)
        return self._process is not None and self._process.poll() is None

    def close(self) -> None:
        if self._process is None:
            return
        try:
            if self._process.stdin is not None:
                self._process.stdin.close()
            self._process.terminate()
            self._process.wait(timeout=1.0)
        except (OSError, subprocess.SubprocessError):
            self._process.kill()
        finally:
            self._process = None

    def _ensure_process(self, silent_fail: bool = False) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        try:
            self._process = subprocess.Popen(
                self._command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError:
            if not silent_fail:
                raise
            self._process = None
            return

        assert self._process.stdout is not None
        assert self._process.stderr is not None
        Thread(target=self._stdout_reader, args=(self._process.stdout,), daemon=True).start()
        Thread(target=self._stderr_reader, args=(self._process.stderr,), daemon=True).start()
        LOGGER.info("canboat_decoder_started command=%s", " ".join(self._command))

    def _stdout_reader(self, stream: object) -> None:
        for line in stream:  # type: ignore[attr-defined]
            self._stdout_queue.put(line)

    def _stderr_reader(self, stream: object) -> None:
        for line in stream:  # type: ignore[attr-defined]
            LOGGER.debug("canboat_stderr %s", line.strip())

    def _read_json_line(self) -> dict[str, object] | None:
        while True:
            try:
                line = self._stdout_queue.get(timeout=self._response_timeout_sec)
            except queue.Empty:
                return None
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

    def _to_candump_line(self, event: CanEvent) -> str:
        ts = event.frame.timestamp.timestamp()
        can_id = f"{event.frame.can_id:08X}" if event.frame.is_extended_id else f"{event.frame.can_id:03X}"
        return f"({ts:.6f}) {event.frame.channel} {can_id}#{event.frame.data_hex}\n"


def _as_int(value: object, fallback: int | None) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return fallback
    return fallback
