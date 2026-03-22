from __future__ import annotations

from cobalt_boat.config import Settings


def test_default_decoder_command_uses_wrapper() -> None:
    settings = Settings()
    assert settings.canboat_command == "/usr/local/bin/cobalt-canboat-decoder"
    assert settings.decoder_required is True
