# FAZ4 — Sıkılaştırma ve Kapanış

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz.

**Amaç:** FAZ1-3 boyunca biriken geçici gevşekliği (shim'ler, dondurulmuş baseline'lar, `ignore_imports` listesi) sıfırlamak; dağıtık-monolit tuzağına düşülmediğini geriye dönük doğrulamak.

**Giriş kriteri:** FAZ3 çıkışı (dil geçişi contract adımı tamamlandı). **Çıkış kriteri:** tüm baseline'lar boş, kontratlar strict, retro raporu yazıldı.

---

## 1. import-linter baseline sıfırlama
`.importlinter`'daki `ignore_imports` listesi (FAZ1'de 181 kenarla başlamıştı) gözden geçirilir — FAZ1-3 boyunca düzeltilen kenarlar zaten `unmatched_ignore_imports_alerting=error` sayesinde otomatik temizlenmiş olmalı (FAZ1 görev dosyasının mekanizması). Kalan varsa, her biri için: ya gerçek bir mimari istisna olarak KALICI kontrata yazılır (gerekçeli, CODEOWNERS onaylı) ya da düzeltilir. Hedef: `ignore_imports` boş VEYA yalnız açıkça gerekçelendirilmiş kalıcı istisnalar.

## 2. Shim temizliği
`arch/quality_baseline.json`'daki `shims` listesi taranır (`faz1-registry-iskelet-ve-shim.md`'de tanımlanan tek-satır shim'ler). Her shim dosyası silinir; hâlâ o eski yola bağımlı test/kod varsa (541 test dosyasından kalan), import yolu güncellenir — shim'siz büyük patlama burada da YASAK, kalan bağımlılıklar teker teker temizlenir.

## 3. xenon bloklayıcı (opsiyonel sıkılaştırma)
FAZ1'de ruff C901 baseline'lıydı (156 mevcut ihlal `noqa` ile). Bu FAZ'da: `xenon --max-absolute B --max-modules A --max-average A app` CI'a EKLENEBİLİR (yalnız yeni kod için — mevcut `noqa`'lı fonksiyonlar dokunulmaz, onların CC azaltımı ayrı, gerekçesiz bir refactor işi olur ve bu planın kapsamı dışındadır).

## 4. Dosya kalite baseline sıfırlama
`arch/quality_baseline.json`'daki `loc_over_500`/`loc_over_1000`/`cc_over_10` listeleri, FAZ1-3 boyunca gerçekleşen split'ler nedeniyle küçülmüş olmalı (her modül görev dosyasının split adımları bu listeyi azaltıyor). FAZ4'te: listede hâlâ kalan dosyalar için YENİ bir split görevi AÇILMAZ (bu FAZ'ın kapsamı temizlik, yeni refactor değil) — kalanlar sonraki bir epik için not edilir.

## 5. Dağıtık-monolit retro kontrol listesi (MEMORY/PROGRESS.md §7 risklerine karşı)
- [ ] shared_kernel dosya sayısı ≤22 mi kaldı (büyümedi mi)? — `git log --follow app/shared_kernel` ile FAZ1'den bugüne diff.
- [ ] Her-şey-event hevesi gerçekleşti mi? — B.2'deki pairwise kararlar (senkron liste) hâlâ geçerli mi, yoksa sessizce hepsi event'e mi çevrildi?
- [ ] FK düşürüldü mü? — `fk_registry.yml`'deki 42 kenar hâlâ 42 mi (azalmadıysa iyi, keyfi düşürülmediyse iyi; artan varsa registry PR süreci çalıştı mı kontrolü).
- [ ] Gereksiz adapter/köprü birikti mi? — kod-kısalığı PR kontrol listesinin (≥2 tüketici testi) her taşıma PR'ında gerçekten uygulandığının örnekleme denetimi (5 rastgele PR).
- [ ] Tek DB instance korundu mu? — event-projeksiyon "şimdi değil" kararının (B.2) hâlâ geçerli olduğu, hiçbir modülün ayrı fiziksel DB'ye geçmediği teyidi.

## 6. Retro raporu
`docs/superpowers/audits/modular-monolith-retro.md`: FAZ0'dan FAZ4'e kadar gerçekleşen sapmalar (planlanan vs gerçekleşen), MEMORY/PROGRESS.md §7'deki 8 riskin her birinin nihai durumu, sonraki olası epikler (ör. gerçek zamanlı anomaly-projeksiyon gerekirse event-projeksiyon işi — B.2'de yazılı tetikleyici).

## Kabul Kriterleri
- [ ] `ignore_imports` boş veya yalnız gerekçeli kalıcı istisnalar
- [ ] Tüm shim'ler silindi
- [ ] Retro kontrol listesinin 5 maddesi de PASS
- [ ] Retro raporu yazıldı ve `MEMORY/PROGRESS.md`'ye link verildi
