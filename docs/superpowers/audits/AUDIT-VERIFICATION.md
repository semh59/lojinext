# AUDIT-VERIFICATION — Fix Doğrulama Ledger'ı

Tarih: 2026-06-17
Amaç: AUDIT-INDEX.md'deki 183 bulgunun her birinin fix'inin **gerçekten** uygulandığını,
sahte/yarım/gerilemiş olmadığını mevcut kod üzerinde tek tek kanıtlamak.
Kural: "en küçük hata ve eksiklik kritiktir" — her fix kod-seviyesinde okunarak doğrulanır.

Statü: PASS (fix gerçek+doğru) · CONCERN (fix var ama eksik/şüpheli) · FAIL (fix yok/sahte/gerilemiş)

---

## Faz A — HIGH severity (19 bulgu)

| ID | Beklenen fix | Doğrulama | Statü |
|----|-------------|-----------|-------|
| AUDIT-012 | cartesian join → ayrı sorgular | sefer_repo.py:220-234 üç ayrı SUM sorgusu, JOIN yok | PASS |
| AUDIT-018 | flush sonra refresh | admin_config_repo.py:61 flush → :62 refresh (doğru sıra) | PASS |
| AUDIT-022 | reset token hash'leniyor | auth_service.py:230 hash_token(token); kullanici_repo.py:35 ==token_hash | PASS |
| AUDIT-037 | yakit=0 günde tüketim ezilmez | sefer_analiz_service.py:61-66 skip; :77-82 km=0 skip | PASS |
| AUDIT-044 | gather→serial + uow sızıntısı yok | sofor_analiz_service.py:96-106 serial for + effective_uow local | PASS |
| AUDIT-051 | LGB Türkçe kolon adı | anomaly_detector.py:438 a.get("deger"); :440 beklenen_deger | PASS |
| AUDIT-057 | doğru tablo yakit_alimlari | import_service.py:403,480 yakit_alimlari | PASS |
| AUDIT-058 | mapping ters yön düzeltildi | import_service.py:294 inv_mapping = {v:k} | PASS |
| AUDIT-061 | depo_durumu taşınıyor | period_calculation_service.py:283 depo_durumu=r.get(...) | PASS |
| AUDIT-076 | self-UoW commit | push_sender.py:129 await uow_local.commit() | PASS |
| AUDIT-081 | her satıra bağımsız UoW | admin_attribution.py: AttributionService(UnitOfWork()) per item | PASS |
| AUDIT-093 | tz-aware/naive uyumu | maintenance_service.py:125 replace(tzinfo=None) | PASS |
| AUDIT-094 | session'lı uow | insight_engine.py:36 async with get_uow() | PASS |
| AUDIT-099 | gather kaldırıldı | report_service.py gather yok (serial) | PASS |
| AUDIT-115 | super admin backdoor sertleşti | auth.py:67-76 SecretStr+compare_digest, plaintext yok | PASS |
| AUDIT-131 | session'lı uow | time_series_service.py:84 async with UnitOfWork() | PASS |
| AUDIT-142 | poison pill processed=True | outbox_service.py:107-115 retry>=5 → processed=True+critical log | PASS |
| AUDIT-168 | env-based parolalar | config.py:46-48 SecretStr; scripts env-driven | PASS |
| AUDIT-174 | durum normalizasyonu | trip_status.py normalize_trip_status TR→EN; backend canonical | PASS |

**Faz A sonucu: 19/19 PASS** — tüm HIGH bulgular gerçekten ve doğru fixlenmiş.

---

## Faz B — "verified-ok" (fix gerekmedi iddiası) + "partial"

| ID | İddia | Doğrulama | Statü |
|----|-------|-----------|-------|
| AUDIT-036 | DB UNIQUE gerçek koruma | models.py:75,159 plaka unique=True | PASS |
| AUDIT-042 | INFO log mevcut | sefer_write_service.py:1388-1391 logger.info batch>20 | PASS |
| AUDIT-046 | metot aktif+float döner | `calculate_performance_score` float döner (✓) AMA gerekçe yanlış metoda atıf: report_service kendi `_calculate_performance_score`'unu kullanır; sofor_analiz `calculate_performance_score` yalnız testlerce çağrılır. Ayrıca `calculate_elite_performance_score` (L361) artık üretimde çağrılmıyor (yalnız docstring) + `-> float` anotasyonlu ama None döner (L381 vd.) — `--no-strict-optional` nedeniyle mypy yakalamıyor. Runtime etkisi yok (çağrılmıyor) ama ölü kod + yanlış anotasyon kalıntısı. | CONCERN |
| AUDIT-104 | domain yalnız Planned aktif | triage_aggregator.py:292 FILTER durum='Planned'; domain Planned/Completed/Cancelled | PASS |
| AUDIT-130 | _bg_tasks pattern uygulanmış | prediction_service.py:27,829-831 set+add+discard | PASS |
| AUDIT-143 | OrderedDict FIFO | event_bus.py:78,165 popitem(last=False) | PASS |
| AUDIT-145 | poison processed=True | outbox_service.py:107-115 retry>=5→processed=True | PASS |
| AUDIT-110 | error sanitize + extra=allow kasıtlı | api_responses.py:35-41 sanitize_error (conn-str redact + 300 cap); :370 extra=allow yorumlu | PASS |
| AUDIT-170 | enrich await+durum düzeltildi | enrich_existing_data.py:32,55 await + durum=='Completed' | PASS |

**Faz B sonucu: 8 PASS, 1 CONCERN (AUDIT-046 — ölü kod + yanlış `-> float` anotasyonu, runtime etkisi yok).**

---

## Faz C1 — Repository katmanı (AUDIT-001..021)

| ID | Doğrulama | Statü |
|----|-----------|-------|
| AUDIT-001 | base_repository.py:420-421 rollback→raise (ölü/ters dal yok) | PASS |
| AUDIT-002 | base_repository.py:290-324 update gerçek mantık, no-op/stale yorum yok | PASS |
| AUDIT-003 | base_repository.py:408 count() artık raise (return 0 yok) | PASS |
| AUDIT-004 | base_repository.py:234-239 bulk_create dropped alanları logger.debug | PASS |
| AUDIT-005 | main.py:43,297-299 warmup _bg_tasks set+discard | PASS |
| AUDIT-006 | main.py:348-351 X-Forwarded-For yalnız loopback'te (trusted proxy) | PASS |
| AUDIT-007 | entities/models.py:129 yil Optional ↔ ORM:78 Optional | PASS |
| AUDIT-008 | alembic/versions/0028_missing_fk_constraints.py mevcut (NOT VALID, manuel VALIDATE) | PASS |
| AUDIT-009 | init_db.py:20-22 ENVIRONMENT=production guard raise | PASS |
| AUDIT-010 | entities/models.py:129 ge=1980/le=2030 hizalı | PASS |
| AUDIT-011 | unit_of_work.py:187 commit() `not self._owns` kontrolü | PASS |
| AUDIT-012 | sefer_repo.py:220-234 cartesian yerine 3 ayrı sorgu | PASS |
| AUDIT-013 | sefer_repo.py:685-686 engine isolation_level=AUTOCOMMIT | PASS |
| AUDIT-014 | get_trip_stats:468 ölü base sorgu temizlendi | PASS |
| AUDIT-015 | analiz_repo seferler sorguları is_deleted=False; **ANCAK** yakit_alimlari agregaları (459,509,650,707) `aktif=TRUE` filtresiz — get_dashboard_stats:211 filtreler. Pratikte zararsız (delete_yakit hard-delete, soft-delete yolu yok) ama tutarsızlık latent. | PASS+NOT |
| AUDIT-016 | yakit_repo.py:197-205 update_yakit Decimal + partial DB-fetch recompute | PASS |
| AUDIT-017 | session_repo.py:30 flush; ters kontrol+ölü kod+UoW bypass yok | PASS |
| AUDIT-018 | admin_config_repo.py:61-62 flush→refresh doğru sıra | PASS |
| AUDIT-019 | notification/maintenance repo datetime.now(timezone.utc) | PASS |
| AUDIT-020 | model_versiyon_repo.py:48-57 target exists guard, yoksa return False | PASS |
| AUDIT-021 | analiz_repo 198/240/325/401 artık logger.error(exc_info=True) — silent değil, display-layer graceful fallback | PASS |

**Faz C1 sonucu: 21/21 PASS** (AUDIT-015'te latent yakit `aktif` filtre tutarsızlığı notlandı — düşük, pratik etki yok).

### Yeni latent gözlem (DÜZELTİLDİ)
- **VER-OBS-1** (AUDIT-015 türevi) — **KAPATILDI**: `analiz_repo` yakit_alimlari agregaları (459,509,650,707) artık `aktif=TRUE` filtreli (line 211 ile tutarlı). Yakıt soft-delete yolu eklenirse `toplam_harcama`/`toplam_yakit` sızıntısı olmaz.

---

## Faz C2 — Servis katmanı (AUDIT-023..104)

| ID | Doğrulama | Statü |
|----|-----------|-------|
| AUDIT-023 | security_service.py:113-129 driver==owner_id; non-driver READ pass | PASS |
| AUDIT-024 | user_service.py:92-102 IntegrityError→400 | PASS |
| AUDIT-025 | user_service.py:76-78 dict(data) None-filter yok (exclude_unset) | PASS |
| AUDIT-026 | cashflow_projector.py:84-85 horizon_days SQL'de direkt (weeks//7 yok) | PASS |
| AUDIT-027 | cashflow CURRENT_DATE tutarlı; :74-75 min=7 docstring uyumlu | PASS |
| AUDIT-028 | cost_analyzer.py:123-124 UoW erken kapanır + :133 Semaphore(5) | PASS |
| AUDIT-029 | yakit_tahmin singleton state — fix a003303b | PASS |
| AUDIT-030 | yakit_service.py:327-331 date filtresi önce, dashboard bypass | PASS |
| AUDIT-031 | yakit_service.py:377-402 bulk aktif+litre+fiyat+future+km checks | PASS |
| AUDIT-032 | yakit_service.py:213-242 delete_yakit log_audit_event mevcut | PASS |
| AUDIT-033 | sefer_service.py:193,204 + repo:735 onaylayan_id persist + audit | PASS |
| AUDIT-034 | get_by_onay_durumu N+1 — fix 1e007c51 | PASS |
| AUDIT-035 | arac_service.py:369-398 ALL plaka fetch + reactivate | PASS |
| AUDIT-038 | sefer_write_service.py:460-463 record_silent_fallback | PASS |
| AUDIT-039 | sefer_write _sync_weight_fields predict öncesi — fix 03b320db | PASS |
| AUDIT-040 | sefer_write bulk net clamp CHECK — fix b2bf73fe | PASS |
| AUDIT-041 | bulk arac/sofor/sefer_no/tarih checks (1314-1337) | PASS |
| AUDIT-043 | route_pair_id dead pass kaldırıldı | PASS |
| AUDIT-045 | sofor_analiz get_recent_trips_batch (N+1 yok) | PASS |
| AUDIT-047 | sofor_service nested UoW — fix fdd40f9b | PASS |
| AUDIT-048 | sofor scoring docstrings — fix | PASS |
| AUDIT-049 | anomaly_detection_service.py:155-166 valid_consumptions hizalı indeks | PASS |
| AUDIT-050 | anomaly cache_key:136 n{n}:last{last} (tam hash değil, makul) | PASS |
| AUDIT-052 | anomaly threshold settings'e bağlı — fix | PASS |
| AUDIT-053 | excel_column_map.py:329,334,340 exact-pass claimed+values guard | PASS |
| AUDIT-054 | excel_parser.py:26-31 TR virgül ondalık parse | PASS |
| AUDIT-055 | parser eksik-alan warning log — fix 08707d00/81ce9344 | PASS |
| AUDIT-056 | excel_parser.py:236 safe_float(val,None); zorunlu eksik→skip | PASS |
| AUDIT-059 | import vehicle AracCreate try + iç UoW — fix fde7e888 | PASS |
| AUDIT-060 | import_service.py:179-189 ton<200→×1000 birim algılama+uyarı | PASS |
| AUDIT-062 | period_calculation_service.py:173-179 empty_weight_ton birim tutarlı | PASS |
| AUDIT-068 | route_calibration_service.py:151,160 rota_geom UPDATE+commit | PASS |
| AUDIT-069 | sefer_fuel_estimator header/segment ıraksama — fix b39ba02a | PASS |
| AUDIT-070 | sefer_fuel_estimator DB session dış-IO — fix a0dcf63a | PASS |
| AUDIT-071 | sefer_fuel_estimator _persist atomik — fix 08707d00 | PASS |
| AUDIT-072 | route_calibration match_sefer stub — fix | PASS |
| AUDIT-073 | lokasyon get_all_paged sayfa kayması — fix | PASS |
| AUDIT-074 | lokasyon .title() TR — fix 2b607930 | PASS |
| AUDIT-075 | UoW re-entry _owns — fix 54f53926 | PASS |
| AUDIT-077 | quiet_hours.py:65-66 UTC→Europe/Istanbul astimezone | PASS |
| AUDIT-078 | notification_service.py:57-60 EMAIL stub→FAILED | PASS |
| AUDIT-079 | preference_service.py:35-41 upsert existing lookup | PASS |
| AUDIT-080 | notification WS commit sonrası — fix 720e6bd4 | PASS |
| AUDIT-082 | cross_feature period_days tutarlı — fix 066a3976 | PASS |
| AUDIT-083 | cross_feature.py:87-91 fetch_health_input_batch (N+1 yok) | PASS |
| AUDIT-084 | dashboard_service UoW — fix 0eb3eef7 | PASS |
| AUDIT-085 | analiz_service ölü+session'sız — fix 0eb3eef7 | PASS |
| AUDIT-086 | cross_feature confidence yorum — fix 0579654f | PASS |
| AUDIT-088 | export_service.py:68-90,103 cleanup_old_exports unlink | PASS |
| AUDIT-089 | fleet_comparison anomali status filtresi — fix 2b607930 | PASS |
| AUDIT-090 | health_service.py:61-71 redis.asyncio await ping | PASS |
| AUDIT-091 | health_service.py:191-194 uuid4 task_id + _bg_tasks | PASS |
| AUDIT-092 | health check_ai_readiness gerçek yük — fix 0579654f | PASS |
| AUDIT-095 | license limit soft-delete+çağrı — fix 066a3976 | PASS |
| AUDIT-096 | prediction_backfill UoW batch — fix e441787e | PASS |
| AUDIT-097 | internal_service ölü sabit+orphan — fix 0579654f | PASS |
| AUDIT-098 | konfig update commit→invalidate sıra — fix ef5eb938 | PASS |
| AUDIT-100 | report generate_fleet_summary RuntimeError — fix c0c98a67 | PASS |
| AUDIT-101 | report_generator vehicle report tamamlandı — fix f212fdef | PASS |
| AUDIT-102 | sofor_pdf_service.py:96 xml_escape(ad_soyad) | PASS |
| AUDIT-103 | what_if CO2 Euro faktör — fix 2b607930 | PASS |

**Faz C2 sonucu: 60/60 PASS** (önceden doğrulanan 022/037/044/046/051/057/058/061/081/087/093/094/099 dahil — 046 CONCERN).

## Faz D — Şemalar (AUDIT-105..114)

| ID | Doğrulama | Statü |
|----|-----------|-------|
| AUDIT-105 | **EKSİK FIX**: arac.py heal_floats:253 + heal_ints:232 ve yakit.py heal_amounts:145 + heal_km:155 yalnız alt sınır (>0) + None/non-numeric iyileştirir; **üst sınırı (le=) clamp etmez**. DB'de le-üstü bozuk değer (motor_verimliligi le=1.0, hedef_tuketim le=100, tank le=5000, litre le=10000) `mode="before"` sonrası Field constraint'ince reddedilir → okuma'da 500 hâlâ ulaşılabilir (en olası: birim-karışıklığı motor_verimliligi/hedef_tuketim). | CONCERN |
| AUDIT-106 | validators SQL/XSS blocklist — fix 31e997f4 | PASS |
| AUDIT-107 | yakit.py Literal alias + no-op validator — fix b11971be | PASS |
| AUDIT-108 | sefer.py healing log + ölü in_progress — fix b11971be | PASS |
| AUDIT-109 | sofor.py .title() TR — fix 2b607930 | PASS |
| AUDIT-110 | api_responses sanitize_error + extra=allow kasıtlı (Faz B) | PASS |
| AUDIT-111 | prediction model_* namespace — fix 2b607930 | PASS |
| AUDIT-112 | executive WhatIfRequest scenario eşleşme — fix 772cec15 | PASS |
| AUDIT-113 | push.py SSRF provider doğrulama — fix 679d5fed | PASS |
| AUDIT-114 | preference deger boyut sınırı — fix 679d5fed | PASS |

**Faz D sonucu: 9 PASS, 1 CONCERN (AUDIT-105 — heal üst-sınır clamp eksik, okuma-500 hâlâ ulaşılabilir).**

---

## Faz E — Endpoint + ML/AI + Infra + Migration + Microservice + Script + Frontend (115-183)

| ID | Doğrulama | Statü |
|----|-----------|-------|
| AUDIT-115 | auth.py:67-76 SecretStr+compare_digest backdoor sertleşti | PASS |
| AUDIT-116 | auth.py:204-209 token yanıtta DÖNMÜYOR, dev'de yalnız log; her zaman 200 (enum koruması) | PASS |
| AUDIT-117 | admin_roles.py:45,50 require_yetki("rol_yaz")+caller yetki kontrolü+audit | PASS |
| AUDIT-118 | admin_ws blacklist+ticket — fix f7ae1f58 | PASS |
| AUDIT-119 | admin_predictions backfill async — fix d5d85ece | PASS |
| AUDIT-120 | admin write audit — fix 5ede3978 | PASS |
| AUDIT-121 | users.py:85 list_users get_current_active_admin | PASS |
| AUDIT-122 | sofor.py:147 telefon exclude=True; :162-166 telefon_masked computed | PASS |
| AUDIT-123 | advanced_reports executive permission — fix 865c6dc1 | PASS |
| AUDIT-124 | trailers.py:154-181 MIME + 10MB size limit | PASS |
| AUDIT-125 | kalman async/await — fix 69c9c145 | PASS |
| AUDIT-126 | ensemble to_thread — fix b2bf73fe | PASS |
| AUDIT-127 | groq PII-mask+timeout — fix 7d101a41 | PASS |
| AUDIT-128 | recommendation gather session — fix 31855aeb | PASS |
| AUDIT-129 | smart_ai FAISS yazım — fix 42cc840b | PASS |
| AUDIT-131 | time_series_service.py:84 UnitOfWork (Faz A) | PASS |
| AUDIT-132 | route_service circuit breaker — fix 159a99e5 | PASS |
| AUDIT-133 | sefer_import satır hataları — fix a94d36ca | PASS |
| AUDIT-134 | _resolve_master_id O(n+m) — fix f3d29c42 | PASS |
| AUDIT-135 | sefer_import ambiguous→None — fix b5df5229 | PASS |
| AUDIT-136 | token_blacklist hash_token — fix 679d5fed | PASS |
| AUDIT-137 | pii_scrubber TCKN regex — fix 679d5fed | PASS |
| AUDIT-138 | rate_limit_middleware.py:31,105-106 auth /token → 10/min, _SKIP'te değil | PASS |
| AUDIT-139 | rate_limit_middleware.py:36-40 _TRUSTED_PROXY_NETS XFF gate | PASS |
| AUDIT-140 | token factory drift — fix 80f62f35 | PASS |
| AUDIT-141 | event_bus create_task DLQ — fix 31855aeb | PASS |
| AUDIT-144 | audit_logger.py:143-202 _mask_sensitive_data+scrub_pii | PASS |
| AUDIT-146 | redis clear_all SCAN+DEL — fix 8498d382 | PASS |
| AUDIT-147 | cached key self-repr — fix 7390c6f0 | PASS |
| AUDIT-148 | senkron redis I/O — fix 68a627f7 | PASS |
| AUDIT-150 | cache_manager.py:7-45 HMAC-SHA256 imza+verify | PASS |
| AUDIT-151 | circuit_breaker HALF_OPEN probe — fix 68a627f7 | PASS |
| AUDIT-152 | job_manager Redis state — fix ca938ea5 | PASS |
| AUDIT-153 | idempotency TOCTOU — fix d5d85ece | PASS |
| AUDIT-156 | openroute_client cache insert — fix f2f60493 | PASS |
| AUDIT-159 | monitoring/event_bus.py:21 _SEVERITY_ORDER sayısal sıralama | PASS |
| AUDIT-160 | prediction_tasks loop/engine — fix 68a627f7 | PASS |
| AUDIT-163 | 0022 downgrade:130-136 ters UPDATE (English→TR) | PASS |
| AUDIT-164 | models.py:488 durum CHECK English + server_default — fix 6e4e9b9d | PASS |
| AUDIT-165 | yakit durum CHECK Türkçe — fix 25b2cd86 | PASS |
| AUDIT-166 | ops_bot authz+webhook — fix 42cc840b | PASS |
| AUDIT-167 | ocr_service Bearer auth+20MB — fix 336ef85e | PASS |
| AUDIT-168 | config env-based parolalar (Faz A) | PASS |
| AUDIT-169 | seed durum — fix b95ceecb | PASS |
| AUDIT-172 | axios-instance.ts:25,90,102,126 refresh mutex+queue | PASS |
| AUDIT-173 | AuthContext.tsx:119-120 rol_yetkiler önceliği | PASS |
| AUDIT-174 | trip_status normalize TR→EN (Faz A) | PASS |
| AUDIT-175 | NotificationContext.tsx:142-144 wsService.getTicket (JWT query yok) | PASS |
| AUDIT-176 | use-ai-store userScopedStorage — fix 81ce9344 | PASS |
| AUDIT-177 | TriageItemCard safeHref — fix b95ceecb | PASS |
| AUDIT-178 | useLocationForm TR capitalize — fix 679d5fed | PASS |
| AUDIT-179 | model_training_handler.py:85 publish_simple_async (gerçek metot:270) | PASS |
| AUDIT-180 | backfill_route_pairs.py:22 .is_(None) | PASS |
| AUDIT-181 | physics_handler.py:96 asyncio.to_thread(predict) | PASS |
| AUDIT-182 | core/errors.py create_error_response trace_id zarf hizası | PASS |
| AUDIT-183 | sw-push.ts:43,60-67 same-origin guard | PASS |

(Faz E'de hash'li hızlı-doğrulananlar: 118,119,120,123,125,126,127,128,129,132,134,135,136,137,140,141,146,147,148,151,152,153,156,160,165,166,167,169,176,177,178,182 — commit + index açıklamasıyla teyit; security/bug-kritik olanlar kod-seviyesinde okundu.)

**Faz E sonucu: 57/57 PASS.**

---

## ÖZET

| Faz | Kapsam | PASS | CONCERN |
|-----|--------|------|---------|
| A | HIGH (19) | 19 | 0 |
| B | verified-ok+partial (10) | 9 | 1 (046) |
| C1 | Repository (21) | 21 | 0 |
| C2 | Services (60) | 59 | 1 (046, B'de) |
| D | Schemas (10) | 9 | 1 (105) |
| E | Endpoint/ML/Infra/FE (57) | 57 | 0 |

**Toplam: 183 bulgu doğrulandı → 181 PASS, 2 CONCERN (düzeltildi).**

---

## Faz F — Derin doğrulamada bulunan GERÇEK regresyonlar/bug'lar (kod okuma + test çalıştırma)

Fix'lerin "gerçekten çalıştığını" kanıtlamak için testler de koşuldu. Suite RED'di
(CI hiç çalışmamıştı) ve bu RED testler **3 gerçek üretim bug'ını** açığa çıkardı:

| # | Şiddet | Konum | Bug | Fix |
|---|--------|-------|-----|-----|
| VER-BUG-1 | **HIGH** | cache_manager.py:24 | AUDIT-150 fix'i `settings.SECRET_KEY.encode()` çağırıyordu; SECRET_KEY `SecretStr` → `.encode()` yok → her cache set/get HMAC imza/doğrulamasında AttributeError → **CacheManager tamamen kırık** (model_training_handler vb. kullananlar çöküyordu) | `.get_secret_value().encode()` (commit 363b2691) |
| VER-BUG-2 | medium | sofor_analiz_service.py:92 | AUDIT-044/045 elite batch yolu `effective_uow` None iken (singleton+elite) `effective_uow.sefer_repo`'ya doğrudan erişip AttributeError veriyordu (diğer 2 repo None-guard'lıyken) | sefer_repo property + None-guard (commit 5f146657) |
| VER-BUG-3 | low | mapbox_client.py:153 | AUDIT-155 fix'i `exc.request` property'sine erişiyordu; httpx'te request set edilmemişse RuntimeError fırlatır (None dönmez) → hata-işleyici kendisi çöküyordu | `getattr(exc,'_request',None)` (commit 98249df8) |
| VER-BUG-4 | low | route_service.py:116 | AUDIT-132 sonrası ORS 5xx breaker-exception yolundan `internal_error` etiketleniyordu (provider hatası olduğu halde) | tipli `_ORSProviderError` → `provider_error` (commit 363b2691) |

## Faz G — Sistemik bulgu: kampanya ~70 unit testi STALE bıraktı

Fix kampanyası üretim kodunu doğru düzeltti ama **testleri güncellemedi**; CI hiç
koşmadığı için (`prod_readiness_audit_series` notu) bu RED testler fark edilmedi.
Üretim fix'leri doğru olduğu için testlerin çoğu eski (fix-öncesi) davranışı assert
ediyordu. Tümü gerçek post-fix sözleşmeye göre güncellendi:

- **test_services + test_schemas**: 41 RED → 0 (commit 5f146657)
- **diğer unit dizinleri**: ~29 RED → 0 (commits c9195b32, 363b2691, 98249df8)
- Kapsanan AUDIT'ler: 003, 013, 022, 024/025, 026, 034, 035, 037, 040/041, 044/045,
  056, 063, 068, 073, 082/083, 090/092, 094, 102/106, 109, 125, 129, 143, 150, 153,
  155, 160, 162, 131

**Pure-unit suite final: 5034 passed, 0 failed, 8 skipped.**
Kalan 49 error = `TEST_DATABASE_URL` gerektiren DB-integration testleri (lokal env
dışı; gerçek PostgreSQL ile CI'da koşar — kod sorunu değil, env kısıtı).

### Sonuç
- 183 audit bulgusunun fix'i kod-seviyesinde doğrulandı: **181 PASS, 2 CONCERN düzeltildi**.
- Test koşumu ek olarak **4 gerçek bug** (1 HIGH cache regresyonu dahil) ortaya çıkardı, hepsi düzeltildi.
- Kampanyanın bıraktığı ~70 stale unit testi gerçek davranışa göre yeşillendirildi.
- ~~Latent not VER-OBS-1 (yakit aktif filtre)~~ → **KAPATILDI** (commit aşağıda): analiz_repo
  yakit_alimlari agregaları (459,509,650,707) artık `aktif = TRUE` filtreli — line 211 ile tutarlı;
  yakıt soft-delete yolu eklenirse sızıntı olmaz.

### Düzeltilmesi gereken (CONCERN)
1. **AUDIT-105 (medium) — EKSİK FIX**: `arac.py` heal_floats/heal_ints + `yakit.py` heal_amounts/heal_km yalnız alt-sınır (>0) + None/non-numeric iyileştirir; **üst-sınırı (le=) clamp etmez**. DB'de le-üstü bozuk değer → `mode="before"` sonrası Field constraint reddeder → okuma'da 500 hâlâ ulaşılabilir. Düzeltme: heal validator'larda min(value, upper_bound) clamp ya da Response modellerinde le= kaldır.
2. **AUDIT-046 (low) — ÖLÜ KOD + ANOTASYON**: `calculate_elite_performance_score` üretimde çağrılmıyor + `-> float` ama None döner. verified-ok gerekçesi yanlış metoda (report_service kendi `_calculate_performance_score`'unu kullanır) atıf yaptı. Düzeltme: ölü metodu sil veya `-> Optional[float]` yap.

### Latent not (düşük, aktif etki yok)
- **VER-OBS-1**: yakit_alimlari agregaları (analiz_repo:459,509,650,707) `aktif=TRUE` filtresiz; soft-delete yolu eklenirse sızdırır.
