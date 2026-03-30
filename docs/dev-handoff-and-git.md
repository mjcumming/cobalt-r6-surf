# Development handoff, Git, and pausing work

This note captures **workflow and closure** items so picking up again (or operating the Pi) stays predictable.

## Repository and IDE

- **Clone root:** Work inside the repository directory (`cobalt-r6-surf`), not only a parent folder like the Linux home directory. **Cursor / VS Code** should open that folder (or a workspace whose `folders[].path` points at it) so **Git**, search, and tests align with `pyproject.toml` and `src/`.
- **Canonical remote:** `https://github.com/mjcumming/cobalt-r6-surf` (SSH: `git@github.com:mjcumming/cobalt-r6-surf.git`).

## Git workflow (this project)

- **Ship changes:** Commit on `main` (or a branch), then **`git push origin main`** so GitHub matches the machine you treat as source of truth.
- **Avoid surprise merges:** A useful repo-local setting is **`git config pull.ff only`** (fast-forward pulls only). If histories diverge, resolve deliberately (this boat project generally expects **this checkout to win** when pushing; use **`git push --force-with-lease`** only after **`git fetch`** and a conscious decision to overwrite the remote branch).
- **Install / runtime** is separate from Git: after **`git pull`**, reinstall or restart when templates change — see [`deployment.md`](deployment.md) (systemd env, port 80, capabilities).

## Documentation map (recent surface area)

| Topic | Location |
| --- | --- |
| Dashboard, ports, TLS, telemetry API | [`web-ui-and-http.md`](web-ui-and-http.md) |
| ADR for web/HTTP/telemetry decisions | [`adr/0004-web-ui-standard-http-telemetry.md`](adr/0004-web-ui-standard-http-telemetry.md) |
| Install, verify, recover | [`deployment.md`](deployment.md) |

## Pausing development (“close down” checklist)

Optional but helpful before leaving the Pi idle or switching to **production-only** testing:

1. **Push Git:** All commits intended to keep are on **`origin/main`** (`git status` clean locally if the Pi is not the only clone).
2. **Service:** `systemctl status cobalt-boat.service` — **active** if the boat should keep observing; **`systemctl stop`** if the CAN hat should be quiet.
3. **Backups worth keeping:** Under the repo, **`data/`** (SQLite catalog, captures) and **`/var/log/cobalt-boat/`** per your retention policy; copy off-device if you need post-mortems.
4. **Versions on record:** `cat /usr/local/share/cobalt/canboat-install.txt` (or re-run **`cobalt-canboat-decoder --self-check`**) so you know the analyzer stack that matched this tree.
5. **Runtime config:** `/etc/default/cobalt-boat` — confirm **`COBALT_API_HOST`** / **`COBALT_API_PORT`** (and optional TLS paths) match how you browse the boat LAN.

When you resume feature work, start from **`git pull`**, **`pip install -e '.[dev]'`**, **`pytest`**, then on-device **`install_systemd_service.sh`** only if unit or env templates changed.
