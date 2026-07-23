"""Magic-byte image validation for the /internal/sefer-belge upload (ARCH-020)."""

from __future__ import annotations

import pytest

from v2.modules.admin_platform.api.internal_routes import _looks_like_allowed_image

pytestmark = pytest.mark.unit

_PAD = b"\x00" * 16


def test_accepts_jpeg_signature():
    assert _looks_like_allowed_image(b"\xff\xd8\xff\xe0" + _PAD)


def test_accepts_png_signature():
    assert _looks_like_allowed_image(b"\x89PNG\r\n\x1a\n" + _PAD)


def test_accepts_webp_signature():
    assert _looks_like_allowed_image(b"RIFF\x00\x00\x00\x00WEBP" + _PAD)


@pytest.mark.parametrize(
    "data",
    [
        b"",  # empty
        b"\xff\xd8",  # truncated JPEG, below min length
        b"%PDF-1.7\n" + _PAD,  # PDF masquerading as an image
        b"<html><script>alert(1)</script>" + _PAD,  # HTML/XSS payload
        b"RIFF\x00\x00\x00\x00AVI " + _PAD,  # RIFF but not WEBP
        b"GIF89a" + _PAD,  # GIF is not in the allow-list
    ],
)
def test_rejects_non_allowed_content(data):
    assert not _looks_like_allowed_image(data)
