# Tasarım denetimi + istek eşlemesi — 2026-06-25

Yöntem: güncel kod Playwright ile render edildi (kullanıcının Docker image'ından
bağımsız), ekran görüntüleri gerçekten incelendi + kod analizi. Görseller:
`frontend/e2e/reports/design-audit/*.png`. Render harness'i:
`frontend/e2e/tests/_design-audit.spec.ts`.

Not: bazı sayfalar (bakım, monitoring) audit mock'unda `*.map is not a function`
ile düştü — bu **mock veri-sözleşmesi** sorunu (array beklenen yere object verdim),
gerçek bug değil; o sayfalar için kod analizine dayandım.

## İstek → bulgu → önerilen çözüm

### 1+4. Hata/bildirim sayfaları — admin'de birleştir
İki ayrı hata görünümü var:
- `/monitoring` (`MonitoringPage`) — ana app, 3 sekme: Bildirimler, **Hatalar
  (`ErrorEventsTab`)**, Eğitim.
- `/admin/saglik` (`SistemSaglikPage`) — admin, 2 sekme: Sağlık, **Hata Analizi
  (`HataAnaliziTab`)** — bu DAHA gelişmiş: severity filtre, istatistik, "resolve"
  aksiyonu, canlı SSE stream (`errorService.getEvents/getStats/resolveEvent`).

**Çözüm:** canonical = admin `/admin/saglik` Hata Analizi (zengin olan).
`MonitoringPage`'deki `ErrorEventsTab`'ı oraya katıp tekrarı kaldır; live
bildirim akışını da admin sayfasına taşı. Böylece "hata bildirimi admin
panelinde" + "benzer sayfayla birleşsin" tek hamlede karşılanır.
- Dosyalar: `src/pages/MonitoringPage.tsx`, `src/pages/admin/SistemSaglikPage.tsx`,
  `src/components/monitoring/{ErrorEventsTab,NotificationsTab}.tsx`.
- Efor: ORTA.

### 2. Admin panelindeki "bakım" kısayolu kalksın
**Güncel kodda admin panelinde bakım YOK.** `AdminLayout.tsx` `ADMIN_NAV` =
[overview, kullanicilar, roller, ml, konfig, atama, dogruluk, veri, saglik,
bildirimler, analitik] — bakım öğesi yok; `OverviewPage` sadece istatistik
kartları. Yani bu büyük olasılıkla **eski image**'da kalmış; güncel kodda zaten
yok. → Kullanıcı hâlâ görüyorsa ekran görüntüsüyle teyit, yoksa kapandı.
- Efor: DÜŞÜK (veya gereksiz).

### 3. Bakıma muayene (araç + dorse)
`BakimPage` sekmeli (geçmiş/liste/takvim). Muayene verisi backend'de var:
`GET /vehicles/inspection-alerts` (araç; `{expiring, overdue}`),
`InspectionAlertModal` bileşeni mevcut. **Dorse muayenesi için backend endpoint
yok** → eklenmeli.
**Çözüm:** BakimPage'e "Muayene" sekmesi (araç + dorse), expiring/overdue listesi.
- Dosyalar: `src/pages/admin/BakimPage.tsx`, yeni `InspectionTab`, backend dorse
  inspection endpoint.
- Efor: ORTA (backend dorse endpoint dahil).

### 4. Bakım → yakıt tahmini (arıza bildirimini geliştir)
Fuel estimator'da zaten `maint` adjustment factor slot'u var
(`sefer_fuel_estimator.py` step-5: temp/wind/precip/seasonal/driver/vehicle_age/
**maint**). Şu an gerçek bakım/arıza verisiyle beslenmiyor.
**Çözüm:** arıza/bakım kayıtlarını (PERIYODIK + arıza) `maint` faktörüne bağla;
arıza bildirim girişini geliştir ki veri birikip faktör anlamlı olsun.
- Dosyalar: `app/core/services/sefer_fuel_estimator.py` (maint faktör), bakım/arıza
  repo + giriş formu.
- Efor: YÜKSEK (backend + veri akışı).

### 5. Dil tuşu → tema yanına, daha güzel simge
Ekran görüntüsü: sol-alt köşede `LanguageSwitcher` = **globe + "EN" pill**
(çerçeveli), yanında **çıplak ay ikonu** (tema). Stiller uyumsuz.
**Çözüm:** dil tuşunu tema gibi ikon-only yap (örn. bayrak/`Languages` ikonu),
ikisini tutarlı bir grup yap; istenirse üst header'a taşı.
- Dosyalar: `src/layouts/LanguageSwitcher.tsx`, `src/layouts/AppLayout.tsx`.
- Efor: DÜŞÜK.

### 6. Araç ekle / Dorse ekle formları yarım
Ekran görüntüsü (1366×768): `VehicleModal` `max-h-[90vh]` + içte
`overflow-y-auto` scroll **var** (güncel kodda kesilme düzeltmesi zaten mevcut →
gördüğün "yarım" muhtemelen **eski image**). Ama modal viewport'u tepeden-tabana
dolduruyor; son alan footer'a yapışık, sıkışık.
`TrailerModal` container'da `max-h` YOK (sadece body `max-h-[70vh]`).
**Çözüm:** ferahlat — modal `max-h-[85vh]`, footer üstüne boşluk; TrailerModal
container'a `max-h-[90vh]` + tutarlı scroll. Küçük viewport'ta da tam görünsün.
- Dosyalar: `src/components/vehicles/VehicleModal.tsx`,
  `src/components/trailers/TrailerModal.tsx`.
- Efor: DÜŞÜK.

## Önerilen sıra (efor×etki)
1. **#6 form ferahlat** (düşük efor, görünür) — VehicleModal/TrailerModal.
2. **#5 dil/tema tuşu** (düşük efor, görünür) — LanguageSwitcher.
3. **#2 teyit** (bakım admin'de zaten yok — eski image mı?).
4. **#1+#4 error merge** (orta) — SistemSaglikPage canonical.
5. **#3 muayene sekmesi** (orta, backend dorse endpoint).
6. **#4 bakım→yakıt** (yüksek, backend).

Her dilim gerçek koşumla (vitest + build, gerekirse render screenshot) kanıtlanacak.
Hayali/sahte kod, test, halüsinasyon yok.
