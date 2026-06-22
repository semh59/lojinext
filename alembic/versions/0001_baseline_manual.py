"""0001 baseline manual

Revision ID: 0001_baseline_manual
Revises:
Create Date: 2026-03-15 14:15:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_baseline_manual"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _now():
    return sa.text("now()")


def _false():
    return sa.text("false")


def _zero():
    return sa.text("0")


def _float_zero():
    return sa.text("0.0")


def upgrade() -> None:
    op.create_table(
        "anomalies",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tarih", sa.Date(), nullable=False),
        sa.Column("tip", sa.String(length=50), nullable=False),
        sa.Column("kaynak_tip", sa.String(length=50), nullable=False),
        sa.Column("kaynak_id", sa.Integer(), nullable=False),
        sa.Column("deger", sa.Float(), nullable=False),
        sa.Column("beklenen_deger", sa.Float(), nullable=False),
        sa.Column("sapma_yuzde", sa.Float(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("aciklama", sa.Text(), nullable=False),
        sa.Column("rca_summary", sa.Text(), nullable=True),
        sa.Column("suggested_action", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )
    op.create_index("ix_anomalies_kaynak_id", "anomalies", ["kaynak_id"], unique=False)
    op.create_index("ix_anomalies_tarih", "anomalies", ["tarih"], unique=False)
    op.create_index("ix_anomalies_tip", "anomalies", ["tip"], unique=False)

    op.create_table(
        "araclar",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("plaka", sa.String(length=20), nullable=False),
        sa.Column("marka", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=50), nullable=True),
        sa.Column("yil", sa.Integer(), nullable=True),
        sa.Column(
            "tank_kapasitesi",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("600"),
        ),
        sa.Column(
            "hedef_tuketim", sa.Float(), nullable=False, server_default=sa.text("32.0")
        ),
        sa.Column("muayene_tarihi", sa.Date(), nullable=True),
        sa.Column(
            "bos_agirlik_kg",
            sa.Float(),
            nullable=False,
            server_default=sa.text("8000.0"),
        ),
        sa.Column(
            "hava_direnc_katsayisi",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.7"),
        ),
        sa.Column(
            "on_kesit_alani_m2",
            sa.Float(),
            nullable=False,
            server_default=sa.text("8.5"),
        ),
        sa.Column(
            "motor_verimliligi",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.38"),
        ),
        sa.Column(
            "lastik_direnc_katsayisi",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.007"),
        ),
        sa.Column(
            "maks_yuk_kapasitesi_kg",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("26000"),
        ),
        sa.Column("aktif", sa.Boolean(), nullable=False),
        sa.Column("notlar", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.CheckConstraint(
            "tank_kapasitesi > 0", name="check_tank_kapasitesi_positive"
        ),
    )
    op.create_index("idx_arac_aktif", "araclar", ["aktif"], unique=False)
    op.create_index("ix_araclar_plaka", "araclar", ["plaka"], unique=True)

    op.create_table(
        "bildirim_kurallari",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("olay_tipi", sa.String(length=50), nullable=False),
        sa.Column("kanallar", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("alici_rol_id", sa.Integer(), nullable=False),
        sa.Column("aktif", sa.Boolean(), nullable=False),
    )
    op.create_index(
        "ix_bildirim_kurallari_olay_tipi",
        "bildirim_kurallari",
        ["olay_tipi"],
        unique=False,
    )

    op.create_table(
        "dorseler",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("plaka", sa.String(length=20), nullable=False),
        sa.Column("marka", sa.String(length=50), nullable=True),
        sa.Column("tipi", sa.String(length=50), nullable=False),
        sa.Column("yil", sa.Integer(), nullable=True),
        sa.Column(
            "bos_agirlik_kg",
            sa.Float(),
            nullable=False,
            server_default=sa.text("6000.0"),
        ),
        sa.Column(
            "maks_yuk_kapasitesi_kg",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("24000"),
        ),
        sa.Column("lastik_sayisi", sa.Integer(), nullable=False),
        sa.Column("dorse_lastik_direnc_katsayisi", sa.Float(), nullable=False),
        sa.Column("dorse_hava_direnci", sa.Float(), nullable=False),
        sa.Column("muayene_tarihi", sa.Date(), nullable=True),
        sa.Column("notlar", sa.Text(), nullable=True),
        sa.Column("aktif", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )
    op.create_index("idx_dorse_aktif", "dorseler", ["aktif"], unique=False)
    op.create_index("ix_dorseler_plaka", "dorseler", ["plaka"], unique=True)

    op.create_table(
        "lokasyonlar",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("cikis_yeri", sa.String(length=100), nullable=False),
        sa.Column("varis_yeri", sa.String(length=100), nullable=False),
        sa.Column("mesafe_km", sa.Float(), nullable=False),
        sa.Column("tahmini_sure_saat", sa.Float(), nullable=True),
        sa.Column("zorluk", sa.String(length=20), nullable=False),
        sa.Column("cikis_lat", sa.Float(), nullable=True),
        sa.Column("cikis_lon", sa.Float(), nullable=True),
        sa.Column("varis_lat", sa.Float(), nullable=True),
        sa.Column("varis_lon", sa.Float(), nullable=True),
        sa.Column("api_mesafe_km", sa.Float(), nullable=True),
        sa.Column("api_sure_saat", sa.Float(), nullable=True),
        sa.Column("ascent_m", sa.Float(), nullable=True),
        sa.Column("descent_m", sa.Float(), nullable=True),
        sa.Column("flat_distance_km", sa.Float(), nullable=False),
        sa.Column("otoban_mesafe_km", sa.Float(), nullable=True),
        sa.Column("sehir_ici_mesafe_km", sa.Float(), nullable=True),
        sa.Column("tahmini_yakit_lt", sa.Float(), nullable=True),
        sa.Column("last_api_call", sa.DateTime(timezone=True), nullable=True),
        sa.Column("route_analysis", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("is_corrected", sa.Boolean(), nullable=False),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column("notlar", sa.Text(), nullable=True),
        sa.Column("aktif", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("cikis_yeri", "varis_yeri", name="uq_cikis_varis"),
    )

    op.create_table(
        "roller",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("ad", sa.String(length=50), nullable=False),
        sa.Column(
            "yetkiler",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "olusturma",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.UniqueConstraint("ad"),
    )

    op.create_table(
        "route_paths",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("origin_lat", sa.Float(), nullable=False),
        sa.Column("origin_lon", sa.Float(), nullable=False),
        sa.Column("dest_lat", sa.Float(), nullable=False),
        sa.Column("dest_lon", sa.Float(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("duration_min", sa.Float(), nullable=False),
        sa.Column("ascent_m", sa.Float(), nullable=False),
        sa.Column("descent_m", sa.Float(), nullable=False),
        sa.Column("flat_distance_km", sa.Float(), nullable=False),
        sa.Column("geometry", sa.JSON(), nullable=False),
        sa.Column("fuel_estimate_cache", sa.JSON(), nullable=True),
        sa.Column(
            "last_fetched",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.UniqueConstraint(
            "origin_lat", "origin_lon", "dest_lat", "dest_lon", name="uq_route_coords"
        ),
    )
    op.create_index(
        "ix_route_paths_dest_lat", "route_paths", ["dest_lat"], unique=False
    )
    op.create_index(
        "ix_route_paths_dest_lon", "route_paths", ["dest_lon"], unique=False
    )
    op.create_index(
        "ix_route_paths_origin_lat", "route_paths", ["origin_lat"], unique=False
    )
    op.create_index(
        "ix_route_paths_origin_lon", "route_paths", ["origin_lon"], unique=False
    )

    op.create_table(
        "soforler",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("ad_soyad", sa.String(length=100), nullable=False),
        sa.Column("telefon", sa.String(length=20), nullable=True),
        sa.Column("ise_baslama", sa.Date(), nullable=True),
        sa.Column("ehliyet_sinifi", sa.String(length=10), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("manual_score", sa.Float(), nullable=False),
        sa.Column("hiz_disiplin_skoru", sa.Float(), nullable=False),
        sa.Column("agresif_surus_faktoru", sa.Float(), nullable=False),
        sa.Column(
            "ramp_skoru", sa.Float(), nullable=False, server_default=sa.text("1.0")
        ),
        sa.Column(
            "istikrar_skoru", sa.Float(), nullable=False, server_default=sa.text("1.0")
        ),
        sa.Column("aktif", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=_false()),
        sa.Column("notlar", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.CheckConstraint(
            "score >= 0.1 AND score <= 2.0", name="chk_sofor_score_range"
        ),
        sa.CheckConstraint(
            "manual_score >= 0.1 AND manual_score <= 2.0",
            name="chk_sofor_manual_score_range",
        ),
    )
    op.create_index("idx_sofor_aktif", "soforler", ["aktif"], unique=False)
    op.create_index("idx_sofor_is_deleted", "soforler", ["is_deleted"], unique=False)
    op.create_index("ix_soforler_ad_soyad", "soforler", ["ad_soyad"], unique=True)

    op.create_table(
        "arac_bakimlari",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "arac_id",
            sa.Integer(),
            sa.ForeignKey("araclar.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "dorse_id",
            sa.Integer(),
            sa.ForeignKey("dorseler.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("bakim_tipi", sa.String(length=20), nullable=False),
        sa.Column("km_bilgisi", sa.Integer(), nullable=False),
        sa.Column(
            "bakim_tarihi",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column("maliyet", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("detaylar", sa.Text(), nullable=True),
        sa.Column("tamamlandi", sa.Boolean(), nullable=False),
        sa.Column(
            "guncelleme_tarihi",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )
    op.create_index(
        "ix_arac_bakimlari_arac_id", "arac_bakimlari", ["arac_id"], unique=False
    )
    op.create_index(
        "ix_arac_bakimlari_dorse_id", "arac_bakimlari", ["dorse_id"], unique=False
    )

    op.create_table(
        "guzergah_kalibrasyonlari",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "lokasyon_id",
            sa.Integer(),
            sa.ForeignKey("lokasyonlar.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("buffer_meters", sa.Float(), nullable=False),
        sa.Column("match_count", sa.Integer(), nullable=False),
        sa.Column("avg_deviation_dist", sa.Float(), nullable=False),
        sa.Column(
            "olusturma_tarihi",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )
    op.create_index(
        "ix_guzergah_kalibrasyonlari_lokasyon_id",
        "guzergah_kalibrasyonlari",
        ["lokasyon_id"],
        unique=False,
    )

    op.create_table(
        "kullanicilar",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("ad_soyad", sa.String(length=100), nullable=False),
        sa.Column("sifre_hash", sa.Text(), nullable=False),
        sa.Column("rol_id", sa.Integer(), sa.ForeignKey("roller.id"), nullable=False),
        sa.Column("aktif", sa.Boolean(), nullable=False),
        sa.Column("son_giris", sa.DateTime(timezone=True), nullable=True),
        sa.Column("son_giris_ip", postgresql.INET(), nullable=True),
        sa.Column("basarisiz_giris_sayisi", sa.Integer(), nullable=False),
        sa.Column("kilitli_kadar", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "sifre_degisim_tarihi",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column("sifre_sifir_token", sa.Text(), nullable=True),
        sa.Column("sifre_sifir_son", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "sofor_id",
            sa.Integer(),
            sa.ForeignKey("soforler.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column(
            "olusturan_id",
            sa.Integer(),
            sa.ForeignKey("kullanicilar.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_kullanicilar_email", "kullanicilar", ["email"], unique=True)
    op.create_index(
        "ix_kullanicilar_sofor_id", "kullanicilar", ["sofor_id"], unique=False
    )

    op.create_table(
        "sofor_adaptasyon",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "surucu_id",
            sa.Integer(),
            sa.ForeignKey("soforler.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("guvenlik_skoru", sa.Float(), nullable=False),
        sa.Column("verimlilik_skoru", sa.Float(), nullable=False),
        sa.Column("eco_driving_basarisi", sa.Float(), nullable=False),
        sa.Column("rutin_disi_davranis_orani", sa.Float(), nullable=False),
        sa.Column(
            "son_degerlendirme_tarihi", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("onerilen_modul", sa.String(length=100), nullable=True),
        sa.Column("risk_kategorisi", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_sofor_adaptasyon_surucu_id", "sofor_adaptasyon", ["surucu_id"], unique=True
    )

    op.create_table(
        "vehicle_event_log",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "arac_id",
            sa.Integer(),
            sa.ForeignKey("araclar.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("old_status", sa.String(length=50), nullable=True),
        sa.Column("new_status", sa.String(length=50), nullable=True),
        sa.Column("triggered_by", sa.String(length=100), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )
    op.create_index(
        "ix_vehicle_event_log_arac_id", "vehicle_event_log", ["arac_id"], unique=False
    )
    op.create_index(
        "ix_vehicle_event_log_event_type",
        "vehicle_event_log",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_vehicle_event_log_triggered_by",
        "vehicle_event_log",
        ["triggered_by"],
        unique=False,
    )

    op.create_table(
        "yakit_alimlari",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tarih", sa.Date(), nullable=False),
        sa.Column(
            "arac_id",
            sa.Integer(),
            sa.ForeignKey("araclar.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("istasyon", sa.String(length=100), nullable=True),
        sa.Column("fiyat_tl", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("litre", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("toplam_tutar", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("km_sayac", sa.Integer(), nullable=False),
        sa.Column("fis_no", sa.String(length=50), nullable=True),
        sa.Column("depo_durumu", sa.String(length=20), nullable=False),
        sa.Column("durum", sa.String(length=20), nullable=False),
        sa.Column("aktif", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column(
            "last_fetched",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.CheckConstraint("litre > 0", name="check_yakit_litre_positive"),
        sa.CheckConstraint("fiyat_tl > 0", name="check_yakit_fiyat_positive"),
    )
    op.create_index("idx_yakit_aktif", "yakit_alimlari", ["aktif"], unique=False)
    op.create_index(
        "idx_yakit_arac_tarih", "yakit_alimlari", ["arac_id", "tarih"], unique=False
    )
    op.create_index(
        "ix_yakit_alimlari_arac_id", "yakit_alimlari", ["arac_id"], unique=False
    )
    op.create_index(
        "ix_yakit_alimlari_tarih", "yakit_alimlari", ["tarih"], unique=False
    )

    op.create_table(
        "yakit_formul",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "arac_id",
            sa.Integer(),
            sa.ForeignKey("araclar.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("katsayilar", sa.JSON(), nullable=False),
        sa.Column("r2_score", sa.Float(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=_now()),
        sa.UniqueConstraint("arac_id"),
    )

    op.create_table(
        "yakit_periyotlari",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "arac_id",
            sa.Integer(),
            sa.ForeignKey("araclar.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("alim1_id", sa.Integer(), nullable=False),
        sa.Column("alim2_id", sa.Integer(), nullable=False),
        sa.Column("alim1_tarih", sa.Date(), nullable=True),
        sa.Column("alim1_km", sa.Integer(), nullable=True),
        sa.Column("alim1_litre", sa.Float(), nullable=True),
        sa.Column("alim2_tarih", sa.Date(), nullable=True),
        sa.Column("alim2_km", sa.Integer(), nullable=True),
        sa.Column("ara_mesafe", sa.Integer(), nullable=True),
        sa.Column("toplam_yakit", sa.Float(), nullable=True),
        sa.Column("ort_tuketim", sa.Float(), nullable=True),
        sa.Column("sefer_sayisi", sa.Integer(), nullable=False),
        sa.Column("durum", sa.String(length=50), nullable=True),
        sa.UniqueConstraint(
            "arac_id", "alim1_id", "alim2_id", name="uq_yakit_periyodu"
        ),
    )

    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column(
            "kullanici_id",
            sa.Integer(),
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kullanici_email", sa.String(length=255), nullable=True),
        sa.Column("aksiyon_tipi", sa.String(length=100), nullable=False),
        sa.Column("hedef_tablo", sa.String(length=100), nullable=True),
        sa.Column("hedef_id", sa.Text(), nullable=True),
        sa.Column("aciklama", sa.Text(), nullable=True),
        sa.Column("eski_deger", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("yeni_deger", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_adresi", postgresql.INET(), nullable=True),
        sa.Column("tarayici", sa.Text(), nullable=True),
        sa.Column("istek_id", sa.String(length=36), nullable=True),
        sa.Column("basarili", sa.Boolean(), nullable=False),
        sa.Column("hata_mesaji", sa.Text(), nullable=True),
        sa.Column("sure_ms", sa.Integer(), nullable=True),
        sa.Column(
            "zaman", sa.DateTime(timezone=True), nullable=False, server_default=_now()
        ),
    )

    op.create_table(
        "bildirim_gecmisi",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "kullanici_id",
            sa.Integer(),
            sa.ForeignKey("kullanicilar.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("baslik", sa.String(length=200), nullable=False),
        sa.Column("icerik", sa.Text(), nullable=False),
        sa.Column("olay_tipi", sa.String(length=50), nullable=True),
        sa.Column("kanal", sa.String(length=20), nullable=False),
        sa.Column("durum", sa.String(length=20), nullable=False),
        sa.Column("okundu_tarihi", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "olusturma_tarihi",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )
    op.create_index(
        "ix_bildirim_gecmisi_kullanici_id",
        "bildirim_gecmisi",
        ["kullanici_id"],
        unique=False,
    )
    op.create_index(
        "ix_bildirim_gecmisi_olay_tipi", "bildirim_gecmisi", ["olay_tipi"], unique=False
    )

    op.create_table(
        "egitim_kuyrugu",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column(
            "arac_id",
            sa.Integer(),
            sa.ForeignKey("araclar.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hedef_versiyon", sa.Integer(), nullable=False),
        sa.Column("durum", sa.String(length=20), nullable=False),
        sa.Column("ilerleme", sa.Float(), nullable=False),
        sa.Column("hata_detay", sa.Text(), nullable=True),
        sa.Column("yeniden_deneme_sayisi", sa.Integer(), nullable=False),
        sa.Column("baslangic_zaman", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bitis_zaman", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "olusturma",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column(
            "guncelleme",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column(
            "tetikleyen_kullanici_id",
            sa.Integer(),
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_egitim_kuyrugu_arac_id", "egitim_kuyrugu", ["arac_id"], unique=False
    )
    op.create_index(
        "ix_egitim_kuyrugu_durum", "egitim_kuyrugu", ["durum"], unique=False
    )

    op.create_table(
        "iceri_aktarim_gecmisi",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("dosya_adi", sa.String(length=255), nullable=False),
        sa.Column("aktarim_tipi", sa.String(length=50), nullable=False),
        sa.Column("durum", sa.String(length=50), nullable=False),
        sa.Column("toplam_kayit", sa.Integer(), nullable=False),
        sa.Column("basarili_kayit", sa.Integer(), nullable=False),
        sa.Column("hatali_kayit", sa.Integer(), nullable=False),
        sa.Column(
            "islem_haritasi", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("hatalar", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "yukleyen_id", sa.Integer(), sa.ForeignKey("kullanicilar.id"), nullable=True
        ),
        sa.Column(
            "baslama_zamani",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column("bitis_zamani", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "rollback_baglantilari",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_iceri_aktarim_gecmisi_aktarim_tipi",
        "iceri_aktarim_gecmisi",
        ["aktarim_tipi"],
        unique=False,
    )
    op.create_index(
        "ix_iceri_aktarim_gecmisi_durum",
        "iceri_aktarim_gecmisi",
        ["durum"],
        unique=False,
    )

    op.create_table(
        "konfig_gecmis",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("anahtar", sa.String(length=100), nullable=False),
        sa.Column(
            "eski_deger", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "yeni_deger", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("degisiklik_sebebi", sa.Text(), nullable=True),
        sa.Column(
            "guncelleyen_id",
            sa.Integer(),
            sa.ForeignKey("kullanicilar.id"),
            nullable=True,
        ),
        sa.Column(
            "zaman", sa.DateTime(timezone=True), nullable=False, server_default=_now()
        ),
    )
    op.create_index(
        "ix_konfig_gecmis_anahtar", "konfig_gecmis", ["anahtar"], unique=False
    )

    op.create_table(
        "kullanici_ayarlari",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "kullanici_id",
            sa.Integer(),
            sa.ForeignKey("kullanicilar.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("modul", sa.String(length=50), nullable=False),
        sa.Column("ayar_tipi", sa.String(length=50), nullable=False),
        sa.Column("deger", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("ad", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )
    op.create_index(
        "ix_kullanici_ayarlari_ayar_tipi",
        "kullanici_ayarlari",
        ["ayar_tipi"],
        unique=False,
    )
    op.create_index(
        "ix_kullanici_ayarlari_kullanici_id",
        "kullanici_ayarlari",
        ["kullanici_id"],
        unique=False,
    )
    op.create_index(
        "ix_kullanici_ayarlari_modul", "kullanici_ayarlari", ["modul"], unique=False
    )

    op.create_table(
        "kullanici_oturumlari",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column(
            "kullanici_id",
            sa.Integer(),
            sa.ForeignKey("kullanicilar.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_token_hash", sa.Text(), nullable=False),
        sa.Column("refresh_token_hash", sa.Text(), nullable=True),
        sa.Column("ip_adresi", postgresql.INET(), nullable=False),
        sa.Column("tarayici", sa.Text(), nullable=True),
        sa.Column(
            "olusturma",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column(
            "son_aktivite",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column("access_bitis", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_bitis", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aktif", sa.Boolean(), nullable=False),
        sa.Column("iptal_sebebi", sa.Text(), nullable=True),
    )

    op.create_table(
        "model_versiyonlar",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "arac_id",
            sa.Integer(),
            sa.ForeignKey("araclar.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("versiyon", sa.Integer(), nullable=False),
        sa.Column(
            "egitim_tarihi",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column("veri_sayisi", sa.Integer(), nullable=False),
        sa.Column("r2_skoru", sa.Float(), nullable=True),
        sa.Column("mae", sa.Float(), nullable=True),
        sa.Column("mape", sa.Float(), nullable=True),
        sa.Column("rmse", sa.Float(), nullable=True),
        sa.Column("model_dosya_yolu", sa.Text(), nullable=True),
        sa.Column("model_boyut_kb", sa.Integer(), nullable=True),
        sa.Column("egitim_suresi_sn", sa.Float(), nullable=True),
        sa.Column(
            "kullanilan_ozellikler",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("xgboost_agirligi", sa.Float(), nullable=True),
        sa.Column("lightgbm_agirligi", sa.Float(), nullable=True),
        sa.Column("rf_agirligi", sa.Float(), nullable=True),
        sa.Column("gb_agirligi", sa.Float(), nullable=True),
        sa.Column("fizik_agirligi", sa.Float(), nullable=True),
        sa.Column("aktif", sa.Boolean(), nullable=False),
        sa.Column("fizik_only_mod", sa.Boolean(), nullable=False),
        sa.Column("fizik_only_sebebi", sa.Text(), nullable=True),
        sa.Column("notlar", sa.Text(), nullable=True),
        sa.Column(
            "egiten_kullanici_id",
            sa.Integer(),
            sa.ForeignKey("kullanicilar.id"),
            nullable=True,
        ),
        sa.Column("tetikleyici", sa.String(length=50), nullable=False),
        sa.UniqueConstraint("arac_id", "versiyon", name="uq_arac_versiyon"),
    )
    op.create_index(
        "idx_model_arac_versiyon",
        "model_versiyonlar",
        ["arac_id", sa.text("versiyon DESC")],
        unique=False,
    )
    op.create_index(
        "ix_model_versiyonlar_arac_id", "model_versiyonlar", ["arac_id"], unique=False
    )

    op.create_table(
        "prediction_results",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )
    op.create_index(
        "ix_prediction_results_task_id", "prediction_results", ["task_id"], unique=True
    )
    op.create_index(
        "ix_prediction_results_user_id", "prediction_results", ["user_id"], unique=False
    )

    op.create_table(
        "seferler",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("sefer_no", sa.String(length=50), nullable=True),
        sa.Column("tarih", sa.Date(), nullable=False),
        sa.Column("saat", sa.String(length=5), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column(
            "guzergah_id",
            sa.Integer(),
            sa.ForeignKey("lokasyonlar.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "arac_id",
            sa.Integer(),
            sa.ForeignKey("araclar.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "dorse_id",
            sa.Integer(),
            sa.ForeignKey("dorseler.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "sofor_id",
            sa.Integer(),
            sa.ForeignKey("soforler.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("periyot_id", sa.Integer(), nullable=True),
        sa.Column(
            "bos_agirlik_kg", sa.Integer(), nullable=False, server_default=_zero()
        ),
        sa.Column(
            "dolu_agirlik_kg", sa.Integer(), nullable=False, server_default=_zero()
        ),
        sa.Column("net_kg", sa.Integer(), nullable=False, server_default=_zero()),
        sa.Column("ton", sa.Float(), nullable=False, server_default=_float_zero()),
        sa.Column("cikis_yeri", sa.String(length=100), nullable=False),
        sa.Column("varis_yeri", sa.String(length=100), nullable=False),
        sa.Column("mesafe_km", sa.Float(), nullable=False),
        sa.Column("baslangic_km", sa.Integer(), nullable=True),
        sa.Column("bitis_km", sa.Integer(), nullable=True),
        sa.Column("bos_sefer", sa.Boolean(), nullable=False, server_default=_false()),
        sa.Column(
            "durum",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'Tamam'"),
        ),
        sa.Column("notlar", sa.String(length=255), nullable=True),
        sa.Column("dagitilan_yakit", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("tahmini_tuketim", sa.Float(), nullable=True),
        sa.Column(
            "tahmin_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("rota_detay", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tuketim", sa.Float(), nullable=True),
        sa.Column("ascent_m", sa.Float(), nullable=True),
        sa.Column("descent_m", sa.Float(), nullable=True),
        sa.Column("flat_distance_km", sa.Float(), nullable=False),
        sa.Column("otoban_mesafe_km", sa.Float(), nullable=True),
        sa.Column("sehir_ici_mesafe_km", sa.Float(), nullable=True),
        sa.Column("is_real", sa.Boolean(), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=True),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_id",
            sa.Integer(),
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("iptal_nedeni", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.CheckConstraint("mesafe_km > 0", name="check_sefer_mesafe_positive"),
        sa.CheckConstraint(
            "net_kg = dolu_agirlik_kg - bos_agirlik_kg", name="check_sefer_net_kg_calc"
        ),
        sa.CheckConstraint(
            "bos_agirlik_kg >= 0", name="check_sefer_bos_agirlik_positive"
        ),
        sa.CheckConstraint(
            "dolu_agirlik_kg >= 0", name="check_sefer_dolu_agirlik_positive"
        ),
        sa.CheckConstraint("net_kg >= 0", name="check_sefer_net_kg_positive"),
        sa.CheckConstraint(
            "durum IN ('Bekliyor', 'Planlandı', 'Yolda', 'Devam Ediyor', 'Tamamlandı', 'Tamam', 'İptal')",
            name="check_sefer_durum_enum",
        ),
    )
    op.create_index(
        "idx_seferler_durum_tarih", "seferler", ["durum", "tarih"], unique=False
    )
    op.create_index(
        "idx_seferler_rota_detay_gin",
        "seferler",
        ["rota_detay"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "idx_seferler_tahmin_meta_gin",
        "seferler",
        ["tahmin_meta"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index("ix_seferler_arac_id", "seferler", ["arac_id"], unique=False)
    op.create_index(
        "ix_seferler_created_by_id", "seferler", ["created_by_id"], unique=False
    )
    op.create_index("ix_seferler_dorse_id", "seferler", ["dorse_id"], unique=False)
    op.create_index(
        "ix_seferler_guzergah_id", "seferler", ["guzergah_id"], unique=False
    )
    op.create_index("ix_seferler_is_deleted", "seferler", ["is_deleted"], unique=False)
    op.create_index("ix_seferler_periyot_id", "seferler", ["periyot_id"], unique=False)
    op.create_index("ix_seferler_sefer_no", "seferler", ["sefer_no"], unique=True)
    op.create_index("ix_seferler_sofor_id", "seferler", ["sofor_id"], unique=False)
    op.create_index("ix_seferler_tarih", "seferler", ["tarih"], unique=False)
    op.create_index(
        "ix_seferler_updated_by_id", "seferler", ["updated_by_id"], unique=False
    )

    op.create_table(
        "sistem_konfig",
        sa.Column("anahtar", sa.String(length=100), primary_key=True, nullable=False),
        sa.Column("deger", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tip", sa.String(length=20), nullable=False),
        sa.Column("birim", sa.String(length=20), nullable=True),
        sa.Column("min_deger", sa.Float(), nullable=True),
        sa.Column("max_deger", sa.Float(), nullable=True),
        sa.Column("grup", sa.String(length=50), nullable=False),
        sa.Column("aciklama", sa.Text(), nullable=True),
        sa.Column("yeniden_baslat", sa.Boolean(), nullable=False),
        sa.Column(
            "son_guncelleme",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
        sa.Column(
            "guncelleyen_id",
            sa.Integer(),
            sa.ForeignKey("kullanicilar.id"),
            nullable=True,
        ),
    )

    op.create_table(
        "seferler_log",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "sefer_id",
            sa.Integer(),
            sa.ForeignKey("seferler.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("degisen_alan", sa.String(length=50), nullable=True),
        sa.Column("eski_deger", sa.String(), nullable=True),
        sa.Column("yeni_deger", sa.String(), nullable=True),
        sa.Column("degistiren_id", sa.Integer(), nullable=True),
        sa.Column("islem_tipi", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_now(),
        ),
    )
    op.create_index(
        "ix_seferler_log_created_at", "seferler_log", ["created_at"], unique=False
    )
    op.create_index(
        "ix_seferler_log_sefer_id", "seferler_log", ["sefer_id"], unique=False
    )


def downgrade() -> None:
    raise NotImplementedError("Baseline migration cannot be reversed safely.")
