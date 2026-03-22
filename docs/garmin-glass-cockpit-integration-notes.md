# Garmin Glass Cockpit + Raspberry Pi Integration Notes (R6 Surf)

Source basis: user-provided technical analysis (March 21, 2026).  
Status: engineering interpretation for this project; details are hypotheses until validated on target vessel.

## 1. Scope for this project

This document captures Garmin-display integration details that complement our NMEA-focused work:

- How a Raspberry Pi can present custom UI on Garmin MFDs.
- How Garmin display discovery likely works for a OneHelm-style HTML app.
- What network and middleware components are required for passive observability first.
- What must be validated before any bidirectional controls are considered.

## 2. Target helm architecture assumptions

Working assumptions for a 2023 Cobalt R6 Surf with dual Garmin displays:

- Dual Garmin MFDs (commonly `GPSMAP 743`, optionally `8610`) are present.
- NMEA 2000 (`250 kbps` CAN) is used for telemetry/control-class marine messages.
- Garmin Marine Network (Ethernet-based) is used for higher-bandwidth display/app transport.
- Pi integration for full value requires participation in both networks:
  - N2K side for raw vessel telemetry ingress.
  - Ethernet side for HTML UI delivery to Garmin displays.

## 3. Physical integration plan (project-safe)

### NMEA 2000 side

- Connect Pi via CAN interface (`PiCAN-M` style HAT or equivalent USB/CAN gateway).
- Join backbone through proper N2K T/drop topology.
- Keep Pi on dedicated, isolated `12V -> 5V` supply (do not power Pi from N2K device port).

### Garmin network side

- Connect Pi Ethernet to Garmin Marine Network hub/port via Garmin marine RJ45 adapter cable.
- Treat this as local vessel LAN for app serving/discovery.

### Power and reliability

- Use marine-suitable buck converter and stable fusing.
- Prefer high-endurance storage media (industrial SD or SSD) due to vibration.
- Expect thermal management needs for Pi 4/5 in enclosed helm spaces.

## 4. OneHelm-style discovery and app handshake (to verify)

Expected discovery chain to test in packet captures:

1. Pi advertises service via mDNS (`_garmin-mrn-html`).
2. Pi provides required TXT keys (at least `protovers=1`, `path=/config.json`).
3. Garmin probes discovery endpoints (including SSDP/UPnP behavior on local multicast).
4. Garmin requests app manifest (`/config.json`).
5. Manifest provides required identity/render fields:
   - `id` (UUID)
   - `title`
   - `icon`
   - `path`
6. Garmin shows app icon in OneHelm/Vessel UI and launches Pi-hosted HTML view.

Project rule: treat all discovery specifics as tentative until reproduced on our exact MFD firmware.

## 5. Middleware pattern for data to UI

Recommended data path for maintainable implementation:

1. N2K PGNs ingested by CAN interface.
2. CANboat performs canonical decode.
3. Signal K (or equivalent internal model) exposes normalized JSON/WebSocket data.
4. Pi-hosted HTML UI consumes normalized paths rather than raw CAN frames.

Example high-value read paths for surf operations:

- engine RPM and related propulsion telemetry
- ballast tank levels
- attitude (pitch/roll)
- battery state
- GPS/SOG and other environmental context

## 6. Control posture and guardrails

- Phase 1 remains read-only on live vessel.
- Command preview/validation stays enabled; live CAN write stays disabled until field-proven.
- Any future write enablement must be constrained to non-critical domains and audited.
- Surf propulsion/steering/safety systems remain out of scope.

## 7. Field validation checklist for Garmin display integration

Use this during first onboard integration session:

1. Confirm Pi is visible on Garmin network (device list/network diagnostics).
2. Confirm OneHelm app icon appears from discovery advertisements.
3. Confirm touch events reach Pi-hosted app with acceptable latency.
4. Confirm app refresh/reconnect behavior after MFD reboot and Pi reboot.
5. Confirm passive telemetry paths populate live values from N2K capture stream.
6. Confirm Pi failure does not degrade core Garmin navigation/helm behavior.

Acceptance criteria:

- Deterministic discovery after restart cycles.
- Stable UI rendering on both displays.
- No disruption to native Garmin or Cobalt controls.
- No unauthorized write traffic present on N2K bus.

## 8. Risks and unknowns to keep explicit

- MFD firmware differences can alter discovery/manifest expectations.
- Proprietary CSS/surf functions may not expose writable public PGNs.
- Network misconfiguration could create noisy traffic or operator confusion.
- Consumer SBC hardware must be hardened for heat, humidity, and vibration.

## 9. Immediate backlog from this research

- Add a dedicated "Garmin discovery diagnostics" endpoint/page in local tooling.
- Add capture scripts for mDNS/SSDP/HTTP handshake events on the Pi.
- Add UI profile support for dual-display layouts (primary nav vs surf analytics view).
- Add startup health checks that verify both N2K ingest and Garmin app serving paths.

## 10. Current implementation status in this repo

Implemented for simulation/testing (no live transmit):

- `GET /debug/garmin/switch-bank` returns a virtual switch bank profile.
- `GET /debug/garmin/switch-bank/template` returns editable typed JSON template.
- `PUT /debug/garmin/switch-bank` updates template with strict validation.
- Profile maps to standard switching PGNs:
  - Status: `127501`
  - Control: `127502`
- Includes conservative virtual controls (for planning):
  - `Evening Lights`
  - `Dock Quiet`
  - `All Accent Off`
- Each control is represented as one or more typed shadow commands (`audio.*` / `lighting.*`).
- Endpoint exposes `write_eligible=false` and current safety `gate_reason` when read-only mode is active.
- Every template update records a `garmin_switch_bank_profile_updated` system event with operator/reason and previous/new template snapshots.

This enables Garmin interoperability planning with standard control objects while preserving Phase 1 safety constraints.
