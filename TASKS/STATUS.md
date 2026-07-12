# STATUS — Modüler Monolit Refaktörü İlerleme Takibi

> **Bu dosya tek gerçek kaynağıdır.** Yeni bir oturumda "kaldığın yerden devam et" dendiğinde, önce bu dosya okunur — plan tamamının yeniden okunmasına gerek yoktur.

## ⚠️ OTURUM HİJYENİ — HER BİRİMDEN SONRA YENİ OTURUM BAŞLAT

**Bu plan tek oturumda bitmez, bitirilmeye ÇALIŞILMAMALI.** Kural:

1. **Bir oturum = en fazla 1 modül (veya 1 FAZ çatı görevi).** Bir modül PR'ı merge olunca, o oturumu KAPAT (yeni pencere / `/clear` / yeni konuşma).
2. **Yeni oturumda ilk mesaj:** *"TASKS/STATUS.md'ye göre kaldığın yerden devam et."* — yeterlidir. Context şişmeden, önceki oturumun ayrıntılarını yeniden anlatmaya gerek kalmadan devam edilir.
3. **Neden:** Uzun süren tek bir oturum (a) context'i şişirip yanıt kalitesini düşürür, (b) bir hata olduğunda geri almayı zorlaştırır, (c) sizin (kullanıcı) takip edebileceğiniz boyuttan çıkar — tam da şikâyet ettiğiniz sorun. Modül-başına oturum, her PR'ı bağımsız gözden geçirilebilir/geri alınabilir tutar.
4. **Onay yükünü azaltmak isterseniz:** tek tek her modülü onaylamak yerine "sıradaki 3 modülü sırayla uygula, her birinden sonra kısa özet ver" gibi toplu talimat da verilebilir — ama yine de her modül ayrı commit/PR olarak kalır (DURMA NOKTASI ilkesi bozulmaz, yalnız onay istemi gruplanır).

---

## FAZ İlerlemesi

| FAZ | Durum | Not |
|---|---|---|
| **FAZ0** — Baseline & rapor modu | ✅ TAMAMLANDI (2026-07-12) | main yeşil, import-linter rapor adımı CI'da; commit `3840de3`,`72a5fe3`,`3e905a8` |
| **FAZ1** — Kod sınırları (17 kalem) | 🔲 BAŞLAMADI | Aşağıdaki dalga sırası |
| **FAZ2** — Veri sınırları | 🔲 FAZ1'i bekliyor | |
| **FAZ3** — Dil geçişi | 🔲 FAZ2'yi bekliyor | Bağımsız FAZ, sınır-enforcement ile aynı PR'da olmaz |
| **FAZ4** — Sıkılaştırma & kapanış | 🔲 FAZ3'ü bekliyor | |

## FAZ1 — Modül Dalga Sırası (bağımlılık az→çok)

Her satır bağımsız bir PR/onay/oturum birimidir. Sıradaki modül, bir öncekinin PR'ı merge olmadan başlamaz (görev dosyasının "Giriş kriteri"nde yazılı).

| # | Modül/kalem | Görev dosyası | Durum |
|---|---|---|---|
| — | Registry+iskelet+shim deseni (çatı) | `faz1-registry-iskelet-ve-shim.md` | 🔲 |
| — | import-linter baseline→gate (çatı) | `faz1-import-linter-baseline-ve-gate.md` | 🔲 |
| — | Davranışsal mimari testleri (çatı) | `faz1-davranissal-mimari-testler.md` | 🔲 |
| — | Dosya kalite + kısalık gate (çatı) | `faz1-dosya-kalite-ve-kisalik-gate.md` | 🔲 |
| — | Modül CLAUDE.md şablonu (çatı) | `faz1-claude-md-per-module-template.md` | 🔲 |
| 1 | **location** (PİLOT) | `modules/location.md` | 🔲 |
| 2 | notification | `modules/notification.md` | 🔲 |
| 3 | fleet | `modules/fleet.md` | 🔲 |
| 4 | fuel | `modules/fuel.md` | 🔲 |
| 5 | driver | `modules/driver.md` | 🔲 |
| 6 | auth-rbac | `modules/auth-rbac.md` | 🔲 |
| 7 | route-simulation | `modules/route-simulation.md` | 🔲 |
| 8 | anomaly | `modules/anomaly.md` | 🔲 |
| 9 | import-excel | `modules/import-excel.md` | 🔲 |
| 10 | reports | `modules/reports.md` | 🔲 |
| 11 | analytics-executive | `modules/analytics-executive.md` | 🔲 |
| 12 | ai-assistant | `modules/ai-assistant.md` | 🔲 |
| 13 | prediction-ml | `modules/prediction-ml.md` | 🔲 |
| 14 | trip (en karmaşık split) | `modules/trip.md` | 🔲 |
| 15 | admin-platform | `modules/admin-platform.md` | 🔲 |
| 16 | shared-kernel (erime) | `modules/shared-kernel.md` | 🔲 |
| 17 | platform-infra (registry finali) | `modules/platform-infra.md` | 🔲 |

**FAZ1 çıkış kriteri:** yukarıdaki 17 kalemin tamamı + import-linter gate main'de 5 ardışık gün yeşil (bkz. `TASKS/README.md`).

## Bilinen açık notlar (ileride çözülecek, kapsam dışı bırakılmadı)
- `admin_ws.py` dosya-sahipliği vs route-işlev tutarsızlığı — notification (dalga 2) VE admin-platform (dalga 15) dosyalarında işaretli, dalga 2'de karar verilecek.
- `model_manager.py`'deki 9 kırık raw-SQL sitesi (`model_versions` tablosu yok) — prediction-ml (dalga 13) dalgasında düzeltilecek/temizlenecek, ayrı bug-fix.

## Son güncelleme
2026-07-12 — FAZ0 kapandı, FAZ1 henüz başlamadı. Depo şu an **PUBLIC** (kullanıcı kararı, GHCR faturalama sorunu için geçici; iş bitince tekrar private yapılması gerekiyor — bkz. görev dışı hatırlatma).
