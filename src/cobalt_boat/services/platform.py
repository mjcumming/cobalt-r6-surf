"""Platform service wiring ingest, storage, and status queries."""

from __future__ import annotations

import logging
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cobalt_boat.can.capture import CaptureManager
from cobalt_boat.can.decoder import CanDecoder
from cobalt_boat.can.interface import SocketCanInterfaceManager
from cobalt_boat.can.models import CanEvent
from cobalt_boat.can.nmea2000 import parse_nmea2000_id
from cobalt_boat.can.socketcan import SocketCanListener
from cobalt_boat.config import Settings
from cobalt_boat.domains.commands import CommandPreviewResult
from cobalt_boat.domains.garmin_switching import (
    build_default_switch_bank_profile,
    build_switch_bank_profile_from_template,
    default_switch_bank_template,
)
from cobalt_boat.domains.state import HealthStatus, SystemStatus, capture_session_id
from cobalt_boat.events import EventBus
from cobalt_boat.safety.models import CommandRequest
from cobalt_boat.safety.policy import PolicyEngine
from cobalt_boat.storage.db import Database
from cobalt_boat.storage.repositories import (
    MessageCatalogRepository,
    PgnWatchlistRepository,
    SystemEventRepository,
    CaptureAnnotationRepository,
    CaptureAnnotationEntry,
    GarminSwitchBankRepository,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class PlatformRuntime:
    """Stateful runtime components."""

    settings: Settings
    database: Database
    event_bus: EventBus
    capture_manager: CaptureManager
    catalog_repository: MessageCatalogRepository
    watchlist_repository: PgnWatchlistRepository
    annotation_repository: CaptureAnnotationRepository
    garmin_switch_bank_repository: GarminSwitchBankRepository
    system_event_repository: SystemEventRepository
    policy_engine: PolicyEngine
    interface_manager: SocketCanInterfaceManager
    decoder: CanDecoder
    can_listener: SocketCanListener


class PlatformService:
    """Service facade for lifecycle and query (read-side) operations."""

    def __init__(self, runtime: PlatformRuntime) -> None:
        self._runtime = runtime
        self._decoder_faulted = False

    def start(self) -> None:
        self._decoder_faulted = False
        self._runtime.database.initialize()
        if self._runtime.settings.auto_configure_can_interface:
            self._runtime.interface_manager.ensure_up()
        if self._runtime.settings.decoder_required and not self._runtime.decoder.is_ready():
            self._runtime.system_event_repository.log_event(
                "decoder_unavailable",
                {"decoder_required": True},
            )
            raise RuntimeError("required decoder is unavailable")
        self._runtime.can_listener.start()
        self._runtime.system_event_repository.log_event(
            "platform_started",
            {
                "can_interface": self._runtime.settings.can_interface,
                "read_only_mode": self._runtime.settings.read_only_mode,
            },
        )
        LOGGER.info("platform_started can_interface=%s", self._runtime.settings.can_interface)

    def stop(self) -> None:
        self._runtime.can_listener.stop()
        self._runtime.decoder.close()
        stopped = self.stop_capture()
        self._runtime.system_event_repository.log_event(
            "platform_stopped",
            {"capture_stopped": stopped is not None, "capture_session_id": stopped},
        )

    def on_can_event(self, event: CanEvent) -> None:
        try:
            decoded = self._runtime.decoder.decode(event)
        except Exception as exc:
            self._decoder_faulted = True
            self._runtime.system_event_repository.log_event(
                "decoder_error",
                {"error": str(exc), "can_id": event.frame.can_id},
            )
            LOGGER.exception("decoder_failed can_id=%s", event.frame.can_id)
            return
        self._runtime.catalog_repository.record_event(event)
        self._runtime.event_bus.publish("can.frame_observed", event)
        self._runtime.event_bus.publish("can.message_decoded", decoded)

    def start_capture(self) -> str:
        """Start a raw frame capture session and return session identifier."""

        session = self._runtime.capture_manager.start()
        self._runtime.system_event_repository.log_event(
            "capture_started",
            {"session_id": session.session_id, "file_path": str(session.file_path)},
        )
        return session.session_id

    def stop_capture(self) -> str | None:
        """Stop active capture session and return session identifier if present."""

        session = self._runtime.capture_manager.stop()
        if session is None:
            return None
        self._runtime.system_event_repository.log_event(
            "capture_stopped",
            {"session_id": session.session_id, "file_path": str(session.file_path)},
        )
        return session.session_id

    def status(self) -> SystemStatus:
        settings = self._runtime.settings
        session = self._runtime.capture_manager.session
        return SystemStatus(
            read_only_mode=settings.read_only_mode,
            write_enable=settings.write_enable,
            emergency_disable=settings.emergency_disable,
            can_interface=settings.can_interface,
            capture_active=session is not None,
            capture_session_id=capture_session_id(session),
        )

    def garmin_switch_bank_profile(self) -> dict[str, object]:
        """Return simulated NMEA switch bank objects for Garmin interoperability tests."""

        settings = self._runtime.settings
        template = self._runtime.garmin_switch_bank_repository.get_profile()
        if template is None:
            profile = build_default_switch_bank_profile(
                read_only_mode=settings.read_only_mode,
                write_enable=settings.write_enable,
                emergency_disable=settings.emergency_disable,
            )
            return profile.as_dict()
        try:
            profile = build_switch_bank_profile_from_template(
                template=template,
                read_only_mode=settings.read_only_mode,
                write_enable=settings.write_enable,
                emergency_disable=settings.emergency_disable,
            )
        except Exception as exc:
            self._runtime.system_event_repository.log_event(
                "garmin_switch_bank_profile_invalid",
                {"error": str(exc)},
            )
            profile = build_default_switch_bank_profile(
                read_only_mode=settings.read_only_mode,
                write_enable=settings.write_enable,
                emergency_disable=settings.emergency_disable,
            )
        return profile.as_dict()

    def update_garmin_switch_bank_profile(
        self,
        *,
        profile_template: dict[str, object],
        operator: str,
        reason: str,
    ) -> dict[str, object]:
        """Persist validated switch-bank template and return effective runtime profile."""

        previous = self._runtime.garmin_switch_bank_repository.get_profile()
        self._runtime.garmin_switch_bank_repository.upsert_profile(profile_template)
        self._runtime.system_event_repository.log_event(
            "garmin_switch_bank_profile_updated",
            {
                "operator": operator,
                "reason": reason,
                "previous_profile": previous,
                "new_profile": profile_template,
            },
        )
        return self.garmin_switch_bank_profile()

    def default_garmin_switch_bank_template(self) -> dict[str, object]:
        """Return immutable default editable template."""

        return default_switch_bank_template()

    def garmin_switch_bank_template(self) -> dict[str, object]:
        """Return current editable template (stored or default)."""

        stored = self._runtime.garmin_switch_bank_repository.get_profile()
        if stored is not None:
            return stored
        return self.default_garmin_switch_bank_template()

    def health(self) -> HealthStatus:
        database_ready = self._runtime.database.ping()
        can_listener_running = self._runtime.can_listener.is_running
        decoder_ready = self._runtime.decoder.is_ready() and not self._decoder_faulted
        return HealthStatus(
            ok=database_ready and can_listener_running and decoder_ready,
            database_ready=database_ready,
            can_listener_running=can_listener_running,
            decoder_ready=decoder_ready,
        )

    def recent_catalog(self, limit: int = 200) -> list[dict[str, object]]:
        """Query recent message catalog entries."""

        return self._runtime.catalog_repository.list_recent(limit=limit)

    def filtered_catalog(
        self, *, limit: int, pgn: int | None, watch_only: bool
    ) -> list[dict[str, object]]:
        """Query catalog with quick filters for debug watch workflows."""

        return self._runtime.catalog_repository.list_recent(
            limit=limit, pgn=pgn, watch_only=watch_only
        )

    def recent_system_events(self, limit: int = 200) -> list[dict[str, object]]:
        """Query recent platform/system events."""

        return self._runtime.system_event_repository.list_recent(limit=limit)

    def list_watchlist(self) -> list[dict[str, object]]:
        """Return all watchlisted PGNs."""

        return self._runtime.watchlist_repository.list_all()

    def upsert_watchlist(self, *, pgn: int, tag: str, note: str) -> list[dict[str, object]]:
        """Create or update watchlist metadata for a PGN."""

        self._runtime.watchlist_repository.upsert(pgn=pgn, tag=tag, note=note)
        self._runtime.system_event_repository.log_event(
            "watchlist_upserted",
            {"pgn": pgn, "tag": tag},
        )
        return self.list_watchlist()

    def remove_watchlist(self, *, pgn: int) -> list[dict[str, object]]:
        """Remove PGN from watchlist."""

        self._runtime.watchlist_repository.delete(pgn=pgn)
        self._runtime.system_event_repository.log_event(
            "watchlist_removed",
            {"pgn": pgn},
        )
        return self.list_watchlist()

    def create_capture_annotation(
        self,
        *,
        session_id: str,
        action_at: datetime,
        action_label: str,
        note: str,
        operator: str,
    ) -> list[dict[str, object]]:
        """Create annotation for a capture session and return updated list."""

        self._runtime.annotation_repository.create(
            CaptureAnnotationEntry(
                session_id=session_id,
                action_at=action_at,
                action_label=action_label,
                note=note,
                operator=operator,
            )
        )
        self._runtime.system_event_repository.log_event(
            "capture_annotation_created",
            {"session_id": session_id, "action_label": action_label, "operator": operator},
        )
        return self.list_capture_annotations(session_id=session_id)

    def list_capture_annotations(self, *, session_id: str) -> list[dict[str, object]]:
        """List annotations for one capture session."""

        return self._runtime.annotation_repository.list_by_session(session_id=session_id)

    def fusion_correlation_report(
        self, *, session_id: str, window_sec: int = 5
    ) -> dict[str, object]:
        """Evaluate Fusion command/status chain correlations for annotated actions."""

        capture_file = self._runtime.settings.capture_dir / f"capture_{session_id}.jsonl"
        annotations = self.list_capture_annotations(session_id=session_id)
        if not capture_file.exists():
            return {
                "session_id": session_id,
                "window_sec": window_sec,
                "total_annotations": len(annotations),
                "matches": 0,
                "confidence": "none",
                "error": f"capture_file_not_found:{capture_file}",
                "results": [],
            }

        frames = self._load_capture_frames(capture_file)
        results: list[dict[str, object]] = []
        matches = 0
        for annotation in annotations:
            action_time = datetime.fromisoformat(str(annotation["action_at"]))
            sequence = [
                frame["pgn"]
                for frame in frames
                if isinstance(frame["pgn"], int)
                and action_time <= frame["timestamp"] <= action_time + timedelta(seconds=window_sec)
            ]

            label = str(annotation["action_label"]).lower()
            target_pgNs = {130582}
            if "source" in label:
                target_pgNs = {130567, 130573, 130569}
            elif "volume" in label or "mute" in label:
                target_pgNs = {130582, 130567}

            chain_ok = self._contains_ordered_chain(sequence, [126208, 59392], target_pgNs)
            if chain_ok:
                matches += 1

            results.append(
                {
                    "annotation_id": annotation["id"],
                    "action_label": annotation["action_label"],
                    "action_at": annotation["action_at"],
                    "observed_pgns": sequence,
                    "chain_matched": chain_ok,
                    "target_pgns": sorted(target_pgNs),
                }
            )

        confidence = "none"
        if matches >= 3:
            confidence = "high"
        elif matches == 2:
            confidence = "medium"
        elif matches == 1:
            confidence = "low"

        return {
            "session_id": session_id,
            "window_sec": window_sec,
            "total_annotations": len(annotations),
            "matches": matches,
            "confidence": confidence,
            "results": results,
        }

    def _load_capture_frames(self, capture_file: Path) -> list[dict[str, object]]:
        frames: list[dict[str, object]] = []
        for line in capture_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            raw_ts = payload.get("timestamp")
            raw_can_id = payload.get("can_id")
            raw_extended = payload.get("is_extended_id")
            if not isinstance(raw_ts, str) or not isinstance(raw_can_id, int):
                continue
            ts = datetime.fromisoformat(raw_ts)
            parsed = parse_nmea2000_id(raw_can_id, bool(raw_extended))
            frames.append({"timestamp": ts, "pgn": parsed.pgn if parsed else None})
        return frames

    def _contains_ordered_chain(
        self, sequence: list[int], required_prefix: list[int], target_pgns: set[int]
    ) -> bool:
        if not sequence:
            return False
        try:
            first = sequence.index(required_prefix[0])
            second = sequence.index(required_prefix[1], first + 1)
        except ValueError:
            return False
        for value in sequence[second + 1 :]:
            if value in target_pgns:
                return True
        return False

    def preview_command(
        self,
        *,
        domain: str,
        command_name: str,
        parameters: dict[str, Any],
        correlation_id: str | None,
    ) -> CommandPreviewResult:
        """Validate command against policy in explicit no-transmit mode."""

        request = CommandRequest(
            domain=domain,
            command_name=command_name,
            parameters=parameters,
            timestamp=datetime.now(tz=timezone.utc),
            correlation_id=correlation_id,
        )
        decision = self._runtime.policy_engine.evaluate(request)
        self._runtime.system_event_repository.log_event(
            "command_preview_evaluated",
            {
                "domain": domain,
                "command_name": command_name,
                "correlation_id": correlation_id,
                "approved": decision.approved,
                "reason": decision.reason,
                "mode": "shadow_no_transmit",
            },
        )
        return CommandPreviewResult(
            domain=domain,
            command_name=command_name,
            parameters=parameters,
            correlation_id=correlation_id,
            approved=decision.approved,
            reason=decision.reason,
        )

    def tail_logs(self, lines: int = 200) -> list[str]:
        """Read last N lines from application log file."""

        log_path: Path = self._runtime.settings.app_log_path
        if not log_path.exists():
            return []
        if lines <= 0:
            return []
        content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return content[-lines:]
