# 🚤 Cobalt Boat Automation Platform

**Target Platform:** 2023 Cobalt R6 Surf  
**Goal:** Safe, non-invasive observability + automation for lighting and audio systems via NMEA 2000.

---

## 🧭 Overview

This project builds a **headless onboard automation system** using a Raspberry Pi connected to the boat's **NMEA 2000 network**.

The system:

- Observes and decodes CAN/NMEA 2000 traffic
- Identifies controllable subsystems (audio, lighting)
- Provides safe, constrained control APIs
- Enables event-driven automations (Dock Mode, Surf Mode)
- Runs independently of internet connectivity

---

## 🎯 Core Goals

- Passive network observability
- Controlled interaction with:
  - Fusion audio system
  - Shadow-Caster lighting
- Safe, event-driven automation
- Clean, modular Python architecture
- Local-only control (no cloud dependency)

---

## 🚫 Non-Goals

- No propulsion, engine, or steering control
- No interference with safety-critical systems
- No replacement of Garmin UI
- No uncontrolled CAN transmission

---

## 🧱 Architecture

## Decoder Standard

- Authoritative decoder: **CANboat**
- Canonical command: `/usr/local/bin/cobalt-canboat-decoder`
- Startup behavior: decoder required by default (service fails fast if unavailable)

See setup guide: [`docs/canboat-setup.md`](docs/canboat-setup.md)

## Service Management

Install CANboat and systemd service on Pi:

```bash
sudo ./scripts/install_canboat.sh
sudo ./scripts/install_systemd_service.sh
sudo systemctl start cobalt-boat.service
```

Deployment details: [`docs/deployment.md`](docs/deployment.md)

## Auditability

- Installed software and libraries are tracked in [`docs/software-inventory.md`](docs/software-inventory.md)
- CANboat install metadata is written to `/usr/local/share/cobalt/canboat-install.txt`
- Runtime config is in `/etc/default/cobalt-boat`

## Local Test Harness

Offline CAN simulation (no boat required): [`docs/test-harness.md`](docs/test-harness.md)

## Shadow Command Mode

Read-only command validation endpoints (no CAN transmit):

- `POST /commands/preview`
- `POST /commands/validate`

These routes evaluate safety policy and write audit records, but always return `write_transmitted=false`.

## Garmin Standard Switching Simulation

For planning Garmin-compatible standard switch objects without Ethernet/OneHelm:

- `GET /debug/garmin/switch-bank`
- `GET /debug/garmin/switch-bank/template`
- `PUT /debug/garmin/switch-bank`

These endpoints return and update a simulated NMEA switch bank profile (PGNs `127501`/`127502`) with virtual controls like "Evening Lights". Updates require typed JSON validation and are written to audit/system events. No CAN messages are transmitted.

## Research Notes

Shadow-Caster-focused engineering notes from current research: [`docs/shadow-caster-research-notes.md`](docs/shadow-caster-research-notes.md)
Fusion MS-RA600 NMEA-focused integration notes: [`docs/fusion-ms-ra600-nmea-guide.md`](docs/fusion-ms-ra600-nmea-guide.md)
Garmin display + OneHelm integration notes: [`docs/garmin-glass-cockpit-integration-notes.md`](docs/garmin-glass-cockpit-integration-notes.md)
