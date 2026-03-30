# ADR 0001: Production deployment, logging, and systemd layout

## Status

Accepted

## Context

The API runs on a Raspberry Pi on the vessel. We need a repeatable install, safe defaults (read-only observation), bounded disk use for text logs, and a clear failure mode when the CANboat toolchain is missing or the wrong version.

## Decision

1. **systemd** is the supported production supervisor: `cobalt-boat.service` plus `cobalt-boat-healthcheck.timer` for periodic health checks.
2. **Environment** is loaded from `/etc/default/cobalt-boat` (installed from `deploy/systemd/cobalt-boat.env`).
3. **Log directory** `/var/log/cobalt-boat` is created via **systemd tmpfiles** (`deploy/systemd/cobalt-boat.tmpfiles.conf`) with ownership matching the **service user and group** (not root), so the application can open log files while `User=` is unprivileged. `ReadWritePaths` in the unit includes this directory and the repo `data/` tree.
4. **Text logs** use both:
   - In-process **size rotation** (`RotatingFileHandler`) driven by `COBALT_LOG_MAX_BYTES` and `COBALT_LOG_BACKUP_COUNT`.
   - Host **logrotate** (daily, `copytruncate`) for `/var/log/cobalt-boat/*.log`.
5. **logrotate** `create` ownership is **rendered at install time** from `deploy/logrotate/cobalt-boat` (same user/group as the service) so post-rotate files remain writable by the app.
6. **ExecStartPre** runs `cobalt-canboat-decoder --self-check` so the unit fails fast if analyzer binaries are missing or the reported version does not match `COBALT_CANBOAT_EXPECTED_VERSION` (with `v`-prefix tolerance in the wrapper).
7. **stdout/stderr** are appended to the same log file as the Python file handler (operational convenience); primary diagnosis remains log file + `journalctl`.

## Consequences

- Installers must run `scripts/install_systemd_service.sh` (as root) after the venv and CANboat wrapper exist; a one-line `systemctl start` is still required if the operator wants the API up immediately.
- SQLite and optional capture JSONL remain the largest sustained write sources on SD cards; text log rotation alone does not cap database growth.
- Changing the runtime user requires re-running the installer (or manually aligning tmpfiles, logrotate, and unit `User=`).
