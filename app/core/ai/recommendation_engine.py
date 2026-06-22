import os
import threading
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import List, Optional

from sqlalchemy import text

from app.database.unit_of_work import unit_of_work
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Recommendation:
    """Öneri modeli"""

    kategori: str  # 'verimlilik', 'maliyet', 'bakim', 'egitim'
    hedef_tip: str  # 'arac', 'sofor', 'filo'
    hedef_id: Optional[int]
    mesaj: str
    oncelik: int  # 1-5 (5 = en yüksek)
    aksiyon: Optional[str] = None


class RecommendationEngine:
    """
    Akıllı öneri motoru (Async & PostgreSQL Optimized).
    """

    # Config (Safe Parse - ValueError önleme)
    try:
        CACHE_TTL = int(os.getenv("AI_CACHE_TTL", "3600"))
    except (ValueError, TypeError):
        CACHE_TTL = 3600  # 1 saat default

    def __init__(self):
        self._cache = {}
        self._cache_time = {}
        self._lock = threading.Lock()  # Thread-safe cache guard

    def _is_cache_valid(self, key: str) -> bool:
        """Cache geçerlilik kontrolü. NOT: Lock DIŞARIDAN alınmalı (deadlock önleme)."""
        # DEADLOCK FIX: Bu metod lock içinden çağrılıyor, iç lock kaldırıldı
        if key not in self._cache_time:
            return False
        elapsed = (datetime.now(timezone.utc) - self._cache_time[key]).total_seconds()
        return elapsed < self.CACHE_TTL

    # =========================================================================
    # ARAÇ ÖNERİLERİ
    # =========================================================================

    async def get_vehicle_recommendations(self, arac_id: int) -> List[Recommendation]:
        """Araç için öneriler üret (Async)"""
        cache_key = f"arac_{arac_id}"
        with self._lock:
            if self._is_cache_valid(cache_key):
                return self._cache[cache_key]

        recommendations: list[Recommendation] = []

        async with unit_of_work() as uow:
            arac = await uow.arac_repo.get_by_id(arac_id)
            if not arac:
                return recommendations

            plaka = arac["plaka"]
            hedef = arac.get("hedef_tuketim", 32.0)
            yil = arac.get("yil", 2020)
            yas = date.today().year - yil

            # Son 30 gün tüketim (PostgreSQL Syntax)
            sql = text("""
                SELECT AVG(tuketim) as ort, COUNT(*) as sayi
                FROM seferler
                WHERE arac_id = :id AND tuketim IS NOT NULL
                AND tarih >= CURRENT_DATE - INTERVAL '30 days'
            """)
            result_raw = await uow.session.execute(sql, {"id": arac_id})
            result = result_raw.fetchone()

            if result and result.ort:
                ort_tuketim = float(result.ort)
                sapma = ((ort_tuketim - hedef) / hedef) * 100 if hedef > 0 else 0

                if sapma > 10:
                    recommendations.append(
                        Recommendation(
                            kategori="verimlilik",
                            hedef_tip="arac",
                            hedef_id=arac_id,
                            mesaj=f"{plaka}: Tüketim hedefin %{sapma:.0f} üzerinde ({ort_tuketim:.1f} L/100km)",
                            oncelik=4 if sapma > 20 else 3,
                            aksiyon="Bakım ve lastik kontrolü yapılmalı",
                        )
                    )

            if yas >= 10:
                recommendations.append(
                    Recommendation(
                        kategori="bakim",
                        hedef_tip="arac",
                        hedef_id=arac_id,
                        mesaj=f"{plaka}: {yas} yaşında, düzenli bakım kritik önemde",
                        oncelik=3,
                        aksiyon="6 ayda bir detaylı bakım önerilir",
                    )
                )

        self._cache[cache_key] = recommendations
        self._cache_time[cache_key] = datetime.now(timezone.utc)
        return recommendations

    # =========================================================================
    # ŞOFÖR ÖNERİLERİ
    # =========================================================================

    async def get_driver_recommendations(self, sofor_id: int) -> List[Recommendation]:
        """Şoför için öneriler üret (Async)"""
        cache_key = f"sofor_{sofor_id}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        recommendations: list[Recommendation] = []
        from app.core.container import get_container

        try:
            deger_service = get_container().degerlendirme_service
            degerlendirme = await deger_service.evaluate_driver(sofor_id)

            if not degerlendirme:
                return recommendations

            ad = degerlendirme.ad_soyad
            puan = degerlendirme.genel_puan

            if puan < 50:
                recommendations.append(
                    Recommendation(
                        kategori="egitim",
                        hedef_tip="sofor",
                        hedef_id=sofor_id,
                        mesaj=f"{ad}: Performans puanı düşük ({puan}/100)",
                        oncelik=4,
                        aksiyon="Ekonomik sürüş eğitimi planlanmalı",
                    )
                )

            if degerlendirme.trend.value == "Kötüleşiyor":
                recommendations.append(
                    Recommendation(
                        kategori="verimlilik",
                        hedef_tip="sofor",
                        hedef_id=sofor_id,
                        mesaj=f"{ad}: Son dönemde verimlilik düşüşü (%{abs(degerlendirme.trend_degisim):.1f})",
                        oncelik=4,
                        aksiyon="Sefer geçmişi incelenmeli",
                    )
                )

            if degerlendirme.filo_karsilastirma < -10:
                recommendations.append(
                    Recommendation(
                        kategori="egitim",
                        hedef_tip="sofor",
                        hedef_id=sofor_id,
                        mesaj=f"{ad}: Filo ortalamasının %{abs(degerlendirme.filo_karsilastirma):.0f} altında",
                        oncelik=3,
                        aksiyon="Bireysel koçluk seansı önerilir",
                    )
                )

        except Exception as e:
            logger.error(f"Driver recommendation error: {e}")

        self._cache[cache_key] = recommendations
        self._cache_time[cache_key] = datetime.now(timezone.utc)
        return recommendations

    # =========================================================================
    # FİLO ÖNERİLERİ
    # =========================================================================

    async def get_fleet_recommendations(self) -> List[Recommendation]:
        """Filo geneli öneriler (Async)"""
        cache_key = "filo"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        recommendations: list[Recommendation] = []

        async with unit_of_work() as uow:
            # Filo ortalaması değişimi (PostgreSQL)
            bu_ay_sql = text(
                "SELECT AVG(tuketim) as ort FROM seferler WHERE tuketim IS NOT NULL AND tarih >= CURRENT_DATE - INTERVAL '30 days'"  # noqa: E501
            )
            gecen_ay_sql = text("""
                SELECT AVG(tuketim) as ort FROM seferler
                WHERE tuketim IS NOT NULL
                AND tarih >= CURRENT_DATE - INTERVAL '60 days'
                AND tarih < CURRENT_DATE - INTERVAL '30 days'
            """)

            bu_ay = (await uow.session.execute(bu_ay_sql)).fetchone()
            gecen_ay = (await uow.session.execute(gecen_ay_sql)).fetchone()

            if bu_ay and gecen_ay and bu_ay.ort and gecen_ay.ort:
                degisim = (
                    (float(bu_ay.ort) - float(gecen_ay.ort)) / float(gecen_ay.ort)
                ) * 100
                if degisim > 5:
                    recommendations.append(
                        Recommendation(
                            kategori="verimlilik",
                            hedef_tip="filo",
                            hedef_id=None,
                            mesaj=f"Filo tüketimi geçen aya göre %{degisim:.1f} arttı",
                            oncelik=4,
                            aksiyon="Genel bakım taraması yapılmalı",
                        )
                    )

            # En kötü performans (PostgreSQL)
            kotu_arac_sql = text("""
                SELECT a.plaka, AVG(s.tuketim) as ort
                FROM seferler s
                JOIN araclar a ON s.arac_id = a.id
                WHERE s.tuketim IS NOT NULL
                AND s.tarih >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY a.id, a.plaka
                ORDER BY ort DESC
                LIMIT 1
            """)
            kotu_arac = (await uow.session.execute(kotu_arac_sql)).fetchone()

            if kotu_arac and kotu_arac.ort > 40:
                recommendations.append(
                    Recommendation(
                        kategori="bakim",
                        hedef_tip="filo",
                        hedef_id=None,
                        mesaj=f"{kotu_arac.plaka}: En yüksek tüketim ({kotu_arac.ort:.1f} L/100km)",
                        oncelik=5,
                        aksiyon="Acil bakım gerekli",
                    )
                )

        self._cache[cache_key] = recommendations
        self._cache_time[cache_key] = datetime.now(timezone.utc)
        return recommendations

    # =========================================================================
    # MALİYET ÖNERİLERİ
    # =========================================================================

    async def get_cost_saving_suggestions(self) -> List[Recommendation]:
        """Maliyet tasarruf önerileri (Async)"""
        recommendations: list[Recommendation] = []

        async with unit_of_work() as uow:
            sql = text("""
                SELECT istasyon, AVG(fiyat_tl) as ort_fiyat
                FROM yakit_alimlari
                WHERE tarih >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY istasyon
                ORDER BY ort_fiyat DESC
            """)
            results = (await uow.session.execute(sql)).fetchall()

            if len(results) >= 2:
                pahali = results[0]
                ucuz = results[-1]
                fark = float(pahali.ort_fiyat) - float(ucuz.ort_fiyat)

                if fark > 1:
                    recommendations.append(
                        Recommendation(
                            kategori="maliyet",
                            hedef_tip="filo",
                            hedef_id=None,
                            mesaj=f"İstasyonlar arası fiyat farkı: {fark:.2f} TL/L ({ucuz.istasyon} en ucuz)",
                            oncelik=3,
                            aksiyon=f"{ucuz.istasyon} tercih edilmeli",
                        )
                    )

        return recommendations

    # =========================================================================
    # TÜM ÖNERİLER
    # =========================================================================

    async def get_all_recommendations(self) -> List[Recommendation]:
        """Tüm önerileri topla ve önceliğe göre sırala (Async & Parallel)"""
        import asyncio

        # Bağımsız önerileri paralel çek
        tasks = [self.get_fleet_recommendations(), self.get_cost_saving_suggestions()]

        results = await asyncio.gather(*tasks)

        # Faz 2: Araç ve şoför id'lerini çek; UoW'u hemen kapat.
        # Sub-tasks her biri kendi UoW açıyor — outer session'ı sub_tasks
        # gather boyunca açık tutmak pool connection'ı boşa atlatır.
        async with unit_of_work() as uow:
            araclar = await uow.arac_repo.get_all(limit=5)
            soforler = await uow.sofor_repo.get_all(limit=5)

        sub_tasks = []
        for a in araclar:
            sub_tasks.append(self.get_vehicle_recommendations(a["id"]))
        for s in soforler:
            sub_tasks.append(self.get_driver_recommendations(s["id"]))

        sub_results = await asyncio.gather(*sub_tasks)
        results.extend(sub_results)

        all_recs = []
        for res in results:
            all_recs.extend(res)

        all_recs.sort(key=lambda x: x.oncelik, reverse=True)
        return all_recs

    def clear_cache(self):
        """Tüm cache'i temizle."""
        self._cache.clear()
        self._cache_time.clear()

    def invalidate_vehicle_cache(self, arac_id: int) -> None:
        """Araç güncellendiğinde cache'i temizle (Thread-safe)."""
        with self._lock:  # SECURITY FIX: Lock eklendi
            cache_key = f"arac_{arac_id}"
            self._cache.pop(cache_key, None)
            self._cache_time.pop(cache_key, None)

    def invalidate_driver_cache(self, sofor_id: int) -> None:
        """Şoför güncellendiğinde cache'i temizle (Thread-safe)."""
        with self._lock:  # SECURITY FIX: Lock eklendi
            cache_key = f"sofor_{sofor_id}"
            self._cache.pop(cache_key, None)
            self._cache_time.pop(cache_key, None)

    def invalidate_fleet_cache(self) -> None:
        """Filo verisi değiştiğinde cache'i temizle (Thread-safe)."""
        with self._lock:  # SECURITY FIX: Lock eklendi
            self._cache.pop("filo", None)
            self._cache_time.pop("filo", None)


# Singleton
_recommendation_engine = None
_recommendation_engine_lock = threading.Lock()


def get_recommendation_engine() -> RecommendationEngine:
    global _recommendation_engine
    if _recommendation_engine is None:
        with _recommendation_engine_lock:
            if _recommendation_engine is None:  # Double-check locking
                _recommendation_engine = RecommendationEngine()
    return _recommendation_engine
