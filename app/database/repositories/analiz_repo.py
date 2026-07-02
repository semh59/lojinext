"""
TIR Yakıt Takip - Analiz Repository
ML eğitim verileri, dashboard istatistikleri, raporlama sorguları
"""

import json
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.sefer_status import SEFER_STATUS_TAMAMLANDI
from app.database.base_repository import BaseRepository
from app.database.models import Anomaly, Sefer, YakitFormul
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

# Configurable defaults
DEFAULT_FILO_ORTALAMA = 32.0


class AnalizRepository(BaseRepository[Sefer]):
    """Analiz ve istatistik veritabanı operasyonları (Async)"""

    # BaseRepository gereksinimi için default model (seferler üzerinden çok analiz yapılıyor)
    model = Sefer

    # =========================================================================
    # ML VERİLERİ
    # =========================================================================

    async def get_training_seferler(
        self, arac_id: int, limit: int = 200, offset: int = 0
    ) -> List[Dict]:
        """AI model eğitimi için sefer verilerini getir.

        [v2.1] FK join on guzergah_id — text-match join removed to avoid
        false positives and to stay consistent with get_for_training.
        """
        # Input validation
        limit = max(1, min(int(limit or 200), 1000))
        offset = max(0, int(offset or 0))
        query = """
            SELECT
                s.mesafe_km,
                s.net_kg / 1000.0 AS ton,
                s.tuketim,
                s.sofor_id,
                s.tarih,
                s.arac_id,
                COALESCE(s.ascent_m, l.ascent_m, 0.0) AS ascent_m,
                COALESCE(s.descent_m, l.descent_m, 0.0) AS descent_m,
                COALESCE(l.zorluk, 'Normal') AS zorluk,
                COALESCE(s.rota_detay, l.route_analysis) AS rota_detay,
                COALESCE(s.otoban_mesafe_km, l.otoban_mesafe_km, 0.0) AS otoban_mesafe_km,
                COALESCE(s.sehir_ici_mesafe_km, l.sehir_ici_mesafe_km, 0.0) AS sehir_ici_mesafe_km
            FROM seferler s
            LEFT JOIN lokasyonlar l ON s.guzergah_id = l.id
            WHERE s.arac_id = :arac_id
              AND s.tuketim IS NOT NULL
              AND s.tuketim > 0
              AND s.is_deleted = False
              AND s.durum = :completed_status
            ORDER BY s.tarih DESC
            LIMIT :limit OFFSET :offset
        """
        return await self.execute_query(
            query,
            {
                "arac_id": arac_id,
                "limit": limit,
                "offset": offset,
                "completed_status": SEFER_STATUS_TAMAMLANDI,
            },
        )

    async def save_model_params(self, arac_id: int, params: Dict[str, Any]):
        """AI model parametrelerini kaydet (Upsert - YakitFormul)"""
        session = self.session
        try:
            delete_stmt = delete(YakitFormul).where(YakitFormul.arac_id == arac_id)
            await session.execute(delete_stmt)

            insert_stmt = insert(YakitFormul).values(
                arac_id=arac_id,
                katsayilar=params,
                r2_score=params.get("r_squared", 0),
                sample_count=params.get("sample_count", 0),
                updated_at=datetime.now(timezone.utc),
            )
            await session.execute(insert_stmt)

            if self._session is None:
                await session.commit()
        except Exception as e:
            if self._session is None:
                await session.rollback()
            logger.error(f"Error saving model params: {e}")
            raise e

    async def get_model_params(self, arac_id: int) -> Optional[Dict]:
        """AI model parametrelerini getir"""
        session = self.session
        stmt = select(YakitFormul).where(YakitFormul.arac_id == arac_id)
        result = await session.execute(stmt)
        obj = result.scalar_one_or_none()

        if obj:
            katsayilar = obj.katsayilar
            if isinstance(katsayilar, str):
                katsayilar = json.loads(katsayilar)
            return {
                "coefficients": katsayilar.get("coefficients")
                if "coefficients" in katsayilar
                else katsayilar,
                "r_squared": obj.r2_score,
                "sample_count": obj.sample_count,
                "updated_at": obj.updated_at,
            }
        return None

    # =========================================================================
    # BULK ANALYTICS (N+1 SOLVER)
    # =========================================================================

    async def get_bulk_driver_metrics(self) -> List[Dict]:
        """
        Tüm şoförler için puanlama metriklerini TEK BİR sorgu ile getirir (PostgreSQL).
        """
        today = date.today()
        son_15_gun = today - timedelta(days=15)
        son_30_gun = today - timedelta(days=30)

        query = text("""
            SELECT
                s.sofor_id,
                sf.ad_soyad,
                COUNT(s.id) as toplam_sefer,
                COALESCE(SUM(s.mesafe_km), 0) as toplam_km,
                COALESCE(SUM(s.net_kg), 0) / 1000.0 as toplam_ton,
                COALESCE(AVG(s.tuketim), 0) as ort_tuketim,
                COALESCE(MIN(NULLIF(s.tuketim, 0)), 0) as en_iyi_tuketim,
                COALESCE(MAX(NULLIF(s.tuketim, 0)), 0) as en_kotu_tuketim,
                COALESCE(STDDEV(s.tuketim), 0) as std_sapma,
                COUNT(DISTINCT (s.cikis_yeri || ' -> ' || s.varis_yeri)) as guzergah_sayisi,
                AVG(s.tuketim) FILTER (WHERE s.tarih >= :son_15_gun AND s.tuketim > 0) as recent_avg,
                AVG(s.tuketim) FILTER (WHERE s.tarih < :son_15_gun AND s.tarih >= :son_30_gun AND s.tuketim > 0) as older_avg
            FROM seferler s
            JOIN soforler sf ON s.sofor_id = sf.id
            WHERE s.is_deleted = False
            GROUP BY s.sofor_id, sf.ad_soyad
        """)  # noqa: E501

        from app.infrastructure.security.pii_encryption import decrypt_pii_or

        session = self.session
        result = await session.execute(
            query, {"son_15_gun": son_15_gun, "son_30_gun": son_30_gun}
        )
        rows = [dict(row._mapping) for row in result.fetchall()]
        for row in rows:
            row["ad_soyad"] = decrypt_pii_or(row.get("ad_soyad"))
        return rows

    async def get_filo_ortalama_tuketim(
        self,
        baslangic: Optional[date] = None,
        bitis: Optional[date] = None,
    ) -> float:
        """Filo ortalama tuketimini (L/100km) getirir."""
        from sqlalchemy import text as sa_text

        params: Dict[str, Any] = {"default_avg": float(DEFAULT_FILO_ORTALAMA)}
        where_clauses = [
            "tuketim IS NOT NULL",
            "tuketim > 0",
            "is_deleted = FALSE",
        ]

        if baslangic:
            where_clauses.append("tarih >= :baslangic")
            params["baslangic"] = baslangic
        if bitis:
            where_clauses.append("tarih <= :bitis")
            params["bitis"] = bitis

        query = (
            f"SELECT COALESCE(AVG(tuketim), :default_avg) AS ort_tuketim "
            f"FROM seferler WHERE {' AND '.join(where_clauses)}"
        )

        session = self.session
        try:
            result = await session.execute(sa_text(query), params)
            avg_value = result.scalar_one_or_none()
            if avg_value is None:
                return float(DEFAULT_FILO_ORTALAMA)
            return round(float(avg_value), 2)
        except Exception:
            logger.error("Fleet average query failed, using default", exc_info=True)
            return float(DEFAULT_FILO_ORTALAMA)

    async def get_dashboard_stats(self, today_utc=None) -> Dict:
        """Genel dashboard istatistiklerini getir (AI Context için)"""
        if today_utc is None:
            today_utc = date.today()

        query = text("""
            SELECT
                (SELECT COUNT(*) FROM seferler WHERE is_deleted = False) AS toplam_sefer,
                (SELECT COALESCE(SUM(mesafe_km), 0) FROM seferler WHERE is_deleted = False) AS toplam_km,
                (SELECT COALESCE(SUM(litre), 0) FROM yakit_alimlari WHERE aktif = TRUE) AS toplam_yakit,
                (SELECT COALESCE(AVG(tuketim), :default_ortalama) FROM seferler
                    WHERE tuketim > 0 AND is_deleted = False) AS filo_ortalama,
                (SELECT COUNT(*) FROM araclar WHERE aktif = True AND is_deleted = False) AS aktif_arac,
                (SELECT COUNT(*) FROM araclar WHERE is_deleted = False) AS toplam_arac,
                (SELECT COUNT(*) FROM soforler WHERE aktif = True AND is_deleted = False) AS aktif_sofor,
                (SELECT COUNT(*) FROM seferler WHERE tarih = :bugun AND is_deleted = False) AS bugun_sefer
        """)

        _default = {
            "toplam_arac": 0,
            "toplam_sofor": 0,
            "filo_ortalama": float(DEFAULT_FILO_ORTALAMA),
            "toplam_yakit": 0,
        }

        session = self.session
        try:
            result = await session.execute(
                query,
                {"default_ortalama": float(DEFAULT_FILO_ORTALAMA), "bugun": today_utc},
            )
            row = result.fetchone()
            if row:
                # Pass through whatever keys the DB row contains.
                # Supports SQLAlchemy Row (_mapping) and SimpleNamespace.
                if hasattr(row, "_mapping"):
                    return dict(row._mapping)
                return {k: getattr(row, k, v) for k, v in _default.items()}
        except Exception:
            logger.error("Error getting dashboard stats", exc_info=True)

        return _default

    async def get_month_over_month_trends(
        self, today_utc: Optional[date] = None
    ) -> Dict[str, float]:
        """Bu ay vs önceki ayın sefer/km/tüketim için yüzdesel değişimi.

        Simetrik dönem karşılaştırması yapılır: bu ayın 1..N günü ile
        geçen ayın 1..N günü kıyaslanır (N = bugünün ayın günü). Bu sayede
        ayın yarısındaki kısmi veri tam aylık baseline ile karıştırılmaz.

        İptal seferleri trend hesabına alınmaz (`durum <> 'Cancelled'`).

        Returns: {"sefer": %, "km": %, "tuketim": %} (önceki dönem 0 ise 0 döner).
        """
        ref = today_utc or date.today()
        current_start = ref.replace(day=1)
        if current_start.month == 1:
            prev_start = current_start.replace(year=current_start.year - 1, month=12)
        else:
            prev_start = current_start.replace(month=current_start.month - 1)

        # Geçen ayın aynı günü (varsa). Ayın 31'inde geçen ay 30 gün ise
        # min(N, geçen_ay_gun_sayisi) — uç durumda aşağıdaki MAKE_DATE/LEAST ile.
        # Postgres'te LEAST(:ref_day, son_gun) ile clamp ediyoruz.
        prev_ref_day = ref.day

        # NOT: asyncpg + SQLAlchemy text() içinde `:name::date` syntax'ı
        # bazen bind parameter dönüştürmesini bozar. CAST(:name AS date)
        # tam taşınabilir alternatif.
        query = text(
            """
            WITH bounds AS (
                SELECT
                    CAST(:curr_start AS date)                    AS curr_start,
                    CAST(:ref AS date)                           AS curr_end,
                    CAST(:prev_start AS date)                    AS prev_start,
                    CAST(
                        CAST(:prev_start AS date)
                        + (LEAST(
                            CAST(:prev_ref_day AS int),
                            CAST(EXTRACT(DAY FROM (date_trunc('month', CAST(:prev_start AS date))
                                              + INTERVAL '1 month - 1 day')) AS int)
                          ) - 1) * INTERVAL '1 day'
                    AS date)                                     AS prev_end
            )
            SELECT
                COUNT(*) FILTER (WHERE s.tarih BETWEEN b.curr_start AND b.curr_end)
                    AS curr_sefer,
                COALESCE(SUM(s.mesafe_km) FILTER (
                    WHERE s.tarih BETWEEN b.curr_start AND b.curr_end), 0)
                    AS curr_km,
                COALESCE(AVG(s.tuketim) FILTER (
                    WHERE s.tarih BETWEEN b.curr_start AND b.curr_end AND s.tuketim > 0), 0)
                    AS curr_tuketim,
                COUNT(*) FILTER (
                    WHERE s.tarih BETWEEN b.prev_start AND b.prev_end)
                    AS prev_sefer,
                COALESCE(SUM(s.mesafe_km) FILTER (
                    WHERE s.tarih BETWEEN b.prev_start AND b.prev_end), 0)
                    AS prev_km,
                COALESCE(AVG(s.tuketim) FILTER (
                    WHERE s.tarih BETWEEN b.prev_start AND b.prev_end AND s.tuketim > 0), 0)
                    AS prev_tuketim
            FROM seferler s, bounds b
            WHERE s.is_deleted = FALSE
              AND s.durum <> 'Cancelled'
              AND s.tarih BETWEEN b.prev_start AND b.curr_end
            """
        )

        try:
            result = await self.session.execute(
                query,
                {
                    "curr_start": current_start,
                    "prev_start": prev_start,
                    "ref": ref,
                    "prev_ref_day": prev_ref_day,
                },
            )
            row = result.fetchone()
        except Exception:
            logger.error("Error computing month-over-month trends", exc_info=True)
            return {"sefer": 0.0, "km": 0.0, "tuketim": 0.0}

        if not row:
            return {"sefer": 0.0, "km": 0.0, "tuketim": 0.0}

        m = row._mapping

        def _delta(curr: float, prev: float) -> float:
            curr_f = float(curr or 0)
            prev_f = float(prev or 0)
            if prev_f == 0:
                return 0.0
            return round((curr_f - prev_f) / prev_f * 100.0, 2)

        return {
            "sefer": _delta(m["curr_sefer"], m["prev_sefer"]),
            "km": _delta(m["curr_km"], m["prev_km"]),
            "tuketim": _delta(m["curr_tuketim"], m["prev_tuketim"]),
        }

    async def get_all_vehicles_consumption_stats(self, days: int = 30) -> List[Dict]:
        """
        Tüm araçların dönem bazlı tüketim istatistiklerini tek sorguda getirir.
        Anomali tespiti ve dashboard widgetları için kullanılır.
        """
        days = max(1, min(int(days or 30), 365))
        start_date = date.today() - timedelta(days=days)
        half_days = days // 2
        half_period = date.today() - timedelta(days=half_days)

        query = text("""
            SELECT
                a.id AS arac_id,
                a.plaka,
                a.hedef_tuketim,
                COUNT(s.id) AS sefer_sayisi,
                COALESCE(AVG(s.tuketim), 0) AS ort_tuketim,
                COALESCE(AVG(s.tuketim) FILTER (
                    WHERE s.tarih >= :half_period AND s.tuketim > 0
                ), 0) AS son_15_gun_ort,
                COALESCE(AVG(s.tuketim) FILTER (
                    WHERE s.tarih < :half_period AND s.tarih >= :start_date AND s.tuketim > 0
                ), 0) AS onceki_15_gun_ort
            FROM araclar a
            LEFT JOIN seferler s
                ON a.id = s.arac_id
                AND s.tarih >= :start_date
                AND s.tuketim IS NOT NULL

                AND s.is_deleted = FALSE
            WHERE a.aktif = TRUE
            GROUP BY a.id, a.plaka, a.hedef_tuketim
            ORDER BY ort_tuketim DESC NULLS LAST
        """)

        session = self.session
        result = await session.execute(
            query, {"start_date": start_date, "half_period": half_period}
        )
        return [dict(row._mapping) for row in result.fetchall()]

    async def get_recent_unread_alerts(self, limit: int = 5) -> List[Dict]:
        """Son anomalileri getir (AI Context için - okunmamış konsepti yok, en yenileri döndür)"""
        query = text("""
            SELECT kaynak_tip as title, aciklama as message, severity, created_at
            FROM anomalies
            WHERE acknowledged_at IS NULL
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        session = self.session
        try:
            result = await session.execute(query, {"limit": limit})
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception:
            logger.error("Recent alerts query failed", exc_info=True)
            return []

    async def bulk_create_alerts(self, payloads: List[Dict[str, Any]]) -> int:
        """Sistem insight'larını alert deposuna (anomalies tablosu) toplu yazar.

        ``insight_engine.generate_all_and_save`` için yazma tarafı.
        ``anomalies`` sistemin alert deposudur (``get_recent_unread_alerts``
        oradan okur). Insight'lar numerik sapma içermediği için
        ``deger/beklenen_deger/sapma_yuzde`` 0.0 sentinel ile, ``tip='insight'``
        olarak yazılır; payload'un title+message'ı ``aciklama``da birleştirilir.
        Eklenen satır sayısını döner.
        """
        if not payloads:
            return 0

        session = self.session
        today = datetime.now(timezone.utc).date()
        rows = [
            {
                "tarih": today,
                "tip": "insight",
                "kaynak_tip": p.get("kaynak_tur") or "sistem",
                "kaynak_id": p.get("kaynak_id") or 0,
                "deger": 0.0,
                "beklenen_deger": 0.0,
                "sapma_yuzde": 0.0,
                "severity": p.get("severity") or "low",
                "aciklama": f"{p.get('title', '')}: {p.get('message', '')}".strip(": "),
            }
            for p in payloads
        ]
        try:
            await session.execute(insert(Anomaly), rows)
            if self._session is None:
                await session.commit()
            return len(rows)
        except Exception as e:
            if self._session is None:
                await session.rollback()
            logger.error(f"Error bulk-creating insight alerts: {e}")
            raise e

    async def bulk_create_anomalies(self, payloads: List[Dict[str, Any]]) -> int:
        """AnomalyDetector'ın heuristic/ML anomali sonuçlarını toplu yazar.

        ``AnomalyDetector.save_anomalies`` için yazma tarafı — ``bulk_create_alerts``'ın
        (insight satırları) aksine burada gerçek sayısal sapma (deger/beklenen_deger/
        sapma_yuzde) ve RCA alanları taşınır. Eklenen satır sayısını döner.
        """
        if not payloads:
            return 0
        try:
            await self.session.execute(insert(Anomaly), payloads)
            if self._session is None:
                await self.session.commit()
            return len(payloads)
        except Exception:
            if self._session is None:
                await self.session.rollback()
            raise

    async def get_anomalies_filtered(
        self,
        days: int,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        sofor_id: Optional[int] = None,
    ) -> List[Dict]:
        """Sürücü/araç adı zenginleştirilmiş, filtrelenmiş anomali listesi.

        ``AnomalyDetector.get_anomalies`` (T7 anomali eylem akışı) için tek
        sorgu — kaynak_tip='sefer'/'arac' ayrımına göre sofor/arac join'i.
        """
        sql = """
            SELECT
                a.*,
                sf.sofor_id as sofor_id,
                COALESCE(s.ad_soyad, 'Bilinmiyor') as sofor_adi,
                COALESCE(v.plaka, 'Bilinmiyor') as plaka
            FROM anomalies a
            LEFT JOIN seferler sf ON a.kaynak_tip = 'sefer' AND a.kaynak_id = sf.id
            LEFT JOIN soforler s ON sf.sofor_id = s.id
            LEFT JOIN araclar v ON (a.kaynak_tip = 'arac' AND a.kaynak_id = v.id) OR (a.kaynak_tip = 'sefer' AND sf.arac_id = v.id)
            WHERE a.tarih >= CURRENT_DATE - (:days || ' days')::interval
        """  # noqa: E501
        params: Dict[str, Any] = {"days": str(days)}

        if severity:
            sql += " AND a.severity = :sev"
            params["sev"] = severity

        if status == "open":
            sql += " AND a.acknowledged_at IS NULL AND a.resolved_at IS NULL"
        elif status == "acknowledged":
            sql += " AND a.acknowledged_at IS NOT NULL AND a.resolved_at IS NULL"
        elif status == "resolved":
            sql += " AND a.resolved_at IS NOT NULL"

        if sofor_id is not None:
            sql += " AND sf.sofor_id = :sofor_id"
            params["sofor_id"] = sofor_id

        sql += " ORDER BY a.tarih DESC"

        from app.infrastructure.security.pii_encryption import decrypt_pii_or

        result = await self.session.execute(text(sql), params)
        rows = [dict(row._mapping) for row in result.fetchall()]
        for row in rows:
            row["sofor_adi"] = decrypt_pii_or(row.get("sofor_adi"))
        return rows

    async def get_anomaly_by_id(self, anomaly_id: int) -> Optional[Anomaly]:
        """Tek anomali kaydını ORM nesnesi olarak getirir (acknowledge/resolve için)."""
        return await self.session.get(Anomaly, anomaly_id)

    async def update_anomaly(self, anomaly_id: int, **values: Any) -> None:
        """Anomali satırını verilen alanlarla günceller (acknowledge/resolve)."""
        await self.session.execute(
            update(Anomaly).where(Anomaly.id == anomaly_id).values(**values)
        )

    async def get_period_stats(self, start: date, end: date) -> Dict:
        """Dönem bazlı yakıt ve sefer özeti (ReportService için)"""
        query = text("""
            WITH s_stats AS (
                SELECT
                    COUNT(*) as toplam_sefer,
                    COALESCE(SUM(mesafe_km), 0) as toplam_km,
                    COALESCE(AVG(tuketim), 0) as ortalama_tuketim
                FROM seferler
                WHERE tarih >= :start AND tarih <= :end
                AND tuketim IS NOT NULL AND is_deleted = False
            ),
            f_stats AS (
                SELECT COALESCE(SUM(litre), 0) as toplam_yakit
                FROM yakit_alimlari
                WHERE tarih >= :start AND tarih <= :end AND aktif = TRUE
            )
            SELECT * FROM s_stats, f_stats
        """)
        session = self.session
        result = await session.execute(query, {"start": start, "end": end})
        row = result.fetchone()
        return dict(row._mapping) if row else {}

    async def get_vehicle_summary_stats(self, arac_id: int, start_date: date) -> Dict:
        """Araç performans özeti (ReportService için)"""
        query = text("""
            SELECT
                COUNT(*) as sefer_sayisi,
                COALESCE(SUM(mesafe_km), 0) as toplam_km,
                COALESCE(AVG(tuketim), 0) as ort_tuketim,
                COALESCE(MIN(tuketim), 0) as en_iyi,
                COALESCE(MAX(tuketim), 0) as en_kotu
            FROM seferler
            WHERE arac_id = :arac_id AND tarih >= :start_date AND is_deleted = False
            AND tuketim IS NOT NULL AND tuketim > 0
        """)
        session = self.session
        result = await session.execute(
            query, {"arac_id": arac_id, "start_date": start_date}
        )
        row = result.fetchone()
        return dict(row._mapping) if row else {}

    async def get_fleet_performance_stats(self, start_date: date) -> Dict:
        """Filo performans özeti (ReportService için).

        toplam_sefer + toplam_km tüm seferleri kapsar; tüketim ortalaması
        AVG NULL'ları otomatik atladığı için extra filter gereksiz —
        bu filter eski versiyonda COUNT'u kırıyordu (yakıt verisi olmayan
        seferler dashboard'da görünmüyordu).
        """
        query = text("""
            WITH stats AS (
                SELECT
                    COUNT(*) as toplam_sefer,
                    COALESCE(SUM(mesafe_km), 0) as toplam_km,
                    COALESCE(AVG(tuketim) FILTER (WHERE tuketim IS NOT NULL), 0)
                        as filo_ortalama
                FROM seferler
                WHERE tarih >= :start_date AND is_deleted = False
            ),
            cost AS (
                SELECT COALESCE(SUM(toplam_tutar), 0) as toplam_harcama
                FROM yakit_alimlari
                WHERE tarih >= :start_date AND aktif = TRUE
            )
            SELECT * FROM stats, cost
        """)
        session = self.session
        result = await session.execute(query, {"start_date": start_date})
        row = result.fetchone()
        return dict(row._mapping) if row else {}

    async def get_top_routes_by_vehicle(
        self, arac_id: int, start_date: date, limit: int = 5
    ) -> List[Dict]:
        """Araç için en çok gidilen güzergahlar (ReportService için)"""
        limit = max(1, min(int(limit or 5), 50))
        query = text("""
            SELECT
                cikis_yeri || ' → ' || varis_yeri as guzergah,
                COUNT(*) as sefer,
                AVG(tuketim) as tuketim
            FROM seferler
            WHERE arac_id = :arac_id AND tarih >= :start_date AND is_deleted = False
            AND tuketim IS NOT NULL
            GROUP BY cikis_yeri, varis_yeri
            ORDER BY sefer DESC
            LIMIT :limit
        """)
        session = self.session
        result = await session.execute(
            query, {"arac_id": arac_id, "start_date": start_date, "limit": limit}
        )
        return [dict(row._mapping) for row in result.fetchall()]

    # =========================================================================
    # RAW SQL REFACTORING METHODS (Servis katmanından taşındı)
    # =========================================================================

    async def get_daily_summary_for_ml(
        self, days: int = 60, arac_id: int = None
    ) -> List[Dict]:
        """
        ML modeli için günlük özet veriler (TimeSeriesService için).
        """
        days = max(1, min(int(days or 60), 730))
        start_date = date.today() - timedelta(days=days)

        if arac_id:
            query = text("""
                SELECT
                    tarih,
                    AVG(tuketim) as ort_tuketim,
                    SUM(mesafe_km) as toplam_km,
                    SUM(tuketim * mesafe_km / 100.0) as toplam_litre,
                    AVG(ton) as ort_ton,
                    COUNT(*) as sefer_sayisi
                FROM seferler
                WHERE arac_id = :arac_id
                  AND tarih >= :start_date
                  AND tuketim IS NOT NULL
                  AND is_deleted = False
                GROUP BY tarih
                ORDER BY tarih ASC
            """)
            params = {"arac_id": arac_id, "start_date": start_date}
        else:
            query = text("""
                SELECT
                    tarih,
                    AVG(tuketim) as ort_tuketim,
                    SUM(mesafe_km) as toplam_km,
                    SUM(tuketim * mesafe_km / 100.0) as toplam_litre,
                    AVG(ton) as ort_ton,
                    COUNT(*) as sefer_sayisi
                FROM seferler
                WHERE tarih >= :start_date
                  AND tuketim IS NOT NULL
                  AND is_deleted = False
                GROUP BY tarih
                ORDER BY tarih ASC
            """)
            params = {"start_date": start_date}

        session = self.session
        result = await session.execute(query, params)
        return [dict(row._mapping) for row in result.fetchall()]

    async def get_heatmap_data(self, days: int = 90) -> List[Dict]:
        """
        Heatmap için varış noktası yoğunluk verisi (ReportService için).
        """
        days = max(1, min(int(days or 90), 365))
        start_date = date.today() - timedelta(days=days)

        query = text("""
            SELECT varis_yeri, COUNT(*) as count, AVG(tuketim) as avg_consumption
            FROM seferler
            WHERE tarih >= :start_date AND is_deleted = False
            GROUP BY varis_yeri
            ORDER BY count DESC
        """)

        session = self.session
        result = await session.execute(query, {"start_date": start_date})
        return [dict(row._mapping) for row in result.fetchall()]

    async def get_driver_comparison(self, limit: int = 10) -> Dict:
        """
        Şoför karşılaştırma chart verisi (ReportService için).
        """
        limit = max(1, min(int(limit or 10), 100))
        query = text("""
            SELECT sf.ad_soyad, AVG(s.tuketim) as avg_consumption
            FROM seferler s
            JOIN soforler sf ON s.sofor_id = sf.id
            WHERE s.tuketim IS NOT NULL AND s.tuketim > 0 AND s.is_deleted = False
            GROUP BY sf.id
            ORDER BY avg_consumption ASC
            LIMIT :limit
        """)

        from app.infrastructure.security.pii_encryption import decrypt_pii_or

        session = self.session
        result = await session.execute(query, {"limit": limit})
        rows = result.fetchall()

        return {
            "categories": [decrypt_pii_or(r.ad_soyad) for r in rows],
            "values": [round(r.avg_consumption, 2) for r in rows],
        }

    async def get_daily_consumption_series(self, days: int = 30) -> List[Dict]:
        """
        Son X günün günlük toplam yakıt tüketim serisi.
        Grafikler için kullanılır.
        """
        days = max(1, min(int(days or 30), 365))
        start_date = date.today() - timedelta(days=days)

        query = text("""
            SELECT
                tarih as date,
                COALESCE(SUM(litre), 0) as value
            FROM yakit_alimlari
            WHERE tarih >= :start_date AND aktif = TRUE
            GROUP BY tarih
            ORDER BY tarih ASC
        """)

        session = self.session
        result = await session.execute(query, {"start_date": start_date})
        return [
            {
                "date": row.date.isoformat() if row.date else None,
                "value": float(row.value),
            }
            for row in result.fetchall()
        ]

    async def get_top_performing_vehicles(self, limit: int = 15) -> List[Dict]:
        """
        En iyi performans gösteren (düşük tüketimli) araçlar.
        """
        limit = max(1, min(int(limit or 15), 100))
        query = text("""
            SELECT
                a.plaka,
                AVG(s.tuketim) as avg_consumption,
                COUNT(s.id) as trip_count
            FROM araclar a
            JOIN seferler s ON a.id = s.arac_id
            WHERE s.tuketim > 0 AND s.is_deleted = False
            GROUP BY a.id, a.plaka
            HAVING COUNT(s.id) >= 3
            ORDER BY avg_consumption ASC
            LIMIT :limit
        """)

        session = self.session
        result = await session.execute(query, {"limit": limit})
        return [
            {
                "plaka": row.plaka,
                "avg_consumption": round(row.avg_consumption, 2),
                "trip_count": row.trip_count,
            }
            for row in result.fetchall()
        ]

    async def get_bulk_cost_stats(self, months: int = 12) -> List[Dict]:
        """
        Aylık maliyet istatistiklerini getir (PostgreSQL optimized).
        """
        months_int = int(months or 12)
        query = text("""
            WITH fuel_stats AS (
                SELECT
                    TO_CHAR(tarih, 'YYYY-MM') as ay,
                    SUM(toplam_tutar) as yakit_tl,
                    SUM(litre) as yakit_litre
                FROM yakit_alimlari
                WHERE tarih >= (CURRENT_DATE - (:months * INTERVAL '1 month'))
                    AND aktif = TRUE
                GROUP BY 1
            ),
            trip_stats AS (
                SELECT
                    TO_CHAR(tarih, 'YYYY-MM') as ay,
                    COUNT(*) as sefer_sayisi,
                    SUM(mesafe_km) as toplam_km
                FROM seferler
                WHERE tarih >= (CURRENT_DATE - (:months * INTERVAL '1 month')) AND is_deleted = False
                GROUP BY 1
            )
            SELECT
                COALESCE(f.ay, s.ay) as ay,
                COALESCE(f.yakit_tl, 0) as yakit_tl,
                COALESCE(f.yakit_litre, 0) as yakit_litre,
                COALESCE(s.sefer_sayisi, 0) as sefer_sayisi,
                COALESCE(s.toplam_km, 0) as toplam_km
            FROM fuel_stats f
            FULL OUTER JOIN trip_stats s ON f.ay = s.ay
            ORDER BY ay DESC
        """)

        session = self.session
        result = await session.execute(query, {"months": months_int})
        return [dict(row._mapping) for row in result.fetchall()]


_analiz_repo_lock = threading.Lock()
_analiz_repo: Optional[AnalizRepository] = None


def get_analiz_repo(session: Optional[AsyncSession] = None) -> AnalizRepository:
    """AnalizRepo Provider. Eğer session verilirse yeni instance döner (UoW için)."""
    global _analiz_repo
    if session:
        return AnalizRepository(session=session)
    with _analiz_repo_lock:
        if _analiz_repo is None:
            _analiz_repo = AnalizRepository()
    return _analiz_repo
