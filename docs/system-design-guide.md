
# 🚤 Boat Automation Platform — Design Specification

*Target Platform: 2023 Cobalt R6 Surf*

---

## 1. Project Overview

This project aims to build a **non-invasive marine automation and observability platform** using a Raspberry Pi connected to the vessel’s **NMEA 2000 network**.

The system will:

* passively observe boat systems
* decode and structure marine data
* selectively enable safe control of non-critical subsystems
* provide a foundation for automation and dashboards

---

## 2. Core Objectives

### Primary Goals

1. **Network Observability**

   * Capture and decode NMEA 2000 traffic
   * Identify all devices on the network
   * Map PGNs to real-world actions

2. **Subsystem Control (Non-Critical)**

   * Fusion audio system (volume, source, zones)
   * Shadow-Caster lighting (zones, brightness, color)

3. **Automation**

   * Implement high-value user scenarios (Dock Mode, Surf Mode)
   * Enable event-driven behavior based on boat state

4. **System Architecture**

   * Build a reusable, modular marine automation platform
   * Maintain separation between raw CAN, decoded data, and automation logic

---

### Secondary Goals

* Data logging (trips, usage, telemetry)
* Mobile/dashboard interface
* Integration with home systems (optional future)
* Extensible framework for future sensors/devices

---

## 3. Explicit Non-Goals (Phase 1)

The system will **NOT**:

* control propulsion, steering, or engine management
* interfere with safety-critical systems
* replace OEM Garmin or vessel control interfaces
* inject commands without understanding their effect

---

## 4. System Architecture

### Layered Design

```
[ Boat Systems ]
    │
    ▼
[NMEA 2000 Backbone]
    │
    ▼
[Raspberry Pi + CAN Interface]
    │
    ▼
[SocketCAN (can0)]
    │
    ▼
[SignalK + CANboat]
    │
    ▼
[Control Abstraction Layer (Python)]
    │
    ▼
[Automation Engine]
    │
    ▼
[UI / Dashboard / API]
```

---

## 5. Hardware Components

### Required

* Raspberry Pi (Pi 4 or Pi 5)
* CAN interface (Pi-CAN-M or equivalent)
* NMEA 2000 drop cable + T connector
* Dedicated 12V → 5V power supply (isolated preferred)

### Optional (Future)

* Dual CAN interface (for accessory bus)
* Isolated CAN transceiver (for electrical protection)
* WiFi AP for onboard access

---

## 6. Software Stack

### Core Components

| Layer           | Tool                                       |
| --------------- | ------------------------------------------ |
| OS              | Raspberry Pi OS                            |
| CAN Interface   | SocketCAN                                  |
| Low-Level Tools | `can-utils`                                |
| NMEA Decoding   | CANboat                                    |
| Data Model      | SignalK                                    |
| Automation      | Python service / Home Assistant (optional) |

---

### Supporting Libraries

* `python-can` (CAN interface)
* `canboat` / `analyzer` (PGN decoding)
* SignalK plugins (NMEA input/output)

---

## 7. Data & Control Model

### Architecture Pattern

#### Event-Driven (Pub/Sub)

* CAN bus publishes events
* SignalK distributes structured data
* Automation layer subscribes and reacts

---

#### CQRS (Command / Query Separation)

| Type    | Description                                     |
| ------- | ----------------------------------------------- |
| Query   | Continuous telemetry (RPM, GPS, lighting state) |
| Command | Discrete actions (set volume, toggle lights)    |

---

### Example Logical Abstractions

```python
set_underwater_lights(on)
set_tower_color("blue")
set_stereo_volume(zone="rear", level=70)
```

No automation should directly use raw PGNs.

---

## 8. Safety Design

### Core Safety Rules

1. **Read-Only First**

   * Initial operation is strictly passive
   * No transmission onto CAN bus

2. **Manual Parity Validation**

   * Only replicate commands already issued by Garmin UI

3. **Non-Critical Scope Only**

   * Lighting
   * Audio
   * UI/comfort features

4. **Fail-Safe Behavior**

   * Pi failure must not impact boat operation
   * System must be removable without consequence

5. **Controlled Write Enablement**

   * Writing enabled only after:

     * message identification
     * repeatability testing
     * no side effects observed

---

## 9. Development Phases

### Phase 0 — Design

* Define goals, architecture, constraints
* Create documentation (this file)

---

### Phase 1 — Platform Bring-Up

* Configure Pi CAN interface (`can0`)
* Validate connectivity with `candump`
* Ensure stable system operation

---

### Phase 2 — Network Discovery

Tasks:

* capture raw CAN traffic
* identify devices (source addresses)
* log PGNs
* categorize messages

Deliverable:

* device inventory
* message catalog

---

### Phase 3 — Reverse Engineering

Method:

1. perform action on Garmin (e.g., change light color)
2. capture traffic
3. isolate new/different messages
4. map PGN → function

Targets:

* Fusion audio control
* lighting control

---

### Phase 4 — Command Replay

* reproduce known commands via software
* validate deterministic behavior
* confirm no unintended side effects

---

### Phase 5 — Abstraction Layer

Create a clean API:

```python
lighting.set_zone("underwater", on=True)
audio.set_volume(zone="cockpit", level=60)
```

---

### Phase 6 — Automation

Implement first scenarios:

#### Dock Mode

* underwater lights on
* cockpit lighting preset
* stereo low volume

#### Surf Mode

* lighting scene
* audio tuning

---

### Phase 7 — Hardening

* logging
* service startup
* watchdog
* configuration management
* rollback capability

---

## 10. Device Discovery Strategy

### Tools

```bash
candump can0
candump can0 | analyzer
```

### Workflow

1. baseline capture
2. perform single action
3. capture delta
4. repeat for validation

---

## 11. Known / Expected Systems

Likely present on **Cobalt R6 Surf**:

* Garmin MFD(s)
* Fusion stereo
* engine gateway
* Shadow-Caster lighting controller
* digital switching module

---

## 12. Risks & Unknowns

| Area                 | Risk                                  |
| -------------------- | ------------------------------------- |
| Lighting control     | proprietary PGNs                      |
| CAN bus segmentation | accessory bus may be separate         |
| command collisions   | multiple controllers issuing commands |
| electrical noise     | marine power environment              |

---

## 13. Future Extensions

* dual CAN bus integration (CAN2)
* trip logging + analytics
* battery/voltage monitoring
* geofencing automations
* remote access
* cabin integration (Minaki system)

---

## 14. Success Criteria

Phase 1 complete when:

* `candump` shows live NMEA traffic
* devices identifiable

Phase 2 complete when:

* Fusion and lighting commands identified

Phase 3 complete when:

* at least one command reproducible

Phase 4 complete when:

* one automation works reliably end-to-end

---

## 15. Guiding Principle

> **Observe → Understand → Replicate → Abstract → Automate**

Never skip steps.

---

## 16. Architecture decisions (ADRs)

Implementation and operations choices (systemd, logging, offline validation, etc.) are recorded as **Architecture Decision Records** in [`docs/adr/README.md`](adr/README.md). Update or add an ADR when changing those conventions so dock-side and boat installs stay aligned.


