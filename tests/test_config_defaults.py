from __future__ import annotations

from cobalt_boat.config import Settings


def test_default_decoder_command_uses_wrapper() -> None:
    settings = Settings()
    assert settings.canboat_command == "/usr/local/bin/cobalt-canboat-decoder"
    assert settings.decoder_required is True


def test_default_log_rotation_bounds() -> None:
    settings = Settings()
    assert settings.log_max_bytes == 5 * 1024 * 1024
    assert settings.log_backup_count == 7


def test_log_rotation_from_env(monkeypatch) -> None:
    monkeypatch.setenv("COBALT_LOG_MAX_BYTES", "1024")
    monkeypatch.setenv("COBALT_LOG_BACKUP_COUNT", "3")
    monkeypatch.delenv("COBALT_LOG_LEVEL", raising=False)
    settings = Settings.from_env()
    assert settings.log_max_bytes == 1024
    assert settings.log_backup_count == 3


def test_log_level_from_env(monkeypatch) -> None:
    monkeypatch.setenv("COBALT_LOG_LEVEL", "WARNING")
    for key in (
        "COBALT_LOG_MAX_BYTES",
        "COBALT_LOG_BACKUP_COUNT",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = Settings.from_env()
    assert settings.log_level == "WARNING"
