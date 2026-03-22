"""Raw CAN capture session management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import TextIOWrapper
from pathlib import Path
from threading import Lock

from cobalt_boat.can.models import RawCanFrame


@dataclass(frozen=True)
class CaptureSession:
    """Capture session metadata."""

    session_id: str
    started_at: datetime
    file_path: Path


class CaptureManager:
    """Writes observed raw CAN frames to timestamped file captures."""

    def __init__(self, capture_dir: Path) -> None:
        self._capture_dir = capture_dir
        self._capture_dir.mkdir(parents=True, exist_ok=True)
        self._session: CaptureSession | None = None
        self._file_handle: TextIOWrapper | None = None
        self._lock = Lock()

    def start(self) -> CaptureSession:
        """Start a capture session. Raises when session is already running."""

        with self._lock:
            if self._session is not None:
                raise RuntimeError("capture session already active")
            now = datetime.now(tz=timezone.utc)
            session_id = now.strftime("%Y%m%dT%H%M%S%fZ")
            file_path = self._capture_dir / f"capture_{session_id}.jsonl"
            file_handle = file_path.open("a", encoding="utf-8")
            self._session = CaptureSession(
                session_id=session_id,
                started_at=now,
                file_path=file_path,
            )
            self._file_handle = file_handle
            return self._session

    def stop(self) -> CaptureSession | None:
        """Stop active capture session and close file resources."""

        with self._lock:
            session = self._session
            if self._file_handle is not None:
                self._file_handle.close()
            self._session = None
            self._file_handle = None
            return session

    def write_frame(self, frame: RawCanFrame) -> None:
        """Append a frame into current capture file."""

        with self._lock:
            if self._file_handle is None:
                return
            line = (
                "{"
                f'"timestamp":"{frame.timestamp.isoformat()}",'
                f'"can_id":{frame.can_id},'
                f'"is_extended_id":{str(frame.is_extended_id).lower()},'
                f'"dlc":{frame.dlc},'
                f'"data_hex":"{frame.data_hex}",'
                f'"channel":"{frame.channel}"'
                "}\n"
            )
            self._file_handle.write(line)
            self._file_handle.flush()

    @property
    def session(self) -> CaptureSession | None:
        """Return currently active capture session."""

        return self._session
