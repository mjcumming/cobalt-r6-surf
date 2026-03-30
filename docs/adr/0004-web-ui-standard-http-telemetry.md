# ADR 0004: Web UI, standard HTTP/HTTPS ports, and live telemetry

## Status

Accepted

## Context

Operators need to reach the onboard API from a phone or laptop **without memorizing paths or nonstandard ports**. Earlier defaults (`127.0.0.1`, port `8080`, root redirecting only to `/debug`) made the service easy to miss on the LAN and tied browsing to IDE port forwarding. We also want a **simple dashboard** that shows commonly useful decoded NMEA 2000 quantities when CANboat supplies structured `fields`, without replacing Garmin as the primary helm UI.

## Decision

1. **Bind address:** Default **`COBALT_API_HOST=0.0.0.0`** in the shipped systemd env so the service is reachable on the boat LAN by **IP or hostname**.
2. **HTTP port:** Default **`COBALT_API_PORT=80`** so browsers can open **`http://<device>/`** with no port suffix. Code defaults match (`Settings.api_port=80`) so ad-hoc runs align with production unless overridden.
3. **Privileged ports without root:** The systemd unit grants **`CAP_NET_BIND_SERVICE`** (and matching **`CapabilityBoundingSet`**) so the service user can bind **80** or **443** without running as root. **`NoNewPrivileges=true`** remains; ambient capabilities are inherited at exec.
4. **HTTPS (optional):** Support **`COBALT_API_SSL_CERTFILE`** and **`COBALT_API_SSL_KEYFILE`**. When both paths exist and point to readable files, **`uvicorn`** is started with **`ssl_certfile`** / **`ssl_keyfile`**. Typical production pairing is **`COBALT_API_PORT=443`**. Self-signed or local CA is an operator concern; the app does not manage ACME.
5. **Routes:**
   - **`/`** — Operator **dashboard** (engine/nav snapshot + navigation to other pages).
   - **`/api/telemetry`** — JSON snapshot of last-known metrics (for the dashboard and future clients).
   - **`/debug`** — Full **debug console** (catalog, watchlist, logs, Garmin template, lab controls).
   - **`/debug/lab`** — **Lab transmit** page only (Fusion stub buttons); same **`POST /debug/lab/fusion/...`** APIs as before.
6. **Telemetry pipeline:** Introduce **`BoatTelemetryStore`** subscribed to **`can.message_decoded`**. Extract values from CANboat **`fields`** using PGNs and keys aligned with **canboat `pgn.h`** (e.g. **127488** `Speed`, **127489** coolant-related `Temperature`, **128259** `Speed Water Referenced`, **129026** `SOG`, **129025/129029** `Latitude`/`Longitude`). The SQLite **message catalog** remains sample-hex-oriented; telemetry is a separate in-memory projection for readability.
7. **Healthcheck:** **`cobalt-boat-healthcheck`** reads **`COBALT_API_PORT`** (default **80**) and **`EnvironmentFile=/etc/default/cobalt-boat`**. If TLS files from env exist on disk, it probes **`https://127.0.0.1:…`** with verification disabled for localhost (boat self-signed cases).

## Consequences

- **Reinstall or edit `/etc/default/cobalt-boat`** is required on existing Pis that still had **`127.0.0.1:8080`**; otherwise nothing listens on port **80** and the LAN sees no UI.
- Developers on workstations **without** capability to bind port **80** can set **`COBALT_API_PORT=8080`** (or similar) for local runs.
- **Dual HTTP+HTTPS on one process** is not implemented; HTTPS mode is a single TLS listener on the configured port. Terminating TLS in **nginx**/Caddy in front of the app remains a valid alternative.
- Telemetry appears missing until the bus emits the relevant PGNs **and** the **canboat** backend returns **`fields`** (the **basic** decoder does not).

## Related documentation

- Operator reference: [`../web-ui-and-http.md`](../web-ui-and-http.md)
- Deployment: [`../deployment.md`](../deployment.md)
