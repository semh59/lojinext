"""OcrProcessor.process() timeout tests.

2026-07-01 prod-grade denetimi P0 #5 bug: `reader.readtext` çağrısına hiçbir
üst sınır uygulanmıyordu — ağır bir görüntü thread-pool'u süresiz işgal edip
servisi DoS'a düşürebiliyordu. Bu dosya `_OCR_TIMEOUT_SECONDS` fix'ini
doğrular.

`easyocr` paketi bu test ortamında kurulu değil (ağır bağımlılık, ~1.5GB
model indirme) — modül seviyesindeki `import easyocr` satırının patlamaması
için gerçek paket `sys.modules`'e stub olarak enjekte edilir; testler
`OcrProcessor.reader`'ı kendi sahte (yavaş/hızlı) `readtext` fonksiyonuyla
değiştirir, gerçek OCR modeline hiç ihtiyaç duymaz.
"""

import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if "easyocr" not in sys.modules:
    _fake_easyocr = types.ModuleType("easyocr")
    _fake_easyocr.Reader = MagicMock()
    sys.modules["easyocr"] = _fake_easyocr

import ocr_processor  # noqa: E402
from ocr_processor import OcrProcessor  # noqa: E402

pytestmark = pytest.mark.asyncio


def _make_processor(readtext_fn):
    processor = OcrProcessor.__new__(OcrProcessor)
    processor.reader = MagicMock()
    processor.reader.readtext = readtext_fn
    return processor


async def test_process_raises_timeout_error_when_readtext_hangs(monkeypatch):
    """A readtext call slower than _OCR_TIMEOUT_SECONDS must raise
    TimeoutError instead of hanging the request indefinitely."""
    monkeypatch.setattr(ocr_processor, "_OCR_TIMEOUT_SECONDS", 0.2)

    def _slow_readtext(image_bytes):
        time.sleep(2)  # far longer than the 0.2s timeout
        return [((0, 0), "should never be reached", 0.9)]

    processor = _make_processor(_slow_readtext)

    with pytest.raises(TimeoutError, match="zaman aşımı"):
        await processor.process(b"fake-image-bytes", "yakit_fisi")


async def test_process_completes_normally_within_timeout(monkeypatch):
    """A fast readtext call must complete normally (no false-positive timeout)."""
    monkeypatch.setattr(ocr_processor, "_OCR_TIMEOUT_SECONDS", 5.0)

    def _fast_readtext(image_bytes):
        return [((0, 0), "OPET 45.50 TL", 0.95)]

    processor = _make_processor(_fast_readtext)

    result = await processor.process(b"fake-image-bytes", "yakit_fisi")
    assert result["ham_metin"] == "OPET 45.50 TL"
    assert result["yapilandirilmis"]["istasyon"] == "OPET"
