"""
TYPE: SINGLETON
SCOPE: Application lifetime
SINGLETON_REASON: Anomali tespiti — Isolation Forest + LGBM modelleri başlangıçta yüklenir.
CREATED_BY: app/core/container.py (lazy property)

``AnomalyDetector`` sınıf istisnası (B.1): ``RouteSimulator``/``LokasyonHydrator``/
``DriverPerformanceML`` ile aynı gerekçe — sklearn ``IsolationForest`` +
LightGBM ``LGBMClassifier`` + ``lgb_trained`` bayrağı gerçek mutable eğitilmiş-model
state'i taşır, tek-cohesive-pipeline'dır (istatistiksel + ML hibrit tespit).
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# sklearn lazy import
try:
    from sklearn.ensemble import IsolationForest

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# LightGBM lazy import
try:
    import lightgbm as lgb

    LIGHTGBM_AVAILABLE = True
except ImportError:
    lgb = None
    LIGHTGBM_AVAILABLE = False

from app.config import settings
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger
from v2.modules.prediction_ml.public import get_prediction_service

logger = get_logger(__name__)


class SeverityEnum(str, Enum):
    """Anomali ciddiyeti"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyType(str, Enum):
    """Anomali tipleri"""

    TUKETIM = "tuketim"
    MALIYET = "maliyet"
    SEFER = "sefer"


@dataclass
class AnomalyResult:
    """Anomali sonucu"""

    tip: AnomalyType
    kaynak_tip: str  # 'arac', 'sofor', 'sefer', 'yakit'
    kaynak_id: int
    deger: float
    beklenen_deger: float
    sapma_yuzde: float
    severity: SeverityEnum
    aciklama: str
    rca_summary: Optional[str] = "Analiz ediliyor..."
    suggested_action: Optional[str] = "İncelenmeli"
    tarih: date = None

    def __post_init__(self):
        if self.tarih is None:
            self.tarih = date.today()


class AnomalyDetector:
    """
    Hibrit Anomali Tespit Sistemi (Async + SQLAlchemy)

    Modeller:
    1. IsolationForest (Unsupervised) - sklearn
    2. LightGBM Classifier (Supervised) - lightgbm
    3. İstatistiksel (Z-Score + IQR)
    """

    # Eşikler (Config-driven). Z_THRESHOLD burada sadece geriye-uyum
    # fallback'i olarak tutulur — gerçek karar yolu
    # detect_consumption_anomalies içinde runtime_config.get_runtime_float
    # ile async boundary'de çözülür (sistem_konfig ANOMALY_Z_THRESHOLD satırı).
    Z_THRESHOLD = settings.ANOMALY_Z_THRESHOLD  # Default: 2.5
    IQR_MULTIPLIER = 1.5
    COST_DEVIATION_THRESHOLD = 0.15  # %15

    # LightGBM severity label mapping
    SEVERITY_MAP = {
        "normal": 0,
        SeverityEnum.LOW.value: 1,
        SeverityEnum.MEDIUM.value: 2,
        SeverityEnum.HIGH.value: 3,
        SeverityEnum.CRITICAL.value: 4,
    }
    REVERSE_SEVERITY_MAP = {v: k for k, v in SEVERITY_MAP.items()}

    def __init__(self):
        # IsolationForest (unsupervised)
        if SKLEARN_AVAILABLE:
            self.isolation_forest = IsolationForest(
                n_estimators=100, contamination=0.1, random_state=42
            )
        else:
            self.isolation_forest = None
            logger.warning("sklearn not available, IsolationForest disabled")

        # LightGBM Classifier (supervised)
        if LIGHTGBM_AVAILABLE:
            self.lgb_classifier = lgb.LGBMClassifier(
                objective="multiclass",
                num_class=5,
                class_weight="balanced",
                num_leaves=15,
                learning_rate=0.05,
                n_estimators=100,
                verbose=-1,
                random_state=42,
            )
            self.lgb_trained = False
            logger.info("LightGBM Classifier initialized for anomaly detection")
        else:
            self.lgb_classifier = None
            self.lgb_trained = False
            logger.warning("lightgbm not available, ML classifier disabled")

    async def detect_consumption_anomalies(
        self, consumptions: List[float], arac_id: int = None, use_ml: bool = True
    ) -> List[AnomalyResult]:
        """Tüketim verilerinde anomali tespit et (İstatistiksel). Eşik: runtime config."""
        if len(consumptions) < 5:
            return []

        from v2.modules.admin_platform.public import (
            get_runtime_float,
        )

        z_threshold = await get_runtime_float(
            "ANOMALY_Z_THRESHOLD", settings.ANOMALY_Z_THRESHOLD
        )

        anomalies = []
        arr = np.array(consumptions)

        mean_val = np.mean(arr)
        std_val = np.std(arr)
        q1, q3 = np.percentile(arr, [25, 75])
        iqr = q3 - q1

        z_scores = (arr - mean_val) / std_val if std_val > 0 else np.zeros_like(arr)
        z_anomalies = np.abs(z_scores) > z_threshold

        lower_bound = q1 - (self.IQR_MULTIPLIER * iqr)
        upper_bound = q3 + (self.IQR_MULTIPLIER * iqr)
        iqr_anomalies = (arr < lower_bound) | (arr > upper_bound)

        confirmed = (z_anomalies.astype(int) + iqr_anomalies.astype(int)) >= 2

        for i, is_anomaly in enumerate(confirmed):
            if is_anomaly:
                value = consumptions[i]
                deviation = ((value - mean_val) / mean_val) * 100 if mean_val > 0 else 0
                severity = self._calculate_severity(abs(deviation))

                anomalies.append(
                    AnomalyResult(
                        tip=AnomalyType.TUKETIM,
                        kaynak_tip="arac" if arac_id else "sefer",
                        kaynak_id=arac_id or i,
                        deger=round(value, 2),
                        beklenen_deger=round(mean_val, 2),
                        sapma_yuzde=round(deviation, 1),
                        severity=severity,
                        aciklama=f"Tüketim {'+' if deviation > 0 else ''}{deviation:.1f}% sapma",
                    )
                )

        return anomalies

    async def detect_trip_anomaly_elite(
        self, trip_data: Dict
    ) -> Optional[AnomalyResult]:
        """
        Sefer Anomalisi: Statik değer yerine PredictionService kullanır.
        """
        consumption = trip_data.get("tuketim")
        if not consumption:
            return None

        pred_service = get_prediction_service()
        prediction = await pred_service.predict_consumption(
            arac_id=trip_data["arac_id"],
            mesafe_km=trip_data["mesafe_km"],
            ton=trip_data.get("ton", 20.0),
            ascent_m=trip_data.get("ascent_m", 0),
            descent_m=trip_data.get("descent_m", 0),
            sofor_id=trip_data.get("sofor_id"),
        )

        expected = prediction["tahmini_tuketim"]
        deviation = ((consumption - expected) / expected) * 100 if expected > 0 else 0

        if abs(deviation) > 20:  # %20 sapma anomali kabul edilir
            severity = self._calculate_severity(abs(deviation))
            model_used = prediction.get("model_used", "ensemble")
            return AnomalyResult(
                tip=AnomalyType.SEFER,
                kaynak_tip="sefer",
                kaynak_id=trip_data.get("id", 0),
                deger=round(consumption, 2),
                beklenen_deger=round(expected, 2),
                sapma_yuzde=round(deviation, 1),
                severity=severity,
                aciklama=f"Tahminden Şaşma: {deviation:+.1f}% ({model_used})",
                tarih=trip_data.get("tarih"),
            )
        return None

    def _calculate_severity(self, deviation_pct: float) -> SeverityEnum:
        if deviation_pct >= 50:
            return SeverityEnum.CRITICAL
        elif deviation_pct >= 30:
            return SeverityEnum.HIGH
        elif deviation_pct >= 15:
            return SeverityEnum.MEDIUM
        return SeverityEnum.LOW

    def _generate_heuristic_rca(self, result: AnomalyResult) -> Tuple[str, str]:
        """Anomali için hızlı, kural tabanlı kök neden analizi."""
        tip = result.tip

        rca = "Bilinmeyen Neden"
        action = "Detaylı inceleme yapın"

        if tip == AnomalyType.TUKETIM or tip == AnomalyType.SEFER:
            if result.sapma_yuzde > 50:
                rca = "Olası Yakıt Hırsızlığı veya Sensör Kaybı"
                action = "Yakıt deposunu ve sensör verilerini acilen kontrol edin"
            elif result.sapma_yuzde > 25:
                rca = "Agresif Sürüş veya Hatalı Rota"
                action = "Sürücü sürüş skorlarını ve rota ihlallerini inceleyin"
            elif result.sapma_yuzde > 15:
                rca = "Ağır Yük / Trafik / Olumsuz Hava"
                action = "Sefer yükü ve güzergah koşullarını teyit edin"
            elif result.sapma_yuzde < -20:
                rca = "Sensör Kalibrasyon Sapması"
                action = "Cihazın son kalibrasyon tarihini kontrol edin"

        return rca, action

    async def save_anomalies(self, anomalies: List[AnomalyResult]) -> int:
        """Anomalileri PostgreSQL'e kaydet (UoW - Bulk Insert)"""
        if not anomalies:
            return 0

        async with UnitOfWork() as uow:
            # RCA'ları önceden hesapla (Pre-calculated)
            for a in anomalies:
                rca, action = self._generate_heuristic_rca(a)
                a.rca_summary = rca
                a.suggested_action = action

            # Toplu kayıt için parametre listesi hazırla
            params_list = [
                {
                    "tarih": a.tarih or date.today(),
                    "tip": a.tip.value,
                    "kaynak_tip": a.kaynak_tip,
                    "kaynak_id": a.kaynak_id,
                    "deger": a.deger,
                    "beklenen_deger": a.beklenen_deger,
                    "sapma_yuzde": a.sapma_yuzde,
                    "severity": a.severity.value,
                    "aciklama": a.aciklama,
                    "rca_summary": a.rca_summary,
                    "suggested_action": a.suggested_action,
                }
                for a in anomalies
            ]

            await uow.anomaly_repo.bulk_create_anomalies(params_list)
            await uow.commit()

        logger.info(f"Saved {len(anomalies)} anomalies to PostgreSQL (bulk)")
        return len(anomalies)

    async def get_recent_anomalies(
        self,
        days: int = 30,
        severity: SeverityEnum = None,
        status: Optional[str] = None,
        sofor_id: Optional[int] = None,
    ) -> List[Dict]:
        """Geçmiş anomalileri getir (Güvenli & Parametreli).

        status: ``open`` (acknowledged_at IS NULL), ``acknowledged``
        (acknowledged_at set ama resolved_at NULL), ``resolved``
        (resolved_at set).

        sofor_id: verildiğinde sadece bu şoföre ait sefer anomalileri
        döner (LEFT JOIN seferler.sofor_id'ye filtre). None ise tüm filo.

        Response her satırda `sofor_id` SELECT edilir; coaching engine
        gibi callerlar post-filter de yapabilir.
        """
        days_val = max(1, min(int(days), 365))

        async with UnitOfWork() as uow:
            return await uow.anomaly_repo.get_anomalies_filtered(
                days=days_val,
                severity=severity.value if severity else None,
                status=status,
                sofor_id=sofor_id,
            )

    # ============== LightGBM Persistence (Güvenli Format) ==============

    def save_model(self, filepath: str):
        """Modeli diske kaydet (Native format - Güvenli)"""
        if not self.lgb_trained or self.lgb_classifier is None:
            raise RuntimeError("Model eğitilmedi")

        import json
        from pathlib import Path

        base_path = Path(filepath).with_suffix("")

        # 1. Native LightGBM (Güvenli JSON/Text)
        self.lgb_classifier.booster_.save_model(f"{base_path}_lgb.json")

        # 2. Metadata
        metadata = {
            "lgb_trained": self.lgb_trained,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        with open(f"{base_path}_meta.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"Anomaly classifier saved to {base_path}")

    def load_model(self, filepath: str):
        """Modeli diskten yükle (Native format - Güvenli)"""
        if not LIGHTGBM_AVAILABLE:
            raise RuntimeError("LightGBM not available")

        import json
        from pathlib import Path

        base_path = Path(filepath).with_suffix("")
        meta_file = Path(f"{base_path}_meta.json")
        lgb_file = Path(f"{base_path}_lgb.json")

        if not meta_file.exists() or not lgb_file.exists():
            raise FileNotFoundError("Model dosyaları bulunamadı")

        # 1. Metadata
        with open(meta_file, encoding="utf-8") as f:
            metadata = json.load(f)
        self.lgb_trained = metadata["lgb_trained"]

        # 2. Native Model
        if self.lgb_classifier is None:
            import lightgbm as lgb_lib

            self.lgb_classifier = lgb_lib.LGBMClassifier()

        self.lgb_classifier.booster_ = lgb.Booster(model_file=str(lgb_file))

        logger.info(f"Anomaly classifier loaded from {base_path}")

    # ============== LightGBM Classifier Methods ==============

    async def train_lgb_classifier(self) -> Dict:
        """
        LightGBM sınıflandırıcıyı geçmiş anomalilerden eğit.

        Features:
        - value: Gerçek tüketim değeri
        - expected_value: Beklenen değer
        - deviation_pct: Sapma yüzdesi
        - abs_deviation: Mutlak sapma

        Target: severity (0-4)
        """
        if not LIGHTGBM_AVAILABLE or self.lgb_classifier is None:
            return {"success": False, "error": "LightGBM not available"}

        # Geçmiş anomalileri çek
        anomalies = await self.get_recent_anomalies(days=365)

        if len(anomalies) < 20:
            return {
                "success": False,
                "error": f"Yetersiz veri: {len(anomalies)} anomali. En az 20 gerekli.",
            }

        try:
            # Feature matrisi oluştur
            X: Any = []
            y: Any = []

            for a in anomalies:
                from app.config import settings

                value = float(a.get("deger", 0) or 0)
                expected = float(
                    a.get("beklenen_deger") or settings.DEFAULT_FILO_HEDEF_TUKETIM
                )
                deviation = float(a.get("sapma_yuzde", 0) or 0)

                severity_str = a.get("severity", "low")

                X.append(
                    [
                        value,
                        expected,
                        deviation,
                        abs(deviation),
                        value / expected if expected > 0 else 1.0,
                    ]
                )

                y.append(self.SEVERITY_MAP.get(severity_str, 1))

            X = np.array(X)
            y = np.array(y)

            import asyncio

            # FAZ 2.1: Model eğitimini thread pool'a al (Event loop blocking önlemi)
            await asyncio.to_thread(self.lgb_classifier.fit, X, y)
            self.lgb_trained = True

            # Metrikleri de thread'de hesapla
            from sklearn.metrics import accuracy_score

            y_pred = await asyncio.to_thread(self.lgb_classifier.predict, X)
            accuracy = await asyncio.to_thread(accuracy_score, y, y_pred)

            logger.info(f"LightGBM anomaly classifier trained: accuracy={accuracy:.3f}")

            return {
                "success": True,
                "accuracy": round(accuracy, 4),
                "sample_count": len(y),
                "class_distribution": {
                    self.REVERSE_SEVERITY_MAP.get(i, "unknown"): int(np.sum(y == i))
                    for i in range(5)
                },
            }

        except Exception as e:
            logger.error(f"LightGBM classifier training error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def predict_severity_lgb(
        self, value: float, expected_value: float, deviation_pct: float
    ) -> SeverityEnum:
        """
        LightGBM ile anomali ciddiyeti tahmin et.

        Args:
            value: Gerçek tüketim değeri
            expected_value: Beklenen değer
            deviation_pct: Sapma yüzdesi

        Returns:
            SeverityEnum: Tahmin edilen ciddiyet
        """
        if not self.lgb_trained or self.lgb_classifier is None:
            # Fallback to rule-based
            return self._calculate_severity(abs(deviation_pct))

        try:
            X = np.array(
                [
                    [
                        value,
                        expected_value,
                        deviation_pct,
                        abs(deviation_pct),
                        value / expected_value if expected_value > 0 else 1.0,
                    ]
                ]
            )

            y_pred = self.lgb_classifier.predict(X)[0]
            severity_str = self.REVERSE_SEVERITY_MAP.get(y_pred, "low")

            if severity_str == "normal":
                return SeverityEnum.LOW

            return SeverityEnum(severity_str)

        except Exception as e:
            logger.warning(f"LightGBM prediction failed: {e}")
            return self._calculate_severity(abs(deviation_pct))

    async def detect_anomaly_hybrid(
        self, trip_data: Dict, use_ml: bool = True
    ) -> Optional[AnomalyResult]:
        """
        Hibrit anomali tespiti: İstatistiksel + ML.

        1. Prediction ile beklenen değeri hesapla
        2. Sapma kontrolü
        3. LightGBM ile ciddiyet tahmini (eğitilmişse)
        """
        consumption = trip_data.get("tuketim")
        if not consumption:
            return None

        # Prediction
        pred_service = get_prediction_service()
        prediction = await pred_service.predict_consumption(
            arac_id=trip_data["arac_id"],
            mesafe_km=trip_data["mesafe_km"],
            ton=trip_data.get("ton", 20.0),
            ascent_m=trip_data.get("ascent_m", 0),
            descent_m=trip_data.get("descent_m", 0),
            sofor_id=trip_data.get("sofor_id"),
        )

        expected = prediction["tahmini_tuketim"]
        deviation = ((consumption - expected) / expected) * 100 if expected > 0 else 0

        # Anomali eşiği: %20
        if abs(deviation) <= 20:
            return None

        # Ciddiyet belirle (ML veya rule-based)
        if use_ml and self.lgb_trained:
            severity = self.predict_severity_lgb(consumption, expected, deviation)
        else:
            severity = self._calculate_severity(abs(deviation))

        return AnomalyResult(
            tip=AnomalyType.SEFER,
            kaynak_tip="sefer",
            kaynak_id=trip_data.get("id", 0),
            deger=round(consumption, 2),
            beklenen_deger=round(expected, 2),
            sapma_yuzde=round(deviation, 1),
            severity=severity,
            aciklama=f"Hibrit Tespit: {deviation:+.1f}% sapma (ML: {self.lgb_trained})",
            tarih=trip_data.get("tarih"),
        )

    async def acknowledge(self, anomaly_id: int, user_id: int) -> Dict:
        """Anomaliyi onaylanmış olarak işaretle."""
        now = datetime.now(timezone.utc)
        async with UnitOfWork() as uow:
            row = await uow.anomaly_repo.get_anomaly_by_id(anomaly_id)
            if not row:
                raise ValueError("Anomali bulunamadı")
            if row.resolved_at is not None:
                raise ValueError("Çözülmüş anomali tekrar onaylanamaz")
            # Virtual superadmin (id=0) has no kullanicilar row — use NULL to avoid FK violation
            safe_user_id = user_id if user_id and user_id > 0 else None
            await uow.anomaly_repo.update_anomaly(
                anomaly_id, acknowledged_at=now, acknowledged_by=safe_user_id
            )
            await uow.commit()
        return {
            "id": anomaly_id,
            "status": "acknowledged",
            "acknowledged_at": now.isoformat(),
            "acknowledged_by": user_id,
        }

    async def resolve(
        self, anomaly_id: int, user_id: int, notes: Optional[str] = None
    ) -> Dict:
        """Anomaliyi çözülmüş olarak işaretle. Notlar opsiyonel ama önerilir."""
        now = datetime.now(timezone.utc)
        async with UnitOfWork() as uow:
            row = await uow.anomaly_repo.get_anomaly_by_id(anomaly_id)
            if not row:
                raise ValueError("Anomali bulunamadı")
            # Henüz onaylanmamışsa, resolve aynı zamanda acknowledge anlamına gelir.
            # Virtual superadmin (id=0) has no kullanicilar row — use NULL to avoid FK violation
            safe_user_id = user_id if user_id and user_id > 0 else None
            values: Dict = {
                "resolved_at": now,
                "resolved_by": safe_user_id,
                "resolution_notes": notes,
            }
            if row.acknowledged_at is None:
                values["acknowledged_at"] = now
                values["acknowledged_by"] = safe_user_id
            await uow.anomaly_repo.update_anomaly(anomaly_id, **values)
            await uow.commit()
        return {
            "id": anomaly_id,
            "status": "resolved",
            "resolved_at": now.isoformat(),
            "resolved_by": user_id,
            "resolution_notes": notes,
        }

    def get_detector_status(self) -> Dict:
        """Detector durumu."""
        return {
            "sklearn_available": SKLEARN_AVAILABLE,
            "lightgbm_available": LIGHTGBM_AVAILABLE,
            "isolation_forest_ready": self.isolation_forest is not None,
            "lgb_classifier_ready": self.lgb_classifier is not None,
            "lgb_trained": self.lgb_trained,
        }


def get_anomaly_detector() -> AnomalyDetector:
    """Delegates to the DI container for the singleton AnomalyDetector instance."""
    from app.core.container import get_container

    return get_container().anomaly_detector
