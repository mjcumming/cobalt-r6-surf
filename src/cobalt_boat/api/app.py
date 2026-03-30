"""Application entrypoint for local-only FastAPI service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from cobalt_boat.can.capture import CaptureManager
from cobalt_boat.can.decoder import (
    BasicNmeaDecoder,
    CanDecoder,
    CanboatProcessDecoder,
)
from cobalt_boat.can.interface import SocketCanInterfaceManager
from cobalt_boat.can.models import CanEvent, DecodedCanMessage
from cobalt_boat.can.socketcan import SocketCanListener
from cobalt_boat.can.transmit import SocketCanTransmitter
from cobalt_boat.config import Settings
from cobalt_boat.domains.telemetry import BoatTelemetryStore
from cobalt_boat.events import EventBus, EventEnvelope
from cobalt_boat.logging_config import configure_logging
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

from .schemas import (
    CommandPreviewRequest,
    CommandPreviewResponse,
    CaptureAnnotationCreateRequest,
    CaptureAnnotationResponse,
    FusionCorrelationReportResponse,
    GarminSwitchBankProfileUpdate,
    GarminSwitchBankUpdateRequest,
    GarminSwitchBankResponse,
    HealthResponse,
    LabFusionTransmitResponse,
    StatusResponse,
    TelemetrySnapshotResponse,
    WatchlistEntryResponse,
    WatchlistUpsertRequest,
)


def create_decoder(settings: Settings) -> CanDecoder:
    """Create configured decoder backend."""

    backend = settings.decoder_backend.strip().lower()
    if backend == "basic":
        if not settings.allow_basic_decoder_insecure:
            raise ValueError("basic decoder is disabled; use canboat or explicitly allow insecure mode")
        return BasicNmeaDecoder()
    if backend == "canboat":
        return CanboatProcessDecoder.from_command_string(
            command=settings.canboat_command,
            response_timeout_sec=settings.canboat_response_timeout_sec,
        )
    raise ValueError(f"unsupported decoder backend: {settings.decoder_backend}")


def create_runtime(settings: Settings) -> PlatformService:
    """Compose runtime dependencies for application services."""

    db = Database(sqlite_path=settings.sqlite_path)
    capture_manager = CaptureManager(settings.capture_dir)
    audit_log_repository = AuditLogRepository(db)
    telemetry = BoatTelemetryStore()

    service_placeholder: dict[str, PlatformService] = {}

    def _can_event_sink(event: CanEvent) -> None:
        service_placeholder["service"].on_can_event(event)

    can_listener = SocketCanListener(
        interface=settings.can_interface,
        event_sink=_can_event_sink,
        capture_manager=capture_manager,
    )
    can_transmitter = (
        SocketCanTransmitter(settings.can_interface)
        if settings.lab_transmit_enabled
        else None
    )
    interface_manager = SocketCanInterfaceManager(
        interface=settings.can_interface,
        bitrate=settings.can_channel_bitrate,
    )

    runtime = PlatformRuntime(
        settings=settings,
        database=db,
        event_bus=EventBus(),
        capture_manager=capture_manager,
        catalog_repository=MessageCatalogRepository(db),
        watchlist_repository=PgnWatchlistRepository(db),
        annotation_repository=CaptureAnnotationRepository(db),
        garmin_switch_bank_repository=GarminSwitchBankRepository(db),
        system_event_repository=SystemEventRepository(db),
        policy_engine=PolicyEngine(settings=settings, audit_log_repository=audit_log_repository),
        interface_manager=interface_manager,
        decoder=create_decoder(settings),
        can_listener=can_listener,
        can_transmitter=can_transmitter,
        telemetry=telemetry,
    )

    def _on_message_decoded(envelope: EventEnvelope) -> None:
        if isinstance(envelope.payload, DecodedCanMessage):
            telemetry.record(envelope.occurred_at, envelope.payload)

    runtime.event_bus.subscribe("can.message_decoded", _on_message_decoded)
    service = PlatformService(runtime)
    service_placeholder["service"] = service
    return service


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create FastAPI app with lifecycle-managed platform services."""

    resolved_settings = settings or Settings.from_env()
    configure_logging(
        resolved_settings.log_level,
        resolved_settings.app_log_path,
        log_max_bytes=resolved_settings.log_max_bytes,
        log_backup_count=resolved_settings.log_backup_count,
    )
    platform_service = create_runtime(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        platform_service.start()
        try:
            yield
        finally:
            platform_service.stop()

    app = FastAPI(title="Cobalt Boat API", version="0.1.0", lifespan=lifespan)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        health_state = platform_service.health()
        return HealthResponse(
            ok=health_state.ok,
            database_ready=health_state.database_ready,
            can_listener_running=health_state.can_listener_running,
            decoder_ready=health_state.decoder_ready,
        )

    @app.get("/status", response_model=StatusResponse)
    def status() -> StatusResponse:
        state = platform_service.status()
        return StatusResponse(
            read_only_mode=state.read_only_mode,
            write_enable=state.write_enable,
            emergency_disable=state.emergency_disable,
            lab_transmit_enabled=state.lab_transmit_enabled,
            can_interface=state.can_interface,
            capture_active=state.capture_active,
            capture_session_id=state.capture_session_id,
        )

    @app.get("/api/telemetry", response_model=TelemetrySnapshotResponse)
    def api_telemetry() -> TelemetrySnapshotResponse:
        return TelemetrySnapshotResponse.model_validate(platform_service.telemetry_snapshot())

    @app.get("/debug/catalog")
    def debug_catalog(
        limit: int = 200, pgn: int | None = None, watch_only: bool = False
    ) -> list[dict[str, object]]:
        return platform_service.filtered_catalog(
            limit=max(1, min(limit, 1000)),
            pgn=pgn,
            watch_only=watch_only,
        )

    @app.get("/debug/events")
    def debug_events(limit: int = 200) -> list[dict[str, object]]:
        return platform_service.recent_system_events(limit=max(1, min(limit, 1000)))

    @app.get("/debug/logs")
    def debug_logs(lines: int = 200) -> dict[str, object]:
        bounded = max(1, min(lines, 2000))
        return {"lines": platform_service.tail_logs(lines=bounded)}

    @app.get("/debug/watchlist", response_model=list[WatchlistEntryResponse])
    def debug_watchlist() -> list[WatchlistEntryResponse]:
        return [WatchlistEntryResponse(**row) for row in platform_service.list_watchlist()]

    @app.put("/debug/watchlist/{pgn}", response_model=list[WatchlistEntryResponse])
    def upsert_watchlist(pgn: int, request: WatchlistUpsertRequest) -> list[WatchlistEntryResponse]:
        rows = platform_service.upsert_watchlist(pgn=pgn, tag=request.tag.strip(), note=request.note.strip())
        return [WatchlistEntryResponse(**row) for row in rows]

    @app.delete("/debug/watchlist/{pgn}", response_model=list[WatchlistEntryResponse])
    def delete_watchlist(pgn: int) -> list[WatchlistEntryResponse]:
        rows = platform_service.remove_watchlist(pgn=pgn)
        return [WatchlistEntryResponse(**row) for row in rows]

    @app.post("/debug/lab/fusion/volume-up", response_model=LabFusionTransmitResponse)
    def lab_fusion_volume_up(
        zone: str = Query("cockpit", min_length=1, max_length=64),
    ) -> LabFusionTransmitResponse:
        payload = platform_service.lab_fusion_transmit(kind="volume_up", zone=zone)
        return LabFusionTransmitResponse.model_validate(payload)

    @app.post("/debug/lab/fusion/volume-down", response_model=LabFusionTransmitResponse)
    def lab_fusion_volume_down(
        zone: str = Query("cockpit", min_length=1, max_length=64),
    ) -> LabFusionTransmitResponse:
        payload = platform_service.lab_fusion_transmit(kind="volume_down", zone=zone)
        return LabFusionTransmitResponse.model_validate(payload)

    @app.post("/debug/lab/fusion/mute-on", response_model=LabFusionTransmitResponse)
    def lab_fusion_mute_on(
        zone: str = Query("cockpit", min_length=1, max_length=64),
    ) -> LabFusionTransmitResponse:
        payload = platform_service.lab_fusion_transmit(kind="mute_on", zone=zone)
        return LabFusionTransmitResponse.model_validate(payload)

    @app.post("/debug/lab/fusion/mute-off", response_model=LabFusionTransmitResponse)
    def lab_fusion_mute_off(
        zone: str = Query("cockpit", min_length=1, max_length=64),
    ) -> LabFusionTransmitResponse:
        payload = platform_service.lab_fusion_transmit(kind="mute_off", zone=zone)
        return LabFusionTransmitResponse.model_validate(payload)

    @app.get(
        "/debug/captures/{session_id}/annotations",
        response_model=list[CaptureAnnotationResponse],
    )
    def list_capture_annotations(session_id: str) -> list[CaptureAnnotationResponse]:
        rows = platform_service.list_capture_annotations(session_id=session_id)
        return [CaptureAnnotationResponse(**row) for row in rows]

    @app.post(
        "/debug/captures/{session_id}/annotations",
        response_model=list[CaptureAnnotationResponse],
    )
    def create_capture_annotation(
        session_id: str, request: CaptureAnnotationCreateRequest
    ) -> list[CaptureAnnotationResponse]:
        action_at = request.action_at.replace("Z", "+00:00")
        rows = platform_service.create_capture_annotation(
            session_id=session_id,
            action_at=datetime.fromisoformat(action_at),
            action_label=request.action_label.strip(),
            note=request.note.strip(),
            operator=request.operator.strip(),
        )
        return [CaptureAnnotationResponse(**row) for row in rows]

    @app.get("/debug/fusion/correlation", response_model=FusionCorrelationReportResponse)
    def fusion_correlation_report(
        session_id: str, window_sec: int = 5
    ) -> FusionCorrelationReportResponse:
        report = platform_service.fusion_correlation_report(
            session_id=session_id,
            window_sec=max(1, min(window_sec, 30)),
        )
        return FusionCorrelationReportResponse(**report)

    @app.get("/debug/garmin/switch-bank", response_model=GarminSwitchBankResponse)
    def garmin_switch_bank() -> GarminSwitchBankResponse:
        return GarminSwitchBankResponse(**platform_service.garmin_switch_bank_profile())

    @app.get("/debug/garmin/switch-bank/template", response_model=GarminSwitchBankProfileUpdate)
    def garmin_switch_bank_template() -> GarminSwitchBankProfileUpdate:
        return GarminSwitchBankProfileUpdate(**platform_service.garmin_switch_bank_template())

    @app.put("/debug/garmin/switch-bank", response_model=GarminSwitchBankResponse)
    def update_garmin_switch_bank(
        request: GarminSwitchBankUpdateRequest,
    ) -> GarminSwitchBankResponse:
        profile = platform_service.update_garmin_switch_bank_profile(
            profile_template=request.profile.to_template_dict(),
            operator=request.operator.strip(),
            reason=request.reason.strip(),
        )
        return GarminSwitchBankResponse(**profile)

    @app.api_route("/debug", methods=["GET", "HEAD"], response_class=HTMLResponse)
    def debug_page() -> str:
        return DEBUG_PAGE_HTML

    @app.api_route("/debug/lab", methods=["GET", "HEAD"], response_class=HTMLResponse)
    def debug_lab_page() -> str:
        return LAB_PAGE_HTML

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False, response_class=HTMLResponse)
    def dashboard_page() -> str:
        return DASHBOARD_PAGE_HTML

    @app.post("/commands/preview", response_model=CommandPreviewResponse)
    def command_preview(request: CommandPreviewRequest) -> CommandPreviewResponse:
        domain, command_name, parameters, correlation_id = request.as_preview()
        result = platform_service.preview_command(
            domain=domain,
            command_name=command_name,
            parameters=parameters,
            correlation_id=correlation_id,
        )
        return CommandPreviewResponse(
            domain=result.domain,
            command_name=result.command_name,
            parameters=result.parameters,
            correlation_id=result.correlation_id,
            approved=result.approved,
            reason=result.reason,
            mode=result.mode,
            write_transmitted=result.write_transmitted,
        )

    @app.post("/commands/validate", response_model=CommandPreviewResponse)
    def command_validate(request: CommandPreviewRequest) -> CommandPreviewResponse:
        return command_preview(request)

    return app


def run() -> None:
    """Run local-only API service."""

    import uvicorn

    settings = Settings.from_env()
    app = create_app(settings)
    ssl_keyfile: str | None = None
    ssl_certfile: str | None = None
    if settings.api_ssl_keyfile and settings.api_ssl_certfile:
        key = settings.api_ssl_keyfile
        cert = settings.api_ssl_certfile
        if key.is_file() and cert.is_file():
            ssl_keyfile = str(key)
            ssl_certfile = str(cert)
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile,
    )


DASHBOARD_PAGE_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Cobalt Boat</title>
    <style>
      :root { font-family: "JetBrains Mono", "Fira Code", monospace; color-scheme: light; }
      body { margin: 0; background: #0b1d2a; color: #d9edf7; }
      header { padding: 12px 16px; background: #12324a; border-bottom: 1px solid #2b5d7e;
              display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
      h1 { margin: 0; font-size: 18px; letter-spacing: 0.4px; }
      nav.site-nav a { color: #7ec8e3; text-decoration: none; font-size: 13px; margin-left: 12px; }
      nav.site-nav a:hover { text-decoration: underline; }
      nav.site-nav span.here { color: #9fb8c8; font-size: 13px; margin-left: 12px; }
      main { padding: 16px; max-width: 960px; margin: 0 auto; }
      .hint { font-size: 12px; color: #9fb8c8; margin-bottom: 16px; line-height: 1.5; }
      .stats { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
      .card { background: #0f283a; border: 1px solid #2b5d7e; border-radius: 6px; padding: 14px; }
      .card h2 { margin: 0 0 8px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.12em; color: #9fb8c8; }
      .card .val { font-size: 22px; font-weight: 600; color: #e8f4fc; }
      .card .sub { font-size: 11px; color: #7a9aad; margin-top: 6px; }
      .actions { margin-top: 20px; display: flex; flex-wrap: wrap; gap: 10px; }
      .actions a { display: inline-block; padding: 10px 16px; background: #173b55; border: 1px solid #2b5d7e;
                   border-radius: 6px; color: #d9edf7; text-decoration: none; font-size: 13px; }
      .actions a:hover { background: #1f4d70; }
    </style>
  </head>
  <body>
    <header>
      <h1>Cobalt Boat</h1>
      <nav class="site-nav">
        <span class="here">Dashboard</span>
        <a href="/debug">Debug console</a>
        <a href="/debug/lab">Lab / test transmit</a>
      </nav>
    </header>
    <main>
      <p class="hint">Live values appear when CANboat decodes them from the NMEA 2000 bus. Use normal web URLs: <strong>http://</strong> and this device&rsquo;s IP on port 80, or <strong>https://</strong> on port 443 when TLS is configured—no custom port or path required for the default install.</p>
      <div class="stats">
        <div class="card"><h2>Engine RPM</h2><div class="val" id="rpm">—</div><div class="sub" id="rpm-sub"></div></div>
        <div class="card"><h2>Coolant</h2><div class="val" id="cool">—</div><div class="sub" id="cool-sub"></div></div>
        <div class="card"><h2>Speed (water)</h2><div class="val" id="stw">—</div><div class="sub" id="stw-sub"></div></div>
        <div class="card"><h2>Speed (SOG)</h2><div class="val" id="sog">—</div><div class="sub" id="sog-sub"></div></div>
        <div class="card" style="grid-column: 1 / -1;"><h2>GPS</h2><div class="val" id="gps">—</div><div class="sub" id="gps-sub"></div></div>
      </div>
      <div class="actions">
        <a href="/debug">Open debug console</a>
        <a href="/debug/lab">Open lab transmit (Fusion stubs)</a>
      </div>
    </main>
    <script>
      const KN = 1.943844492642;
      function fmtTime(iso) {
        if (!iso) return "";
        try {
          const d = new Date(iso);
          return "Updated " + d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        } catch (_) { return ""; }
      }
      function fmtLatLon(lat, lon) {
        if (lat == null || lon == null) return null;
        const ns = lat >= 0 ? "N" : "S";
        const ew = lon >= 0 ? "E" : "W";
        return Math.abs(lat).toFixed(5) + "° " + ns + ", " + Math.abs(lon).toFixed(5) + "° " + ew;
      }
      async function refresh() {
        try {
          const t = await (await fetch("/api/telemetry", { cache: "no-store" })).json();
          const rpm = t.engine_rpm;
          document.getElementById("rpm").textContent = rpm.value != null ? Math.round(rpm.value).toString() + " RPM" : "—";
          document.getElementById("rpm-sub").textContent = fmtTime(rpm.updated_at);
          const cool = t.engine_coolant_c;
          document.getElementById("cool").textContent = cool.value != null ? cool.value.toFixed(1) + " °C" : "—";
          document.getElementById("cool-sub").textContent = fmtTime(cool.updated_at);
          const stw = t.speed_water_mps;
          if (stw.value != null) {
            const kn = stw.value * KN;
            document.getElementById("stw").textContent = kn.toFixed(2) + " kn";
            document.getElementById("stw-sub").textContent = stw.value.toFixed(3) + " m/s · " + fmtTime(stw.updated_at);
          } else {
            document.getElementById("stw").textContent = "—";
            document.getElementById("stw-sub").textContent = "";
          }
          const sogM = t.speed_over_ground_mps;
          if (sogM.value != null) {
            const kn = sogM.value * KN;
            document.getElementById("sog").textContent = kn.toFixed(2) + " kn";
            document.getElementById("sog-sub").textContent = sogM.value.toFixed(3) + " m/s · " + fmtTime(sogM.updated_at);
          } else {
            document.getElementById("sog").textContent = "—";
            document.getElementById("sog-sub").textContent = "";
          }
          const lat = t.latitude.value;
          const lon = t.longitude.value;
          const gpsTxt = fmtLatLon(lat, lon);
          document.getElementById("gps").textContent = gpsTxt != null ? gpsTxt : "—";
          document.getElementById("gps-sub").textContent = fmtTime(t.latitude.updated_at || t.longitude.updated_at);
        } catch (e) {
          document.getElementById("rpm").textContent = "—";
          document.getElementById("rpm-sub").textContent = "Could not load /api/telemetry";
        }
      }
      refresh();
      setInterval(refresh, 1500);
    </script>
  </body>
</html>
"""

LAB_PAGE_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Cobalt Lab Transmit</title>
    <style>
      :root { font-family: "JetBrains Mono", "Fira Code", monospace; color-scheme: light; }
      body { margin: 0; background: #0b1d2a; color: #d9edf7; }
      header { padding: 12px 16px; background: #12324a; border-bottom: 1px solid #2b5d7e;
              display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
      h1 { margin: 0; font-size: 16px; letter-spacing: 0.4px; }
      nav.site-nav a { color: #7ec8e3; text-decoration: none; font-size: 13px; margin-left: 12px; }
      nav.site-nav a:hover { text-decoration: underline; }
      nav.site-nav span.here { color: #9fb8c8; font-size: 13px; margin-left: 12px; }
      main { padding: 12px 16px; max-width: 720px; }
      .panel { background: #0f283a; border: 1px solid #2b5d7e; border-radius: 6px; overflow: hidden; margin-top: 12px; }
      .panel h2 { margin: 0; padding: 8px 10px; font-size: 13px; background: #173b55; }
      pre { margin: 0; padding: 10px; min-height: 120px; font-size: 12px; white-space: pre-wrap; }
      .controls { display: flex; gap: 8px; flex-wrap: wrap; padding: 8px 10px; border-bottom: 1px solid #2b5d7e; }
      .controls input, .controls button { background: #0b1d2a; color: #d9edf7; border: 1px solid #2b5d7e; padding: 4px 6px; border-radius: 4px; font-family: inherit; font-size: 12px; }
      .warn { margin: 8px 10px; padding: 8px; font-size: 12px; background: #3a2218; border: 1px solid #8b5a30; border-radius: 4px; color: #f2d4c4; }
      .lab-hint { margin: 4px 10px 8px; font-size: 11px; color: #9fb8c8; }
    </style>
  </head>
  <body>
    <header>
      <h1>Lab — Fusion CAN transmit (stubs)</h1>
      <nav class="site-nav">
        <a href="/">Dashboard</a>
        <a href="/debug">Debug console</a>
        <span class="here">Lab</span>
      </nav>
    </header>
    <main>
      <section class="panel">
        <h2>PGN 126208 placeholders (vcan / verification only)</h2>
        <p class="warn">Requires <code>COBALT_LAB_TRANSMIT_ENABLED=true</code>, <code>COBALT_READ_ONLY_MODE=false</code>, and <code>COBALT_WRITE_ENABLE=true</code>. Replace payload bytes from a real vessel capture before relying on these frames.</p>
        <p class="lab-hint" id="labFusionHint"></p>
        <div class="controls">
          <input id="labFusionZone" placeholder="zone label" value="cockpit" style="min-width:120px">
          <button type="button" id="labVolUp">Volume +</button>
          <button type="button" id="labVolDown">Volume −</button>
          <button type="button" id="labMuteOn">Mute</button>
          <button type="button" id="labMuteOff">Unmute</button>
        </div>
        <pre id="labFusionResult"></pre>
      </section>
    </main>
    <script>
      async function fetchJson(url) {
        const response = await fetch(url, { cache: "no-store" });
        if (!response.ok) throw new Error(url + " status=" + response.status);
        return response.json();
      }
      function labFusionHintText(status) {
        if (!status.lab_transmit_enabled) {
          return "Lab transmit: OFF (COBALT_LAB_TRANSMIT_ENABLED). API calls will be refused until enabled and restarted.";
        }
        const gates = [];
        if (status.read_only_mode) gates.push("read_only_mode");
        if (!status.write_enable) gates.push("write_enable");
        if (status.emergency_disable) gates.push("emergency_disable");
        if (gates.length) {
          return "Lab flag on, but policy blocks transmit until: " + gates.join(", ") + " cleared.";
        }
        return "Lab transmit armed. Use vcan + candump to verify frames.";
      }
      async function refreshHint() {
        try {
          const status = await fetchJson("/status");
          document.getElementById("labFusionHint").textContent = labFusionHintText(status);
        } catch (_) {}
      }
      async function postLabFusion(path) {
        const zone = (document.getElementById("labFusionZone").value || "cockpit").trim();
        const response = await fetch(path + "?zone=" + encodeURIComponent(zone), { method: "POST" });
        const body = await response.json();
        document.getElementById("labFusionResult").textContent = JSON.stringify(body, null, 2);
      }
      document.getElementById("labVolUp").addEventListener("click", () => postLabFusion("/debug/lab/fusion/volume-up"));
      document.getElementById("labVolDown").addEventListener("click", () => postLabFusion("/debug/lab/fusion/volume-down"));
      document.getElementById("labMuteOn").addEventListener("click", () => postLabFusion("/debug/lab/fusion/mute-on"));
      document.getElementById("labMuteOff").addEventListener("click", () => postLabFusion("/debug/lab/fusion/mute-off"));
      refreshHint();
      setInterval(refreshHint, 2000);
    </script>
  </body>
</html>
"""

DEBUG_PAGE_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Cobalt Boat Debug</title>
    <style>
      :root { font-family: "JetBrains Mono", "Fira Code", monospace; color-scheme: light; }
      body { margin: 0; background: #0b1d2a; color: #d9edf7; }
      header { padding: 12px 16px; background: #12324a; border-bottom: 1px solid #2b5d7e;
              display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
      h1 { margin: 0; font-size: 16px; letter-spacing: 0.4px; }
      nav.site-nav a { color: #7ec8e3; text-decoration: none; font-size: 13px; margin-left: 12px; }
      nav.site-nav a:hover { text-decoration: underline; }
      nav.site-nav span.here { color: #9fb8c8; font-size: 13px; margin-left: 12px; }
      .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 12px; }
      .panel { background: #0f283a; border: 1px solid #2b5d7e; border-radius: 6px; overflow: hidden; }
      .panel h2 { margin: 0; padding: 8px 10px; font-size: 13px; background: #173b55; }
      pre { margin: 0; padding: 10px; height: 280px; overflow: auto; font-size: 12px; white-space: pre-wrap; }
      textarea { width: calc(100% - 20px); margin: 10px; min-height: 220px; background: #081622; color: #d9edf7; border: 1px solid #2b5d7e; border-radius: 4px; font-family: inherit; font-size: 12px; padding: 8px; }
      .full { grid-column: 1 / -1; }
      .small { height: 170px; }
      .controls { display: flex; gap: 8px; flex-wrap: wrap; padding: 8px 10px; border-bottom: 1px solid #2b5d7e; }
      .controls input, .controls button { background: #0b1d2a; color: #d9edf7; border: 1px solid #2b5d7e; padding: 4px 6px; border-radius: 4px; font-family: inherit; font-size: 12px; }
      .controls label { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; }
      .warn { margin: 8px 10px; padding: 8px; font-size: 12px; background: #3a2218; border: 1px solid #8b5a30; border-radius: 4px; color: #f2d4c4; }
      .lab-hint { margin: 4px 10px 8px; font-size: 11px; color: #9fb8c8; }
      @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
    </style>
  </head>
  <body>
    <header>
      <h1>Cobalt Boat Debug Console (Read-Only)</h1>
      <nav class="site-nav">
        <a href="/">Dashboard</a>
        <a href="/debug/lab">Lab transmit</a>
        <span class="here">Debug</span>
      </nav>
    </header>
    <main class="grid">
      <section class="panel"><h2>Health</h2><pre id="health" class="small"></pre></section>
      <section class="panel"><h2>Status</h2><pre id="status" class="small"></pre></section>
      <section class="panel"><h2>Recent System Events</h2><pre id="events"></pre></section>
      <section class="panel">
        <h2>Message Catalog</h2>
        <div class="controls">
          <input id="filterPgn" placeholder="PGN filter (e.g. 127501)">
          <label><input id="watchOnly" type="checkbox"> watch-only</label>
          <button id="applyFilters">apply</button>
        </div>
        <pre id="catalog"></pre>
      </section>
      <section class="panel full">
        <h2>PGN Watchlist</h2>
        <div class="controls">
          <input id="watchPgn" placeholder="PGN">
          <input id="watchTag" placeholder="Tag (e.g. lighting-candidate)">
          <input id="watchNote" placeholder="Note (optional)">
          <button id="saveWatch">save</button>
          <button id="removeWatch">remove</button>
        </div>
        <pre id="watchlist" class="small"></pre>
      </section>
      <section class="panel full">
        <h2>Garmin Switch Bank Template (JSON)</h2>
        <div class="controls">
          <input id="garminOperator" placeholder="Operator" value="local-dev">
          <input id="garminReason" placeholder="Reason for update">
          <button id="saveGarminProfile">save template</button>
        </div>
        <textarea id="garminTemplate"></textarea>
      </section>
      <section class="panel full">
        <h2>Lab Fusion transmit (PGN 126208 stubs)</h2>
        <p class="warn">Placeholder payloads for bus verification on <strong>vcan</strong> only until you replace bytes from vessel capture. Requires <code>COBALT_LAB_TRANSMIT_ENABLED=true</code>, <code>COBALT_READ_ONLY_MODE=false</code>, and <code>COBALT_WRITE_ENABLE=true</code>.</p>
        <p class="lab-hint" id="labFusionHint"></p>
        <div class="controls">
          <input id="labFusionZone" placeholder="zone label" value="cockpit" style="min-width:120px">
          <button type="button" id="labVolUp">Volume +</button>
          <button type="button" id="labVolDown">Volume −</button>
          <button type="button" id="labMuteOn">Mute</button>
          <button type="button" id="labMuteOff">Unmute</button>
        </div>
        <pre id="labFusionResult" class="small"></pre>
      </section>
      <section class="panel full"><h2>Application Log Tail</h2><pre id="logs"></pre></section>
    </main>
    <script>
      async function fetchJson(url) {
        const response = await fetch(url, { cache: "no-store" });
        if (!response.ok) { throw new Error(url + " status=" + response.status); }
        return response.json();
      }
      function render(id, value) {
        document.getElementById(id).textContent = JSON.stringify(value, null, 2);
      }
      function catalogUrl() {
        const pgn = (document.getElementById("filterPgn").value || "").trim();
        const watchOnly = document.getElementById("watchOnly").checked;
        const params = new URLSearchParams();
        params.set("limit", "50");
        if (pgn) { params.set("pgn", pgn); }
        if (watchOnly) { params.set("watch_only", "true"); }
        return "/debug/catalog?" + params.toString();
      }
      async function updateWatchlist() {
        const watchlist = await fetchJson("/debug/watchlist");
        render("watchlist", watchlist);
      }
      async function saveWatchlistEntry() {
        const pgn = (document.getElementById("watchPgn").value || "").trim();
        const tag = (document.getElementById("watchTag").value || "").trim();
        const note = (document.getElementById("watchNote").value || "").trim();
        if (!pgn || !tag) { return; }
        await fetch("/debug/watchlist/" + encodeURIComponent(pgn), {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tag, note })
        });
        await updateWatchlist();
        await refresh();
      }
      async function removeWatchlistEntry() {
        const pgn = (document.getElementById("watchPgn").value || "").trim();
        if (!pgn) { return; }
        await fetch("/debug/watchlist/" + encodeURIComponent(pgn), { method: "DELETE" });
        await updateWatchlist();
        await refresh();
      }
      async function saveGarminSwitchProfile() {
        const operator = (document.getElementById("garminOperator").value || "").trim();
        const reason = (document.getElementById("garminReason").value || "").trim();
        const templateText = document.getElementById("garminTemplate").value;
        if (!operator || !reason || !templateText.trim()) { return; }
        const profile = JSON.parse(templateText);
        const response = await fetch("/debug/garmin/switch-bank", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ operator, reason, profile })
        });
        if (!response.ok) {
          const body = await response.text();
          throw new Error("save failed status=" + response.status + " body=" + body);
        }
        await refresh();
      }
      function labFusionHintText(status) {
        if (!status.lab_transmit_enabled) {
          return "Lab transmit: OFF (COBALT_LAB_TRANSMIT_ENABLED). Buttons call the API but the service will refuse until enabled and restarted.";
        }
        const gates = [];
        if (status.read_only_mode) gates.push("read_only_mode");
        if (!status.write_enable) gates.push("write_enable");
        if (status.emergency_disable) gates.push("emergency_disable");
        if (gates.length) {
          return "Lab flag on, but policy blocks transmit until: " + gates.join(", ") + " cleared.";
        }
        return "Lab transmit armed (policy may still rate-limit). Use vcan + candump to verify frames.";
      }
      async function postLabFusion(path) {
        const zone = (document.getElementById("labFusionZone").value || "cockpit").trim();
        const response = await fetch(path + "?zone=" + encodeURIComponent(zone), { method: "POST" });
        const body = await response.json();
        document.getElementById("labFusionResult").textContent = JSON.stringify(body, null, 2);
      }
      async function refresh() {
        try {
          const [health, status, events, catalog, logs, watchlist, garminTemplate] = await Promise.all([
            fetchJson("/health"),
            fetchJson("/status"),
            fetchJson("/debug/events?limit=50"),
            fetchJson(catalogUrl()),
            fetchJson("/debug/logs?lines=200"),
            fetchJson("/debug/watchlist"),
            fetchJson("/debug/garmin/switch-bank/template")
          ]);
          render("health", health);
          render("status", status);
          render("events", events);
          render("catalog", catalog);
          render("watchlist", watchlist);
          document.getElementById("labFusionHint").textContent = labFusionHintText(status);
          if (document.activeElement !== document.getElementById("garminTemplate")) {
            document.getElementById("garminTemplate").value = JSON.stringify(garminTemplate, null, 2);
          }
          document.getElementById("logs").textContent = (logs.lines || []).join(String.fromCharCode(10));
        } catch (err) {
          document.getElementById("health").textContent = "Refresh failed: " + String(err);
        }
      }
      document.getElementById("applyFilters").addEventListener("click", refresh);
      document.getElementById("saveWatch").addEventListener("click", saveWatchlistEntry);
      document.getElementById("removeWatch").addEventListener("click", removeWatchlistEntry);
      document.getElementById("saveGarminProfile").addEventListener("click", saveGarminSwitchProfile);
      document.getElementById("labVolUp").addEventListener("click", () => postLabFusion("/debug/lab/fusion/volume-up"));
      document.getElementById("labVolDown").addEventListener("click", () => postLabFusion("/debug/lab/fusion/volume-down"));
      document.getElementById("labMuteOn").addEventListener("click", () => postLabFusion("/debug/lab/fusion/mute-on"));
      document.getElementById("labMuteOff").addEventListener("click", () => postLabFusion("/debug/lab/fusion/mute-off"));
      refresh();
      setInterval(refresh, 2000);
    </script>
  </body>
</html>
"""
