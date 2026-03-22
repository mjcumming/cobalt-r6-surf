from __future__ import annotations

import pytest

from cobalt_boat.api.app import create_decoder
from cobalt_boat.config import Settings


def test_basic_decoder_rejected_without_insecure_flag() -> None:
    settings = Settings(decoder_backend="basic", allow_basic_decoder_insecure=False)

    with pytest.raises(ValueError, match="basic decoder is disabled"):
        create_decoder(settings)


def test_unsupported_decoder_backend_rejected() -> None:
    settings = Settings(decoder_backend="unknown")

    with pytest.raises(ValueError, match="unsupported decoder backend"):
        create_decoder(settings)
