# Web UI, HTTP, and telemetry

Quick reference for browsers and integrators after a normal [`deployment.md`](deployment.md) install.

## URLs (default install)

| Page | Path | Purpose |
| --- | --- | --- |
| Dashboard | `http://<pi-ip>/` | Live snapshot of decoded engine/nav metrics; links to Debug and Lab |
| Telemetry JSON | `http://<pi-ip>/api/telemetry` | Same metrics as structured JSON |
| Debug console | `http://<pi-ip>/debug` | Catalog, watchlist, logs, Garmin switch-bank template, lab controls |
| Lab transmit | `http://<pi-ip>/debug/lab` | Fusion stub buttons only (`POST /debug/lab/fusion/...`) |
| Health | `http://<pi-ip>/health` | Liveness / decoder readiness |
| Status | `http://<pi-ip>/status` | Mode flags (`read_only_mode`, `write_enable`, etc.) |

Use **`https://`** and port **443** when TLS env vars are set (see below).

## Troubleshooting

- **“Wrong” port in the browser:** If an **IDE** shows something like `http://127.0.0.1:62528`, that is usually **port forwarding** to the Pi’s app—not the boat Wi‑Fi URL. On the boat network use **`http://<Pi-LAN-IP>/`** (default install, port **80**).
- **Nothing on port 80:** Confirm `/etc/default/cobalt-boat` has **`COBALT_API_PORT=80`** and **`COBALT_API_HOST=0.0.0.0`**, the systemd unit includes **`CAP_NET_BIND_SERVICE`**, and you ran **`sudo systemctl restart cobalt-boat.service`** after changes. Re-run **`sudo ./scripts/install_systemd_service.sh`** if the unit predates those defaults.

## Environment variables (`/etc/default/cobalt-boat`)

| Variable | Role |
| --- | --- |
| `COBALT_API_HOST` | Bind address; **`0.0.0.0`** for all interfaces |
| `COBALT_API_PORT` | **`80`** HTTP default; **`443`** common with TLS |
| `COBALT_API_SSL_CERTFILE` | Optional PEM cert path |
| `COBALT_API_SSL_KEYFILE` | Optional PEM key path |

If both SSL paths exist and files are present, the API serves **HTTPS** on `COBALT_API_PORT`.

After changing the env file: **`sudo systemctl restart cobalt-boat.service`**.

If the unit was installed before port **80** / capabilities were added, re-run:

```bash
sudo ./scripts/install_systemd_service.sh
sudo systemctl restart cobalt-boat.service
```

## Telemetry fields (`/api/telemetry`)

Values update when CANboat decodes the PGN and includes a `fields` object. Names follow CANboat’s analyzer output.

| Display | PGN | Typical `fields` keys |
| --- | --- | --- |
| Engine RPM | 127488 | `Speed` |
| Coolant °C | 127489 | `Temperature` (and coolant aliases) |
| Speed through water | 128259 | `Speed Water Referenced` (m/s; UI shows knots too) |
| Speed over ground | 129026 | `SOG` |
| Position | 129025, 129029 | `Latitude`, `Longitude` |

Missing rows usually mean the PGN is absent on the bus, fast-packet decode did not yield fields, or the decoder backend is **basic** (no `fields`).

## Architecture decision

Rationale and trade-offs: [`adr/0004-web-ui-standard-http-telemetry.md`](adr/0004-web-ui-standard-http-telemetry.md).
