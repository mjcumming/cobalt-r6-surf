"""Central logging configuration."""

from __future__ import annotations

import logging
from logging.config import dictConfig
from pathlib import Path


def configure_logging(
    level: str = "INFO",
    file_path: Path | None = None,
    *,
    log_max_bytes: int = 5 * 1024 * 1024,
    log_backup_count: int = 7,
) -> None:
    """Initialize logging for the service.

    When ``file_path`` is set and ``log_max_bytes`` > 0, the file handler uses
    size-based rotation (``RotatingFileHandler``). Set ``log_max_bytes`` to 0
    to use a single growing file (e.g. if only ``logrotate`` should rotate).

    Production installs also ship ``/etc/logrotate.d/cobalt-boat`` (daily);
    in-process rotation caps burst logging before the next logrotate run.
    """

    handlers: dict[str, dict[str, object]] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": level,
        }
    }
    root_handlers = ["console"]
    if file_path is not None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if log_max_bytes > 0:
            handlers["file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "standard",
                "level": level,
                "filename": str(file_path),
                "maxBytes": log_max_bytes,
                "backupCount": log_backup_count,
            }
        else:
            handlers["file"] = {
                "class": "logging.FileHandler",
                "formatter": "standard",
                "level": level,
                "filename": str(file_path),
            }
        root_handlers.append("file")

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
                }
            },
            "handlers": handlers,
            "root": {"handlers": root_handlers, "level": level},
        }
    )
    logging.getLogger(__name__).info(
        "logging_configured level=%s file=%s max_bytes=%s backup_count=%s",
        level,
        file_path,
        log_max_bytes if file_path else None,
        log_backup_count if file_path and log_max_bytes > 0 else None,
    )
