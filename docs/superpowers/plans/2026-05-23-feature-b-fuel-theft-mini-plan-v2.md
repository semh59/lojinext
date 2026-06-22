# Feature B — Yakıt Hırsızlığı Tespit + Soruşturma Akışı (Mini-Plan v2)

> **Üst plan:** `docs/superpowers/plans/2026-05-21-frontend-derinlik-ve-yeni-ozellikler.md` Faz 2 → Sprint 5.

**İş problemi:** Yakıt anomalileri tespit ediliyor (fuel_gap_liters>0) ama yöneticinin "ne yapacağım?" sorusuna yapısal bir cevap yok. Şu an her anomali tek tek değerlendiriliyor, soruşturma akışı yok, kanıt bağlanmıyor, pattern'ler kaçıyor.

**Çözüm tezi:** Mevcut tüketim anomalisi + leakage + sefer/araç metadata'sını kural-bazlı bir sınıflandırıcıdan geçirerek "düşük/orta/yüksek şüphe" skoru üret. Yüksek şüpheliler için soruşturma kaydı aç → atama → notlar/kanıt → çözüm akışı. Pattern detection ile aynı şoför/araç/lokasyon kombinasyonlarını yüzeye çıkar. Yüksek şüphe oluşunca admin Telegram grup'una alarm.

---

## 0. Bağlam ve Mevcut Altyapı

### 0.1 Hazır altyapı sözleşmeleri

| Bileşen | Konum | Kullanılacak API |
|---------|-------|------------------|
| Anomaly model | `app/database/models.py:723` | kaynak_id, kaynak_tip, sapma_yuzde, severity. T7'de acknowledged_at/resolved_at alanları eklendi. |
| `get_cost_leakage_stats` | `app/database/repositories/sefer_repo.py:193` | fuel_gap_liters + cost hesabı |
| `get_recent_anomalies(status)` | `app/core/services/anomaly_detector.py:290` | open/acknowledged/resolved filtre |
| `T7` anomali aksiyon endpoint'leri | `app/api/v1/endpoints/anomalies.py` | `/anomalies/{id}/acknowledge`, `/resolve` |
| AlertsPage 3 sekme | `frontend/src/pages/AlertsPage.tsx` | `AlertTab = 'all'|'leakage'|'maintenance'` |
| Telegram grup endpoint | `app/config.py:TELEGRAM_DRIVER_BOT_TOKEN` | Driver bot; ops_bot.py de var |
| Audit log helper | `app/infrastructure/audit/audit_logger.py` | `log_audit_event(action, module, entity_id, ...)` |

### 0.2 Mimari/veri akış

```
Anomali (mevcut tablo) ──┐
                         │  FuelTheftClassifier
fuel_gap_stats ──────────┼──► (rule-based + ML hibrit)
                         │   ─► suspicion_score (0..1)
sefer/yakıt metadata ────┘   ─► suspicion_level (low/med/high)

high → INSERT FuelInvestigation (status='open')
       + POST Telegram alarm (admin grup)

Investigation flow:
  open → assigned (assigned_to user_id)
       → investigating (notes, evidence_files)
       → resolved (resolution_type: real_theft / false_alarm / data_error / inconclusive)
       → closed

Pattern detection (offline Celery):
  GROUP BY (sofor_id, arac_id, lokasyon_id) → count > threshold → "tekrarlayan örüntü"
```

### 0.3 Performans bütçesi

| İşlem | Hedef | Strateji |
|-------|-------|----------|
| Classifier 1 anomali için | <100ms | Pure-py, DB tek sorgu |
| Investigation list (50 kayıt) | <300ms | SQL JOIN, index'li |
| Pattern detection (filo geneli) | <30s | Celery offline, günde 1× |
| Telegram alarm | <2s | httpx, fire-and-forget |

### 0.4 Güvenlik / yetki

- `/admin/investigations/*` → `require_permissions("admin:read")` veya yeni `"investigation:read|write"` permission. MVP'de `"sefer:write"` yeterli (admin'in zaten var).
- Evidence file upload (B.2'de) → MIME whitelist (image/jpeg, image/png, application/pdf), max 10MB.
- PII: notes/evidence sadece admin gözleri; LLM/Groq'a GİTMEZ.

### 0.5 Hata matrisi

| Hata | Backend | Frontend |
|------|---------|----------|
| Classifier exception | suspicion_level='unknown', score=0 | Kanban'da "Sınıflandırılmamış" sütunu |
| Investigation FK violation | 409 | Banner |
| Pattern detection task fail | log + Celery retry | mevcut Kanban etkilenmez |
| Telegram alarm fail | audit log: `theft_alarm_failed` | Sessiz; admin UI bildirimi |

### 0.6 Rollback

`settings.THEFT_INVESTIGATION_ENABLED = False` → tüm `/investigations/*` ve `/classify` 503. Tablo Alembic `0014_fuel_investigation` downgrade ile silinir.

---

## B.1 — FuelTheftClassifier (Core Logic) [3 saat]

### Files
- Create: `app/core/ai/fuel_theft_classifier.py`
- Create: `app/schemas/investigation.py`
- Create: `app/tests/unit/test_fuel_theft_classifier.py`

### Pre-conditions
- Anomaly tablosunda en az `tip='tuketim'` ve `tip='maliyet'` örnek satırlar var (test fixture'ı ile yaratılacak).
- `get_cost_leakage_stats` çalışır (verified).

### Pydantic şemalar (`app/schemas/investigation.py`)

```python
from typing import List, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

SuspicionLevel = Literal["low", "medium", "high", "unknown"]
InvestigationStatus = Literal["open", "assigned", "investigating", "resolved", "closed"]
ResolutionType = Literal["real_theft", "false_alarm", "data_error", "inconclusive"]


class TheftClassification(BaseModel):
    anomaly_id: int
    suspicion_score: float = Field(..., ge=0, le=1)
    suspicion_level: SuspicionLevel
    factors: List[str]  # "Yüksek fuel gap", "Tekrarlayan şoför", ...
    suggested_action: str


class InvestigationCreate(BaseModel):
    anomaly_id: int
    suspicion_score: Optional[float] = None
    suspicion_level: Optional[SuspicionLevel] = None
    initial_notes: Optional[str] = Field(None, max_length=2000)


class InvestigationUpdate(BaseModel):
    status: Optional[InvestigationStatus] = None
    assigned_to_user_id: Optional[int] = None
    notes: Optional[str] = Field(None, max_length=4000)
    resolution_type: Optional[ResolutionType] = None
    evidence_files: Optional[List[str]] = None


class InvestigationResponse(BaseModel):
    id: int
    anomaly_id: int
    status: InvestigationStatus
    suspicion_score: Optional[float]
    suspicion_level: Optional[SuspicionLevel]
    assigned_to_user_id: Optional[int]
    notes: Optional[str]
    resolution_type: Optional[ResolutionType]
    evidence_files: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]
    plaka: Optional[str] = None
    sofor_adi: Optional[str] = None
    sapma_yuzde: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)


class PatternMatch(BaseModel):
    sofor_id: Optional[int]
    sofor_adi: Optional[str]
    arac_id: Optional[int]
    plaka: Optional[str]
    lokasyon_id: Optional[int]
    lokasyon_label: Optional[str]
    occurrence_count: int
    avg_suspicion_score: float
    last_seen: datetime
```

### Classifier (`fuel_theft_classifier.py`)

```python
class FuelTheftClassifier:
    """Rule-based hibrit sınıflandırıcı. LLM YOK — küçük model gerekirse
    LightGBM ileride eklenebilir; MVP saf kurallarla.

    Skor bileşenleri:
    - Sapma yüzdesi (sapma_yuzde) ağırlık 0.5
    - Severity (low=0.1, medium=0.4, high=0.7, critical=1.0) ağırlık 0.3
    - Tekrarlayan örüntü (aynı şoför/araç son 30g >2 anomali) ağırlık 0.2

    suspicion_level eşikleri:
      score >= 0.7 → high
      score >= 0.4 → medium
      else        → low
    """

    SEVERITY_W = {"low": 0.1, "medium": 0.4, "high": 0.7, "critical": 1.0}

    async def classify(self, anomaly: dict) -> TheftClassification:
        # 1. Sapma bileşeni
        sapma_norm = min(1.0, abs(float(anomaly.get("sapma_yuzde", 0))) / 50.0)
        # 2. Severity
        sev_score = self.SEVERITY_W.get(anomaly.get("severity", "low"), 0.1)
        # 3. Pattern: aynı kaynak_id son 30 günde N anomali
        pattern_score = await self._pattern_score(anomaly["kaynak_id"], anomaly["kaynak_tip"])

        suspicion = 0.5 * sapma_norm + 0.3 * sev_score + 0.2 * pattern_score
        level = "high" if suspicion >= 0.7 else "medium" if suspicion >= 0.4 else "low"

        factors = self._explain(sapma_norm, sev_score, pattern_score, anomaly)
        action = self._suggest_action(level, factors)

        return TheftClassification(
            anomaly_id=anomaly["id"],
            suspicion_score=round(suspicion, 3),
            suspicion_level=level,
            factors=factors,
            suggested_action=action,
        )

    async def _pattern_score(self, kaynak_id: int, kaynak_tip: str) -> float:
        # SQL: anomaliler son 30g aynı kaynak_id+tip GROUP BY COUNT
        # ≥3 → 1.0, 2 → 0.5, ≤1 → 0.0
        ...
```

### Unit testler (8 senaryo)

1. Low sapma + low severity → suspicion_level='low'
2. Critical severity + high sapma → 'high'
3. Pattern score 1.0 (mock) → bileşen ağırlığı doğrulanır
4. _explain → factors içinde her bileşenden çıkarılan açıklama
5. _suggest_action → level başına 3 farklı mesaj
6. Exception → suspicion_level='unknown', score=0 fallback
7. sapma_yuzde negatif (lehte sapma) → abs() uygulanır
8. PII regex: factors içinde plaka/isim YOK (anomaly metadata'sı saklı)

### Acceptance
- pytest 8/8
- mypy + ruff temiz
- Hız: 100 anomali için <500ms (pytest-benchmark opsiyonel)

---

## B.2 — Investigation Tablosu + CRUD [3 saat]

### Files
- Modify: `app/database/models.py` (FuelInvestigation)
- Create: `alembic/versions/0014_fuel_investigation.py`
- Create: `app/api/v1/endpoints/investigations.py`
- Modify: `app/api/v1/api.py` (router include, prefix='/admin/investigations')
- Create: `app/tests/integration/test_investigations_crud.py`

### Model

```python
class FuelInvestigation(Base):
    __tablename__ = "fuel_investigations"
    __table_args__ = (
        Index("ix_fuel_inv_anomaly_id", "anomaly_id"),
        Index("ix_fuel_inv_status", "status"),
        Index("ix_fuel_inv_assigned", "assigned_to_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    anomaly_id: Mapped[int] = mapped_column(
        ForeignKey("anomalies.id", ondelete="CASCADE"), unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="open")  # open/assigned/investigating/resolved/closed
    suspicion_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    suspicion_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kullanicilar.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    evidence_files: Mapped[list] = mapped_column(JSONB, default=list)  # URL/key listesi
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("kullanicilar.id", ondelete="SET NULL"), nullable=True)
```

### Endpoints

| Metod | Path | Davranış |
|-------|------|----------|
| `POST` | `/admin/investigations` | Anomali için yeni inv aç. anomaly_id unique → 409 zaten var |
| `GET` | `/admin/investigations` | Liste; query: status, assigned_to_user_id, suspicion_level, days |
| `GET` | `/admin/investigations/{id}` | Tek kayıt + JOIN ile plaka/şoför/sapma_yuzde |
| `PATCH` | `/admin/investigations/{id}` | Status/notes/assigned güncelleme; resolution_type set olunca closed_at otomatik |
| `DELETE` | `/admin/investigations/{id}` | Audit log + soft delete (status='closed') |
| `POST` | `/admin/investigations/{id}/classify` | Mevcut classifier'ı çalıştırıp suspicion_* alanlarını güncelle |

### Integration testler (8 senaryo)

1. POST → 201 + body shape
2. POST anomaly_id duplicate → 409
3. GET list, filter status=open
4. PATCH status='resolved' → closed_at otomatik dolar
5. PATCH resolution_type='real_theft' → status='closed' otomatik
6. DELETE → status='closed' + audit log
7. POST /classify → suspicion_score/level güncellenir
8. POST unknown anomaly_id → 404

### Acceptance
- Alembic single head: 0014_fuel_investigation
- pytest 8/8

---

## B.3 — Pattern Detection [2 saat]

### Files
- Modify: `app/core/ai/fuel_theft_classifier.py` (`detect_patterns`)
- Modify: `app/api/v1/endpoints/investigations.py` (`GET /patterns`)
- Modify: `app/workers/tasks/coaching_tasks.py` veya yeni `theft_tasks.py` (Celery offline)
- Modify: `app/infrastructure/background/celery_app.py` (beat günlük 03:00)

### Algoritma

```sql
-- Aynı (sofor_id, arac_id) ikilisi son 30 gün ≥3 anomali
SELECT
    sofor_id,
    arac_id,
    COUNT(*) AS n,
    AVG(suspicion_score) AS avg_score,
    MAX(created_at) AS last_seen
FROM fuel_investigations fi
JOIN anomalies a ON fi.anomaly_id = a.id
JOIN seferler s ON a.kaynak_tip = 'sefer' AND a.kaynak_id = s.id
WHERE fi.created_at >= NOW() - INTERVAL '30 days'
GROUP BY sofor_id, arac_id
HAVING COUNT(*) >= 3
ORDER BY avg_score DESC NULLS LAST;
```

Frontend buna heat-map cell olarak gösterir; X axis = gün, Y axis = şoför, intensity = avg_suspicion.

### Acceptance
- `GET /admin/investigations/patterns?days=30` → PatternMatch[] döner
- Celery `theft.daily_pattern_scan` task'ı çalıştırılıp sonucu logger'a yazar (basit; UI'da gerçek zamanlı sorgu yeterli MVP'de)

---

## B.4 — Frontend Kanban + Soruşturmalar Sekmesi [4 saat]

### Files
- Modify: `frontend/src/components/alerts/SeverityFilter.tsx` (AlertTab'a 'investigations' ekle)
- Create: `frontend/src/components/alerts/InvestigationsKanban.tsx`
- Create: `frontend/src/components/alerts/InvestigationCard.tsx`
- Create: `frontend/src/components/alerts/InvestigationDetailDialog.tsx`
- Create: `frontend/src/components/alerts/PatternHeatmap.tsx`
- Create: `frontend/src/services/api/investigation-service.ts`
- Create: `frontend/src/resources/tr/investigations.ts`
- Modify: `frontend/src/pages/AlertsPage.tsx`

### Kanban düzeni

```
┌─Açık──┐ ┌─Atandı─┐ ┌─Soruşturuluyor─┐ ┌─Çözüldü─┐ ┌─Kapandı─┐
│ card  │ │ card    │ │ card           │ │ card     │ │ card     │
│ card  │ │         │ │ card           │ │          │ │          │
└───────┘ └─────────┘ └────────────────┘ └──────────┘ └──────────┘
```

Card içeriği:
- Suspicion badge (high=danger, medium=warning, low=secondary)
- Plaka • Şoför
- Sapma %
- "Detay" → InvestigationDetailDialog

InvestigationDetailDialog:
- Tüm alanlar inline edit (assigned dropdown — admin kullanıcı listesi)
- Status select; resolution_type select (status='resolved' iken)
- Notes textarea
- Evidence files: küçük preview + "yeni dosya" yükleme butonu (MVP'de string URL listesi; gerçek upload sonraki iterasyona)

PatternHeatmap:
- /investigations/patterns sorgusu
- Sade tablo: ad, plaka, sayı, ort skor, son tarih (heat-map için recharts ScatterChart MVP fazlası — basit liste yeterli)

### Test (vitest 6)

1. Kanban 5 sütun render edilir, boş sütunlar "—" placeholder
2. Card click → DetailDialog açılır
3. Status değişimi → mutation çağrı parametresi doğru
4. resolution_type set + save → mutation çağrılır
5. Pattern table boş veri → empty state
6. Pattern table 3+ pattern → satırlar görünür

---

## B.5 — Telegram Alarm Entegrasyonu [2 saat]

### Files
- Modify: `app/api/v1/endpoints/investigations.py` (`POST /classify` → high ise alarm)
- Modify: `app/workers/tasks/coaching_tasks.py` veya yeni `theft_tasks.py` (broadcast helper)
- Modify: `app/config.py` (TELEGRAM_OPS_CHAT_ID env)
- Create: `app/tests/integration/test_theft_alarm.py`

### Davranış

```python
# investigations.py POST /classify sonrası
if result.suspicion_level == "high" and settings.THEFT_ALARM_ENABLED:
    await _broadcast_theft_alarm(investigation_id, result, anomaly_metadata)
```

Mesaj template (HTML, html.escape):

```
🚨 <b>Yüksek Şüpheli Yakıt Anomalisi</b>

🚛 Plaka: {plaka}
👤 Şoför: {sofor}
📉 Sapma: {sapma:+.1f}%
🎯 Şüphe skoru: {score:.2f}

🔗 İncele: {frontend_url}/alerts?tab=investigations&id={id}
```

### Test (3)

1. High classify → mocked Telegram POST çağrılır
2. Medium classify → çağrılmaz
3. TELEGRAM_OPS_CHAT_ID boş → alarm skip + warning log

---

## Bağımlılık & Çalıştırma Sırası

```
B.1 (classifier) ── B.2 (CRUD)
                    │
                    ├─ B.3 (patterns)
                    ├─ B.4 (frontend)
                    └─ B.5 (telegram alarm)
```

**Önerilen commit sırası:**

1. `feat(theft): B.1 — FuelTheftClassifier + schemas + 8 unit test`
2. `feat(theft): B.2 — FuelInvestigation + 0014 migration + 6 endpoint + 8 integration`
3. `feat(theft): B.3 — pattern detection endpoint + daily Celery scan`
4. `feat(theft): B.4 — Kanban + DetailDialog + heatmap + 6 vitest`
5. `feat(theft): B.5 — Telegram alarm + 3 test`

## Genel kabul kriterleri

- [ ] pytest unit + integration tamamı yeşil
- [ ] vitest tüm coaching + theft testleri yeşil
- [ ] tsc temiz
- [ ] vite build başarılı
- [ ] ruff + mypy yeni hata yok
- [ ] alembic single head (0014_fuel_investigation)
- [ ] CLAUDE.md → "Theft Investigation modülü" bölümü
- [ ] Feature flag `THEFT_INVESTIGATION_ENABLED` + `THEFT_ALARM_ENABLED`
- [ ] PII: classifier factors + alarm mesajı plaka/isim içerir (admin-only) ama LLM'e gitmez

## Tahmini süre

| Adım | Süre | Risk |
|------|------|------|
| B.1 | 3 saat | Skor formülü iterasyon olabilir |
| B.2 | 3 saat | Alembic + 6 endpoint test |
| B.3 | 2 saat | SQL agg query optimizasyon |
| B.4 | 4 saat | Kanban dnd/scroll detayları (MVP statik 5 sütun, no drag) |
| B.5 | 2 saat | Telegram OPS_CHAT_ID config gerekiyor |
| **Toplam** | **14 saat** | Plan tahmini 14-18 saat içinde |

## Karara bağlanan tasarım soruları

| # | Soru | Karar |
|---|------|-------|
| Q1 | Evidence file upload (binary) gerçek mi? | **MVP'de string URL listesi.** Gerçek binary upload OCR servisi pattern'i ile gelir, scope dışı. |
| Q2 | Heat-map gerçek (recharts ScatterChart) mı tablo mu? | **MVP tablo.** Heat-map fazla efor, veri yoğunluğu düşük; ileride visualization upgrade. |
| Q3 | Pattern detection task günde mi gerçek-zamanlı mı? | **GET endpoint gerçek zamanlı**, Celery task günde 1× sadece logger için. |
| Q4 | Telegram OPS grubu config? | **Yeni `TELEGRAM_OPS_CHAT_ID` env var.** Boş ise alarm skip + warning. |
| Q5 | Kanban dnd? | **Statik sütunlar, drag YOK.** Status değişimi inline dropdown ile detail dialog'tan. |
