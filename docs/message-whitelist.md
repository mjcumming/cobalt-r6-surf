# ✅ Command Whitelist

## Allowed Commands

### Audio
- set volume
- mute/unmute
- change source

### Lighting
- zone on/off
- brightness
- color (validated set)

---

## Structure

Each command must define:

- PGN
- payload schema
- allowed values
- rate limit

---

## Example

```yaml
lighting_underwater_on:
  pgn: 127501
  payload: [...]
  safe: true