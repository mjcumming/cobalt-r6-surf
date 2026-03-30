# ADR 0003: Gated lab CAN transmit (Fusion stub frames)

## Status

Accepted

## Context

We need a **controlled** path to exercise **SocketCAN transmit** and end-to-end **policy + audit** before trusting any real Fusion command encoding. Raw hex paste is error-prone; high-level **volume / mute** actions match operator intent and future production command shapes.

## Decision

1. Add **`SocketCanTransmitter`** (lazy `python-can` `Bus.send`) separate from the read-only listener.
2. Instantiate it only when **`COBALT_LAB_TRANSMIT_ENABLED=true`** (service restart required).
3. **`build_nmea2000_can_id`** encodes PGN **126208** (PDU1) with configurable source and destination addresses.
4. **`fusion_lab.py`** holds **placeholder 8-byte payloads** (distinct per action) for **`candump`** visibility on **`vcan`**; they are **not** asserted to control a real MS-RA600 until replaced from vessel captures.
5. Each button/API call runs **`PolicyEngine.evaluate`** for **`audio.lab_volume_step`** or **`audio.lab_mute`** (whitelist) after the same gates as production writes: **`read_only_mode`**, **`write_enable`**, **`emergency_disable`**, rate limits.
6. Debug UI buttons call **`POST /debug/lab/fusion/...`** and show JSON results; **`/status`** exposes **`lab_transmit_enabled`**.

## Consequences

- **Boat default remains safe:** all lab flags off; production installs unchanged.
- **Real Fusion control** still requires validated **126208** (and possibly fast-packet) byte sequences; until then, lab mode is for **bus plumbing verification** only.
- Two `python-can` handles on one interface (RX listener + TX) are accepted on Linux SocketCAN for this use case.
