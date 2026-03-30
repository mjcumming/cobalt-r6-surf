# Fusion MS-RA600 NMEA 2000 Integration Notes (Project-Focused)

Source basis: user-provided technical analysis (March 21, 2026).  
Status: engineering interpretation for Cobalt R6 Surf implementation; items remain hypotheses until validated on-vessel.

## 1. What matters immediately for this project

- The Fusion `MS-RA600` is expected to be controllable from Garmin MFDs over `NMEA 2000` (CAN, `250 kbps`).
- Our platform should treat the stereo as a non-critical, in-scope subsystem for eventual constrained control.
- Initial phase remains passive: observe traffic, map PGNs, verify repeatability, then consider replay.

## 2. Candidate PGN watchlist for Fusion discovery and control

Highest-priority PGNs to label and track in captures:

- `059392` (`ISO Acknowledgement`) - confirms command receipt/execution semantics.
- `060928` (`ISO Address Claim`) - source address ownership and re-claim behavior.
- `126208` (`NMEA - Command/Request/Acknowledge Group Function`) - primary control path used by MFDs.
- `126464` (`PGN List`) - capability discovery.
- `126996` (`Product Information`) - product identification.
- `127488` (`Engine Parameters, Rapid Update`) - optional speed-volume input when RPM-based.
- `128259` (`Speed, Water Referenced`) - optional speed-volume input when STW-based.
- `129026` (`COG/SOG, Rapid Update`) - optional speed-volume input when SOG-based.
- `130306` (`Wind Data`) - optional speed-volume input for sail setups.
- `130567` (`Entertainment - System Status`) - power/mute/system state.
- `130569` (`Entertainment - Current File and Status`) - track metadata (fast-packet behavior likely).
- `130573` (`Entertainment - Supported Source Data`) - source inventory.
- `130574` (`Entertainment - Supported Zone Data`) - zone inventory and naming.
- `130582` (`Entertainment - Zone Volume`) - zone volume + possible sub level fielding.
- `126720` (proprietary fast packet) - potential Fusion-Link extended controls.
- `130820` (proprietary server message) - potential Fusion-Link extended controls.

Project implication:

- Start with decode/tagging and correlation of `126208` requests to `130582`/status changes.
- Treat proprietary PGNs as opaque until repeatable decode patterns emerge.

## 3. PGN priority tiers (operational)

Use these tiers in debug watchlists and analysis passes.

### Tier A (primary command/state chain)

- `126208` (command/request)
- `059392` (ack)
- `130567` (system state)
- `130582` (zone volume)
- `130573` / `130574` (source/zone capability)

### Tier B (identity/discovery/session context)

- `060928` (address claim)
- `126464` (PGN list)
- `126996` (product info)

### Tier C (contextual/proprietary or optional dependencies)

- `126720`, `130820` (proprietary)
- `127488`, `128259`, `129026`, `130306` (speed/wind context)
- `130569` (metadata fast-packet; useful but not primary for first control mapping)

## 4. Expected control flow on Garmin + Fusion

Working model to validate in captures:

1. Fusion claims a source address (`060928`) on bus startup.
2. Garmin discovers stereo (`126996`/`126464`) and enables Media UI.
3. User interaction on Garmin emits `126208` commands targeting Fusion address.
4. Fusion emits `059392` acknowledgement and updated entertainment status (`130567`, `130582`, etc.).
5. All controllers (second MFD, remotes) converge to the new state through broadcast updates.

If this model holds, it gives a deterministic state machine for safe command validation and replay.

## 5. Correlation rules (tooling acceptance checks)

Use these rule templates in offline analysis/reporting:

- Rule `R1` (volume action candidate):
  - detect `126208` from Garmin source to Fusion destination
  - observe `059392` within `0-2s`
  - observe `130582` update within `0-3s`
- Rule `R2` (source-change action candidate):
  - detect `126208`
  - observe `059392` within `0-2s`
  - observe `130567` and/or `130573`/`130569` changes within `0-5s`
- Rule `R3` (negative check):
  - no unexpected non-audio domain side effects in same action window

If `R1`/`R2` fail intermittently, classify as low confidence and keep read-only.

## 6. Physical/network assumptions to validate on boat

- NMEA 2000 backbone is terminated at both ends (`120 ohm` each).
- Bus resistance measured unpowered across CAN-H/CAN-L should be near `60 ohm`.
- Drop length constraints and power integrity impact control responsiveness and device visibility.
- Fusion head unit has separate high-current power for amplification; N2K interface behavior may remain present based on internal power settings.

Practical diagnostics during field sessions:

- If stereo disappears from MFD: inspect `060928` churn and power state behavior.
- If volume control lags: inspect bus load and retransmission/error indicators.
- If track metadata is partial/missing: inspect fast-packet continuity/timeouts for `130569`.

## 7. Project safety posture for Fusion control

- Keep write path disabled by default until command mappings are proven repeatable.
- Restrict scope to audio comfort functions only:
  - volume/mute
  - source selection
  - zone-level controls
- Exclude any control surface that overlaps safety-critical domains.
- Require audit logs for every control intent and every rejected command.

## 8. Mapping to current shadow command API

Use this direct mapping while still in no-transmit mode:

- `audio.set_volume`
  - expected eventual PGN chain: `126208 -> 059392 -> 130582`
  - current implementation: `POST /commands/preview` or `/commands/validate`
- `audio.set_source`
  - expected eventual PGN chain: `126208 -> 059392 -> 130567/130573/130569`
  - current implementation: `POST /commands/preview` or `/commands/validate`

Keep `write_transmitted=false` until on-vessel confidence is high.

## 9. Field capture plan (Fusion-specific)

Primary objective: build high-confidence mapping from user action to PGN signature.

1. Start passive capture and log idle baseline (2-3 minutes).
2. Execute one Garmin action at a time:
   - zone 1 volume up/down
   - zone 2 volume up/down
   - mute/unmute
   - source change
   - track next/previous (if active source supports it)
3. Record 20-30 seconds after each action.
4. Repeat each action at least 3 times.
5. Annotate timestamps with manual action labels.

Candidate command confidence criteria:

- Repeatable PGN sequence across trials.
- Consistent source/destination behavior.
- Deterministic resulting status broadcast.
- No observed side effects outside audio scope.

## 10. Confidence rubric (required for mapping catalog)

Apply this rubric to each candidate action mapping.

| Confidence | Required Evidence |
|---|---|
| Low | Pattern observed at least once, but missing deterministic ack/status chain |
| Medium | Pattern observed in at least 2 trials, mostly stable chain with minor variance |
| High | Pattern observed in at least 3 clean trials, deterministic chain, no side effects |

Only `High` mappings should be candidates for future controlled replay evaluation.

## 11. Immediate backlog derived from this research

- Add Fusion Tier A PGN watchlist tags to message-catalog workflow.
- Add correlation tooling for `126208` command -> acknowledgement -> state update chain.
- Add confidence metadata (`low`/`medium`/`high`) for Fusion action mappings.
- Add offline test fixtures for expected volume/source command traces.

## 12. Known limitations and expectations

- `MS-RA600` is NMEA 2000-centric and lacks Ethernet-class media features.
- Expect control + metadata support, but not high-bandwidth UI features (for example album art).
- Firmware behavior can vary by stereo and MFD versions; all mappings require validation on target boat.

## 13. Lab transmit stubs (Cobalt platform)

The API exposes **debug-only** `POST /debug/lab/fusion/*` routes that send **single-frame PGN 126208** messages with **distinct placeholder payloads** (volume up/down, mute on/off). These exist to prove **SocketCAN transmit**, policy gating, and auditing on **`vcan`** — **not** as a correct Fusion-Link encoding.

To arm transmit (requires **service restart** after env change):

- `COBALT_LAB_TRANSMIT_ENABLED=true`
- `COBALT_READ_ONLY_MODE=false`
- `COBALT_WRITE_ENABLE=true`
- Optional: `COBALT_LAB_TRANSMIT_SOURCE_ADDRESS`, `COBALT_LAB_FUSION_DEST_ADDRESS` (defaults: `0x90` → `255` global PDU1 destination)

Replace the placeholder bytes in `src/cobalt_boat/domains/fusion_lab.py` with **capture-derived** data once field confidence is high (see §10).
