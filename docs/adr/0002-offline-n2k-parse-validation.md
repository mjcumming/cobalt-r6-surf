# ADR 0002: Offline NMEA 2000 ID and candump validation

## Status

Accepted

## Context

Parser and ingest code should be verified **before** relying on it on the boat. Field debugging on the water is costly; regressions in CAN ID → PGN mapping would corrupt the message catalog and downstream logic.

## Decision

1. **Unit tests** assert known **29-bit NMEA 2000 CAN IDs** decode to the expected priority, PGN, source address, and (for PDU1) destination address (`tests/test_nmea2000_id.py`).
2. A small **`cobalt_boat.can.candump_parse`** module parses common **candump** log line shapes into `RawCanFrame`, then attaches metadata via the same `parse_nmea2000_id` used in production.
3. **Fixture files** under `tests/fixtures/` (e.g. `office_sample.candump`) hold representative lines; operators can append real captures for regression tests.
4. **Integration with the decoder smoke path:** fixtures are fed through `BasicNmeaDecoder` to ensure the event → decode pipeline accepts realistic events.

## Consequences

- NMEA **0183** ASCII sentences are out of scope unless a separate serial path is added later.
- Payload field semantics remain the responsibility of **CANboat**; these tests focus on **ID parsing** and **log ingest**, not full PGN field matrices.
- A large “Garmin catalog” of messages is unnecessary for confidence; **real bus captures** plus a **small set of documented vectors** are preferred.
