# TASKS/ — LOJINEXT Modüler Monolit Refaktörü Görev Dizini

> **Önce `TASKS/STATUS.md`'yi oku.** Hangi modülün sırada olduğunu, oturum-hijyeni kuralını (bir oturum = bir modül) ve bilinen açık notları orada bulursun — bu dosyayı (README) baştan sona yeniden okumana gerek yok.

## DURMA NOKTASI

**Hiçbir görev dosyası, kullanıcının o dosyaya özel onayı olmadan uygulanmaz.** Bu dizin tamamen plandır. Bir görev dosyasını uygulamaya başlamadan önce:
1. Kullanıcıdan o spesifik dosya için onay al.
2. İlgili modül görev dosyasıysa, önce `app/modules/<x>/CLAUDE.md`'yi Read ile oku (henüz yoksa, o görev dosyasının 7. adımı önce onu oluşturur).
3. Görev tamamlanınca gerçek CI koşumu (lokal + pipeline) ile doğrula — "muhtemelen geçti" kabul edilmez, kanıt şart (bkz. proje kuralı `no_error_no_fake_code`).

## FAZ Tablosu (giriş/çıkış kriterleri)

| FAZ | İçerik | GİRİŞ | ÇIKIŞ |
|---|---|---|---|
| **0** Ölçüm & emniyet | baseline JSON, import-linter rapor modu, açık soru doğrulamaları | Bu planın onayı | baseline repo'da; main YEŞİL |
| **1** Kod sınırları | modül iskeleti, taşıma dalgaları, import-linter gate, davranışsal testler | FAZ0 çıkışı | 15 modül + shared_kernel erimesi + platform-infra registry finali; gate 5 ardışık gün yeşil |
| **2** Veri sınırları | 14 şema, PG rolleri, fk_registry, güvenlik state→Redis | FAZ1 çıkışı (5 gün yeşil) | 43 tablo modül şemalarında; rol ihlali runtime'da permission-denied |
| **3** Dil geçişi (BAĞIMSIZ) | kod/DB/API → İngilizce; UI i18n TR/EN kalır | FAZ2 çıkışı + prod satır ölçümü | eski anahtar okuması 0 (≥14 gün); contract/drop |
| **4** Sıkılaştırma | baseline sıfırlama, shim temizliği, retro | FAZ3 çıkışı | kontratlar strict, retro raporu |

Sınır-enforcement (FAZ1-2) ile dil geçişi (FAZ3) **ASLA aynı PR'da değil**.

## Dosya Dizini

```
faz0-baseline-olcum-ve-rapor-modu.md          # FAZ0 — tek görev dosyası
faz1-registry-iskelet-ve-shim.md              # FAZ1 çatı: ModuleSpec + registry
faz1-import-linter-baseline-ve-gate.md        # FAZ1 çatı: kontrat + baseline
faz1-davranissal-mimari-testler.md            # FAZ1 çatı: pytest-archon + el yazması
faz1-dosya-kalite-ve-kisalik-gate.md          # FAZ1 çatı: LOC/CC/kısalık kuralı
faz1-claude-md-per-module-template.md         # FAZ1 çatı: modül CLAUDE.md şablonu
modules/
  location.md notification.md fleet.md fuel.md driver.md auth-rbac.md
  route-simulation.md anomaly.md import-excel.md reports.md
  analytics-executive.md ai-assistant.md prediction-ml.md trip.md
  admin-platform.md shared-kernel.md platform-infra.md
faz2-schema-per-module-postgres.md
faz2-db-rol-izolasyonu-ve-read-model-grantlari.md
faz2-guvenlik-state-redis.md
faz3-dil-gecisi-kod-db-api-ingilizce.md
faz4-sikilastirma-ve-kapanis.md
bug-connection-pool-leak-under-load.md        # BAĞIMSIZ bug — dalga sırası dışında, herhangi bir oturumda ele alınabilir
```

## Modül Taşıma Dalga Sırası (FAZ1, bağımlılık az→çok)

```
1. location          (pilot — en küçük: 5 dosya/1.695 LOC, 2 tablo, in=3/out=11)
2. notification       (in=8/out=4, dış bağımlılığı düşük)
3. fleet               (out=4/in=19 — sağlıklı sağlayıcı, erken taşınmalı)
4. fuel
5. driver
6. auth-rbac           (out=1/in=17 — en sağlıklı sağlayıcı)
7. route-simulation
8. anomaly
9. import-excel
10. reports
11. analytics-executive
12. ai-assistant
13. prediction-ml      (out=27 — en dolaşık tüketici, geç taşınmalı)
14. trip               (out=20/in=18 — en karmaşık split, sefer_write_service dahil)
15. admin-platform
16. shared-kernel       (erime — modül taşımaları bittikçe küçülür, FAZ1 sonunda son hâli)
17. platform-infra      (registry finali — main.py/container.py/api.py'nin kalıntısı)
```

Her dalga: 1 modül = 1 PR = 1 onay turu. Bir dalga başlamadan önceki dalganın CI'ı yeşil olmalı.

## Kaynak

Tüm sayılar `MEMORY/PROGRESS.md`'de detaylandırılmıştır — bu görev dosyalarındaki her rakam oradan gelir, tahmin edilmemiştir.
