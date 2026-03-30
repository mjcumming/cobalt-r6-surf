from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from cobalt_boat.can.capture import CaptureManager
from cobalt_boat.can.models import CanEvent, RawCanFrame
from cobalt_boat.config import Settings
from cobalt_boat.domains.telemetry import BoatTelemetryStore
from cobalt_boat.events import EventBus
from cobalt_boat.safety.policy import PolicyEngine
from cobalt_boat.services.platform import PlatformRuntime, PlatformService
from cobalt_boat.storage.db import Database
from cobalt_boat.storage.repositories import (
    AuditLogRepository,
    CaptureAnnotationRepository,
    GarminSwitchBankRepository,
    MessageCatalogRepository,
    PgnWatchlistRepository,
    SystemEventRepository,
)


class _DecoderUnavailable:
    def decode(self, event):  # type: ignore[no-untyped-def]
        raise RuntimeError("not used")

    def is_ready(self) -> bool:
        return False

    def close(self) -> None:
        return


class _NoopListener:
    is_running = False

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False


class _NoopInterfaceManager:
    def ensure_up(self) -> bool:
        return True


class _DecoderFaulty:
    def decode(self, event: CanEvent):  # type: ignore[no-untyped-def]
        raise RuntimeError("decode timeout")

    def is_ready(self) -> bool:
        return True

    def close(self) -> None:
        return


def test_platform_start_fails_if_required_decoder_unavailable(tmp_path: Path) -> None:
    settings = Settings(
        sqlite_path=tmp_path / "cobalt.db",
        data_dir=tmp_path,
        capture_dir=tmp_path / "captures",
        decoder_required=True,
    )
    db = Database(settings.sqlite_path)
    runtime = PlatformRuntime(
        settings=settings,
        database=db,
        event_bus=EventBus(),
        capture_manager=CaptureManager(settings.capture_dir),
        catalog_repository=MessageCatalogRepository(db),
        watchlist_repository=PgnWatchlistRepository(db),
        annotation_repository=CaptureAnnotationRepository(db),
        garmin_switch_bank_repository=GarminSwitchBankRepository(db),
        system_event_repository=SystemEventRepository(db),
        policy_engine=PolicyEngine(settings=settings, audit_log_repository=AuditLogRepository(db)),
        interface_manager=_NoopInterfaceManager(),
        decoder=_DecoderUnavailable(),
        can_listener=_NoopListener(),
        can_transmitter=None,
        telemetry=BoatTelemetryStore(),
    )

    service = PlatformService(runtime)

    with pytest.raises(RuntimeError, match="required decoder is unavailable"):
        service.start()


def test_decoder_runtime_error_degrades_health(tmp_path: Path) -> None:
    settings = Settings(
        sqlite_path=tmp_path / "cobalt.db",
        data_dir=tmp_path,
        capture_dir=tmp_path / "captures",
        decoder_required=False,
    )
    db = Database(settings.sqlite_path)
    runtime = PlatformRuntime(
        settings=settings,
        database=db,
        event_bus=EventBus(),
        capture_manager=CaptureManager(settings.capture_dir),
        catalog_repository=MessageCatalogRepository(db),
        watchlist_repository=PgnWatchlistRepository(db),
        annotation_repository=CaptureAnnotationRepository(db),
        garmin_switch_bank_repository=GarminSwitchBankRepository(db),
        system_event_repository=SystemEventRepository(db),
        policy_engine=PolicyEngine(settings=settings, audit_log_repository=AuditLogRepository(db)),
        interface_manager=_NoopInterfaceManager(),
        decoder=_DecoderFaulty(),
        can_listener=_NoopListener(),
        can_transmitter=None,
        telemetry=BoatTelemetryStore(),
    )
    service = PlatformService(runtime)
    service.start()

    event = CanEvent(
        frame=RawCanFrame(
            timestamp=datetime.now(tz=timezone.utc),
            can_id=0x18F11234,
            is_extended_id=True,
            dlc=8,
            data_hex="0102030405060708",
            channel="vcan0",
        ),
        pgn=61714,
        source_address=0x34,
        destination_address=0x12,
        priority=6,
    )
    service.on_can_event(event)
    health = service.health()

    assert health.decoder_ready is False
    assert health.ok is False
