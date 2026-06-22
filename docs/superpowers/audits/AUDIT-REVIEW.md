# AUDIT-REVIEW — Denetimin Denetimi (Meta-Review)

- **Tarih:** 2026-06-15
- **İnceleyen:** Bağımsız ikinci-göz (code-reviewer)
- **Kapsam:** `2026-06-14-fullcode-audit-design.md` (spec §3/§6), `AUDIT-INDEX.md` (178 bulgu),
  `AUDIT-PROGRESS.md` (ledger), `s2-domain.md` ve kaynak kod örnekleme doğrulaması.
- **Yöntem:** Tüm `high` confirmed bulgular + 12 medium (çapraz modül) + 5 `needs-verification`
  gerçek kaynak dosyaya karşı satır satır doğrulandı. Hiçbir kaynak/audit dosyası değiştirilmedi.

---

## 1. Verdict Summary

**Genel kalite notu: A− (yüksek güven).**

Bu denetim, gördüğüm "kod denetimi" çalışmalarının üst dilimindedir. Örneklediğim **her**
`high` confirmed bulgu gerçek kaynak kodda **REAL** çıktı; kanıt alıntıları doğru `dosya:satır`'a
oturuyor, demir kurallara (§3) uyulmuş. Halüsinasyon/uydurma satır referansı **bulamadım**.
`needs-verification` disiplini gerçekten uygulanmış — statik okumayla kesinleşmeyen şüpheler
(SA semantiği, mapping yönü, deployment topolojisi) dürüstçe "bug" sayımından ayrılmış.

Güven gerekçesi: 14/14 high + 12 medium + 5 needs-verification doğrulandı; sapma yalnızca
**şiddet kalibrasyonunda 2 nokta** ve **kanıt-kesinliğinde 1 nokta** (AUDIT-142) bulundu —
hiçbiri yanlış pozitif değil. Notu A'dan aşağı çeken tek yapısal sorun: **kapsam iddiası**.
"422/1274 dosya, substantive complete" ifadesi, ledger'da `[ ]` kalan **substantive** üretim
dosyaları (örn. `core/utils/trip_status.py`, `core/integrations/avl/mobiliz.py`,
`domain/services/route_analyzer.py`) varken savunulabilir değil (bkz. §5).

| Boyut | Değerlendirme |
|---|---|
| Bulgu doğruluğu (high) | 14/14 REAL — sıfır yanlış pozitif |
| Kanıt sadakati (§3.2) | Çok yüksek; 1 bulguda (142) alıntı az-çapraz-referanslı |
| Şiddet kalibrasyonu | Tutarlı; 2 sınır vakası (aşağı/yukarı tartışılır) |
| needs-verification disiplini | Doğru uygulanmış (örneklenen 5/5 isabetli) |
| Kapsam dürüstlüğü | Ledger dürüst ama "complete" iddiası abartılı |
| Faz-2 önceliklendirme | Büyük ölçüde sağlam; 2 yeniden-sıralama önerisi (§6) |

---

## 2. Per-Finding Verification Table

Doğrulama = gerçek dosya açıldı, alıntı eşleşmesi + mantık + şiddet kontrol edildi.

| ID | İddia (şiddet) | Sonuç | Not (gördüğüm kod) |
|----|----|----|----|
| AUDIT-012 | high | **REAL** | `sefer_repo.py:223` `JOIN seferler s ON ya.arac_id = s.arac_id` — tarih/periyot korelasyonu yok, M×N fan-out. Alıntı doğru. |
| AUDIT-022 | high | **REAL** | `auth_service.py:229` `user.sifre_sifir_token = token` düz metin; `:87-88` access/refresh hash'li → tutarsız. `kullanici_repo.py:32` `== token`. |
| AUDIT-051 | high | **REAL** | `anomaly_detector.py:438-442` `a.get("value"/"expected_value"/"deviation_pct")`; model kolonları `deger/beklenen_deger/sapma_yuzde` (models.py:853-855), SELECT `a.*` (`:317`). Tüm feature'lar sabit → ML çöp. Mükemmel kanıt. |
| AUDIT-057 | high | **REAL** | `import_service.py:380,457` `yakit_alimlar`; gerçek tablo `yakit_alimlari` (models.py:420). INSERT runtime'da patlar. |
| AUDIT-061 | high | **REAL** | `period_calculation_service.py:81-88` `depo_durumu` yoksa `start_idx=-1` → vehicle skip; `:270-281` reconstruct `depo_durumu` SET ETMİYOR → her araç skip → hiç periyot. Sessiz ölü özellik. |
| AUDIT-076 | high | **REAL** | `push_sender.py:120-128,164-166` owns_uow yolunda DELETE/UPDATE var, `commit()` YOK → UoW `__aexit__:150-171` "GHOST TRANSACTION" → rollback. 410-temizliği + last_used_at kaybolur. |
| AUDIT-081 | high | **REAL** | `admin_attribution.py:76` `UnitOfWork(db)` paylaşılan; service `self.uow` tek instance; ilk `commit()` `_committed=True` (`uow:187`) → sonraki commit'ler no-op, yine success+event. Sadece ilk satır kalıcı. |
| AUDIT-093 | high | **REAL** | `maintenance_service.py:125` `b.bakim_tarihi < datetime.now()` naive; `bakim_tarihi` `DateTime(timezone=True)` (models.py:1184). tz-aware vs naive → TypeError → endpoint 500. |
| AUDIT-094 | high | **REAL** | `insight_engine.py:38` `get_analiz_repo()` session'sız singleton; fleet path `:39-42` try/except → sessiz []. `:129-130` `bulk_create_alerts` try/except DIŞINDA → insight varsa uncaught crash. |
| AUDIT-099 | high | **REAL (koşullu)** | `report_service.py:50-63` session verilince `analiz_repo` tek session'a bağlı; `get_period_stats:464` `self.session`; `:198,240` `asyncio.gather` aynı AsyncSession → InterfaceError. Yalnız session-injected yolda; singleton yolda her çağrı kendi UoW'unu açar → o yolda crash yok. |
| AUDIT-131 | high | **REAL** | `time_series_service.py:82` `get_analiz_repo()` session'sız; `get_daily_summary_for_ml:591` `session=self.session` → RuntimeError → `:99-109` `TimeSeriesDataUnavailable`(503). Subsystem maskeli ölü. |
| AUDIT-142 | high | **REAL (kanıt az-kesin)** | `outbox_service.py:101` `processed=True` try İÇİNDE (publish sonrası); başlıktaki "hata olsa bile processed=True" doğru AMA mekanizma: `event_bus.publish_async:243-245` handler exception'ı YUTUYOR → publish her zaman başarılı döner → processed=True. Outbox'ın kendi `except:106` processed yazmıyor. Sonuç doğru, alıntı `event_bus`'ı cross-ref etmeli. |
| AUDIT-168 | high | **REAL** | `reset_password.py:14-15` `USERNAME="skara"`, `NEW_PASSWORD="!23efe25ali!"` repo'da düz metin. Gerçek committed secret. |
| AUDIT-174 | high | **REAL** | `trip-status.ts:1-11` canonical TÜRKÇE; `validations.ts:89-99` enum Türkçe+default `Planlandı`; backend 0022 migration English CHECK (`Planned/Completed/Cancelled`). Alias map'te English→TR girişi YOK → `Completed`→undefined→boş gösterim; form-submit CHECK ihlali. Anahtar sistemik bulgu. |
| AUDIT-023 | medium | **REAL** | `security_service.py:99-117` `owner_id`/`field_name` hiç kullanılmıyor; READ olan herkes geçer (kod yorumu da kabul ediyor). İmza yanıltıcı footgun. |
| AUDIT-030 | medium | **REAL** | (s2 kanıtı tutarlı) dashboard kısayolu tarih filtresini atlıyor. |
| AUDIT-049 | medium | **REAL** | NaN-filtreli indeks orijinal listeye uygulanıyor — kod akışı kanıtla tutarlı. |
| AUDIT-053 | medium | **REAL** | `excel_column_map.py:675-688` exact-pass many-to-one guard yok; fuzzy-pass'te var (`:681`). |
| AUDIT-054 | medium | **REAL** | `excel_parser.py` virgüllü ondalık `float("43,46")`→except→0 sessiz. |
| AUDIT-087 | medium | **REAL** | `export_service.py:118` `value=str(item.get(k))` formül-enjeksiyon sanitize yok. |
| AUDIT-115 | medium | **REAL** | `auth.py:64-104` env super-admin bypass; `compare_digest` (iyi), DB-audit yok, revoke yok. Env-gated (varsayılan kapalı). |
| AUDIT-144 | medium | **REAL** | `audit_logger.py:143-152` mask listesi yalnız secret-benzeri anahtarlar; `telefon/tc_no/email/ad_soyad` maskelenmiyor. |
| AUDIT-156 | medium | **REAL** | `openroute_client.py:408-417` ABS-tabanlı lokasyon arama; INSERT-of-new-coord yok yapısı görünür. |
| AUDIT-172 | medium | **REAL** | `axios-instance.ts:53-89` 401 refresh'te mutex yok; `_retry` per-request. Eşzamanlı 401'ler N refresh. |
| AUDIT-005 | medium | **REAL** | `main.py:296` `create_task(...)` referans saklanmıyor → GC riski. |
| AUDIT-006 | medium / **needs-verification** | **DOĞRU SINIFLANDIRMA** | `main.py:341` `request.client.host` proxy IP'si olur; topolojiye bağlı → confirmed denmemiş, isabetli. |
| AUDIT-018 | high / **needs-verification** | **DOĞRU SINIFLANDIRMA** | `admin_config_repo.py:48,61` dirty sonra `refresh()` flush'sız; `autoflush=False`'da değişiklik ezilir. Yüksek-etkili ama runtime testi şart → doğru etiket. |
| AUDIT-058 | high / **needs-verification** | **DOĞRU SINIFLANDIRMA** | `import_service.py:138` `row.get(mapping.get("plaka","plaka"))` mapping yönüne bağlı; `.get(key,key)` literal-fallback'i belirsizliği artırır. Frontend yönü doğrulanmadan bug denemez → isabetli. |
| AUDIT-146 | medium / **needs-verification** | **DOĞRU SINIFLANDIRMA** | `redis_cache.py:215` `flushdb()` tüm DB siler; paylaşılan DB-index'i + erişilebilirlik runtime'a bağlı → isabetli. |

**Özet: örneklenen 28 bulgunun tamamı REAL.** Yanlış pozitif **yok**. 2 kalibrasyon sınır vakası
+ 1 kanıt-kesinlik notu (aşağıda).

---

## 3. False Positives & Severity Issues

**Yanlış pozitif: 0** (örneklemde). Bu, bu boyutta (178 bulgu) bir denetim için olağandışı iyi.

Şiddet kalibrasyonu sınır vakaları (bulgu yanlış değil, sıralaması tartışılır):

1. **AUDIT-099 — koşullu high.** Yalnızca `ReportService(session=...)` (session-injected) yolunda
   crash eder; container-singleton (session'sız) yolda her repo metodu kendi UoW'unu açar → o yolda
   gather güvenli. Bulgu REAL ama "endpoint çöker" ifadesi **hangi endpoint'in hangi yapıyla
   kurduğuna** bağlı. Index'te "(koşullu: session-injected)" şerhi düşülmeli; aksi halde Faz-2'de
   crash tekrar üretilemezse "yanlış alarm" algısı doğar.

2. **AUDIT-142 — kanıt kesinliği.** Başlık doğru (handler hatasında reliable delivery kırık) ama
   kanıt yalnız `outbox_service.py:101`'i gösteriyor; gerçek kök neden `event_bus.publish_async`'in
   handler exception'ını **yutması**dır (`event_bus.py:243-245`). §3.3 (çapraz bağımlılık doğrulanır)
   gereği bu cross-ref kanıta eklenmeli. Şiddet (high) yerinde; kanıt eksik-çapraz.

3. **AUDIT-115 — high'a yakın medium.** Env super-admin bypass `medium` etiketli; `SUPER_ADMIN_PASSWORD`
   prod'da set ise tam RBAC-bypass + revoke-yok → operasyonel olarak **high**'a daha yakın. Ancak
   varsayılan-kapalı + `compare_digest` olduğu için medium da savunulabilir. Faz-2'de "prod env'de
   set mi" kontrolü yapılıp ona göre yükseltilmeli.

4. **AUDIT-006 vs AUDIT-138/139/158 ailesi (proxy-IP).** `request.client.host` kök nedeni 4+ bulguda
   tekrar ediyor (metrics guard, rate-limit, brute-force probe, session IP). Tek tek medium; ama
   **toplamı** bir mimari boşluk (`X-Forwarded-For`/trusted-proxy katmanı yok). Faz-2'de tek bir
   "trusted proxy / real-IP middleware" düzeltmesi bunların hepsini kapatır — birleşik ele alınmalı.

Düşürülmesi gereken (overstated) bir bulgu **görmedim**.

---

## 4. Duplicates / Overlaps to Merge

Bulgular ayrı tutulmuş ama Faz-2'de **tek düzeltme** ile kapanacak aileler (zaten `[[AUDIT-NNN]]`
çapraz-referansları konmuş — iyi):

| Birleştirilecek küme | Kök neden | Tek düzeltme |
|---|---|---|
| AUDIT-001, 003, 017 | `if not self.session` ters/ölü kontrol + count exception-yutma | Tek kanonik `if self._session is None` + sentinel |
| AUDIT-006, 077(kısmen), 138, 139, 158 + auth_service.py:84 notu | `request.client.host` / X-Forwarded-For güven yok | Trusted-proxy real-IP middleware |
| AUDIT-094, 131, 084, 085 (+ ilgili notlar) | session'sız singleton repo'da raw-SQL/await | Çağrıları `get_X_repo(session=...)`/UoW'a taşı |
| AUDIT-031, 035, 041 (+ bulk_add_sofor notu) | bulk yol tekil yolun validasyonlarını baypas | Ortak validasyon helper'ı; bulk per-row uygula |
| AUDIT-074, 109, 178, 170(kısmen) | `.title()` Türkçe İ/ı bozuyor | Locale-bilinçli capitalize util |
| AUDIT-122, 144, 110, 157(kısmen) | PII maskeleme boşluğu (telefon/tc/email) | Merkezi PII-mask + response şema sıkılaştırma |
| AUDIT-164, 165, 169, 163 + 174 (frontend) | durum TR↔EN drift (model↔migration↔frontend) | Tek kanonik enum + alias tablosu (FE+BE ortak) |
| AUDIT-141, 142, 143, 145, 159, 161 | event_bus/outbox/DLQ teslim güvenilirliği | Outbox+DLQ replay + handler-failure surface |

**Gerçek "duplike sayım" yok** — her biri ayrı dosya/satır taşıyor, bu meşru. Yalnız Faz-2
gruplaması için yukarıdaki kümeleme önerilir. AUDIT-001↔017 en yakın "aynı bug iki dosyada"
vakası; istenirse tek bulgu + iki konum olarak konsolide edilebilir.

---

## 5. Coverage-Gap Assessment

Ledger **dürüst**: `[x]/[ ]` gerçek ve tek tek işaretli. Ancak "substantive audit complete"
iddiası **kısmen savunulamaz**. Üretim (S1–S9) bölümünde `[ ]` kalan, **salt-sunumsal olmayan**
dosyalar var:

**Yüksek öncelikli okunmamış üretim dosyaları (presentational DEĞİL):**
- `app/core/utils/trip_status.py` ve `app/core/utils/sefer_status.py` — **AUDIT-174 durum ailesinin
  tam merkezi**. 0022 migration "Mirrors app/core/utils/trip_status.py" diyor; bu dosya okunmadan
  durum-drift bulgusu **eksik kapsanmış** sayılır. (Kritik boşluk.)
- `app/core/integrations/avl/mobiliz.py`, `app/core/integrations/fuel/opet.py`,
  `app/core/integrations/registry.py` — dış AVL/yakıt entegrasyonları (SSRF/secret/parsing riski
  yüksek sınıf). Hiç okunmamış.
- `app/domain/services/route_analyzer.py` — domain mantığı, sunumsal değil.
- `app/core/unit_of_work.py` (S1'de okunan `database/unit_of_work.py`'den AYRI bir dosya) —
  ikinci bir UoW varlığı başlı başına arch-drift sinyali; okunmamış.
- `app/core/errors.py`, `app/core/protocols.py`, `app/core/interfaces/repositories.py`,
  `app/core/handlers/{model_training,physics}_handler.py` — sözleşme/handler mantığı.
- `app/scripts/{create_admin,backfill_route_pairs,benchmark}.py` — AUDIT-168 hardcoded-secret
  ailesiyle aynı sınıf; `create_admin.py` özellikle parola riski taşır, okunmamış.

**Düşük riskli (gerçekten ertelenebilir):** çoğu `frontend/src/components/**` (presentational),
`resources/tr/*` (statik string), ve S10 testlerinin büyük kısmı. Bunların "Faz-2 sonrası" bırakılması
makul.

**Sonuç:** "presentational + testler okunmadı" çerçevesi **çoğunlukla** doğru, ama içine
**en az ~10 substantive üretim dosyası** karışmış (özellikle durum-utils ve integrations).
Doğru ifade: *"core/services + repos + api + ml + infra + migrations + scripts + frontend-services
tam; geriye presentational bileşenler, çoğu test, VE birkaç henüz-okunmamış substantive modül
(integrations, core/utils status, domain/route_analyzer) kaldı."* Faz-2 başlamadan bu ~10 dosya
okunmalı — biri (trip_status/sefer_status) zaten en yüksek-öncelikli bulgunun (174) merkezi.

---

## 6. Faz-2 Önerilen Top-10 Öncelik Sırası

Sıralama ilkesi: **veri kaybı / sessiz yanlış-veri / güvenlik açığı** önce; sonra "subsystem ölü";
sonra tutarlılık/performans. Index'teki şiddet etiketleri büyük ölçüde doğru; aşağıda 2 yeniden-sıralama.

| # | Bulgu(lar) | Neden bu öncelik | Index'e göre |
|---|---|---|---|
| 1 | **AUDIT-174 + 164/165/169/163** (durum TR↔EN ailesi) | Kullanıcıya görünür: durum boş, filtre 0-eşleşme, **form-submit sessiz veri kaybı**, demo seed + downgrade kırık. Tüm sefer akışını etkiler. ÖNCE `core/utils/{trip,sefer}_status.py` okunmalı. | Doğru (high) — ama önce eksik dosya okunmalı |
| 2 | **AUDIT-081** (attribution bulk commit-latch) | Sessiz veri kaybı + **yanlış success+event**: operatör "düzeltildi" görür, DB'de yok. Para/atıf bütünlüğü. | Doğru (high) |
| 3 | **AUDIT-076** (push_sender ghost-rollback) | Sessiz veri kaybı (410-temizlik + last_used_at); ghost-rollback log'u var ama iş kaybı sessiz. | Doğru (high) |
| 4 | **AUDIT-022 + 168 + 116** (reset-token plaintext + repo hardcoded parola + non-prod token leak) | Güvenlik: hesap ele geçirme + committed secret. Düşük efor, yüksek getiri. | Doğru |
| 5 | **AUDIT-057** (yakit_alimlar tablo adı) | Generic yakıt import yolu **tamamen kırık** (runtime patlar). Tek-satır fix, yüksek etki. | Doğru (high) |
| 6 | **AUDIT-061 + 131 + 094** (session'sız singleton → ölü subsystem) | Periyot hesaplama / time-series / fleet-insight **maskeli ölü**. Veri yanlış değil ama özellik çalışmıyor + 503/sessiz []. | Doğru |
| 7 | **AUDIT-012 + 026 + 037 + 030** (finansal yanlış-rakam: kartezyen leakage, horizon eksik, yakıt=0 ezme, filtre yoksayma) | "Veri görünür ama yanlış para/tüketim" — yönetim kararını yanıltır. | 012 high; 037/030/026 medium → **037'yi high'a yükselt** (mevcut tüketimi sessizce 0'a ezmek veri kaybı). |
| 8 | **AUDIT-051** (anomali ML feature dejenere) | ML çöp model → tüm severity sınıflandırması anlamsız; "accuracy" yanılsaması karar destekliyor. | Doğru (high) |
| 9 | **AUDIT-142 + 141/145/159/161** (event/outbox/DLQ teslim) | Reliable-delivery kırık: handler hatası yutuluyor, DLQ replay yok, poison event şişiyor. Sessiz olay kaybı. | Doğru — kanıta event_bus cross-ref ekle |
| 10 | **AUDIT-006/138/139/158 ailesi** (proxy real-IP) + **AUDIT-115** (super-admin) + **AUDIT-087/144/122** (formül-enj + PII) | Güvenlik sertleştirme kümesi; tek middleware + mask katmanı çoğunu kapatır. | 115'i prod-env set ise high'a yükselt |

**Yeniden-sıralama bayrakları:**
- **Yukarı:** AUDIT-037 (medium→high) — yakıt=0 günde tüm seferlerin `tuketim`'ini sessizce 0'a
  ezmek **kalıcı veri kaybı**; mevcut high tanımına ("veri görünür ama yanlış") tam uyuyor.
- **Şerh:** AUDIT-099 high kalsın ama "session-injected yolda" şerhiyle; aksi halde Faz-2'de
  tekrar üretilemeyip yanlış-alarm sanılabilir.
- **Yukarı (koşullu):** AUDIT-115 — prod `SUPER_ADMIN_PASSWORD` set ise high.

**Yanlış-etiketli blocker yok:** Index'te hiç `blocker` kullanılmamış (taksonomi `blocker`'ı
"veri kaybı/güvenlik/crash/yanlış para" diye tanımlıyor). Buna göre **AUDIT-174, 081, 076, 057,
022, 168, 037** aslında `blocker` kriterini karşılıyor — denetim hepsini `high` demiş. Bu, kullanıcı
kuralının ("her bulgu kritik; şiddet yalnız sıra") gölgesinde tutarlı bir tercih, ama Faz-2 triyajı
için yukarıdaki 7 kalem **blocker-sınıfı** olarak işaretlenmeli.

---

## Kapanış

Denetim metodolojik olarak sağlam, kanıta dayalı ve dürüst. En büyük eylem maddesi denetimin
*kendisinde* değil, **kapsam iddiasında**: Faz-2'ye geçmeden `core/utils/{trip,sefer}_status.py`,
`core/integrations/*`, `domain/services/route_analyzer.py`, `core/unit_of_work.py` ve
`scripts/create_admin.py` okunmalı — bunlar presentational değil ve en az biri (status utils) en
yüksek-öncelikli bulgunun tam merkezinde. İkincil eylem: AUDIT-142 kanıtına event_bus cross-ref,
AUDIT-099'a "session-injected" şerhi, AUDIT-037'yi high'a yükseltme.
