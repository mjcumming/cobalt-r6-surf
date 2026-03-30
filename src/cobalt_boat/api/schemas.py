"""API response schemas."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HealthResponse(BaseModel):
    """Health endpoint response."""

    ok: bool
    database_ready: bool
    can_listener_running: bool
    decoder_ready: bool


class StatusResponse(BaseModel):
    """Platform status endpoint response."""

    read_only_mode: bool
    write_enable: bool
    emergency_disable: bool
    lab_transmit_enabled: bool
    can_interface: str
    capture_active: bool
    capture_session_id: str | None


class TelemetryMetric(BaseModel):
    """Single decoded metric with optional freshness timestamp (UTC ISO)."""

    value: float | None = None
    updated_at: str | None = None


class TelemetrySnapshotResponse(BaseModel):
    """Last-known navigation/engine values from observed NMEA 2000 traffic."""

    engine_rpm: TelemetryMetric
    engine_coolant_c: TelemetryMetric
    speed_water_mps: TelemetryMetric
    speed_over_ground_mps: TelemetryMetric
    latitude: TelemetryMetric
    longitude: TelemetryMetric
    notes: str


class LabFusionTransmitResponse(BaseModel):
    """Result of a gated lab Fusion CAN transmit."""

    model_config = ConfigDict(extra="ignore")

    ok: bool
    kind: str | None = None
    zone: str | None = None
    can_id: str | None = None
    data_hex: str | None = None
    reason: str | None = None
    hint: str | None = None


class AudioSetVolumeCommand(BaseModel):
    """Shadow command for audio volume change validation."""

    kind: Literal["audio.set_volume"]
    correlation_id: str | None = None
    zone: str
    level: int = Field(ge=0, le=100)

    def as_preview(self) -> tuple[str, str, dict[str, Any], str | None]:
        return ("audio", "set_volume", {"zone": self.zone, "level": self.level}, self.correlation_id)


class AudioSetSourceCommand(BaseModel):
    """Shadow command for audio source change validation."""

    kind: Literal["audio.set_source"]
    correlation_id: str | None = None
    source: str

    def as_preview(self) -> tuple[str, str, dict[str, Any], str | None]:
        return ("audio", "set_source", {"source": self.source}, self.correlation_id)


class LightingSetBrightnessCommand(BaseModel):
    """Shadow command for lighting brightness validation."""

    kind: Literal["lighting.set_brightness"]
    correlation_id: str | None = None
    zone: str
    level: int = Field(ge=0, le=100)

    def as_preview(self) -> tuple[str, str, dict[str, Any], str | None]:
        return (
            "lighting",
            "set_brightness",
            {"zone": self.zone, "level": self.level},
            self.correlation_id,
        )


class LightingSetColorCommand(BaseModel):
    """Shadow command for lighting color validation."""

    kind: Literal["lighting.set_color"]
    correlation_id: str | None = None
    zone: str
    rgb: tuple[int, int, int]

    def as_preview(self) -> tuple[str, str, dict[str, Any], str | None]:
        return ("lighting", "set_color", {"zone": self.zone, "rgb": list(self.rgb)}, self.correlation_id)


CommandPreviewRequest = Annotated[
    Union[
        AudioSetVolumeCommand,
        AudioSetSourceCommand,
        LightingSetBrightnessCommand,
        LightingSetColorCommand,
    ],
    Field(discriminator="kind"),
]


class CommandPreviewResponse(BaseModel):
    """Policy evaluation response for shadow command flow."""

    domain: str
    command_name: str
    parameters: dict[str, Any]
    correlation_id: str | None
    approved: bool
    reason: str
    mode: str
    write_transmitted: bool


class WatchlistUpsertRequest(BaseModel):
    """Request to create or update a PGN watchlist entry."""

    tag: str = Field(min_length=1, max_length=64)
    note: str = Field(default="", max_length=500)


class WatchlistEntryResponse(BaseModel):
    """Watchlist entry response model."""

    pgn: int
    tag: str
    note: str
    created_at: str
    updated_at: str


class CaptureAnnotationCreateRequest(BaseModel):
    """Create annotation request for capture sessions."""

    action_label: str = Field(min_length=1, max_length=120)
    action_at: str
    note: str = Field(default="", max_length=500)
    operator: str = Field(default="unknown", min_length=1, max_length=80)


class CaptureAnnotationResponse(BaseModel):
    """Capture annotation response model."""

    id: int
    session_id: str
    action_at: str
    action_label: str
    note: str
    operator: str
    created_at: str


class FusionCorrelationResult(BaseModel):
    """Per-annotation Fusion correlation result."""

    annotation_id: int
    action_label: str
    action_at: str
    observed_pgns: list[int]
    chain_matched: bool
    target_pgns: list[int]


class FusionCorrelationReportResponse(BaseModel):
    """Session-level Fusion correlation report."""

    session_id: str
    window_sec: int
    total_annotations: int
    matches: int
    confidence: str
    error: str | None = None
    results: list[FusionCorrelationResult]


class GarminShadowCommandResponse(BaseModel):
    """One simulated command tied to a virtual Garmin switch object."""

    kind: str
    parameters: dict[str, Any]


class GarminSwitchControlResponse(BaseModel):
    """One virtual switch control entry for Garmin/NMEA switching views."""

    instance: int
    label: str
    description: str
    shadow_commands: list[GarminShadowCommandResponse]


class GarminSwitchBankResponse(BaseModel):
    """Simulated switch bank profile for Garmin interoperability planning."""

    bank_instance: int
    bank_label: str
    status_pgn: int
    control_pgn: int
    write_eligible: bool
    gate_reason: str
    controls: list[GarminSwitchControlResponse]


class GarminAudioSetVolumeCommand(BaseModel):
    """Typed Garmin switch action command for audio volume."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["audio.set_volume"]
    zone: str = Field(min_length=1, max_length=80)
    level: int = Field(ge=0, le=100)

    def as_shadow(self) -> GarminShadowCommandResponse:
        return GarminShadowCommandResponse(
            kind=self.kind,
            parameters={"zone": self.zone, "level": self.level},
        )

    def to_template_command(self) -> dict[str, object]:
        return {"kind": self.kind, "zone": self.zone, "level": self.level}


class GarminAudioSetSourceCommand(BaseModel):
    """Typed Garmin switch action command for audio source select."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["audio.set_source"]
    source: str = Field(min_length=1, max_length=80)

    def as_shadow(self) -> GarminShadowCommandResponse:
        return GarminShadowCommandResponse(
            kind=self.kind,
            parameters={"source": self.source},
        )

    def to_template_command(self) -> dict[str, object]:
        return {"kind": self.kind, "source": self.source}


class GarminLightingSetBrightnessCommand(BaseModel):
    """Typed Garmin switch action command for lighting brightness."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["lighting.set_brightness"]
    zone: str = Field(min_length=1, max_length=80)
    level: int = Field(ge=0, le=100)

    def as_shadow(self) -> GarminShadowCommandResponse:
        return GarminShadowCommandResponse(
            kind=self.kind,
            parameters={"zone": self.zone, "level": self.level},
        )

    def to_template_command(self) -> dict[str, object]:
        return {"kind": self.kind, "zone": self.zone, "level": self.level}


class GarminLightingSetColorCommand(BaseModel):
    """Typed Garmin switch action command for lighting color."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["lighting.set_color"]
    zone: str = Field(min_length=1, max_length=80)
    rgb: tuple[int, int, int]

    @model_validator(mode="after")
    def _validate_rgb(self) -> GarminLightingSetColorCommand:
        if any(channel < 0 or channel > 255 for channel in self.rgb):
            raise ValueError("rgb values must be in range 0..255")
        return self

    def as_shadow(self) -> GarminShadowCommandResponse:
        return GarminShadowCommandResponse(
            kind=self.kind,
            parameters={"zone": self.zone, "rgb": list(self.rgb)},
        )

    def to_template_command(self) -> dict[str, object]:
        return {"kind": self.kind, "zone": self.zone, "rgb": list(self.rgb)}


GarminSwitchCommandUpdate = Annotated[
    Union[
        GarminAudioSetVolumeCommand,
        GarminAudioSetSourceCommand,
        GarminLightingSetBrightnessCommand,
        GarminLightingSetColorCommand,
    ],
    Field(discriminator="kind"),
]


class GarminSwitchControlUpdate(BaseModel):
    """One editable switch control profile item."""

    model_config = ConfigDict(extra="forbid")

    instance: int = Field(ge=1, le=64)
    label: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=240)
    shadow_commands: list[GarminSwitchCommandUpdate] = Field(min_length=1, max_length=8)

    def to_response(self) -> GarminSwitchControlResponse:
        return GarminSwitchControlResponse(
            instance=self.instance,
            label=self.label,
            description=self.description,
            shadow_commands=[command.as_shadow() for command in self.shadow_commands],
        )


class GarminSwitchBankProfileUpdate(BaseModel):
    """Editable switch-bank profile template."""

    model_config = ConfigDict(extra="forbid")

    bank_instance: int = Field(default=1, ge=1, le=16)
    bank_label: str = Field(min_length=1, max_length=80)
    status_pgn: int = Field(default=127501)
    control_pgn: int = Field(default=127502)
    controls: list[GarminSwitchControlUpdate] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def _validate_standard_pgns(self) -> GarminSwitchBankProfileUpdate:
        if self.status_pgn != 127501:
            raise ValueError("status_pgn must be 127501")
        if self.control_pgn != 127502:
            raise ValueError("control_pgn must be 127502")
        instances = [control.instance for control in self.controls]
        if len(set(instances)) != len(instances):
            raise ValueError("control instances must be unique")
        return self

    def to_template_dict(self) -> dict[str, object]:
        return {
            "bank_instance": self.bank_instance,
            "bank_label": self.bank_label,
            "status_pgn": self.status_pgn,
            "control_pgn": self.control_pgn,
            "controls": [
                {
                    "instance": control.instance,
                    "label": control.label,
                    "description": control.description,
                    "shadow_commands": [
                        command.to_template_command()
                        for command in control.shadow_commands
                    ],
                }
                for control in self.controls
            ],
        }


class GarminSwitchBankUpdateRequest(BaseModel):
    """Validated update request for switch-bank template edits."""

    model_config = ConfigDict(extra="forbid")

    operator: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=240)
    profile: GarminSwitchBankProfileUpdate
