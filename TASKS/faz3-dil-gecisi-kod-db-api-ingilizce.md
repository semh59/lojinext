# FAZ3 — Dil Geçişi: Kod + DB + API → İngilizce (BAĞIMSIZ FAZ)

> **DURMA NOKTASI:** Kullanıcı onayı olmadan uygulanmaz. Bu FAZ, FAZ1/FAZ2'nin sınır-enforcement işiyle **ASLA aynı PR'da karışmaz** — Sert Kısıt 9 + kullanıcı talimatı.

**Kullanıcı talimatı (bu FAZ'ın kapsamını tanımlar):** UI/UX metinleri **TR↔EN çift dilli KALIR** (mevcut i18next `frontend/src/locales/tr.json`/`en.json`). **Geri kalan HER ŞEY İngilizce olur:** kod kimlikleri (değişken/fonksiyon/sınıf adları), DB (tablo/kolon/enum değeri), API kontratı (path/query/body field), docstring/yorum, log mesajı.

**Giriş kriteri:** FAZ2 çıkışı + **prod satır sayıları ölçüldü** (bkz. madde 0 — dev DB boş ölçüldü, bu sayı VARSAYILAMAZ).
**Çıkış kriteri:** eski Türkçe anahtar/kolon okuması log-metrikle ölçülü 0 (≥14 gün) → contract/drop adımı; OpenAPI diff onaylı.

---

## Madde 0 — Prod satır sayısı ölçüm gate'i (giriş şartı)

```sql
SELECT relname, n_live_tup FROM pg_stat_user_tables
WHERE relname IN (
  'araclar','dorseler','soforler','lokasyonlar','yakit_alimlari','seferler',
  'seferler_log','yakit_periyotlari','yakit_formul','roller','kullanicilar',
  'entegrasyon_ayarlari','kullanici_oturumlari','egitim_kuyrugu','model_versiyonlar',
  'sistem_konfig','konfig_gecmis','iceri_aktarim_gecmisi','guzergah_kalibrasyonlari',
  'arac_bakimlari','bildirim_kurallari','bildirim_gecmisi','kullanici_ayarlari','sefer_belgeler'
) ORDER BY n_live_tup DESC;
```
Bu sorgu PROD'da çalıştırılmadan FAZ3 BAŞLAMAZ. Dev ortamında (2026-07-11 ölçümü) tüm iş tabloları boştu — bu sonuç PROD'a EKSTRAPOLE EDİLEMEZ. Büyük tablo çıkarsa (>1M satır), madde 3'teki batch backfill zorunlu; küçükse tek-transaction UPDATE kabul edilebilir.

## Madde 1 — DB kapsamı (expand-migrate-contract, TEK ADIMDA rename YASAK)

**27 Türkçe tablo adı** (MEMORY kaynağı, tam liste): `araclar, dorseler, soforler, sofor_ad_soyad_trigram, sofor_adaptasyon, lokasyonlar, lokasyon_segments, yakit_alimlari, seferler, seferler_log, yakit_periyotlari, yakit_formul, roller, kullanicilar, entegrasyon_ayarlari, kullanici_oturumlari, egitim_kuyrugu, model_versiyonlar, sistem_konfig, konfig_gecmis, iceri_aktarim_gecmisi, guzergah_kalibrasyonlari, arac_bakimlari, bildirim_kurallari, bildirim_gecmisi, kullanici_ayarlari, sefer_belgeler`.

**109 Türkçe kolon adı** (models.py'de ölçülü, örnekler): `plaka, marka, yil, sefer_no, sefer_sayisi, durum, onay_durumu, bakim_tipi, bakim_tarihi, belge_tipi, ocr_durumu, ad_soyad, ehliyet_sinifi, risk_kategorisi, depo_durumu, mesafe_km, guzergah_id, kaynak_tip, aksiyon_tipi, islem_tipi, olay_tipi, aktarim_tipi, km_sayac, muayene_tarihi, sigorta_tarihi, yetkiler, ...`.

**18 persisted enum/status değer kümesi** (dual-accept fail-closed gerektiren — DB'de zaten yazılı satırlar var):
```
yakit_alimlari.durum: ['Bekliyor','Onaylandı','Reddedildi']  (aksanlı! CHECK constraint'li)
seferler.durum: ['Planned','Completed','Cancelled']  (zaten İngilizce — DEĞİŞMEZ)
seferler.onay_durumu: ['beklemede','onaylandi','reddedildi']
anomalies.severity: ['low','medium','high','critical']  (zaten İngilizce)
egitim_kuyrugu.durum: ['WAITING','RUNNING','COMPLETED','FAILED','CANCELED']  (zaten İngilizce)
fuel_investigations.status: ['open','assigned','investigating','resolved','closed']  (zaten İngilizce)
arac_bakimlari.bakim_tipi: ['PERIYODIK','ARIZA','ACIL']
bildirim_gecmisi.durum: ['SENT','FAILED','READ']  (zaten İngilizce)
iceri_aktarim_gecmisi.durum: ['PENDING','VALIDATING','PROCESSING','COMPLETED','FAILED','ROLLED_BACK']  (zaten İngilizce)
sefer_belgeler.ocr_durumu: ['bekliyor','islendi','hata']
sefer_belgeler.belge_tipi: ['yakit_fisi','sefer_fisi','tir_ekran']
dorseler.tipi: default 'Standart'
soforler.risk_kategorisi: default 'Düşük'
soforler.ehliyet_sinifi: default 'E'
lokasyonlar.zorluk: default 'Normal'
yakit_alimlari.depo_durumu: default 'Bilinmiyor'
prediction_results.yakit_tipi: default 'DIZEL'
seferler_log.islem_tipi: ['INSERT','UPDATE','DELETE']  (zaten İngilizce)
```
**Sadece Türkçe değer taşıyanlar** (10/18) gerçek dil geçişi gerektirir; kalan 8 zaten İngilizce (dokunulmaz).

**Prosedür (her Türkçe tablo/kolon/enum için, TEK ADIMDA rename YASAK):**
1. **Expand:** yeni İngilizce kolon/tablo eklenir (ör. `seferler.approval_status`), eski (`onay_durumu`) SİLİNMEZ.
2. **Dual-write:** uygulama kodu HER İKİ kolona da yazar (bir transaction'da).
3. **Backfill:** mevcut satırlar batch'li UPDATE ile yeni kolona kopyalanır (madde 0'daki satır sayısına göre batch boyutu — >100K satırda `LIMIT`'li döngü, lock riski azaltmak için).
4. **Dual-read (migrate):** okuma yolu yeni kolona geçer, eskisi hâlâ senkron yazılıyor (rollback güvenliği).
5. **İzleme:** eski kolon/anahtar okuma sıklığı log-metrikle izlenir, ≥14 gün.
6. **Contract:** 14 gün boyunca eski-kolon okuması 0 ise, eski kolon DROP edilir (bu adım GERİ ALINAMAZ — plan genelinin tek geri-alınamaz adımı, en sona bırakılır).

**Enum dual-accept (fail-closed, çift yönlü map):**
```python
TR_TO_EN_ONAY_DURUMU = {"beklemede": "pending", "onaylandi": "approved", "reddedildi": "rejected"}
EN_TO_TR_ONAY_DURUMU = {v: k for k, v in TR_TO_EN_ONAY_DURUMU.items()}

def normalize_onay_durumu(value: str) -> str:
    if value in TR_TO_EN_ONAY_DURUMU:
        return TR_TO_EN_ONAY_DURUMU[value]
    if value in EN_TO_TR_ONAY_DURUMU:
        return value  # zaten İngilizce
    raise ValueError(f"Bilinmeyen onay_durumu değeri: {value}")  # fail-closed — sessizce geçmez
```

## Madde 2 — API kontratı kapsamı

**Türkçe API yüzeyi** (ölçülü, sınırlı): path param adları (`{sofor_id}`, `{arac_id}`, `{sefer_id}`, `{dorse_id}`, `{yakit_id}`, `{lokasyon_id}`), 2 aksiyon verb'i (`POST /trips/{sefer_id}/onayla`→`/approve`, `/reddet`→`/reject`), 4 `/internal/sofor-*`/`sefer-*` segmenti, 2 query param (`baslangic_tarihi`→`start_date`, `bitis_tarihi`→`end_date`). Router PREFIX'leri ZATEN İngilizce (`/vehicles`, `/trips`, vb. — dokunulmaz).

**75 Türkçe Pydantic field adı** (schemas'ta ölçülü, örnekler): `plaka, marka, yil, sefer_id, sefer_no, durum, onay_durumu, onay_notu, bakim_tipi, sofor_adi, ad_soyad, ehliyet_sinifi, dorse_plakasi, guzergah_adi, net_kg, dolu_agirlik_kg, toplam_maliyet, toplam_litre, yakit_tipi, sifre, yetkiler, ...`.

**Pydantic dual-emit deseni** (eski frontend kırılmadan yeni alan adı eklenir):
```python
class SeferResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    approval_status: str = Field(serialization_alias="approval_status")
    onay_durumu: str = Field(deprecated=True)  # eski alan, dual-emit — FAZ3 sonunda kaldırılır

    @model_validator(mode="after")
    def _sync_legacy_field(self):
        self.onay_durumu = self.approval_status
        return self
```
Eski route'lar (`/onayla`, `/reddet`) yeni route'lara (`/approve`, `/reject`) 307 redirect ile yönlendirilir — API sözleşmesi kırılmaz.

## Madde 3 — Frontend önkoşulu (rename ÖNCESİ)

**Ölçülü risk:** merkezi API katmanı YOK (`frontend/src/services/api/` = 5 dosya — CLAUDE.md'nin "domain başına dosya" iddiası SAHTE çıktı, MEMORY başlık notu). **370/760 dosya** Türkçe field tüketiyor doğrudan (`plaka` 340 ref, `arac_id` 215, `durum` 208, `ad_soyad` 153, ...). Bu FAZ'ın İLK ADIMI: `frontend/src/services/api/` altında domain-başına typed client dosyaları oluşturmak (trip-service.ts zaten var — CLAUDE.md doğru kısmı; eksik olan merkezi tip tanımları `frontend/src/types/`'ta domain-başına dosyalara bölünür). Bu katman kurulmadan alan-adı rename'i 370 dosyaya dağınık şekilde yapılmaz.

## Madde 4 — Kod kimlikleri (docstring/yorum/log/değişken adları)

**214/327 dosya** Türkçe identifier içeriyor (ölçülü). Bu, DB/API'den bağımsız en düşük riskli katman (dış kontrat değil) — modül-başına, o modülün FAZ1 taşıması sırasında AÇILAN CLAUDE.md'sindeki "Domain terimleri TR↔EN sözlüğü" bölümü kullanılarak mekanik rename yapılır (ruff/ast-grep ile toplu, davranış değişmez — yalnız isim).

## Kabul Kriterleri
- [ ] Prod satır sayısı ölçüldü, batch stratejisi buna göre seçildi
- [ ] Her Türkçe tablo/kolon expand-migrate-contract 6 adımından geçti
- [ ] 10 gerçek-Türkçe enum kümesi dual-accept fail-closed map'e sahip
- [ ] API dual-emit + 307 redirect, OpenAPI diff onaylı
- [ ] Frontend typed-client katmanı rename'den ÖNCE kuruldu
- [ ] Eski-anahtar okuma metriği ≥14 gün 0 gösterdi → contract/drop uygulandı
- [ ] UI i18next TR/EN metinleri BU FAZ'DA DEĞİŞMEDİ (kapsam dışı, kullanıcı talimatı)
