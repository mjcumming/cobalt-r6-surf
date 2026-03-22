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
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/status
```

Expected:

- `cobalt-boat.service` is `active (running)`
- `cobalt-boat-healthcheck.timer` is `active (waiting)`
- `/health` shows `decoder_ready=true`
- `/status` shows `read_only_mode=true` and `write_enable=false`

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
3. Verify API locally: `curl -s http://127.0.0.1:8080/health`
