# Feature M — Takograf Entegrasyonu (Mini-Plan v3) — **DEFERRED**

> ## ⚠ Bu plan ertelendi (2026-05-26)
>
> Mevcut taslakta tespit edilen kritik boşluklar:
> 1. **DDD parser uydurma:** Plandaki `_parse_*` fonksiyonları gerçek AB Reg
>    2016/799 Annex IC formatını yansıtmıyor (ASN.1 BER, 13-bit bitfield,
>    BCD-encoded). 300 satır değil ~2000-5000 LoC üretim seviyesi gerekir.
> 2. **Dijital imza doğrulaması yok** (ERCA root cert chain) — olmadan sahte
>    DDD upload edilebilir.
> 3. **AETR kuralları eksik:** 15+30 split mola handle edilmiyor; 15-günlük
>    90sa kuralı yok; weekly rest reduction yok.
> 4. **KVKK uyumu yok:** PII encryption, retention policy, data subject
>    rights — Türkiye'de tachograph verisi işleyen sistemler KVK kuruluna
>    kayıtlı olmalı.
> 5. **Çoklu şoför TIR** ve **Gen 2 Smart-Tachograph** "açık not" olarak
>    geçildi ama Türk operasyonunda core kullanılabilirlik gereği.
> 6. **17 saat tahmini gerçekçi 40-80 saat** (gerçek parser + AETR + KVKK).
>
> ## Yeniden ele almak için ön gereksinimler:
> - [ ] AB Reg 2016/799 Annex IC tam okuma + AETR pratik kılavuzları
> - [ ] KGM (Karayolları Genel Müdürlüğü) ile temas — Türkiye'ye özel kurallar
> - [ ] KVKK rehberlik (Verbis kayıt + politikalar)
> - [ ] 3rd-party DDD parser değerlendirmesi: dtco-tools, ddd-reader, pyddd
> - [ ] Gerçek (anonim) DDD fixture toplama (üretim ortamından)
> - [ ] ERCA certificate chain validation referans implementasyonu
>
> ## Aktif plan durumu
>
> E v3 planında (2026-05-26-feature-e-strategic-cockpit-v3.md) **E.4
> compliance heatmap v1 sadece muayene + ehliyet'i kapsar.** Takograf
> entegrasyonu bu plan revize edilip aktive olana kadar **scope dışı**.
>
> Aşağıdaki içerik referans olarak korunuyor — uygulanması için yukarıdaki
> 6 ön gereksinim tamamlanmadan başlanmamalı.
>
> ---

**Tarih:** 2026-05-26
**Status:** **DEFERRED** (yukarıdaki nedenlerle)
**Önceki sürümler:** yok (yeni özellik; E v3'ün §18 "Açık notlar"ında v2'ye
bırakılmıştı, kullanıcı 2026-05-26'da E'den önce takografa odaklanmayı
seçti çünkü tüm motorları besliyor).

---

## 0. Özet (TL;DR)

**Sorun:** Türkiye'de 3.5+ ton ticari araçlarda **dijital takograf zorunlu**
(2010+). AETR/AB kuralları (günlük 9 sa sürüş, 4.5 sa sonra 45 dk mola,
haftalık 56 sa, vb.) ihlali ciddi ceza + iş kazası riski. LojiNext bu
veriyi şu an tamamen kör — şoför skoru manuel + auto karışım heuristic,
hırsızlık kanıtlama anomali sapma %'sine bağlı.

**Çözüm:** DDD dosyalarından (takograf standart format) çıkarılan **gerçek
şoför davranış verisi** mevcut tüm motorlara beslenir:
- **A koçluk** otomatik öneri üretir (mola eksiği, agresif sürüş)
- **B hırsızlık** kontak kapalı + yakıt eksilmesi kanıtı
- **D.4 bakım factor** agresif fren/hızlanma sayısı dahil
- **C planner** şoför uygunluk skoru gerçek davranıştan
- **E.4 compliance** muayene+ehliyet'ten AETR'e genişler
- **Sofor.score** auto-component'i artar (%50 → %70 ağırlık)

Yeni ML modeli yok — DDD binary parser + AETR kural motoru + sefer
eşleşme. Yeni microservice yok (mevcut FastAPI app içinde). Tek yeni
dependency: opsiyonel `python-ddd-parser` (yoksa custom Annex IB parser).

**Hedef KPI:** 3 ay sonra AETR ihlal sayısı %30 düşmeli (uyarı +
proaktif koçluk ile). Şoför skor otomasyon oranı %50 → %80.

---

## 1. İş ihtiyacı

### 1.1 Yasal arka plan (Türkiye)

AETR/AB regülasyonu uyumlu kurallar (TKHK, KGM, 4925 Karayolu Taşıma):

| Kural | Limit | İhlal cezası* |
|---|---|---|
| Günlük max sürüş | 9 saat (haftada 2× 10) | ~₺3.000-15.000 |
| Haftalık max sürüş | 56 saat | ~₺5.000-20.000 |
| 15-günlük max | 90 saat | ~₺10.000-30.000 |
| 4.5 sa sonra mola | min 45 dk (15+30 bölünebilir) | ~₺1.500-5.000 |
| Günlük dinlenme | min 11 saat | ~₺3.000-10.000 |
| Haftalık dinlenme | 45 saat (her 6g'de) | ~₺5.000-15.000 |

*2026 yaklaşık değerler; gerçek tabloyu KGM yayınlar.

**Cihaz zorunluluğu:**
- 2010+ dijital takograf (tüm 3.5t+ ticari araçlar)
- 2020+ Smart-Tachograph Gen 2 (yeni araçlar, AB uyumu)
- Şoför kartı (kişiye özel smart card) — her şoför için zorunlu
- 28 günlük veri kartta tutulur

### 1.2 Mevcut LojiNext durumu

| Veri | Şu an | Takograf entegrasyonu ile |
|---|---|---|
| Şoför davranışı | Manuel skor + heuristic auto (yakıt sapma) | Gerçek timeline: sürüş/mola/aktif iş |
| AETR uyumu | Hiçbir kontrol yok | Otomatik ihlal tespit + uyarı |
| Sefer hızı/mesafe | Sefer.mesafe_km (manuel) | DDD'den auto: gerçek mesafe + max/avg hız |
| Hırsızlık kanıtı | Yakıt sapma % + sezgisel | Kontak kapalı + yakıt akışı = kanıt |
| Bakım factor | Yaş + son PERIYODIK | + agresif fren/hızlanma sayısı |
| Koçluk önerisi | LLM + tablodan | + gerçek davranış kanıtı |

### 1.3 Operasyonel akış

```
[Şoför seferden döner ofise]
   │
   ├─ USB Şoför Kart Okuyucu (Continental DLD, Stoneridge Optac3, ~₺500-1500)
   │  → C_<kartno>.DDD dosyası (28 günlük aktivite)
   │
   ├─ Veya: Mobile uygulamadan upload (geleceğe yönelik)
   │
   ↓
[Frontend Drag-Drop Upload]
   POST /tachograph/upload (multipart .ddd)
   ↓
[Backend: ddd_parser.py]
   • TREP 03: kart kimliği → Sofor eşleştir
   • TREP 06: aktivite timeline → tachograph_records'a yaz
   • TREP 07: vehicles used → Arac.vin eşleştir
   ↓
[AETR Rule Engine]
   • Günlük 9 sa? Haftalık 56 sa? Mola 45 dk? ...
   • İhlal → tachograph_violations tablosuna yaz
   • → anomalies tablosuna severity=high anomaly üret
   ↓
[Sefer Eşleşme]
   • Aynı tarih + sofor_kart_id + arac_vin → Sefer
   • Sefer'i tachograph metadata ile zenginleştir
   ↓
[Cross-Motor Beslemesi]
   • Sofor.score auto güncelle
   • D.4 maintenance_factor agresif sürüş bonusu
   • A koçluk insight üret
   • E.4 compliance heatmap güncel veri
```

---

## 2. Karar matrisi (5 kritik soru ve cevapları)

### Q1 — DDD parser strateji?

**Cevap:** Minimal parse, sadece 4 TREP. Tam Annex IB spec'i ~200 sayfa;
v1'de gereken alt küme aşağıdaki.

| TREP | İçerik | v1'de gerekli mi? |
|---|---|---|
| 01 | ICC info (kart elektronik bilgi) | ❌ |
| 02 | Card identification | ✓ |
| 03 | **Driver identification** | ✓ (kart no, ehliyet) |
| 04 | Driving licence info | ❌ (zaten Sofor.ehliyet_sinifi var) |
| 05 | Events/faults (overspeeding) | ✓ (bonus, max hız ihlali) |
| 06 | **Driver activity** (timeline) | ✓ (en kritik) |
| 07 | **Vehicles used** | ✓ (arac eşleşmesi) |
| 08 | Places (start/end work) | ❌ (sefer.cikis/varis zaten var) |
| 09 | Card download | ❌ |
| 0A | Specific conditions | ❌ |

**Tek bağımlılık:** Python stdlib `struct` + `datetime`. Custom binary
parser (~300 satır). `python-ddd-parser` paketi varsa onu da deneyebiliriz
ama temel: TLV (Type-Length-Value) parsing + Annex IB tablolarına göre
field decode.

### Q2 — Şoför kart ID nasıl eşleşir?

**Cevap:** Yeni alan `Sofor.tachograph_kart_no` (nullable, unique).
Migration: `0015_tachograph_setup`.

```sql
ALTER TABLE soforler ADD COLUMN tachograph_kart_no VARCHAR(20) UNIQUE;
ALTER TABLE araclar ADD COLUMN vin VARCHAR(17);  -- chassis no
```

İlk upload'da kart no Sofor'a manuel atanır (UI'da "Şoför seç" dropdown);
sonraki upload'larda otomatik. Eşleşmeyen kart → "Bu kart sistemde
tanımlı değil — şoföre atayın" mesajı.

### Q3 — İhlal aksiyon akışı?

**Cevap:** İki kademeli — kayıt + alarm.

1. **tachograph_violations** tablosu: her ihlal ayrı satır (id, tachograph_record_id,
   ihlal_tipi, eski_deger, limit, severity).
2. **anomalies** tablosuna severity=high entry (mevcut B akışı: ack/resolve UI ile yönet).
3. Severity=critical olanlar (örn 90sa 15-günlük cap aşımı) → Telegram OPS alarm (B.5 pattern reuse).
4. Repeat-offender (son 30g 3+ ihlal) → A koçluk auto-trigger.

### Q4 — Sefer eşleşme algoritması?

**Cevap:** 3-koşullu fuzzy match, en yüksek skor kazanır.

```
score = 0
if tacho_record.tarih == sefer.tarih:                           score += 50
if tacho_record.sofor_kart_no maps to sefer.sofor_id:           score += 30
if abs(tacho_record.total_mesafe - sefer.mesafe_km) < 20:       score += 20
if abs(tacho_record.surus_baslangic - sefer.saat) < 2 saat:    score += 10
# match if score >= 70 (60'a indirilebilir ama %30 false positive riski)
```

**Çoklu sefer aynı gün:** Şoför aynı gün 2 sefer yaparsa, takograf timeline
zaten ayrık sürüş bloklarını gösterir; her bloğu en yakın sefere atarız.

**Eşleşmeyen takograf kaydı:** Sefer kaydı eksik olabilir (manuel girilmemiş);
panel'de "Eşleşmeyen takograf" listesi → operator manuel sefer oluşturabilir.

### Q5 — Şoför kart kayıp/değişim?

**Cevap:** Sofor.tachograph_kart_no audit log + history table.

Yeni kart geldiğinde:
1. Eski kart no `tachograph_kart_history` tablosuna geçirilir (sofor_id,
   eski_no, yeni_no, degisim_tarihi, sebep).
2. Yeni kart no `Sofor.tachograph_kart_no`'da güncellenir.
3. Eski kart numarasıyla gelen DDD upload'lar history'e bakıp eşleştirir
   (geçmiş ihlalleri kaybetmemek için).

Kart kayıp + zorunlu yenileme (Türkiye'de TÜRSAB) durumunda kullanıcı
admin UI'da "Kart yenile" formundan günceller.

---

## 3. Mimari (yeni + değişen dosyalar)

### Backend

```
app/
├── core/
│   ├── services/
│   │   ├── ddd_parser.py                    # NEW (M.2) — binary DDD parser
│   │   ├── tachograph_service.py            # NEW — yüksek seviye orkestrasyon
│   │   └── aetr_rule_engine.py              # NEW (M.4) — kural motoru
│   ├── ml/
│   │   └── vehicle_health_factor.py         # MODIFY (M.6) — agresif sürüş factor
│   └── ai/
│       └── driver_coaching_engine.py        # MODIFY (M.6) — AETR ihlal insight
├── api/v1/endpoints/
│   └── tachograph.py                        # NEW (M.3) — upload + list + violations
├── workers/tasks/
│   └── tachograph_tasks.py                  # NEW (M.8) — günlük cron + sefer eşle
├── database/
│   └── models.py                            # MODIFY (M.1) — TachographRecord +
│                                              TachographViolation + alanlar
├── schemas/
│   └── tachograph.py                        # NEW — Pydantic schemas
├── infrastructure/background/
│   └── celery_app.py                        # MODIFY — beat schedule
├── config.py                                # MODIFY — TACHOGRAPH_* flags
└── tests/
    ├── unit/
    │   ├── test_ddd_parser.py               # NEW (M.2) — binary fixtures
    │   ├── test_aetr_rule_engine.py         # NEW (M.4) — kural sınır testleri
    │   ├── test_tachograph_trip_match.py    # NEW (M.5) — eşleşme algoritması
    │   └── test_tachograph_coaching.py      # NEW (M.6) — insight üretimi
    └── integration/
        ├── test_tachograph_upload.py        # NEW (M.3) — endpoint kontratı
        └── test_tachograph_cron.py          # NEW (M.8) — beat task

alembic/versions/
└── 0015_tachograph_setup.py                 # NEW (M.1) — tablo + alan migration
```

### Frontend

```
frontend/src/
├── pages/admin/
│   └── TakografPage.tsx                     # NEW (M.3) — yeni admin sayfası
├── components/admin/tachograph/
│   ├── TachographUpload.tsx                 # NEW (M.3) — drag-drop
│   ├── ViolationsList.tsx                   # NEW (M.4) — ihlal paneli
│   ├── DriverActivityTimeline.tsx           # NEW (M.5) — günlük timeline
│   ├── UnmatchedRecordsPanel.tsx            # NEW (M.5) — eşleşmemiş kayıtlar
│   ├── ComplianceHeatmap.tsx                # MODIFY/MOVE — E.4 ile birleşir
│   └── __tests__/                           # NEW — 5 vitest
├── services/api/
│   └── tachograph-service.ts                # NEW — API wrapper
├── resources/tr/
│   └── tachograph.ts                        # NEW — Türkçe + AETR sözlük
├── hooks/
│   └── useTachograph.ts                     # NEW — RQ hook'lar
└── App.tsx                                  # MODIFY — /admin/takograf route
```

**Migration zorunlu** — yeni tablo + Sofor/Arac'a alanlar.

---

## 4. M.1 — Database migration

### 4.1 `alembic/versions/0015_tachograph_setup.py`

```python
"""Tachograph setup (Feature M.1)

Revision ID: 0015_tachograph_setup
Revises: 0014_fuel_investigation
Create Date: 2026-05-26 ...
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision: str = "0015_tachograph_setup"
down_revision: Union[str, Sequence[str], None] = "0014_fuel_investigation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sofor: tachograph_kart_no (kişisel kart)
    op.add_column(
        "soforler",
        sa.Column("tachograph_kart_no", sa.String(20), nullable=True),
    )
    op.create_index(
        "ix_sofor_tachograph_kart_no",
        "soforler", ["tachograph_kart_no"],
        unique=True,
        postgresql_where=sa.text("tachograph_kart_no IS NOT NULL"),
    )

    # Arac: VIN (chassis no — takograf birimi VIN'i raporlar)
    op.add_column(
        "araclar",
        sa.Column("vin", sa.String(17), nullable=True),
    )
    op.create_index(
        "ix_arac_vin", "araclar", ["vin"], unique=False,
    )

    # Şoför kart history (kayıp/yenileme audit)
    op.create_table(
        "tachograph_kart_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "sofor_id", sa.Integer,
            sa.ForeignKey("soforler.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("eski_kart_no", sa.String(20), nullable=False),
        sa.Column("yeni_kart_no", sa.String(20), nullable=True),
        sa.Column("degisim_tarihi", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("sebep", sa.String(40), nullable=True),
    )

    # Ana tablo: takograf günlük kayıt
    op.create_table(
        "tachograph_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "sofor_id", sa.Integer,
            sa.ForeignKey("soforler.id", ondelete="RESTRICT"),
            nullable=False, index=True,
        ),
        sa.Column(
            "arac_id", sa.Integer,
            sa.ForeignKey("araclar.id", ondelete="SET NULL"),
            nullable=True, index=True,
        ),
        sa.Column("tarih", sa.Date, nullable=False, index=True),
        sa.Column("kart_no_at_upload", sa.String(20), nullable=False),
        # Süre dakikaları (gün için toplam)
        sa.Column("surus_dk", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mola_dk", sa.Integer, nullable=False, server_default="0"),
        sa.Column("calisma_dk", sa.Integer, nullable=False, server_default="0"),
        sa.Column("hazir_dk", sa.Integer, nullable=False, server_default="0"),
        # Detay
        sa.Column("total_mesafe_km", sa.Float, nullable=True),
        sa.Column("max_hiz_kmh", sa.Float, nullable=True),
        sa.Column("avg_hiz_kmh", sa.Float, nullable=True),
        sa.Column("agresif_fren_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("agresif_hizlanma_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rolanti_dk", sa.Integer, nullable=False, server_default="0"),
        # Timeline detayları
        sa.Column("aktivite_timeline", JSONB, nullable=True),
        # Sefer eşleşmesi
        sa.Column(
            "matched_sefer_id", sa.Integer,
            sa.ForeignKey("seferler.id", ondelete="SET NULL"),
            nullable=True, index=True,
        ),
        sa.Column("match_score", sa.Integer, nullable=True),
        # Audit
        sa.Column("source_filename", sa.String(255), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer,
                  sa.ForeignKey("kullanicilar.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("sofor_id", "tarih",
                            name="uq_tachograph_sofor_date"),
    )
    op.create_index(
        "ix_tachograph_sofor_date",
        "tachograph_records", ["sofor_id", "tarih"],
    )

    # İhlaller
    op.create_table(
        "tachograph_violations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "tachograph_record_id", sa.Integer,
            sa.ForeignKey("tachograph_records.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "sofor_id", sa.Integer,
            sa.ForeignKey("soforler.id", ondelete="RESTRICT"),
            nullable=False, index=True,
        ),
        sa.Column("ihlal_tipi", sa.String(40), nullable=False, index=True),
        sa.Column("severity", sa.String(20), nullable=False),  # low/medium/high/critical
        sa.Column("aktual_deger", sa.Float, nullable=False),
        sa.Column("limit_deger", sa.Float, nullable=False),
        sa.Column("birim", sa.String(20), nullable=False),  # dk, sa, kmh
        sa.Column("tarih", sa.Date, nullable=False, index=True),
        sa.Column("aciklama", sa.Text, nullable=True),
        # Anomaly entegrasyonu
        sa.Column("anomaly_id", sa.Integer,
                  sa.ForeignKey("anomalies.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="chk_tacho_violation_severity",
        ),
    )


def downgrade() -> None:
    op.drop_table("tachograph_violations")
    op.drop_index("ix_tachograph_sofor_date", table_name="tachograph_records")
    op.drop_table("tachograph_records")
    op.drop_table("tachograph_kart_history")
    op.drop_index("ix_arac_vin", table_name="araclar")
    op.drop_column("araclar", "vin")
    op.drop_index("ix_sofor_tachograph_kart_no", table_name="soforler")
    op.drop_column("soforler", "tachograph_kart_no")
```

### 4.2 SQLAlchemy model'ler

`app/database/models.py` — `TachographRecord`, `TachographViolation`,
`TachographKartHistory` modelleri eklenir + Sofor/Arac'a yeni alanlar.

### 4.3 Test

- `test_migration_0015_upgrade_downgrade.py` (mevcut migration test
  şablonuna uy)

---

## 5. M.2 — DDD parser servisi

### 5.1 `app/core/services/ddd_parser.py`

```python
"""Feature M.2 — DDD (Digital Tachograph) binary parser.

AB Annex IB Appendix A1 (Tachograph Data Dictionary) uyumlu minimal parser:
4 TREP record (02, 03, 06, 07) extract eder. Tam spec ~200 sayfa; bu
parser üretim ihtiyacı kadar (driver_id + activity timeline + vehicles).
"""
from __future__ import annotations
import struct
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional


# TREP tag'ler (Annex IB §B)
TREP_CARD_IDENTIFICATION = 0x02
TREP_DRIVER_IDENTIFICATION = 0x03
TREP_DRIVER_ACTIVITY = 0x06
TREP_VEHICLES_USED = 0x07

# Aktivite tipleri (4 bit upper nibble)
ACTIVITY_REST = 0   # B - rest
ACTIVITY_AVAILABLE = 1  # A - available
ACTIVITY_WORK = 2   # W - work
ACTIVITY_DRIVING = 3   # D - driving


@dataclass
class ActivityChunk:
    """Tek aktivite bloğu — günün herhangi bir saatinde başlayıp süren tek tip aktivite."""
    activity: int          # 0..3 (rest/available/work/driving)
    minute_in_day: int     # 0..1440 başlangıç
    duration_min: int      # 1..1440 süre


@dataclass
class DailyActivity:
    tarih: date
    chunks: List[ActivityChunk] = field(default_factory=list)
    distance_km_at_end: Optional[float] = None


@dataclass
class VehicleUsage:
    vin: Optional[str]
    plaka: Optional[str]
    sefer_baslangic: datetime
    sefer_bitis: Optional[datetime]
    start_km: Optional[int]
    end_km: Optional[int]


@dataclass
class DddParseResult:
    sofor_kart_no: str
    sofor_ad_soyad: Optional[str]      # PII — sadece eşleşmeyen kart için
    daily_activities: List[DailyActivity]
    vehicles_used: List[VehicleUsage]
    parsing_warnings: List[str] = field(default_factory=list)


class DddParseError(Exception):
    """Parse hatası — bozuk dosya veya beklenmeyen format."""


def parse_ddd_bytes(raw: bytes) -> DddParseResult:
    """DDD binary'yi parse et; 4 TREP record'u extract et.

    Format (Annex IB §B):
      File = TLV records concatenated
      Record = TAG (1 byte) | LEN (2 bytes BE) | VALUE (LEN bytes)

    TREP'ler için ayrı parser fonksiyonları çağırılır.
    """
    if len(raw) < 16:
        raise DddParseError("Dosya çok kısa — DDD değil")

    cursor = 0
    sofor_kart_no = ""
    sofor_ad = None
    daily_activities: List[DailyActivity] = []
    vehicles: List[VehicleUsage] = []
    warnings: List[str] = []

    while cursor < len(raw) - 3:
        tag = raw[cursor]
        length = struct.unpack(">H", raw[cursor + 1:cursor + 3])[0]
        if cursor + 3 + length > len(raw):
            warnings.append(f"Tag {tag:02x} length aşkın — kalan atlanıyor")
            break
        value = raw[cursor + 3:cursor + 3 + length]
        cursor += 3 + length

        if tag == TREP_DRIVER_IDENTIFICATION:
            kart, ad = _parse_driver_id(value)
            sofor_kart_no = kart
            sofor_ad = ad
        elif tag == TREP_DRIVER_ACTIVITY:
            day_list = _parse_driver_activity(value)
            daily_activities.extend(day_list)
        elif tag == TREP_VEHICLES_USED:
            v_list = _parse_vehicles_used(value)
            vehicles.extend(v_list)
        # Diğer TREP'leri atla (TREP 02, 04, 05, 08, vs.)

    if not sofor_kart_no:
        raise DddParseError("Şoför kart kimliği bulunamadı (TREP 03)")

    return DddParseResult(
        sofor_kart_no=sofor_kart_no,
        sofor_ad_soyad=sofor_ad,
        daily_activities=daily_activities,
        vehicles_used=vehicles,
        parsing_warnings=warnings,
    )


def _parse_driver_id(data: bytes) -> tuple[str, Optional[str]]:
    """TREP 03 minimal parse: kart numarası + ad-soyad (varsa).

    Annex IB §A1: Card identification — driverCardIdentification
    Bu fonksiyon SADELEŞTİRİLMİŞ; gerçek implementasyon Annex tablolarına
    bakmalı. Test ile fixture üzerinden doğrulanır.
    """
    # Sahte minimal layout (gerçeği test fixture ile ayarlanır):
    # bytes [0:16]: kart no ASCII (boşluk padded)
    # bytes [16:48]: ad-soyad UTF-8 (boşluk padded)
    if len(data) < 16:
        return "", None
    kart_no = data[0:16].decode("latin-1", errors="ignore").strip("\x00 ")
    ad = None
    if len(data) >= 48:
        ad = data[16:48].decode("latin-1", errors="ignore").strip("\x00 ")
    return kart_no, ad or None


def _parse_driver_activity(data: bytes) -> List[DailyActivity]:
    """TREP 06: günlük aktivite timeline.

    Format (Annex IB §A1 - CardActivityDailyRecord):
      Header: timestamp (4 byte epoch) + activity_distance (2 byte km)
      ActivityChangeInfo: 2 byte (slot + status + driver + activity + time)

    Bu sadeleştirilmiş bir simulasyon — gerçek implementasyonda 4-bit
    nibble decode (Annex IB Table A.X) gerekir.
    """
    days: List[DailyActivity] = []
    cursor = 0
    while cursor + 6 <= len(data):
        epoch = struct.unpack(">I", data[cursor:cursor + 4])[0]
        distance = struct.unpack(">H", data[cursor + 4:cursor + 6])[0]
        cursor += 6
        # Activity changes: 2-byte each, until next day marker
        day = DailyActivity(
            tarih=datetime.fromtimestamp(epoch, tz=timezone.utc).date(),
            distance_km_at_end=float(distance),
        )
        # ActivityChangeInfo loop — bir sonraki day-header'a kadar
        chunk_start_min = 0
        chunk_activity = ACTIVITY_REST
        while cursor + 2 <= len(data):
            word = struct.unpack(">H", data[cursor:cursor + 2])[0]
            cursor += 2
            # bit 12-13: activity; bit 0-10: minute in day
            new_activity = (word >> 12) & 0x03
            new_minute = word & 0x07FF
            # Önceki chunk'ı bitir
            duration = new_minute - chunk_start_min
            if duration > 0:
                day.chunks.append(ActivityChunk(
                    activity=chunk_activity,
                    minute_in_day=chunk_start_min,
                    duration_min=duration,
                ))
            chunk_activity = new_activity
            chunk_start_min = new_minute
            if new_minute == 0 and chunk_activity == ACTIVITY_REST:
                # day terminator (heuristic)
                break
        days.append(day)
    return days


def _parse_vehicles_used(data: bytes) -> List[VehicleUsage]:
    """TREP 07: kullanılan araçlar — VIN + tarih aralığı.

    Annex IB §A1 - CardVehicleRecord:
      vehicleOdometerBegin (3 byte)
      vehicleOdometerEnd (3 byte)
      vehicleFirstUse (4 byte epoch)
      vehicleLastUse (4 byte epoch)
      vehicleRegistration (1 byte nation + 14 byte plaka)
      vin (17 byte) — opsiyonel
    """
    vehicles: List[VehicleUsage] = []
    record_size = 18 + 14 + 17  # 49 byte per record (minimal)
    cursor = 0
    while cursor + 32 <= len(data):
        try:
            odo_begin = int.from_bytes(data[cursor:cursor + 3], "big")
            odo_end = int.from_bytes(data[cursor + 3:cursor + 6], "big")
            first_use = struct.unpack(
                ">I", data[cursor + 6:cursor + 10]
            )[0]
            last_use = struct.unpack(
                ">I", data[cursor + 10:cursor + 14]
            )[0]
            plaka_raw = data[cursor + 15:cursor + 29].decode(
                "latin-1", errors="ignore"
            ).strip("\x00 ")
            vin = data[cursor + 29:cursor + 46].decode(
                "latin-1", errors="ignore"
            ).strip("\x00 ") if cursor + 46 <= len(data) else None
            cursor += record_size
            vehicles.append(VehicleUsage(
                vin=vin or None,
                plaka=plaka_raw or None,
                sefer_baslangic=datetime.fromtimestamp(first_use, tz=timezone.utc),
                sefer_bitis=datetime.fromtimestamp(last_use, tz=timezone.utc),
                start_km=odo_begin,
                end_km=odo_end,
            ))
        except (struct.error, ValueError):
            break
    return vehicles


# ── Süre özetlemesi ───────────────────────────────────────────────────
def summarize_daily(day: DailyActivity) -> dict:
    """Bir günün chunk'larından toplam süre dakikalarını çıkar."""
    totals = {"rest": 0, "available": 0, "work": 0, "driving": 0}
    keys = {0: "rest", 1: "available", 2: "work", 3: "driving"}
    for c in day.chunks:
        totals[keys.get(c.activity, "rest")] += c.duration_min
    return totals
```

### 5.2 Test

`test_ddd_parser.py`:
- TLV record parse (mock bytes ile)
- TREP 03: kart no extract
- TREP 06: aktivite timeline reconstruction
- TREP 07: VIN + plaka parse
- Bozuk/kısa dosya → DddParseError
- summarize_daily — toplam dakikalar
- Annex IB Türk plaka edge case (TR + plaka)

> **NOT:** Gerçek DDD fixture'ları üretim ortamından sentetik (anonim)
> olarak v1 release'de hazırlanmalı. v1'de minimal mock-byte fixture'ları
> ile parser doğrulanır; gerçek dosya testi v1.1'de.

---

## 6. M.3 — Upload endpoint + frontend

### 6.1 `app/api/v1/endpoints/tachograph.py`

```python
@router.post("/upload", response_model=TachographUploadResponse)
async def upload_ddd(
    file: UploadFile = File(...),
    sofor_id_override: Optional[int] = None,  # eşleşmeyen kart için manuel
    current_admin: Annotated[Kullanici, Depends(
        require_yetki(["admin", "super_admin", "fleet_manager", "takograf_yukle"])
    )],
) -> TachographUploadResponse:
    """DDD dosya yükle, parse et, tachograph_records'a yaz, ihlal tara."""
    if not settings.TACHOGRAPH_ENABLED:
        raise HTTPException(503, "Takograf modülü devre dışı")
    if not file.filename.lower().endswith(".ddd"):
        raise HTTPException(400, "Yalnız .ddd uzantılı dosya kabul edilir")
    raw = await file.read()
    if len(raw) > settings.TACHOGRAPH_MAX_FILE_BYTES:
        raise HTTPException(413, "Dosya çok büyük")

    try:
        parsed = await asyncio.to_thread(parse_ddd_bytes, raw)
    except DddParseError as exc:
        raise HTTPException(422, f"DDD parse hatası: {exc}")

    service = TachographService()
    result = await service.ingest(
        parsed, filename=file.filename, user_id=current_admin.id,
        sofor_id_override=sofor_id_override,
    )
    return TachographUploadResponse.from_ingest(result)


@router.get("/records", response_model=List[TachographRecordResponse])
async def list_records(...): ...

@router.get("/violations", response_model=List[ViolationResponse])
async def list_violations(...): ...

@router.get("/unmatched", response_model=List[UnmatchedRecord])
async def list_unmatched(...): ...
```

### 6.2 Frontend `TakografPage.tsx`

```tsx
export default function TakografPage() {
    const tabs: ('upload' | 'records' | 'violations' | 'unmatched')[] = [
        'upload', 'records', 'violations', 'unmatched'
    ]
    return (
        <div className="space-y-6 p-6">
            <Header />
            <TabBar tabs={tabs} />
            {active === 'upload' && <TachographUpload />}
            {active === 'records' && <RecordsTable />}
            {active === 'violations' && <ViolationsList />}
            {active === 'unmatched' && <UnmatchedRecordsPanel />}
        </div>
    )
}
```

`TachographUpload.tsx`: drag-drop area + progress + sonuç özet card.

### 6.3 Test

- `test_tachograph_upload.py` — 4 senaryo (happy, invalid file, parse error, RBAC 403)
- Vitest 2 dosya (upload + violations panel)

---

## 7. M.4 — AETR Kural Motoru

### 7.1 `app/core/services/aetr_rule_engine.py`

```python
"""Feature M.4 — AETR/AB sürüş süresi kural motoru.

Tek dosya DDD parse edildikten sonra çağrılır → ihlal listesi döner.
Kural sınırları config'ten alınır (üretim için sıkı, test için override).
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List

# Default AETR/AB limitleri (dakika)
DAILY_DRIVING_MAX = 9 * 60
DAILY_DRIVING_EXTENDED = 10 * 60  # haftada 2× izin
WEEKLY_DRIVING_MAX = 56 * 60
BIWEEKLY_DRIVING_MAX = 90 * 60
CONTINUOUS_DRIVING_MAX = 4.5 * 60     # 4.5 sa sonra mola
BREAK_MIN = 45                         # min mola
BREAK_SPLIT_MIN_FIRST = 15
BREAK_SPLIT_MIN_SECOND = 30
DAILY_REST_MIN = 11 * 60
WEEKLY_REST_MIN = 45 * 60


@dataclass
class Violation:
    sofor_id: int
    tarih: date
    ihlal_tipi: str           # "daily_driving_excess", "break_insufficient", vb.
    severity: str             # low/medium/high/critical
    aktual_deger: float
    limit_deger: float
    birim: str                # "dk", "sa"
    aciklama: str


def detect_daily_driving_violations(
    daily_minutes: int, *, tarih: date, sofor_id: int,
    extended_allowed_this_week: bool = False,
) -> List[Violation]:
    """Günlük sürüş süresi 9 (veya 10) saati aştı mı?"""
    out: List[Violation] = []
    limit = DAILY_DRIVING_EXTENDED if extended_allowed_this_week else DAILY_DRIVING_MAX
    if daily_minutes > limit:
        delta_pct = (daily_minutes - limit) / limit
        severity = (
            "critical" if delta_pct > 0.3
            else "high" if delta_pct > 0.1
            else "medium"
        )
        out.append(Violation(
            sofor_id=sofor_id, tarih=tarih,
            ihlal_tipi="daily_driving_excess",
            severity=severity,
            aktual_deger=daily_minutes,
            limit_deger=limit,
            birim="dk",
            aciklama=f"Günlük {daily_minutes // 60}sa {daily_minutes % 60}dk sürüş; max {limit // 60}sa",
        ))
    return out


def detect_break_violations(
    activity_chunks: list, *, tarih: date, sofor_id: int,
) -> List[Violation]:
    """4.5 sa kesintisiz sürüş sonrasında 45 dk mola alındı mı?"""
    out: List[Violation] = []
    cont = 0   # birikmiş kesintisiz sürüş dakikası
    for c in activity_chunks:
        if c.activity == 3:  # DRIVING
            cont += c.duration_min
            if cont > CONTINUOUS_DRIVING_MAX:
                out.append(Violation(
                    sofor_id=sofor_id, tarih=tarih,
                    ihlal_tipi="continuous_driving_excess",
                    severity="high",
                    aktual_deger=cont,
                    limit_deger=CONTINUOUS_DRIVING_MAX,
                    birim="dk",
                    aciklama=f"4.5 sa kesintisiz sürüş aşıldı: {cont} dk",
                ))
                cont = 0  # tekrar saymaya başla
        elif c.activity == 0 and c.duration_min >= BREAK_MIN:
            # Geçerli tek-parça mola → counter sıfırla
            cont = 0
        # 15+30 split mola için ekstra mantık (v2'de)
    return out


def detect_daily_rest_violations(
    rest_minutes: int, *, tarih: date, sofor_id: int,
) -> List[Violation]:
    if rest_minutes < DAILY_REST_MIN:
        return [Violation(
            sofor_id=sofor_id, tarih=tarih,
            ihlal_tipi="daily_rest_insufficient",
            severity="medium",
            aktual_deger=rest_minutes,
            limit_deger=DAILY_REST_MIN,
            birim="dk",
            aciklama=f"Günlük dinlenme {rest_minutes // 60}sa; min {DAILY_REST_MIN // 60}sa",
        )]
    return []


def detect_weekly_driving_violations(
    week_minutes: int, *, week_end: date, sofor_id: int,
) -> List[Violation]:
    if week_minutes > WEEKLY_DRIVING_MAX:
        delta_pct = (week_minutes - WEEKLY_DRIVING_MAX) / WEEKLY_DRIVING_MAX
        sev = "critical" if delta_pct > 0.15 else "high"
        return [Violation(
            sofor_id=sofor_id, tarih=week_end,
            ihlal_tipi="weekly_driving_excess",
            severity=sev,
            aktual_deger=week_minutes,
            limit_deger=WEEKLY_DRIVING_MAX,
            birim="dk",
            aciklama=f"Haftalık {week_minutes // 60}sa; max 56sa",
        )]
    return []


def detect_all_violations(
    *, daily_summary: dict, activity_chunks: list,
    sofor_id: int, tarih: date,
) -> List[Violation]:
    out: List[Violation] = []
    out.extend(detect_daily_driving_violations(
        daily_summary["driving"], tarih=tarih, sofor_id=sofor_id,
    ))
    out.extend(detect_break_violations(
        activity_chunks, tarih=tarih, sofor_id=sofor_id,
    ))
    out.extend(detect_daily_rest_violations(
        daily_summary["rest"], tarih=tarih, sofor_id=sofor_id,
    ))
    # Haftalık check ayrı çağrılır (week boundary detection gerek)
    return out
```

### 7.2 Test

- Günlük 9 sa tam → OK; 9sa 1dk → low; 11sa → critical
- 4.5 sa kesintisiz sürüş + 30 dk mola → break violation (45 dk eksik)
- 4.5 sa + 45 dk mola + 4.5 sa → OK (counter reset)
- Haftalık 56sa tam → OK; 56sa 5dk → high
- 15 günlük 90 sa testi (v2 — şimdilik open note)

8 unit test minimum.

---

## 8. M.5 — Sefer eşleşme algoritması

### 8.1 `tachograph_service.py`'da match fonksiyonu

```python
async def match_record_to_sefer(
    uow, *, record_id: int, tolerance_km: float = 20,
) -> tuple[Optional[int], int]:
    """Tachograph record'u en uygun Sefer'e eşleştir.

    Returns: (sefer_id, score). Score < 60 ise None döner.
    """
    from sqlalchemy import text
    rec = await uow.session.get(TachographRecord, record_id)
    if not rec:
        return None, 0
    rows = (await uow.session.execute(text("""
        SELECT id, mesafe_km, saat FROM seferler
        WHERE sofor_id = :sofor_id AND tarih = :tarih
          AND is_deleted = FALSE
        ORDER BY id
    """), {"sofor_id": rec.sofor_id, "tarih": rec.tarih})).mappings().all()

    best: tuple[int, int] = (None, 0)
    for r in rows:
        score = 50  # aynı sofor + aynı tarih
        if rec.total_mesafe_km and r["mesafe_km"]:
            dist_diff = abs(rec.total_mesafe_km - r["mesafe_km"])
            if dist_diff < tolerance_km:
                score += 30
            elif dist_diff < tolerance_km * 2:
                score += 15
        # +20 if arac eşleşmesi varsa
        # +10 if saat tolerans içindeyse (v2 — saat tachograph timeline'dan)
        if score > best[1]:
            best = (int(r["id"]), score)

    if best[1] >= 60:
        return best
    return None, 0
```

### 8.2 Test

- Aynı sofor + tarih + mesafe match → score ≥ 80
- Mesafe farklı → tolerance dışında match yok
- Sefer yok → None
- Birden fazla sefer aynı tarih → en yüksek skor seçilir

---

## 9. M.6 — Cross-motor entegrasyon

### 9.1 D.4 maintenance_factor genişlemesi

`app/core/ml/vehicle_health_factor.py`'ye `agresif_surus_penalty` ekle:

```python
AGRESIF_DRIVE_PENALTY_PER_EVENT = 0.001   # her event %0.1 ekstra
AGRESIF_PENALTY_CAP = 1.05                # max %5

def _aggressive_driving_factor(uow, arac_id: int, days: int = 90) -> float:
    """Son N gün için araç bazlı agresif sürüş penalty."""
    # tachograph_records → SUM(agresif_fren + agresif_hizlanma) WHERE arac_id
    # → bonus = min(cap, count × per_event)
    ...

# compute_maintenance_factor:
# raw = base × ariza × acil × aggressive_drive_factor
```

### 9.2 A koçluk auto-insight

`DriverCoachingEngine`'e yeni insight kategorisi: "AETR ihlali":

```python
async def detect_aetr_pattern_insights(sofor_id: int) -> List[CoachingInsight]:
    """Son 30 gün AETR ihlal sayısı ≥ 3 → otomatik koçluk insight üret."""
    # tachograph_violations COUNT WHERE sofor_id + son 30g
    # → category="aetr_uyum", pattern="Mola eksiği tekrarı",
    #    suggestion="4.5 sa sonra zorunlu mola; mobil hatırlatma kullan"
```

### 9.3 B hırsızlık kanıt

`fuel_theft_classifier` evidence'a tachograph link ekle:

```python
# Investigation create sırasında:
# Sefer ile eşleşmiş tachograph_record varsa
# evidence_files'a "tachograph://record/{id}" link ekle
# UI: detay dialog'da "Takograf timeline'ı gör" butonu
```

### 9.4 Sofor.score auto-component artışı

Mevcut `get_score_breakdown`'da auto_weight=0.5 → 0.7 olur. Auto-component:
```
0.4 × yakit_score_pct
+ 0.3 × tachograph_compliance_score   # YENİ: 1 - violations / total_days
+ 0.3 × agresif_drive_score           # YENİ: 1 - events / km
```

### 9.5 E.4 compliance heatmap

`compliance_scanner`'a yeni tip: `tachograph_aetr`:
```python
items.append(ComplianceItem(
    entity_type="sofor", entity_id=...,
    plaka=..., field="aetr",
    expiry_date=...,  # son ihlal tarihi
    days_until=days_since_last_violation,
    risk_level=...,
))
```

### 9.6 Test

Her motor için 1-2 entegrasyon testi:
- D.4: agresif sürüş eklenince factor artıyor mu?
- A: 3 ihlal → coaching insight üretildi mi?
- Sofor.score: auto ağırlık 0.7 ile hesaplama doğru mu?

8 cross-motor integration testi.

---

## 10. M.7 — E.4 Compliance Heatmap entegrasyonu

E.4 v1 planı muayene'yi kapsıyordu; M ile aynı zamanda gelişiyor:

```
E.4 v1 (muayene)               → E.4 v2 (muayene + AETR)
  - araclar.muayene_tarihi      - hepsi aynı +
  - dorseler.muayene_tarihi     + tachograph_violations son 30g
  - soforler.ehliyet_sinifi     + sofor başına ihlal trendi
```

`ComplianceItem` schema'sı genişler (field değeri "aetr" olabilir).

### 10.1 Test

- E.4 endpoint takograf ihlali olan şoförü dahil eder mi?
- Filter `?include_aetr=true` çalışıyor mu?

---

## 11. M.8 — Günlük cron task

### 11.1 `app/workers/tasks/tachograph_tasks.py`

```python
@celery_app.task(bind=True, name="tachograph.daily_analysis")
def daily_analysis(self) -> dict:
    """Her sabah 04:00 UTC: son 24g tachograph_records için:
    1. Eşleşmemiş kayıtları otomatik sefer'e bağla (retry)
    2. Haftalık 56sa kontrolü (gün-bazında değil hafta-bazında)
    3. Repeat-offender şoförler için A koçluk insight üret
    4. Critical ihlaller için Telegram OPS alarm (B.5 pattern)
    """
    ...
```

Beat schedule:
```python
"tachograph-daily-analysis": {
    "task": "tachograph.daily_analysis",
    "schedule": crontab(hour=4, minute=0),
},
```

### 11.2 Test

- `_run_daily_analysis()` boş tablo için çalışır mı?
- Beat schedule kayıtlı mı?

---

## 12. Konfig + feature flag

```python
# app/config.py
# Feature M — Takograf
TACHOGRAPH_ENABLED: bool = True
TACHOGRAPH_MAX_FILE_BYTES: int = 5 * 1024 * 1024  # 5 MB DDD
TACHOGRAPH_AUTO_MATCH_TOLERANCE_KM: float = 20.0
TACHOGRAPH_VIOLATION_ALARM_ENABLED: bool = True   # critical → Telegram OPS

# AETR override (test için)
AETR_DAILY_DRIVING_MAX_MIN: int = 540    # 9 sa
AETR_WEEKLY_DRIVING_MAX_MIN: int = 3360  # 56 sa
```

---

## 13. Yol haritası

| Sıra | Alt görev | Çıktı | Test | Tahmini |
|---|---|---|---|---|
| M.1 | Migration + ORM models | 4 tablo + 2 alan | 1 migration check | 1.5 sa |
| M.2 | DDD parser servisi | parse_ddd_bytes + 4 TREP | 7 unit (mock fixtures) | 3 sa |
| M.3 | Upload endpoint + frontend | /tachograph/upload + TakografPage | 4 integration + 2 vitest | 3 sa |
| M.4 | AETR kural motoru | detect_*_violations × 4 | 8 unit | 2 sa |
| M.5 | Sefer eşleşme | match_record_to_sefer | 4 unit + 1 integration | 1.5 sa |
| M.6 | Cross-motor entegrasyon | D.4 + A + B + sofor.score + E.4 | 8 integration | 3 sa |
| M.7 | E.4 compliance entegrasyonu | compliance_scanner extended | 2 integration | 1 sa |
| M.8 | Daily cron task | beat + analyze + alarm | 2 integration | 1.5 sa |

**Toplam tahmin:** ~17 saat.

### Gating

- M.1 → M.2 (parser tabloya yazar)
- M.2 → M.3, M.4, M.5 (paralel başlatılabilir)
- M.3+M.4+M.5 → M.6 (cross-motor için tüm veriler hazır olmalı)
- M.6 → M.7 + M.8

---

## 14. Riskler ve azaltma

| Risk | Etki | Azaltma |
|---|---|---|
| DDD format farklı versiyonları (Gen1 vs Gen2) | Parser başarısız | TLV parser format-agnostic; bilinmeyen TAG'leri atlar |
| Türkçe karakter (ş/ı/Ö) ad-soyad bozulması | PII kayıp | Latin-1 decode + UTF-8 fallback; bozuk char "?" ile gösterilir |
| Çoklu şoför aynı araçta (2 şoförlü TIR) | Eşleşme yanlış | Tachograph multi-driver TREP'i v1'de atlanır (open note §17) |
| Şoför kart kayıp/yenileme | Geçmiş veri sahipsiz | tachograph_kart_history tablosu (M.1) |
| Gerçek DDD fixture yok (test) | Parser doğruluğu düşük | Sentetik mock-byte fixtures v1; gerçek dosya v1.1 |
| 5 MB üzeri dosya yüklenir | Sunucu DOS | TACHOGRAPH_MAX_FILE_BYTES + 413 |
| Yanlış sofor'a kart atanır | İhlaller yanlış kişiye | Upload öncesi UI'da "Şoför doğrula" adımı |
| 15-günlük 90sa kuralı v1'de yok | Eksik compliance | Open note §17 v1.1 |
| Critical alarm flood (yeni filo) | OPS bot spam | Rate limit + per-sofor 24sa cooldown |

---

## 15. PII ve güvenlik

- Şoför kart no PII — DB'de düz tutulur (encryption v2'de hedeflenebilir)
- Şoför ad-soyad parse edilir ama **yalnız eşleşmeyen kart uyarı mesajında**
  gösterilir; eşleşmiş kayıtlarda Sofor.ad_soyad kullanılır.
- Audit log: `tachograph_uploaded`, `tachograph_record_matched`,
  `tachograph_violation_detected` (sofor_id + ihlal_tipi; PII text yok).
- RBAC: `takograf_yukle` izni operatör için; `super_admin` + `fleet_manager`
  okuyabilir.
- LLM çağrısı **YOK** — tüm hesap deterministik.

---

## 16. Acceptance criteria

- [ ] `POST /tachograph/upload` happy path 200 → record created
- [ ] DDD parse error → 422 + Türkçe mesaj
- [ ] Eşleşmeyen kart → response'da `unmatched_card_warning` field
- [ ] AETR ihlal 4 tip için (daily/weekly/break/rest) detect doğru
- [ ] Sefer eşleşme: aynı sofor + tarih + mesafe ±20km → score ≥ 80
- [ ] D.4: agresif sürüş eventleri factor'ı %5'e kadar artırır
- [ ] A koçluk: 3+ ihlal → otomatik insight üretilir
- [ ] B investigations: tachograph evidence link eklenir
- [ ] Sofor.score auto-weight 0.7 (eskiden 0.5)
- [ ] E.4 compliance heatmap takograf ihlali olan şoförleri içerir
- [ ] Cron task daily_analysis çalışır
- [ ] Critical ihlal → Telegram OPS alarm (B.5 pattern reuse)
- [ ] Feature flag `TACHOGRAPH_ENABLED=False` → tüm endpoint 503
- [ ] RBAC: izleyici → 403
- [ ] Frontend `/admin/takograf` route yalnız yetkili görür
- [ ] Tüm yeni unit/vitest yeşil
- [ ] `ruff check --ignore=E501`, `tsc`, `vite build` clean
- [ ] Alembic 0015 upgrade + downgrade test

---

## 17. Açık notlar (uygulama sırasında karara bağlanacak)

1. **Çoklu şoför TIR** (2 şoförlü uzun mesafe). Annex IB Slot 1/2 ayrımı
   var; v1'de yalnız Slot 1 (asıl şoför) parse edilir. v1.1'de Slot 2 da
   eklenir → her ikisi için ayrı tachograph_record.

2. **15-günlük 90 sa kuralı**. Haftalık kontrol var; 2-haftalık (90 sa
   biriken) kontrol v1.1'e bırakıldı. Pratik etki: critical ihlal
   gecikebilir (haftalık 56sa zaten yakalıyor).

3. **Smart-Tachograph Gen 2 ek alanlar** (2020+ AB direktifi). v1'de
   eski + yeni format aynı parser ile işlenir (TLV format-agnostic).
   Gen 2 ek TREP'ler (örn. otomatik konum log) v2'de.

4. **Türk plaka ↔ AB plaka standartı**. Türkiye'de plaka 7 char; AB'de 14
   char alan rezervli. v1'de 14 byte'ı strip + trim ile parse; "34 ABC 123"
   formatı korunur.

5. **DDD fixture üretimi**. Üretim DDD'leri kişisel PII içerir; v1 unit
   test'leri sentetik mock-byte fixtures. v1.1'de operasyondan anonim
   örnek alınıp `tests/fixtures/tachograph/` altına eklenir.

6. **OCR microservice precedent**. Plan §3'te DDD parser pure-Python.
   Eğer ileride C-extension performans gerektirse OCR microservice gibi
   ayrı service'e taşınabilir (paralel processing için).

7. **Mobil upload**. Şu an UI sadece desktop drag-drop. Şoför'ün cep
   telefonundan upload yapması için mobile-optimized component (PWA)
   gerekebilir. v1.1.

8. **Yasal compliance gözden geçirme**. AETR/AB kural limitleri Türkiye
   uyumu için KGM/TKHK ile son kontrol yapılmalı. Konfig'e taşıdığımız
   limitler kolayca güncellenebilir.

Bu 8 nokta M.1 başlangıcında doğrulanır, ardından plan kilitlenir.
