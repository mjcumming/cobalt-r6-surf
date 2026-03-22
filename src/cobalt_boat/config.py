"""Runtime configuration for the Cobalt Boat platform."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables.

    Defaults enforce read-only and local-only behavior.
    """

    app_name: str = "cobalt-boat"
    environment: str = "production"
    api_host: str = "127.0.0.1"
    api_port: int = 8080

    can_interface: str = "can0"
    can_channel_bitrate: int = 250_000
    auto_configure_can_interface: bool = False
    decoder_backend: str = "canboat"
    canboat_command: str = "/usr/local/bin/cobalt-canboat-decoder"
    canboat_response_timeout_sec: float = 1.0
    decoder_required: bool = True
    allow_basic_decoder_insecure: bool = False

    data_dir: Path = Path("data")
    capture_dir: Path = Path("data/captures")
    sqlite_path: Path = Path("data/cobalt_boat.db")
    app_log_path: Path = Path("/var/log/cobalt-boat/cobalt-boat.log")

    read_only_mode: bool = True
    write_enable: bool = False
    emergency_disable: bool = False

    command_rate_limit_window_sec: int = 5
    command_rate_limit_max_attempts: int = 5

    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from environment variables."""

        return cls(
            app_name=os.getenv("COBALT_APP_NAME", cls.app_name),
            environment=os.getenv("COBALT_ENV", cls.environment),
            api_host=os.getenv("COBALT_API_HOST", cls.api_host),
            api_port=int(os.getenv("COBALT_API_PORT", str(cls.api_port))),
            can_interface=os.getenv("COBALT_CAN_INTERFACE", cls.can_interface),
            can_channel_bitrate=int(
                os.getenv("COBALT_CAN_BITRATE", str(cls.can_channel_bitrate))
            ),
            auto_configure_can_interface=_parse_bool(
                os.getenv("COBALT_AUTO_CONFIGURE_CAN_INTERFACE"),
                default=cls.auto_configure_can_interface,
            ),
            decoder_backend=os.getenv("COBALT_DECODER_BACKEND", cls.decoder_backend),
            canboat_command=os.getenv("COBALT_CANBOAT_COMMAND", cls.canboat_command),
            canboat_response_timeout_sec=float(
                os.getenv(
                    "COBALT_CANBOAT_RESPONSE_TIMEOUT_SEC",
                    str(cls.canboat_response_timeout_sec),
                )
            ),
            decoder_required=_parse_bool(
                os.getenv("COBALT_DECODER_REQUIRED"),
                default=cls.decoder_required,
            ),
            allow_basic_decoder_insecure=_parse_bool(
                os.getenv("COBALT_ALLOW_BASIC_DECODER_INSECURE"),
                default=cls.allow_basic_decoder_insecure,
            ),
            data_dir=Path(os.getenv("COBALT_DATA_DIR", str(cls.data_dir))),
            capture_dir=Path(os.getenv("COBALT_CAPTURE_DIR", str(cls.capture_dir))),
            sqlite_path=Path(os.getenv("COBALT_SQLITE_PATH", str(cls.sqlite_path))),
            app_log_path=Path(os.getenv("COBALT_APP_LOG_PATH", str(cls.app_log_path))),
            read_only_mode=_parse_bool(
                os.getenv("COBALT_READ_ONLY_MODE"), default=cls.read_only_mode
            ),
            write_enable=_parse_bool(
                os.getenv("COBALT_WRITE_ENABLE"), default=cls.write_enable
            ),
            emergency_disable=_parse_bool(
                os.getenv("COBALT_EMERGENCY_DISABLE"), default=cls.emergency_disable
            ),
            command_rate_limit_window_sec=int(
                os.getenv(
                    "COBALT_RATE_LIMIT_WINDOW_SEC",
                    str(cls.command_rate_limit_window_sec),
                )
            ),
            command_rate_limit_max_attempts=int(
                os.getenv(
                    "COBALT_RATE_LIMIT_MAX_ATTEMPTS",
                    str(cls.command_rate_limit_max_attempts),
                )
            ),
            log_level=os.getenv("COBALT_LOG_LEVEL", cls.log_level),
        )


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return default
