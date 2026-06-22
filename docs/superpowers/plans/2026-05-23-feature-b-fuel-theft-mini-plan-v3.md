# Feature B — Yakıt Hırsızlığı Tespit + Soruşturma (Mini-Plan v3 — Operasyonel)

> **Sürüm farkı:** v1 iskelet, v2 derin-orta (456 satır). **v3** her alt-görev için tam Python/SQL/TypeScript kodları, edge-case matrisi, contract örnekleri, observability, accessibility, performans benchmarkları. Direkt copy-paste'le uygulanabilir.

**Üst plan:** Faz 2 → Sprint 5 → Feature B (14-18 saat).

---

## 0. Operasyonel Bağlam

### 0.1 Mevcut altyapı + tam sözleşmeler

| Bileşen | Konum | Çağrı |
|---------|-------|-------|
| `Anomaly` model | `app/database/models.py:723` | `id, tarih, tip, kaynak_tip, kaynak_id, deger, beklenen_deger, sapma_yuzde, severity, aciklama, acknowledged_at, resolved_at` (T7 alanları) |
| `get_cost_leakage_stats(days)` | `app/database/repositories/sefer_repo.py:193` | `{route_deviation_km, fuel_gap_liters, total_leakage_cost, ...}` |
| `get_recent_anomalies(days, severity, status)` | `app/core/services/anomaly_detector.py:290` | `[{id, tip, kaynak_id, sapma_yuzde, severity, plaka, sofor_adi, ...}]` |
| `Kullanici` model | `app/database/models.py:607` | `id, email, rol_id, aktif` |
| Sefer JOIN | `seferler s` | `s.arac_id, s.sofor_id, s.guzergah_id` |
| Audit usage | locations.py:181 | `log_audit_event(module, action, entity_id, old_value, new_value, user_id)` |
| Telegram OPS config | `app/config.py:132` | `TELEGRAM_OPS_BOT_TOKEN`, `TELEGRAM_OPS_CHAT_ID` (ikisi de boş default) |
| Feature flag pattern | `app/config.py` | `COACHING_ENABLED: bool = True` (A modülünden) |

### 0.2 Data flow diyagramı

```
                          ┌──────────────────┐
                          │  Anomaly tablosu │
                          │  (mevcut, T7)    │
                          └────────┬─────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
       FuelTheftClassifier   _pattern_score      Sefer/Yakıt JOIN
       (B.1)                 (son 30g aynı       (kaynak_tip='sefer'
                              kaynak_id sayısı)   ise s.arac_id alınır)
              │
              ▼
       suspicion_score ∈ [0,1] + level (high/medium/low)
              │
       ┌──────┴───────┐
       │              │
       ▼              ▼
  INSERT FuelInv.   _broadcast_theft_alarm (B.5)
  status='open'     (level='high' + TELEGRAM_OPS_CHAT_ID set)
       │
       ▼
  Investigation flow (B.2):
   open ─assign▶ assigned ─start▶ investigating ─resolve▶ resolved ─close▶ closed
                                                  │
                                                  ├─resolution_type: real_theft
                                                  ├─resolution_type: false_alarm
                                                  ├─resolution_type: data_error
                                                  └─resolution_type: inconclusive
       │
       ▼
  Pattern detection (B.3):
  GROUP BY (sofor_id, arac_id) son 30g ≥3 inv → pattern listesi

  Frontend Kanban (B.4):
  5 sütun, status'a göre kart yerleştirme
  + PatternHeatmap tablosu
  + InvestigationDetailDialog (status değiştir, not yaz, evidence URL ekle)
```

### 0.3 Performans bütçesi + tasarım kararları

| İşlem | Hedef | Strateji |
|-------|-------|----------|
| Single classify | <100ms | `_pattern_score` tek SQL (count, indexed) |
| Bulk classify (50 anomali) | <3s | Pattern score cache (same kaynak_id sorgusu reused) |
| GET /investigations (50 kayıt) | <300ms | JOIN ile şoför/araç bilgisi tek round-trip |
| GET /patterns | <500ms | Single agg query, index'li |
| POST /classify trigger | <200ms | Classifier sync (LLM yok) |
| Telegram alarm | <2s | httpx 5s timeout, fire-forget retry yok |
| Daily pattern Celery task | <30s | Filo 200 şoför için |

### 0.4 Edge-case matrisi (B.1+B.2+B.5 birleşik)

| Edge case | Davranış | Test |
|-----------|----------|------|
| `anomaly.kaynak_tip != 'sefer'` | classify çalışır, pattern_score sadece kaynak_id'ye bakar | B.1 test 9 |
| `sapma_yuzde` NULL | sapma_norm=0 (factors'a "sapma yok" eklenir) | B.1 test 10 |
| `sapma_yuzde` negatif (lehte sapma) | `abs()` ile mutlak değer | B.1 test 7 |
| `severity` bilinmeyen string | SEVERITY_W default 0.1 | B.1 test 11 |
| Aynı `anomaly_id` POST iki kez (race) | DB unique constraint → 409 | B.2 test 2 |
| `assigned_to_user_id` geçersiz | FK SET NULL pattern → field NULL kalır | B.2 test 9 |
| `evidence_files` >10 öğe | Validation: max_items=10 | B.2 test 10 |
| Investigation `status='resolved'` → tekrar update | resolution_type yeniden set edilir, closed_at güncellenmez (immutable) | B.2 test 11 |
| Status="closed" iken PATCH gelir | 409 "kapatılmış soruşturma değiştirilemez" | B.2 test 12 |
| Classifier exception | suspicion_score=0, level='unknown', factors=["sınıflandırma başarısız"], log warning | B.1 test 6 |
| Telegram alarm Telegram down | audit `theft_alarm_failed`, akış devam eder | B.5 test 4 |
| `TELEGRAM_OPS_CHAT_ID` boş | Skip + warning log; classifier başarı | B.5 test 3 |
| Pattern count <3 | empty list, yine 200 | B.3 test 2 |
| Pattern query timeout | 500 + warning | B.3 test 3 |
| Frontend Kanban veri yok | "Henüz soruşturma yok" placeholder | B.4 test 1 |
| DetailDialog mutation network error | Toast kırmızı + form resetlenmez | B.4 test 5 |

### 0.5 Observability — metrikler

- `theft_classifier_runs_total` (Prometheus counter) — total classify çağrısı
- `theft_classifier_high_level_total` (counter) — high suspicion sayısı
- `theft_alarm_sent_total` (counter) — başarılı Telegram alarm
- `theft_alarm_failed_total` (counter) — Telegram başarısızlığı
- `investigations_by_status` (gauge) — Kanban için snapshot
- `investigations_resolution_distribution` (counter) — real_theft/false_alarm/...

MVP'de bu metrikler **opsiyonel** — `app/infrastructure/metrics/` paterni var ama scope dışı. Audit log her olayı zaten yakalar.

### 0.6 Yetki matrisi

| Endpoint | Permission | Sebep |
|----------|------------|-------|
| `POST /classify` | `sefer:write` | Admin; mevcut anomaly write yetkisi yeterli |
| `GET /investigations` | `sefer:read` | Mevcut read yetkisi |
| `POST /investigations` | `sefer:write` | Yeni soruşturma açma |
| `PATCH /investigations/{id}` | `sefer:write` | Status değişimi |
| `DELETE /investigations/{id}` | `sefer:write` | Soft delete (status='closed') |
| `GET /investigations/patterns` | `sefer:read` | Analitik görünüm |

Yeni permission key TANITILMAYACAK (gereksiz karmaşıklık); admin'in mevcut `sefer:write/read` izinleri yeterli.

### 0.7 Rollback stratejisi

```python
# app/config.py
THEFT_INVESTIGATION_ENABLED: bool = True
THEFT_ALARM_ENABLED: bool = True
```

`THEFT_INVESTIGATION_ENABLED=False`:
- Tüm `/admin/investigations/*` → 503
- Frontend AlertsPage'de "Soruşturmalar" sekmesi gizlenir (`?feature=investigations` server check)
- Mevcut Anomaly aksiyonları (T7) etkilenmez

`THEFT_ALARM_ENABLED=False`:
- Telegram broadcast skip, audit `theft_alarm_disabled`

Alembic downgrade (`0014`):
```sql
DROP TABLE fuel_investigations;  -- CASCADE FK
DROP INDEX ix_fuel_inv_*;
```

---

## B.1 — FuelTheftClassifier (3 saat, ~180 satır kod)

### Files
- Create: `app/core/ai/fuel_theft_classifier.py`
- Create: `app/schemas/investigation.py`
- Create: `app/tests/unit/test_fuel_theft_classifier.py`

### Tam Pydantic kod (`app/schemas/investigation.py`)

```python
"""Feature B — Yakıt Hırsızlığı Tespit + Soruşturma Pydantic şemaları."""
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SuspicionLevel = Literal["low", "medium", "high", "unknown"]
InvestigationStatus = Literal[
    "open", "assigned", "investigating", "resolved", "closed"
]
ResolutionType = Literal[
    "real_theft", "false_alarm", "data_error", "inconclusive"
]


class TheftClassification(BaseModel):
    """B.1 — Classifier çıktısı."""

    anomaly_id: int
    suspicion_score: float = Field(..., ge=0, le=1, description="0..1 normalize")
    suspicion_level: SuspicionLevel
    factors: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="İnsan-okur açıklama listesi",
    )
    suggested_action: str = Field(..., max_length=240)


class InvestigationCreate(BaseModel):
    anomaly_id: int = Field(..., gt=0)
    initial_notes: Optional[str] = Field(None, max_length=2000)


class InvestigationUpdate(BaseModel):
    """Tüm alanlar opsiyonel — partial update."""

    status: Optional[InvestigationStatus] = None
    assigned_to_user_id: Optional[int] = Field(None, gt=0)
    notes: Optional[str] = Field(None, max_length=4000)
    resolution_type: Optional[ResolutionType] = None
    evidence_files: Optional[List[str]] = Field(None, max_length=10)


class InvestigationResponse(BaseModel):
    id: int
    anomaly_id: int
    status: InvestigationStatus
    suspicion_score: Optional[float] = None
    suspicion_level: Optional[SuspicionLevel] = None
    assigned_to_user_id: Optional[int] = None
    notes: Optional[str] = None
    resolution_type: Optional[ResolutionType] = None
    evidence_files: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    # JOIN'den gelen meta (Optional çünkü kaynak_tip != 'sefer' olabilir)
    plaka: Optional[str] = None
    sofor_adi: Optional[str] = None
    sapma_yuzde: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class PatternMatch(BaseModel):
    sofor_id: Optional[int] = None
    sofor_adi: Optional[str] = None
    arac_id: Optional[int] = None
    plaka: Optional[str] = None
    occurrence_count: int = Field(..., ge=1)
    avg_suspicion_score: float = Field(..., ge=0, le=1)
    last_seen: datetime
```

### Tam classifier kod (`app/core/ai/fuel_theft_classifier.py`)

```python
"""Feature B.1 — Yakıt hırsızlığı şüphe sınıflandırıcısı (kural-bazlı).

LLM yok — saf kurallar. Skor bileşenleri:
  1. Sapma yüzdesi normalize (abs, sapma/50 clamp 0..1)  ağırlık 0.5
  2. Severity weight (low=0.1, medium=0.4, high=0.7, critical=1.0)  ağırlık 0.3
  3. Pattern score (aynı kaynak_id son 30g anomali sayısı)  ağırlık 0.2

Eşikler:
  >= 0.7 → high  → otomatik alarm + investigation auto-create
  >= 0.4 → medium → investigation manual review
  <  0.4 → low   → no investigation by default
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.database.unit_of_work import UnitOfWork
from app.schemas.investigation import (
    SuspicionLevel,
    TheftClassification,
)

logger = logging.getLogger(__name__)


SEVERITY_WEIGHT: Dict[str, float] = {
    "low": 0.1,
    "medium": 0.4,
    "high": 0.7,
    "critical": 1.0,
}

# Score ağırlıkları — toplamları 1.0
WEIGHT_SAPMA = 0.5
WEIGHT_SEVERITY = 0.3
WEIGHT_PATTERN = 0.2

# Pattern eşikleri
PATTERN_LOOKBACK_DAYS = 30
PATTERN_THRESHOLDS = [
    (3, 1.0),   # ≥3 olay → tam puan
    (2, 0.5),   # 2 olay → yarı puan
    (1, 0.0),   # tek olay → 0 (zaten classify ediliyor)
]


@dataclass
class _ScoreBreakdown:
    sapma_norm: float
    severity_w: float
    pattern_score: float
    pattern_count: int


class FuelTheftClassifier:
    """Stateless — kullanım: `get_fuel_theft_classifier()` singleton."""

    async def classify(self, anomaly: Dict[str, Any]) -> TheftClassification:
        """Tek anomali için suspicion classify.

        anomaly: get_recent_anomalies'in döndüğü dict (id, tip, kaynak_id,
                 kaynak_tip, sapma_yuzde, severity, plaka, sofor_adi).
        """
        try:
            breakdown = await self._compute_breakdown(anomaly)
            suspicion = (
                WEIGHT_SAPMA * breakdown.sapma_norm
                + WEIGHT_SEVERITY * breakdown.severity_w
                + WEIGHT_PATTERN * breakdown.pattern_score
            )
            suspicion = max(0.0, min(1.0, suspicion))
            level = self._to_level(suspicion)
            factors = self._explain(anomaly, breakdown)
            action = self._suggest_action(level, breakdown)

            return TheftClassification(
                anomaly_id=int(anomaly["id"]),
                suspicion_score=round(suspicion, 3),
                suspicion_level=level,
                factors=factors,
                suggested_action=action,
            )
        except Exception as exc:
            logger.warning(
                "Theft classify failed for anomaly %s: %s",
                anomaly.get("id"),
                exc,
            )
            return TheftClassification(
                anomaly_id=int(anomaly.get("id") or 0),
                suspicion_score=0.0,
                suspicion_level="unknown",
                factors=["Sınıflandırma başarısız (rule engine hatası)"],
                suggested_action="Manuel inceleme önerilir.",
            )

    async def classify_batch(
        self, anomalies: List[Dict[str, Any]]
    ) -> List[TheftClassification]:
        """Çoklu anomali için tek seferde — pattern cache reused."""
        # MVP: sıralı; küçük N (<200) için yeterli.
        results = []
        for a in anomalies:
            results.append(await self.classify(a))
        return results

    # ── İç hesap ──────────────────────────────────────────────────────────

    async def _compute_breakdown(
        self, anomaly: Dict[str, Any]
    ) -> _ScoreBreakdown:
        sapma_raw = anomaly.get("sapma_yuzde")
        sapma_norm = (
            min(1.0, abs(float(sapma_raw)) / 50.0) if sapma_raw is not None else 0.0
        )
        severity = str(anomaly.get("severity") or "low")
        severity_w = SEVERITY_WEIGHT.get(severity, 0.1)
        pattern_count = await self._pattern_count(
            int(anomaly["kaynak_id"]),
            str(anomaly.get("kaynak_tip") or ""),
        )
        pattern_score = self._pattern_to_score(pattern_count)
        return _ScoreBreakdown(
            sapma_norm=sapma_norm,
            severity_w=severity_w,
            pattern_score=pattern_score,
            pattern_count=pattern_count,
        )

    async def _pattern_count(self, kaynak_id: int, kaynak_tip: str) -> int:
        """Son 30 gün, aynı (kaynak_tip, kaynak_id) için anomali sayısı.

        Index'li sorgu — `idx_anomalies_*` mevcut (kaynak_id index'li).
        """
        if not kaynak_tip:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=PATTERN_LOOKBACK_DAYS)
        sql = text(
            """
            SELECT COUNT(*) FROM anomalies
            WHERE kaynak_id = :kid AND kaynak_tip = :ktip
              AND created_at >= :cutoff
            """
        )
        async with UnitOfWork() as uow:
            result = await uow.session.execute(
                sql, {"kid": kaynak_id, "ktip": kaynak_tip, "cutoff": cutoff}
            )
            return int(result.scalar() or 0)

    @staticmethod
    def _pattern_to_score(count: int) -> float:
        for threshold, score in PATTERN_THRESHOLDS:
            if count >= threshold:
                return score
        return 0.0

    @staticmethod
    def _to_level(score: float) -> SuspicionLevel:
        if score >= 0.7:
            return "high"
        if score >= 0.4:
            return "medium"
        return "low"

    @staticmethod
    def _explain(
        anomaly: Dict[str, Any], breakdown: _ScoreBreakdown
    ) -> List[str]:
        factors: List[str] = []
        sapma = anomaly.get("sapma_yuzde")
        if sapma is not None:
            factors.append(f"Sapma %{float(sapma):+.1f} (norm {breakdown.sapma_norm:.2f})")
        severity = anomaly.get("severity")
        if severity:
            factors.append(f"Severity={severity} (ağırlık {breakdown.severity_w:.2f})")
        if breakdown.pattern_count >= 2:
            factors.append(
                f"Tekrarlayan örüntü: son {PATTERN_LOOKBACK_DAYS}g "
                f"aynı kaynak için {breakdown.pattern_count} anomali"
            )
        elif breakdown.pattern_count == 1:
            factors.append("Tekil anomali (tekrar yok)")
        return factors

    @staticmethod
    def _suggest_action(
        level: SuspicionLevel, breakdown: _ScoreBreakdown
    ) -> str:
        if level == "high":
            return (
                "Yüksek şüphe: sefer/yakıt kayıtlarını incele, GPS güzergahını "
                "kontrol et, şoför ile yüz yüze görüş."
            )
        if level == "medium":
            return (
                "Orta şüphe: yakıt fişi + km sayaç tutarlılığını doğrula; "
                "tekrar görülürse soruşturma aç."
            )
        return (
            "Düşük şüphe: rutin loglama yeterli; ek aksiyon gerekmiyor."
        )


# Singleton
_classifier_singleton: Optional[FuelTheftClassifier] = None


def get_fuel_theft_classifier() -> FuelTheftClassifier:
    global _classifier_singleton
    if _classifier_singleton is None:
        _classifier_singleton = FuelTheftClassifier()
    return _classifier_singleton
```

### Unit testler — 11 senaryo (detaylı)

| # | Senaryo | Beklenti |
|---|---------|----------|
| 1 | low sapma (5) + low severity + 0 pattern | score~0.06, level='low' |
| 2 | high sapma (40) + critical severity + 3+ pattern | score~0.8+0.3+0.2=full, level='high' |
| 3 | sapma=80 (clamp) | sapma_norm=1.0 |
| 4 | severity bilinmeyen 'extreme' | weight=0.1 (default) |
| 5 | _pattern_to_score: count=3→1.0, 2→0.5, 0→0.0 | parametrize |
| 6 | classify exception (mock UoW kötü) | level='unknown', factors=["Sınıflandırma başarısız..."] |
| 7 | sapma_yuzde negatif (-25) | abs uygulanır, sapma_norm=0.5 |
| 8 | sapma_yuzde None | sapma_norm=0, factors'da yok |
| 9 | kaynak_tip='' | pattern_count=0 |
| 10 | _explain pattern_count=5 | factors'da "5 anomali" |
| 11 | _suggest_action her seviye için doğru metin | 3 ayrı assertion |

PII testi: classify'ın factors'unda plaka/isim regex yok.

### Acceptance
- 11/11 unit test
- ruff + mypy temiz
- `classify_batch(50)` <3s mock pattern_count ile

---

## B.2 — FuelInvestigation tablo + CRUD (3 saat, ~300 satır)

### Files
- Modify: `app/database/models.py` (FuelInvestigation)
- Create: `alembic/versions/0014_fuel_investigation.py`
- Create: `app/api/v1/endpoints/investigations.py`
- Modify: `app/api/v1/api.py`
- Modify: `app/config.py` (THEFT_INVESTIGATION_ENABLED)
- Create: `app/tests/integration/test_investigations_crud.py`

### Model (tam kod)

```python
class FuelInvestigation(Base):
    """Feature B.2 — yakıt hırsızlığı soruşturma akış kaydı.

    Bir anomaly için tek soruşturma olur (unique constraint).
    Status akışı: open → assigned → investigating → resolved → closed.
    resolution_type ENUM benzeri (string, frontend'de set):
        real_theft, false_alarm, data_error, inconclusive
    """

    __tablename__ = "fuel_investigations"
    __table_args__ = (
        Index("ix_fuel_inv_status", "status"),
        Index("ix_fuel_inv_assigned_to_user_id", "assigned_to_user_id"),
        Index("ix_fuel_inv_created_at", "created_at"),
        CheckConstraint(
            "status IN ('open','assigned','investigating','resolved','closed')",
            name="chk_fuel_inv_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    anomaly_id: Mapped[int] = mapped_column(
        ForeignKey("anomalies.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    suspicion_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    suspicion_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    evidence_files: Mapped[list] = mapped_column(
        JSONB, default=list, nullable=False, server_default="[]"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=False,
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), nullable=True
    )
```

### Alembic migration (tam upgrade/downgrade)

```python
"""fuel investigation (Feature B.2)

Revision ID: 0014_fuel_investigation
Revises: 0013_coaching_delivery
Create Date: 2026-05-23 10:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op


revision: str = "0014_fuel_investigation"
down_revision: Union[str, Sequence[str], None] = "0013_coaching_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fuel_investigations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "anomaly_id",
            sa.Integer,
            sa.ForeignKey("anomalies.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("suspicion_score", sa.Float, nullable=True),
        sa.Column("suspicion_level", sa.String(20), nullable=True),
        sa.Column(
            "assigned_to_user_id",
            sa.Integer,
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("resolution_type", sa.String(40), nullable=True),
        sa.Column(
            "evidence_files",
            JSONB,
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.Integer,
            sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('open','assigned','investigating','resolved','closed')",
            name="chk_fuel_inv_status",
        ),
    )
    op.create_index("ix_fuel_inv_status", "fuel_investigations", ["status"])
    op.create_index(
        "ix_fuel_inv_assigned_to_user_id",
        "fuel_investigations",
        ["assigned_to_user_id"],
    )
    op.create_index("ix_fuel_inv_created_at", "fuel_investigations", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_fuel_inv_created_at", table_name="fuel_investigations")
    op.drop_index("ix_fuel_inv_assigned_to_user_id", table_name="fuel_investigations")
    op.drop_index("ix_fuel_inv_status", table_name="fuel_investigations")
    op.drop_table("fuel_investigations")
```

### Endpoint kodu (tam, ~250 satır)

```python
"""Feature B.2 — Yakıt Hırsızlığı Soruşturmaları endpoint'leri.

Tüm endpoint'ler `THEFT_INVESTIGATION_ENABLED` flag'ine bakar; False ise 503.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text, update

from app.api.deps import SessionDep, require_permissions
from app.config import settings
from app.core.ai.fuel_theft_classifier import get_fuel_theft_classifier
from app.database.models import Anomaly, FuelInvestigation, Kullanici
from app.infrastructure.audit.audit_logger import log_audit_event
from app.schemas.investigation import (
    InvestigationCreate,
    InvestigationResponse,
    InvestigationUpdate,
    PatternMatch,
    TheftClassification,
)

router = APIRouter()


def _ensure_enabled() -> None:
    if not settings.THEFT_INVESTIGATION_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Hırsızlık soruşturma modülü devre dışı",
        )


# ── Liste + JOIN'li detay ───────────────────────────────────────────────


_LIST_SQL = """
    SELECT
        fi.*,
        a.sapma_yuzde,
        COALESCE(s.ad_soyad, NULL) AS sofor_adi,
        COALESCE(v.plaka, NULL) AS plaka
    FROM fuel_investigations fi
    JOIN anomalies a ON fi.anomaly_id = a.id
    LEFT JOIN seferler sf ON a.kaynak_tip = 'sefer' AND a.kaynak_id = sf.id
    LEFT JOIN soforler s ON sf.sofor_id = s.id
    LEFT JOIN araclar v ON (a.kaynak_tip = 'arac' AND a.kaynak_id = v.id)
                        OR (a.kaynak_tip = 'sefer' AND sf.arac_id = v.id)
    WHERE 1=1
"""


@router.get("", response_model=List[InvestigationResponse])
async def list_investigations(
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    status: Optional[str] = Query(
        None, pattern="^(open|assigned|investigating|resolved|closed)$"
    ),
    suspicion_level: Optional[str] = Query(
        None, pattern="^(low|medium|high|unknown)$"
    ),
    assigned_to_user_id: Optional[int] = Query(None, ge=1),
    days: int = Query(30, ge=1, le=180),
    limit: int = Query(100, ge=1, le=500),
):
    _ensure_enabled()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    sql = _LIST_SQL
    params: Dict[str, Any] = {"cutoff": cutoff, "limit": limit}
    sql += " AND fi.created_at >= :cutoff"
    if status:
        sql += " AND fi.status = :status"
        params["status"] = status
    if suspicion_level:
        sql += " AND fi.suspicion_level = :sl"
        params["sl"] = suspicion_level
    if assigned_to_user_id:
        sql += " AND fi.assigned_to_user_id = :assigned"
        params["assigned"] = assigned_to_user_id
    sql += " ORDER BY fi.created_at DESC LIMIT :limit"

    rows = (await db.execute(text(sql), params)).mappings().all()
    return [InvestigationResponse(**dict(r)) for r in rows]


@router.get("/{inv_id}", response_model=InvestigationResponse)
async def get_investigation(
    inv_id: int,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
):
    _ensure_enabled()
    sql = _LIST_SQL + " AND fi.id = :id LIMIT 1"
    row = (await db.execute(text(sql), {"cutoff": datetime(2000, 1, 1, tzinfo=timezone.utc), "id": inv_id, "limit": 1})).mappings().one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
    return InvestigationResponse(**dict(row))


# ── POST: yeni soruşturma + auto-classify ───────────────────────────────


@router.post("", response_model=InvestigationResponse, status_code=201)
async def create_investigation(
    payload: InvestigationCreate,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
):
    _ensure_enabled()
    # 1. Anomaly var mı?
    anomaly = await db.get(Anomaly, payload.anomaly_id)
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomali bulunamadı")
    # 2. Mevcut investigation var mı? (unique constraint da yakalar ama erken 409)
    exist = (
        await db.execute(
            select(FuelInvestigation).where(FuelInvestigation.anomaly_id == payload.anomaly_id)
        )
    ).scalar_one_or_none()
    if exist:
        raise HTTPException(status_code=409, detail="Bu anomali için soruşturma zaten var")

    # 3. Classify et
    classifier = get_fuel_theft_classifier()
    classification = await classifier.classify(
        {
            "id": anomaly.id,
            "tip": anomaly.tip,
            "kaynak_id": anomaly.kaynak_id,
            "kaynak_tip": anomaly.kaynak_tip,
            "sapma_yuzde": anomaly.sapma_yuzde,
            "severity": anomaly.severity,
        }
    )

    # 4. Insert
    creator_id = current_admin.id if current_admin.id and current_admin.id > 0 else None
    inv = FuelInvestigation(
        anomaly_id=payload.anomaly_id,
        status="open",
        suspicion_score=classification.suspicion_score,
        suspicion_level=classification.suspicion_level,
        notes=payload.initial_notes,
        created_by_user_id=creator_id,
        evidence_files=[],
    )
    db.add(inv)
    await db.flush()
    await db.refresh(inv)
    await db.commit()

    await log_audit_event(
        module="theft",
        action="investigation_created",
        entity_id=str(inv.id),
        new_value={
            "anomaly_id": payload.anomaly_id,
            "suspicion_level": classification.suspicion_level,
            "suspicion_score": classification.suspicion_score,
        },
        user_id=current_admin.id,
    )

    # 5. High suspicion → alarm (B.5)
    if classification.suspicion_level == "high" and settings.THEFT_ALARM_ENABLED:
        from app.core.ai.fuel_theft_classifier import _broadcast_theft_alarm  # B.5

        await _broadcast_theft_alarm(
            inv_id=inv.id, classification=classification, anomaly=anomaly
        )

    # Re-fetch with JOIN
    return await get_investigation(inv.id, db, current_admin)


# ── PATCH: güncelle ─────────────────────────────────────────────────────


_TERMINAL_STATUSES = {"closed"}


@router.patch("/{inv_id}", response_model=InvestigationResponse)
async def update_investigation(
    inv_id: int,
    payload: InvestigationUpdate,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
):
    _ensure_enabled()
    inv = await db.get(FuelInvestigation, inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
    if inv.status in _TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="Kapatılmış soruşturma değiştirilemez",
        )

    old_value = {"status": inv.status, "assigned_to_user_id": inv.assigned_to_user_id}
    values: Dict[str, Any] = {}
    if payload.status is not None:
        values["status"] = payload.status
        if payload.status == "resolved":
            values["closed_at"] = datetime.now(timezone.utc)
    if payload.assigned_to_user_id is not None:
        values["assigned_to_user_id"] = payload.assigned_to_user_id
        # assignment varsa status='assigned' (henüz open ise)
        if inv.status == "open" and "status" not in values:
            values["status"] = "assigned"
    if payload.notes is not None:
        values["notes"] = payload.notes
    if payload.resolution_type is not None:
        values["resolution_type"] = payload.resolution_type
        # resolution set olunca otomatik resolved + closed_at
        if "status" not in values:
            values["status"] = "resolved"
            values["closed_at"] = datetime.now(timezone.utc)
    if payload.evidence_files is not None:
        values["evidence_files"] = payload.evidence_files

    if not values:
        return await get_investigation(inv_id, db, current_admin)

    await db.execute(
        update(FuelInvestigation).where(FuelInvestigation.id == inv_id).values(**values)
    )
    await db.commit()

    await log_audit_event(
        module="theft",
        action="investigation_updated",
        entity_id=str(inv_id),
        old_value=old_value,
        new_value=values,
        user_id=current_admin.id,
    )
    return await get_investigation(inv_id, db, current_admin)


# ── DELETE: soft (status='closed') ──────────────────────────────────────


@router.delete("/{inv_id}", status_code=204)
async def soft_delete_investigation(
    inv_id: int,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
):
    _ensure_enabled()
    inv = await db.get(FuelInvestigation, inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
    if inv.status == "closed":
        return  # idempotent

    await db.execute(
        update(FuelInvestigation)
        .where(FuelInvestigation.id == inv_id)
        .values(status="closed", closed_at=datetime.now(timezone.utc))
    )
    await db.commit()
    await log_audit_event(
        module="theft",
        action="investigation_closed",
        entity_id=str(inv_id),
        user_id=current_admin.id,
    )


# ── POST /{id}/classify: re-run classifier ──────────────────────────────


@router.post("/{inv_id}/classify", response_model=TheftClassification)
async def reclassify_investigation(
    inv_id: int,
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:write"))],
):
    _ensure_enabled()
    inv = await db.get(FuelInvestigation, inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Soruşturma bulunamadı")
    anomaly = await db.get(Anomaly, inv.anomaly_id)
    if not anomaly:
        raise HTTPException(status_code=404, detail="İlişkili anomali bulunamadı")

    classification = await get_fuel_theft_classifier().classify(
        {
            "id": anomaly.id,
            "tip": anomaly.tip,
            "kaynak_id": anomaly.kaynak_id,
            "kaynak_tip": anomaly.kaynak_tip,
            "sapma_yuzde": anomaly.sapma_yuzde,
            "severity": anomaly.severity,
        }
    )
    await db.execute(
        update(FuelInvestigation)
        .where(FuelInvestigation.id == inv_id)
        .values(
            suspicion_score=classification.suspicion_score,
            suspicion_level=classification.suspicion_level,
        )
    )
    await db.commit()
    return classification


# ── GET /patterns ───────────────────────────────────────────────────────


_PATTERN_SQL = """
    WITH inv_data AS (
        SELECT
            fi.suspicion_score,
            fi.created_at,
            COALESCE(sf.sofor_id, NULL) AS sofor_id,
            COALESCE(sf.arac_id, NULL) AS arac_id,
            COALESCE(s.ad_soyad, NULL) AS sofor_adi,
            COALESCE(v.plaka, NULL) AS plaka
        FROM fuel_investigations fi
        JOIN anomalies a ON fi.anomaly_id = a.id
        LEFT JOIN seferler sf ON a.kaynak_tip = 'sefer' AND a.kaynak_id = sf.id
        LEFT JOIN soforler s ON sf.sofor_id = s.id
        LEFT JOIN araclar v ON (a.kaynak_tip = 'arac' AND a.kaynak_id = v.id)
                            OR (a.kaynak_tip = 'sefer' AND sf.arac_id = v.id)
        WHERE fi.created_at >= :cutoff
          AND fi.suspicion_score IS NOT NULL
    )
    SELECT
        sofor_id, sofor_adi, arac_id, plaka,
        COUNT(*)::int AS occurrence_count,
        AVG(suspicion_score)::float AS avg_suspicion_score,
        MAX(created_at) AS last_seen
    FROM inv_data
    WHERE sofor_id IS NOT NULL OR arac_id IS NOT NULL
    GROUP BY sofor_id, sofor_adi, arac_id, plaka
    HAVING COUNT(*) >= :min_count
    ORDER BY avg_suspicion_score DESC NULLS LAST
    LIMIT :limit
"""


@router.get("/patterns", response_model=List[PatternMatch])
async def get_patterns(
    db: SessionDep,
    current_admin: Annotated[Kullanici, Depends(require_permissions("sefer:read"))],
    days: int = Query(30, ge=7, le=180),
    min_count: int = Query(2, ge=1, le=10),
    limit: int = Query(50, ge=1, le=200),
):
    _ensure_enabled()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        await db.execute(
            text(_PATTERN_SQL),
            {"cutoff": cutoff, "min_count": min_count, "limit": limit},
        )
    ).mappings().all()
    return [PatternMatch(**dict(r)) for r in rows]
```

### Integration testler — 12 senaryo

| # | Senaryo | HTTP / DB beklenti |
|---|---------|-------------------|
| 1 | POST → 201 | id, status='open', suspicion_score>0 |
| 2 | POST anomaly_id duplicate | 409 |
| 3 | POST unknown anomaly_id | 404 |
| 4 | GET list, no filter | 200 + [N] |
| 5 | GET filter status=open | sadece open'lar |
| 6 | GET single by id | 200 + plaka/sofor_adi JOIN |
| 7 | GET 404 unknown | 404 |
| 8 | PATCH status='assigned' + assigned_to_user_id | status değişir, audit kayıt |
| 9 | PATCH assigned_to_user_id=999999 (geçersiz) | FK ignore SET NULL OR 200 + null |
| 10 | PATCH resolution_type='real_theft' | status auto='resolved' + closed_at dolar |
| 11 | PATCH evidence_files 11 öğe | 422 max_length=10 |
| 12 | PATCH after status='closed' | 409 |
| 13 | DELETE → 204 | status='closed' DB'de |
| 14 | DELETE idempotent (zaten closed) | 204 |
| 15 | POST /classify | classification döner + suspicion_* DB güncellenir |
| 16 | THEFT_INVESTIGATION_ENABLED=False | tüm endpoint 503 |

### Acceptance
- 16/16 integration test
- alembic head: 0014_fuel_investigation
- audit_log entries her POST/PATCH/DELETE'ta

---

## B.3 — Pattern detection (2 saat)

Kapsam B.2'nin `/patterns` endpoint'inde zaten karşılandı. Ek olarak:

### Files
- Create: `app/workers/tasks/theft_tasks.py`
- Modify: `app/infrastructure/background/celery_app.py` (beat 03:00 UTC)

### Celery task

```python
"""Feature B.3 — günlük pattern tarama (yalnız logger)."""

@celery_app.task(
    bind=True,
    name="theft.daily_pattern_scan",
    max_retries=1,
)
def daily_pattern_scan(self):  # noqa: ARG001
    """Her sabah 03:00 UTC çalışır, log'a yüksek occurrence pattern'leri yazar."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        from sqlalchemy import text
        from app.database.unit_of_work import UnitOfWork

        async with UnitOfWork() as uow:
            rows = (await uow.session.execute(
                text(_PATTERN_SQL),
                {"cutoff": ..., "min_count": 3, "limit": 100},
            )).mappings().all()
            for r in rows:
                logger.warning(
                    "THEFT_PATTERN sofor=%s plaka=%s count=%s avg_score=%.2f",
                    r["sofor_adi"], r["plaka"], r["occurrence_count"], r["avg_suspicion_score"],
                )
            return {"count": len(rows)}
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()
```

### Beat schedule entry
```python
"theft-pattern-scan-daily": {
    "task": "theft.daily_pattern_scan",
    "schedule": crontab(hour=3, minute=0),
},
```

### Acceptance
- `celery_app.tasks["theft.daily_pattern_scan"]` mevcut
- Beat schedule key kayıtlı

---

## B.4 — Frontend (4 saat, ~600 satır)

### Files
- Modify: `frontend/src/components/alerts/SeverityFilter.tsx` (AlertTab union'a 'investigations' ekle)
- Create: `frontend/src/components/alerts/InvestigationsKanban.tsx`
- Create: `frontend/src/components/alerts/InvestigationCard.tsx`
- Create: `frontend/src/components/alerts/InvestigationDetailDialog.tsx`
- Create: `frontend/src/components/alerts/PatternList.tsx`
- Create: `frontend/src/services/api/investigation-service.ts`
- Create: `frontend/src/resources/tr/investigations.ts`
- Modify: `frontend/src/pages/AlertsPage.tsx` (yeni tab render)
- Tests: 6 vitest

### Service (tam TypeScript)

```typescript
import axiosInstance from './axios-instance'

export type SuspicionLevel = 'low' | 'medium' | 'high' | 'unknown'
export type InvestigationStatus = 'open' | 'assigned' | 'investigating' | 'resolved' | 'closed'
export type ResolutionType = 'real_theft' | 'false_alarm' | 'data_error' | 'inconclusive'

export interface Investigation {
    id: number
    anomaly_id: number
    status: InvestigationStatus
    suspicion_score: number | null
    suspicion_level: SuspicionLevel | null
    assigned_to_user_id: number | null
    notes: string | null
    resolution_type: ResolutionType | null
    evidence_files: string[]
    created_at: string
    updated_at: string
    closed_at: string | null
    plaka: string | null
    sofor_adi: string | null
    sapma_yuzde: number | null
}

export interface PatternMatch {
    sofor_id: number | null
    sofor_adi: string | null
    arac_id: number | null
    plaka: string | null
    occurrence_count: number
    avg_suspicion_score: number
    last_seen: string
}

export interface InvestigationUpdatePayload {
    status?: InvestigationStatus
    assigned_to_user_id?: number
    notes?: string
    resolution_type?: ResolutionType
    evidence_files?: string[]
}

export const investigationService = {
    list: async (params: {
        status?: InvestigationStatus
        suspicion_level?: SuspicionLevel
        days?: number
        limit?: number
    } = {}): Promise<Investigation[]> => {
        const r = await axiosInstance.get<Investigation[]>('/admin/investigations', { params })
        return r.data
    },

    get: async (id: number): Promise<Investigation> => {
        const r = await axiosInstance.get<Investigation>(`/admin/investigations/${id}`)
        return r.data
    },

    create: async (anomalyId: number, initialNotes?: string): Promise<Investigation> => {
        const r = await axiosInstance.post<Investigation>('/admin/investigations', {
            anomaly_id: anomalyId,
            initial_notes: initialNotes,
        })
        return r.data
    },

    update: async (id: number, payload: InvestigationUpdatePayload): Promise<Investigation> => {
        const r = await axiosInstance.patch<Investigation>(`/admin/investigations/${id}`, payload)
        return r.data
    },

    close: async (id: number): Promise<void> => {
        await axiosInstance.delete(`/admin/investigations/${id}`)
    },

    classify: async (id: number) => {
        const r = await axiosInstance.post(`/admin/investigations/${id}/classify`)
        return r.data
    },

    getPatterns: async (params: { days?: number; min_count?: number } = {}): Promise<PatternMatch[]> => {
        const r = await axiosInstance.get<PatternMatch[]>('/admin/investigations/patterns', { params })
        return r.data
    },
}
```

### Kanban ASCII düzeni

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Soruşturmalar                                                              │
│                                                                            │
│ ┌─Açık (4)─┐ ┌─Atandı (2)─┐ ┌─Soruşturuluyor (3)─┐ ┌─Çözüldü (8)─┐         │
│ │┌────────┐│ │┌──────────┐│ │┌──────────────────┐│ │┌────────────┐│         │
│ ││High    ││ ││Med       ││ ││High              ││ ││Real theft  ││         │
│ ││34 ABC  ││ ││07 XYZ    ││ ││34 DEF            ││ ││34 ABC      ││         │
│ ││+45%    ││ ││+25%      ││ ││+50%              ││ ││+60%        ││         │
│ ││Ali V.  ││ ││Ahmet K.  ││ ││Mehmet Y.         ││ ││Ali V.      ││         │
│ │└────────┘│ │└──────────┘│ │└──────────────────┘│ │└────────────┘│         │
│ │┌────────┐│ │            │ │┌──────────────────┐│ │┌────────────┐│         │
│ ││Med     ││ │            │ ││Med               ││ ││False alarm ││         │
│ │└────────┘│ │            │ │└──────────────────┘│ │└────────────┘│         │
│ └──────────┘ └────────────┘ └────────────────────┘ └──────────────┘         │
│                                                                            │
│ ┌─Pattern Tablosu (son 30g)─────────────────────────────────────────────┐  │
│ │ Şoför        │ Plaka     │ Olay │ Ort. Skor │ Son                    │  │
│ │ Ali Veli     │ 34 ABC    │ 5    │ 0.78      │ 22.05.2026             │  │
│ │ Mehmet Y.    │ 34 DEF    │ 3    │ 0.65      │ 18.05.2026             │  │
│ └──────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────┘
```

### InvestigationCard prop interface + render kuralları

```typescript
interface InvestigationCardProps {
    investigation: Investigation
    onClick: () => void
}

// Render:
// - Top: Suspicion badge (high=danger/red, medium=warning/orange, low=secondary/gray)
// - Title: plaka + sofor_adi
// - sapma_yuzde: +/-NN.N%
// - Footer: created_at relative ("2 saat önce")
// - Hover: subtle shadow + cursor-pointer
```

### DetailDialog UX akış

```
[Modal açılır]
┌────────────────────────────────────┐
│ Soruşturma #123          [X kapat] │
│ ────────────────────────────────── │
│ Anomali: #45 — Sapma: +45%         │
│ Şüphe: High (0.85)                 │
│                                    │
│ Status:    [open ▼]    Atandı:    │
│            [Ali V. ▼]              │
│                                    │
│ Çözüm tipi (opsiyonel):            │
│   [○ Gerçek hırsızlık]             │
│   [○ Sahte alarm]                  │
│   [○ Veri hatası]                  │
│   [○ Belirsiz]                     │
│                                    │
│ Notlar:                            │
│ ┌────────────────────────────────┐ │
│ │ Yakıt fişi eksikti...          │ │
│ └────────────────────────────────┘ │
│                                    │
│ Kanıt (URL listesi):               │
│ • /uploads/2026/foto1.jpg          │
│ • /uploads/2026/foto2.jpg          │
│ [+ Yeni URL]                       │
│                                    │
│ [İptal]              [Kaydet]      │
└────────────────────────────────────┘
```

Mutation onSuccess: invalidate `['investigations', 'list']`. Eğer resolution_type set ise modal otomatik kapanır.

### Vitest senaryoları (6)

1. Kanban 5 sütun + her sütunda boş state
2. Investigation card render (high → red badge, plaka, sofor_adi)
3. Card click → DetailDialog açılır
4. Status dropdown değişimi → mutation çağrı parametresi
5. resolution_type seçimi → save → mutation + close
6. Pattern table 3+ row → satırlar render edilir

---

## B.5 — Telegram alarm (2 saat)

### Files
- Modify: `app/core/ai/fuel_theft_classifier.py` (`_broadcast_theft_alarm` helper)
- Modify: `app/api/v1/endpoints/investigations.py` (zaten POST içinde çağrılıyor)
- Modify: `app/config.py` (`THEFT_ALARM_ENABLED`)
- Create: `app/tests/integration/test_theft_alarm.py`

### Broadcast helper (HTML escape ile)

```python
async def _broadcast_theft_alarm(
    inv_id: int,
    classification: TheftClassification,
    anomaly: Any,  # ORM nesne
) -> None:
    """High suspicion oluşunca admin grup'una Telegram bildirimi."""
    if not settings.THEFT_ALARM_ENABLED:
        return
    bot_token = settings.TELEGRAM_OPS_BOT_TOKEN or settings.TELEGRAM_DRIVER_BOT_TOKEN
    chat_id = settings.TELEGRAM_OPS_CHAT_ID
    if not (bot_token and chat_id):
        logger.warning("Theft alarm skipped: TELEGRAM_OPS_CHAT_ID empty")
        return

    # JOIN ile plaka/şoför çek (PII, sadece admin)
    # MVP: zaten anomaly_id var, basit get
    sapma = float(anomaly.sapma_yuzde or 0)
    plaka = "—"
    sofor = "—"
    try:
        async with UnitOfWork() as uow:
            sql = text(
                """
                SELECT v.plaka, s.ad_soyad
                FROM anomalies a
                LEFT JOIN seferler sf ON a.kaynak_tip='sefer' AND a.kaynak_id=sf.id
                LEFT JOIN soforler s ON sf.sofor_id=s.id
                LEFT JOIN araclar v ON (a.kaynak_tip='arac' AND a.kaynak_id=v.id)
                                    OR (a.kaynak_tip='sefer' AND sf.arac_id=v.id)
                WHERE a.id = :aid
                """
            )
            row = (await uow.session.execute(sql, {"aid": anomaly.id})).mappings().one_or_none()
            if row:
                plaka = row.get("plaka") or "—"
                sofor = row.get("ad_soyad") or "—"
    except Exception:
        pass

    safe_plaka = html.escape(plaka)
    safe_sofor = html.escape(sofor)
    body = (
        f"🚨 <b>Yüksek Şüpheli Yakıt Anomalisi</b>\n\n"
        f"🚛 <b>Plaka</b>: {safe_plaka}\n"
        f"👤 <b>Şoför</b>: {safe_sofor}\n"
        f"📉 <b>Sapma</b>: {sapma:+.1f}%\n"
        f"🎯 <b>Şüphe</b>: {classification.suspicion_score:.2f} (high)\n\n"
        f"🔗 Soruşturma #{inv_id}"
    )

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": body, "parse_mode": "HTML"},
            )
            resp.raise_for_status()
        await log_audit_event(
            module="theft",
            action="theft_alarm_sent",
            entity_id=str(inv_id),
            new_value={"chat_id": chat_id[:8] + "***", "suspicion_score": classification.suspicion_score},
        )
    except httpx.HTTPError as exc:
        logger.error("Theft alarm failed: %s", exc)
        await log_audit_event(
            module="theft",
            action="theft_alarm_failed",
            entity_id=str(inv_id),
            new_value={"error": str(exc)},
        )
```

### Test senaryoları (4)

1. High classify + chat_id set → mocked Telegram POST çağrılır + audit `theft_alarm_sent`
2. Medium classify → broadcast çağrılmaz
3. TELEGRAM_OPS_CHAT_ID boş → skip + warning log + audit YOK
4. Telegram down (mocked HTTPError) → `theft_alarm_failed` audit + akış 201 başarılı

### Acceptance
- 4/4 test
- `settings.THEFT_ALARM_ENABLED` flag çalışır

---

## API contract örnekleri (mock JSON)

### POST /admin/investigations

Request:
```json
{
  "anomaly_id": 42,
  "initial_notes": "Yakıt fişi eksik, ek inceleme gerekli."
}
```

Response 201:
```json
{
  "id": 7,
  "anomaly_id": 42,
  "status": "open",
  "suspicion_score": 0.78,
  "suspicion_level": "high",
  "assigned_to_user_id": null,
  "notes": "Yakıt fişi eksik, ek inceleme gerekli.",
  "resolution_type": null,
  "evidence_files": [],
  "created_at": "2026-05-23T14:30:00Z",
  "updated_at": "2026-05-23T14:30:00Z",
  "closed_at": null,
  "plaka": "34 ABC 1234",
  "sofor_adi": "Ali Veli",
  "sapma_yuzde": 45.2
}
```

### PATCH /admin/investigations/7

Request:
```json
{
  "resolution_type": "real_theft",
  "notes": "Şoför itiraf etti, 50L kaçırılmış."
}
```

Response 200 (status auto='resolved'):
```json
{
  "id": 7,
  "status": "resolved",
  "resolution_type": "real_theft",
  "closed_at": "2026-05-25T09:15:00Z",
  ...
}
```

### GET /admin/investigations/patterns?days=30&min_count=3

Response:
```json
[
  {
    "sofor_id": 12,
    "sofor_adi": "Ali Veli",
    "arac_id": 5,
    "plaka": "34 ABC 1234",
    "occurrence_count": 5,
    "avg_suspicion_score": 0.78,
    "last_seen": "2026-05-22T10:00:00Z"
  }
]
```

---

## Bağımlılık + commit sırası

```
B.1 ─── B.2 ─── B.3
        │
        ├── B.4 (frontend, B.2 endpoint'lerine bağımlı)
        │
        └── B.5 (B.1 classifier + B.2 POST'a hook)
```

**5 commit:**
1. `feat(theft): B.1 — FuelTheftClassifier + investigation schemas + 11 unit test`
2. `feat(theft): B.2 — FuelInvestigation tablosu + 0014 migration + 6 CRUD endpoint + 16 integration`
3. `feat(theft): B.3 — daily pattern scan Celery task`
4. `feat(theft): B.4 — AlertsPage soruşturmalar sekmesi + Kanban + DetailDialog + 6 vitest`
5. `feat(theft): B.5 — Telegram OPS alarm + 4 test`

## Genel kabul kriterleri

- [ ] `pytest -m "unit or integration"` toplam yeşil (mevcut + 31 yeni: 11+16+4)
- [ ] `npx vitest --run` 6 yeni dahil yeşil
- [ ] `npx tsc --noEmit` 0
- [ ] `npx vite build` 0
- [ ] `ruff check --ignore=E501` yeni hata 0
- [ ] `mypy --ignore-missing-imports` yeni hata 0
- [ ] `alembic` single head 0014_fuel_investigation
- [ ] CLAUDE.md → "Theft Investigation modülü" bölümü
- [ ] Feature flag `THEFT_INVESTIGATION_ENABLED` + `THEFT_ALARM_ENABLED` doğrulandı (503 testi)
- [ ] Audit log her CRUD'da entry oluşturuyor (audit_log_dosyasından grep ile doğrulanabilir)
- [ ] PII: classifier `factors` listesi anomaly_id dışında ID/isim içermez; Telegram alarm PII içerir ama sadece admin grub'a gider

## Tahmin tablosu (gerçekçi)

| Adım | Bütçe | Risk |
|------|-------|------|
| B.1 | 3h | LightGBM ileride eklenebilir; MVP saf kurallar — risk yok |
| B.2 | 3h | 6 endpoint × test; migration eşleştirme |
| B.3 | 1.5h | Endpoint zaten B.2'de yapıldı, Celery sadece logger |
| B.4 | 4-5h | Kanban + DetailDialog + Pattern table; +0.5h state mgmt |
| B.5 | 1.5h | Helper küçük, 4 test |
| Buffer | 1h | Integration test bağımlılıkları, lint düzeltme |
| **Toplam** | **14-15h** | Plan tahmini 14-18h içinde |

## Karara bağlı tasarım (v3'te eklendi)

1. **Permission key:** Yeni `theft:*` izni YOK. Mevcut `sefer:read/write` kullanılır — admin zaten sahip.
2. **State mgmt frontend:** Zustand YOK. TanStack Query + local component state yeterli (Kanban data'sı tek query, mutation invalidate eder).
3. **Evidence file gerçek upload:** **scope dışı (MVP'de URL listesi)**. Gerçek upload sonraki PR'da OCR servisi pattern'iyle.
4. **Pattern heatmap görselleştirme:** MVP'de **tablo** (recharts ScatterChart sonraki PR).
5. **Telegram OPS_BOT_TOKEN ayrı bot mu, driver bot mu?:** Mevcut config'de ayrı `TELEGRAM_OPS_BOT_TOKEN` var; öncelik OPS, yoksa DRIVER fallback.
6. **Kanban dnd:** YOK. Status değişimi inline dropdown / detail dialog.
7. **Re-classify cron'u:** Open investigation'lar her gün re-classify edilsin mi? **HAYIR MVP'de.** Sadece manual `POST /classify` ile.

## Açık sorular (uygulamadan önce karara bağlanmalı)

- **Q1:** Soruşturma kanıt URL'leri public mi yoksa imzalı mı? → **MVP'de string field; production'da imzalı URL gerekecek (sonraki PR).**
- **Q2:** Birden fazla admin aynı anda PATCH yaparsa son yazan kazanır mı, optimistic locking mi? → **Son yazan kazanır (MVP).** Audit log ile geri izlenebilir.
- **Q3:** "investigation_assigned" → assigned_to_user_id mailini bilgilendirelim mi? → **Hayır MVP'de.** İleride.
- **Q4:** Pattern detection threshold'u (`min_count=3`) config'lenebilir mi? → **HAYIR sabit.** İhtiyaç olursa endpoint param + admin config.

Bu plan **direkt B.1'e başlamaya hazır** durumda.
