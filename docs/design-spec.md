# Design specification

## 1. System philosophy

This system is a **non-invasive marine automation platform**.

- Observes before acting
- Controls only non-critical systems
- Uses strict safety policies
- Designed for reliability over cleverness

---

## 2. Architecture layers

### Layer 1 — Physical

- NMEA 2000 network
- Raspberry Pi + CAN HAT

### Layer 2 — CAN interface

- SocketCAN (`can0`)
- 250 kbps

### Layer 3 — Data decoding

- CANboat (authoritative payload decode)
- Optional: SignalK and other consumers of the same bus

### Layer 4 — Domain layer

- Python models and services (PGN-oriented views, subsystems)

### Layer 5 — Policy layer

- Command validation
- Safety enforcement
- Audit logging

### Layer 6 — API / UI

- FastAPI
- **Operator dashboard** at `/`, **JSON telemetry** at `/api/telemetry`, **debug console** at `/debug`, **lab transmit** page at `/debug/lab`
- Default deployment: **HTTP on port 80** on the boat LAN; optional **HTTPS** via TLS file paths and port **443** (see [`web-ui-and-http.md`](web-ui-and-http.md))
- Local-only HTTP API, shadow command endpoints, and simulation/debug surfaces

---

## 3. Core patterns

### Event-driven (pub/sub)

The platform reacts to decoded bus events and internal signals.

### CQRS-style split

- Reads: status, catalog, health, **telemetry snapshot** (last-known decoded engine/nav fields)
- Writes: gated commands, profile updates, capture sessions (all policy-controlled)

---

## 4. Command model

Tiered approach:

### Tier 0

- Read-only observation

### Tier 1

- Replay known safe commands (when explicitly enabled)

### Tier 2

- Parameterized commands (validated, audited)

---

## 5. Data flow

Observed CAN frames flow:

**SocketCAN** → `parse_nmea2000_id` → **`CanEvent`** → decoder (CANboat or basic) → **SQLite message catalog** / **event bus**.

Optional **raw JSONL capture** is **off** until an operator starts a capture session via the API, to limit storage and SD wear.

---

## 6. Operations and deployment

- Runtime is **headless** on Raspberry Pi OS; primary unit is **`cobalt-boat.service`** (see [`deployment.md`](deployment.md)).
- **Logging:** `COBALT_LOG_LEVEL`, optional file path, in-process **size-based rotation** (`COBALT_LOG_MAX_BYTES`, `COBALT_LOG_BACKUP_COUNT`) plus **logrotate** for `/var/log/cobalt-boat/*.log`. The log directory is created for the **service user** via **systemd tmpfiles** so the app and `RotatingFileHandler` can write without running as root.
- **CANboat** is checked at service start (`cobalt-canboat-decoder --self-check`); pinned version expectations are documented in [`canboat-setup.md`](canboat-setup.md).
- **Dock-side** iteration (tests, captures, SSH) is the default; the boat carries **stable** installs.
- **Lab CAN transmit** (Fusion PGN 126208 **placeholder** payloads) is opt-in via env flags for **`vcan`** verification only; see ADR 0003.

---

## 7. Testing strategy (summary)

- **pytest:** configuration, decoder adapter, **NMEA 2000 CAN ID** parsing (`tests/test_nmea2000_id.py`), **candump log lines** → frames/events (`tests/fixtures/`, `tests/test_candump_parser.py`).
- **vcan / can-utils:** local bus simulation without the vessel ([`test-harness.md`](test-harness.md)).

---

## 8. Architecture decisions

Normative decisions and rationale live in **[Architecture Decision Records](adr/README.md)** (`docs/adr/`).
