# S1 — Backend Çekirdek Denetimi

**Kapsam:** 14 dosya (config, main, security, deps, rate_limiter, container, unit_of_work,
base_repository, connection, db_session, init_db, models, entities/models, exceptions).
**Yöntem:** her dosya `Read` ile baştan sona okundu; her bulgu kaynak satırına + alıntıya dayanır
(demir kural §3). Çapraz-doğrulamalar grep ile teyit edildi.

> Şiddet yalnız düzeltme sırası içindir — kullanıcı kuralı gereği **her bulgu kritiktir**.

---

### AUDIT-001 — `execute_query` rollback dalı ölü + ters mantık
- Şiddet: medium · Sınıf: bug / dead-code · Durum: confirmed
- Konum: `app/database/base_repository.py:415`
- Kanıt:
  ```python
  async def execute_query(self, query, params=None):
      session = self.session            # 409 — None ise BURADA RuntimeError fırlar
      try:
          ...
      except Exception as e:
          logger.error(f"Database query error: {e}")
          if not self.session:          # 415 — property None'da raise eder, asla falsy DÖNMEZ
              await session.rollback()
          raise e
  ```
- Sorun: `self.session` bir property; `_session is None` iken `RuntimeError` fırlatır, aksi halde
  truthy session döner. Dolayısıyla `if not self.session` **hiçbir zaman True olamaz** → rollback
  satırı ölü. Niyet muhtemelen "session'ı biz açtıysak rollback et" idi; mantık ters yazılmış.
  Pratik etki düşük (dış `get_db`/UoW zaten rollback ediyor) ama kod yanıltıcı ve yanlış.
- Önerilen düzeltme: ölü dalı kaldır; raw-SQL hata rollback'i gerekiyorsa `_external_session`/
  ownership bilgisini repo'ya taşıyıp ona göre karar ver (yama Faz 2).

### AUDIT-002 — `update()` içinde atanmayan no-op + stale yorum bloğu
- Şiddet: low · Sınıf: dead-code · Durum: confirmed
- Konum: `app/database/base_repository.py:281-290`
- Kanıt:
  ```python
  inspect(self.model).primary_key[0].name      # 281 — hesaplanıp ATILMIYOR (no-op)
  # 282-289: "Assuming get_session is an async context manager ... If get_session
  #           does not exist, this will cause an error ... following the user's
  #           explicit instruction ..." — gerçeklikle alâkasız stale yorum
  session = self.session  # Reverting to original session acquisition ...
  ```
- Sorun: 281'deki ifade hiçbir değişkene atanmıyor (etkisiz). 282-290 arası, var olmayan bir
  `get_session` metodu hakkında AI-üretimi kararsız yorum artığı; okuyucuyu yanıltıyor.
- Önerilen düzeltme: 281'i sil, 282-290 yorum bloğunu kaldır.

### AUDIT-003 — `count()` exception'ı yutup 0 döndürüyor (sessiz hata)
- Şiddet: medium · Sınıf: silent-failure · Durum: confirmed
- Konum: `app/database/base_repository.py:398-403`
- Kanıt:
  ```python
  try:
      result = await session.execute(stmt)
      return result.scalar() or 0
  except Exception as e:
      logger.error(f"Count error for {self.model.__name__}: {e}")
      return 0
  ```
- Sorun: DB hatası ile "0 kayıt" çağıran için ayırt edilemez. Pagination toplamı, "veri yok" UI'ı,
  kapasite/oran kapıları 0'ı gerçek değer sanar → sessiz veri yanlış-temsili.
- Önerilen düzeltme: exception'ı yut**ma**; ya yukarı fırlat ya da `Optional[int]` döndürüp çağıranın
  hata/0 ayrımı yapmasını sağla.

### AUDIT-004 — `create`/`bulk_create` bilinmeyen alanı sessizce düşürüyor
- Şiddet: low · Sınıf: silent-failure · Durum: confirmed
- Konum: `app/database/base_repository.py:234, 253`
- Kanıt:
  ```python
  filtered_data = {k: v for k, v in data.items() if k in physical_columns}
  ```
- Sorun: Yanlış yazılmış / yeniden adlandırılmış bir kolon adı uyarısız atılır → değer sessizce
  yazılmaz. Güvenlik amaçlı bilinçli bir tasarım ama çağıran hatasını maskeler.
- Önerilen düzeltme: bilinmeyen anahtarları en azından `logger.warning` ile raporla (Faz 2).

### AUDIT-005 — ML warm-up task'ı referanssız `create_task` → GC riski; `_bg_tasks` ölü
- Şiddet: medium · Sınıf: concurrency / dead-code · Durum: confirmed
- Konum: `app/main.py:296` (ve `:42`)
- Kanıt:
  ```python
  _bg_tasks: set[asyncio.Task] = set()   # 42 — "keep ... alive ... prevent GC" yorumu
  ...
  _asyncio.create_task(_warmup_all_predictors())   # 296 — dönüş referansı TUTULMUYOR
  ```
- Sorun: asyncio dokümanı: `create_task` dönüşüne güçlü referans tutulmazsa task çalışırken GC
  edilebilir. main.py bu amaç için `_bg_tasks` set'ini tanımlamış ama warm-up'ı eklemiyor →
  `_bg_tasks` **ölü** (grep: main.py'de yalnız satır 42; hiç `.add()` yok). Kardeş modüller doğru
  yapıyor: `alarm_router.py:170` ve `db_probe.py:168` `add()` + `add_done_callback(discard)`.
- Önerilen düzeltme: `t = _asyncio.create_task(...); _bg_tasks.add(t); t.add_done_callback(_bg_tasks.discard)`.

### AUDIT-006 — `/metrics` IP guard reverse-proxy arkasında baypas edilebilir
- Şiddet: medium · Sınıf: security · Durum: needs-verification (deployment'a bağlı)
- Konum: `app/main.py:337-347` + `_is_metrics_allowed` `:45-66` + `config.py:90`
- Kanıt:
  ```python
  client_ip = request.client.host if request.client else ""   # doğrudan peer IP
  if not _is_metrics_allowed(client_ip): return 403
  # METRICS_ALLOWED_IPS default: "127.0.0.1,::1,172.16.0.0/12,10.0.0.0/8"
  ```
- Sorun: Guard yalnız doğrudan peer IP'ye bakar; X-Forwarded-For / güvenilir-proxy işlenmiyor.
  Bir reverse proxy'nin IP'si Docker aralığında (172.16/12, 10/8) ise, o proxy üzerinden gelen
  **her** istek guard'ı geçer → proxy `/metrics`'i dışarı forward ediyorsa metrik sızıntısı.
- Önerilen düzeltme: proxy mimarisini doğrula; gerekiyorsa /metrics'i ağ katmanında (proxy/ingress)
  kapat veya güvenilir-proxy + XFF tabanlı gerçek istemci IP çözümü ekle.

### AUDIT-007 — Entity `Arac.yil` zorunlu ama ORM kolonu nullable → NULL yılda 500
- Şiddet: medium · Sınıf: data-integrity / validation-gap · Durum: confirmed
- Konum: `app/core/entities/models.py:129,151-153` ↔ `app/database/models.py:78`
- Kanıt:
  ```python
  # entity: zorunlu + computed dereference
  yil: int = Field(ge=1990, le=2030)                 # entities:129
  def yas(self): return date.today().year - self.yil # entities:151-153
  # ORM: nullable
  yil: Mapped[Optional[int]] = mapped_column(Integer) # models:78
  ```
- Sorun: `from_attributes=True` ile ORM'den entity kurulurken `yil=None` olan araç ValidationError
  fırlatır (`yas` da None'u dereference ederdi). NULL `yil` taşıyan bir kayıt okuma yolunu 500'e
  düşürür. Entity şemadan daha katı.
- Önerilen düzeltme: ya ORM'de `yil` NOT NULL + backfill, ya entity'de `yil: Optional[int]` + `yas`
  None-safe. (Karar Faz 2; veri durumu kontrol edilmeli.)

### AUDIT-008 — Kullanıcı/ref id kolonları FK'sız (referans bütünlüğü boşluğu)
- Şiddet: low · Sınıf: data-integrity / arch-drift · Durum: confirmed
- Konum: `app/database/models.py:874,878` (`Anomaly.acknowledged_by`,`resolved_by`),
  `:649` (`SeferLog.degistiren_id`), `:1206` (`BildirimKurali.alici_rol_id`),
  `:665-666` (`YakitPeriyot.alim1_id`,`alim2_id`)
- Kanıt:
  ```python
  acknowledged_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # FK YOK
  resolved_by:     Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # FK YOK
  ```
- Sorun: Gerçek kullanıcı/rol/alım id'leri tutan bu alanlarda FK yok → orphan/tutarsızlık DB
  düzeyinde engellenmiyor. Bir kısmı bilinçli "soft link" (periyot/alım), ama `acknowledged_by`/
  `resolved_by` gerçek kullanıcıyı işaret ediyor.
- Önerilen düzeltme: anlamlı olanlara `ForeignKey("kullanicilar.id", ondelete="SET NULL")` ekle
  (migration, Faz 2). Soft-link olanları yorum + index ile koru.

### AUDIT-009 — `init_db.py` `Base.metadata.create_all` kullanıyor (CLAUDE.md ihlali)
- Şiddet: low · Sınıf: arch-drift · Durum: confirmed (prod'da çağrılmıyor)
- Konum: `app/database/init_db.py:22`
- Kanıt:
  ```python
  await conn.run_sync(Base.metadata.create_all)   # 22
  if __name__ == "__main__": asyncio.run(init_primary_data())  # 28
  ```
- Sorun: CLAUDE.md: "Do not use `Base.metadata.create_all` in production — always use
  `alembic upgrade head`." Grep teyidi: `init_primary_data` yalnız `__main__`'de çağrılıyor,
  `lifespan` çağırmıyor → prod startup'ta tetiklenmez (risk düşük). Yine de yol mevcut; çağrılırsa
  Alembic damgalanmamış (drift'li) şema üretir.
- Önerilen düzeltme: dosyaya prod-guard ekle veya yalnız test/local helper olduğunu belgele;
  `ENVIRONMENT=="prod"` ise reddet.

### AUDIT-010 — Create-DTO ile read-entity validasyon sınırları çelişiyor
- Şiddet: low · Sınıf: consistency / validation-gap · Durum: confirmed
- Konum: `app/core/entities/models.py` — `:242` vs `:129`; `:380-381` vs `:336-337`
- Kanıt:
  ```python
  # yil: create 1980..today+1, entity 1990..2030
  if v < 1980 or v > date.today().year + 1: ...     # AracCreate.validate_yil:242
  yil: int = Field(ge=1990, le=2030)                # Arac entity:129
  # fiyat/litre: create le=200/2000, entity le=1000/10000
  fiyat_tl: Decimal = Field(..., gt=0, le=Decimal("200"));  litre: float = Field(..., gt=0, le=2000)  # Create:380-381
  fiyat_tl: Decimal = Field(..., gt=0, le=Decimal("1000")); litre: float = Field(..., gt=0, le=10000) # entity:336-337
  ```
- Sorun: Create'te geçerli bir değer entity'de (okuma) geçersiz olabilir veya tersi → tutarsız
  doğrulama sözleşmesi; sınır kararları tek yerde değil.
- Önerilen düzeltme: sınırları tek bir kaynak (paylaşılan sabit/validator) üzerinden tanımla.

### AUDIT-011 — UoW `commit()`/`rollback()` `_owns` kontrol etmiyor → iç içe commit dış transaction'ı erken kalıcı kılar
- Şiddet: medium · Sınıf: concurrency / design · Durum: needs-verification (kullanım deseni S2'de)
- Konum: `app/database/unit_of_work.py:186-196`
- Kanıt:
  ```python
  async def commit(self):
      if self._session is None or self._committed: return
      await self._session.commit()     # _owns kontrolü YOK
      self._committed = True
  ```
- Sorun: Docstring "outermost owner controls lifecycle" diyor ama `commit()` ownership'e bakmıyor.
  Dışarıdan verilen/iç içe (non-owning) bir UoW `await uow.commit()` çağırırsa **paylaşılan** session'ı
  commit eder → dış transaction'ın bekleyen yazımları erken kalıcı olur (kısmi/yanlış commit riski).
- Önerilen düzeltme: S2'de servislerin `uow.commit()`'i ne zaman çağırdığını doğrula; gerekirse
  non-owning UoW'da commit'i no-op yap (yalnız owner commit etsin). (Doğrulama sonrası karar.)

---

## Doğrulanan ama bulgu OLMAYAN (negatif kanıt — şeffaflık için)

- **security.py:66 "RS256→HS256 sessiz downgrade" YOK.** `config.py:286-291` `_validate`,
  `ALGORITHM=RS256` iken her iki anahtarı (PRIVATE+PUBLIC) zorunlu kılıyor (fail-fast) →
  `create_access_token`'daki `and settings.JWT_PRIVATE_KEY` yalnız savunmacı fazlalık, downgrade
  pratikte imkânsız.
- **deps.py JWT decode** `algorithms=[settings.ALGORITHM]` ile tek algoritma kabul ediyor →
  algorithm-confusion yok.
- **Süper-admin virtual user** yalnız imzası doğrulanmış `is_super=True` + `sub==SUPER_ADMIN_USERNAME`
  token'ı için üretiliyor; forge için SECRET gerekir.
- **connection.py** pool, `pool_reset_on_return="rollback"`, prod SSL (`ssl=require`/`sslmode=require`),
  per-statement `command_timeout` — sağlam.

## Sonraki sıraya taşınan iz (S5/S2)
- `app/infrastructure/security/jwt_handler.py` da token üretiyor → `core/security.py` ile **ikinci
  JWT implementasyonu** (duplikasyon adayı, S5'te denetlenecek).
- AUDIT-011 kullanım deseni doğrulaması S2 (core/services) sırasında.

**Özet:** 11 bulgu (blocker 0 · high 0 · medium 6 · low 5) — 14/14 dosya okundu.
