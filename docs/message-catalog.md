
---

# 📁 5. `docs/message-catalog.md`

```markdown
# 📚 Message Catalog

## Purpose

Track known CAN/NMEA messages.

---

## Format

| PGN | Device | Action | Payload | Confidence | Notes |
|-----|------|--------|--------|------------|------|

---

## Example

| PGN | Device | Action | Payload | Confidence | Notes |
|-----|------|--------|--------|------------|------|
| 127501 | Lighting | Underwater ON | ... | High | Confirmed |

---

## Rules

- Only validated entries marked "High"
- Unknown messages tracked separately
- Commands must be cataloged before use