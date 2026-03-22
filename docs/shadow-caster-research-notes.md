# Shadow-Caster Research Notes (Actionable for Cobalt Platform)

Source basis: user-provided research summary (March 21, 2026).  
Status: engineering interpretation for project planning; not all claims are yet validated on target vessel.

## 1. What matters immediately for this project

- Shadow-Caster control appears to be split across:
  - NMEA 2000 control/interop path (MFD-facing)
  - Shadow-NET high-speed effects path (controller-to-fixture internals)
- For Cobalt platform scope, the safe integration point is NMEA 2000 observation first.
- We should treat all lighting control PGN mappings as hypotheses until confirmed via captures on the real R6 Surf bus.

## 2. Candidate NMEA 2000 PGNs to watch first

These were called out in the research and are the highest-priority PGNs for cataloging/diff tests:

- `127500` (`Load Control`) - likely command semantics
- `127501` (`Binary Status Report`) - likely output state/status
- `127502` (`Switch Bank Control`) - likely virtual switch events
- `126996` (`Product Information`) - device identification
- `126464` (`PGN List`) - capability discovery
- `060928` (`ISO Address Claim`) - device address claim
- `130824` (proprietary status, manufacturer-specific) - possible extended status

Project implication:

- Add explicit PGN tags in our message catalog tooling for these values.
- Build first on passive inference from correlation, not write attempts.

## 3. Architecture guidance for our codebase

- Keep CANboat authoritative for decode semantics.
- Keep Domain Layer abstraction strict (`lighting`, `audio`) and avoid leaking raw PGN usage outside domain/policy internals.
- Continue CQRS split:
  - Queries: telemetry/status/catalog
  - Commands: shadow-mode preview/validate only until proven-safe command signatures exist
- Keep write path disabled by default and audit every attempted command (already implemented).

## 4. Control strategy for pre-boat development (safe)

Do now:

- Build typed lighting command specifications (already started in shadow mode):
  - `lighting.set_brightness`
  - `lighting.set_color`
- Expand validation policy to include:
  - zone allowlists
  - value ranges (brightness 0-100, RGB bounds)
  - per-command cooldown
- Build replay/diff tooling that compares capture windows before/after known user actions.

Do not do yet:

- No CAN transmit on live NMEA 2000.
- No direct Shadow-NET control assumptions.
- No propulsion/surf/ballast/trim related behavior.

## 5. Field capture plan for first live boat session

Primary objective: identify reliable, repeatable lighting/audio signatures while remaining passive.

Sequence:

1. Start capture.
2. Record idle baseline (2-3 minutes).
3. Perform one manual MFD action at a time (e.g., underwater lights on).
4. Record post-action window (20-30 seconds).
5. Repeat for off, brightness changes, color changes, zone changes.
6. Export session annotations mapping timestamp to manual action.

Acceptance criteria for a "candidate controllable action":

- Repeatable PGN pattern across at least 3 trials.
- Same source/destination behavior each time.
- No overlap with denied/safety-critical domains.
- Human-readable interpretation from CANboat output is consistent.

## 6. Risks and caveats to keep explicit

- Manufacturer implementations vary by firmware and MFD brand behavior.
- Some lighting semantics may use proprietary PGNs and not be portable.
- MFD may cache configuration/state and affect apparent behavior during swaps.
- Some claims in research (feature support matrix, exact protocol usage) require on-vessel verification.

## 7. Immediate backlog items derived from this research

- Add "candidate PGN watchlist" feature in debug page.
- Add capture annotation support (`action_label`, `operator_note`, timestamp).
- Add catalog export/report command for offline reverse engineering.
- Add "confidence" metadata in message catalog entries (low/medium/high) based on repeatability.

## 8. Working assumptions (to revisit after boat data)

- Shadow-Caster Light Commander is present on NMEA 2000 bus.
- NMEA 2000 PGNs are sufficient for top-level state/control intent.
- Shadow-NET remains internal to fixture ecosystem and not directly required for our integration layer.

