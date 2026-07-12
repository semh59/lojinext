# FAZ1 (çatı) — import-linter Baseline → Gate

> **DURMA NOKTASI:** Bu görev, kullanıcının açık onayı olmadan uygulanmaz.

**Amaç:** FAZ0'da rapor-modunda kurulan import-linter'ı gerçek modül kontratlarıyla donatmak; **181 mevcut çapraz-modül import kenarını** (MEMORY/PROGRESS.md §2.1) `ignore_imports` ile dondurup yalnız YENİ ihlallere karşı gate açmak. Sert Kısıt 2 + 8.

**Giriş kriteri:** FAZ0 çıkışı + en az 1 modül taşınmış olmalı (kontratın test edeceği gerçek bir sınır olmalı).
**Çıkış kriteri:** Gate **5 ardışık gün main'de yeşil**; yeni ihlal sayısı = 0.

---

## Kontrat tasarımı (`.importlinter`, INI — root pyproject.toml yok, ölçüldü)

```ini
[importlinter]
root_package = app

[importlinter:contract:module-independence]
name = Modüller birbirinin iç katmanına giremez, yalnız public/events
type = forbidden
source_modules =
    app.modules.trip
    app.modules.fleet
    app.modules.driver
    app.modules.fuel
    app.modules.location
    app.modules.route_simulation
    app.modules.anomaly
    app.modules.prediction_ml
    app.modules.ai_assistant
    app.modules.import_excel
    app.modules.reports
    app.modules.analytics_executive
    app.modules.notification
    app.modules.auth_rbac
    app.modules.admin_platform
forbidden_modules =
    app.core.container
    app.api.v1.api
ignore_imports =
    # 181 kenarın taşıma anında buraya eklenen listesi — her modül görev
    # dosyasının "Bağlaşıklık karnesi" bölümünden birebir kopyalanır.
    # Örnek biçim:
    # app.modules.trip.application.add_trip -> app.modules.fleet.public

[importlinter:contract:module-layers]
name = Modül-içi katman sırası (api -> application -> domain <- infrastructure)
type = layers
layers =
    api
    application
    domain
    infrastructure
containers =
    app.modules.trip
    app.modules.fleet
    # ... her taşınan modül eklendikçe buraya eklenir

[importlinter:contract:public-surface-only]
name = Modüller arası yalnız public.py + events.py
type = forbidden
source_modules =
    app.modules.trip.application
    app.modules.fleet.application
    # ... (modül ekledikçe genişler)
forbidden_modules =
    app.modules.trip.infrastructure
    app.modules.fleet.infrastructure
    # (kendi modülü hariç — import-linter'ın kendi-modül istisnası kullanılır)
```

## Baseline dondurma (Sert Kısıt 2, somut prosedür)

1. Her modül taşındığında, o modülün "Bağlaşıklık karnesi"nde listelenen import kenarları `ignore_imports`'a eklenir (**dondurma**, silme değil).
2. `unmatched_ignore_imports_alerting = error` (import-linter 2.13 varsayılanı) — bir `ignore_imports` satırı artık gerçek grafikte yoksa (yani o ihlal düzeltildiyse) CI FAIL eder, geliştirici o satırı SİLMEK ZORUNDA kalır. Bu, baseline'ı monoton küçültür; sessizce şişmesini engeller.
3. `lint-imports` gün 1'de `continue-on-error: true` (rapor); tüm 15 modül taşındıktan ve baseline donduktan SONRA `continue-on-error` kaldırılır (gerçek gate).

## Gate'e geçiş kriteri
- Tüm 15 modül + shared_kernel + platform-infra taşınmış.
- `ignore_imports` listesi 181 kenarın (veya taşıma sırasında düzeltilenler çıkarılmış hâliyle daha azının) tam listesini içeriyor — `lint-imports` lokalde 0 rapor-dışı ihlalle temiz.
- `continue-on-error: true` satırı CI workflow'undan kaldırılır.
- 5 ardışık gün main'de bu adım yeşil kalır (flake yok).

## Kabul Kriterleri
- [ ] `.importlinter` üç kontrat tipini de içeriyor (independence/forbidden, layers, public-surface)
- [ ] 181 kenarın tamamı ya düzeltilmiş ya da `ignore_imports`'ta kayıtlı
- [ ] `unmatched_ignore_imports_alerting = error` aktif
- [ ] CI'da gate blocking (continue-on-error kaldırılmış), 5 gün yeşil
