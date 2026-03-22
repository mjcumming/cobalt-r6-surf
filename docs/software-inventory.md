# Software Inventory

This document records software/libraries used by the platform and how they are installed.

## 1. Operating system and core runtime

- Raspberry Pi OS (Debian-based)
- Python 3.11+ (project runtime)
- `systemd` (service supervision and watchdog timer)

## 2. Python packages (project dependencies)

Declared in `pyproject.toml`:

- `fastapi`
- `uvicorn`
- `python-can`

Development/testing extras:

- `pytest`
- `httpx`
- `ruff`
- `mypy`

Installed in project virtual environment:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

## 3. CANboat (authoritative decoder)

Installed via:

```bash
sudo ./scripts/install_canboat.sh
```

Pinned defaults in installer:

- repository: `https://github.com/canboat/canboat.git`
- version tag: `v6.1.6`
- install prefix: `/usr/local`

Installed binaries used by this project:

- `/usr/local/bin/analyzer`
- `/usr/local/bin/cobalt-canboat-decoder` (project wrapper)

Install metadata written to:

- `/usr/local/share/cobalt/canboat-install.txt`

## 4. APT packages installed by CANboat installer

- `build-essential`
- `git`
- `libsocketcan-dev`
- `pkg-config`
- `ca-certificates`

## 5. Additional tooling for local test harness

- `can-utils`
  - `cangen` (synthetic traffic)
  - `canplayer` (replay `candump` logs)
  - `candump` (capture bus traffic)

## 6. System services and operational assets

Installed via:

```bash
sudo ./scripts/install_systemd_service.sh
```

Systemd units:

- `/etc/systemd/system/cobalt-boat.service`
- `/etc/systemd/system/cobalt-boat-healthcheck.service`
- `/etc/systemd/system/cobalt-boat-healthcheck.timer`

Runtime environment file:

- `/etc/default/cobalt-boat`

Runtime helper binary:

- `/usr/local/bin/cobalt-boat-healthcheck`

Tempfiles policy:

- `/etc/tmpfiles.d/cobalt-boat.conf`

Log rotation policy:

- `/etc/logrotate.d/cobalt-boat`
