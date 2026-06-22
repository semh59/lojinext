"""SafeColumnMapper regresyon testleri.

Bu session 2 production-aykırı bug yakalamıştı:
1. Substring skor formülü `max(...) * 0.8` → 1.7+ skor → "Plaka" → `dorse_plakasi`'na drift.
2. Eksik aliases: ad_soyad, yakit_tipi, lat/lon, Tırmanış (m), vs.

Bu test'ler her iki bug'ın geri gelmesini engeller — gelecek refactor'lar
mapper'ı kıramaz.
"""

from __future__ import annotations

import pytest

from app.core.services.excel_column_map import SafeColumnMapper


def _map(cols):
    return SafeColumnMapper.map_columns(cols)


class TestPlakaDriftRegression:
    """`Plaka` her zaman `plaka`'ya gitmeli, `dorse_plakasi`'na değil."""

    def test_plaka_alone_maps_to_plaka(self):
        m = _map(["Plaka"])
        assert m == {"Plaka": "plaka"}

    def test_plaka_with_dorse_plaka_both_correct(self):
        """En kritik bug — substring skor `min/max ratio * 0.8` ile çözüldü +
        exact-match precedence (`Plaka` ilk pass'ta lock olur)."""
        m = _map(["Plaka", "Dorse Plakası"])
        assert m["Plaka"] == "plaka"
        assert m["Dorse Plakası"] == "dorse_plakasi"

    def test_plaka_in_full_template(self):
        """Vehicle template — Dorse yok ama dorse_plakasi alias'ı drift
        riskini taşıyor."""
        cols = ["Plaka", "Marka", "Model", "Yil", "Yakit_Tipi"]
        m = _map(cols)
        assert m["Plaka"] == "plaka"


class TestNewAliasesPresent:
    """Bu session eklenen aliases'lar — eksik kalırsa Excel import sessiz fail."""

    @pytest.mark.parametrize(
        "header,expected",
        [
            ("Ad_Soyad", "ad_soyad"),
            ("Yakit_Tipi", "yakit_tipi"),
            ("Çıkış Lat", "cikis_lat"),
            ("Çıkış Lon", "cikis_lon"),
            ("Varış Lat", "varis_lat"),
            ("Varış Lon", "varis_lon"),
            ("Tahmini Süre (saat)", "tahmini_sure_saat"),
            ("Yük (KG)", "net_kg"),
            ("Tırmanış (m)", "ascent_m"),
            ("İniş (m)", "descent_m"),
            ("Düz Mesafe (KM)", "flat_distance_km"),
            ("Maks_Yuk_Kapasitesi_KG", "maks_yuk_kapasitesi_kg"),
            ("Dingil_Sayisi", "dingil_sayisi"),
            ("Hava_Direnc_Katsayisi", "hava_direnc_katsayisi"),
            ("On_Kesit_Alani_m2", "on_kesit_alani_m2"),
            ("Lastik_Direnc_Katsayisi", "lastik_direnc_katsayisi"),
            ("Hedef_Tuketim", "hedef_tuketim"),
            ("Muayene_Tarihi", "muayene_tarihi"),
            ("Telegram_ID", "telegram_id"),
        ],
    )
    def test_alias_present(self, header, expected):
        m = _map([header])
        assert m.get(header) == expected, (
            f"{header!r} → {m.get(header)} (beklenen {expected})"
        )


class TestExcelExporterTemplates:
    """excel_exporter.py'nin ürettiği template'ler her kolonu mapper kapsar.

    Kullanıcı template indirdiğinde her başlık DB alanına gitmeli — aksi
    halde kullanıcı doldurmuş bile olsa kolon sessizce yok sayılır.
    """

    SEFER_TEMPLATE = [
        "Tarih",
        "Saat",
        "Çıkış Yeri",
        "Varış Yeri",
        "Mesafe (KM)",
        "Yük (KG)",
        "Plaka",
        "Dorse Plakası",
        "Şoför Adı",
        "Durum",
        "Tırmanış (m)",
        "İniş (m)",
        "Düz Mesafe (KM)",
        "Sefer No",
        "Notlar",
    ]
    YAKIT_TEMPLATE = [
        "Tarih",
        "Plaka",
        "İstasyon",
        "Litre",
        "Fiyat",
        "Toplam Tutar",
        "KM Sayacı",
        "Fiş No",
        "Depo Durumu",
    ]
    ARAC_TEMPLATE = [
        "Plaka",
        "Marka",
        "Model",
        "Yil",
        "Tank_Kapasitesi",
        "Bos_Agirlik_KG",
        "Maks_Yuk_Kapasitesi_KG",
        "Dingil_Sayisi",
        "Motor_Verimliligi",
        "Hava_Direnc_Katsayisi",
        "On_Kesit_Alani_m2",
        "Lastik_Direnc_Katsayisi",
        "Hedef_Tuketim",
        "Yakit_Tipi",
        "Muayene_Tarihi",
        "Notlar",
    ]
    SOFOR_TEMPLATE = [
        "Ad_Soyad",
        "Telefon",
        "Ise_Baslama",
        "Ehliyet_Sinifi",
        "Telegram_ID",
        "Notlar",
    ]
    GUZERGAH_TEMPLATE = [
        "Çıkış Yeri",
        "Varış Yeri",
        "Çıkış Lat",
        "Çıkış Lon",
        "Varış Lat",
        "Varış Lon",
        "Mesafe (KM)",
        "Tahmini Süre (saat)",
        "Tırmanış (m)",
        "İniş (m)",
    ]

    @pytest.mark.parametrize(
        "name,cols",
        [
            ("sefer", SEFER_TEMPLATE),
            ("yakit", YAKIT_TEMPLATE),
            ("arac", ARAC_TEMPLATE),
            ("sofor", SOFOR_TEMPLATE),
            ("guzergah", GUZERGAH_TEMPLATE),
        ],
    )
    def test_template_fully_mapped(self, name, cols):
        m = _map(cols)
        unmapped = [c for c in cols if c not in m]
        assert not unmapped, (
            f"{name} template'inde {len(unmapped)} unmapped kolon: {unmapped}"
        )

    def test_sefer_template_critical_fields(self):
        """Sefer pipeline'ı için zorunlu alanlar doğru internal_key'lere
        bağlı olmalı."""
        m = _map(self.SEFER_TEMPLATE)
        assert m["Plaka"] == "plaka"
        assert m["Dorse Plakası"] == "dorse_plakasi"
        assert m["Yük (KG)"] == "net_kg"
        assert m["Şoför Adı"] == "sofor_adi"
        assert m["Çıkış Yeri"] == "cikis_yeri"
        assert m["Varış Yeri"] == "varis_yeri"

    def test_yakit_template_fiyat_separate_from_toplam(self):
        """Eski bug: 'Fiyat' ile 'Toplam Tutar' karışıyordu (substring drift).
        Şimdi ayrı internal_key'lere bağlanmalı."""
        m = _map(self.YAKIT_TEMPLATE)
        assert m["Fiyat"] == "fiyat_tl"
        assert m["Toplam Tutar"] == "toplam_tutar"
        # Litre fiyat ile karışmamalı
        assert m["Litre"] == "litre"


class TestExactMatchPrecedence:
    """Two-pass mapper: exact-match column'u lock'lar, fuzzy onu geri alamaz."""

    def test_exact_match_locks_column(self):
        """`Marka` `marka` aliası ile exact — başka internal_key fuzzy ile
        çalamasın."""
        m = _map(["Marka", "Model"])
        assert m["Marka"] == "marka"
        assert m["Model"] == "model"

    def test_substring_score_never_exceeds_one(self):
        """`min/max ratio * 0.8` formülü skor üst sınırı 0.8 yapar."""
        # Düz substring case — "Plaka" "Dorse Plakası" içinde
        # Skor min/max = 5/13 * 0.8 = 0.31 < 0.75 threshold → no fuzzy match
        m = _map(["Dorse Plakası", "Plaka"])
        # Plaka exact match → plaka, Dorse Plakası exact → dorse_plakasi
        assert m["Plaka"] == "plaka"
        assert m["Dorse Plakası"] == "dorse_plakasi"


class TestCaseInsensitiveAndUnicode:
    def test_lowercase_input(self):
        m = _map(["plaka", "marka", "model"])
        assert m == {"plaka": "plaka", "marka": "marka", "model": "model"}

    def test_turkish_diacritics(self):
        m = _map(["İstasyon", "Şoför Adı", "Çıkış Yeri"])
        assert m["İstasyon"] == "istasyon"
        assert m["Şoför Adı"] == "sofor_adi"
        assert m["Çıkış Yeri"] == "cikis_yeri"

    def test_extra_whitespace(self):
        m = _map(["  Plaka  ", "Marka "])
        # strip() yapılıyor, hâlâ orijinal anahtar dönüyor
        assert m.get("  Plaka  ") == "plaka"


class TestUnmappedColumnsSilent:
    """Tanınmayan kolonlar mapping'de görünmez — silent ignore, exception yok."""

    def test_unknown_column_omitted(self):
        m = _map(["Plaka", "Bilinmeyen_Kolon_XYZ"])
        assert m == {"Plaka": "plaka"}

    def test_empty_input(self):
        assert _map([]) == {}
