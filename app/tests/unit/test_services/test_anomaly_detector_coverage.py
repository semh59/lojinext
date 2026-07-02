"""
Tests for app/core/services/anomaly_detector.py

Coverage target: ≥75%
Covers: AnomalyResult, AnomalyDetector (all methods), SeverityEnum, AnomalyType,
        detect_consumption_anomalies, detect_trip_anomaly_elite,
        detect_anomaly_hybrid, _calculate_severity, _generate_heuristic_rca,
        save_anomalies, get_recent_anomalies, acknowledge, resolve,
        predict_severity_lgb, get_detector_status, save_model, load_model.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import insert, select

from app.core.services.anomaly_detector import (
    AnomalyDetector,
    AnomalyResult,
    AnomalyType,
    SeverityEnum,
)
from app.database.models import Anomaly, Kullanici, Rol
from app.infrastructure.security.pii_encryption import blind_index

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Real-DB seed helpers (the save/get/ack/resolve methods run a real UnitOfWork
# against the conftest-monkeypatched test session).
# ---------------------------------------------------------------------------


async def _seed_anomaly(
    db_session,
    *,
    tip: str = "tuketim",
    kaynak_tip: str = "arac",
    kaynak_id: int = 1,
    severity: str = "high",
    tarih: date | None = None,
    acknowledged_at: datetime | None = None,
    acknowledged_by: int | None = None,
    resolved_at: datetime | None = None,
) -> int:
    aid = (
        await db_session.execute(
            insert(Anomaly).values(
                tarih=tarih or date.today(),
                tip=tip,
                kaynak_tip=kaynak_tip,
                kaynak_id=kaynak_id,
                deger=30.0,
                beklenen_deger=20.0,
                sapma_yuzde=50.0,
                severity=severity,
                aciklama="test",
                acknowledged_at=acknowledged_at,
                acknowledged_by=acknowledged_by,
                resolved_at=resolved_at,
            )
        )
    ).inserted_primary_key[0]
    await db_session.commit()
    return aid


async def _seed_user(db_session, email: str = "anom-op@lojinext.test") -> int:
    rid = (
        await db_session.execute(insert(Rol).values(ad="anom_op", yetkiler={}))
    ).inserted_primary_key[0]
    uid = (
        await db_session.execute(
            insert(Kullanici).values(
                email=email,
                email_bidx=blind_index(email),
                sifre_hash="x",
                ad_soyad="Anom Op",
                rol_id=rid,
                aktif=True,
            )
        )
    ).inserted_primary_key[0]
    await db_session.commit()
    return uid


async def _get_anomaly(db_session, aid: int) -> Anomaly:
    row = (
        await db_session.execute(select(Anomaly).where(Anomaly.id == aid))
    ).scalar_one()
    await db_session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_detector() -> AnomalyDetector:
    """Return a fresh AnomalyDetector with no external dependencies wired."""
    return AnomalyDetector()


def make_anomaly_result(
    *,
    tip: AnomalyType = AnomalyType.TUKETIM,
    kaynak_tip: str = "arac",
    kaynak_id: int = 1,
    deger: float = 30.0,
    beklenen_deger: float = 20.0,
    sapma_yuzde: float = 50.0,
    severity: SeverityEnum = SeverityEnum.HIGH,
    aciklama: str = "test",
    tarih: date = None,
) -> AnomalyResult:
    return AnomalyResult(
        tip=tip,
        kaynak_tip=kaynak_tip,
        kaynak_id=kaynak_id,
        deger=deger,
        beklenen_deger=beklenen_deger,
        sapma_yuzde=sapma_yuzde,
        severity=severity,
        aciklama=aciklama,
        tarih=tarih,
    )


# ---------------------------------------------------------------------------
# SeverityEnum / AnomalyType basic smoke
# ---------------------------------------------------------------------------


class TestEnums:
    def test_severity_values(self):
        assert SeverityEnum.LOW.value == "low"
        assert SeverityEnum.MEDIUM.value == "medium"
        assert SeverityEnum.HIGH.value == "high"
        assert SeverityEnum.CRITICAL.value == "critical"

    def test_anomaly_type_values(self):
        assert AnomalyType.TUKETIM.value == "tuketim"
        assert AnomalyType.MALIYET.value == "maliyet"
        assert AnomalyType.SEFER.value == "sefer"


# ---------------------------------------------------------------------------
# AnomalyResult dataclass
# ---------------------------------------------------------------------------


class TestAnomalyResult:
    def test_default_tarih_is_today(self):
        ar = AnomalyResult(
            tip=AnomalyType.TUKETIM,
            kaynak_tip="arac",
            kaynak_id=1,
            deger=10.0,
            beklenen_deger=8.0,
            sapma_yuzde=25.0,
            severity=SeverityEnum.MEDIUM,
            aciklama="test",
        )
        assert ar.tarih == date.today()

    def test_explicit_tarih_kept(self):
        d = date(2024, 1, 15)
        ar = AnomalyResult(
            tip=AnomalyType.SEFER,
            kaynak_tip="sefer",
            kaynak_id=5,
            deger=10.0,
            beklenen_deger=8.0,
            sapma_yuzde=25.0,
            severity=SeverityEnum.LOW,
            aciklama="x",
            tarih=d,
        )
        assert ar.tarih == d

    def test_default_rca_and_action(self):
        ar = AnomalyResult(
            tip=AnomalyType.MALIYET,
            kaynak_tip="sefer",
            kaynak_id=2,
            deger=5.0,
            beklenen_deger=4.0,
            sapma_yuzde=25.0,
            severity=SeverityEnum.MEDIUM,
            aciklama="cost anomaly",
        )
        assert ar.rca_summary == "Analiz ediliyor..."
        assert ar.suggested_action == "İncelenmeli"


# ---------------------------------------------------------------------------
# AnomalyDetector._calculate_severity
# ---------------------------------------------------------------------------


class TestCalculateSeverity:
    def setup_method(self):
        self.d = make_detector()

    def test_low_below_15(self):
        assert self.d._calculate_severity(10.0) == SeverityEnum.LOW

    def test_medium_at_15(self):
        assert self.d._calculate_severity(15.0) == SeverityEnum.MEDIUM

    def test_medium_between_15_and_30(self):
        assert self.d._calculate_severity(20.0) == SeverityEnum.MEDIUM

    def test_high_at_30(self):
        assert self.d._calculate_severity(30.0) == SeverityEnum.HIGH

    def test_high_between_30_and_50(self):
        assert self.d._calculate_severity(40.0) == SeverityEnum.HIGH

    def test_critical_at_50(self):
        assert self.d._calculate_severity(50.0) == SeverityEnum.CRITICAL

    def test_critical_above_50(self):
        assert self.d._calculate_severity(99.0) == SeverityEnum.CRITICAL


# ---------------------------------------------------------------------------
# AnomalyDetector._generate_heuristic_rca
# ---------------------------------------------------------------------------


class TestGenerateHeuristicRca:
    def setup_method(self):
        self.d = make_detector()

    def _make(self, tip: AnomalyType, sapma: float) -> AnomalyResult:
        return AnomalyResult(
            tip=tip,
            kaynak_tip="arac",
            kaynak_id=1,
            deger=10.0,
            beklenen_deger=8.0,
            sapma_yuzde=sapma,
            severity=SeverityEnum.HIGH,
            aciklama="x",
        )

    def test_consumption_theft_above_50(self):
        rca, action = self.d._generate_heuristic_rca(
            self._make(AnomalyType.TUKETIM, 60.0)
        )
        assert "Hırsızlığı" in rca or "Sensör" in rca

    def test_consumption_aggressive_driving_above_25(self):
        rca, action = self.d._generate_heuristic_rca(
            self._make(AnomalyType.TUKETIM, 30.0)
        )
        assert "Agresif" in rca or "Rota" in rca

    def test_consumption_heavy_load_above_15(self):
        rca, action = self.d._generate_heuristic_rca(
            self._make(AnomalyType.TUKETIM, 18.0)
        )
        assert "Yük" in rca or "Hava" in rca

    def test_consumption_calibration_negative(self):
        rca, action = self.d._generate_heuristic_rca(
            self._make(AnomalyType.TUKETIM, -25.0)
        )
        assert "Kalibrasyon" in rca or "Bilinmeyen" in rca

    def test_sefer_type_same_branches(self):
        rca, action = self.d._generate_heuristic_rca(
            self._make(AnomalyType.SEFER, 55.0)
        )
        assert isinstance(rca, str)

    def test_maliyet_type_returns_unknown(self):
        rca, action = self.d._generate_heuristic_rca(
            self._make(AnomalyType.MALIYET, 30.0)
        )
        assert rca == "Bilinmeyen Neden"


# ---------------------------------------------------------------------------
# detect_consumption_anomalies
# ---------------------------------------------------------------------------


class TestDetectConsumptionAnomalies:
    def setup_method(self):
        self.d = make_detector()

    async def test_too_few_values_returns_empty(self):
        result = await self.d.detect_consumption_anomalies([10.0, 11.0, 12.0])
        assert result == []

    async def test_exactly_five_no_outlier(self):
        result = await self.d.detect_consumption_anomalies(
            [10.0, 10.5, 11.0, 10.8, 10.2]
        )
        assert isinstance(result, list)

    async def test_clear_outlier_detected(self):
        # 100.0 is a clear outlier; with 10+ values should fire z + IQR
        data = [10.0] * 12 + [100.0]
        result = await self.d.detect_consumption_anomalies(data)
        assert len(result) >= 1
        assert result[0].tip == AnomalyType.TUKETIM

    async def test_arac_id_used_as_kaynak_id(self):
        data = [10.0] * 12 + [100.0]
        result = await self.d.detect_consumption_anomalies(data, arac_id=42)
        assert all(r.kaynak_id == 42 for r in result)
        assert all(r.kaynak_tip == "arac" for r in result)

    async def test_no_arac_id_uses_index(self):
        data = [10.0] * 12 + [100.0]
        result = await self.d.detect_consumption_anomalies(data)
        # kaynak_tip should be 'sefer' when arac_id is None
        assert all(r.kaynak_tip == "sefer" for r in result)

    async def test_zero_std_no_crash(self):
        # All identical → std=0, no anomalies
        data = [10.0] * 8
        result = await self.d.detect_consumption_anomalies(data)
        assert result == []

    async def test_anomaly_result_fields_populated(self):
        data = [10.0] * 12 + [200.0]
        result = await self.d.detect_consumption_anomalies(data, arac_id=7)
        assert len(result) >= 1
        r = result[0]
        assert r.deger > 0
        assert r.beklenen_deger > 0
        assert r.severity in list(SeverityEnum)
        assert "%" in r.aciklama or "sapma" in r.aciklama.lower()


# ---------------------------------------------------------------------------
# detect_trip_anomaly_elite
# ---------------------------------------------------------------------------


class TestDetectTripAnomalyUnit:
    def setup_method(self):
        self.d = make_detector()

    async def test_no_consumption_returns_none(self):
        result = await self.d.detect_trip_anomaly_elite(
            {"arac_id": 1, "mesafe_km": 500}
        )
        assert result is None

    async def test_anomaly_above_20pct(self):
        mock_pred = AsyncMock(
            return_value={
                "tahmini_tuketim": 25.0,
                "model_used": "ensemble",
            }
        )
        with patch(
            "app.core.services.anomaly_detector.get_prediction_service"
        ) as mock_svc:
            instance = MagicMock()
            instance.predict_consumption = mock_pred
            mock_svc.return_value = instance

            # consumption 35 vs expected 25 → (35-25)/25*100 = 40%
            result = await self.d.detect_trip_anomaly_elite(
                {
                    "id": 99,
                    "arac_id": 1,
                    "mesafe_km": 500,
                    "tuketim": 35.0,
                    "tarih": date(2024, 1, 1),
                }
            )

        assert result is not None
        assert result.tip == AnomalyType.SEFER
        assert result.kaynak_id == 99
        assert result.sapma_yuzde == pytest.approx(40.0, abs=0.2)
        assert result.tarih == date(2024, 1, 1)

    async def test_within_20pct_returns_none(self):
        mock_pred = AsyncMock(
            return_value={
                "tahmini_tuketim": 30.0,
                "model_used": "physics",
            }
        )
        with patch(
            "app.core.services.anomaly_detector.get_prediction_service"
        ) as mock_svc:
            instance = MagicMock()
            instance.predict_consumption = mock_pred
            mock_svc.return_value = instance

            result = await self.d.detect_trip_anomaly_elite(
                {"id": 1, "arac_id": 1, "mesafe_km": 200, "tuketim": 31.0}
            )

        assert result is None


# ---------------------------------------------------------------------------
# detect_anomaly_hybrid
# ---------------------------------------------------------------------------


class TestDetectAnomalyHybrid:
    def setup_method(self):
        self.d = make_detector()

    async def test_no_consumption_returns_none(self):
        result = await self.d.detect_anomaly_hybrid({"arac_id": 1, "mesafe_km": 100})
        assert result is None

    async def test_within_threshold_returns_none(self):
        mock_pred = AsyncMock(
            return_value={"tahmini_tuketim": 30.0, "model_used": "physics"}
        )
        with patch(
            "app.core.services.anomaly_detector.get_prediction_service"
        ) as mock_svc:
            instance = MagicMock()
            instance.predict_consumption = mock_pred
            mock_svc.return_value = instance

            result = await self.d.detect_anomaly_hybrid(
                {"arac_id": 1, "mesafe_km": 200, "tuketim": 31.0}
            )
        assert result is None

    async def test_above_threshold_rule_based_severity(self):
        mock_pred = AsyncMock(
            return_value={"tahmini_tuketim": 20.0, "model_used": "ensemble"}
        )
        with patch(
            "app.core.services.anomaly_detector.get_prediction_service"
        ) as mock_svc:
            instance = MagicMock()
            instance.predict_consumption = mock_pred
            mock_svc.return_value = instance

            # 40 vs 20 → 100% deviation → CRITICAL
            result = await self.d.detect_anomaly_hybrid(
                {"id": 55, "arac_id": 1, "mesafe_km": 300, "tuketim": 40.0},
                use_ml=False,
            )
        assert result is not None
        assert result.severity == SeverityEnum.CRITICAL
        assert result.kaynak_id == 55

    async def test_hybrid_uses_lgb_when_trained(self):
        """When lgb_trained=True, predict_severity_lgb is called."""
        mock_pred = AsyncMock(
            return_value={"tahmini_tuketim": 20.0, "model_used": "ensemble"}
        )
        with patch(
            "app.core.services.anomaly_detector.get_prediction_service"
        ) as mock_svc:
            instance = MagicMock()
            instance.predict_consumption = mock_pred
            mock_svc.return_value = instance

            self.d.lgb_trained = True
            with patch.object(
                self.d, "predict_severity_lgb", return_value=SeverityEnum.HIGH
            ) as mock_lgb:
                result = await self.d.detect_anomaly_hybrid(
                    {"id": 10, "arac_id": 1, "mesafe_km": 300, "tuketim": 40.0},
                    use_ml=True,
                )
            mock_lgb.assert_called_once()
            assert result is not None
            assert result.severity == SeverityEnum.HIGH


# ---------------------------------------------------------------------------
# predict_severity_lgb
# ---------------------------------------------------------------------------


class TestPredictSeverityLgb:
    def setup_method(self):
        self.d = make_detector()

    def test_fallback_when_not_trained(self):
        self.d.lgb_trained = False
        sev = self.d.predict_severity_lgb(30.0, 20.0, 50.0)
        assert sev == SeverityEnum.CRITICAL  # 50% → CRITICAL via rule-based

    def test_fallback_when_lgb_classifier_none(self):
        self.d.lgb_trained = True
        self.d.lgb_classifier = None
        sev = self.d.predict_severity_lgb(22.0, 20.0, 10.0)
        assert sev == SeverityEnum.LOW

    def test_lgb_classifier_predict_called(self):
        mock_clf = MagicMock()
        mock_clf.predict.return_value = [2]  # maps to "medium"
        self.d.lgb_classifier = mock_clf
        self.d.lgb_trained = True

        sev = self.d.predict_severity_lgb(25.0, 20.0, 25.0)
        assert sev == SeverityEnum.MEDIUM
        mock_clf.predict.assert_called_once()

    def test_lgb_normal_class_returns_low(self):
        mock_clf = MagicMock()
        mock_clf.predict.return_value = [0]  # "normal" → LOW
        self.d.lgb_classifier = mock_clf
        self.d.lgb_trained = True

        sev = self.d.predict_severity_lgb(21.0, 20.0, 5.0)
        assert sev == SeverityEnum.LOW

    def test_lgb_exception_falls_back_to_rule(self):
        mock_clf = MagicMock()
        mock_clf.predict.side_effect = RuntimeError("boom")
        self.d.lgb_classifier = mock_clf
        self.d.lgb_trained = True

        sev = self.d.predict_severity_lgb(30.0, 20.0, 50.0)
        assert sev == SeverityEnum.CRITICAL  # rule-based fallback

    def test_zero_expected_value_handled(self):
        mock_clf = MagicMock()
        mock_clf.predict.return_value = [1]
        self.d.lgb_classifier = mock_clf
        self.d.lgb_trained = True
        # expected_value=0 → ratio uses 1.0 guard
        sev = self.d.predict_severity_lgb(25.0, 0.0, 25.0)
        assert sev in list(SeverityEnum)


# ---------------------------------------------------------------------------
# get_detector_status
# ---------------------------------------------------------------------------


class TestGetDetectorStatus:
    def test_status_keys_present(self):
        d = make_detector()
        status = d.get_detector_status()
        assert "sklearn_available" in status
        assert "lightgbm_available" in status
        assert "isolation_forest_ready" in status
        assert "lgb_classifier_ready" in status
        assert "lgb_trained" in status

    def test_lgb_trained_false_initially(self):
        d = make_detector()
        assert d.get_detector_status()["lgb_trained"] is False


# ---------------------------------------------------------------------------
# save_anomalies — real DB bulk insert
# ---------------------------------------------------------------------------


class TestSaveAnomalies:
    def setup_method(self):
        self.d = make_detector()

    async def test_empty_list_returns_zero(self):
        assert await self.d.save_anomalies([]) == 0

    async def test_saves_anomalies_and_returns_count(self, db_session):
        anomalies = [
            make_anomaly_result(kaynak_tip="arac", kaynak_id=1),
            make_anomaly_result(
                tip=AnomalyType.SEFER,
                kaynak_tip="sefer",
                kaynak_id=2,
                severity=SeverityEnum.CRITICAL,
            ),
        ]

        result = await self.d.save_anomalies(anomalies)

        assert result == 2
        rows = (await db_session.execute(select(Anomaly))).scalars().all()
        assert len(rows) == 2
        assert {r.kaynak_id for r in rows} == {1, 2}
        assert {r.severity for r in rows} == {"high", "critical"}

    async def test_rca_populated_before_save(self, db_session):
        """save_anomalies fills RCA on each anomaly and persists it."""
        anomaly = make_anomaly_result(sapma_yuzde=55.0, severity=SeverityEnum.CRITICAL)
        assert anomaly.rca_summary == "Analiz ediliyor..."

        await self.d.save_anomalies([anomaly])

        assert anomaly.rca_summary != "Analiz ediliyor..."
        row = (await db_session.execute(select(Anomaly))).scalar_one()
        assert row.rca_summary == anomaly.rca_summary
        assert row.suggested_action == anomaly.suggested_action


# ---------------------------------------------------------------------------
# get_recent_anomalies — real DB
# ---------------------------------------------------------------------------


class TestGetRecentAnomalies:
    def setup_method(self):
        self.d = make_detector()

    async def test_returns_list_of_dicts(self, db_session):
        aid = await _seed_anomaly(db_session, severity="high")
        results = await self.d.get_recent_anomalies(days=30)
        assert isinstance(results, list)
        match = next(r for r in results if r["id"] == aid)
        assert match["severity"] == "high"

    async def test_days_clamped_min(self, db_session):
        """days < 1 is clamped to 1 (real query, no crash)."""
        results = await self.d.get_recent_anomalies(days=0)
        assert isinstance(results, list)

    async def test_days_clamped_max(self, db_session):
        """days > 365 is clamped to 365 (real query, no crash)."""
        await _seed_anomaly(db_session)
        results = await self.d.get_recent_anomalies(days=9999)
        assert isinstance(results, list)
        assert len(results) >= 1

    async def test_severity_filter_appended(self, db_session):
        await _seed_anomaly(db_session, severity="high", kaynak_id=1)
        await _seed_anomaly(db_session, severity="low", kaynak_id=2)
        results = await self.d.get_recent_anomalies(days=7, severity=SeverityEnum.HIGH)
        assert results  # at least the high one
        assert all(r["severity"] == "high" for r in results)

    async def test_status_open_filter(self, db_session):
        await _seed_anomaly(db_session)  # open: no acknowledged_at/resolved_at
        results = await self.d.get_recent_anomalies(status="open")
        assert all(r["acknowledged_at"] is None for r in results)
        assert all(r["resolved_at"] is None for r in results)

    async def test_status_acknowledged_filter(self, db_session):
        await _seed_anomaly(db_session, acknowledged_at=datetime.now(timezone.utc))
        results = await self.d.get_recent_anomalies(status="acknowledged")
        assert results
        assert all(r["acknowledged_at"] is not None for r in results)
        assert all(r["resolved_at"] is None for r in results)

    async def test_status_resolved_filter(self, db_session):
        await _seed_anomaly(db_session, resolved_at=datetime.now(timezone.utc))
        results = await self.d.get_recent_anomalies(status="resolved")
        assert results
        assert all(r["resolved_at"] is not None for r in results)

    async def test_sofor_id_filter(self, db_session):
        """sofor_id filter joins seferler; with no matching sefer → empty list."""
        await _seed_anomaly(db_session, kaynak_tip="arac", kaynak_id=1)
        results = await self.d.get_recent_anomalies(sofor_id=99)
        assert isinstance(results, list)
        assert results == []


# ---------------------------------------------------------------------------
# acknowledge — real DB
# ---------------------------------------------------------------------------


class TestAcknowledge:
    def setup_method(self):
        self.d = make_detector()

    async def test_anomaly_not_found_raises(self, db_session):
        with pytest.raises(ValueError, match="bulunamadı"):
            await self.d.acknowledge(anomaly_id=999, user_id=10)

    async def test_already_resolved_raises(self, db_session):
        aid = await _seed_anomaly(db_session, resolved_at=datetime.now(timezone.utc))
        with pytest.raises(ValueError, match="Çözülmüş"):
            await self.d.acknowledge(anomaly_id=aid, user_id=10)

    async def test_acknowledge_success_persists(self, db_session):
        uid = await _seed_user(db_session)
        aid = await _seed_anomaly(db_session)

        result = await self.d.acknowledge(anomaly_id=aid, user_id=uid)

        assert result["id"] == aid
        assert result["status"] == "acknowledged"
        assert result["acknowledged_by"] == uid
        # Real row updated.
        row = await _get_anomaly(db_session, aid)
        assert row.acknowledged_at is not None
        assert row.acknowledged_by == uid
        assert row.resolved_at is None


# ---------------------------------------------------------------------------
# resolve — real DB
# ---------------------------------------------------------------------------


class TestResolve:
    def setup_method(self):
        self.d = make_detector()

    async def test_anomaly_not_found_raises(self, db_session):
        with pytest.raises(ValueError, match="bulunamadı"):
            await self.d.resolve(anomaly_id=999, user_id=1)

    async def test_resolve_success_persists(self, db_session):
        uid = await _seed_user(db_session)
        aid = await _seed_anomaly(
            db_session, acknowledged_at=datetime.now(timezone.utc)
        )

        result = await self.d.resolve(
            anomaly_id=aid, user_id=uid, notes="Fixed the sensor"
        )

        assert result["id"] == aid
        assert result["status"] == "resolved"
        assert result["resolved_by"] == uid
        assert result["resolution_notes"] == "Fixed the sensor"
        row = await _get_anomaly(db_session, aid)
        assert row.resolved_at is not None
        assert row.resolved_by == uid
        assert row.resolution_notes == "Fixed the sensor"

    async def test_resolve_auto_acknowledges_when_not_acknowledged(self, db_session):
        """resolve without prior ack also sets acknowledged_at (real row)."""
        uid = await _seed_user(db_session)
        aid = await _seed_anomaly(db_session)  # acknowledged_at is NULL

        result = await self.d.resolve(anomaly_id=aid, user_id=uid)

        assert result["status"] == "resolved"
        row = await _get_anomaly(db_session, aid)
        assert row.resolved_at is not None
        assert row.acknowledged_at is not None  # auto-acknowledged
        assert row.acknowledged_by == uid

    async def test_resolve_no_notes(self, db_session):
        uid = await _seed_user(db_session)
        aid = await _seed_anomaly(
            db_session, acknowledged_at=datetime.now(timezone.utc)
        )
        result = await self.d.resolve(anomaly_id=aid, user_id=uid)
        assert result["resolution_notes"] is None
        row = await _get_anomaly(db_session, aid)
        assert row.resolution_notes is None


# ---------------------------------------------------------------------------
# save_model / load_model (error branches)
# ---------------------------------------------------------------------------


class TestModelPersistence:
    def setup_method(self):
        self.d = make_detector()

    def test_save_model_raises_if_not_trained(self):
        self.d.lgb_trained = False
        with pytest.raises(RuntimeError, match="eğitilmedi"):
            self.d.save_model("/tmp/test_model.pkl")

    def test_load_model_raises_if_lgbm_unavailable(self):
        with patch("app.core.services.anomaly_detector.LIGHTGBM_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="not available"):
                self.d.load_model("/tmp/test_model.pkl")

    def test_load_model_raises_if_files_missing(self):
        with patch("app.core.services.anomaly_detector.LIGHTGBM_AVAILABLE", True):
            with pytest.raises(FileNotFoundError):
                self.d.load_model("/tmp/nonexistent_model.pkl")


# ---------------------------------------------------------------------------
# train_lgb_classifier (early-return branches)
# ---------------------------------------------------------------------------


class TestTrainLgbClassifier:
    async def test_not_available_returns_error_dict(self):
        d = make_detector()
        with patch("app.core.services.anomaly_detector.LIGHTGBM_AVAILABLE", False):
            d.lgb_classifier = None
            result = await d.train_lgb_classifier()
        assert result["success"] is False
        assert "not available" in result["error"].lower()

    async def test_insufficient_data_returns_error(self):
        d = make_detector()
        # Return fewer than 20 rows from get_recent_anomalies
        with patch.object(
            d, "get_recent_anomalies", return_value=[{"id": i} for i in range(5)]
        ):
            result = await d.train_lgb_classifier()
        assert result["success"] is False
        assert "Yetersiz" in result["error"]
