# Deployment Guide

This guide targets Raspberry Pi OS on a headless Pi connected to NMEA 2000 via SocketCAN.

## 1. Prepare runtime

From the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

## 2. Install CANboat (authoritative decoder)

```bash
sudo ./scripts/install_canboat.sh
/usr/local/bin/cobalt-canboat-decoder --self-check
```

Reference: [`docs/canboat-setup.md`](canboat-setup.md)

## 3. Install and enable systemd service + watchdog timer

```bash
sudo ./scripts/install_systemd_service.sh
sudo systemctl start cobalt-boat.service
```

Installer actions:

- Renders and installs `cobalt-boat.service` with detected repo owner/group/path.
- Installs `/etc/default/cobalt-boat` (backs up existing file first).
- Installs healthcheck assets:
  - `cobalt-boat-healthcheck.service`
  - `cobalt-boat-healthcheck.timer` (enabled and started)
  - `/usr/local/bin/cobalt-boat-healthcheck`
- Installs tmpfiles config and creates runtime/log directories.
- Installs logrotate policy for `/var/log/cobalt-boat/cobalt-boat.log`.

## 4. Verify

```bash
systemctl status cobalt-boat.service --no-pager
systemctl status cobalt-boat-healthcheck.timer --no-pager
journalctl -u cobalt-boat-healthcheck.service -n 50 --no-pager
sudo logrotate -d /etc/logrotate.d/cobalt-boat
journalctl -u cobalt-boat.service -n 100 --no-pager
curl -s http://127.0.0.1/health
curl -s http://127.0.0.1/status
```

Expected:

- `cobalt-boat.service` is `active (running)`
- `cobalt-boat-healthcheck.timer` is `active (waiting)`
- `/health` shows `decoder_ready=true`
- `/status` shows `read_only_mode=true` and `write_enable=false`

### Web UI and HTTP ports

The default install listens on **port 80** (`COBALT_API_PORT=80`) and **`0.0.0.0`**, so opening **`http://<Pi-address>/`** in a browser shows the dashboard. Optional HTTPS uses **`COBALT_API_SSL_CERTFILE`**, **`COBALT_API_SSL_KEYFILE`**, and typically port **443**. See [`docs/web-ui-and-http.md`](web-ui-and-http.md) and ADR [0004](adr/0004-web-ui-standard-http-telemetry.md). If you upgraded from an older env that used **`127.0.0.1:8080`**, re-run **`install_systemd_service.sh`** and restart the service so **`CAP_NET_BIND_SERVICE`** and the new env apply.

## 5. Update workflow

```bash
git pull
. .venv/bin/activate
pip install -e '.[dev]'
pytest -q
sudo systemctl restart cobalt-boat.service
```

## 6. Runtime configuration

Primary runtime settings live in `/etc/default/cobalt-boat`.

Critical defaults:

- `COBALT_DECODER_BACKEND=canboat`
- `COBALT_CANBOAT_COMMAND=/usr/local/bin/cobalt-canboat-decoder`
- `COBALT_DECODER_REQUIRED=true`
- `COBALT_READ_ONLY_MODE=true`
- `COBALT_WRITE_ENABLE=false`

### Logging, rotation, and SD card wear

- **Level:** `COBALT_LOG_LEVEL` (for example `INFO` on the boat, `WARNING` when stable, `DEBUG` only dock-side).
- **Text log file:** `COBALT_APP_LOG_PATH` (default under `/var/log/cobalt-boat/`).
- **In-process rotation:** `COBALT_LOG_MAX_BYTES` and `COBALT_LOG_BACKUP_COUNT` use Python’s `RotatingFileHandler` so a debug spike cannot grow one file without bound before the next system rotate.
- **System rotation:** `scripts/install_systemd_service.sh` installs `/etc/logrotate.d/cobalt-boat` (daily, compressed, `copytruncate`) for `/var/log/cobalt-boat/*.log`.

`systemd` also appends stdout/stderr to the same log file, so you normally inspect it with `tail -F` or your editor; detailed systemd status still comes from `journalctl -u cobalt-boat.service`.

**Larger write source than text logs:** every observed frame updates the **SQLite message catalog** (`COBALT_SQLITE_PATH`). A busy NMEA 2000 bus can generate far more SD traffic than application logging. Optional mitigations later: throttle or batch catalog updates, move `data/` to USB, or run long captures only dock-side. Raw JSONL capture sessions are **off** until you start one via the API.

**ZRAM / swap:** Enabling zram swap on Raspberry Pi OS (see Raspberry Pi documentation or `raspi-config` / `systemd-zram-generator`) reduces swap traffic to the SD card when memory pressure appears. It does **not** replace managing log level, rotation, and database write patterns.

### Dock-first operations

Plan on **SSH or copying `data/` and logs at the dock** (Wi-Fi, Tailscale, or physical access). The service is designed to run headless without a laptop in sunlight at the helm.

## 7. Recovery

If service fails to start:

1. `journalctl -u cobalt-boat.service -n 200 --no-pager`
2. Validate decoder: `/usr/local/bin/cobalt-canboat-decoder --self-check`
3. Confirm venv binary exists: `<repo>/.venv/bin/cobalt-boat-api`
4. Confirm env file values in `/etc/default/cobalt-boat`
5. Restart: `sudo systemctl restart cobalt-boat.service`

If healthcheck repeatedly fails:

1. `journalctl -u cobalt-boat-healthcheck.service -n 200 --no-pager`
2. Test manually: `/usr/local/bin/cobalt-boat-healthcheck`
3. Verify API locally: `curl -s http://127.0.0.1/health`

## See also

- [`dev-handoff-and-git.md`](dev-handoff-and-git.md) — Git workflow, opening the correct repo folder in the IDE, and a checklist for pausing development.
