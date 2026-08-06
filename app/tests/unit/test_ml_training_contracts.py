from v2.modules.analytics_executive.infrastructure.executive_read_models import (
    AnalizRepository,
)
from v2.modules.trip.infrastructure.repository import SeferRepository
from v2.modules.trip.sefer_status import SEFER_STATUS_TAMAMLANDI

LEGACY_REAL_FLAG = "is" + "_real"


async def test_sefer_repo_get_for_training_uses_fk_join_and_rich_route_columns():
    repo = SeferRepository()
    captured = {}

    async def fake_execute(query: str, params: dict):
        captured["query"] = query
        captured["params"] = params
        return []

    repo.execute_query = fake_execute

    await repo.get_for_training(17, limit=55)

    query = captured["query"]
    assert "LEFT JOIN lokasyonlar l ON s.guzergah_id = l.id" in query
    assert "LOWER(s.cikis_yeri)" not in query
    assert "s.tarih" in query
    assert "s.arac_id" in query
    assert "COALESCE(s.rota_detay, l.route_analysis)" in query
    assert "COALESCE(s.otoban_mesafe_km, l.otoban_mesafe_km, 0.0)" in query
    assert "COALESCE(s.sehir_ici_mesafe_km, l.sehir_ici_mesafe_km, 0.0)" in query
    assert captured["params"] == {
        "arac_id": 17,
        "limit": 55,
        "completed_status": SEFER_STATUS_TAMAMLANDI,
    }


async def test_sefer_repo_get_all_for_training_joins_araclar_for_tank_kapasitesi():
    """train_general_model's vehicle-class bucketing needs
    araclar.tank_kapasitesi on every row -- unlike get_for_training
    (single vehicle, arac_id already known), get_all_for_training spans
    all vehicles and must join araclar itself."""
    repo = SeferRepository()
    captured = {}

    async def fake_execute(query: str, params: dict):
        captured["query"] = query
        captured["params"] = params
        return []

    repo.execute_query = fake_execute

    await repo.get_all_for_training(limit=500)

    query = captured["query"]
    assert "LEFT JOIN lokasyonlar l ON s.guzergah_id = l.id" in query
    assert "LEFT JOIN araclar a ON s.arac_id = a.id" in query
    assert "a.tank_kapasitesi" in query
    assert "s.arac_id = :arac_id" not in query
    assert captured["params"] == {
        "limit": 500,
        "completed_status": SEFER_STATUS_TAMAMLANDI,
    }


async def test_analiz_repo_training_query_keeps_fk_join_without_synthetic_filters():
    """Covers AnalizRepository.get_training_seferler -- unrelated to the
    prediction_ml_service extraction (Task 5, 2026-08-04): ensemble_service
    now sources training data from trip's sefer_repo via cross_module_client,
    not this method. Left as-is; this method's own liveness is a separate,
    pre-existing question not introduced by that move."""
    repo = AnalizRepository()
    captured = {}

    async def fake_execute(query: str, params: dict):
        captured["query"] = query
        captured["params"] = params
        return []

    repo.execute_query = fake_execute

    await repo.get_training_seferler(9, limit=44)

    query = captured["query"]
    assert "LEFT JOIN lokasyonlar l ON s.guzergah_id = l.id" in query
    assert "LOWER(s.cikis_yeri)" not in query
    assert "AND s.is_deleted = False" in query
    assert LEGACY_REAL_FLAG not in query
    assert captured["params"] == {
        "arac_id": 9,
        "limit": 44,
        "offset": 0,
        "completed_status": SEFER_STATUS_TAMAMLANDI,
    }
