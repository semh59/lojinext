# Modül Görevi: shared_kernel (dalga 16/17 — ERİME, yeni modül DEĞİL)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. **1. Adım:** `app/shared_kernel/CLAUDE.md`'yi Read ile oku (yoksa oluştur).

**Doğa farkı:** Bu bir iş modülü değil — 15 modül taşındıkça geriye kalan, GERÇEKTEN paylaşılan kod. Bu dalga 15 modülün TAMAMI bitince başlar; amaç mevcut 22 dosyayı/5.162 LOC'u YALNIZ KÜÇÜLTMEK (B.1 kuralı: shared_kernel yalnız küçülebilir).

**Giriş kriteri:** admin-platform dalgası (15) tamamlandı — tüm iş modülleri artık `app/modules/` altında. **Çıkış kriteri:** `app/shared_kernel/` dizini yalnız GERÇEKTEN ≥2 modül tarafından kullanılan kod içeriyor; cross-module her yeni giriş CODEOWNERS onaylı.

---

## 1. Mevcut envanter (22 dosya, 5.162 LOC)
```
app/__init__.py
app/core/__init__.py
app/core/entities/__init__.py
app/core/entities/models.py
app/database/models.py               # 1.988 satır — EN BÜYÜK, bkz. madde 3
app/schemas/base.py
app/schemas/api_responses.py         # 846 satır — bkz. madde 4
app/schemas/validators.py
app/core/interfaces/__init__.py
app/core/interfaces/repositories.py
app/core/protocols.py
app/core/errors.py
app/core/exceptions.py
app/core/unit_of_work.py
app/core/services/__init__.py
app/core/utils/__init__.py
app/core/utils/clock.py
app/core/utils/type_helpers.py
app/database/__init__.py
app/database/repositories/__init__.py    # re-export hunisi — bkz. madde 5
app/database/base_repository.py
app/database/unit_of_work.py
```

## 2. Her dosya için ayrı karar (küçültme kararı — büyütme YOK)
Her dosya 15 modül taşınırken zaten "kim import ediyor" ile test edildi (import-linter kontratları). Bu dalgada: dosya ≥2 modül tarafından import ediliyorsa BURADA KALIR; 1 modül tarafından kullanılıyorsa o modüle TAŞINIR (yanlışlıkla shared_kernel'e düşmüş olabilir — `grep -rln "from app.core.X import\|from app.database.X import"` ile gerçek kullanım taranır, varsayılmaz).

## 3. models.py bölünmesi (D.1 risk #1 — en riskli mekanik adım)
`app/database/models.py` (1.988 satır, 43 ORM tablosu, 45 `relationship()`) BU DALGADA modül-başına dağıtılır: her tablo `app/modules/<sahip>/infrastructure/models.py`'ye taşınır (sahiplik MEMORY/PROGRESS.md §2.2 tablosundan — 15 iş modülü + platform şeması). Ortak `Base` sınıfı BURADA (`shared_kernel/infrastructure/base.py`) kalır, her modül ondan miras alır.

**27 çapraz-modül `relationship()`** kaldırılırken lazy-load kırılma riski var — mitigasyon sırası:
1. Önce trip dalgasında yapılan `_with_relations()` indirgemesi (bkz. trip.md madde 5) TÜM modüllerde tekrarlanır — her modülün repository'si kendi joinedload'unu explicit tutar.
2. `relationship(back_populates=...)` çiftleri (ör. `Arac.seferler`↔`Sefer.arac`) iki ayrı modülün models.py'sinde TANIMLANAMAZ (SQLAlchemy kısıtı) — çözüm: FK kolonu kalır (ID referansı), `relationship()` KALDIRILIR, ilgili okuma explicit sorguya (repository metodu) çevrilir. Bu, D.1/1'in önerdiği "önce `_with_relations()`, sonra explicit sorgu" sırasının 2. adımı.
3. Her adımda `alembic check` BOŞ DİFF vermeli (modeller yer değiştiriyor, şema değişmiyor — FAZ2'nin şema taşıması AYRI, burada yalnız Python dosya konumu değişiyor).

## 4. api_responses.py (846 satır, ~40 sınıf) dağıtımı
MEMORY §B.1'deki ölçüm: health/import/notification/maintenance/fuel/weather/route/location/fleet/dorse karışık sınıflar. Her sınıf, hangi modülün response şeması olduğuna göre o modülün `schemas.py`'sine taşınır (ör. `MaintenanceRecordResponse`→fleet, `WeatherDashboardResponse`→route_simulation, `NotificationRuleResponse`→notification). Ortak taban sınıflar (`MessageResponse`, `SuccessCountResponse`, `DeleteResultResponse` gibi jenerik zarflar) BURADA kalır.

## 5. repositories/__init__.py re-export hunisi
MEMORY §2.1'de tespit edilen `database/repositories/__init__.py`'nin 15 modülün repo'sunu re-export etmesi — bu dalgada TAMAMEN SİLİNİR (her modül kendi repository'sini `infrastructure/repository.py`'den doğrudan import eder, merkezi huniye ihtiyaç kalmaz).

## 6. Kabul kriterleri
- [ ] models.py 15+1 hedefe dağıtıldı, her adımda `alembic check` boş-diff
- [ ] 27 çapraz relationship kaldırıldı, explicit sorgulara çevrildi (regresyon testleriyle kanıtlı)
- [ ] api_responses.py 846 satır dağıtıldı, yalnız jenerik zarflar kaldı
- [ ] repositories/__init__.py hunisi silindi
- [ ] Kalan shared_kernel dosya sayısı ≤22 (büyümedi) — FAZ-sonu boyut raporu PROGRESS.md'ye eklendi
