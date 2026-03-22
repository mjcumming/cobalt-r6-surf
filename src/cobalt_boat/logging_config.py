"""Central logging configuration."""

from __future__ import annotations

import logging
from logging.config import dictConfig
from pathlib import Path


def configure_logging(level: str = "INFO", file_path: Path | None = None) -> None:
    """Initialize structured JSON-like logging format for service and audit traces."""

    handlers: dict[str, dict[str, str]] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": level,
        }
    }
    root_handlers = ["console"]
    if file_path is not None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
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
    logging.getLogger(__name__).info("logging_configured level=%s file=%s", level, file_path)
