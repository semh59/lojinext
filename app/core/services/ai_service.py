"""
LOJINEXT Intelligence Service (AIService)
Handles ML predictions and data intelligence.
Globalized to English (v2.1).

TYPE: SINGLETON
SCOPE: Application lifetime
SINGLETON_REASON: AI servisi — Groq LLM çağrıları, context builder.
CREATED_BY: app/core/container.py (lazy property)
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

import numpy as np

from app.core.entities.models import PredictionResult as PredictionResultModel
from app.core.ml.ensemble_predictor import EnsembleFuelPredictor
from app.core.ml.physics_fuel_predictor import VehicleSpecs
from app.database.unit_of_work import UnitOfWork
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class AIService:
    """AI Service for fuel prediction, anomaly detection, and LLM chat."""

    # Patterns to redact from user prompts (prompt-injection guards)
    _REDACT_PATTERNS = [
        r"SYSTEM\s*:",
        r"ADMIN[\s_]+MODE",
        r"###",
    ]

    _PREDICTOR_CACHE_TTL = 3600  # 1 saat — yeni sefer verisi sonrası yeniden eğitim

    def __init__(self):
        self._predictor_cache: Dict[int, tuple] = {}  # arac_id → (predictor, cached_at)
        from app.core.ai.groq_service import GroqService

        self.groq = GroqService()

    # ── Prompt safety ────────────────────────────────────────────────────────
    def _sanitize_prompt(self, prompt: str, max_length: int = 1000) -> str:
        """Redact dangerous injection tokens and truncate to max_length."""
        import re

        sanitized = prompt
        for pattern in self._REDACT_PATTERNS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                sanitized = re.sub(
                    pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE
                )
        return sanitized[:max_length]

    # ── Context builder ──────────────────────────────────────────────────────
    async def _build_context(self) -> str:
        """Build a fleet-context string for LLM grounding."""
        try:
            from app.database.unit_of_work import UnitOfWork

            async with UnitOfWork() as uow:
                stats = await uow.analiz_repo.get_dashboard_stats()
                alerts = await uow.analiz_repo.get_recent_unread_alerts()
                vehicles = await uow.arac_repo.get_all(limit=5)

            parts: List[str] = []
            if stats:
                parts.append(
                    f"Filo Ozeti: {stats.get('toplam_arac', 0)} Arac, "
                    f"{stats.get('toplam_sofor', 0)} Sofor, "
                    f"Ort Tuketim: {stats.get('filo_ortalama', 0):.1f} L/100km"
                )
            for alert in (alerts or [])[:3]:
                parts.append(
                    f"Uyari: {alert.get('title', '')} - {alert.get('message', '')}"
                )
            for v in (vehicles or [])[:3]:
                parts.append(
                    f"Arac: {v.get('plaka', '')} ({v.get('motor_verimliligi', ''):.2f} verim)"
                )

            return "\n".join(parts) if parts else "Filo verisi mevcut degil."
        except Exception as exc:
            logger.warning(f"Context build failed: {exc}")
            return "Sistem verileri su an alinamiyor"

    # ── LLM response ─────────────────────────────────────────────────────────
    async def generate_response(self, user_input: str) -> str:
        """Generate a single LLM response grounded in fleet context."""
        try:
            context = await self._build_context()
            safe_prompt = self._sanitize_prompt(user_input)
            return await self.groq.chat(
                f"Filo Bağlamı:\n{context}\n\nKullanıcı: {safe_prompt}"
            )
        except Exception as exc:
            logger.error(f"generate_response failed: {exc}")
            return "Uzgunum, su an cevap veremiyorum."

    async def stream_response(self, user_input: str):
        """Yield response tokens one by one."""
        context = await self._build_context()
        safe_prompt = self._sanitize_prompt(user_input)
        async for token in self.groq.chat_stream(
            f"Filo Bağlamı:\n{context}\n\nKullanıcı: {safe_prompt}"
        ):
            yield token

    def get_progress(self) -> Dict[str, Any]:
        """RAG engine'in yüklenme durumu — /ai/progress endpoint'i kullanır.

        `status`: 'ready' | 'loading' | 'error' | 'offline' (rag_engine.status)
        `pending_jobs`: Şu an arka planda devam eden RAG/embedding işi sayısı
        (rag_engine.async_pending_jobs döndürür, yoksa 0).
        """
        try:
            from app.core.ai.rag_engine import get_rag_engine

            rag = get_rag_engine()
            return {
                "status": getattr(rag, "status", "offline"),
                "pending_jobs": int(getattr(rag, "async_pending_jobs", 0) or 0),
            }
        except Exception as exc:
            logger.warning(f"AI progress probe failed: {exc}")
            return {"status": "error", "pending_jobs": 0}

    def invalidate_predictor_cache(self, arac_id: int) -> None:
        """Force-expire a vehicle's predictor (call after new trips are saved)."""
        self._predictor_cache.pop(arac_id, None)

    async def _get_predictor_for_vehicle(
        self, arac_id: int, uow: UnitOfWork
    ) -> EnsembleFuelPredictor:
        """Retrieves or initializes a predictor for a specific vehicle."""
        cached = self._predictor_cache.get(arac_id)
        if cached and (time.monotonic() - cached[1]) < self._PREDICTOR_CACHE_TTL:
            return cached[0]

        # Get vehicle specs
        arac = await uow.arac_repo.get_by_id(arac_id)
        if not arac:
            logger.warning(f"Predictor requested for non-existent vehicle: {arac_id}")
            # Fallback to default specs
            specs = VehicleSpecs()
        else:
            specs = VehicleSpecs(
                engine_efficiency=float(arac.get("motor_verimliligi") or 0.35),
                rolling_resistance=float(arac.get("lastik_direnc_katsayisi") or 0.007),
                frontal_area_m2=float(arac.get("on_kesit_alani_m2") or 9.5),
                drag_coefficient=float(arac.get("hava_direnc_katsayisi") or 0.65),
                empty_weight_kg=float(arac.get("bos_agirlik_kg") or 7500.0),
            )

        predictor = EnsembleFuelPredictor(vehicle_specs=specs)

        # Train with historical data if available
        history = await uow.sefer_repo.get_for_training(arac_id, limit=200)
        if len(history) >= 10:
            history_data = [dict(h) for h in history]
            y_actual = np.array([float(h.get("tuketim") or 0) for h in history_data])
            try:
                await asyncio.to_thread(predictor.fit, history_data, y_actual)
                logger.info(
                    f"Predictor trained for Vehicle {arac_id} with {len(history)} trips."
                )
            except Exception as e:
                logger.error(f"Predictor training failed for Vehicle {arac_id}: {e}")

        self._predictor_cache[arac_id] = (predictor, time.monotonic())
        return predictor

    async def predict_trip_fuel(
        self,
        arac_id: int,
        ton: float,
        mesafe_km: float,
        ascent_m: float = 0,
        descent_m: float = 0,
        flat_km: float = 0,
        dorse_id: Optional[int] = None,
        route_analysis: Optional[Dict] = None,
    ) -> PredictionResultModel:
        """Main prediction entry point (English)."""
        async with UnitOfWork() as uow:
            predictor = await self._get_predictor_for_vehicle(arac_id, uow)

            # Build prediction context (The "Sync" part)
            sefer_context = {
                "ton": ton,
                "mesafe_km": mesafe_km,
                "ascent_m": ascent_m,
                "descent_m": descent_m,
                "flat_distance_km": flat_km,
                "rota_detay": {"route_analysis": route_analysis}
                if route_analysis
                else {},
            }

            # Propagate trailer (dorse) specs to ML model if dorse_id is provided
            if dorse_id:
                dorse_row = await uow.dorse_repo.get_by_id(
                    dorse_id, include_inactive=True
                )
                if dorse_row:
                    sefer_context["dorse_bos_agirlik"] = float(
                        dorse_row.get("bos_agirlik_kg") or 6500
                    )
                    sefer_context["dorse_lastik_sayisi"] = int(
                        dorse_row.get("lastik_sayisi") or 6
                    )
                    logger.debug(
                        f"Trailer features synced: {sefer_context['dorse_bos_agirlik']}kg, {sefer_context['dorse_lastik_sayisi']} tires."  # noqa: E501
                    )

            # Run ensemble prediction (predict takes one context, returns one result)
            res = await asyncio.to_thread(predictor.predict, sefer_context)

            return PredictionResultModel(
                tahmin_l_100km=res.tahmin_l_100km,
                guven_araligi_alt=res.confidence_low,
                guven_araligi_ust=res.confidence_high,
                fizik_basarimi=res.physics_weight,
                feature_etkisi=res.features_used,
            )

    async def detect_anomalies(self, arac_id: int) -> List[Dict]:
        """Anomaly detection for fuel logs."""
        async with UnitOfWork() as uow:
            # get_all returns a paginated {"items": [...], "total": N} dict — the
            # anomaly loop below needs the record list, not the envelope.
            history = (await uow.yakit_repo.get_all(arac_id=arac_id, limit=50)).get(
                "items", []
            )
            if len(history) < 5:
                return []

            anomalies = []
            # Simple Z-Score anomaly detection for demonstration
            # In production, this would use a more sophisticated isolation forest or similar.
            litres = [float(h.get("litre") or 0) for h in history]
            kms = [int(h.get("km_sayac") or 0) for h in history]
            consumptions = []
            for i in range(len(litres) - 1):
                dist = kms[i] - kms[i + 1]
                if dist > 0:
                    consumptions.append((litres[i] / dist) * 100)

            if consumptions:
                avg = np.mean(consumptions)
                std = np.std(consumptions)
                if std > 0:
                    threshold = 2.0
                    for i, cons in enumerate(consumptions):
                        z = abs(cons - avg) / std
                        if z > threshold:
                            anomalies.append(
                                {
                                    "index": i,
                                    "date": history[i].get("tarih"),
                                    "value": cons,
                                    "z_score": z,
                                    "type": "CONSUMPTION_SPIKE",
                                }
                            )

            return anomalies


def get_ai_service() -> AIService:
    from app.core.container import get_container

    return get_container().ai_service
