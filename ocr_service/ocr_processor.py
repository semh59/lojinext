import asyncio
import re
from typing import Optional

import easyocr


class OcrProcessor:
    def __init__(self) -> None:
        # Model ilk yüklemede ~1.5GB indirilir, sonraki başlatmalarda cache'den gelir
        self.reader = easyocr.Reader(["tr", "en"], gpu=False)

    async def process(self, image_bytes: bytes, belge_tipi: str) -> dict:
        results = await asyncio.to_thread(self.reader.readtext, image_bytes)
        ham_metin = " ".join([r[1] for r in results])

        if belge_tipi == "yakit_fisi":
            yapilandirilmis = self._parse_yakit_fisi(ham_metin)
        elif belge_tipi == "sefer_fisi":
            yapilandirilmis = self._parse_sefer_fisi(ham_metin)
        else:
            yapilandirilmis = {}

        return {"ham_metin": ham_metin, "yapilandirilmis": yapilandirilmis}

    def _parse_yakit_fisi(self, metin: str) -> dict:
        litre_m = re.search(r"(\d+[.,]\d{2,3})\s*[Ll][Tt]?(?:re|re\.)?", metin)
        tutar_m = re.search(r"(\d+[.,]\d{2})\s*(?:TL|₺)", metin, re.IGNORECASE)
        km_m = re.search(r"(\d{4,7})\s*[Kk][Mm]", metin)
        tarih_m = re.search(r"(\d{2}[./]\d{2}[./]\d{4})", metin)
        istasyon_m = re.search(
            r"(OPET|SHELL|BP|PETROL OFISI|TOTAL|AYTEMIZ|TP|PO)\b",
            metin,
            re.IGNORECASE,
        )

        return {
            "litre": _to_float(litre_m),
            "tutar": _to_float(tutar_m),
            "km": int(km_m.group(1)) if km_m else None,
            "tarih": tarih_m.group(1) if tarih_m else None,
            "istasyon": istasyon_m.group(1).upper() if istasyon_m else None,
        }

    def _parse_sefer_fisi(self, metin: str) -> dict:
        tarih_m = re.search(r"(\d{2}[./]\d{2}[./]\d{4})", metin)
        plaka_m = re.search(r"\b(\d{2}\s?[A-Z]{1,3}\s?\d{2,4})\b", metin)
        km_m = re.search(r"(\d{4,7})\s*[Kk][Mm]", metin)

        return {
            "tarih": tarih_m.group(1) if tarih_m else None,
            "plaka": plaka_m.group(1).replace(" ", "") if plaka_m else None,
            "km": int(km_m.group(1)) if km_m else None,
        }


def _to_float(match: Optional[re.Match]) -> Optional[float]:
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None
