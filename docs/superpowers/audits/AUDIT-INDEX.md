# AUDIT-INDEX — Bulgu Özeti

Şiddet yalnız düzeltme sırası içindir; kullanıcı kuralı gereği **her bulgu kritiktir**.

| ID | Şiddet | Sınıf | Konum (dosya:satır) | Başlık | Durum |
|----|--------|-------|---------------------|--------|-------|
| AUDIT-001 | medium | bug/dead-code | base_repository.py:415 | execute_query rollback dalı ölü + ters mantık | fixed 49c3be89 |
| AUDIT-002 | low | dead-code | base_repository.py:281-290 | update() no-op ifade + stale yorum bloğu | fixed |
| AUDIT-003 | medium | silent-failure | base_repository.py:398-403 | count() exception yutup 0 döndürüyor | fixed 49c3be89 |
| AUDIT-004 | low | silent-failure | base_repository.py:234,253 | create/bulk_create bilinmeyen alanı sessizce düşürüyor | fixed |
| AUDIT-005 | medium | concurrency/dead-code | main.py:296,42 | warm-up task referanssız create_task; _bg_tasks ölü | fixed 49c3be89 |
| AUDIT-006 | medium | security | main.py:337-347 | /metrics IP guard reverse-proxy arkasında baypas | fixed d3d6d05b |
| AUDIT-007 | medium | data-integrity | entities/models.py:129 ↔ models.py:78 | Arac.yil entity zorunlu / ORM nullable → okuma 500 | fixed 2e9737d2 |
| AUDIT-008 | low | data-integrity | models.py:874,878,649,1206,665 | kullanıcı/ref id kolonları FK'sız | fixed: model FK + migration 0028 NOT VALID (mevcut veri doğrulanmaz; VALIDATE CONSTRAINT manuel çalıştırılmalı) |
| AUDIT-009 | low | arch-drift | init_db.py:22 | Base.metadata.create_all (prod'da çağrılmıyor) | fixed |
| AUDIT-010 | low | consistency | entities/models.py:242,380 | create-DTO vs read-entity validasyon sınırı çelişiyor | fixed |
| AUDIT-011 | medium | concurrency | unit_of_work.py:186-196 | UoW commit()/rollback() _owns kontrol etmiyor | fixed d3d6d05b |
| AUDIT-012 | high | bug/domain-rule | sefer_repo.py:220-228 | get_cost_leakage_stats yakıt kartezyen join → yanlış maliyet | fixed de38a583 |
| AUDIT-013 | medium | silent-failure | sefer_repo.py:683-707 | refresh_stats_mv autocommit etkisiz → CONCURRENTLY sessiz fallback | fixed d3d6d05b |
| AUDIT-014 | low | dead-code | sefer_repo.py:474-480 | get_trip_stats kullanılmayan base sorgusu | fixed |
| AUDIT-015 | medium | data-integrity | arac_repo:106,238; sofor_repo:220,241; analiz_repo:459,507,707 | soft-delete/aktif filtre tutarsızlığı → silinmişler agregaya sızıyor | fixed 31e997f4 |
| AUDIT-016 | medium | domain-rule/bug | yakit_repo.py:196-199 | update_yakit float toplam_tutar + kısmi güncellemede bayat toplam | fixed ea5c5cd4 |
| AUDIT-017 | medium | bug/dead-code | session_repo.py:32 | if not self.session ters/ölü kontrol (AUDIT-001 tekrarı); dead `if session:` + UoW bypass `commit()` | fixed 49c3be89 (ters mantık); re-fixed 81ce9344 (dead code + UoW bypass → flush) |
| AUDIT-018 | high | bug/silent-failure | admin_config_repo.py:43-62 | update_value flush öncesi refresh() → konfig değişikliği sessizce kaybolur | fixed d3d6d05b |
| AUDIT-019 | low | bug/consistency | notification_repository.py:68,87; maintenance_repository.py:37 | naive datetime.now() tz-aware kolonlara | fixed 2a064f56 |
| AUDIT-020 | low | bug | model_versiyon_repo.py:46-57 | activate kötü version_id'de aracı aktif versiyonsuz bırakır | fixed 2b607930 |
| AUDIT-021 | medium | silent-failure | analiz_repo.py:198,240,401,325 | analitik sorgular exception yutup default dönüyor | fixed c57318d5 |
| AUDIT-022 | high | security | auth_service.py:228-240 ↔ kullanici_repo.py:32 | parola sıfırlama token'ı düz metin saklanıyor (hash'siz) | fixed 53c91f01 |
| AUDIT-023 | medium | security/api-design | security_service.py:99-117 ↔ sefer_read_service.py:40 | verify_ownership owner_id'yi kontrol etmiyor → sahte izolasyon | fixed c7acea1e |
| AUDIT-024 | medium | error-handling | user_service.py:69-90 | update_user IntegrityError yakalamıyor → 500 (create 400 dönerken) | fixed 6c3d1907 |
| AUDIT-025 | low | data-integrity | user_service.py:76 | update_user None-filtresi nullable alanı NULL'a çekmeyi engelliyor | fixed 772cec15 |
| AUDIT-026 | medium | domain-rule/financial | cashflow_projector.py:145,152 | horizon artık günleri düşüyor → grand_total eksik sayıyor | fixed 1a8414d3 |
| AUDIT-027 | low | consistency/doc | cashflow_projector.py:127,72 | date.today() vs CURRENT_DATE tz + docstring min uyumsuz | fixed 772cec15 |
| AUDIT-028 | medium | performance | cost_analyzer.py:120-163 | get_vehicle_cost_comparison N eşzamanlı UoW + atıl dış transaction | fixed 03b320db |
| AUDIT-029 | medium | concurrency | yakit_tahmin_service.py:27,116-124 | singleton paylaşılan mutable model state (kırılgan eşzamanlılık) | fixed a003303b |
| AUDIT-030 | medium | silent-failure | yakit_service.py:307-327 | get_stats dashboard yolunda tarih filtrelerini yok sayıyor | fixed 2824d724 |
| AUDIT-031 | medium | data-integrity | yakit_service.py:336-393 | bulk_add_yakit tekil add'in doğrulamalarını baypas ediyor | fixed 7eb7bb82 |
| AUDIT-032 | medium | audit-gap | yakit_service.py:211-233 | delete_yakit finansal hard-delete + @audit_log yok | fixed (log_audit_event already present) |
| AUDIT-033 | medium | audit-gap | sefer_service.py:188-213 | onaylayan_id DB'ye yazılmıyor (yalnız log) + audit yok + atomik değil | fixed 9ec8c84a |
| AUDIT-034 | low | performance | sefer_service.py:215-225 | get_by_onay_durumu N+1 (zaten dolu satırları yeniden çekiyor) | fixed 1e007c51 |
| AUDIT-035 | medium | consistency | arac_service.py:357-402 | bulk_add_arac pasif-plaka çakışmasında batch çöker + reaktivasyon yok | fixed 95e6eaee |
| AUDIT-036 | low | concurrency | arac_service.py:47,94,177 | asyncio.Lock süreç-yerel → çok-worker'da etkisiz + darboğaz | verified-ok: plaka kolonunda DB UNIQUE constraint (models.py:75) gerçek güvenlik ağı; lock tek-süreç eş-zamanlılığı için yeterli |
| AUDIT-037 | high | data-integrity | sefer_analiz_service.py:59-96 | reconcile_costs yakıt=0 günde tüketimi 0'a eziyor (kalıcı veri kaybı — review §3 ile high'a yükseltildi) | fixed f643b887 |
| AUDIT-038 | medium | observability | sefer_write_service.py:561-567 | legacy predict timeout fallback record_silent_fallback ile kaydedilmiyor | fixed a0dcf63a |
| AUDIT-039 | medium | domain-rule/ordering | sefer_write_service.py:851,856,546 | tahmin ağırlık-sync'ten önce → dolu/boş-only veride ton=0 tahmin | fixed 03b320db |
| AUDIT-040 | medium | data-integrity | sefer_write_service.py:1374-1394 | bulk net clamp CHECK kısıtını ihlal eder (dolu<bos) → batch çöker | fixed b2bf73fe |
| AUDIT-041 | medium | consistency | sefer_write_service.py:1233-1421 | bulk_add_sefer arac/sofor aktif + sefer_no dup + tarih doğrulamasını baypas | fixed 407ffe5b |
| AUDIT-042 | low | silent-behavior | sefer_write_service.py:1324 | bulk >20 batch'te tahmini sessizce atlıyor (keyfi eşik) | verified-ok: INFO log zaten var (L1388-1391); geçmiş veri import'u için kasıtlı tasarım |
| AUDIT-043 | low | dead-code | sefer_write_service.py:782-784 | route_pair_id resolve boş pass placeholder (eksik özellik) | fixed |
| AUDIT-044 | high | concurrency | sofor_analiz_service.py:92-98,326 | uow-bağlı paralel elite gather aynı AsyncSession'ı eşzamanlı kullanıyor + self._uow sızıntısı | fixed 01255460 (gather→serial); re-fixed 81ce9344 (self._uow mutation→effective_uow local) |
| AUDIT-045 | medium | performance | sofor_analiz_service.py:85-98,330 | elite-score yolu masif N+1 ("N+1 yok" iddiasıyla çelişik) | fixed 066a3976 |
| AUDIT-046 | low | dead-code | sofor_analiz_service.py:386-419 | calculate_performance_score ölü + None döner (-> float) | fixed 5f146657 (doğrulama: `calculate_elite_performance_score` -> Optional[float] düzeltildi; gerekçe yanlış metoda atıf yapıyordu — bkz AUDIT-VERIFICATION Faz B) |
| AUDIT-047 | medium | transaction | sofor_service.py:232-260 | calculate_hybrid_score dış UoW+lock içinde kendi UoW'sunu açıyor (iç içe) | fixed fdd40f9b |
| AUDIT-048 | medium | consistency | sofor_service + sofor_analiz | üç uyumsuz şoför puanlama ölçeği (hangisi otoriter belirsiz) | fixed: docstrings her metodun ölçeği+amacını açıklıyor; değerler kasıtlı farklı (ML factor vs dashboard vs raporlar) |
| AUDIT-049 | medium | bug | anomaly_detection_service.py:134,141-143 | NaN-filtreli anomali indeksleri orijinal listeye uygulanıyor (indeks kayması) | fixed 4affb9dd |
| AUDIT-050 | low | caching | anomaly_detection_service.py:119-128 | cache yalnız arac_id ile anahtarlı (girdi yok) → bayat/çapraz sonuç | fixed 720e6bd4 |
| AUDIT-051 | high | ml-correctness | anomaly_detector.py:438-456 | train_lgb var-olmayan İngilizce kolon adı okuyor → tüm öznitelikler dejenere (ML çöp) | fixed 444f5c30 |
| AUDIT-052 | medium | arch-duplication | anomaly_detector vs anomaly_detection_service | iki örtüşen anomali alt-sistemi ıraksak eşik mantığı | fixed: eşik settings.ANOMALY_Z_THRESHOLD'a bağlandı; class docstring iki sistemin farkını belgeler (istatistiksel/in-memory vs ML/DB-persist) |
| AUDIT-053 | medium | data-mapping | excel_column_map.py:332-341 | exact-pass aynı internal_key'e birden fazla kolon bağlayabiliyor | fixed b39ba02a |
| AUDIT-054 | medium | i18n/data-integrity | excel_parser.py:42-51,97-107 | Türkçe virgüllü ondalık sayı sessizce 0'a çevriliyor | fixed 988ba384 |
| AUDIT-055 | medium | silent-failure | excel_parser.py:63,111,146,201,238,294 | tüm parser'lar eksik-alan satırları sessizce düşürüyor (sebep raporu yok) | fixed 08707d00 (sefer/yakit/route); re-fixed 81ce9344 (vehicle/driver parser'lar da warning log) |
| AUDIT-056 | medium | data-integrity | excel_parser.py:188-197 | araç parser sihirli default uyduruyor (bos=8000, hedef_tuketim=0.38) | fixed 08707d00 |
| AUDIT-057 | high | bug | import_service.py:380,457 | yakıt import/rollback YANLIŞ tablo adı (yakit_alimlar, gerçek yakit_alimlari) | fixed a589849d |
| AUDIT-058 | high | bug | import_service.py:138,146,160,217 | _validate_import_rows mapping'i ters yönde kullanıyor olabilir → satırlar None | fixed a003303b |
| AUDIT-059 | medium | error-handling | import_service.py:697-732 | vehicle import AracCreate list-comp tek kötü satırda tüm import düşer + iç içe UoW | fixed fde7e888 |
| AUDIT-060 | medium | data-integrity | import_service.py:173-210 | sefer import bos=0 + birim-belirsiz Yük→dolu_agirlik (ton kg gibi) | fixed c0c98a67 |
| AUDIT-061 | high | silent-failure | period_calculation_service.py:269-283 | recalc depo_durumu taşımıyor → hiç periyot üretmiyor (özellik sessiz ölü) | fixed b07c4608 |
| AUDIT-062 | medium | domain-rule | period_calculation_service.py:171-180 | kg boş-ağırlık + ton yük karışık → Ton-Km dağıtım ~Km'ye dejenere | fixed f2f60493 |
| AUDIT-063 | medium | performance | ai_service.py:131-164,215 | _predictor_cache hiç invalidate edilmiyor + fit/predict event loop'ta senkron (bloke) | fixed 69c9c145 |
| AUDIT-064 | medium | security | ai_service.py:100-106 | stream_response _sanitize_prompt'u baypas + redaksiyon listesi yetersiz | fixed 69c9c145 |
| AUDIT-065 | medium | concurrency | ml_service.py:21,32-35 | _locks sınıf-düzeyi dict oluşturması racy + süreç-yerel + sınırsız büyüme | fixed 80f62f35 |
| AUDIT-066 | medium | bug | weather_service.py:237-248 | get_trip_impact_analysis boş daily dizilerinde IndexError çöker | fixed 3a96ea93 |
| AUDIT-067 | medium | silent-fabrication | openroute_service.py:82-107 | offline fallback sentetik mesafe/yükseklik uyduruyor (gerçek/offline bayrağı yok) | fixed f2f60493 |
| AUDIT-068 | medium | silent-failure | route_calibration_service.py:149-154 | calibrate Lokasyon.rota_geom dict mutasyonu → sessiz no-op (kalıcı olmaz) | fixed d5d85ece |
| AUDIT-069 | medium | data-integrity | sefer_fuel_estimator.py:233-246,495 | header total_l (düzeltilmiş) vs segment sim_l_total (salt-fizik) ıraksıyor | fixed b39ba02a |
| AUDIT-070 | medium | performance | sefer_fuel_estimator.py:182-279 | DB oturumu tüm dış-IO (Mapbox+Open-Meteo) boyunca açık/atıl → pool tükenmesi | fixed a0dcf63a |
| AUDIT-071 | medium | transaction | sefer_fuel_estimator.py:443-506 | _persist bağımsız oturumda commit → orphan simülasyon + sefer ile atomik değil | fixed 08707d00 |
| AUDIT-072 | low | dead-code | route_calibration_service.py:50-104 | match_sefer_to_path hiç uygulanmamış stub; docstring spatial analiz iddia ediyor | fixed |
| AUDIT-073 | low | consistency | lokasyon_service.py:280-290 | get_all_paged validasyon-düşen satırları atlıyor ama total sayıyor (sayfa kayması) | fixed |
| AUDIT-074 | low | i18n | lokasyon_service.py:164-165 | add_lokasyon .title() Türkçe i'yi bozuyor (saklanan görünen ad) | fixed 2b607930 |
| AUDIT-075 | medium | concurrency | route_calibration_service.py ↔ unit_of_work.py:124-137 | UoW aynı-instance re-entry _owns'u siler → owner çıkışı oturum/token sızdırır (latent) | fixed 54f53926 |
| AUDIT-076 | high | silent-failure | push_sender.py:120-136,164-198 | kendi-UoW yolunda commit yok → ghost rollback → 410-temizliği + last_used_at kaybolur | fixed 58f632a1 |
| AUDIT-077 | medium | timezone | quiet_hours.py:59 | UTC saati kullanıcı-yerel HH:MM sessiz aralığıyla karşılaştırılıyor → ~3s kayma | fixed 54f53926 |
| AUDIT-078 | medium | silent-failure | notification_service.py:62,100-101 | EMAIL kanalı log-only stub ama durum=SENT → asla teslim edilmiyor | fixed 9b2e03f6 |
| AUDIT-079 | medium | data-integrity | preference_service.py:35-64 | save_preference 'sutun' dışı tiplerde upsert yerine yeni satır → duplikat birikimi | fixed d549674c |
| AUDIT-080 | low | transaction | notification_service.py:68-103 | WS push commit'ten önce + açık transaction içinde network I/O | fixed 720e6bd4 |
| AUDIT-081 | high | data-integrity | attribution_service.py:32-80 ↔ admin_attribution.py:76-104 | bulk override paylaşılan UoW commit() latch → yalnız ilk satır kalıcı, hepsi success+event | fixed f5138175 |
| AUDIT-082 | medium | domain-rule | cross_feature_aggregator.py:106-142 | koçluk tasarrufu sürücü sayısını yok sayıyor + yıllık km vs period karışık | fixed 066a3976 |
| AUDIT-083 | medium | performance | cross_feature_aggregator.py:90-99 | D.4 araç-başı fetch_health_input → N+1 | fixed 873d116a |
| AUDIT-084 | medium | dead-code | dashboard_service.py:36-67 | DashboardService ölü (çağıran yok) + latent session'sız get_all + eşzamanlı gather | fixed (pending commit) |
| AUDIT-085 | medium | dead-code | analiz_service.py:132-244 | in-house stat metotları ölü + session'sız singleton repo çağrıları | fixed (pending commit) |
| AUDIT-086 | low | consistency | cross_feature_aggregator.py:21,57,181 | confidence/birim yorumları koddan sapmış (0.40 vs 0.55) | fixed 0579654f |
| AUDIT-087 | medium | security | excel_exporter.py:317; export_service.py:118,123 | Excel/CSV formül enjeksiyonu — kullanıcı string'leri sanitize edilmeden hücreye | fixed b57f108c |
| AUDIT-088 | low | resource-leak | export_service.py:129-132,312-314 | export dosyaları yerel diske birikiyor (temizlik yok) + çok-instance kırılgan | fixed 0579654f |
| AUDIT-089 | low | domain-rule | fleet_comparison.py:87-91 | "açık anomali" metriği status filtresiz → çözülmüşleri de sayıyor | fixed 2b607930 |
| AUDIT-090 | medium | concurrency | health_service.py:56-72 | check_redis senkron redis ping → event loop bloklar | fixed f5bab9db |
| AUDIT-091 | medium | bug | health_service.py:170-178 | trigger_manual_backup uydurma task_id + referanssız create_task | fixed 68a627f7 |
| AUDIT-092 | low | observability | health_service.py:82-86 | check_ai_readiness sabit model listesi (gerçek yük değil) | fixed 0579654f |
| AUDIT-093 | high | bug | maintenance_service.py:124-126 | get_upcoming_alerts tz-aware vs naive datetime → TypeError (endpoint 500) | fixed a57a14a4 |
| AUDIT-094 | high | silent-failure | insight_engine.py:36-39,129-130 | session'sız singleton get_analiz_repo → fleet insight sessiz ölü + save uncaught çöker | fixed dec1fa33 |
| AUDIT-095 | medium | domain-rule | license_service.py:88-119 | limit kontrolleri soft-delete sayıyor + hiç çağrılmıyor (ölü kapı) | fixed 066a3976 |
| AUDIT-096 | medium | performance | prediction_backfill_service.py:63-102 | UoW/bağlantı tüm batch (dış-IO + sleep) boyunca açık | fixed e441787e |
| AUDIT-097 | low | dead-code | internal_service.py:24-25,56-61 | upload sabitleri ölü/duplike + senkron yazım + orphan dosya | fixed 0579654f |
| AUDIT-098 | low | consistency | konfig_service.py:98-117 | update_config cache-invalide+publish repo self-commit'e bağlı (stale riski) | fixed |
| AUDIT-099 | high | concurrency | report_service.py:196-198,240-242 | paylaşılan session'da asyncio.gather → AsyncSession eşzamanlı op hatası (endpoint çöker) | fixed e8b38c3b |
| AUDIT-100 | low | consistency | report_service.py:281,283-291 | generate_fleet_summary tutarsız RuntimeError yakalama (analiz korumasız) | fixed c0c98a67 |
| AUDIT-101 | low | dead-code | report_generator.py:365-401 | generate_vehicle_report yarım stub (yalnız teknik kart) | fixed (pending commit) |
| AUDIT-102 | low | security | sofor_pdf_service.py:95 | ad_soyad reportlab Paragraph markup'ına escape'siz | fixed 1e007c51 |
| AUDIT-103 | low | domain-rule | what_if_engine.py:102-106 | fleet_renewal CO2 azaltımı Euro faktör farkı (yanlış metrik) | fixed 2b607930 |
| AUDIT-104 | low | domain-rule | triage_aggregator.py:291-296 | aktif sefer sayacı yalnız durum='Planned' (in-progress kaçabilir) | verified-ok: domain yalnız Planned/Completed/Cancelled; Planned=aktif |
| AUDIT-105 | medium | bug | arac.py:191-244; yakit.py:136-155 | Response heal_* değerleri field constraint'i ihlal ediyor → okuma'da 500 | fixed 85251507; **re-fixed 5f146657** (ilk fix yalnız alt-sınırı iyileştiriyordu; le= üst-sınır ihlali hâlâ 500 veriyordu — heal_floats/ints/amounts/km artık [gt,le] clamp eder) |
| AUDIT-106 | medium | validation-gap | validators.py:38-45 ↔ sefer/arac/yakit/sofor | SQL/XSS blocklist serbest-metni 422 reddediyor (+ tiyatro) | fixed 31e997f4 |
| AUDIT-107 | low | consistency | yakit.py:37-39,97,67-73 | durum Literal duplike Onaylandi/Onaylandı + Base↔Update tutarsız + no-op validator | fixed b11971be |
| AUDIT-108 | low | data-integrity | sefer.py:271-316,345-352 | SeferResponse agresif healing bozuk veriyi maskeliyor + ölü in_progress_count | fixed b11971be |
| AUDIT-109 | low | i18n | sofor.py:44-52 | sanitize_name .title() Türkçe İ/ı bozuyor | fixed 2b607930 |
| AUDIT-110 | low | security | api_responses.py:23-40,120,329,396 | response şemaları extra=allow + ham exception string sızıntısı | partial: error field sanitized; extra=allow intentional for provider fields |
| AUDIT-111 | low | maintainability | prediction.py:38,58,65,96 | model_* alanları Pydantic v2 korumalı namespace çakışması | fixed 2b607930 |
| AUDIT-112 | low | validation-gap | executive.py:55-61 | WhatIfRequest scenario_type↔input variant eşleşmesi doğrulanmıyor | fixed 772cec15 |
| AUDIT-113 | low | security | push.py:21-26 ↔ push_sender.py:48-56 | endpoint push-sağlayıcı doğrulaması yok → webpush blind SSRF | fixed 679d5fed |
| AUDIT-114 | low | validation-gap | preference.py:7-16 | deger: Any sınırsız → keyfi büyük JSON (DB bloat) | fixed 679d5fed |
| AUDIT-115 | high | security | auth.py:64-104 | süper admin env backdoor (düz-metin parola, RBAC baypas, revoke yok — review ile high'a yükseltildi) | fixed 2e96347a |
| AUDIT-116 | medium | security | auth.py:197-211 | password-reset-request non-prod'da token'ı yanıtta döndürüyor | fixed f492033b |
| AUDIT-117 | medium | security | admin_roles.py:40-52 | create_role keyfi-yetkili rol (priv-esc) + audit log yok | fixed f878a001 |
| AUDIT-118 | medium | security | admin_ws.py:67-132 | WS token query-param + blacklist yok + /training yetkisiz | fixed f7ae1f58 |
| AUDIT-119 | medium | performance | admin_predictions.py:13-23 | backfill inline limit≤500 → çok-dakikalık senkron istek | fixed d5d85ece |
| AUDIT-120 | low | audit-gap | admin_maintenance/ml/health/predictions/notifications | admin write/op endpoint'lerinde tutarsız audit | fixed |
| AUDIT-121 | medium | security | users.py:83-91 ↔ KullaniciRead | GET /users tüm dizini (email+yetkiler+IP) authenticated herkese açıyor | fixed f878a001 |
| AUDIT-122 | medium | security | drivers.py ↔ SoforResponse | ham telefon (PII) JSON yanıtta → telefon_masked kozmetik | fixed c9a57cf6 |
| AUDIT-123 | medium | security | advanced_reports.py:204-298 | finansal raporlar yalnız authn (executive permission-gated iken) | fixed 865c6dc1 |
| AUDIT-124 | medium | security | trailers.py:146-156; locations.py:454-465 | trailers+locations upload MIME/boyut doğrulaması yok (sınırsız upload) | fixed d05656bc |
| AUDIT-125 | medium | dead-code | kalman_estimator.py:271-349 | KalmanEstimatorService senkron metotlar async repo'yu await'siz çağırıyor + ölü | fixed 69c9c145 |
| AUDIT-126 | medium | concurrency | ensemble_service.py:143-200,305,572 | async metotlarda bloklayan ML (joblib.load/fit/predict) to_thread'siz → event loop bloke | fixed b2bf73fe |
| AUDIT-127 | medium | security | groq_service.py ↔ llm_client.py | iki LLM istemcisi tutarsız: GroqService PII-mask yok + timeout yok | fixed 7d101a41 |
| AUDIT-128 | medium | concurrency | recommendation_engine.py:295-320 | get_all_recommendations gather paylaşılan UoW session eşzamanlı + locksuz cache | fixed 31855aeb |
| AUDIT-129 | medium | performance | smart_ai_service.py:82 | KnowledgeBase her add'de tüm FAISS indeksini diske yazıyor + 1M cap'te sessiz öğrenme durması | fixed 42cc840b |
| AUDIT-130 | low | reliability | prediction_service.py:808 | _log_prediction_to_ai referanssız create_task (GC) + her tahminde KB yazımı | verified-ok: _bg_tasks set pattern zaten uygulanmış (L27, L830-831) |
| AUDIT-131 | high | bug | time_series_service.py:79-109 | TimeSeriesService session'sız get_analiz_repo → her train/predict/trend 503'e düşüyor (subsystem ölü, maskeli) | fixed 9598dcc1 |
| AUDIT-132 | low | robustness | route_service.py:83-310 | ORS yolunda circuit-breaker yok; outage'da istek başına ~15-30s asılı | fixed; **doğrulama 363b2691**: 5xx breaker-exception yolu `internal_error` yerine tipli `_ORSProviderError`→`provider_error` etiketlenir |
| AUDIT-133 | medium | error-handling | sefer_import_service.py:157-166 | bulk_add_sefer hatası import'u count=0 + jenerik hataya çökertir, satır hataları kaybolur | fixed a94d36ca |
| AUDIT-134 | low | performance | sefer_import_service.py:173-222 | _resolve_master_id satır×master kuadratik lineer tarama | fixed |
| AUDIT-135 | medium | data-integrity | sefer_import_service.py:179-191 | aynı adlı şoförde sefer sessizce yanlış şoföre bağlanır (ilk eşleşme) | fixed |
| AUDIT-136 | low | security | token_blacklist.py:33 | Redis blacklist anahtarı ham JWT (hash_token mevcutken kullanılmıyor) | fixed 679d5fed |
| AUDIT-137 | low | bug | pii_scrubber.py:28-32 | telefon regex 11-haneli TCKN'yi önce yakalıyor; TCKN pattern erişilemez + aşırı maskeleme | fixed 679d5fed |
| AUDIT-138 | medium | security | rate_limit_middleware.py:20-27 | login endpoint rate-limit dışı (brute-force sınırsız) | fixed (auth path ayrı 10 req/min limit; _SKIP_PATHS'ten çıkarıldı) |
| AUDIT-139 | medium | security | rate_limit_middleware.py:114-118 | rate-limit spoof'lanabilir X-Forwarded-For'a dayanıyor → per-IP bypass | fixed (X-Forwarded-For yalnız trusted RFC-1918+Docker proxy'den kabul edilir) |
| AUDIT-140 | medium | maintainability | core/security.py:41 vs jwt_handler.py:47 | iki token fabrikası drift (jti var/yok) | fixed 80f62f35 |
| AUDIT-141 | medium | reliability | event_bus.py:216-225 | publish() async handler create_task: loop yoksa yutulur, GC, coroutine exception DLQ'ya düşmez | fixed 31855aeb |
| AUDIT-142 | high | reliability | outbox_service.py:98-103 | relay handler hatasında bile processed=True + DLQ replay yok → reliable delivery kırık | fixed b8baf443 |
| AUDIT-143 | low | bug | event_bus.py:160-163 | bellek dedup eviction list(set)[-500:] rastgele tutar (set sırasız), en-yeni değil | verified-ok: kod zaten OrderedDict.popitem(last=False) FIFO kullanıyor |
| AUDIT-144 | medium | security | audit_logger.py:143-165 | log_audit_event old/new_value PII (telefon/tc_no/email) maskesiz admin_audit_log'a yazılıyor | fixed 7d101a41 |
| AUDIT-145 | low | reliability | outbox_service.py:62-67 | poison event (retry>=5) sonsuza dek processed=False, temizlik/DLQ yok → tablo şişer | verified-ok: AUDIT-142 düzeltmesinde processed=True zaten yapılıyor |
| AUDIT-146 | medium | security | redis_cache.py:211-222 | clear_all() flushdb → tüm Redis DB siler (blacklist/rate-limit/outbox/celery) | fixed (pending commit) |
| AUDIT-147 | medium | bug | redis_cache.py:265-302 | cached decorator key self-repr (bellek adresi) + json default=str tip drift | fixed 7390c6f0 |
| AUDIT-148 | medium | performance | redis_cache.py:274-285 + cache_invalidation.py:34-116 | senkron Redis I/O async context'te event loop bloklar | fixed 68a627f7 |
| AUDIT-149 | low | bug | redis_pubsub.py:145-158 | memory-fallback set/incr expire'ı yok sayar (TTL yok) + thread-unsafe singleton | fixed |
| AUDIT-150 | medium | security | cache_manager.py:67,80 | pickle.dumps/loads cache değerleri → Redis yazılabilirse deserialization RCE | fixed (HMAC-SHA256 imzalama); **re-fixed 363b2691** (doğrulama: `SECRET_KEY.encode()` SecretStr'de AttributeError → her cache set/get çöküyordu → `.get_secret_value()` — HIGH regresyon) |
| AUDIT-151 | medium | reliability | circuit_breaker.py:104-131 | HALF_OPEN tek-probe kapısı yok → iyileşen servise eşzamanlı probe sürüsü | fixed 68a627f7 |
| AUDIT-152 | medium | reliability | job_manager.py:28-70 | job durumu süreç-içi bellek → çok-worker'da poll unknown, restart'ta kayıp, cleanup leak | fixed (pending commit) |
| AUDIT-153 | medium | concurrency | idempotency.py:48-57 | get-sonra-set TOCTOU → eşzamanlı dupe geçer; başarısız istek 5dk kilitler | fixed d5d85ece |
| AUDIT-154 | low | reliability | celery_app.py:29-30 | global task_time_limit=90s ağır beat task'larını kesebilir (kısmi tamamlanma) | fixed |
| AUDIT-155 | low | security | mapbox_client.py:90 + openroute_client.py:174 | API anahtarları URL query param'ında → log sızıntı riski | fixed be71feeb; **re-fixed 98249df8** (doğrulama: `exc.request` set edilmemişse httpx RuntimeError fırlatır → handler çöküyordu → `getattr(exc,'_request',None)`) |
| AUDIT-156 | medium | performance | openroute_client.py:393-453 | _save_to_cache yeni koord INSERT etmez → ad-hoc rotalar cache'lenmez, ORS kota yakımı + ABS seq-scan | fixed f2f60493 |
| AUDIT-157 | low | security | backup_manager.py:57-84 | şifrelenmemiş düz-metin .sql dump (tüm PII); cleanup .sqlite3 atlar | fixed (dump -Fc gzip compressed; cleanup .sqlite3+.sql.gz kapsar; full AES encryption prod'da secrets manager gerektirir — dışı kapsam) |
| AUDIT-158 | medium | security | security_probe.py:23-50 | brute-force detector proxy IP + docker-bridge trust → reverse proxy ardında devre dışı | fixed (logging_middleware get_real_client_ip kullanır; X-ForwardedFor yalnız trusted proxy'den) |
| AUDIT-159 | medium | bug | event_bus.py:216-226 | ErrorEventBus severity string karşılaştırması → critical batch'te warning'e düşer | fixed a94d36ca |
| AUDIT-160 | medium | reliability | prediction_tasks.py:28-29 | Celery task event-loop/engine yönetimi tutarsız: loop leak + dispose'suz asyncio.run cross-loop riski | fixed 68a627f7 |
| AUDIT-161 | low | reliability | dlq_tasks.py:20-45 | drain_prediction_dlq siler+loglar, requeue no-op → başarısız tahminler kalıcı kayıp | fixed 679d5fed |
| AUDIT-162 | low | bug | ocr_tasks.py:44-63 | ocr_durumu="hata" retry rollback ile geri alınır → terminal hata durumu yazılmaz | fixed 679d5fed |
| AUDIT-163 | low | bug | 0022_durum_canonical_english.py:118-130 | downgrade İngilizce veriye Türkçe CHECK ekliyor → mevcut satırlar ihlal, downgrade patlar | fixed (downgrade'e ters UPDATE eklendi: Planned→Bekliyor, Completed→Tamamlandı, Cancelled→İptal) |
| AUDIT-164 | medium | data-integrity | 0001_baseline.py:966 + 0022 + models.py:561 | seferler.durum default 'Tamam' İngilizce CHECK ile çelişir + model drift (alembic check kaçırır) | fixed 6e4e9b9d |
| AUDIT-165 | medium | data-integrity | 0006_fk_indexes_and_checks.py:45-49 | yakit durum CHECK ASCII 'Onaylandi' — app 'Onaylandı' (Türkçe) yazıyorsa onay ihlal | fixed 25b2cd86 |
| AUDIT-166 | medium | security | ops_bot.py:78-105,113-193 | /yeniden_baslat per-user authz yok (docker restart DoS) + webhook'lar kimlik doğrulamasız | fixed 42cc840b |
| AUDIT-167 | medium | security | ocr_service/main.py:19-26 | /ocr/process kimlik doğrulamasız + upload boyut/tip limiti yok | fixed (OCR_SERVICE_API_KEY Bearer auth + 20MB upload limit; backend callers header ekler) |
| AUDIT-168 | high | security | reset_password.py:15, create_db.py:14, elite_audit_backend.py:21, stress_import.py:32 | sabit-kodlu düz-metin parolalar repo'da (aynı pw ×3 + süper-admin default) | fixed ea43e558 |
| AUDIT-169 | low | bug | seed_demo_data.py:167-169 | seed Türkçe durum 'Tamam' 0022 İngilizce CHECK'i ihlal eder → demo seed kırık | fixed b95ceecb |
| AUDIT-170 | low | bug/dead-code | enrich_existing_data.py:86 + init_ml_db + cleanup + e2e_error_smoke | bozuk/şema-ıraksak dev script'ler (await yok, phantom tablo, .title() Türkçe, sahte token) | partially fixed (enrich: await eklendi + Completed→Tamam düzeltildi; init_ml_db: deprecated uyarı; e2e_error_smoke: sahte token gerçek auth gerektirir, dışı kapsam) |
| AUDIT-171 | low | reliability | retraining/deploy_new_models.py:32-37 | manuel retrain→deploy doğrulama kapısı yok (v3 pkl körlemesine prod'a) + prod akıştan ıraksak | fixed (pkl boyut+loadability doğrulama kapısı eklendi; --dry-run flag; tek hata tüm deploy'u iptal eder) |
| AUDIT-172 | medium | concurrency | axios-instance.ts:53-89 | 401 refresh mutex yok → eşzamanlı 401'ler N /auth/refresh → rotate'te sahte logout | fixed 6e4e9b9d |
| AUDIT-173 | medium | maintainability | AuthContext.tsx:111-152 | hasPermission sabit role→izin haritası, gerçek rol_yetkiler'i yok sayar → RBAC drift | fixed fdd40f9b |
| AUDIT-174 | high | bug | lib/trip-status.ts:1-61 + validations.ts:89-99 | frontend durum canonical TÜRKÇE, backend İNGİLİZCE → durum gösterimi boş + filtre 0-eşleşme/422 + form-submit sessiz kayıp | fixed 48e54ba0 |
| AUDIT-175 | medium | security | NotificationContext.tsx:80-92 | admin WS JWT'yi query-param'da yolluyor (log sızıntısı); ws-service ticket kullanırken tutarsız | fixed fdd40f9b |
| AUDIT-176 | low | privacy | stores/use-ai-store.ts:93-100 | use-ai-store user-scoped değil → AI sohbet geçmişi paylaşılan tarayıcıda sızar | fixed 81ce9344 (b95ceecb claimed fix ancak uygulanmamıştı; userScopedStorage adapter eklendi) |
| AUDIT-177 | low | security | components/today/TriageItemCard.tsx:63-72 | window.open backend url'yi safeHref'siz açıyor (InvestigationDetailDialog safeHref kullanırken tutarsız) | fixed b95ceecb |
| AUDIT-178 | low | i18n | hooks/useLocationForm.ts:83-89 | normalizePlaceName Türkçe-bilinçsiz capitalize → kayıtlı güzergah adlarında İ/ı bozulması | fixed 679d5fed |
| AUDIT-179 | medium | bug | model_training_handler.py:87 | var-olmayan event_bus.publish_simple → AttributeError yutulur → auto-train sonrası cache/RAG invalidation hiç olmaz | fixed 54ed9643 |
| AUDIT-180 | medium | bug | app/scripts/backfill_route_pairs.py:22 | `.where(... is None)` → WHERE false → backfill 0 satır işler (sessiz no-op) | fixed 1f8aa4fd |
| AUDIT-181 | low | performance | physics_handler.py:28-101 | async handler'da senkron physics predict (loop bloke) + manuel tahmini_tuketim ezilir | fixed (predict → asyncio.to_thread; manuel ezilme şema değişikliği gerektirir — kapsam dışı) |
| AUDIT-182 | low | consistency | core/errors.py:51-70 | iki ayrı hata-yanıt zarfı (errors.py vs main.py) → tutarsız API hata formatı | fixed be71feeb (create_error_response → trace_id, no success/timestamp; test_coverage_boost imports+patches düzeltildi) |
| AUDIT-183 | low | security | sw-push.ts:40-58 | notificationclick push payload url'sini same-origin doğrulaması olmadan openWindow ile açıyor (phishing click-through) | fixed (pending commit) |
