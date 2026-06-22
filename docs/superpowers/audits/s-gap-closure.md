# GAP-CLOSURE — Review sonrası okunmamış sunum-dışı üretim dosyaları

`AUDIT-REVIEW.md` (bağımsız code-reviewer) "substantive tamam" iddiasının ~32 okunmamış üretim dosyasını
(core/utils, core/integrations, core/handlers, core/interfaces, core/unit_of_work, domain/services,
app/scripts, çeşitli __init__) kapsadığını tespit etti. Bu dosyalar okundu. Sonuç: **2 yeni confirmed bug
(AUDIT-179/180) + 2 ek (181/182)** + mevcut ailelere kanıt.

## Temiz/örnek (0 bulgu)
- `core/utils/trip_status.py` — **AUDIT-174 backend KÖKÜ**: İngilizce canonical (Planned/Completed/Cancelled) +
  `_fold_status` (NFKD+ASCII-fold+casefold) Türkçe/ASCII/İngilizce → İngilizce normalize eder. Frontend bunu
  AYNALAMALI (AUDIT-174 fix yönü kesinleşti). `sefer_status.py` = Türkçe-adlı re-export (değerler İngilizce).
- `core/unit_of_work.py` — **benign re-export** (app.database.unit_of_work.UnitOfWork + get_uow CM). Review'in
  "ikinci UoW" şüphesi → ÇÜRÜTÜLDÜ, divergent değil.
- `core/integrations/{avl,fuel}/*` — provider stub'ları (NotImplementedError, healthcheck=False, config-driven,
  sabit sır yok), registry disabled-if-unconfigured. `base.py` Protocol+dataclass (idempotent external_id).
- `core/utils/clock.py` (clock injection — date.today() testability fix), `polyline.py` (saf decoder),
  `type_helpers.py` (safe_float). `app/scripts/create_admin.py` (env-based, sabit sır YOK — kök scripts/ ikizi).
- `interfaces/repositories.py` + `protocols.py` (ABC/Protocol — iz: concrete repo'lar bunları implemente
  etmiyor olabilir, aspirational/dead; low). `errors.py` exception handler'ları (global generic-message,
  stack sızıntısı yok).
- `domain/services/route_analyzer.py` — sağlam geometri matematiği (iz: `_aggregate_results` ölü metot, low).
- `entities/sofor_degerlendirme.py` — AUDIT-048 (3. şoför puanlama ölçeği: verimlilik40/tutarlilik25/deneyim20/
  trend15) + AUDIT-084 ailesi (`_add_guzergah_performansi` session'sız get_sofor_repo, try/except→sessiz boş;
  `get_all_evaluations(include_routes=True)` N+1). Yeni numara yok, mevcut aileleri pekiştirir.

### AUDIT-179 — ModelTrainingHandler var-olmayan `event_bus.publish_simple` çağırıyor → AttributeError (yutulur) → otomatik-eğitim sonrası cache/RAG invalidation hiç tetiklenmez
- Şiddet: medium
- Sınıf: bug
- Konum: model_training_handler.py:87 (event_bus.py'de yalnız publish/publish_async/publish_simple_async var)
- Durum: confirmed
- Kanıt:
    ```python
    loop.create_task(svc.train_for_vehicle(vehicle_id))   # ref tutulmaz → GC (AUDIT-130 ailesi)
    self.event_bus.publish_simple(EventType.CACHE_INVALIDATED, entity="model", arac_id=vehicle_id)
    #                  ^^^^^^^^^^^^ EventBus'ta böyle metot YOK → AttributeError
    ```
  EventBus API'si `publish`, `publish_async`, `publish_simple_async`, `publish_typed` sağlar — `publish_simple`
  YOK. Threshold'a ulaşınca (5 kayıt) auto-train tetiklenir ama hemen ardından `publish_simple` AttributeError
  fırlatır; tüm blok try/except içinde (l.71-94) olduğundan yutulur ("auto-train error" loglanır). Sonuç:
  model eğitilir ama cache/RAG invalidation event'i ASLA yayınlanmaz → eğitilen modelin sonuçları RAG'e/cache'e
  yansımaz. Ayrıca `create_task` referanssız (GC riski).
- Önerilen düzeltme: `publish_simple` → `await publish_simple_async` (handler zaten async) ya da
  `publish_typed`; create_task referansını sakla.
- Bağımlılık: AUDIT-141/130 (event_bus create_task), AUDIT-126 (train blocking), event_bus API.

### AUDIT-180 — backfill_route_pairs.py `.where(Sefer.route_pair_id is None)` Python `is None` → `WHERE false` → 0 satır → backfill sessizce hiçbir şey yapmaz
- Şiddet: medium
- Sınıf: bug
- Konum: app/scripts/backfill_route_pairs.py:22
- Durum: confirmed
- Kanıt:
    ```python
    .where(Sefer.route_pair_id is None)   # Python identity check → False; SQLAlchemy .is_(None) DEĞİL
    ```
  `Sefer.route_pair_id is None` Python'da `False` döner (column kimlik karşılaştırması), `.where(False)` →
  `WHERE false` → sorgu HİÇBİR satır döndürmez. Script her çalıştığında "updated 0 records" der; route_pair_id
  backfill'i hiç gerçekleşmez (HB2 kontratı çözülmemiş kalır). Doğru kullanım `Sefer.route_pair_id.is_(None)`.
- Önerilen düzeltme: `.where(Sefer.route_pair_id.is_(None))`.
- Bağımlılık: seferler.route_pair_id (9728 migration), route_service route_pair (AUDIT-043).

### AUDIT-181 — PhysicsRecalculationHandler async handler'da senkron `predictor.predict` (event-loop bloke) + her SEFER_UPDATED'de manuel tahmini_tuketim'i eziyor
- Şiddet: low
- Sınıf: performance
- Konum: physics_handler.py:28-101
- Durum: needs-verification
- Kanıt:
    ```python
    async def on_sefer_updated(self, event):
        ...
        prediction = predictor.predict(conditions)   # senkron CPU fizik, to_thread YOK → loop bloklar
        await uow.sefer_repo.update(sefer_id, tahmini_tuketim=prediction.total_liters)  # manuel değeri ezer
    ```
  Handler SEFER_UPDATED'de senkron physics predict çalıştırır (to_thread'siz → event-loop bloke, AUDIT-063/126
  ailesi) ve `trigger != "physics_recalculation"` olan her güncellemede `tahmini_tuketim`'i yeniden hesaplayıp
  yazar → kullanıcının manuel girdiği tahmini_tuketim ezilir. Handler'ın `register()` ile aktif edilip
  edilmediği (startup'ta çağrılıyor mu) doğrulanmalı; aktifse her override'da çalışır.
- Önerilen düzeltme: predict'i `asyncio.to_thread` ile sar; manuel-override koruması ekle (kullanıcı elle
  set ettiyse physics ezmesin).
- Bağımlılık: AUDIT-126/063 (sync ML in async), event_bus subscribe (registration).

### AUDIT-182 — İki ayrı hata-yanıt zarfı: `core/errors.py` ({success/suggestion/request_id/timestamp}) vs `main.py` ({error:{code,message,trace_id}}) → tutarsız API hata formatı
- Şiddet: low
- Sınıf: consistency
- Konum: core/errors.py:51-70 (vs CLAUDE.md'deki main.py envelope)
- Durum: needs-verification
- Kanıt:
    ```python
    # errors.py
    content={"success": False, "error": {"code","message","details","suggestion","request_id","timestamp"}}
    # main.py (CLAUDE.md): {"error": {"code","message","trace_id"}}
    ```
  İki farklı hata zarfı var; `request_id` vs `trace_id`, +success/suggestion/timestamp. Hangi handler'ların
  main.py'de register edildiği (errors.py ölü mü, yoksa ikisi de aktif olup farklı uçlarda farklı format mı
  dönüyor) doğrulanmalı. Aktifse frontend hata-parse'ı (axios-instance errData.error.message) bir formatta
  çalışır diğerinde kaçırır.
- Önerilen düzeltme: tek hata-zarfı konvansiyonu; ölü handler'ı kaldır. Ayrıca dev-tool izleri:
  `app/scripts/benchmark.py` async servis metotlarını `await`'siz çağırıyor (coroutine — ölçüm anlamsız,
  AUDIT-170 ailesi).
- Bağımlılık: main.py exception handlers, axios-instance error parse, AUDIT-110 (response leak).

> **GAP-CLOSURE TAMAM: 32 dosya okundu. Yeni bulgular AUDIT-179..182 (confirmed 2 + nv 2). Review'in kapsam
> uyarısı haklıydı — backfill `is None` ve handler `publish_simple` gerçek bug'lardı. trip_status.py (AUDIT-174
> kökü) ve core/unit_of_work (benign) netleşti.**

## Review-önerisi şiddet düzeltmeleri (uygulandı)
- AUDIT-037 medium→**high** (yakıt=0 günde tüketimi 0'a ezme = kalıcı veri kaybı; review §3).
- AUDIT-115 medium→**high** (env super-admin bypass; SUPER_ADMIN_PASSWORD prod'da set ise).
- **Faz-2 blocker seti** (spec §6 blocker tanımına uyan, triyaj başı): AUDIT-174, 081, 076, 057, 022, 168, 037.
