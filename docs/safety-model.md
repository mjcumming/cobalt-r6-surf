# 🔐 Safety Model

## 1. Default State

- System starts in **read-only mode**

---

## 2. Write Enable Conditions

Commands allowed only if:

- Device is whitelisted
- Command matches known pattern
- Payload validated
- System not in restricted mode
- Audit log entry created

---

## 3. Allowed Domains

- Audio (Fusion)
- Lighting (Shadow-Caster)

---

## 4. Denied Domains

Never allowed:

- Engine / propulsion
- Steering
- Surf systems
- Ballast
- Trim tabs

---

## 5. Fail-Safe Design

- Pi failure → no impact to boat
- No inline control dependencies
- No interception of CAN messages

---

## 6. Rate Limiting

- Prevent command flooding
- Enforce cooldown between writes

---

## 7. Audit Logging

Every command logs:

- timestamp
- command type
- parameters
- result
- approval/denial reason

---

## 8. Emergency Disable

- Config flag disables all writes
- Runtime toggle available