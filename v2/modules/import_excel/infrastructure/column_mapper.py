"""Excel sütun eşleştirme yardımcıları.

``SafeColumnMapper`` — DÜRÜST NOT (2026-07-15 dedektif denetimi): bu sınıf
``RouteSimulator``/``LokasyonHydrator``/``DriverPerformanceML`` ile "aynı
gerekçe" DEĞİL — hiç `__init__`'i yok, hiç instantiate edilmiyor (her çağrı
`SafeColumnMapper.map_columns(...)` classmethod'u), `COLS` class-level sabit
dict. Gerçek bir B.1 borcu: `map_columns` trivially bir free function'a,
`COLS` bir modül sabitine çevrilebilirdi. Taşımadan ÖNCE de (eski
`excel_column_map.py`'de) sınıftı, dalga 9 yalnız yerini değiştirdi —
free-function'a çevrilmesi ayrı bir refactor kapsamı (bkz.
`v2/modules/import_excel/CLAUDE.md`).
"""

import difflib
from typing import Dict, List


class SafeColumnMapper:
    """Fuzzy matching for Excel headers to internal keys"""

    COLS = {
        "tarih": [
            "tarih",
            "sefer tarihi",
            "alış tarihi",
            "tür",
            "gün",
            "date",
            "trip date",
            "fiş tarihi",
            "islem tarihi",
        ],
        "plaka": ["plaka", "plaka no", "araç plaka", "plate", "vehicle", "tasit plaka"],
        "litre": [
            "litre",
            "miktar",
            "yakıt miktarı",
            "liters",
            "amount",
            "volüm",
            "yakit miktari",
        ],
        "fiyat_tl": ["fiyat", "birim fiyat", "price", "unit price", "birim tutar"],
        "toplam_tutar": [
            "tutar",
            "toplam tutar",
            "toplam",
            "cost",
            "total cost",
            "amount paid",
            "brut tutar",
            "net tutar",
        ],
        "km_sayac": [
            "km",
            "km sayacı",
            "araç km",
            "odometer",
            "mileage",
            "km sayaci",
            "arac km",
        ],
        "mesafe_km": [
            "mesafe",
            "mesafe km",
            "yol",
            "distance",
            "total distance",
            "yol km",
        ],
        "toplam_km": ["toplam km", "toplam yol", "total km"],
        "istasyon": [
            "istasyon",
            "bayi",
            "servis alanı",
            "station",
            "provider",
            "tesis adi",
        ],
        "fis_no": [
            "fis no",
            "fiş no",
            "makbuz",
            "receipt",
            "inv no",
            "belge no",
            "evrak no",
        ],
        "depo_durumu": ["depo durumu", "depo", "tank status", "fullness"],
        "cikis_yeri": [
            "cikis yeri",
            "çıkış yeri",
            "başlangıç",
            "start",
            "origin",
            "from",
            "yukleme yeri",
        ],
        "varis_yeri": [
            "varis yeri",
            "varış yeri",
            "bitiş",
            "destination",
            "to",
            "bosaltma yeri",
        ],
        "sofor_adi": [
            "sofor adi",
            "şoför adı",
            "şoför",
            "driver",
            "operator",
            "surucu",
        ],
        "net_kg": [
            "yuk",
            "yük",
            "yük (kg)",
            "yuk (kg)",
            "net yük",
            "net yuk",
            "net_kg",
            "ağırlık",
            "agirlik",
            "weight",
            "load",
            "kg",
            "ton",
            "tonaj",
        ],
        "saat": ["saat", "zaman", "time"],
        "durum": ["durum", "status"],
        "marka": ["marka", "brand"],
        "model": ["model"],
        "yil": ["yil", "yıl", "model yılı", "year"],
        "tank_kapasitesi": ["tank kapasitesi", "depo hacmi", "tank capacity"],
        "bos_agirlik_kg": [
            "bos agirlik",
            "boş ağırlık",
            "bos_agirlik_kg",
            "bos agirlik kg",
            "tare",
        ],
        "maks_yuk_kapasitesi_kg": [
            "maks yuk",
            "maks yük",
            "max yuk",
            "maks yuk kapasitesi",
            "maks_yuk_kapasitesi_kg",
            "maks yuk kapasitesi kg",
            "max payload",
            "max load",
            "load capacity",
        ],
        "dingil_sayisi": [
            "dingil",
            "dingil sayisi",
            "dingil sayısı",
            "axle count",
            "axles",
        ],
        "hava_direnc_katsayisi": [
            "hava direnc",
            "hava direnç",
            "cx",
            "drag coefficient",
            "hava direnc katsayisi",
            "hava_direnc_katsayisi",
        ],
        "on_kesit_alani_m2": [
            "on kesit alani",
            "ön kesit alanı",
            "frontal area",
            "on_kesit_alani_m2",
            "on kesit alani m2",
        ],
        "lastik_direnc_katsayisi": [
            "lastik direnc",
            "lastik direnç",
            "rolling resistance",
            "lastik_direnc_katsayisi",
            "lastik direnc katsayisi",
        ],
        "hedef_tuketim": [
            "hedef tuketim",
            "hedef tüketim",
            "hedef_tuketim",
            "target consumption",
            "target fuel",
        ],
        "muayene_tarihi": [
            "muayene tarihi",
            "muayene",
            "muayene_tarihi",
            "inspection date",
        ],
        "telegram_id": [
            "telegram id",
            "telegram_id",
            "telegram chat",
            "tg id",
        ],
        "motor_verimliligi": [
            "motor verimliligi",
            "motor verimliliği",
            "engine efficiency",
        ],
        "telefon": ["telefon", "phone", "gsm"],
        "ise_baslama": ["ise baslama", "işe başlama", "baslangic", "hire date"],
        "ehliyet_sinifi": ["ehliyet sinifi", "ehliyet", "license"],
        "ad_soyad": [
            "ad soyad",
            "ad_soyad",
            "adı soyadı",
            "adi soyadi",
            "isim",
            "ad",
            "name",
            "full name",
            "şoför adı",
            "sofor adi",
        ],
        "yakit_tipi": [
            "yakit tipi",
            "yakıt tipi",
            "yakit_tipi",
            "yakit",
            "fuel type",
            "fuel",
        ],
        "cikis_lat": [
            "cikis lat",
            "çıkış lat",
            "cikis_lat",
            "start lat",
            "origin lat",
            "yukleme lat",
            "lat from",
        ],
        "cikis_lon": [
            "cikis lon",
            "çıkış lon",
            "cikis_lon",
            "start lon",
            "origin lon",
            "yukleme lon",
            "lon from",
            "cikis lng",
            "çıkış lng",
        ],
        "varis_lat": [
            "varis lat",
            "varış lat",
            "varis_lat",
            "end lat",
            "destination lat",
            "bosaltma lat",
            "lat to",
        ],
        "varis_lon": [
            "varis lon",
            "varış lon",
            "varis_lon",
            "end lon",
            "destination lon",
            "bosaltma lon",
            "lon to",
            "varis lng",
            "varış lng",
        ],
        "tahmini_sure_saat": [
            "tahmini sure",
            "tahmini süre",
            "tahmini süre (saat)",
            "estimated duration",
            "duration",
            "süre saat",
        ],
        "dorse_plakasi": ["dorse", "dorse plaka", "dorse plakası", "trailer"],
        "dorse_tipi": ["dorse tipi", "dorse türü", "trailer type"],
        "lastik_sayisi": ["lastik sayisi", "lastik sayısı", "tires"],
        # GPS rotası alanları (sefer Excel'i için)
        "ascent_m": [
            "ascent",
            "ascent_m",
            "ascent (m)",
            "tırmanış",
            "tırmanış (m)",
            "tirmanis",
            "tirmanis (m)",
            "yukselti m",
            "yükselti",
            "elevation gain",
        ],
        "descent_m": [
            "descent",
            "descent_m",
            "descent (m)",
            "iniş",
            "iniş (m)",
            "inis",
            "inis (m)",
            "alcalma m",
            "alçalma",
            "elevation loss",
        ],
        "flat_distance_km": [
            "flat distance",
            "flat_distance_km",
            "düz mesafe",
            "düz mesafe (km)",
            "duz mesafe",
            "duz mesafe (km)",
            "level km",
        ],
        "sefer_no": ["sefer no", "sefer_no", "trip no", "voyage", "fiş", "sefer id"],
        "notlar": ["notlar", "not", "aciklama", "açıklama", "notes", "comment"],
    }

    @classmethod
    def map_columns(cls, df_columns: List[str]) -> Dict[str, str]:
        """Excel başlıklarını internal key'lere eşle.

        İki geçişli:
          1) **Exact match önceliği** — bir Excel kolonu bir internal_key
             aliasıyla birebir eşleşmişse, başka bir internal_key onu fuzzy
             ile geri alamaz. (Bu olmadan "Plaka" → `dorse_plakasi`'na drift
             ediyordu: `plaka` substring `dorse plakası` içinde.)
          2) Sadece henüz claim edilmemiş kolonlar için fuzzy match.

        Fuzzy skor `min/max` ratio (Jaccard benzeri) — kısa-uzun substring'de
        skoru 1'in üstüne çıkarmaz.
        """
        mapping: Dict[str, str] = {}
        claimed: set = set()  # exact-match ile bağlanan Excel kolonları
        df_columns_clean = [str(c).strip().lower() for c in df_columns]

        # ── 1) Exact-match pass ──────────────────────────────────────────────
        for internal_key, aliases in cls.COLS.items():
            if internal_key in mapping.values():
                continue  # bu internal_key başka bir Excel kolonuna zaten bağlı
            for alias in aliases:
                if alias in df_columns_clean:
                    idx = df_columns_clean.index(alias)
                    excel_col = df_columns[idx]
                    if excel_col not in claimed:
                        mapping[excel_col] = internal_key
                        claimed.add(excel_col)
                    break

        # ── 2) Fuzzy pass — sadece exact'te claim edilmeyenler ──────────────
        for internal_key, aliases in cls.COLS.items():
            if internal_key in mapping.values():
                continue  # internal_key zaten bir kolona bağlı
            best_match = None
            highest_score = 0.0
            for col_idx, col in enumerate(df_columns_clean):
                excel_col = df_columns[col_idx]
                if excel_col in claimed:
                    continue
                for alias in aliases:
                    if alias in col or col in alias:
                        # Substring durumu — kısa olanın uzun olana oranı.
                        # Bu skor 1'i geçmez (eşit uzunlukta 0.8).
                        score = (
                            min(len(alias), len(col)) / max(len(alias), len(col)) * 0.8
                        )
                    else:
                        score = difflib.SequenceMatcher(None, col, alias).ratio()
                    if score > 0.75 and score > highest_score:
                        highest_score = score
                        best_match = excel_col
            if best_match:
                mapping[best_match] = internal_key
                claimed.add(best_match)

        return mapping
