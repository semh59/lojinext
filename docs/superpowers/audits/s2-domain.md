# S2 — Domain Katmanı Denetimi

Bölümler: **Repositories** (T2/S2a — bu commit), Services (T3-T4), Schemas (T4).
Yöntem: her dosya `Read` ile baştan sona; her bulgu kaynak satırı + alıntı taşır.

> Şiddet yalnız düzeltme sırası içindir — her bulgu kritiktir.

---

## S2a — Repositories (21 dosya, tam okundu)

Genel olumlu: **tüm ham SQL parametrik** (`:name` bind) — string interpolasyonu yalnız
sabit/whitelist'li parçalarda (`order_direction`, `where` clause birleştirme), kullanıcı
girdisi enjekte edilmiyor → **SQL injection bulgusu YOK**. `notification.mark_as_read_for_user`
IDOR-safe (sahiplik kontrolü). FOR UPDATE kilitleri ve TOCTOU fast-path'ler dürüstçe belgelenmiş.

### AUDIT-012 — `get_cost_leakage_stats` yakıt sorgusu kartezyen join → yanlış finansal rakam
- Şiddet: high · Sınıf: bug / domain-rule · Durum: confirmed
- Konum: `app/database/repositories/sefer_repo.py:220-228`
- Kanıt:
  ```sql
  SELECT COALESCE(SUM(ya.litre - (s.mesafe_km * :est_litre_per_km / 100.0)), 0)
  FROM yakit_alimlari ya
  JOIN seferler s ON ya.arac_id = s.arac_id          -- yalnız arac_id; tarih/periyot korelasyonu YOK
  WHERE ya.tarih >= :start_date AND s.tarih >= :start_date AND s.is_deleted = FALSE AND s.durum='Completed'
  ```
- Sorun: Her yakıt alımı, aynı aracın penceredeki **her** tamamlanmış seferiyle eşleşir
  (M×N). N_sefer yakıt alımı, N_yakıt sefer kez sayılır → `fuel_gap_liters`/`fuel_gap_cost`/
  `total_leakage_cost` anlamsızca şişer. "Maliyet kaçağı" KPI'ı yanlış para gösterir.
- Önerilen düzeltme: yakıt-açığını araç+dönem bazında **ayrı** agregalardan hesapla
  (Σlitre − Σmesafe·est/100), sefer-yakıt arası kartezyen join'i kaldır.

### AUDIT-013 — `refresh_stats_mv` autocommit option'ı SA2.0'da etkisiz → CONCURRENTLY sessiz fallback
- Şiddet: medium · Sınıf: silent-failure · Durum: needs-verification (SA sürüm davranışı)
- Konum: `app/database/repositories/sefer_repo.py:683-707`
- Kanıt:
  ```python
  await self.session.execute(
      text("REFRESH MATERIALIZED VIEW CONCURRENTLY sefer_istatistik_mv")
      .execution_options(autocommit=True))   # SA2.0'da 'autocommit' exec option YOK/no-op
  ```
- Sorun: SQLAlchemy 2.0'da statement-level `autocommit` execution option kaldırıldı. CONCURRENTLY
  bir transaction bloğunda çalışamaz → ambient transaction içinde çağrı PG hatası verir → `except`
  → rollback → **blocking** (non-CONCURRENTLY) refresh'e düşer (SELECT'leri kilitler). Yani
  amaçlanan CONCURRENTLY pratikte hiç kullanılmaz; bu sessizce gizlenir.
- Önerilen düzeltme: ayrı bir AUTOCOMMIT bağlantısı kullan (`engine.connect().execution_options(isolation_level="AUTOCOMMIT")`).

### AUDIT-014 — `get_trip_stats` kullanılmayan `base` sorgusu (ölü kod)
- Şiddet: low · Sınıf: dead-code · Durum: confirmed
- Konum: `app/database/repositories/sefer_repo.py:474-480`
- Kanıt: `base = select(Sefer).where(...)` kurulup filtrelerle zenginleştiriliyor ama hiç
  execute/refere edilmiyor; `stats_q` (482) where'i bağımsız yeniden kuruyor.
- Önerilen düzeltme: `base` bloğunu sil.

### AUDIT-015 — Soft-delete / aktif filtre tutarsızlığı → silinmiş kayıtlar agregalara sızıyor
- Şiddet: medium · Sınıf: data-integrity / domain-rule · Durum: confirmed
- Konum (filtre EKSİK olanlar):
  - `arac_repo.py:106` (`get_all_with_stats_paged`) ve `:238` (`get_arac_with_stats`) —
    `LEFT JOIN seferler s ON a.id=s.arac_id AND s.tuketim IS NOT NULL` (s.is_deleted yok)
    → silinmiş seferler `toplam_km`/`toplam_sefer`/`ort_tuketim`'i şişirir.
  - `sofor_repo.py:220` (`get_guzergah_performansi`), `:241` (`get_driver_consumptions`) —
    s.is_deleted filtresi yok → silinmiş seferler şoför performansına girer.
  - `analiz_repo.py:459` (`get_period_stats` f_stats), `:507-511` (`get_fleet_performance_stats`
    cost), `:707` (`get_bulk_cost_stats`) — `yakit_alimlari` üzerinde `aktif=TRUE` yok →
    silinmiş yakıt alımları **maliyet raporlarına** girer (oysa `get_dashboard_stats:211` ve
    `yakit_repo.get_stats` filtreliyor).
  - `lokasyon_repo.py:64` (`get_benzersiz_lokasyonlar`), `:45` (`get_by_route`) — is_deleted yok.
- Sorun: aynı kavram için bazı sorgular silinmişleri dışlar bazıları dışlamaz → tutarsız,
  şişik km/tüketim/maliyet sayıları.
- Önerilen düzeltme: tek bir kanonik soft-delete predicate'i (helper) ile tüm agregalarda uygula.

### AUDIT-016 — `update_yakit` float ile `toplam_tutar` + kısmi güncellemede bayat toplam
- Şiddet: medium · Sınıf: domain-rule / bug · Durum: confirmed
- Konum: `app/database/repositories/yakit_repo.py:196-199`
- Kanıt:
  ```python
  if "fiyat_tl" in updates and "litre" in updates:           # SADECE ikisi de gelince
      updates["toplam_tutar"] = round(float(updates["fiyat_tl"]) * float(updates["litre"]), 2)
  ```
- Sorun: (1) `add()` aynı dosyada Decimal kullanıp float cent-yuvarlama hatasından kaçınıyor
  (docstring satır 100-103 bunu açıkça uyarıyor) — `update_yakit` ise float ile çarpıyor →
  yuvarlama hatası geri geliyor. (2) Yalnız `litre` veya yalnız `fiyat_tl` güncellenirse
  `toplam_tutar` yeniden hesaplanmıyor → stored toplam yeni litre/fiyatla **tutarsız** kalır.
- Önerilen düzeltme: Decimal kullan; mevcut satırı çekip eksik alanı tamamlayarak her durumda
  `toplam_tutar`'ı yeniden hesapla.

### AUDIT-017 — `if not self.session` ters/ölü kontrol session_repo'da tekrar ediyor
- Şiddet: medium · Sınıf: bug / dead-code · Durum: confirmed
- Konum: `app/database/repositories/session_repo.py:32` (ayrıca [[AUDIT-001]] base_repository.py:415)
- Kanıt:
  ```python
  async def deactivate_all(self, kullanici_id):
      session = self.session          # None ise BURADA raise
      ... s.aktif = False ...
      if not self.session:            # property None'da raise eder → asla falsy
          await session.commit()
  ```
- Sorun: `self.session` property None iken `RuntimeError` fırlatır, aksi halde truthy →
  `if not self.session` asla True olmaz → session-less (UoW'suz) kullanımda commit hiç çalışmaz
  (deaktivasyon kalıcı olmaz). Doğru desen `if self._session is None` (sefer_repo:760,
  analiz_repo:97 bunu kullanıyor) — tutarsızlık.
- Önerilen düzeltme: `if self._session is None:` olarak düzelt (her iki dosyada).

### AUDIT-018 — `update_value` flush'tan önce `session.refresh()` → konfig değişikliği sessizce kaybolur
- Şiddet: high · Sınıf: bug / silent-failure · Durum: needs-verification (SA semantiği; yüksek güven)
- Konum: `app/database/repositories/admin_config_repo.py:43-62`
- Kanıt:
  ```python
  config.deger = new_value          # 48 — dirty (henüz flush yok; engine autoflush=False)
  config.guncelleyen_id = updated_by_id
  self.session.add(history)
  await self.session.refresh(config)   # 61 — DB'den GERİ okur, bekleyen değişikliği EZER
  return self._to_dict(config)          # eski değeri döner; UPDATE emit edilmez → kalıcı olmaz
  ```
- Sorun: `Session.refresh()` nesne attribute'larını DB'den yeniden yükler ve flush edilmemiş
  yerel değişiklikleri ezer (engine `autoflush=False`). `config.deger` eski değere döner;
  nesne artık dirty değil → UoW commit'inde UPDATE üretilmez. **Admin sistem-konfig güncellemesi
  sessizce uygulanmaz** ve fonksiyon eski değeri döndürür. KonfigGecmis ise yeni değeri yazar →
  log ile gerçeklik çelişir.
- Önerilen düzeltme: `refresh` yerine `await self.session.flush()` (gerekirse sonra refresh).
  Runtime testi ile doğrula (config update→read).

### AUDIT-019 — Naive `datetime.now()` tz-aware kolonlara yazılıyor
- Şiddet: low · Sınıf: bug / consistency · Durum: confirmed
- Konum: `notification_repository.py:68,87` (`okundu_tarihi=datetime.now()`),
  `maintenance_repository.py:37` (`now=datetime.now()` ile tz-aware `bakim_tarihi` karşılaştırma)
- Sorun: Kolonlar `DateTime(timezone=True)`; naive `datetime.now()` (yerel saat) yazımı/karşılaştırması
  TZ kaymasına yol açar (sunucu yerel ≠ UTC). Diğer yerlerde `datetime.now(timezone.utc)` kullanılıyor.
- Önerilen düzeltme: `datetime.now(timezone.utc)` kullan.

### AUDIT-020 — `model_versiyon.activate` kötü `version_id`'de aracı aktif versiyonsuz bırakır
- Şiddet: low · Sınıf: bug · Durum: confirmed
- Konum: `app/database/repositories/model_versiyon_repo.py:46-57`
- Kanıt: önce `UPDATE ... SET aktif=False WHERE arac_id=:a` (hepsini kapatır), sonra
  `UPDATE ... SET aktif=True WHERE id=:v AND arac_id=:a`. `version_id` araca ait değilse 2. update
  0 satır → `False` döner ama 1. update zaten tüm versiyonları deaktive etti.
- Sorun: araç **aktif model versiyonsuz** kalır (deaktivasyon transaction commit edilirse). Ayrıca
  hedef versiyon `fizik_only_mod=True` ise `check_model_versiyon_aktif_fizik_xor` ihlali (handle edilmiyor).
- Önerilen düzeltme: önce hedef versiyonun varlığını/uygunluğunu doğrula; yoksa hiç deaktive etme.

### AUDIT-021 — Analitik sorgular exception yutup default/[] dönüyor (sessiz hata yayılımı)
- Şiddet: medium · Sınıf: silent-failure · Durum: confirmed
- Konum: `analiz_repo.py:198` (get_filo_ortalama→DEFAULT), `:240` (get_dashboard_stats→_default),
  `:401` (get_recent_unread_alerts→[]), `:325` (get_month_over_month_trends→0.0); benzer desen
  [[AUDIT-003]] base_repository.count().
- Sorun: DB hatası ile "gerçekten boş/varsayılan" ayırt edilemez; dashboard/AI-context yanlış
  ama makul görünen değerler gösterir, hata gizlenir.
- Önerilen düzeltme: en azından hata sayacı/sentinel ile çağırana sinyal ver; kritik path'lerde fırlat.

**S2a özeti:** 10 bulgu (high 2, medium 5, low 3) — 21/21 repo okundu. Sonraki: T3/S2b core/services.
İz: `kullanici_repo.get_by_reset_token` reset-token'ı düz eşitlikle arıyor → token'ın hash'lenip
hashlenmediği S2 services (auth_service) sırasında doğrulanacak.

---

## S2b — Core Services (T3, sürüyor)

### AUDIT-022 — Parola sıfırlama token'ı veritabanında düz metin saklanıyor (hash'siz)
- Şiddet: high · Sınıf: security · Durum: confirmed
- Konum: `app/core/services/auth_service.py:228-229` (üretim) + `:240` (doğrulama) ↔
  `app/database/repositories/kullanici_repo.py:32` (`sifre_sifir_token == token`) ↔
  `app/database/models.py:747` (`sifre_sifir_token: Mapped[Optional[str]] = mapped_column(Text)`)
- Kanıt:
  ```python
  token = secrets.token_urlsafe(32)
  user.sifre_sifir_token = token            # 229 — düz metin DB'ye yazılıyor
  ...
  user = await self.uow.kullanici_repo.get_by_reset_token(token)  # 240 — düz eşitlikle aranıyor
  ```
- Sorun: Erişim/refresh token'ları `jwt_handler.hash_token(...)` ile **hash'lenerek** saklanıyor
  (auth_service.py:87-88), ama parola-sıfırlama token'ı düz metin. DB yedeği sızması, salt-okunur
  SQL erişimi veya içeriden tehdit → token doğrudan kullanılıp **hesap ele geçirilir** (parola
  sıfırlama 1 saat geçerli). Token-handling içinde tutarsız güvenlik modeli.
- Önerilen düzeltme: token'ı sabit-zamanlı hash (SHA-256) ile sakla; doğrulamada gelen token'ın
  hash'ini karşılaştır. (Plaintext token yalnız kullanıcıya e-posta ile gider, DB'ye hash girer.)

### AUDIT-023 — `verify_ownership` `owner_id` parametresini hiç kontrol etmiyor → sahte izolasyon
- Şiddet: medium · Sınıf: security / api-design · Durum: confirmed
- Konum: `app/core/services/security_service.py:99-117`; çağrı yeri
  `app/core/services/sefer_read_service.py:40` (`SecurityService.verify_ownership(current_user, sefer.sofor_id)`)
- Kanıt:
  ```python
  def verify_ownership(cls, user, owner_id, field_name="sofor_id"):
      if cls.has_permission(user, Permission.ADMIN):
          return
      if cls.has_permission(user, Permission.READ):   # tüm rollerde READ var → herkes geçer
          return
      raise HTTPException(403, ...)
  ```
- Sorun: Metodun adı/imzası sahiplik denetimi vaadediyor (`owner_id`, `field_name` alıyor) ama
  `owner_id` **hiç kullanılmıyor**. `ROLE_PERMISSIONS`'ta `driver` ve `user` rollerinin ikisi de
  READ'e sahip → her kimliği doğrulanmış kullanıcı **her** seferi görür. `sefer_read_service.py:40`
  çağrısı sefer-bazlı izolasyon uyguluyormuş gibi görünüp aslında uygulamıyor → sürücü kendi
  olmayan seferleri okuyabilir. Tek-tenant tasarımı kasıtlı (CLAUDE.md) ama imza yanıltıcı; ileride
  bir çağıran bunun izolasyon uyguladığını varsayacak (footgun).
- Önerilen düzeltme: ya `owner_id`'yi gerçekten uygula (sürücü self-only), ya da parametreyi kaldırıp
  metodu `verify_read_access` gibi yeniden adlandır; çağrı yerini netleştir.

### AUDIT-024 — `update_user` IntegrityError'ı yakalamıyor → 500 (create_user 400 dönerken)
- Şiddet: medium · Sınıf: error-handling / consistency · Durum: confirmed
- Konum: `app/core/services/user_service.py:69-90` (krş. `create_user:50-60` IntegrityError yakalıyor)
- Kanıt: `update_user` doğrudan `await uow.kullanici_repo.update(...)` + `await uow.commit()` çağırıyor;
  `create_user`'daki `try/except IntegrityError` koruması yok.
- Sorun: e-postayı mevcut başka kullanıcınınkiyle çakışacak şekilde güncellemek (unique ihlali) veya
  geçersiz `rol_id` vermek (FK ihlali) → `commit()` `IntegrityError` fırlatır, yakalanmaz → istemciye
  **500** döner. Aynı hatalar `create_user`'da temiz **400** dönüyor. Tutarsız API + sızdıran iç hata.
- Önerilen düzeltme: `update_user`'ı `create_user`'la aynı IntegrityError→400 eşlemesine sar.

### AUDIT-025 — `update_user` `if v is not None` filtresi nullable alanları NULL'a çekmeyi engelliyor
- Şiddet: low · Sınıf: bug / data-integrity · Durum: confirmed
- Konum: `app/core/services/user_service.py:76`
- Kanıt: `update_data = {k: v for k, v in data.items() if v is not None}`
- Sorun: `sofor_id=None` göndererek bir kullanıcının sürücü bağını kaldırmak (veya başka nullable
  alanı temizlemek) sessizce düşürülür — güncelleme uygulanmaz, kullanıcıya hata da dönmez. "None
  atlama" deseni partial-update'te yaygın ama burada anlamlı bir iş alanını (sofor_id unlink) bloke
  ediyor.
- Önerilen düzeltme: Pydantic `model_fields_set` / `exclude_unset` ile "gönderilmedi" vs "None'a çek"
  ayrımı yap.

> Not (low, ayrı bulgu değil): `auth_service.py:84` oturum IP'si `request.client.host` ile alınıyor
> (X-Forwarded-For değil) → reverse-proxy arkasında oturum kayıtlarına proxy IP'si yazılır
> ([[AUDIT-006]] ile aynı kök neden). Güvenlik logu doğruluğu etkilenir.

### AUDIT-026 — Cashflow projeksiyonu horizon artık günlerini düşürüyor → grand_total eksik sayıyor
- Şiddet: medium · Sınıf: domain-rule / financial · Durum: confirmed
- Konum: `app/core/services/cashflow_projector.py:145,152-172` (krş. SQL penceresi `:82-83`)
- Kanıt:
  ```python
  weeks_count = max(1, horizon_days // 7)     # 90 // 7 = 12 hafta = 84 gün
  for w in range(weeks_count):
      week_start = today + timedelta(days=w * 7)
      week_end = week_start + timedelta(days=7)   # son hafta: gün 77..83
  ```
- Sorun: SQL yakıt sorgusu `CURRENT_DATE + (:h * INTERVAL '1 day')` ile **90 günü** çekiyor, ama
  haftalık döngü yalnız `horizon_days // 7 = 12` hafta = **84 gün**i kovalara dağıtıyor. Gün 84-89
  arasındaki yakıt (`tahmini_tuketim`) ve bakım tahminleri çekiliyor ama hiçbir haftaya girmeden
  düşüyor → `total_fuel` / `grand_total_tl` belirtilen 90-günlük horizon'a göre ~6-7 günlük yakıtı
  **eksik** gösterir. Başlık rakamı (grand_total) sessizce gerçek pencereden az.
- Önerilen düzeltme: `weeks_count = ceil(horizon_days / 7)` kullan, son haftayı `min(week_end, horizon_end)`
  ile kırp; veya SQL penceresini bucketlenen güne (84) eşitle (tercih: tam horizon'u say).

### AUDIT-027 — Cashflow `date.today()` (yerel) vs SQL `CURRENT_DATE` (DB tz) + docstring min uyumsuz
- Şiddet: low · Sınıf: consistency / doc-drift · Durum: confirmed
- Konum: `app/core/services/cashflow_projector.py:127` (`today = date.today()`) vs `:82` (`CURRENT_DATE`);
  ayrıca `:72-73` (`if horizon_days < 7: horizon_days = 7`) vs docstring `:61` ("min 14")
- Sorun: (1) Python tarafı `date.today()` (sunucu yerel) ile SQL `CURRENT_DATE` (DB session tz) ayrı
  saat dilimlerindeyse hafta kovalama ile SQL filtresi bir gün kayar. Proje başka yerde `current_date()`
  clock util'i kullanıyor (cost_analyzer.py:122) — tutarsız. (2) Docstring "min 14" diyor, kod min 7
  uyguluyor → API sözleşmesi belgeyle çelişir.
- Önerilen düzeltme: `current_date()` util'ini kullan; min sınırını docstring ile eşitle.

### AUDIT-028 — `get_vehicle_cost_comparison` N eşzamanlı UoW + atıl dış transaction → bağlantı havuzu baskısı
- Şiddet: medium · Sınıf: performance / resource-leak · Durum: confirmed
- Konum: `app/core/services/cost_analyzer.py:120-163` (dış `UnitOfWork`), her araç için
  `calculate_period_cost` `:44` kendi `UnitOfWork`'ünü açıyor; `asyncio.gather` `:161`
- Kanıt:
  ```python
  async with UnitOfWork() as uow:                     # 120 — dış session
      vehicles = await uow.arac_repo.get_all(...)      # tek kullanım
      ...
      comparisons = await asyncio.gather(              # 161 — dış session AÇIK iken
          *[calculate_for_vehicle(v) for v in vehicles])  # her biri YENİ UoW açar
  ```
- Sorun: Dış `uow` yalnız `get_all` için kullanılıp gather boyunca **atıl-in-transaction** açık
  kalıyor; aynı anda gather M aracın her biri için `calculate_period_cost` içinde **ayrı** bir
  `UnitOfWork`/session açıyor → M+1 eşzamanlı DB bağlantısı. Büyük filoda asyncpg havuzu tükenir
  (`pool timeout`), küçük filoda dahi gereksiz bağlantı tüketimi.
- Önerilen düzeltme: dış `uow`'u kapat (veya tek uow'u inner çağrılara paylaştır — `calculate_period_cost`'a
  opsiyonel `uow` parametresi); gather concurrency'sini `Semaphore` ile sınırla.

### AUDIT-029 — `YakitTahminService` singleton paylaşılan mutable model state (kırılgan eşzamanlılık)
- Şiddet: medium · Sınıf: concurrency / arch-fragility · Durum: needs-verification (bugün güvenli, kırılgan)
- Konum: `app/core/services/yakit_tahmin_service.py:27` (`self.model = LinearRegressionModel()`),
  `:116-124` (predict her çağrıda paylaşılan instance'a per-araç param yüklüyor)
- Kanıt:
  ```python
  self.model.coefficients = np.array(params["coefficients"]["weights"])   # 116
  self.model.intercept = params["coefficients"]["intercept"]
  self.model._is_fitted = True
  ... y_pred, meta = self.model.predict(X_input)                          # 133
  ```
- Sorun: Servis SINGLETON (container property, docstring `:5-8`) ama `predict()` paylaşılan
  `self.model`'i araç-bazlı parametrelerle **mutate** ediyor. **Bugün güvenli**: 116→133 arası `await`
  yok, dolayısıyla load+predict atomik (event loop araya başka isteği sokamaz). Ancak bu güvenlik
  yalnızca o sıralamaya bağlı — ileride 116-133 arasına herhangi bir `await` eklenirse iki eşzamanlı
  predict çağrısı modeli birbirinin araç ağırlıklarıyla ezer (yanlış araca yanlış model). `retrain_all_models`
  3 eşzamanlı `train_model` çalıştırıp aynı `self.model.fit`'i çağırıyor (şimdilik `result` dönüşten
  okunduğu için kontaminasyon yok). Mimari koku + latent yarış yüzeyi.
- Önerilen düzeltme: predict/train içinde **yerel** bir model instance kullan (paylaşılan state'i kaldır);
  veya servisi per-request yap. En azından load+predict'i tek senkron blokta tut (regresyon testi ekle).

> Not (low): `yakit_tahmin_service.py:103` `sofor_id: int = None` → tip `Optional[int]` olmalı
> (proje `--no-strict-optional` ile mypy'den kaçıyor; doğru tip yine de gerekli).

### AUDIT-030 — `YakitService.get_stats` dashboard yolunda tarih filtrelerini sessizce yok sayıyor
- Şiddet: medium · Sınıf: bug / silent-failure · Durum: confirmed
- Konum: `app/core/services/yakit_service.py:307-327`; `get_dashboard_stats(self, today_utc=None)`
  (`analiz_repo.py:202`) tarih aralığı parametresi **almıyor**.
- Kanıt:
  ```python
  async def get_stats(self, baslangic_tarih=None, bitis_tarih=None):
      dashboard = await uow.analiz_repo.get_dashboard_stats()   # tarih filtresi YOK
      if dashboard:
          return {... **dashboard}                              # filtreli istek → global döner
      ...
      return await uow.yakit_repo.get_stats(baslangic_tarih=..., bitis_tarih=...)  # yalnız fallback'te
  ```
- Sorun: Çağıran `baslangic_tarih`/`bitis_tarih` geçse bile dashboard yolu başarılıysa **global**
  (filtre uygulanmamış) istatistikler döner; tarih-filtreli `yakit_repo.get_stats` yalnız dashboard
  boş/hata verdiğinde çalışır. Kullanıcı "bu ay" filtreler, tüm-zaman rakamı görür → sessiz yanlış sonuç.
- Önerilen düzeltme: tarih filtresi verildiğinde dashboard kısayolunu atla, doğrudan filtreli
  `yakit_repo.get_stats`'ı çağır.

### AUDIT-031 — `bulk_add_yakit` tekil `add_yakit`'in doğrulamalarını baypas ediyor
- Şiddet: medium · Sınıf: data-integrity / consistency · Durum: confirmed
- Konum: `app/core/services/yakit_service.py:336-393` (krş. `add_yakit:120-185`)
- Kanıt: bulk yol yalnız `litre > 0` (`:353`) ve KM-monotonluk (`:356`) kontrol ediyor. `add_yakit`'te
  bulunan şu kontroller bulk'ta **yok**: aktif/var-olan araç (`:124-128`), `fiyat_tl > 0` (`:133-134`),
  ileri-tarih reddi (`:141-142`), duplicate kontrolü (`:144-153`).
- Sorun: Excel/toplu import yolu, tekil girişte engellenen kötü veriyi sessizce kabul eder: pasif araca
  yakıt, `fiyat_tl <= 0` (→ `toplam_tutar=0`/negatif), gelecek tarih, mükerrer kayıt. Maliyet
  raporları bozulur. Aynı iş kuralı iki yolda farklı uygulanıyor.
- Önerilen düzeltme: doğrulamayı ortak bir yardımcıya çıkar; bulk yol da aktif-araç/fiyat/tarih/duplicate
  kontrollerini uygulasın (geçersizleri rapor edip atlasın, sessizce kabul etmesin).

### AUDIT-032 — `delete_yakit` finansal kaydı HARD-delete ediyor + `@audit_log` yok
- Şiddet: medium · Sınıf: data-integrity / audit-gap · Durum: confirmed
- Konum: `app/core/services/yakit_service.py:211-233`
- Kanıt:
  ```python
  @monitor_errors(...)
  @publishes(EventType.YAKIT_DELETED)      # @audit_log YOK (update_yakit:188'de var)
  async def delete_yakit(self, yakit_id):
      success = await uow.yakit_repo.hard_delete(yakit_id)   # kalıcı silme
  ```
- Sorun: Diğer varlıklar soft-delete (`aktif=False`) kullanırken yakıt alımı (finansal kayıt) **kalıcı**
  siliniyor — geri dönüş/iz yok. Ayrıca `update_yakit` `@audit_log("UPDATE","yakit")` taşırken
  `delete_yakit`'te audit decorator yok → en yıkıcı işlemin denetim kaydı yok. `admin_audit_log`'a
  "kim sildi" düşmez.
- Önerilen düzeltme: `@audit_log("DELETE","yakit")` ekle; finansal kayıt için soft-delete tercih et
  (raporların `aktif=TRUE` filtresiyle — bkz. [[AUDIT-015]]).

### AUDIT-033 — Sefer onayında `onaylayan_id` DB'ye yazılmıyor (yalnız log) + audit yok + atomik değil
- Şiddet: medium · Sınıf: audit-gap / data-integrity · Durum: confirmed
- Konum: `app/core/services/sefer_service.py:188-213`; repo `set_onay_durumu(sefer_id, yeni_durum, onay_notu)`
  imzası `onaylayan_id` **almıyor** (`sefer_repo.py:736`)
- Kanıt:
  ```python
  updated = await self.repo.set_onay_durumu(sefer_id, yeni_durum, onay_notu)  # onaylayan_id geçmiyor
  ...
  logger.info("set_onay_durumu: ... by user_id=%s", ..., onaylayan_id)        # yalnız log
  ```
- Sorun: Sefer onay/red sensitif bir finansal-kontrol aksiyonu; ama **kim onayladı** kalıcı saklanmıyor
  (sadece uygulama logunda). `@audit_log` decorator da yok. Ek olarak işlem 3 ayrı round-trip (before-read,
  repo update kendi transaction'ında commit, after-read) → atomik değil; biri başarısızsa tutarsız ara durum.
- Önerilen düzeltme: `onaylayan_id` + zaman damgasını sefer/onay tablosuna yaz; `@audit_log("APPROVE","sefer")`
  ekle; oku-yaz-oku'yu tek UoW'da topla.

### AUDIT-034 — `get_by_onay_durumu` N+1: zaten dolu satırları id ile yeniden çekiyor
- Şiddet: low · Sınıf: performance · Durum: confirmed
- Konum: `app/core/services/sefer_service.py:215-225`
- Kanıt:
  ```python
  rows = await self.repo.get_by_onay_durumu(onay_durumu, skip=skip, limit=limit)  # tam _to_dict satırlar
  for row in rows:
      data = await self.read_service.get_sefer_by_id(row["id"])   # her satır için yeni sorgu
  ```
- Sorun: Repo `get_by_onay_durumu` zaten `_to_dict(s)` ile **tam** sefer sözlüklerini döndürüyor
  (`sefer_repo.py:781`). Servis her satırı `id` ile tekrar sorguluyor → N+1 (50 satır = 51 sorgu).
- Önerilen düzeltme: repo'nun döndürdüğü satırları doğrudan kullan (detay gerekiyorsa repo'da JOIN'le çek).

> Not (low): `sefer_read_service.py:92` except bloğunda `r.get('id')` — `r` dict değilse (line 89
> defensif `dict(r)` ima ediyor) `Row.get` yok → log satırı AttributeError fırlatıp asıl hatayı maskeler.

### AUDIT-035 — `bulk_add_arac` pasif-plaka çakışmasında batch'i çökertir + reaktivasyon/spec-timeline yok
- Şiddet: medium · Sınıf: consistency / data-integrity · Durum: confirmed
- Konum: `app/core/services/arac_service.py:357-402` (krş. `_create_arac_impl:93-159` reaktivasyon)
- Kanıt:
  ```python
  existing_plakalar = await uow.arac_repo.get_aktif_plakalar()   # YALNIZ aktif plakalar
  existing_set = set(existing_plakalar)
  for data in data_list:
      if data.plaka in existing_set:    # pasif (aktif=False) plaka burada YOK → eklenmeye çalışılır
          continue
  ...
  ids = await uow.arac_repo.bulk_create(to_add)   # plaka unique (ix_araclar_plaka) → IntegrityError
  ```
- Sorun: `plaka` DB'de `unique=True` (`models.py:75`). Tekil `create_arac` pasif araçları
  **reaktive** ederken (`:97-115`), bulk yol yalnız *aktif* plakaları dışlıyor → import edilen plaka
  pasif bir araca aitse `bulk_create` unique ihlaliyle **tüm batch'i** patlatır (kısmi-başarı yok).
  Ayrıca bulk yol `VehicleSpecTimeline` oluşturmuyor (tekil create `:148` oluşturuyor) → bulk araçların
  ilk spesifikasyon kaydı yok. Aynı iş kuralı iki yolda farklı.
- Önerilen düzeltme: bulk'ta pasif plakaları da çekip reaktive et (veya per-row upsert); spec timeline
  ekle; batch'i kısmi-başarı toleranslı yap.

### AUDIT-036 — `asyncio.Lock` TOCTOU guard'ı süreç-yerel → çok-worker'da etkisiz + throughput darboğazı
- Şiddet: low · Sınıf: concurrency / arch · Durum: confirmed
- Konum: `app/core/services/arac_service.py:47` (`self._lock = asyncio.Lock()`), `:94,177` kullanım
- Kanıt: `AracService` container singleton (tek süreç içi). `self._lock` araç create/update'i
  serialize ediyor. Plaka için gerçek güvenlik DB unique index'i (`ix_araclar_plaka`).
- Sorun: (1) Gunicorn/uvicorn çok-worker veya çok-konteyner kurulumda lock **süreç-yerel** — iki
  worker aynı anda plaka kontrolünü geçip insert deneyebilir; gerçek koruma yine DB unique constraint
  (yani lock gereksiz güvenlik hissi). (2) Tek süreçte dahi **tüm** araç yazımlarını seri hale getirir
  → throughput darboğazı (bulk dönemde belirgin). (3) `get_by_plaka(for_update=True)` var-olmayan satırda
  hiçbir şey kilitlemez (INSERT TOCTOU'yu çözmez) — backstop yalnız unique constraint.
- Önerilen düzeltme: lock'u kaldır, unique-violation'ı yakalayıp 409/reaktivasyona çevir (DB'ye güven).

### AUDIT-037 — `reconcile_costs` yakıt=0 günde tüm seferlerin tüketimini sessizce 0'a yazıyor
- Şiddet: medium · Sınıf: data-integrity / domain-rule · Durum: confirmed
- Konum: `app/core/services/sefer_analiz_service.py:59,70,88-96`
- Kanıt:
  ```python
  total_fuel_liters = sum(float(f["litre"]) for f in daily_fuels)   # yakıt yoksa 0
  if total_daily_km <= 0: return {... "skipped"}                    # km guard VAR
  # total_fuel_liters <= 0 için guard YOK:
  allocated = total_fuel_liters * ratio          # = 0
  consumption = (allocated / t_km) * 100          # = 0
  await uow.sefer_repo.update_sefer(t_id, tuketim=consumption, dagitilan_yakit=allocated)  # tuketim=0 yazılır
  ```
- Sorun: O gün/araç için henüz yakıt girişi yokken (veya hepsi soft-delete) reconcile çağrılırsa,
  total_fuel=0 → o günkü **tüm** seferlerin `tuketim`'i 0'a ezilir (önceki gerçek/tahmini değer kaybolur).
  Async job (`reconcile_costs`) yakıt girişinden önce tetiklenirse sessiz veri bozulması. km için guard
  var ama yakıt için yok.
- Önerilen düzeltme: `if total_fuel_liters <= 0: return {"status":"skipped","reason":"no fuel"}` ekle
  (km guard'ıyla simetrik); mevcut tüketimi ezme.

> Not: `reconcile_costs:54-58` `daily_fuels` yakıt sorgusu `aktif=TRUE` filtreliyor mu — [[AUDIT-015]]
> kapsamında; filtrelemiyorsa soft-delete yakıt dağıtıma girer. `dorse_service.py` ince geçiş katmanı,
> kritik bulgu yok (yalnız `search: str = None` → `Optional[str]` tip gevşekliği + `import_trailers`
> satır-satır create = N transaction; düşük öncelik).

### `sefer_write_service.py` (1484 satır — tam okundu)

### AUDIT-038 — Legacy `_predict_outbound` timeout fallback'i `record_silent_fallback` ile kaydedilmiyor
- Şiddet: medium · Sınıf: observability / silent-failure · Durum: confirmed
- Konum: `app/core/services/sefer_write_service.py:561-567` (legacy yol) vs `:453-464` (estimator yolu)
- Kanıt:
  ```python
  # estimator yolu (:463):
  except _asyncio.TimeoutError:
      record_silent_fallback("sefer_estimator_timeout", arac_id=data.arac_id)   # KAYIT VAR
      return None, None, None
  # legacy yol (:561):
  except _asyncio.TimeoutError:
      logger.warning("Prediction timeout (>2.5s) ...")   # SADECE log, record_silent_fallback YOK
      return None, None, None
  ```
- Sorun: 2.5s timeout'ta sefer tahminisiz kaydediliyor (silent fallback). Estimator yolu bunu
  `silent_fallback_probe`'a yazıyor (→ `/admin/fuel-accuracy coverage_pct`), legacy yol yazmıyor.
  `USE_SEFER_FUEL_ESTIMATOR=False` (varsayılan) olan tüm ortamlarda timeout-fallback'ler görünmez →
  coverage metriği tahmin kaybını eksik raporlar. İki yol gözlemlenebilirlik açısından asimetrik.
- Önerilen düzeltme: legacy timeout dalına da `record_silent_fallback("sefer_prediction_timeout", ...)` ekle.

### AUDIT-039 — `add_sefer` tahmini ağırlık-senkronizasyonundan ÖNCE çalıştırıyor → dolu/boş-only veride ton=0 tahmin
- Şiddet: medium · Sınıf: domain-rule / ordering · Durum: confirmed
- Konum: `app/core/services/sefer_write_service.py:851` (predict) vs `:856` (`_sync_weight_fields`); `:546`
- Kanıt:
  ```python
  tahmini_tuk, ... = await self._predict_outbound(uow, data, trip_date, route_dict)   # 851 — net_kg HENÜZ türetilmemiş
  self._sync_weight_fields(data, arac)                                                # 856 — net = dolu - bos burada hesaplanıyor
  # _predict_outbound içinde (:546):
  ton=data.ton or round(data.net_kg / 1000, 2)   # net_kg None ise TypeError (try yutar → tahminsiz)
  ```
- Sorun: Kullanıcı `dolu_agirlik_kg`+`bos_agirlik_kg` gönderip `net_kg` göndermezse, tahmin (851)
  `net_kg=0` ile çalışır → `ton=0` → **boş yük** için tahmin üretilir; oysa kayıt sonradan
  (856) `net = dolu - bos > 0` ile saklanır. Tahmin saklanan tonajla **uyuşmaz** → yanlış/düşük
  yakıt tahmini. Ayrıca `:546` `round(data.net_kg/1000,2)` None-güvensiz (schema default'una bağımlı);
  estimator yolu (`:421`) `if data.net_kg else 0.0` ile güvenli — asimetrik.
- Önerilen düzeltme: `_sync_weight_fields`'i `_predict_outbound`'tan **önce** çağır; predict türetilmiş
  `data.ton`/`data.net_kg`'yi kullansın. `:546`'yı None-güvenli yap.

### AUDIT-040 — `bulk_add_sefer` net clamp'i `ck_seferler...net_kg_calc` CHECK kısıtını ihlal ediyor
- Şiddet: medium · Sınıf: bug / data-integrity · Durum: confirmed
- Konum: `app/core/services/sefer_write_service.py:1374-1394`
- Kanıt:
  ```python
  bos_kg  = float(data.bos_agirlik_kg or arac_bos_map.get(data.arac_id, 0) or 0)
  net_kg  = float(data.net_kg or 0)
  dolu_kg = float(data.dolu_agirlik_kg or (bos_kg + net_kg))
  net_kg  = max(dolu_kg - bos_kg, 0.0)    # 1381 — net'i 0'a clamp'ler AMA dolu/bos'u bırakır
  ... "net_kg": net_kg, "dolu_agirlik_kg": dolu_kg, "bos_agirlik_kg": bos_kg
  ```
- Sorun: DB kısıtı `net_kg = dolu_agirlik_kg - bos_agirlik_kg` (CLAUDE.md). Kullanıcı `dolu < bos`
  veren bir satır gönderirse `max(dolu-bos, 0)=0` ile net=0 yazılır ama dolu/bos olduğu gibi kalır →
  `0 ≠ dolu-bos (<0)` → **CheckViolationError** → `bulk_create` tüm batch'i rollback eder (`:1418`).
  Clamp "negatifi engelleme" niyetiyle yazılmış ama tam tersine kısıtı kıran tutarsız üçlü üretiyor.
  Tekil yol (`_sync_weight_fields:592`) bunu dostça `ValueError` ile reddediyor — bulk'ta tek kötü
  satır tüm import'u düşürür.
- Önerilen düzeltme: `dolu < bos` satırını reddet/atla (tekil yoldaki gibi) veya `dolu = bos + net`
  ile tutarlı yeniden hesapla; net'i tek başına clamp'leme.

### AUDIT-041 — `bulk_add_sefer` tekil `add_sefer`'in doğrulamalarını baypas ediyor (arac/sofor aktif, sefer_no dup, tarih)
- Şiddet: medium · Sınıf: consistency / data-integrity · Durum: confirmed
- Konum: `app/core/services/sefer_write_service.py:1233-1421` (krş. `add_sefer:807-833,199-204`)
- Kanıt: bulk yol yalnız `mesafe_km > 0` (`:1278`) ve `cikis != varis` (`:1293`) kontrol ediyor.
  `add_sefer`'deki şu kontroller bulk'ta **yok**: araç var/aktif (`:817-824`), şoför var/aktif
  (`:826-833`), `sefer_no` mükerrer kontrolü (`:807-814`), tarih-1-yıldan-ileri reddi (`:199-204`).
- Sorun: Toplu import pasif/var-olmayan araç-şoföre sefer açabilir (FK yalnız var-olmayanı yakalar,
  pasifi değil), mükerrer `sefer_no` ekleyebilir (unique varsa batch çöker, yoksa dup), 1 yıldan ileri
  tarih kabul eder. Aynı iş kuralı iki yolda farklı uygulanıyor ([[AUDIT-031]], [[AUDIT-035]] ile aynı desen).
- Önerilen düzeltme: doğrulamaları ortak yardımcıya çıkar; bulk her satırı doğrulayıp geçersizi
  rapor edip atlasın.

### AUDIT-042 — `bulk_add_sefer` >20 batch'te tahmini sessizce atlıyor (keyfi eşik, çağırana sinyal yok)
- Şiddet: low · Sınıf: silent-behavior · Durum: confirmed
- Konum: `app/core/services/sefer_write_service.py:1324`
- Kanıt: `skip_prediction = len(sefer_list) > 20` → 21+ satırlık batch'te tüm seferler `tahmini_tuketim=None`.
- Sorun: 20 satır tahmin alır, 21 satır hiç almaz (keyfi uçurum). Gerekçe (geçmiş import'ta gerçek
  tüketim var) belgelenmiş ama bu yeni planlı seferlerin toplu girişinde de geçerli sayılıyor; çağırana
  "tahmin atlandı" sinyali dönmüyor. Sonuç dashboard coverage'ını sessizce etkiler.
- Önerilen düzeltme: eşiği "is_real/geçmiş veri" bayrağına bağla (satır sayısına değil); response'a
  `predictions_skipped` sinyali ekle.

> Not (low): `add_sefer:782-784` `if route_pair_id and not guzergah_id: pass` — boş placeholder
> (yorum "resolve logic here" diyor, no-op). route_pair_id repo'ya ham geçiyor, guzergah_id'ye
> çözülmüyor → eksik/ölü özellik. Ayrıca `_repredikt_for_update:335` tahmin hatasını yutuyor →
> tahmin-etkileyen alan değişse de eski `tahmini_tuketim` bayat kalır (sessiz).

### AUDIT-044 — `SoforAnalizService` uow-bağlı iken paralel elite-score gather aynı AsyncSession'ı eşzamanlı kullanıyor
- Şiddet: high · Sınıf: concurrency · Durum: needs-verification (runtime crash; yüksek güven)
- Konum: `app/core/services/sofor_analiz_service.py:92-98` (gather) → `:326,330` (paylaşılan session);
  bağlama yeri `app/api/v1/endpoints/advanced_reports.py:168-169` (`SoforAnalizService(uow=uow)` →
  `get_driver_stats()` `include_elite_score` default True)
- Kanıt:
  ```python
  elite_scores = await asyncio.gather(*[                      # 92 — tüm şoförler eşzamanlı
      self.calculate_elite_performance_score(sid, ...) for sid in sofor_ids])
  # calculate_elite içinde:
  sefer_repo = self._uow.sefer_repo if self._uow else get_sefer_repo()   # 326 — uow varsa PAYLAŞILAN session
  seferler = await sefer_repo.get_all(filters={"sofor_id": sofor_id}, ...)  # 330 — N task aynı session'da
  ```
- Sorun: (1) Servis uow'a bağlıyken (`SoforAnalizService(uow=uow)` veya `get_driver_stats(uow=...)`),
  `gather` her şoför için `calculate_elite`'i **eşzamanlı** çalıştırır; her biri `self._uow.sefer_repo`
  (aynı `AsyncSession`) üzerinde `get_all` yapar. SQLAlchemy/asyncpg tek session/bağlantıda eşzamanlı
  işlemi **yasaklar** (`InterfaceError: another operation is in progress`) → advanced_reports raporu
  patlayabilir. (2) Servis CONTAINER SINGLETON (`container.py:443`) ve `self._uow` çağrı sonunda
  **hiç sıfırlanmıyor** — bir çağrı `uow` geçerse singleton'ın `self._uow`'u o (muhtemelen kapanmış)
  session'da kalır; sonraki uow'suz çağrılar (`if uow:` false) onu kullanır → çapraz-istek session sızması.
- Önerilen düzeltme: temporal `self._uow` binding'i kaldır — uow'u parametre olarak repo'lara aktar
  (state'siz); elite gather'ı her task kendi session'ını açan repo singleton'larıyla çalıştır veya
  semaphore+session-per-task ile izole et.

### AUDIT-045 — Elite-score yolu masif N+1 (şoför × sefer × tahmin × 5 fetch) — "N+1 yok" iddiasıyla çelişiyor
- Şiddet: medium · Sınıf: performance · Durum: confirmed
- Konum: `app/core/services/sofor_analiz_service.py:85-98` (tüm şoförler), `:330-366` (her şoför için
  her seferde `predict_consumption`)
- Kanıt: `get_driver_stats` docstring "N+1 probleminden arındırılmış" diyor; ama
  `calculate_elite_performance_score` her şoförün son `ELITE_SCORE_TRIP_LIMIT` seferi için
  `pred_service.predict_consumption` çağırıyor (`:347`) ve her predict 5 taze DB fetch yapıyor
  (bkz. [[AUDIT-041]] yorumu). 50 şoför × 20 sefer × 5 fetch ≈ 5000 sorgu/dashboard.
- Sorun: Bulk metrik sorgusu N+1'i çözüyor ama elite-score yolu çok daha büyük bir N+1'i geri getiriyor.
  Dashboard/rapor endpoint'lerinde ağır gecikme + DB yükü.
- Önerilen düzeltme: elite skoru için seferleri toplu çek, tahmini batch'le (veya kayıtlı gerçek
  tüketim varsa tahmini atla); fan-out'u sınırla.

> Not (low): `sofor_analiz_service.py:386-419` `calculate_performance_score` (base=50) **ölü kod** —
> hiçbir yerden çağrılmıyor (kullanılan: elite base=75 formülü; `report_service._calculate_performance_score`
> ayrı bir metod). İki ayrı puanlama formülü kafa karıştırıcı. Ayrıca `calculate_elite_performance_score`
> `-> float` annotate ama `None` dönebiliyor (`:334,370`).

### AUDIT-047 — `calculate_hybrid_score` dış UoW + `self._lock` içindeyken kendi UoW'sunu açıyor (iç içe transaction)
- Şiddet: medium · Sınıf: concurrency / transaction · Durum: confirmed
- Konum: `app/core/services/sofor_service.py:232-260` (kendi `UnitOfWork`'ü `:237`); çağrı yerleri
  `update_sofor:157-163` ve `update_score:217` (her ikisi dış `UnitOfWork` + `self._lock` içinde)
- Kanıt:
  ```python
  async def update_score(self, sofor_id, score):
      async with UnitOfWork() as uow:        # dış session
          async with self._lock:             # lock TUTULUYOR
              hybrid_score = await self.calculate_hybrid_score(sofor_id, score)  # 2. UoW açar
  ...
  async def calculate_hybrid_score(...):
      async with UnitOfWork() as uow:        # 237 — İÇ İÇE / ikinci session
          stats_list = await uow.sofor_repo.get_sefer_stats(...)
  ```
- Sorun: Skor güncellemesi sırasında dış transaction + lock açıkken `calculate_hybrid_score` **ikinci**
  bir UoW/bağlantı açıyor. (1) İki ayrı transaction → hybrid skor dış update'in göremediği bağımsız
  snapshot'tan okunuyor (tutarlılık zayıf). (2) `self._lock` tutulurken ikinci bağlantı alınıyor →
  havuz baskısında lock-altında-bekleme riski. (3) Mimari koku: aynı mantığı paylaşan `get_score_breakdown`
  da ayrı UoW + ayrıca `self.repo.get_by_id` (singleton) karışık kullanıyor.
- Önerilen düzeltme: `calculate_hybrid_score`'a opsiyonel `uow` parametresi ver, çağıran dış uow'u paylaştır;
  ikinci session açma.

### AUDIT-048 — Üç uyumsuz şoför puanlama sistemi/ölçeği (hangisi "şoför skoru" belirsiz)
- Şiddet: medium · Sınıf: consistency / domain-rule · Durum: confirmed
- Konum: `sofor_service.calculate_hybrid_score:232-256` (0.1–2.0 çarpan, `score` kolonuna yazılır) ·
  `sofor_analiz_service.calculate_elite_performance_score:311-384` (0–100, kalıcı değil) ·
  `sofor_service.get_performance_details:460-525` (0–100 composite safety/eco/compliance, kalıcı değil)
- Sorun: Üç farklı formül + üç farklı ölçek aynı kavramı ("şoför performansı") temsil ediyor. `score`
  kolonu hybrid (0.1–2.0) tutarken, dashboard'lar 0–100 elite veya composite gösteriyor — biri persist,
  ikisi uçucu. `target_reference=30` üçünde de hard-code (tek yerden gelmiyor). Kullanıcı için "şoför
  skoru" tutarsız ve hangisinin otoriter olduğu belirsiz; raporlar arası çelişki üretir.
- Önerilen düzeltme: tek kanonik puanlama tanımla (ölçek + formül + referans config'den); diğerlerini
  bunun türevleri yap veya kaldır.

> Not (low): `sofor_service.py` `self._lock` aynı süreç-yerel guard ([[AUDIT-036]] ile aynı; `ad_soyad`
> DB'de `unique=True` olduğundan gerçek backstop o). Ek: isim-benzerliği olan gerçek iki şoför
> (`ad_soyad` unique) ikinci kaydı engellenir — iş anahtarı olarak tam-ad şüpheli domain kararı.
> `bulk_add_sofor:413-458` pasif-isim reaktivasyonunu atlıyor ([[AUDIT-035]] deseni).

### AUDIT-049 — `_sync_analyze_vehicle_consumption` NaN-filtreli indeksleri orijinal listeye uyguluyor → indeks kayması
- Şiddet: medium · Sınıf: bug / data-integrity · Durum: confirmed
- Konum: `app/core/services/anomaly_detection_service.py:134,141-143` ↔ filtre `:49-51`
- Kanıt:
  ```python
  # _sync_detect_anomalies içinde girdi YENİDEN filtreleniyor → indeksler FİLTRELİ listeye göre:
  consumptions = [c for c in consumptions if isinstance(c,(int,float)) and math.isfinite(c)]  # 49
  ... AnomalyResult(index=i, ...)                                                              # i = filtreli indeks
  # _sync_analyze içinde indeksler ORİJİNAL (filtresiz) listeye uygulanıyor:
  anomalies = self._sync_detect_anomalies(consumptions)                                        # 134
  clean_consumptions = [c for i,c in enumerate(consumptions) if i not in anomaly_indices]      # 141-143 ORİJİNAL
  ```
- Sorun: Girdi non-finite (NaN/inf) içeriyorsa detect içinde filtrelenir, dönen `index` filtreli
  konuma göre; `_sync_analyze` bu indeksi **orijinal** listeye uygular → **yanlış elemanlar** anomali
  sayılıp dışlanır, gerçek aykırı değer (örn. 100 L/100km) temiz ortalamada kalır → `ort_tuketim`
  bozulur. Filtre tam da "üst katmandan kirli veri" için var, yani tetiklenmesi olası.
- Önerilen düzeltme: filtrelemeyi tek yerde yap; detect'in temizlenmiş listeyi de döndürmesini sağla
  veya _sync_analyze aynı filtreyi uygulayıp indeksleri hizalasın.

### AUDIT-050 — `analyze_vehicle_consumption` cache yalnız arac_id ile anahtarlı (girdi yok) → bayat/çapraz sonuç
- Şiddet: low · Sınıf: caching / correctness · Durum: confirmed
- Konum: `app/core/services/anomaly_detection_service.py:119-128`
- Kanıt: `cache_key = f"arac:{arac_id}:stats"` (1 saat TTL); `consumptions` girdisi anahtara dahil değil.
- Sorun: Sonuç tamamen `consumptions`'a bağlı ama cache yalnız `arac_id`'ye anahtarlı. Aynı araç için
  farklı tüketim listesiyle çağrı → ilk çağrının sonucu döner (1 saat). Yeni sefer eklense de istatistik
  bayat kalır. Çağıranlar farklı alt-küme geçerse çapraz kontaminasyon.
- Önerilen düzeltme: anahtara girdi hash'i ekle veya yeni sefer/yakıt event'inde cache invalidasyonu yap.

### `anomaly_detector.py` (657 satır — ikinci, ayrı anomali alt-sistemi)

### AUDIT-051 — `train_lgb_classifier` var-olmayan İngilizce kolon adlarını okuyor → tüm eğitim öznitelikleri dejenere (ML çöp)
- Şiddet: high · Sınıf: bug / ml-correctness · Durum: confirmed
- Konum: `app/core/services/anomaly_detector.py:438-456`; DB kolonları `deger`/`beklenen_deger`/`sapma_yuzde`
  (`models.py` Anomaly), `get_recent_anomalies` `SELECT a.*` ile bu Türkçe adları döndürüyor.
- Kanıt:
  ```python
  value     = float(a.get("value", 0) or 0)                    # 'value' kolonu YOK → 0
  expected  = float(a.get("expected_value") or settings.DEFAULT_FILO_HEDEF_TUKETIM)  # 'expected_value' YOK → default
  deviation = float(a.get("deviation_pct", 0) or 0)            # 'deviation_pct' YOK → 0
  X.append([value, expected, deviation, abs(deviation), value/expected if expected>0 else 1.0])
  ```
- Sorun: Satır sözlüğünün gerçek anahtarları `deger`, `beklenen_deger`, `sapma_yuzde`. Kod İngilizce
  `value`/`expected_value`/`deviation_pct` okuyor → hepsi default'a düşüyor: her örnekte
  `value=0, expected=DEFAULT, deviation=0, abs=0, ratio=0/DEFAULT=0`. Yani **tüm X satırları aynı/sabit**
  → LightGBM sınıflandırıcı ayrım yapamaz, yalnız çoğunluk sınıfını öğrenir. `predict_severity_lgb`
  (gerçek değerlerle çağrılsa da) anlamsız/sabit ciddiyet döndürür; `detect_anomaly_hybrid` `use_ml=True`
  yolunda bu çöp modeli kullanır (`:565-566`). Raporlanan `accuracy` da çoğunluk-sınıf yanılsaması.
- Önerilen düzeltme: anahtarları `a.get("deger")`, `a.get("beklenen_deger")`, `a.get("sapma_yuzde")`
  olarak düzelt; bir regresyon testi ile feature varyansını doğrula.

### AUDIT-052 — İki örtüşen anomali alt-sistemi, ıraksak mantık (tutarsız sonuç)
- Şiddet: medium · Sınıf: consistency / arch-duplication · Durum: confirmed
- Konum: `AnomalyDetectionService._sync_detect_anomalies:77-94` (z VEYA iqr → MEDIUM) vs
  `AnomalyDetector.detect_consumption_anomalies:154` (`>= 2` → z VE iqr ikisi de gerekli)
- Sorun: İki ayrı servis aynı kavramı (tüketim anomalisi) farklı eşik mantığıyla hesaplıyor: biri
  tek yöntemle bile MEDIUM üretirken diğeri her iki yöntemin onayını şart koşuyor. Hangi servisin
  hangi endpoint'te kullanıldığına göre aynı veri için farklı anomali sayısı/ciddiyeti → tutarsızlık,
  bakım yükü, kullanıcı kafa karışıklığı.
- Önerilen düzeltme: tek anomali tespit çekirdeğinde birleştir; eşik politikasını config'den tek yerde tanımla.

> Not (medium/low): `anomaly_detector.detect_consumption_anomalies:165-166` `arac_id` None iken
> `kaynak_tip='sefer'` + `kaynak_id=i` (liste indeksi) kaydediyor → `get_recent_anomalies` JOIN
> `seferler ON kaynak_id=sf.id` yanlış/var-olmayan sefere bağlanır (veri kirliliği). Ayrıca
> `:197,557` `prediction["prediction_l_100km"]` doğrudan key erişimi — anahtar yoksa KeyError ile
> anomali tespiti çöker (başka yerlerde `.get(...,0)` kullanılıyor).

### Excel import pipeline (excel_column_map, excel_parser, excel_service — tam okundu)

### AUDIT-053 — `SafeColumnMapper.map_columns` exact-pass aynı internal_key'e BİRDEN FAZLA Excel kolonu bağlayabiliyor
- Şiddet: medium · Sınıf: bug / data-mapping · Durum: confirmed
- Konum: `app/core/services/excel_column_map.py:332-341` (exact pass) vs `:344-346` (fuzzy pass guard'ı var)
- Kanıt:
  ```python
  # exact pass — internal_key zaten map'lendi mi diye BAKMIYOR:
  for internal_key, aliases in cls.COLS.items():
      for alias in aliases:
          if alias in df_columns_clean:
              if excel_col not in claimed:
                  mapping[excel_col] = internal_key   # iki farklı excel_col aynı internal_key'e gidebilir
  # fuzzy pass — guard VAR:
  if internal_key in mapping.values(): continue       # 345
  ```
- Sorun: Excel'de hem "Tutar" hem "Toplam Tutar" (ikisi de `toplam_tutar` aliası) veya "Litre"+"Miktar"
  (ikisi de `litre`) varsa exact pass **ikisini de** aynı internal_key'e map'ler (`{"tutar":"toplam_tutar",
  "toplam tutar":"toplam_tutar"}`). Downstream pandas `rename` ile iki kolon aynı ada gelir → `df[key]`
  Series yerine DataFrame döndürür → satır işleme çöker veya rastgele biri seçilir. Fuzzy pass'teki
  many-to-one guard'ı exact pass'te yok.
- Önerilen düzeltme: exact pass'e de `if internal_key in mapping.values(): continue` ekle (ilk eşleşen alias kazansın).

### AUDIT-054 — Türkçe virgüllü ondalık sayılar sessizce 0'a çevriliyor (litre/fiyat/tutar/km/mesafe/net_kg)
- Şiddet: medium · Sınıf: bug / i18n / data-integrity · Durum: confirmed
- Konum: `app/core/services/excel_parser.py:42-51` (sefer), `:97-107` (yakit), `:138-142` (route)
- Kanıt:
  ```python
  if model_field == "litre" and val:
      val = round(float(val), 2)          # float("43,46") → ValueError
  ...
  except (ValueError, TypeError):
      val = 0                              # sessizce 0
  ```
- Sorun: Türkçe Excel hücreleri çoğu kez metin-formatlı virgül ondalıklıdır ("43,46", "1.234,5").
  `float("43,46")` ValueError fırlatır → `except` ile değer **sessizce 0**. Yani yakıt litresi/fiyatı,
  km, mesafe, net_kg metin-virgül geldiğinde 0 olur → maliyet/tüketim verisi sessizce yok edilir
  (kullanıcı "import başarılı" görür). Türkçe bir ürün için yüksek olasılıklı senaryo.
- Önerilen düzeltme: cast öncesi normalize et (binlik `.` kaldır, ondalık `,`→`.`); başarısız cast'i
  0'a düşürmek yerine satırı hata listesine ekle.

### AUDIT-055 — Tüm parser'lar zorunlu alanı eksik satırları SESSİZCE düşürüyor (sayı/sebep raporu yok)
- Şiddet: medium · Sınıf: silent-failure / ux · Durum: confirmed
- Konum: `excel_parser.py:63` (plaka+tarih), `:111` (yakit), `:146` (route), `:201` (vehicle plaka+marka),
  `:238` (driver ad_soyad), `:294` (dorse plaka)
- Kanıt: `if item.get("plaka") and item.get("tarih"): result.append(item)` — koşul sağlanmazsa satır
  hiçbir sinyal vermeden atlanır; `result` yalnız geçerli satırları taşır.
- Sorun: 100 satırlık Excel'in 30'unda tarih eksikse 30 satır sessizce düşer, kullanıcıya "70 içe
  aktarıldı" denir; hangi/kaç satırın neden atlandığı bilinmez. Veri-import ürününde kabul edilemez
  şeffaflık kaybı; e2e_pilot_smoke `errors == []` kontrolünü de yanıltabilir.
- Önerilen düzeltme: atlanan satırları satır-no + sebep ile bir `skipped`/`errors` listesinde döndür;
  parser sonucu `{"items": [...], "skipped": [...]}` zarfı olsun.

### AUDIT-056 — Araç parser'ı eksik kritik fiziksel parametrelere sihirli default uyduruyor (bos_agirlik=8000, hedef_tuketim=0.38)
- Şiddet: medium · Sınıf: bug / data-integrity · Durum: confirmed
- Konum: `app/core/services/excel_parser.py:188-197`
- Kanıt:
  ```python
  elif model_field in ["yil","tank_kapasitesi"]:
      val = safe_int(val, None if model_field=="yil" else 600)        # tank default 600
  elif model_field in ["bos_agirlik_kg","motor_verimliligi","hedef_tuketim"]:
      val = safe_float(val, 8000.0 if "agirlik" in model_field else 0.38)  # bos=8000, hedef=0.38(!)
  ```
- Sorun: (1) `bos_agirlik_kg` eksik/geçersizse **8000 kg** uydurulur — bu değer net_kg (`net=dolu-bos`)
  ve fizik yakıt tahminini doğrudan besler → o aracın tüm tahminleri yanlış zemine oturur, kullanıcı
  uydurma değeri fark etmez. (2) `hedef_tuketim` eksikse **0.38** atanır — hedef tüketim L/100km
  ölçeğinde ~30 olmalı; 0.38 ölçek olarak saçma (default `motor_verimliligi` ile karışmış) → hedefe-bağlı
  tüm skor/EEI hesapları bozulur.
- Önerilen düzeltme: kritik fiziksel parametreler eksikse satırı reddet (sessiz default uydurma);
  `hedef_tuketim` default'unu doğru ölçeğe (config'deki `DEFAULT_FILO_HEDEF_TUKETIM`) çek.

> Not (low): `_parse_date_flexible:373-380` `%d/%m/%Y` ve `%m/%d/%Y` ikisi de listede → "03/05/2024"
> belirsiz tarih satır-değerine göre farklı parse edilir (locale karışımı sessiz). Excel numeric
> serial tarihler (float) string değil → None'a düşer. `excel_parser` vehicle/dorse `safe_float/safe_int`
> her satır iç içe yeniden tanımlanıyor (stil/perf, düşük). `excel_service.py` saf facade — bulgu yok.

### `import_service.py` (905 satır — tam okundu)

### AUDIT-057 — `execute_import`/`rollback_import` yakıt yolu YANLIŞ tablo adı (`yakit_alimlar`, gerçek `yakit_alimlari`)
- Şiddet: high · Sınıf: bug · Durum: confirmed
- Konum: `app/core/services/import_service.py:380` (INSERT), `:457` (rollback DELETE); gerçek tablo
  `models.py:420` `__tablename__ = "yakit_alimlari"`
- Kanıt:
  ```python
  "INSERT INTO yakit_alimlar (arac_id, tarih, litre, toplam_tutar, km_sayac) ..."   # 380 — son 'i' yok
  stmt = text("DELETE FROM yakit_alimlar WHERE id = ANY(:ids)")                       # 457
  ```
- Sorun: Tablo adı `yakit_alimlari`; kod `yakit_alimlar` (sondaki "i" eksik) kullanıyor →
  `relation "yakit_alimlar" does not exist`. Admin generic import (`/admin/imports/commit`,
  `aktarim_tipi="yakit"`) her satırda patlar (per-row except → hepsi `hatali`, 0 başarılı), yakıt
  job'unun `rollback_import`'u 500 verir. (Domain yolu `process_yakit_import` ORM `bulk_add_yakit`
  kullandığından çalışıyor — yalnız bu generic yol kırık.)
  > Stale-test notu: `test_import_service_coverage.py:556` `assert any("yakit_alimlar" in s ...)` —
  > "yakit_alimlar", "yakit_alimlari"nin substring'i olduğu için yanlış adı yakalamıyor; mock DB'ye
  > vurmadığından gerçek hatayı maskeliyor.
- Önerilen düzeltme: her iki yerde `yakit_alimlari` yaz; testi gerçek tablo adına bağla (tam eşleşme).

### AUDIT-058 — `_validate_import_rows` mapping'i ters yönde kullanıyor olabilir → tüm satır okumaları None
- Şiddet: high · Sınıf: bug · Durum: needs-verification (frontend mapping yönü)
- Konum: `app/core/services/import_service.py:138,146,160,217` (`row.get(mapping.get(internal_key, internal_key))`)
- Kanıt:
  ```python
  plaka = row.get(mapping.get("plaka", "plaka"))   # row anahtarları EXCEL başlıkları
  ```
- Sorun: `row` sözlüğü Excel başlıklarıyla anahtarlı (`_parse_import_file` → `df.to_dict`). Kod
  `mapping.get(internal_key)` ile Excel başlığını bekliyor → yani mapping'in `{internal_key: excel_header}`
  yönünde olmasını varsayıyor. `SafeColumnMapper.map_columns` ise tersini (`{excel: internal}`) üretir.
  Mapping endpoint'e frontend'den JSON string olarak geliyor (`admin_imports.py:55,64`); yönü frontend
  belirliyor. Eğer frontend `{excel: internal}` gönderirse `mapping.get("plaka")` → "plaka" default →
  `row.get("plaka")` → Türkçe başlıklı Excel'de None → tüm çözümlemeler boş → admin import tümüyle kırık.
- Önerilen düzeltme: mapping yönünü tek bir sözleşmeye sabitle ve kodda açıkça belgele; gerekirse
  `{v:k}` ile ters çevir. **Frontend import UI'ının gönderdiği yön S8/S9'da doğrulanacak** (carry).

### AUDIT-059 — `process_vehicle_import` `AracCreate(**it)` list-comp'te tek kötü satır tüm import'u düşürür + iç içe UoW
- Şiddet: medium · Sınıf: error-handling / transaction · Durum: confirmed
- Konum: `app/core/services/import_service.py:697-732`
- Kanıt:
  ```python
  async with UnitOfWork() as uow:                          # dış UoW (reaktivasyon)
      ...
      arac_models = [AracCreate(**it) for it in to_add]     # 729 — biri geçersizse TÜM liste patlar
      count = await self.arac_service.bulk_add_arac(arac_models)  # bulk_add_arac KENDİ UoW'sunu açar
      await uow.commit()                                    # 731 — bulk'un commit'inden sonra
  ```
- Sorun: (1) `AracCreate(**it)` list-comprehension'ı tek geçersiz satırda `ValidationError` fırlatır →
  `except` (`:733`) tüm import'u "Sistem hatası" yapar; per-row hata izolasyonu yok (oysa döngüde
  `_validate_plaka` per-row yakalanıyor ama Pydantic doğrulaması toplu). (2) `bulk_add_arac` iç içe
  ikinci UoW açıyor ([[AUDIT-047]]/[[AUDIT-028]] deseni); reaktivasyon dış UoW'da, ekleme iç UoW'da →
  ayrık transaction sınırları (biri başarısızsa tutarsız).
- Önerilen düzeltme: `AracCreate(**it)`'i per-row try içine al, geçersizi errors'a ekle; bulk_add_arac'a
  paylaşılan uow geçir.

### AUDIT-060 — Sefer `execute_import` `bos_agirlik_kg=0` + birim-belirsiz "Yük"→`dolu_agirlik_kg` (ton kg gibi)
- Şiddet: medium · Sınıf: data-integrity / domain-rule · Durum: confirmed
- Konum: `app/core/services/import_service.py:173-179,207-210`
- Kanıt:
  ```python
  ton = self._validate_numeric(row.get(mapping.get("ton","ton"), 0), "Yük")
  bos_agirlik_kg = 0
  dolu_agirlik_kg = int(round(ton))            # 'ton' DEĞERİ kg olarak kullanılıyor
  ton = round(dolu_agirlik_kg / 1000.0, 2)
  ... "net_kg": dolu_agirlik_kg, "bos_agirlik_kg": 0, "dolu_agirlik_kg": dolu_agirlik_kg
  ```
- Sorun: (1) `bos_agirlik_kg` sabit 0 → seferin dolu ağırlığı = yalnız yük (aracın boş ağırlığı kayıp);
  CHECK kısıtı (`net=dolu-0`) geçer ama dolu/net semantiği fiziksel değil. (2) "Yük" kolonu ton mu kg mı
  belirsiz: değer ton ise (20) `dolu=20 kg`, `ton=0.02` → fizik tahmini 1000× hatalı; kg ise doğru.
  Birim doğrulaması yok. (Karşılaştır: `sefer_write._sync_weight_fields` aracın `bos_agirlik_kg`'sini
  kullanır — generic import bunu atlıyor.)
- Önerilen düzeltme: aracın master `bos_agirlik_kg`'sini çek, `dolu=bos+net` hesapla; "Yük" biriminin
  kg olduğunu doğrula/şablonda zorla.

> Not (low): `process_driver_import:736-747` `errors` listesi hiç doldurulmuyor → sürücü import satır
> hatası raporlamıyor (her zaman `[]`). `_normalize_text:868-871` yalnız büyük `İ→I` çeviriyor; Python
> Türkçe casing (`ı/i`) locale-duyarsız → güzergah eşleşmesi İstanbul/Istanbul/ıstanbul'da kaçabilir.

### AUDIT-061 — `recalculate_vehicle_periods` `depo_durumu`'yu YakitAlimi'ye taşımıyor → hiç periyot üretmiyor (özellik sessiz ölü)
- Şiddet: high · Sınıf: bug / silent-failure · Durum: confirmed
- Konum: `app/core/services/period_calculation_service.py:269-283` (entity inşası — `depo_durumu` YOK) ↔
  `_sync_create_fuel_periods:80-88,102-107` (sınır için `depo_durumu` "dolu"/"full" arar);
  `core/entities/models.py:340` `depo_durumu: str = Field(default="Bilinmiyor")`
- Kanıt:
  ```python
  fuel_records = [YakitAlimi(id=r["id"], tarih=..., arac_id=..., istasyon=..., fiyat_tl=...,
      litre=..., km_sayac=..., fis_no=r["fis_no"]) for r in raw_alimlar]   # depo_durumu PAS GEÇİLDİ → "Bilinmiyor"
  # algoritma:
  if "dolu" in status or "full" in status: start_idx = k   # "bilinmiyor"da asla True olmaz
  if start_idx == -1: continue                              # her araç atlanır → periyot=[]
  ```
- Sorun: Periyot algoritması dolu-depo sınırlarını `depo_durumu`'ndan bulur. `recalculate_vehicle_periods`
  entity'yi `depo_durumu` olmadan kuruyor → hepsi default "Bilinmiyor" → hiçbir "dolu/full" kaydı
  bulunamaz → `start_idx=-1` → **her araç atlanır, hiç periyot oluşmaz**. Bu metod her yakıt import'undan
  sonra çağrılıyor (`process_yakit_import:673`) → periyot-tabanlı tüketim türetme özelliği bu giriş
  noktasından **tamamen sessiz çalışmıyor** (DB'de depo_durumu verisi mevcut, ama entity'ye taşınmıyor).
  (`if periods:` boş olduğundan `save_fuel_periods(clear_existing=True)` çağrılmıyor → veri silinmiyor,
  ama cache yine de temizleniyor.)
- Önerilen düzeltme: entity inşasına `depo_durumu=r["depo_durumu"]` ekle; periyot üretiminin >0 olduğunu
  doğrulayan regresyon testi yaz.

### AUDIT-062 — `distribute_fuel_to_trips` kg boş-ağırlık + ton yük karıştırıyor → "Ton-Km" dağıtım ~Km'ye dejenere
- Şiddet: medium · Sınıf: bug / domain-rule · Durum: confirmed
- Konum: `app/core/services/period_calculation_service.py:171-180`; `config.py:196`
  `HGV_EMPTY_WEIGHT: float = 8000.0  # kg`
- Kanıt:
  ```python
  empty_weight = settings.HGV_EMPTY_WEIGHT            # 8000 (kg)
  load_ton = (trip.net_kg or 0)/1000.0 ...            # ton (0–25)
  total_mass = empty_weight + load_ton                # 8000 + 20 = 8020 (kg+ton karışık!)
  factor = trip.mesafe_km * total_mass
  ```
- Sorun: `empty_weight` kg (8000), `load_ton` ton (0–25). `total_mass = 8000 + 20 = 8020` birim
  uyumsuz; sabit 8000, yükü (5 vs 20 ton) tamamen gölgeliyor (8005 vs 8020 = %0.2 fark) → ton-km
  ağırlıklandırma pratikte **salt mesafe** dağıtımına dönüşüyor. Ağır yük seferi daha çok yakıt
  almıyor (amaçlanan tersine). Maliyet/tüketim per-sefer dağıtımı yanlış.
- Önerilen düzeltme: birimleri eşitle (`empty_ton = HGV_EMPTY_WEIGHT/1000` → `8 + 20 = 28`, yük anlamlı)
  veya yükü kg'a çevir.

> Not (low/medium): `_sync_create_fuel_periods:72` `sorted_records = fuel_records` — isim "sorted"
> ama **sıralama yok**; `groupby` arac_id sıralı girdi şart (recalc tek-arac olduğundan şimdilik güvenli,
> ama public `create_fuel_periods` çok-araç sırasız girdide parçalanır). `recalculate_vehicle_periods:299`
> `net_kg=int(s["net_kg"])` — NULL net_kg'de `int(None)` TypeError → tüm recalc çöker.
>
> `route_validator.py` (74 satır) genelde temiz. İz (low/nv): `validate_and_correct` dönen dict'e
> `is_corrected`/`correction_reason` ekliyor; `sefer_write._update_sefer_uow:1017` ve `create_return_trip:1473`
> bu dict'i doğrudan repo `update_sefer`/`add`'e `**` ile geçiyor → bu sunum-bayrakları seferler kolonu
> değilse repo'nun bilinmeyen-alan filtresine ([[AUDIT-004]]) bağlı; filtrelemezse hata. Ayrıca grade
> eşikleri (%0.7–2.5 ort.) Türkiye dağlık rotalarında (Bolu/Tahtalı) gerçek tırmanışı kırpabilir →
> fizik underestimate (nv — kalibrasyon).

### `ml_service.py` + `ai_service.py` (ML/AI orkestrasyon)

### AUDIT-063 — `AIService._predictor_cache` hiç invalidate edilmiyor (bayat tahmin) + `fit`/`predict` event loop'ta SENKRON (bloke)
- Şiddet: medium · Sınıf: performance / correctness · Durum: confirmed
- Konum: `app/core/services/ai_service.py:37,131-164,215`
- Kanıt:
  ```python
  if arac_id in self._predictor_cache: return self._predictor_cache[arac_id]   # 131 — kalıcı cache
  ...
  predictor.fit(history_data, y_actual)   # 157 — asyncio.to_thread YOK → event loop bloke
  ...
  res = predictor.predict(sefer_context)  # 215 — yine senkron
  ```
- Sorun: (1) AIService SINGLETON; `_predictor_cache[arac_id]` bir aracın predictor'ını **uygulama
  ömrü boyunca** tutar (ilk 200 seferle eğitilmiş haliyle) → sonradan eklenen seferler modeli
  güncellemez → tahminler bayatlar; ayrıca filo büyüklüğüyle bellek büyür (araç başına ensemble).
  (2) `predictor.fit` (ve `predict`) doğrudan **senkron** çağrılıyor — CLAUDE.md "tüm ML çağrıları
  `asyncio.to_thread` ile" kuralını ihlal ediyor → ilk tahmin isteğinde ensemble eğitimi event loop'u
  bloke eder (tüm istekler bekler).
- Önerilen düzeltme: cache'i TTL/event-invalidasyonlu yap; `fit`/`predict`'i `asyncio.to_thread`'e al
  (proje genelindeki ML deseni gibi).

### AUDIT-064 — `stream_response` `_sanitize_prompt`'u tümüyle baypas ediyor + redaksiyon listesi yetersiz
- Şiddet: medium · Sınıf: security · Durum: confirmed
- Konum: `app/core/services/ai_service.py:100-106` (sanitize YOK) vs `:88-95` (generate_response sanitize VAR);
  redaksiyon listesi `:30-34`
- Kanıt:
  ```python
  async def stream_response(self, user_input):
      async for token in self.groq.chat_stream(f"...Kullanıcı: {user_input}"):   # 104 — ham user_input
  ```
- Sorun: (1) `generate_response` `_sanitize_prompt` çağırırken (`:92`) `stream_response` ham `user_input`'u
  doğrudan LLM'e geçiriyor → (zayıf da olsa) injection guard streaming yolunda **hiç** uygulanmıyor.
  (2) Redaksiyon listesi yalnız `SYSTEM:`/`ADMIN_MODE`/`###` — "ignore previous instructions", unicode
  varyasyonları, satır araları vb. ile trivially baypas edilir; gerçek bir injection savunması değil
  (güvenlik tiyatrosu). Filo bağlamı prompt'a enjekte edildiğinden bağlam-sızdırma/manipülasyon riski.
- Önerilen düzeltme: her iki yolda da aynı sanitizasyonu uygula; injection için içerik-tabanlı politika
  + LLM system-prompt izolasyonu (delimiter + role separation) kullan, regex redaksiyona güvenme.

### AUDIT-065 — `MLService._locks` sınıf-düzeyi dict oluşturması racy + süreç-yerel + sınırsız büyüme
- Şiddet: medium · Sınıf: concurrency · Durum: confirmed
- Konum: `app/core/services/ml_service.py:21,32-35`
- Kanıt:
  ```python
  _locks: Dict[int, asyncio.Lock] = {}          # sınıf-düzeyi paylaşılan
  if arac_id not in self._locks:
      self._locks[arac_id] = asyncio.Lock()      # 33 — check-then-set TOCTOU
  async with self._locks[arac_id]:
  ```
- Sorun: İki eşzamanlı istek aynı **yeni** `arac_id` için `arac_id not in self._locks`'u aynı anda
  görüp **ayrı** Lock oluşturur (ikinci birinciyi ezer) → farklı lock'larda → karşılıklı dışlama yok.
  Gerçek guard DB `get_active_tasks_for_vehicle` ama o da unique-constraint/FOR UPDATE olmadan TOCTOU →
  aynı araç için **iki WAITING eğitim görevi** oluşabilir. Lock süreç-yerel (çok-worker'da etkisiz) ve
  `_locks` hiç temizlenmez (araç başına kalıcı lock → bellek sızıntısı).
- Önerilen düzeltme: aktif görev için DB unique partial index (`WHERE durum='WAITING'`) veya
  `INSERT ... ON CONFLICT`/advisory lock kullan; in-process lock'a güvenme.

> Not (low): `ai_service.detect_anomalies:225-265` **üçüncü** anomali tespit implementasyonu (basit z>2.0)
> — [[AUDIT-052]]'yi pekiştirir (toplam 3 ıraksak anomali yolu). `dist = kms[i]-kms[i+1]` newest-first
> sıralama varsayar; get_all sırası farklıysa dist<0 → sessizce hiç anomali. `_build_context:79`
> `motor_verimliligi` None ise `f"{None:.2f}"` TypeError riski (try yutuyor → tüm bağlam "alınamıyor").

### `weather_service.py` + `openroute_service.py` (dış API istemcileri)

### AUDIT-066 — `get_trip_impact_analysis` boş `daily` dizilerinde IndexError ile çöker
- Şiddet: medium · Sınıf: bug · Durum: confirmed
- Konum: `app/core/services/weather_service.py:237-248` (krş. güvenli desen `get_forecast_analysis:161-163`)
- Kanıt:
  ```python
  avg_temp = (start_daily.get("temperature_2m_max", [20])[0]
              + end_daily.get("temperature_2m_max", [20])[0]) / 2
  ```
- Sorun: `.get("key", [20])[0]` default'u yalnız anahtar **eksikse** uygulanır. API anahtarı
  döndürüp değeri **boş liste** verirse (`{"temperature_2m_max": []}`) → `[][0]` → **IndexError**
  (try yok) → `get_trip_impact_analysis` çöker. Üstteki `if "error" in start_weather` kontrolü
  başarılı-ama-boş yanıtı yakalamaz. `get_forecast_analysis` (`:161-163`) `index < len(...)` ile
  korunuyor — bu yol korunmuyor (asimetrik). Bu fonksiyon sefer create tahmin yolunda çağrılıyor
  (`sefer_write._predict_outbound:518`).
- Önerilen düzeltme: dizileri okumadan önce boşluk kontrolü yap (örn. `(arr or [default])[0]`), veya
  `get_forecast_analysis`'teki uzunluk-guard'ını kullan.

### AUDIT-067 — `OpenRouteService` offline fallback SENTETİK mesafe/yükseklik uyduruyor (gerçek/offline bayrağı YOK)
- Şiddet: medium · Sınıf: data-integrity / silent-fabrication · Durum: confirmed
- Konum: `app/core/services/openroute_service.py:82-107` (`get_route_profile_offline`); çağrı
  `get_route_profile:121,177,181,186,189` (her hata/timeout/circuit yolu buraya düşüyor)
- Kanıt:
  ```python
  distance_km = air_distance * 1.25
  ascent  = (distance_km / 100) * 450        # uydurma tırmanış
  descent = (distance_km / 100) * 400
  return RouteProfile(distance_km=..., ascent_m=..., elevation_gain_ratio=0.53)  # offline/is_real bayrağı YOK
  ```
- Sorun: API yapılandırılmamış/500/timeout/circuit-open olduğunda servis **sentetik** mesafe+yükseklik
  içeren normal bir `RouteProfile` döndürüyor; çağıran gerçek ORS profili ile uydurmayı ayırt edemez.
  Bu uydurma ascent (450m/100km) fizik yakıt tahminini besler → "gerçekmiş gibi" sentetik veriyle tahmin.
  Bu, projenin kendi kuralıyla **çelişir**: `weather_service` modül-başı kuralı "canlı veri yoksa bunu
  bildir, mevsimsel sentetik değerleri gerçekmiş gibi döndürme" diyor ve uymuyor. Aynı serviste tutarsızlık:
  `geocode` başarısızlıkta `None` (dürüst) ama `get_route_profile` uyduruyor.
- Önerilen düzeltme: `RouteProfile`'a `is_estimated/offline` bayrağı ekle ve çağıranlar bunu tahmin
  kalite/coverage metriğine yansıtsın (weather'daki dürüst-offline deseni gibi).

> Not (olumlu+low): `weather_service` genelde **örnek dürüstlük** — `get_forecast_analysis_offline`
> uydurmuyor, `offline=True`/`fuel_impact_factor=None` döndürüyor. İz (low): `weather._cache` singleton
> üzerinde sınırsız in-memory dict (3h TTL ama eviction yok → bellek sızıntısı). `openroute.geocode`
> rate-limiter + circuit-breaker'dan yoksun (`get_route_profile`'da var) → tutarsız dayanıklılık + kota riski.

---

## S2b-11 — Lokasyon + rota simülasyon kümesi (6 dosya)

Okunan: `lokasyon_service.py` (378), `lokasyon_hydrator.py` (191), `route_simulator.py` (184),
`segment_resampler.py` (183), `route_calibration_service.py` (157), `sefer_fuel_estimator.py` (528).
Temiz (0 bulgu): `lokasyon_hydrator.py`, `route_simulator.py`, `segment_resampler.py` — orkestrasyon
+ saf fonksiyonlar; grade/None fallback'leri tutarlı, idempotent re-hydrate doğru. Bulgular aşağıda.

### AUDIT-068 — `calibrate_route_from_trip` Lokasyon `rota_geom` güncellemesi sessiz no-op (dict mutasyonu kaybolur)
- Şiddet: medium
- Sınıf: silent-failure / data-integrity
- Konum: route_calibration_service.py:149-154
- Durum: confirmed
- Kanıt:
    ```python
    lokasyon = await self._get_lokasyon(guzergah_id)
    if lokasyon:
        if isinstance(lokasyon, dict):
            lokasyon["rota_geom"] = geom_wkb
        else:
            setattr(lokasyon, "rota_geom", geom_wkb)
    ```
  `self._get_lokasyon` → `uow.lokasyon_repo.get_by_id` → `BaseRepository._to_dict(obj)` **her zaman bir
  `dict` döndürür** (lokasyon_repo.py:51 `get_by_route` ve base `get_by_id` aynı `_to_dict`'i kullanır).
  Dolayısıyla `isinstance(lokasyon, dict)` dalı çalışır ve `geom_wkb` **tracked ORM nesnesine değil, tek
  kullanımlık bir dict'e** yazılır → commit'te (line 156) hiçbir UPDATE üretmez. `else: setattr(...)`
  dalı bu repo'dan **asla** erişilmez (ölü). Sonuç: golden-path kalibrasyonunda `GuzergahKalibrasyon.hedef_path`
  yazılır (doğru) ama `Lokasyon.rota_geom` **sessizce güncellenmez** → spatial tüketiciler bayat geometri görür.
- Önerilen düzeltme: lokasyon'u `uow.session.get(Lokasyon, guzergah_id)` ile **ORM nesnesi** olarak çek
  (dict değil) ve `rota_geom`'u öyle ata; veya lokasyon_repo'ya `update(... rota_geom=...)` çağrısı yap.
- Bağımlılık: lokasyon_repo.py:51 (`_to_dict`), AUDIT-004 (base repo dict dönüşü).

### AUDIT-069 — Estimator: `route_simulations.total_l` (düzeltilmiş) ile `route_segments.sim_l_total` (salt-fizik) ıraksıyor
- Şiddet: medium
- Sınıf: data-integrity / consistency
- Konum: sefer_fuel_estimator.py:233-246, 468, 495-496
- Durum: confirmed
- Kanıt:
    ```python
    physics_adjusted = physics_baseline * combine_factors(driver=..., vehicle_age=..., ...)
    breakdown.final = round(physics_adjusted, 2)
    ...
    total_l = round(breakdown.final * distance_km / 100.0, 2)     # ADJUSTED
    ...
    total_l=total_l,                  # route_simulations header (adjusted)
    ...
    sim_l_total=seg.sim_l_total,      # route_segments (physics-only, simulator çıktısı)
    ```
  Header `total_l` ve `avg_l_per_100km` weather+driver+age+seasonal `combine_factors` çarpanını içerir;
  ama per-segment `sim_l_total`/`sim_l_per_100km` doğrudan `simulate_route` (salt-fizik) çıktısından
  yazılır — adjustment factor **segmentlere hiç uygulanmaz**. Sonuç: `Σ route_segments.sim_l_total ≠
  route_simulations.total_l` (combine_factors çarpanı kadar fark). Segmentleri toplayıp doğrulama yapan
  bir tüketici (UI breakdown, rapor) header ile uyuşmayan toplam görür.
- Önerilen düzeltme: ya segment seviyesine de aynı çarpanı uygula (segment `sim_l_total *= factor`),
  ya da header `total_l`'i segment toplamından türet ve adjustment'ı ayrı bir alanda (`adjustment_factor`)
  sakla; en azından şema/doküman segmentlerin "salt-fizik, düzeltilmemiş" olduğunu açıkça belirtmeli.

### AUDIT-070 — Estimator: dış `AsyncSessionLocal` oturumu tüm dış-IO pipeline'ı boyunca açık/atıl tutuluyor
- Şiddet: medium
- Sınıf: performance / concurrency
- Konum: sefer_fuel_estimator.py:182-279
- Durum: confirmed
- Kanıt:
    ```python
    async with AsyncSessionLocal() as db:
        arac, sofor, dorse = await self._load_entities(db, inp)   # 184
        ...
        cikis_lon, ... = await self._resolve_route(db, inp)        # 190
        ...
        sim_result = await self._simulator.simulate(...)           # 200 — Mapbox + Open-Meteo (saniyeler)
        weather_samples = await self._fetch_weather_samples(...)   # 219 — Open-Meteo weather
        ...
        return SeferFuelEstimate(...)                              # 261
    ```
  `db` oturumu yalnız 184 ve 190'da (entity load + route resolve) kullanılır; 196'dan sonra **bir daha
  kullanılmaz** (persist kendi oturumunu açar, bkz. AUDIT-071). Buna rağmen havuzdan çekilmiş bağlantı,
  Mapbox + elevation + weather dış HTTP çağrıları (cold cache'de 2.5s+ — CLAUDE.md) boyunca açık/atıl
  tutulur. Yük altında pool tükenmesi riski: her eşzamanlı tahmin bir bağlantıyı dış-IO süresince rehin alır.
- Önerilen düzeltme: oturumu yalnız 1-2. adımları (entity+route) saracak şekilde daralt, koordinatları
  çıkarıp oturumu kapat; simülasyon/weather oturumsuz koşsun. (Persist zaten ayrı oturum açıyor.)

### AUDIT-071 — Estimator `_persist` bağımsız oturumda commit ediyor → çağıranın transaction'ından kopuk (orphan + atomik değil)
- Şiddet: medium
- Sınıf: transaction / data-integrity
- Konum: sefer_fuel_estimator.py:443-506
- Durum: confirmed
- Kanıt:
    ```python
    async def _persist(self, ...):
        row = RouteSimulation(...)
        ...
        async with AsyncSessionLocal() as db:
            db.add(row)
            await db.commit()
            await db.refresh(row)
        return int(row.id)
    ```
  `persist=True` (default) ile `_persist` **yeni bir bağımsız oturum açıp hemen commit** eder. Sefer create
  akışı estimator'ı çağırıp dönen `simulation_id`'yi `seferler.route_simulation_id`'ye yazsa bile, sefer
  transaction'ı sonradan rollback olursa `route_simulations`/`route_segments` satırları **zaten kalıcı** →
  hiçbir sefere bağlı olmayan **orphan simülasyon** satırları. Tahmin, çağıranın atomik birimine dahil
  edilemiyor.
- Önerilen düzeltme: `predict`'e opsiyonel `uow`/`session` geçir; persist çağıranın oturumunda flush edilip
  commit kararı çağırana bırakılsın (docstring `persist=False → commit caller'da` zaten bu niyeti ima ediyor
  ama `persist=True` yolu onu çiğniyor). Orphan'lara karşı periyodik temizlik veya sefer-FK zorunluluğu.

### AUDIT-072 — `match_sefer_to_path` hiç uygulanmamış stub; docstring "spatial buffer analizi" iddia ediyor
- Şiddet: low
- Sınıf: dead-code / incomplete-feature
- Konum: route_calibration_service.py:50-104
- Durum: confirmed
- Kanıt:
    ```python
    async def match_sefer_to_path(self, sefer_id: int) -> Dict[str, Any]:
        """Verify if a trip followed its assigned route using spatial buffer analysis."""
        ...
        return {
            "status": "verification_unavailable",
            ...
            "error_code": "SPATIAL_VERIFICATION_NOT_IMPLEMENTED",
            "reason": ("Spatial route verification is not available ..."),
        }
    ```
  Tüm context kontrolleri (sefer/rota_detay/guzergah_id/calibration/coordinates) yapıldıktan sonra metod
  **her durumda** `verification_available: False` + `SPATIAL_VERIFICATION_NOT_IMPLEMENTED` döner — yani
  hiçbir spatial buffer eşleştirmesi yok. Docstring yanıltıcı. (Not: `test_production_foundation_guards.py:506`
  `'"matches": True' not in` dosya guard'ı var → ekip bunun bilerek stub olduğunu biliyor; o yüzden low.)
- Önerilen düzeltme: ya PostGIS `ST_DWithin(hedef_path, trip_line, buffer_meters)` ile gerçek eşleştirmeyi
  uygula, ya da docstring'i "stub — not implemented" olarak düzelt ve endpoint'i feature-flag arkasına al.

### AUDIT-073 — `get_all_paged` validasyondan düşen satırları sessizce atlıyor ama `total` onları sayıyor (sayfa tutarsızlığı)
- Şiddet: low
- Sınıf: consistency / silent-failure
- Konum: lokasyon_service.py:280-290
- Durum: confirmed
- Kanıt:
    ```python
    total = await self.repo.count(filters=filters, include_inactive=not aktif_only)
    items = []
    for r in records:
        try:
            items.append(LokasyonResponse.model_validate(dict(r)))
        except Exception as e:
            logger.error(f"Lokasyon validasyon hatasi (ID {r.get('id')}): {e}")
            continue
    return {"items": items, "total": total}
    ```
  Bir kayıt şema validasyonundan geçemezse `items`'ten sessizce düşer ama `total` (ayrı `count`) onu hâlâ
  sayar → `len(items) < total` olabilir; frontend "100 kayıt var" der ama 99 gösterir, sonraki sayfa
  hesabı kayar. Ayrıca bozuk satırlar yalnız ERROR log'a düşer, çağırana sinyal yok.
- Önerilen düzeltme: validasyon hatasını ya yüzeye çıkar (kısmi sonuç + `skipped` sayacı), ya da `total`'ı
  gerçekten döndürülen item sayısıyla tutarlı hale getir.

### AUDIT-074 — `add_lokasyon` `.title()` Türkçe noktalı/noktasız i'yi bozuyor (saklanan görünen ad)
- Şiddet: low
- Sınıf: i18n / data-quality
- Konum: lokasyon_service.py:164-165
- Durum: confirmed
- Kanıt:
    ```python
    data.cikis_yeri = data.cikis_yeri.strip().title()
    data.varis_yeri = data.varis_yeri.strip().title()
    ```
  Python `str.title()` Türkçe-bilinçsiz: `"İSTANBUL".title()` → `"Istanbul"`, `"IĞDIR".title()` → `"Iğdir"`
  (doğrusu "Iğdır"/"İğdır"). Saklanan **görünen ad** bozuk büyük/küçük harf alır. Dedup `get_by_route`
  Türkçe i'yi nötrleştirdiği için (lokasyon_repo.py:42-43) tekilleştirme bozulmaz, ama kullanıcıya gösterilen
  şehir adı yanlış kaselenir.
- Önerilen düzeltme: Türkçe-bilinçli başlık-kasesi (locale-aware) kullan veya kullanıcı girdisini olduğu
  gibi sakla (yalnız trim), normalizasyonu sadece eşleştirme katmanında yap.

### AUDIT-075 — `UnitOfWork` aynı-instance yeniden girişi `_owns`'u False'a çevirir → sahip çıkışı oturumu/token'ı temizlemez (latent footgun)
- Şiddet: medium
- Sınıf: concurrency / resource-leak
- Konum: route_calibration_service.py:43,54,67 ↔ unit_of_work.py:124-137,179-183
- Durum: needs-verification (latent — mevcut endpoint'ler tetiklemiyor)
- Kanıt:
    ```python
    # route_calibration_service.py — match_sefer_to_path zaten `async with self.uow` içindeyken:
    async def get_calibration_for_lokasyon(self, lokasyon_id):
        async with self.uow:                      # AYNI instance'a ikinci giriş
            ...
    ```
    ```python
    # unit_of_work.py __aenter__
    if self._session is not None:
        self._owns = False        # ikinci giriş sahiplik bayrağını siler
    ...
    # __aexit__ finally
    if self._owns:                # artık False
        if self._token is not None: _session_ctx.reset(self._token)
        await self._session.close()
    ```
  Aynı UoW **instance**'ı iç içe `async with self.uow` ile tekrar girilince ikinci `__aenter__`,
  `_session is not None` olduğu için `_owns`'u **kalıcı olarak False** yapar. Eğer ilk giriş kendi
  oturumunu yaratmış (sahip, `_owns=True`, `_token` set) bir UoW idiyse, dış çıkış `_owns=False` görüp
  `_session_ctx.reset(token)` ve `session.close()`'u **atlar** → oturum sızıntısı + contextvar token sızıntısı.
  Mevcut endpoint'ler `UnitOfWork(db)` (dış oturum enjekte) kullandığından `_owns` baştan False ve sızıntı
  oluşmaz; ancak `RouteCalibrationService` bare `UnitOfWork()` ile kurulursa (ya da iç içe `async with self.uow`
  deseni kopyalanırsa) hata gerçekleşir. Desen kırılgan.
- Önerilen düzeltme: servis metodları `self.uow`'u **yeniden açmasın** — çağıran zaten açık UoW veriyor;
  `async with self.uow` sarmalarını kaldırıp doğrudan `self.uow.session`/repo kullan. Alternatif: UoW
  `__aenter__` aynı-instance reentrancy'yi sayaçla yönetsin (`_owns`'u ezmesin).
- Bağımlılık: AUDIT-011 (UoW commit/rollback `_owns` kontrolü).

> Notlar (low / iz):
> - `calibrate_route_from_trip` mevcut kalibrasyonu güncellerken `calibration.match_count = 1` (artırmıyor,
>   1'e **sıfırlıyor** — route_calibration_service.py:139). "Golden path tek seferden" niyetiyle kasıtlı
>   olabilir ama recalibrate'te birikmiş eşleşme sayısı kaybolur. (low / domain, needs-verification)
> - `segment_resampler.resample_segments` `len(cum) != len(coords)` olduğunda boundary koordinatlarını
>   **ham** döndürür (resample etmeden, line 85-86) → downstream `boundary_coords[i]` indeksleri resample'lı
>   segmentlerle hizasız kalır (mid_lon/lat + elevation yanlış noktadan). `i+1 < len(...)` guard'ları crash'i
>   önler ama sessiz veri-kalitesi kaybı. Mapbox extract normalde N+1 garanti ettiği için nadir. (low, needs-verification)
> - `_derive_arac_yasi` (sefer_fuel_estimator.py:360) `dt_date.today()` (naive/yerel) kullanıyor — tz sınırında
>   1 yıl sapma olası ama yaş hesabı için ihmal edilebilir. (low)
> - Olumlu: estimator weather hatasında `record_silent_fallback("open_meteo_weather_failed", ...)` ile
>   sessiz degrade'i **probe'a kaydediyor** (sefer_fuel_estimator.py:346) — AUDIT-038'in tersine **doğru** desen.
>   `route_simulator`/`segment_resampler` saf, test edilebilir, deterministik — temiz.

---

## S2b-12 — Bildirim + tercih kümesi (5 dosya)

Okunan: `notification_service.py` (156), `notification_prioritizer.py` (59), `push_sender.py` (229),
`quiet_hours.py` (60), `preference_service.py` (89). Bulgular AUDIT-076…080.
`notification_prioritizer.py` + `quiet_hours.py` saf mantık olarak temiz (yalnız aşağıdaki tz bulgusu).

### AUDIT-076 — `push_sender` kendi-UoW yolunda hiç commit etmiyor → ghost-transaction rollback → 410-temizliği + last_used_at kalıcı olmuyor
- Şiddet: high
- Sınıf: silent-failure / data-integrity / transaction
- Konum: push_sender.py:120-136 (`send_push_to_user`), 164-167 + 170-198 (`send_push_broadcast`/`_send_for_all`)
- Durum: confirmed
- Kanıt:
    ```python
    if owns_uow:
        async with ctx as uow_local:
            sent, expired, failed, expired_ids = await _send_for_user(uow_local, user_id, payload)
            if expired_ids:
                await uow_local.session.execute(
                    delete(PushSubscription).where(PushSubscription.id.in_(expired_ids))
                )
        # <-- async with çıkışı: commit YOK
    ```
  `_send_for_user`/`_send_for_all` içinde `last_used_at` UPDATE'i ve burada expired DELETE'i **bekleyen
  yazımlar** olarak kalır; `owns_uow` (uow=None) dalı `async with ctx` bloğundan **`await uow.commit()`
  olmadan** çıkar. UoW commit EXPLICIT'tir (unit_of_work.py:1-22, 150-171): pending yazımla commitsiz temiz
  çıkış → **GHOST TRANSACTION error log'u + rollback**. Sonuç: push'lar gönderilir (webpush dış yan etki)
  ama dosyanın başlık vaadi olan "410 Gone subscription'ları silinir" **sessizce gerçekleşmez** + her
  gönderimde ERROR log'u + `last_used_at` hiç güncellenmez. Ölü 410 abonelikler **sonsuza dek birikir** ve
  her broadcast'te tekrar başarısız olur.
  Üretimde erişilir (uow GEÇİLMİYOR): `insight_engine.py:169` `send_push_broadcast(...)` (kritik filo
  uyarısı), `compliance_tasks.py:29` `send_push_broadcast(...)` (muayene hatırlatma), `push.py:122`
  `send_push_to_user(...)` (admin test). Yalnız `notification_tasks.py:44` `uow=uow` geçtiği için sağlam.
- Önerilen düzeltme: `owns_uow` dallarında yazımlardan sonra `await uow_local.commit()` ekle (her iki
  fonksiyon). Alternatif: tek yol — daima `async with` + commit, non-owns yolu kaldır.
- Bağımlılık: unit_of_work.py:150-171 (ghost-transaction guard), AUDIT-011.

### AUDIT-077 — `is_user_quiet_now` UTC saatini kullanıcı-yerel "HH:MM" sessiz aralığıyla karşılaştırıyor (yanlış duvar-saati)
- Şiddet: medium
- Sınıf: domain-rule / timezone
- Konum: quiet_hours.py:59 ↔ 23-38
- Durum: needs-verification
- Kanıt:
    ```python
    current = (now or datetime.now(timezone.utc)).time()
    return is_within_quiet_hours(deger, current)
    ```
  `deger = {enabled, start 'HH:MM', end 'HH:MM'}` /preferences'tan gelir; Türk filo uygulamasında kullanıcı
  bunu **yerel duvar-saati** olarak girer ("22:00–07:00 rahatsız etme"). Ama karşılaştırma `datetime.now(
  timezone.utc).time()` ile yapılıyor → Türkiye UTC+3 olduğundan sessiz pencere **~3 saat kayar** (kullanıcının
  22:00'si UTC 19:00'da değerlendirilir). Sonuç: digest/push'lar sessiz saatte gönderilir veya tersi.
  Uygulamada tz alanı yok → saklanan değer yerel olmalı; bu yüzden mismatch olası.
- Önerilen düzeltme: karşılaştırmayı uygulama yerel tz'sine (veya kullanıcı tz'sine) çevir; ya da /preferences
  değerini açıkça UTC sakla ve UI'da yerel↔UTC dönüştür. Tek-tenant ise sabit `Europe/Istanbul` yeterli.

### AUDIT-078 — `NotificationService` EMAIL kanalı log-only stub ama `durum=SENT` → bildirim "gönderildi" işaretli, asla teslim edilmiyor
- Şiddet: medium
- Sınıf: silent-failure / incomplete-feature
- Konum: notification_service.py:62, 100-101
- Durum: confirmed
- Kanıt:
    ```python
    durum=BildirimDurumu.SENT,    # line 62 — teslimden ÖNCE optimist
    ...
    elif notif.kanal == "EMAIL":
        logger.info(f"Email task queued for user {notif.kullanici_id}")   # gerçek email YOK
    ```
  EMAIL kanallı bildirim DB'ye `durum=SENT` yazılır ama teslim adımı **yalnız bir log satırı** — hiçbir
  email kuyruğa atılmaz/gönderilmez. Kullanıcı/operatör DB'de "gönderildi" görür, e-posta hiç gelmez. UI
  kanalı gerçekten WS push yapar (line 84) ama yine teslim öncesi `SENT` damgası vurulur.
- Önerilen düzeltme: EMAIL için gerçek kuyruk (Celery task) bağla; teslim doğrulanana dek `durum=PENDING/
  QUEUED`, başarıda `SENT`, hata/stub'da `FAILED` yaz.

### AUDIT-079 — `save_preference` 'sutun' dışı tüm tercihlerde upsert yerine YENİ satır ekliyor → quiet_hours vb. duplikat birikimi
- Şiddet: medium
- Sınıf: data-integrity
- Konum: preference_service.py:35-64
- Durum: confirmed
- Kanıt:
    ```python
    existing = None
    if ayar_tipi == "sutun":
        settings = await uow.setting_repo.get_user_settings(user_id, modul, ayar_tipi)
        if settings:
            existing = settings[0]
    if existing:
        ... update ...
    # Create new preference
    pref = KullaniciAyari(...); uow.session.add(pref)
    ```
  Upsert yalnız `ayar_tipi == "sutun"` için yapılır. `quiet_hours` dahil diğer tüm ayar tipleri her
  kaydetmede **yeni KullaniciAyari satırı** ekler → kullanıcı sessiz saatini her güncellediğinde tablo
  duplikat satırla şişer. `get_user_settings` `created_at.desc()` sıraladığı için tüketici (`is_user_quiet_now`
  items[0]) en yeniyi okur (doğru), ama eski satırlar **temizlenmez** → sınırsız büyüme + /preferences
  listesinde mükerrer girişler.
- Önerilen düzeltme: quiet_hours gibi tekil-amaçlı ayar tiplerini de upsert kapsamına al (modul+ayar_tipi
  başına tek satır), veya kaydetmeden önce eski aynı-tip satırları sil.
- Bağımlılık: setting_repository.py:28-30 (`created_at.desc()` sırası).

### AUDIT-080 — `NotificationService.handle_event` commit'ten ÖNCE WS push + açık transaction içinde network I/O
- Şiddet: low
- Sınıf: transaction / concurrency
- Konum: notification_service.py:68-103
- Durum: confirmed
- Kanıt:
    ```python
    uow.session.add_all(notifications); await uow.session.flush()      # 68-69 (id'ler atanır)
    for notif in notifications:
        ...
        await notification_ws_manager.send_personal_message({... "id": notif.id ...}, user_email)  # 84
    ...
    await uow.commit()                                                 # 103
    ```
  WS teslimi (network I/O) `flush`'tan sonra ama `commit`'ten **önce** yapılır: (1) commit başarısız olursa
  kullanıcı rollback edilmiş bir bildirimin WS push'unu zaten almış olur; (2) DB transaction WS I/O süresince
  açık tutulur (kendi-UoW, bağlantı rehin). Çoklu kullanıcıda kısmi teslim + tam rollback olası.
- Önerilen düzeltme: önce commit et, sonra WS push yap (teslim DB gerçeğini takip etsin); veya WS push'u
  outbox/event ile transaction dışına al.

> Notlar (low / iz):
> - `_format_message` ANOMALY başlığında yazım hatası: "Anomali Tespit **Ediidi**" (notification_service.py:122).
>   Ayrıca `ANOMALY_DETECTED` formatı var ama `register_handlers` yalnız SEFER_UPDATED + SLA_DELAY subscribe
>   ediyor → anomali dalı bu serviste erişilmez (başka yerden tetiklenmiyorsa ölü). (low)
> - `notification_prioritizer.priority_for` iki ayrı COUNT sorgusu atıyor (total + read) — tek koşullu agregat
>   (FILTER/CASE) ile birleştirilebilir. (low, perf)
> - `PreferenceService.get_preferences` ORM nesnelerini `async with UnitOfWork()` kapandıktan SONRA döndürür
>   (detached); yüklü kolonlar (`deger`) okunur ama herhangi bir lazy relationship erişimi
>   DetachedInstanceError verir. (low, latent)
> - `handle_event` `user_email` araması her bildirim için tüm rules×users üzerinde iç içe comprehension
>   (line 72-81) → O(N²) bellek-içi; pratikte küçük ama gereksiz. (low)

---

## S2b-13 — Analitik/admin kümesi (6 dosya, plan alfabetik sırası)

Okunan: `admin_audit_service.py` (106), `analiz_service.py` (262), `attribution_service.py` (98),
`compliance_scanner.py` (133), `cross_feature_aggregator.py` (182), `dashboard_service.py` (105).
Temiz: `admin_audit_service.py` (AdminAuditLog modeli tüm kolonlara sahip — model uyumlu; bağımsız-UoW +
hata yutma audit için doğru desen), `compliance_scanner.py` (parametreli raw SQL, enjeksiyon yok).
Bulgular AUDIT-081…086.

### AUDIT-081 — `override_attribution` toplu çağrıda paylaşılan UoW'de `commit()` latch'i → yalnız İLK override kalıcı oluyor, geri kalanı rollback ama hepsi success
- Şiddet: high
- Sınıf: data-integrity / silent-failure / transaction
- Konum: attribution_service.py:32-80 (override_attribution), 82-98 (bulk_override) ↔ admin_attribution.py:76-104 ↔ unit_of_work.py:186-190
- Durum: confirmed
- Kanıt:
    ```python
    # attribution_service.override_attribution — her çağrıda:
    async with self.uow:
        ...
        success = await self.uow.sefer_repo.update(sefer_id, **updates)
        if success:
            await self.uow.commit()          # <-- paylaşılan uow
            await self.event_bus.publish_async(Event(type=SEFER_UPDATED, ...))
    ```
    ```python
    # unit_of_work.commit()
    async def commit(self):
        if self._session is None or self._committed:   # ilk commit'ten sonra _committed=True
            return                                      # → sonraki commit'ler NO-OP
        await self._session.commit(); self._committed = True
    ```
    ```python
    # admin_attribution.py bulk-override endpoint — TEK uow, döngüde tekrar tekrar:
    async with UnitOfWork(db) as uow:
        attribution_service = AttributionService(uow)
        for req in requests:
            success = await attribution_service.override_attribution(...)  # her tur commit() çağırır
    ```
  Bulk-override (admin_attribution.py:76) tüm döngüyü **tek `UnitOfWork(db)`** içinde sarar ve her turda
  `override_attribution` aynı uow'da `commit()` çağırır. İlk commit `_committed=True` set eder → **2..N
  turlarının `commit()`'i sessizce no-op**. Dış UoW external-session olduğu (get_db sahibi) ve commitsiz
  çıktığı için 2..N güncellemeleri istek sonunda **rollback** olur. Yine de her tur `success=True` döndürür
  ve `SEFER_UPDATED` event'i (physics/ML/cache recalc) yayınlar. Sonuç: toplu atfetme düzeltmesinde yalnız
  **ilk sefer** gerçekten güncellenir; kalanı geri alınır ama operatör "hepsi başarılı" görür + sahte recalc
  event'leri tetiklenir.
- Önerilen düzeltme: `override_attribution`'ı kendi commit'ini yapmaktan çıkar (flush et, commit kararını
  çağırana bırak); bulk yolunda tüm güncellemeleri tek transaction'da yapıp sonda bir kez commit et. Event'leri
  yalnız gerçekten commit edilen seferler için yayınla (outbox).
- Bağımlılık: AUDIT-075 (UoW aynı-instance re-entry), AUDIT-011.

### AUDIT-082 — `aggregate_cross_feature` koçluk tasarrufu sürücü sayısını yok sayıyor + yıllık km'yi period penceresiyle karıştırıyor
- Şiddet: medium
- Sınıf: domain-rule / financial
- Konum: cross_feature_aggregator.py:106-142
- Durum: confirmed
- Kanıt:
    ```python
    COUNT(*) FILTER (WHERE evaluated_at IS NOT NULL) AS evaluated,   # hesaplanıyor
    COALESCE(AVG(score_after_2w - score_before) FILTER (...), 0) AS avg_delta
    ...
    a5_delta = float(a5_row.get("avg_delta") or 0)
    if a5_delta > 0:
        coaching_savings_l = a5_delta * COACHING_KM_PER_DRIVER_AVG * COACHING_IMPACT_RATIO
    ```
  `coaching_savings_l = ortalama_delta × 50_000 (YILLIK km/şoför) × 0.30`. İki kusur: (1) `evaluated`
  (değerlendirilen şoför sayısı) SELECT'te hesaplanıp **kullanılmıyor** → tasarruf, koçlanan şoför sayısından
  bağımsız (tek "ortalama şoför" tasarrufu). (2) `COACHING_KM_PER_DRIVER_AVG=50_000` **yıllık** km ama sonuç
  `period_days` (default 90 gün) penceresi için sunuluyor → birim uyumsuzluğu. Çıktı `coaching_savings_tl`
  yönetici panelinde **filo geneli TL tasarruf** olarak gösteriliyor ama ne kişi-başı-period ne de filo-toplam;
  keyfi bir sayı. (confidence=0.55 düşük tutulsa da TL rakam yanıltıcı.)
- Önerilen düzeltme: `coaching_savings_l = avg_delta × evaluated × (KM × period_days/365) × ratio` gibi
  sürücü sayısı + period-orantılı km kullan; ya da formülü kişi-başı olarak etiketle.

### AUDIT-083 — `aggregate_cross_feature` D.4 döngüsü araç-başı `fetch_health_input` DB çağrısı → N+1
- Şiddet: medium
- Sınıf: performance
- Konum: cross_feature_aggregator.py:90-99
- Durum: confirmed
- Kanıt:
    ```python
    for r in arac_rows:
        h_inp = await fetch_health_input(uow, int(r["id"]))   # her araç için ayrı DB fetch
        h_res = compute_maintenance_factor(h_inp)
    ```
  Dış sorgu zaten araç-başı `period_l` topladı; sonra tüm aktif araçlar üzerinde döngüyle her biri için
  `fetch_health_input` (DB) çağrılıyor → N+1. Filo büyüdükçe panel yavaşlar.
- Önerilen düzeltme: health input'ları tek toplu sorguda çek (arac_id IN (...)) veya D.4'ü tek SQL agregatına
  indir.

### AUDIT-084 — `DashboardService` ölü/yetim (üretim çağıranı yok) + diriltirilirse latent çökme: session'sız singleton `get_all` RuntimeError + aynı repo'da eşzamanlı gather
- Şiddet: medium
- Sınıf: dead-code / concurrency
- Konum: dashboard_service.py:36-67
- Durum: confirmed (ölü) / needs-verification (latent buglar)
- Kanıt:
    ```python
    self.sefer_repo = get_sefer_repo()   # session'sız singleton
    ...
    tasks = (
        self.report_service.get_dashboard_summary(),
        ...
        self.sefer_repo.get_all(limit=recent_limit, filters={"is_deleted": False}),
        self.sefer_repo.count(filters={"is_deleted": False}),
        ...
    )
    ... await asyncio.gather(*tasks)
    ```
  `DashboardService`/`get_dashboard_service`/`get_dashboard_data` için app/ içinde (test hariç) **hiç üretim
  çağıranı yok** → ölü kod. Diriltirilirse iki latent bug: (1) `get_sefer_repo()` session'sız singleton; base
  `get_all` (base_repository.py:185 `session = self.session`) session'sızda `RuntimeError` fırlatır → gather
  patlar (`count` ise base_repository.py:401-403 exception'ı yutup sessizce **0** döner). (2) aynı singleton
  repo'da `get_all` + `count` `asyncio.gather` ile **eşzamanlı** çalışır → tek AsyncSession paylaşılıyorsa
  AsyncSession concurrency ihlali (AUDIT-044 sınıfı).
- Önerilen düzeltme: kullanılmıyorsa kaldır; kullanılacaksa UoW içine al (`async with UnitOfWork() as uow`)
  ve repo'ları `uow.sefer_repo` üzerinden, gather yerine ardışık/ayrı session ile çağır.
- Bağımlılık: base_repository.py:40-47 (session property), AUDIT-044.

### AUDIT-085 — `AnalizService` in-house istatistik metotları ölü (üretim çağıranı yok) + session'sız singleton repo çağrıları
- Şiddet: medium
- Sınıf: dead-code
- Konum: analiz_service.py:132-244 (get_fleet_average, calculate_long_term_stats, calculate_trend, calculate_moving_average)
- Durum: confirmed (ölü) / needs-verification (latent çökme)
- Kanıt:
    ```python
    async def get_fleet_average(self, year, month):
        repo = get_analiz_repo()                       # session'sız singleton
        val = await repo.get_filo_ortalama_tuketim()   # analiz_repo.py:28 `session = self.session` → raise
    ...
    async def calculate_long_term_stats(self, arac_id):
        alimlar = await self.yakit_repo.get_all(arac_id=arac_id, limit=1000, desc=False)  # session'sız singleton
    ```
  `get_fleet_average` / `calculate_long_term_stats` / `calculate_trend` / `calculate_moving_average` için
  app/ içinde (test hariç) üretim çağıranı bulunamadı → ölü. Ayrıca ilk ikisi session'sız singleton repo
  (`get_analiz_repo()` / `get_yakit_repo()`) çağırıyor; `get_filo_ortalama_tuketim` `self.session` kullanır
  (analiz_repo.py:28) → diriltirilirse "Database session not initialized" ile çöker. Facade'in DELEGE eden
  metotları (period/anomaly) ayrı; bu in-house blok terk edilmiş.
- Önerilen düzeltme: ölü metotları kaldır ya da UoW içine taşı; facade'i yalnız gerçekten kullanılan
  delegasyonlarla sınırla.

### AUDIT-086 — `cross_feature_aggregator` confidence + birim yorumları bayat/çelişik
- Şiddet: low
- Sınıf: consistency / doc
- Konum: cross_feature_aggregator.py:21, 57, 181
- Durum: confirmed
- Kanıt:
    ```python
    # line 21: "Mevcut response.confidence=0.40 düşük tutuluyor çünkü kalibrasyon yok."
    # line 57: "her araç için ... yıllık L = ekstra L"   (ama period_l = period_days penceresi kullanılıyor)
    # line 181: confidence=0.55,
    ```
  Modül-başı yorum confidence=0.40 diyor, kod 0.55 döndürüyor (docstring de 0.55). D.4 yorumu "yıllık L"
  diyor ama kod `period_l` (period_days penceresi) kullanıyor. Yorumlar koddan sapmış → bakım/anlaşılırlık riski.
- Önerilen düzeltme: yorumları kodla eşitle (0.55, period-bazlı).

> Notlar (low / iz):
> - `compliance_scanner.scan_compliance` + birçok yer `date.today()` (naive/yerel) kullanıyor; muayene gün
>   farkı için ihmal edilebilir ama tz sınırında 1 gün oynayabilir. (low)
> - `admin_audit_service.log_action` `request.client.host`'u IP olarak yazıyor (admin_audit_service.py:56) —
>   reverse-proxy arkasında proxy IP'si kaydedilir (X-Forwarded-For okunmuyor); audit IP'si yanıltıcı olabilir.
>   (low; AUDIT-006 ile aynı sınıf)
> - `attribution_service.bulk_override` (servis-içi, line 82) endpoint'ten kullanılmıyor (endpoint kendi
>   döngüsünü yazıyor) ama aynı `_committed` latch hatasına sahip — AUDIT-081 kapsamında. (low)

---

## S2b-14 — Export/rapor + sağlık kümesi (6 dosya, plan alfabetik sırası)

Okunan: `excel_exporter.py` (619), `executive_pdf_generator.py` (343), `export_service.py` (326),
`fleet_comparison.py` (137), `health_service.py` (226), `ics_generator.py` (121).
Temiz: `ics_generator.py` (RFC 5545 doğru — UTF-8 güvenli fold + escape sırası doğru),
`executive_pdf_generator.py` (sadece sayısal/kontrollü veri PDF'e gidiyor; iz: her çağrıda
`PDFReportGenerator()` font yeniden kaydı — low perf). Bulgular AUDIT-087…092.

### AUDIT-087 — Excel export'unda formül/CSV enjeksiyonu: kullanıcı string'leri `= + - @` ile başlarsa formül olarak yazılıyor
- Şiddet: medium
- Sınıf: security
- Konum: excel_exporter.py:317 (`worksheet.write`), export_service.py:118,123 (`ws.cell(value=...)`)
- Durum: confirmed
- Kanıt:
    ```python
    # excel_exporter.py — xlsxwriter write() leading '=' → write_formula
    worksheet.write(row_num + 2, col_num, cell_value, fmt)
    ```
    ```python
    # export_service.py — openpyxl cell.value, leading '=' → formula
    ws.cell(row=row, column=col, value=str(item.get(k, "-")))
    ```
  Her iki export motoru da DB'den gelen **kullanıcı-kontrollü string'leri** (sefer `notlar`, yakıt
  `istasyon`/`fis_no`, `plaka`, şoför adı) hücreye yazıyor. xlsxwriter `write()` ve openpyxl `cell.value`,
  `=`/`+`/`-`/`@` ile başlayan string'i **formül** olarak değerlendirir. Bir `notlar = "=HYPERLINK(\"http://evil\",\"tıkla\")"` ya da DDE `=cmd|'/c calc'!A1`, operatör export'u Excel'de açtığında
  formül/CSV-injection olarak çalışabilir (OWASP CSV Injection). İçeri-aktarma veya form bu alanlara veri
  sokabildiği için yüzey gerçek.
- Önerilen düzeltme: hücreye yazmadan önce string `= + - @ \t \r` ile başlıyorsa başına tek tırnak (`'`)
  veya boşluk ekle (neutralize); ya da xlsxwriter'da `write_string()`, openpyxl'de `cell.data_type='s'`
  zorla. Tek bir `_excel_safe(str)` yardımcısıyla her iki motorda uygula.

### AUDIT-088 — `ExportService` üretilen dosyaları sunucu-yerel dizine yazıp biriktiriyor (temizlik yok + çok-instance kırılgan)
- Şiddet: low
- Sınıf: resource-leak / arch
- Konum: export_service.py:41-49, 129-132, 157-165, 312-314
- Durum: confirmed
- Kanıt:
    ```python
    EXPORT_DIR = _get_export_dir()    # %APPDATA%/LojiNext/exports veya ~/.lojinext/exports
    ...
    filepath = self.EXPORT_DIR / filename
    wb.save(filepath); return str(filepath)
    ```
  Her export sunucu-yerel diske kalıcı dosya yazar ve **hiç silinmez** → zamanla disk dolar. Ayrıca
  dönen `filepath` yerel-disk yolu; çok-instance/konteyner dağıtımda dosyayı başka instance servis edemez
  (single-tenant olduğu için düşük ama mimari iz). `_sanitize_filename` path-traversal'ı doğru engelliyor.
- Önerilen düzeltme: geçici dosya + indirildikten sonra sil (veya bytes'ı doğrudan stream et, diske yazma);
  ya da periyodik TTL temizliği.

### AUDIT-089 — `fleet_comparison` "açık anomali" metriği aslında TÜM anomalileri sayıyor (status filtresi yok)
- Şiddet: low
- Sınıf: domain-rule / consistency
- Konum: fleet_comparison.py:87-91 ↔ docstring:6
- Durum: confirmed
- Kanıt:
    ```python
    (SELECT COUNT(*) FROM anomalies
       WHERE tarih BETWEEN :start AND :end
         AND severity IN ('critical', 'high', 'medium')) AS anomaly_count
    ```
  Modül docstring'i "Açık anomali sayısı (severity > low)" diyor ama SQL `status` (open/acknowledged/
  resolved — migration 0012) filtrelemiyor → **çözülmüş anomaliler de** sayıma giriyor. Period-over-period
  karşılaştırmada "açık anomali" trendi gerçeği yansıtmaz.
- Önerilen düzeltme: `AND status IN ('open','acknowledged')` (veya `resolved_at IS NULL`) ekle, ya da
  docstring'i "tüm anomali" olarak düzelt.

### AUDIT-090 — `HealthService.check_redis` async metotta SENKRON redis ping → event loop'u bloklar
- Şiddet: medium
- Sınıf: concurrency
- Konum: health_service.py:56-72
- Durum: confirmed
- Kanıt:
    ```python
    import redis as redis_lib
    client = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=2)
    client.ping()        # SENKRON, to_thread YOK
    client.close()
    ```
  `check_db` async engine kullanırken `check_redis` **senkron** `redis` istemcisi ile `ping()` yapıyor —
  `asyncio.to_thread` yok. Redis yavaş/erişilemezse `socket_connect_timeout=2`'ye kadar **tüm event loop
  bloke** olur. `get_full_status` bunu `asyncio.gather` ile çağırsa da senkron ping gather'ın faydasını
  yok eder + diğer coroutine'leri durdurur.
- Önerilen düzeltme: `redis.asyncio` istemcisi kullan ya da `await asyncio.to_thread(_sync_ping)`.

### AUDIT-091 — `trigger_manual_backup` uydurma `task_id` döndürüyor (gerçek task'a bağlı değil) + referanssız `create_task`
- Şiddet: medium
- Sınıf: bug / observability
- Konum: health_service.py:170-178
- Durum: confirmed
- Kanıt:
    ```python
    task_id = f"backup_{uuid4().hex}"
    manager = self._get_backup_manager()
    asyncio.create_task(asyncio.to_thread(manager.create_backup))
    return {"message": "Yedekleme islemi baslatildi.", "task_id": task_id}
    ```
  Dönen `task_id` rastgele üretiliyor ve başlatılan göreve **bağlı değil** — hiçbir registry yok, çağıran
  bu id ile durum sorgulayamaz (sahte sözleşme). Ayrıca `asyncio.create_task(...)` sonucu **referans
  tutulmuyor**; CPython task'ı tamamlanmadan GC edebilir ("never retain a reference" uyarısı). Backup
  başarısızlığı da yutulur (kimse await etmiyor).
- Önerilen düzeltme: `BackgroundJobManager.submit(...)` kullanıp gerçek task_id döndür ve `GET .../tasks/{id}`
  ile durum sorgulanabilsin; task referansını sakla.
- Bağımlılık: job_manager (async job pattern, CLAUDE.md).

### AUDIT-092 — `check_ai_readiness` sabit `models: [LightGBM, LSTM, RAG]` listesi döndürüyor (gerçek yük durumu değil)
- Şiddet: low
- Sınıf: observability / misleading
- Konum: health_service.py:82-86
- Durum: confirmed
- Kanıt:
    ```python
    return {
        "status": "healthy" if rag_stats.get("initialized") else "degraded",
        "rag_engine": rag_stats,
        "models": ["LightGBM", "LSTM", "RAG"],   # sabit liste
    }
    ```
  `models` her zaman aynı statik liste; gerçek model yük/eğitim durumunu yansıtmıyor. Sağlık paneli
  yüklü olmayan modelleri "var" gibi gösterebilir. (Ayrıca proje LSTM yerine ensemble/ARIMA kullanıyor —
  CLAUDE.md; liste yanıltıcı.)
- Önerilen düzeltme: gerçek model registry/manager'dan yüklü model adlarını + durumunu üret.

> Notlar (low / iz):
> - `excel_exporter._export_data_sync` `pd.ExcelWriter`'ı try/finally olmadan kullanıyor (line 182→339);
>   ara exception'da `writer.close()` çağrılmaz (BytesIO sızıntısı, küçük). Rapor başlığı
>   `datetime.now(timezone.utc)` ama yerel-görünümlü formatlanıyor (UTC saat, TR kullanıcı yerel sanır). (low)
> - `executive_pdf_generator.generate_executive_pdf` her çağrıda `PDFReportGenerator()` kurup font yeniden
>   kaydı yapıyor (line 85) — idempotent ama gereksiz iş. (low)
> - `health_service.get_backup_status` async metotta senkron FS glob/stat (low, yerel FS hızlı).
> - `fleet_comparison` cross-feature `coaching_savings` ile aynı sınıf değil ama `date.today()` yerel tz. (low)

---

## S2b-15 — Insight/lisans/konfig/bakım/backfill kümesi (6 dosya, plan alfabetik sırası)

Okunan: `insight_engine.py` (190), `internal_service.py` (154), `konfig_service.py` (132),
`license_service.py` (125), `maintenance_service.py` (129), `prediction_backfill_service.py` (116).
Doğrulanıp elenen: `expire_on_commit=False` (connection.py:79) → commit sonrası ORM dönüşü güvenli
(maintenance/preference detached-erişim endişesi düştü). Bulgular AUDIT-093…098.

### AUDIT-093 — `get_upcoming_alerts` tz-aware kolonu naive `datetime.now()` ile karşılaştırıyor → TypeError (canlı endpoint çöker)
- Şiddet: high
- Sınıf: bug / crash
- Konum: maintenance_service.py:124-126 ↔ models.py (AracBakim.bakim_tarihi DateTime(timezone=True)) ↔ admin_maintenance.py:89
- Durum: confirmed
- Kanıt:
    ```python
    "vade_durumu": "OVERDUE"
    if b.bakim_tarihi < datetime.now()    # naive
    else "UPCOMING",
    ```
  `AracBakim.bakim_tarihi` `DateTime(timezone=True)` (models.py) → asyncpg **tz-aware** datetime döndürür.
  `datetime.now()` **naive**. Python aware vs naive karşılaştırması `TypeError: can't compare offset-naive
  and offset-aware datetimes` fırlatır. Endpoint `admin_maintenance.py:89` `await service.get_upcoming_alerts()`
  çağırıyor → `get_upcoming_maintenance` en az bir satır döndürdüğünde endpoint **500** verir. Yaklaşan/geciken
  bakımı olan her gerçek veride garanti çökme.
- Önerilen düzeltme: `datetime.now(timezone.utc)` kullan (tz-aware) — `b.bakim_tarihi < datetime.now(timezone.utc)`.

### AUDIT-094 — `insight_engine` session'sız singleton `get_analiz_repo()` kullanıyor → fleet insight sessiz ölü + save UNCAUGHT çöker
- Şiddet: high
- Sınıf: silent-failure / bug
- Konum: insight_engine.py:36-39, 129-130 ↔ analiz_repo.py:26,14 (`session = self.session`)
- Durum: confirmed
- Kanıt:
    ```python
    # generate_fleet_insights — try/except içinde:
    repo = analiz_repo_mod.get_analiz_repo()        # session'sız singleton
    stats = await _safe_await(repo.get_dashboard_stats())   # analiz_repo.py:26 self.session → RuntimeError
    # → except (line 40) yutar → her zaman [] döner (fleet insight ASLA üretilmez)
    ...
    # generate_all_and_save — try/except DIŞINDA:
    repo = analiz_repo_mod.get_analiz_repo()        # session'sız singleton
    saved = int(await _safe_await(repo.bulk_create_alerts(payload)))  # bulk_create_alerts:14 self.session → RuntimeError (yutulmaz)
    ```
  `get_analiz_repo()` argümansız → **session'sız singleton**; `get_dashboard_stats` (analiz_repo.py:26) ve
  `bulk_create_alerts` (analiz_repo.py:14) `self.session` kullanır → session'sızda `RuntimeError("Database
  session not initialized")`. İki sonuç: (1) `generate_fleet_insights` hatayı yutup **her zaman []** döner →
  filo-düzeyi insight özelliği sessizce ölü. (2) `generate_all_and_save` insight varsa (vehicle/driver yolu
  `get_uow()` ile çalışır → insight üretebilir) `bulk_create_alerts`'i session'sız singleton'da **try/except
  DIŞINDA** çağırır → kaydetme yolu **çöker** (insight kaydedilmez + serious push tetiklenmez).
- Önerilen düzeltme: her iki yerde de `async with get_uow() as uow: uow.analiz_repo...` kullan (vehicle/driver
  yolundaki gibi); session'sız singleton'da raw-SQL repo metodu çağırma.
- Bağımlılık: CLAUDE.md "Singleton repos need UoW for raw-SQL", AUDIT-084/085 (aynı sınıf).

### AUDIT-095 — `LicenseEngine` limit kontrolleri soft-delete'li satırları sayıyor + hiç çağrılmıyor (wire'lanmamış)
- Şiddet: medium
- Sınıf: domain-rule / dead-code
- Konum: license_service.py:88-119
- Durum: confirmed
- Kanıt:
    ```python
    count = await uow.session.scalar(select(func.count(Arac.id)))           # is_deleted/aktif filtresi YOK
    ...
    count = await uow.session.scalar(select(func.count(Sefer.id)).where(Sefer.tarih >= first_day))  # is_deleted YOK
    ```
  `check_car_limit`/`check_monthly_trip_limit` `Arac`/`Sefer` sayarken `is_deleted`/`aktif` filtrelemiyor →
  **soft-delete'li araç/sefer de limite sayılır** (silinen aracın yerine yeni eklenemez). Ayrıca bu iki
  enforcement metodu app/ içinde (test hariç) **hiç çağrılmıyor** → lisans limitleri pratikte uygulanmıyor
  (engine container'da kurulu ama limit kapısı bağlı değil). Yani hem latent domain hatası hem ölü kapı.
- Önerilen düzeltme: sayımlara `is_deleted == False` (+ Arac için `aktif`) ekle; limit kontrolünü gerçekten
  create yollarına bağla ya da kullanılmıyorsa kaldır. (Tek-tenant; CLAUDE.md.)

### AUDIT-096 — `PredictionBackfillService.backfill` tek UoW/bağlantıyı tüm batch boyunca (dış-IO + sleep) açık tutuyor
- Şiddet: medium
- Sınıf: performance / concurrency
- Konum: prediction_backfill_service.py:63-102
- Durum: confirmed
- Kanıt:
    ```python
    async with self._get_uow() as uow:
        ids = ... # ≤ limit(50)
        for sid in ids:
            ...
            estimate = await estimator.predict(inp, persist=True)   # Mapbox+Open-Meteo, saniyeler
            await uow.sefer_repo.update(sid, ...)
            if self._throttle_s:
                await asyncio.sleep(self._throttle_s)               # 0.5s/iter
        await uow.commit()
    ```
  Tek UoW (havuz bağlantısı) ≤50 iterasyon × (estimator'ın çok-saniyelik Mapbox+Open-Meteo çağrıları +
  0.5s throttle) boyunca **açık/atıl** tutulur → bağlantı dakikalarca rehin. Estimator ayrıca kendi
  oturumlarını açtığı için (AUDIT-070/071) eşzamanlı bağlantı baskısı artar. Gece job'ı olsa da havuz baskısı
  + uzun-yaşayan transaction.
- Önerilen düzeltme: koordinatları/sefer verisini kısa oturumda topla, estimator + sleep oturumsuz koşsun,
  update'leri ayrı kısa oturum(lar)da (veya küçük gruplar halinde commit) yap.
- Bağımlılık: AUDIT-070, AUDIT-071.

### AUDIT-097 — `internal_service` upload validasyon sabitleri ölü/duplike + senkron dosya yazımı + commit hatasında orphan dosya
- Şiddet: low
- Sınıf: dead-code / robustness
- Konum: internal_service.py:24-25, 56-61
- Durum: confirmed
- Kanıt:
    ```python
    _ALLOWED_BELGE_TIPLERI = frozenset({"yakit_fisi", "sefer_fisi", "tir_ekran"})  # serviste KULLANILMIYOR
    _MAX_UPLOAD_BYTES = 10 * 1024 * 1024                                            # serviste KULLANILMIYOR
    ...
    with open(filepath, "wb") as f_out:      # senkron yazım, to_thread yok
        f_out.write(image_bytes)
    async with UnitOfWork() as uow: ...       # dosya zaten yazıldı; DB commit başarısızsa orphan dosya
    ```
  Sabitler serviste tanımlı ama enforce edilmiyor; gerçek doğrulama **endpoint'te** (`internal.py:118,130`)
  yapılıyor (orada `_ALLOWED_BELGE_TIPLERI`/`_MAX_UPLOAD_BYTES` kopyaları kullanılıyor) → servisteki kopyalar
  ölü/duplike. Ayrıca `kaydet_belge` dosyayı **senkron** yazıyor (event loop bloklar) ve DB kaydından ÖNCE
  yazdığı için commit hatasında diskte **orphan dosya** kalır.
- Önerilen düzeltme: ölü sabitleri kaldır (tek kaynak endpoint veya servis); dosya yazımını `asyncio.to_thread`'e
  al; DB kaydı başarısızsa dosyayı sil (veya önce DB flush, sonra yaz).

### AUDIT-098 — `KonfigService.update_config` DB yazımı repo self-commit'e bağlıyken cache invalide + event publish ediyor (yazım sessizce başarısızsa stale)
- Şiddet: low
- Sınıf: consistency
- Konum: konfig_service.py:98-117
- Durum: needs-verification
- Kanıt:
    ```python
    updated_config = await self.repo.update_value(key=key, new_value=value, ...)  # commit repo'ya bırakılmış
    ...
    cache.delete(f"config:val:{key}"); cache.delete(...); cache.delete("configs:all")
    pubsub.publish("config_updates", {...})
    ```
  `update_config` kendi UoW/commit'ini açmıyor; kalıcılık `admin_config_repo.update_value`'a bağlı (AUDIT-018:
  flush-öncesi refresh riski). Yazım sessizce başarısız olsa bile cache **silinir** + `config_updates` event'i
  **yayınlanır** → dağıtık worker'lar DB'den ESKİ değeri yeniden yükler (cache miss → stale read) ve config
  değişmiş sanır. Yazım+cache+event aynı transaction'da değil.
- Önerilen düzeltme: update_config'i açık UoW içinde yap, commit sonrası cache invalide + publish; ya da
  update_value'nun commit garantisini netleştir (AUDIT-018 ile birlikte düzelt).
- Bağımlılık: AUDIT-018.

> Notlar (low / iz):
> - `insight_engine.generate_all_and_save` serious push'u `send_push_broadcast` ile gönderiyor (line 169) →
>   AUDIT-076 ghost-rollback bug'ına maruz (410-temizliği çalışmaz). (AUDIT-076 kapsamında)
> - `maintenance_service._invalidate_predictions_cache` `redis.asyncio` + SCAN ile **doğru** async desen
>   (health_service.check_redis'in tersine) — olumlu. `get_upcoming_alerts` batch-fetch (get_by_ids) N+1 önler.
> - `license_service._LICENSE_HASHES` sınıf-düzeyi mutable dict, `__init__`'te mutasyon (singleton olduğu için
>   pratikte sorunsuz). (low)
> - `konfig_service.get_value` config değeri legitimately None ise hiç cache'lenmez (her çağrı DB) — küçük. (low)

---

## S2b-16 — Rapor/PDF/triage/what-if kümesi (6 dosya) — core/services TAMAM

Okunan: `report_service.py` (356), `report_generator.py` (494), `sofor_pdf_service.py` (152),
`triage_aggregator.py` (321), `what_if_engine.py` (303), `__init__.py` (15).
Temiz: `__init__.py` (yalnız AnalizService re-export), `triage_aggregator.py` (parametreli SQL, kaynak-başı
try/except dayanıklı, tz-aware timestamp'ler tutarlı). Bulgular AUDIT-099…104. **Bu küme ile core/services
61/61 (S2b) tamamlandı.**

### AUDIT-099 — `ReportService` paylaşılan oturumda `asyncio.gather` → AsyncSession eşzamanlı operasyon hatası (canlı endpoint çöker)
- Şiddet: high
- Sınıf: concurrency / bug
- Konum: report_service.py:196-198 (generate_monthly_trend), 240-242 (generate_vehicle_report) ↔ advanced_reports.py:126-127
- Durum: confirmed
- Kanıt:
    ```python
    # ReportService.__init__(session=session) → TÜM repolar aynı session'ı paylaşır:
    self.arac_repo = AracRepository(session=session); ...; self._analiz_repo = get_analiz_repo(session=session)
    ...
    # generate_monthly_trend:
    bu_ay_task = self.analiz_repo.get_period_stats(bu_ay_bas, bu_ay_son)
    gecen_ay_task = self.analiz_repo.get_period_stats(gecen_ay_bas, gecen_ay_son)
    bu_ay_data, gecen_ay_data = await asyncio.gather(bu_ay_task, gecen_ay_task)   # AYNI session, eşzamanlı
    # generate_vehicle_report:
    stats, gunluk, guzergahlar = await asyncio.gather(stats_task, gunluk_task, guzergahlar_task)  # AYNI session
    ```
  Endpoint'ler `ReportService(session=db)` ile kurar (advanced_reports.py:83,126,354; reports.py:67) →
  arac/sofor/sefer/yakit/analiz repo'ları **tek `db` session'ını paylaşır**. `asyncio.gather` ile aynı
  `analiz_repo` (aynı AsyncSession) üzerinde iki/üç sorgu **eşzamanlı** koşturulur. SQLAlchemy AsyncSession
  tek-operasyon kuralı gereği `InvalidRequestError: ... concurrent operations are not permitted` fırlatır.
  `generate_vehicle_report` `advanced_reports.py:127`'den erişilir → endpoint **çöker**.
- Önerilen düzeltme: gather'ları **ardışık await**'e çevir (aynı session'da paralel sorgu yapma); ya da her
  paralel dal için ayrı session/UoW kullan.
- Bağımlılık: AUDIT-044 (aynı sınıf — sofor_analiz; o needs-verification idi, bu construction kanıtlı).

### AUDIT-100 — `generate_fleet_summary` tutarsız savunmacı RuntimeError yakalama (analiz korumasız, yakit korumalı)
- Şiddet: low
- Sınıf: consistency
- Konum: report_service.py:281, 283-291
- Durum: confirmed
- Kanıt:
    ```python
    stats = await self.analiz_repo.get_fleet_performance_stats(start_date)   # 281 — try YOK
    get_stats = getattr(self.yakit_repo, "get_stats", None)
    if callable(get_stats):
        try:
            yakit_stats = await get_stats(...)
        except RuntimeError:        # yalnız yakit korunuyor (session'sız "not initialized" yakalanıyor)
            yakit_stats = {}
    ```
  `yakit_repo.get_stats` çağrısı session'sız `RuntimeError`'a karşı korunmuş ama `analiz_repo.get_fleet_
  performance_stats` (281) korumasız. Session-bound yolda (endpoint session veriyor) ikisi de çalışır →
  yakit'teki try ölü/savunmacı; ama desen tutarsız ve session'sız bir çağıran gelirse analiz çöker.
- Önerilen düzeltme: ya iki çağrıyı da aynı şekilde ele al, ya da session zorunluluğunu netleştir (session
  yoksa erken hata).

### AUDIT-101 — `PDFReportGenerator.generate_vehicle_report` yarım/stub (yalnız teknik kart)
- Şiddet: low
- Sınıf: dead-code / incomplete
- Konum: report_generator.py:365-401
- Durum: confirmed
- Kanıt:
    ```python
    elements.append(t_table)
    # ... Diğer bölümler benzer elite tasarım ile eklenebilir ...
    doc.build(elements)
    ```
  Araç raporu PDF'i yalnız "TEKNİK ÖZELLİKLER" kartını içeriyor; tüketim/trend/güzergah bölümleri yok
  (yorum "eklenebilir" diyor). `report_service.generate_vehicle_report` zengin veri (gunluk_trend,
  top_guzergahlar) topluyor ama PDF'e yansımıyor → emek boşa + eksik çıktı.
- Önerilen düzeltme: kalan bölümleri ekle ya da raporu "özet" olarak etiketle.

### AUDIT-102 — `sofor_pdf_service` `ad_soyad`'ı reportlab Paragraph markup'ına escape'siz koyuyor
- Şiddet: low
- Sınıf: security / robustness
- Konum: sofor_pdf_service.py:95
- Durum: confirmed
- Kanıt:
    ```python
    Paragraph(f"Sefer Raporu — {sofor.ad_soyad}", self.styles["EliteTitle"])
    ```
  `sofor.ad_soyad` (kullanıcı girdisi) reportlab Paragraph'a **markup olarak** gidiyor; isimde `<`, `&`
  ya da `<b>` gibi içerik olursa Paragraph parse'ı bozulur/render hatası (mini markup injection). Tablo
  hücreleri (rows) düz string olduğu için güvenli — yalnız başlık Paragraph'ı korumasız.
- Önerilen düzeltme: `xml.sax.saxutils.escape(sofor.ad_soyad)` ile escape et (reportlab markup'ında).

### AUDIT-103 — `simulate_fleet_renewal` CO2 azaltımı yanlış metrik (Euro faktör farkı × aynı tüketim)
- Şiddet: low
- Sınıf: domain-rule
- Konum: what_if_engine.py:102-106
- Durum: confirmed
- Kanıt:
    ```python
    for r in eligible:
        old_factor = euro_class_for_year(r["yil"]).co2_factor_kg_per_l
        new_factor = 2.63  # Euro VI
        co2_reduction += float(r["yearly_consum_l"] or 0) * (old_factor - new_factor)
    ```
  CO2/L yakıtın karbon içeriğiyle belirlenir (~2.6 kg/L) ve Euro sınıfıyla **kayda değer değişmez** (Euro
  sınıfı NOx/PM'i etkiler). Gerçek CO2 azaltımı **daha az yakıt yakmaktan** gelir (yearly_savings_l ×
  CO2_factor), faktör farkından değil. Mevcut formül yanıltıcı/yanlış bir CO2 rakamı üretir (faktör farkı
  ~0 ise ≈0, ya da negatif olabilir). Yönetici raporuna giden sayı.
- Önerilen düzeltme: `co2_reduction = yearly_savings_l × ~2.63` (tüketim azalmasından) kullan.

### AUDIT-104 — `triage_aggregator` aktif sefer sayacı yalnız `durum='Planned'` sayıyor (in-progress kaçabilir)
- Şiddet: low
- Sınıf: domain-rule
- Konum: triage_aggregator.py:291-296
- Durum: needs-verification
- Kanıt:
    ```sql
    COUNT(*) FILTER (WHERE durum = 'Planned') AS active,
    COUNT(*) FILTER (WHERE durum = 'Completed' AND tarih = CURRENT_DATE) AS completed_today
    ```
  "Aktif sefer sayısı" yalnız `durum='Planned'` sayıyor. Canonical durum enum'unda (migration 0022) yolda/
  devam-eden bir durum varsa (ör. 'Active'/'InProgress'/'Assigned') bunlar **aktif sayılmaz** → counter
  gerçek aktif seferi eksik gösterir. (durum enum değerleri S6/migration denetiminde teyit edilecek.)
- Önerilen düzeltme: aktif tanımını canonical enum'la hizala (devam-eden durumları da say).

> Notlar (low / iz):
> - `report_generator` PDF'leri `to_thread` ile sarılı (doğru); `_create_metric_box` markup'ı yalnız
>   kontrollü label/sayısal value alıyor (injection yok). Renkler `__init__`'te CLASS attribute olarak
>   atanıyor (singleton, sorunsuz).
> - `report_service` constructor'ı session'sız yolda (singleton) analiz_repo'yu session'sız bırakır →
>   o yolda analiz çağrıları çöker; ama tüm endpoint'ler `ReportService(session=db)` kullanıyor (session-bound).
>   Singleton yolu fiilen DashboardService (ölü, AUDIT-084) dışında kullanılmıyor.
> - `what_if_engine` percentile indeksleme yaklaşık (`samples[int(0.1*len)]`) — küçük örneklemde hafif sapma. (low)

---

# S2c — Schemas (Pydantic) denetimi

## S2c-1 — base + validators + sefer/arac/yakit/sofor (6 dosya)

Okunan: `base.py` (23), `validators.py` (294), `sefer.py` (352), `arac.py` (283), `yakit.py` (224),
`sofor.py` (271). `base.py` temiz (StandardResponse, extra='ignore' default → mass-assignment yok).
Bulgular AUDIT-105…109.

### AUDIT-105 — Response "healing" validator'ları field constraint'lerini İHLAL eden değer üretiyor → okuma'da 500 (healing amacını çürütüyor)
- Şiddet: medium
- Sınıf: bug / data-integrity
- Konum: arac.py:191-244 (heal_yil/heal_ints/heal_floats), yakit.py:136-155 (heal_amounts/heal_km)
- Durum: confirmed
- Kanıt:
    ```python
    # arac.py — AracBase.yil = Field(None, ge=1990); AracResponse.heal_yil:
    if val < 1900 or val > 2100: return None
    return val                       # 1985 → geçer; ama ge=1990 constraint REDDEDER → ValidationError
    # heal_floats → 0.0 ama hava_direnc_katsayisi gt=0.1 / motor_verimliligi gt=0.1
    # heal_ints  → 0   ama tank_kapasitesi gt=0 / dingil_sayisi ge=1
    ```
    ```python
    # yakit.py — YakitBase.fiyat_tl/litre/toplam_tutar = Field(..., gt=0); YakitResponse.heal_amounts:
    if v is None: return Decimal("0")        # 0 → gt=0 constraint REDDEDER → ValidationError
    # heal_km → 0 ama km_sayac gt=0
    ```
  Response şemaları "bozuk veriyi düzeltip görünürlüğü garanti etmek" için `heal_*` (mode=before)
  validator'ları kullanıyor; ama healed değerler miras alınan **field constraint'lerini ihlal ediyor**:
  `heal_yil` 1900-2100 izin verir ama `ge=1990` → **1900-1989 yıllı araç okuma'da 500**; `heal_floats`/
  `heal_ints` 0/0.0 döndürür ama `gt=0`/`gt=0.1`/`ge=1` → **NULL/0 teknik param 500**; `heal_amounts`
  Decimal("0") döndürür ama `gt=0` → **NULL/0 finansal alan (fiyat/litre/tutar) 500**. Yani "500'ü önlemek"
  için yazılan healing tam tersine, kenar değerlerde **500 GARANTİLER**. (Karşı-örnek: `sofor.py` healing'i
  doğru — değerleri constraint aralığına çeker, AUDIT yok.)
- Önerilen düzeltme: Response field constraint'lerini gevşet (ör. `ge=1990` → `ge=1900` veya kaldır;
  finansal/teknik `gt=0` → `ge=0`), ya da heal değerlerini constraint aralığına çek (sofor deseni gibi).
- Bağımlılık: AUDIT-007 (Arac.yil entity/ORM nullable mismatch — aynı sınıf).

### AUDIT-106 — `validate_safe_string` SQL/XSS blocklist'i serbest-metin alanlara uygulanıyor → meşru Türkçe içerik 422 ile reddediliyor (+ güvenlik tiyatrosu)
- Şiddet: medium
- Sınıf: validation-gap / security
- Konum: validators.py:38-45,100-114 ↔ sefer.py:79, arac.py:90, yakit.py:41, sofor.py:62
- Durum: confirmed
- Kanıt:
    ```python
    SQL_DANGEROUS_PATTERNS = [re.compile(r";\s*--"), re.compile(r"'\s*(OR|AND)\s*'"),
        re.compile(r"UNION\s+SELECT"), re.compile(r"DROP\s+TABLE"),
        re.compile(r"DELETE\s+FROM"), re.compile(r"INSERT\s+INTO")]
    # notlar/istasyon/cikis_yeri/varis_yeri hepsi validate_safe_string'den geçiyor
    ```
  `notlar`, `istasyon`, `cikis_yeri`, `varis_yeri` gibi serbest-metin alanları `check_sql_injection` +
  `check_xss` blocklist'inden geçiyor. Meşru içerik **yanlış pozitif** reddedilir: bir not "müşteri silme
  talebi (delete from list)", "javascript eğitimi", "data: aktarımı", "drop table konusu" → **422**. Üstelik
  blocklist SQL kontrolü güvenlik tiyatrosu (kodun kendi yorumu "asıl koruma parameterized query"); XSS
  blocklist'i de eksik (allowlist/escape değil). Gerçek koruma yokken meşru veriyi engelliyor.
- Önerilen düzeltme: SQL-injection blocklist'i kaldır (parameterized query yeterli); XSS için saklarken
  blocklist yerine **çıktıda escape** uygula (frontend zaten React escape ediyor); serbest-metni reddetme.

### AUDIT-107 — `yakit.py` durum Literal'ında duplike "Onaylandi"/"Onaylandı" + Base↔Update tutarsız + no-op validator
- Şiddet: low
- Sınıf: consistency / dead-code
- Konum: yakit.py:37-39, 97, 67-73
- Durum: confirmed
- Kanıt:
    ```python
    # YakitBase:
    durum: Literal["Bekliyor", "Onaylandi", "Reddedildi", "Onaylandı"] = Field("Bekliyor")  # iki "Onaylandı"
    # YakitUpdate:
    durum: Optional[Literal["Bekliyor", "Onaylandı", "Reddedildi"]] = None                  # yalnız dotted
    # no-op:
    @field_validator("toplam_tutar")
    def validate_toplam_tutar(cls, v, info): return v   # docstring "fiyat*litre kontrolü" ama hiçbir şey yapmıyor
    ```
  `durum` Literal'ı hem noktalı ("Onaylandı") hem noktasız ("Onaylandi") değeri kabul ediyor → kanonik
  drift (iki farklı string aynı durumu temsil eder, filtreleme/karşılaştırma bozulur). Base ile Update farklı
  küme tanımlıyor. `validate_toplam_tutar` docstring'i kontrol vaat ediyor ama gövdesi `return v` (ölü).
- Önerilen düzeltme: tek kanonik değer ("Onaylandı"), Base/Update aynı küme; ölü validator'ı ya gerçek
  kontrolle doldur (|toplam - fiyat×litre| toleransı) ya da kaldır.

### AUDIT-108 — `SeferResponse` agresif sessiz healing okuma yolunda bozuk veriyi makul-ama-uydurma değerlerle maskeliyor + ölü `in_progress_count`
- Şiddet: low
- Sınıf: data-integrity / dead-code
- Konum: sefer.py:271-316, 345-352
- Durum: confirmed
- Kanıt:
    ```python
    def heal_required_floats(cls, v): ... return val if val > 0 else 1.0   # bozuk mesafe → 1.0 km
    def heal_durum(cls, v): ... return SEFER_STATUS_PLANLANDI              # bozuk durum → Planned
    ...
    class SeferStatsResponse: ... in_progress_count: int   # IN_PROGRESS durumu kaldırıldı (line 28) → kaynaksız
    ```
  `SeferResponse` bozuk DB değerlerini sessizce makul default'lara çeviriyor (mesafe→1.0 km, durum→Planned,
  tarih→None) → API "1.0 km"lik uydurma değer döndürür, veri bütünlüğü sorunu sinyalsiz gizlenir.
  `SeferStatsResponse.in_progress_count` ise canonical status setinde IN_PROGRESS kaldırıldığı için (yorum
  line 26-28) kaynağı olmayan ölü alan (hep 0).
- Önerilen düzeltme: read-path healing'i en aza indir (bozuk satırı logla + işaretle, uydurma değer döndürme);
  `in_progress_count`'u kaldır.

### AUDIT-109 — `SoforBase.sanitize_name` `.title()` Türkçe İ/ı'yı bozuyor (şoför adı)
- Şiddet: low
- Sınıf: i18n
- Konum: sofor.py:44-52, 94-101
- Durum: confirmed
- Kanıt:
    ```python
    v = sanitize_string(v)
    v = v.title()   # "İLKER" → "İlker"? Hayır: "ILKER".title()="Ilker", "İLKER".title()="İlker" (Türkçe-bilinçsiz)
    ```
  `str.title()` Türkçe-bilinçsiz: `ad_soyad` kaydedilirken/güncellenirken yanlış kaselenir (örn. "IŞIL" →
  "Işil", doğrusu "Işıl"). Saklanan şoför adı bozulur. (AUDIT-074 lokasyon `.title()` ile aynı sınıf.)
- Önerilen düzeltme: Türkçe-bilinçli başlık-kasesi (locale-aware) ya da kullanıcı girdisini olduğu gibi sakla.

> Notlar (low / iz):
> - `validators.validate_name` TURKISH_NAME_PATTERN circumflex (â/î/û) içermiyor → bazı meşru kelimeler/isimler
>   reddedilebilir; ayrıca isim alanlarında uzunluk üst sınırı regex'te yok (DoS riski düşük, linear). (low)
> - `sefer.heal_yakit` (line 93) `except (ValueError, TypeError, Exception)` — Exception zaten diğerlerini
>   kapsar (gereksiz). (low)
> - `arac.py` plaka regex yalnız büyük harf kabul eder ama Create/Update before-validator uppercase yapmıyor →
>   küçük harf plaka 422 (Response heal_plaka upper'lıyor). (low)

---

## S2c-2 — user/dorse/lokasyon/prediction/executive/api_responses (6 dosya)

Okunan: `user.py` (162), `dorse.py` (182), `lokasyon.py` (181), `prediction.py` (208),
`executive.py` (224), `api_responses.py` (410).
Temiz: `user.py` (healing güvenli — constraint ihlali yok; RolCreate StrictBool ile mass-assignment yok),
`lokasyon.py` (response heal'leri güvenli). Bulgular AUDIT-110…112 + AUDIT-105 genişlemesi.

### AUDIT-110 — `api_responses.py` çok sayıda response şeması `extra="allow"` + ham exception string sızıntısı
- Şiddet: low
- Sınıf: security / api-design
- Konum: api_responses.py:23-40 (ComponentHealth/HealthCheckResponse), 120, 329, 396
- Durum: confirmed
- Kanıt:
    ```python
    class ComponentHealth(BaseModel):
        status: str; latency_ms: ...; error: Optional[str] = None
        model_config = ConfigDict(extra="allow")
    # check_db/check_redis: return {"status": "unhealthy", "error": str(e)}  → error = ham exception
    ```
  `ComponentHealth`, `HealthCheckResponse`, `NotificationRuleResponse`, `FuelStatsResponse`,
  `RouteInfoResponse` `extra="allow"` ile tanımlı → servis dict'indeki **belgesiz/iç alanlar** istemciye
  sızabilir (API sözleşmesi gevşer). Ayrıca `ComponentHealth.error` `str(e)` (health_service) ile ham
  exception mesajını döndürür → DB bağlantı string'i/dosya yolu gibi iç detay bilgi ifşası (admin endpoint
  olsa da). Yorumlar bunu kasıtlı ("service-driven extra") açıklıyor ama sözleşme zayıflığı + leak riski var.
- Önerilen düzeltme: response şemalarında `extra="ignore"` (belgelenen alanlar açık); `error`'ı genel mesaja
  indir (ham exception loglansın, response'a sızmasın).

### AUDIT-111 — `prediction.py` `model_*` alanları Pydantic v2 korumalı namespace ile çakışıyor
- Şiddet: low
- Sınıf: maintainability
- Konum: prediction.py:38,58,65,96 (model_type/model_used/model_version)
- Durum: confirmed
- Kanıt:
    ```python
    model_type: Literal["linear", "xgboost", "ensemble"] = Field("ensemble", ...)
    model_used: Literal[...] = "ensemble"
    model_version: Optional[str] = Field(None, ...)
    ```
  Pydantic v2 `model_` prefix'ini korumalı namespace olarak ayırır; bu alanlar tanım anında `UserWarning:
  Field "model_used" has conflict with protected namespace "model_"` üretir (gürültü + ileride kırılma riski).
- Önerilen düzeltme: ilgili şemalara `model_config = ConfigDict(protected_namespaces=())` ekle ya da alanları
  yeniden adlandır (ör. `ml_model_type`).

### AUDIT-112 — `WhatIfRequest` `scenario_type` ile eşleşen input variant'ının verildiğini doğrulamıyor
- Şiddet: low
- Sınıf: validation-gap
- Konum: executive.py:55-61
- Durum: confirmed
- Kanıt:
    ```python
    class WhatIfRequest(BaseModel):
        scenario_type: ScenarioType
        fleet_renewal: Optional[FleetRenewalInputs] = None
        training: Optional[TrainingInputs] = None
        route_portfolio: Optional[RoutePortfolioInputs] = None
    ```
  Docstring "scenario_type'a göre 3 input variant'tan biri gerekir" diyor ama hiçbir model_validator bunu
  zorlamıyor: `scenario_type="training"` + `training=None` şemadan geçer → servis None input alır (None deref
  veya boş senaryo riski).
- Önerilen düzeltme: `@model_validator(mode="after")` ile `getattr(self, scenario_type)` not-None kontrolü.

> Notlar (low / iz):
> - **AUDIT-105 genişlemesi:** `dorse.py:118-166` aynı heal-vs-constraint hatasına sahip (heal_yil 1900-2100
>   vs `ge=1990`; heal_floats→0.0 vs `gt=0`; heal_ints→0 vs `ge=4`/`gt=0`). `lokasyon.py` LokasyonResponse
>   miras alınan `mesafe_km gt=0`'ı healing'siz bırakıyor → DB'de mesafe_km≤0 ise okuma 500. (AUDIT-105 kapsamı)
> - `user.KullaniciBase.email` format validasyonu yok (EmailStr değil) — kullanıcı-adı login'i için kasıtlı,
>   ama tamamen serbest string kabul ediyor. (low, kasıtlı)
> - `prediction.TrainingResponse.validate_metrics_values` derinlik/tip kontrolü ile DoS koruması **doğru** desen.

---

## S2c-3 — kalan 13 schema (coaching/investigation/trip_planner/push/analytics/attribution/fleet_insights/maintenance_prediction/ml_schemas/preference/report_template/telegram/today)

Temiz (11): `coaching.py` (PII-bilinçli, max_length bütçeli), `investigation.py`, `trip_planner.py`,
`analytics.py`, `attribution.py` (reason min_length=5), `fleet_insights.py`, `maintenance_prediction.py`,
`report_template.py` (statik Literal meta), `telegram.py` (AliasChoices ile geriye-uyum doğru), `today.py`,
`ml_schemas.py` (yalnız AUDIT-111 namespace izi). Bulgular AUDIT-113…114. **Bu küme ile schemas 25/25 →
S2 (domain) TAMAM.**

### AUDIT-113 — `PushSubscriptionRequest.endpoint` push-sağlayıcı URL doğrulaması yok → sunucu-taraflı webpush ile blind SSRF
- Şiddet: low
- Sınıf: security
- Konum: push.py:21-26 ↔ push_sender.py:48-56 (_do_send)
- Durum: confirmed
- Kanıt:
    ```python
    class PushSubscriptionRequest(BaseModel):
        endpoint: str = Field(..., min_length=10)   # sadece uzunluk; şema/host allowlist YOK
        keys: PushSubscriptionKeys
    ```
  `endpoint` yalnız `min_length` ile sınırlı; push-sağlayıcı (FCM/Mozilla autopush) host'u doğrulanmıyor.
  `push_sender._do_send` webpush ile bu URL'e **sunucudan POST** atar. Doğrudan API çağrısıyla
  `endpoint="http://169.254.169.254/..."` veya iç servis URL'i verilirse sunucu o adrese istek yapar →
  blind SSRF (yanıt dönmez ama iç port tarama/tetikleme). Auth-gated ve tarayıcı normalde meşru URL verir,
  bu yüzden low.
- Önerilen düzeltme: `endpoint`'i bilinen push-sağlayıcı host allowlist'i + `https://` şeması ile doğrula
  (field_validator); özel/iç IP'leri reddet.

### AUDIT-114 — `PreferenceBase.deger: Any` sınırsız → keyfi büyük JSON saklanabilir (DB bloat/DoS)
- Şiddet: low
- Sınıf: validation-gap / dos
- Konum: preference.py:7-16
- Durum: confirmed
- Kanıt:
    ```python
    class PreferenceBase(BaseModel):
        modul: str            # max_length yok
        ayar_tipi: str        # max_length yok
        deger: Any            # boyut/tip sınırı yok
    ```
  `deger: Any` herhangi bir JSON kabul eder; `validators.validate_dict_size` mevcut ama burada **uygulanmıyor**
  → kullanıcı megabaytlarca JSON'u tercih olarak kaydedebilir (DB şişmesi, AUDIT-079 duplikat birikimiyle
  birleşince katlanır). `modul`/`ayar_tipi` de uzunluk-sınırsız.
- Önerilen düzeltme: `deger`'e boyut sınırı (validate_dict_size / serialize edip byte limiti), `modul`/
  `ayar_tipi`'ye `max_length` ekle.

> Notlar (low / iz):
> - **AUDIT-111 genişlemesi:** `ml_schemas.ModelVersionRead.model_dosya_yolu` (line 41) da `model_` korumalı
>   namespace ile çakışır (Pydantic v2 UserWarning). (AUDIT-111 kapsamı)
> - `today.TriageItem` / `triage_aggregator` "active_trip" semantiği AUDIT-104 ile aynı (durum='Planned').
> - S2 (domain) kapsamı kapandı: repositories 22 + core/services 62 + schemas 25 = **109 dosya**, AUDIT-001…114.
