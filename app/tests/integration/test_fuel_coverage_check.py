"""monitoring.fuel_coverage_check beat task — gerçek-DB davranış testleri.

Kanıtlanan davranış (fuel-coverage ops alarmı epiği, 2026-07-07): son 7 gün
tamamlanmış seferlerde yakıt-tahmin coverage'ı runtime-config eşiğinin
(``FUEL_COVERAGE_ALERT_THRESHOLD_PCT``) altına düşerse Telegram ops kanalına
uyarı gider. Mock yok — gerçek DB satırları + gerçek sistem_konfig okuma
yolu; sadece Telegram HTTP çıkışı (``notify_error``) patch'lenir.
"""

from datetime import date

import pytest
from sqlalchemy import text

from app.core.services.fuel_coverage import compute_coverage
from app.workers.tasks.fuel_coverage_check import _run_fuel_coverage_check

pytestmark = pytest.mark.integration


async def _seed_vehicle_and_driver(db_session) -> tuple[int, int]:
    from app.infrastructure.security.pii_encryption import blind_index, encrypt_pii

    vehicle = await db_session.execute(
        text(
            "INSERT INTO araclar (plaka, marka, model, yil, aktif) "
            "VALUES ('34 FUEL 001', 'Test', 'Model', 2021, true) "
            "RETURNING id"
        )
    )
    vehicle_id = vehicle.scalar()

    driver = await db_session.execute(
        text(
            "INSERT INTO soforler (ad_soyad, ad_soyad_bidx, telefon, ise_baslama, "
            "ehliyet_sinifi, aktif, score, manual_score, hiz_disiplin_skoru, "
            "agresif_surus_faktoru) "
            "VALUES (:ad, :ad_bidx, :tel, '2020-01-01', 'E', true, 1.0, 1.0, 1.0, 1.0) "
            "RETURNING id"
        ),
        {
            "ad": encrypt_pii("Fuel Test"),
            "ad_bidx": blind_index("Fuel Test"),
            "tel": encrypt_pii("5559876543"),
        },
    )
    driver_id = driver.scalar()
    return vehicle_id, driver_id


async def _seed_completed_seferler(
    db_session,
    vehicle_id: int,
    driver_id: int,
    *,
    total: int,
    with_estimate: int,
) -> None:
    """`total` tamamlanmış sefer ekler; ilk `with_estimate` tanesinde
    tahmini_tuketim + mesafe_km > 0 dolu, geri kalanı NULL (tahminsiz)."""
    today = date.today()
    for i in range(total):
        has_estimate = i < with_estimate
        await db_session.execute(
            text(
                "INSERT INTO seferler "
                "(arac_id, sofor_id, tarih, cikis_yeri, varis_yeri, mesafe_km, "
                "durum, is_deleted, flat_distance_km, tuketim, tahmini_tuketim) "
                "VALUES (:a, :d, :tarih, 'Start', 'End', 450, 'Completed', false, "
                "450, 120.0, :tahmini)"
            ),
            {
                "a": vehicle_id,
                "d": driver_id,
                "tarih": today,
                "tahmini": 115.0 if has_estimate else None,
            },
        )
    await db_session.commit()


_THRESHOLD_KEY = "FUEL_COVERAGE_ALERT_THRESHOLD_PCT"


async def _set_threshold_row(db_session, value: str) -> None:
    from app.infrastructure.cache.redis_cache import get_redis_cache

    await db_session.execute(
        text(
            "INSERT INTO sistem_konfig (anahtar, deger, tip, grup, yeniden_baslat) "
            "VALUES (:k, CAST(:v AS jsonb), 'number', 'ml', FALSE) "
            "ON CONFLICT (anahtar) DO UPDATE SET deger = EXCLUDED.deger"
        ),
        {"k": _THRESHOLD_KEY, "v": value},
    )
    await db_session.commit()
    get_redis_cache().delete(f"config:val:{_THRESHOLD_KEY}")


@pytest.fixture(autouse=True)
async def _clean_threshold_config(db_session):
    """DB satırı testler arası her zaman temizlenir (conftest bunu yapar) ama
    KonfigService'in redis cache'i ayrı bir docker-run içinde bile TTL boyunca
    hayatta kalabiliyor (gerçek Redis, test-izole değil) — bir önceki test
    dosyası koşumundan kalma "90" değeri bu dosyayı BAĞIMSIZ koştuğunda bile
    sızıntı yapabiliyordu (kanıtlanmış davranış). Her testten önce/sonra
    cache'i açıkça sıfırla ki testler fallback (%50 default) ile başlasın."""
    from app.infrastructure.cache.redis_cache import get_redis_cache

    get_redis_cache().delete(f"config:val:{_THRESHOLD_KEY}")
    yield
    get_redis_cache().delete(f"config:val:{_THRESHOLD_KEY}")


class TestComputeCoverage:
    async def test_coverage_calculation_correct(self, db_session):
        """(a) 10 tamamlanmış sefer, 6'sında tahmin var -> coverage %60."""
        vehicle_id, driver_id = await _seed_vehicle_and_driver(db_session)
        await _seed_completed_seferler(
            db_session, vehicle_id, driver_id, total=10, with_estimate=6
        )

        result = await compute_coverage(db_session, days=7)

        assert result.total_completed == 10
        assert result.sample_size == 6
        assert result.coverage_pct == 60.0


class TestFuelCoverageCheckTask:
    async def test_below_threshold_triggers_notifier(self, db_session, monkeypatch):
        """(b) coverage eşiğin ALTINDA -> notify_error çağrılır (iş sonucu kanıtı)."""
        vehicle_id, driver_id = await _seed_vehicle_and_driver(db_session)
        # 10 tamamlanmış, sadece 2 tahminli -> %20 coverage < %50 default eşik.
        await _seed_completed_seferler(
            db_session, vehicle_id, driver_id, total=10, with_estimate=2
        )

        calls = []

        async def _fake_notify_error(*, level, message, path="", trace_id=""):
            calls.append({"level": level, "message": message, "path": path})

        monkeypatch.setattr(
            "v2.modules.notification.infrastructure.telegram_client.notify_error",
            _fake_notify_error,
        )

        await _run_fuel_coverage_check()

        assert len(calls) == 1
        assert calls[0]["path"] == "fuel_coverage_check"
        assert "20.0" in calls[0]["message"]
        assert "50.0" in calls[0]["message"]

    async def test_above_threshold_does_not_trigger_notifier(
        self, db_session, monkeypatch
    ):
        """(c) coverage eşiğin ÜSTÜNDE -> notifier çağrılmaz."""
        vehicle_id, driver_id = await _seed_vehicle_and_driver(db_session)
        # 10 tamamlanmış, 8 tahminli -> %80 coverage >= %50 default eşik.
        await _seed_completed_seferler(
            db_session, vehicle_id, driver_id, total=10, with_estimate=8
        )

        calls = []

        async def _fake_notify_error(*, level, message, path="", trace_id=""):
            calls.append(message)

        monkeypatch.setattr(
            "v2.modules.notification.infrastructure.telegram_client.notify_error",
            _fake_notify_error,
        )

        await _run_fuel_coverage_check()

        assert calls == []

    async def test_below_min_sample_does_not_trigger_notifier(
        self, db_session, monkeypatch
    ):
        """(d) total_completed < 5 -> az veri gürültüsü, alarm YOK."""
        vehicle_id, driver_id = await _seed_vehicle_and_driver(db_session)
        # 3 tamamlanmış, 0 tahminli -> %0 coverage ama örneklem < 5.
        await _seed_completed_seferler(
            db_session, vehicle_id, driver_id, total=3, with_estimate=0
        )

        calls = []

        async def _fake_notify_error(*, level, message, path="", trace_id=""):
            calls.append(message)

        monkeypatch.setattr(
            "v2.modules.notification.infrastructure.telegram_client.notify_error",
            _fake_notify_error,
        )

        await _run_fuel_coverage_check()

        assert calls == []

    async def test_threshold_read_from_db_row(self, db_session, monkeypatch):
        """(e) eşik sistem_konfig satırından okunur: satırı %90 yap -> normalde
        (%60 coverage, default %50 eşik) alarm tetiklenmezdi ama DB satırı %90
        olduğunda tetiklenir — davranış kanıtı, eşik gerçekten DB'den okunuyor.
        """
        vehicle_id, driver_id = await _seed_vehicle_and_driver(db_session)
        # 10 tamamlanmış, 6 tahminli -> %60 coverage (default %50 eşiğin ÜSTÜNDE).
        await _seed_completed_seferler(
            db_session, vehicle_id, driver_id, total=10, with_estimate=6
        )
        await _set_threshold_row(db_session, "90")

        calls = []

        async def _fake_notify_error(*, level, message, path="", trace_id=""):
            calls.append(message)

        monkeypatch.setattr(
            "v2.modules.notification.infrastructure.telegram_client.notify_error",
            _fake_notify_error,
        )

        await _run_fuel_coverage_check()

        assert len(calls) == 1
        assert "60.0" in calls[0]
        assert "90.0" in calls[0]
