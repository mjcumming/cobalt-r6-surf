
---

# 📁 2. `docs/design-spec.md`

```markdown
# 🧱 Design Specification

## 1. System Philosophy

This system is a **non-invasive marine automation platform**.

- Observes before acting
- Controls only non-critical systems
- Uses strict safety policies
- Designed for reliability over cleverness

---

## 2. Architecture Layers

### Layer 1 — Physical
- NMEA 2000 network
- Raspberry Pi + CAN HAT

### Layer 2 — CAN Interface
- SocketCAN (`can0`)
- 250 kbps

### Layer 3 — Data Decoding
- CANboat
- SignalK (optional)

### Layer 4 — Domain Layer
- Python abstraction
- Logical APIs (audio, lighting)

### Layer 5 — Policy Layer
- Command validation
- Safety enforcement
- Audit logging

### Layer 6 — API/UI
- FastAPI
- Local-only web interface

---

## 3. Core Patterns

### Event-Driven (Pub/Sub)
- System reacts to state changes

### CQRS
- Queries (read)
- Commands (write)

---

## 4. Command Model

Tiered approach:

### Tier 0
- Read-only

### Tier 1
- Replay known safe commands

### Tier 2
- Parameterized commands (validated)

---

## 5. Data Flow
