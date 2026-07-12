# FAZ1 (çatı) — Davranışsal Mimari Testleri (pytest-archon + el yazması)

> **DURMA NOKTASI:** Bu görev, kullanıcının açık onayı olmadan uygulanmaz.

**Amaç:** import-linter'ın statik-AST körlüğünü kapatmak — dinamik import, ORM nesne sızıntısı, event payload'da ORM taşınması, Celery isim-uzayı ihlali gibi statik grafikte görünmeyen ihlalleri yakalamak. Sert Kısıt 8 (araç seçimi gerekçeli, "ya biri ya öteki" değil).

**Giriş kriteri:** En az 1 modül taşınmış (test edilecek gerçek public.py/events.py olmalı).
**Çıkış kriteri:** 5 test kategorisinin hepsi CI'da çalışıyor, `pytest-archon` kuralları modül sayısı arttıkça genişliyor.

**Araç seçimi gerekçesi:** `MEMORY/PROGRESS.md` §6 — import-linter + pytest-archon (adlandırılmış ArchUnitPython fallback'li). PyTestArch elendi (import-linter'ı tekrarlıyor, komplemanlık sağlamıyor).

---

## 1. pytest-archon kurulumu

`app/requirements-dev.txt`:
```
pytest-archon==0.0.7
```

`app/tests/architecture/test_module_boundaries.py` (dosya adı — henüz yok, bu görev oluşturur):
```python
from pytest_archon import archrule

def test_modules_only_import_public_and_events():
    archrule("module-boundary").match("app.modules.*").should_not_import(
        "app.modules.*.infrastructure"
    ).check("app")
```
Her modül taşındıkça kurallar bu dosyaya eklenir (modül-başına 1 kural bloğu — modül görev dosyalarının "Kabul kriterleri" bölümünde referans verilir).

## 2. ORM model sızıntısı testi (el yazması — hiçbir araç purpose-built değil)

`app/tests/architecture/test_no_orm_leakage.py`:
```python
import ast
from pathlib import Path

def test_public_py_does_not_export_orm_models():
    """public.py dosyaları SQLAlchemy Base alt sınıflarını dışa vermemeli."""
    for public_file in Path("app/modules").glob("*/public.py"):
        tree = ast.parse(public_file.read_text(encoding="utf-8"))
        exported_names = {
            n.name for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
            for n in [node]
        }
        # models.py'deki ORM sınıf adları listesiyle (FAZ1'de üretilecek
        # app/modules/*/infrastructure/models.py taramasından) kesişim kontrolü.
        # Gerçek karşılaştırma listesi, o modülün infrastructure/models.py'sinden
        # import edilerek yapılır — burada placeholder DEĞİL, çalışma zamanı
        # importuyla üretilecek gerçek liste kullanılır.
```
Not: Bu test taslağı FAZ1'in ilk modülü taşınırken tam implementasyona kavuşur (gerçek `Base` sınıf listesiyle); burada iskelet + niyet net.

## 3. Event payload ORM kontrolü

`app/tests/architecture/test_event_payloads_are_dtos.py`: her modülün `events.py`'sindeki dataclass/Pydantic tiplerini toplar, `publish_async`/`publish_simple_async` çağrı sitelerinde geçirilen `data=` argümanının SQLAlchemy `Base` örneği İÇERMEDİĞİNİ doğrular (AST'te `data=dict(...)` veya `data={...}` biçimlerini tarar; ORM instance geçirilen bir alan varsa FAIL). MEMORY/PROGRESS.md §3'teki dürüst not: bu, publish-sitesi başına henüz ölçülmedi — bu test o ölçümü ilk kez yapan mekanizma olacak.

## 4. Dinamik import kaçağı

CI adımı:
```bash
git grep -n "importlib\." app --include="*.py" | grep -v tests
```
Sıfır sonuç beklenir (mevcut kod tabanında zaten yok — bu adım REGRESYON'a karşı). Bulunursa: pytest-archon custom predicate ile o modülün gerçekten kendi sınırları içinde kaldığı doğrulanır (importlib walk).

## 5. Celery isim-uzayı testi

`app/tests/architecture/test_celery_task_namespace.py`:
```python
"""20 task tanımının her biri kendi modülünün task-adı prefix'ini taşımalı."""
EXPECTED_PREFIX = {
    "app.workers.tasks.coaching_tasks": "coaching.",
    "app.workers.tasks.driver_tasks": "driver.",
    "app.workers.tasks.fuel_coverage_check": "monitoring.",  # MEMORY §3'teki gerçek isimlerle
    # ... 20 task'ın tam eşlemesi MEMORY/PROGRESS.md §3 + ilgili modül dosyasından
}
```
Task'lar modüllere taşındıkça (`app.workers.tasks.*` → `app.modules.<x>.infrastructure.tasks`) bu sözlük güncellenir; her modül görev dosyasının kendi bölümünde bu task'ların yeni yolu belirtilir.

## Kabul Kriterleri
- [ ] pytest-archon kurulu, en az 1 kural aktif
- [ ] ORM sızıntısı testi gerçek Base-sınıf listesiyle çalışıyor (placeholder değil)
- [ ] Event payload testi en az 14 publisher sitesini tarıyor (MEMORY §3'teki liste)
- [ ] Dinamik import CI adımı sıfır sonuç veriyor
- [ ] 20 task'ın tamamı isim-uzayı testinde eşleşiyor
