"""
TIR Yakıt Takip - Context Builder
AI için sistem verilerinden context hazırlama
"""

import asyncio
import os
import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    pass

from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ContextBuilder:
    """
    AI chatbot için context hazırlama.

    Sistem verilerini alıp AI'ya anlamlı bir format olarak sunar.
    """

    def __init__(self):
        pass

    @property
    def report_service(self):
        from app.core.services.report_service import get_report_service

        return get_report_service()

    @property
    def arac_repo(self):
        from app.database.repositories.arac_repo import get_arac_repo

        return get_arac_repo()

    @property
    def sefer_repo(self):
        from app.database.repositories.sefer_repo import get_sefer_repo

        return get_sefer_repo()

    @property
    def yakit_repo(self):
        from app.database.repositories.yakit_repo import get_yakit_repo

        return get_yakit_repo()

    @property
    def analiz_repo(self):
        from app.database.repositories.analiz_repo import get_analiz_repo

        return get_analiz_repo()

    @property
    def rag_engine(self):
        from app.core.ai.rag_engine import get_rag_engine

        return get_rag_engine()

    async def build_system_context(self) -> str:
        """Genel sistem durumu ve RAG özeti context'i (async)"""
        try:
            # Dashboard verileri
            stats_task = self.report_service.get_dashboard_summary()

            # RAG istatistikleri (thread'e al - sync call'u event loop'u bloklamasın)
            rag_stats_task = asyncio.to_thread(self.rag_engine.get_stats)

            stats, rag_stats = await asyncio.gather(stats_task, rag_stats_task)

            return f"""
## Sistem Durumu (Güncel)
- Aktif Araç: {stats.get("aktif_arac", 0)}
- Aktif Şoför: {stats.get("aktif_sofor", 0)}
- Toplam Sefer: {stats.get("toplam_sefer", 0)}
- Toplam KM: {stats.get("toplam_km", 0):,}
- Filo Ortalama Tüketim: {stats.get("filo_ortalama", 32.0):.1f} L/100km
- RAG Zekası: {rag_stats.get("total_documents", 0)} indekslenmiş kayıt
"""
        except Exception as e:
            logger.exception(f"Context build error: {e}")
            return "Sistem verilerine erişilemiyor."

    async def build_vehicle_context(self, arac_id: int) -> str:
        """Belirli araç için detaylı context (async)"""
        # SECURITY: Integer validation
        if not isinstance(arac_id, int) or arac_id <= 0:
            logger.warning(f"Invalid arac_id type or value: {type(arac_id).__name__}")
            return "Geçersiz araç ID."

        try:
            arac = await self.arac_repo.get_by_id(arac_id)
            if not arac:
                return "Araç bulunamadı."

            # Paralel veri çekme
            son_seferler_task = self.sefer_repo.get_all(arac_id=arac_id, limit=5)
            son_yakitlar_task = self.yakit_repo.get_all(arac_id=arac_id, limit=3)

            son_seferler, son_yakitlar = await asyncio.gather(
                son_seferler_task, son_yakitlar_task
            )

            # Araç istatistikleri
            from app.core.entities.models import Arac

            arac_pydantic = Arac(**arac)

            context = f"""
## Araç Bilgileri
- Plaka: {arac["plaka"]}
- Marka/Model: {arac["marka"]} {arac.get("model", "")}
- Yıl: {arac["yil"]} (Yaş: {arac_pydantic.yas} yıl)
- Euro Sınıfı: {arac_pydantic.euro_sinifi}
- Yaş Faktörü: {arac_pydantic.yas_faktoru:.2f}
- Tank Kapasitesi: {arac.get("tank_kapasitesi", 600)} L
- Hedef Tüketim: {arac.get("hedef_tuketim", 32.0):.1f} L/100km

## Son 5 Sefer
"""
            for s in son_seferler[:5]:
                tuketim = s.get("tuketim", "-")
                if tuketim and isinstance(tuketim, (int, float)):
                    tuketim = f"{tuketim:.1f} L/100km"
                context += f"- {s['tarih']}: {s['cikis_yeri']} → {s['varis_yeri']} ({s['mesafe_km']} km, {tuketim})\n"

            return context

        except Exception as e:
            logger.exception(f"Vehicle context error: {e}")
            return "Araç verilerine erişilemiyor."

    async def build_driver_context(self, sofor_id: int) -> str:
        """Belirli şoför için detaylı context (async)"""
        # SECURITY: Integer validation
        if not isinstance(sofor_id, int) or sofor_id <= 0:
            logger.warning(f"Invalid sofor_id type or value: {type(sofor_id).__name__}")
            return "Geçersiz şoför ID."

        try:
            from app.core.container import get_container

            service = get_container().degerlendirme_service
            degerlendirme = await service.evaluate_driver(sofor_id)

            if not degerlendirme:
                return "Şoför değerlendirmesi yapılamadı."

            context = f"""
## Şoför Performans Raporu
- Ad Soyad: {degerlendirme.ad_soyad}
- Genel Puan: {degerlendirme.genel_puan}/100 ({degerlendirme.derece.value} - {degerlendirme.yildiz}⭐)

### Alt Puanlar
- Verimlilik: {degerlendirme.verimlilik_puani}/100
- Tutarlılık: {degerlendirme.tutarlilik_puani}/100
- Deneyim: {degerlendirme.deneyim_puani}/100
- Trend: {degerlendirme.trend_puani}/100

### İstatistikler
- Toplam Sefer: {degerlendirme.toplam_sefer}
- Toplam KM: {degerlendirme.toplam_km:,}
- Ortalama Tüketim: {degerlendirme.ort_tuketim:.1f} L/100km
- Filo Karşılaştırma: {degerlendirme.filo_karsilastirma:+.1f}%
- Trend: {degerlendirme.trend.value}
"""

            if degerlendirme.guclu_yanlar:
                context += "\n### Güçlü Yanlar\n"
                for g in degerlendirme.guclu_yanlar:
                    context += f"✓ {g}\n"

            if degerlendirme.tavsiyeler:
                context += "\n### Tavsiyeler\n"
                for t in degerlendirme.tavsiyeler:
                    context += f"• {t}\n"

            return context

        except Exception as e:
            logger.exception(f"Driver context error: {e}")
            return "Şoför verilerine erişilemiyor."

    async def build_analysis_context(self) -> str:
        """Analiz ve raporlar için context (async)"""
        try:
            # Paralel veri çekme
            filo_ort_task = self.analiz_repo.get_filo_ortalama_tuketim()
            araclar_task = self.arac_repo.get_all(sadece_aktif=True)

            from app.core.container import get_container

            service = get_container().degerlendirme_service
            rankings_task = service.get_rankings()

            filo_ort, araclar, rankings = await asyncio.gather(
                filo_ort_task, araclar_task, rankings_task
            )

            filo_ort = filo_ort or 32.0

            context = f"""
## Filo Analizi
- Filo Ortalama Tüketimi: {filo_ort:.1f} L/100km
- Aktif Araç Sayısı: {len(araclar)}

### Performans Özeti
"""

            if rankings.get("genel"):
                context += "\n**En İyi 3 Şoför:**\n"
                for r in rankings["genel"][:3]:
                    context += (
                        f"{r['sira']}. {r['ad']} - {r['puan']}/100 ({r['derece']})\n"
                    )

            return context

        except Exception as e:
            logger.exception(f"Analysis context error: {e}")
            return "Analiz verilerine erişilemiyor."

    # Config (Safe Parse - ValueError önleme)
    try:
        MAX_CONTEXT_CHARS = int(os.getenv("AI_MAX_CONTEXT_CHARS", "8000"))
    except (ValueError, TypeError):
        MAX_CONTEXT_CHARS = 8000  # ~2000 token limit guard

    async def build_full_context(
        self,
        arac_id: Optional[int] = None,
        sofor_id: Optional[int] = None,
        include_analysis: bool = False,
    ) -> str:
        """Tam context oluştur (async & parallel)"""
        tasks = [self.build_system_context()]

        if arac_id:
            tasks.append(self.build_vehicle_context(arac_id))

        if sofor_id:
            tasks.append(self.build_driver_context(sofor_id))

        if include_analysis:
            tasks.append(self.build_analysis_context())

        parts = await asyncio.gather(*tasks)
        result = "\n".join(parts)

        # Guard: Context'i sınırla (token overflow önleme)
        if len(result) > self.MAX_CONTEXT_CHARS:
            result = (
                result[: self.MAX_CONTEXT_CHARS]
                + "\n[... Context sınırı aşıldı, kırpıldı ...]"
            )

        return result


# Singleton
_context_builder = None
_context_builder_lock = threading.Lock()


def get_context_builder() -> ContextBuilder:
    global _context_builder
    if _context_builder is None:
        with _context_builder_lock:
            if _context_builder is None:  # Double-check locking
                _context_builder = ContextBuilder()
    return _context_builder
