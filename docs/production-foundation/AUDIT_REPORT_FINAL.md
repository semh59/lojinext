## EXACT CUSTOM MATCH REPORT WITH SEPARATED TRACKS

### B-01
File: frontend\src\lib\utils.ts
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: Some exports are missing in utils.ts and api-validator.ts.

TRACK 2 — Language (English-only technical surface):
  Status: CLEAN
  Dirty items: none

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-02
File: app\requirements-dev.txt
Line: multiple

TRACK 1 — B-code fix:
  Status: PARTIAL
  Evidence: File exists but missing required dependencies.

TRACK 2 — Language (English-only technical surface):
  Status: CLEAN
  Dirty items: none

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-03
File: app\.env
Line: multiple

TRACK 1 — B-code fix:
  Status: DONE
  Evidence: Secret keys are defined.

TRACK 2 — Language (English-only technical surface):
  Status: CLEAN
  Dirty items: none

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-04
File: alembic\versions
Line: multiple

TRACK 1 — B-code fix:
  Status: DONE
  Evidence: Directory exists with 4 migration files.

TRACK 2 — Language (English-only technical surface):
  Status: SKIP
  Dirty items: none

TRACK 3 — Production truth:
  Status: SKIP
  Fake items: none
### B-05
File: docker-compose.yml
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: Backend service does not explicitly declare the latest image.

TRACK 2 — Language (English-only technical surface):
  Status: CLEAN
  Dirty items: none

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-06
File: app\config.py
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: OPENROUTESERVICE_API_KEY has no default empty string.

TRACK 2 — Language (English-only technical surface):
  Status: CLEAN
  Dirty items: none

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-07
File: frontend\src
Line: multiple

TRACK 1 — B-code fix:
  Status: DONE
  Evidence: No instances of legacy bg-bg-* classes found.

TRACK 2 — Language (English-only technical surface):
  Status: SKIP
  Dirty items: none

TRACK 3 — Production truth:
  Status: SKIP
  Fake items: none
### B-08
File: frontend\src\index.css
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: Missing required CSS classes or config keys.

TRACK 2 — Language (English-only technical surface):
  Status: CLEAN
  Dirty items: none

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-09
File: app\infrastructure\routing\openroute_client.py
Line: multiple

TRACK 1 — B-code fix:
  Status: PARTIAL
  Evidence: Contains legacy mapping or reads both keys.

TRACK 2 — Language (English-only technical surface):
  Status: MIXED
  Dirty items: resilience

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-10
File: app\infrastructure\routing\openroute_client.py
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: No actual INSERT statement found in cache fallback.

TRACK 2 — Language (English-only technical surface):
  Status: MIXED
  Dirty items: resilience

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-11
File: app\core\services\lokasyon_service.py
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: include_details defaults to False or unspecified.

TRACK 2 — Language (English-only technical surface):
  Status: DIRTY
  Dirty items: lokasyonservice, lokasyoncreate, lokasyon_repo, lokasyonresponse, lokasyonupdate

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-12
File: app\core\services\route_validator.py
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: Threshold remains a static single value.

TRACK 2 — Language (English-only technical surface):
  Status: CLEAN
  Dirty items: none

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-13
File: app\infrastructure\routing\mapbox_client.py
Line: multiple

TRACK 1 — B-code fix:
  Status: DONE
  Evidence: ascent_m correctly preserved in hybrid structure.

TRACK 2 — Language (English-only technical surface):
  Status: CLEAN
  Dirty items: none

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-14
File: app\api\v1\endpoints\locations.py
Line: multiple

TRACK 1 — B-code fix:
  Status: DONE
  Evidence: Geocode endpoint exists.

TRACK 2 — Language (English-only technical surface):
  Status: DIRTY
  Dirty items: delete_lokasyon, create_lokasyon, lokasyonservice, kullanici, lokasyonupdate

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-15
File: app\core\services\sefer_write_service.py
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: Allows saving without rigorous guzergah_id check.

TRACK 2 — Language (English-only technical surface):
  Status: DIRTY
  Dirty items: sefer_status_transitions, sefer_status, seferrepository, seferupdate, ensure_canonical_sefer_status

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-16
File: app\database\repositories\sefer_repo.py
Line: multiple

TRACK 1 — B-code fix:
  Status: DONE
  Evidence: JOIN uses deterministic FK guzergah_id instead of string matches.

TRACK 2 — Language (English-only technical surface):
  Status: DIRTY
  Dirty items: sofor, sefer, arac_id, sofor_id, baslangic_tarih

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-23
File: app\core\ml\ensemble_predictor.py
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: Both legacy factors are actively applied inside feature matrix computations.

TRACK 2 — Language (English-only technical surface):
  Status: CLEAN
  Dirty items: none

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-31
File: app\api\v1\endpoints\trips.py
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: Found 12 base except blocks masking error types.

TRACK 2 — Language (English-only technical surface):
  Status: DIRTY
  Dirty items: resilience, read_seferler, seferbulkcancel, seferresponse, kullanici

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-DS-01
File: app\core\services\dashboard_service.py
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: Illegitimately calls get_dashboard_summary instead of generate_fleet_summary().

TRACK 2 — Language (English-only technical surface):
  Status: MIXED
  Dirty items: sefer_repo, isoformat, get_sefer_repo

TRACK 3 — Production truth:
  Status: PARTIAL
  Fake items: date.today()
### B-SW-02
File: app\core\services\sefer_write_service.py
Line: 921

TRACK 1 — B-code fix:
  Status: PARTIAL
  Evidence: Mixed usage: reads prediction_liters as a fallback instead of hard-forcing tahmini_tuketim.

TRACK 2 — Language (English-only technical surface):
  Status: DIRTY
  Dirty items: sefer_status_transitions, sefer_status, seferrepository, seferupdate, ensure_canonical_sefer_status

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-79
File: app\api\v1\endpoints\predictions.py
Line: multiple

TRACK 1 — B-code fix:
  Status: DONE
  Evidence: simulate_training_for_task has been successfully purged/is absent.

TRACK 2 — Language (English-only technical surface):
  Status: MIXED
  Dirty items: kullanici, sefer, sofor

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-108
File: app\core\services\security_service.py
Line: multiple

TRACK 1 — B-code fix:
  Status: DONE
  Evidence: verify_ownership bypasses ownership checks gracefully for Admin roles.

TRACK 2 — Language (English-only technical surface):
  Status: MIXED
  Dirty items: kullanici, role_permissions

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-115
File: app\core\services\sefer_read_service.py
Line: multiple

TRACK 1 — B-code fix:
  Status: PARTIAL
  Evidence: Isolation applied but fails to strictly enforce filter=-1 block.

TRACK 2 — Language (English-only technical surface):
  Status: DIRTY
  Dirty items: kullanici, seferresponse, seferrepository, seferreadservice, sefer_id

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-82
File: app\core\services\cost_analyzer.py
Line: multiple

TRACK 1 — B-code fix:
  Status: DONE
  Evidence: Cost analyzer explicitly implements the standard date range fetch loop.

TRACK 2 — Language (English-only technical surface):
  Status: MIXED
  Dirty items: arac_repo, arac_id, isoformat, yakit_repo, sefer_repo

TRACK 3 — Production truth:
  Status: PARTIAL
  Fake items: date.today()
### B-83
File: app\core\services\maintenance_service.py
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: No direct calls to the repository getter found.

TRACK 2 — Language (English-only technical surface):
  Status: DIRTY
  Dirty items: arac_id, bakim_tipi, bakimtipi, maliyet, aracbakim

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-111
File: app\core\services\attribution_service.py
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: override_attribution still references obsolete sefer_repo directly rather than passing through abstractions.

TRACK 2 — Language (English-only technical surface):
  Status: MIXED
  Dirty items: sofor_id, sefer_id, arac_id

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-ML-03
File: app\core\ml\ensemble_predictor.py
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: _dorse_repo is initialized maliciously.

TRACK 2 — Language (English-only technical surface):
  Status: CLEAN
  Dirty items: none

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-ML-02
File: app\core\ml\ensemble_predictor.py
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: date.today() usage prevents backdated prediction stability.

TRACK 2 — Language (English-only technical surface):
  Status: CLEAN
  Dirty items: none

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-PS-03
File: app\core\ml\ensemble_predictor.py
Line: multiple

TRACK 1 — B-code fix:
  Status: NOT STARTED
  Evidence: Prediction dict lacks confidence_score field entirely.

TRACK 2 — Language (English-only technical surface):
  Status: CLEAN
  Dirty items: none

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-98
File: app\core\services\health_service.py
Line: multiple

TRACK 1 — B-code fix:
  Status: DONE
  Evidence: Backup dynamics reliably use filesystem paths, untouched un-mocked data.

TRACK 2 — Language (English-only technical surface):
  Status: MIXED
  Dirty items: resilience, isoformat

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-97
File: app\api\v1\endpoints\admin_health.py
Line: multiple

TRACK 1 — B-code fix:
  Status: DONE
  Evidence: admin parameter correctly accepts dynamic strings.

TRACK 2 — Language (English-only technical surface):
  Status: MIXED
  Dirty items: require_yetki

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-RS-06
File: app\core\services\report_service.py
Line: multiple

TRACK 1 — B-code fix:
  Status: DONE
  Evidence: Mocks explicitly stripped from logical performance evaluations.

TRACK 2 — Language (English-only technical surface):
  Status: DIRTY
  Dirty items: sofor_repo, sofor, get_arac_repo, get_sefer_repo, arac_repo

TRACK 3 — Production truth:
  Status: PARTIAL
  Fake items: date.today()
### B-Contracts
File: app\infrastructure\events\contracts.py
Line: multiple

TRACK 1 — B-code fix:
  Status: DONE
  Evidence: Duplicate contract EventType absent.

TRACK 2 — Language (English-only technical surface):
  Status: CLEAN
  Dirty items: none

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none
### B-Token
File: app\infrastructure\security\token_blacklist.py
Line: multiple

TRACK 1 — B-code fix:
  Status: DONE
  Evidence: Backed faithfully by redis engine cache over local python instances.

TRACK 2 — Language (English-only technical surface):
  Status: CLEAN
  Dirty items: none

TRACK 3 — Production truth:
  Status: CLEAN
  Fake items: none


## LANGUAGE SCAN FINDINGS

LANGUAGE — app\core\services\sefer_write_service.py:
  Turkish identifiers found: update_seferduration_minguzergah_idguzergah_idtahmini_sure_saattahmini_sure_saatsefer_idarac_idarac_idplanned_minactual_mindelay_minseferwriteservice, mesafe_km, seferin, deletesefersefer, base_sefer_no, is_round_tripsefer_nosefer_notarihtarihsaatsaatarac_idarac_idsofor_idsofor_idguzergah_idguzergah_idcikis_yericikis_yerivaris_yerivaris_yerimesafe_kmmesafe_kmbos_agirlik_kgbos_agirlik_kgdolu_agirlik_kgdolu_agirlik_kgnet_kgnet_kgbos_seferbos_seferdurumdurumis_round_tripreturn_net_kgreturn_net_kgreturn_sefer_noreturn_sefer_noascent_mascent_mdescent_mdescent_mflat_distance_kmflat_distance_km, guncelleme, seferwriteservice, guzergah_id, return_sefer_no, sefer_status_tamamlandi, bulunamadısefer_no, mvaris_yericikis_yerimesafe_kmbos_agirlik_kgbos_agirlik_kgdescent_mascent_mflat_distance_kmdönüş, otoban_mesafe_km, get_sefer_repo, sefer_no, tarihsaatarac_iddorse_idsofor_idguzergah_idnet_kgtonbos_agirlik_kgdolu_agirlik_kgcikis_yerivaris_yerimesafe_kmbos_seferascent_mdescent_mflat_distance_kmtahmini_tuketimtahmin_metadurumnotlarsefer_nobulk, sofor_id, seferupdate, ensure_canonical_sefer_status, bos_sefer, tahmini_tuketim, olamazmesafe, sefer_id, seferi, sefer_status_iptal, sefer_status, sefercreate, sefer, sil, full_sefer_obj, silme, arac_id, darac_idsofor_iddorse_idguzergah_id, durum, net_kgbos_agirlik_kgdolu_agirlik_kgbos_agirlik_kgbos_agirlik_kgdolu_agirlik_kgdolu_agirlik_kgnet_kgnet_kgdolu_agirlik_kgbos_agirlik_kgnet_kgnet_kgdolu_agirlik_kgtonsefer_idarac_idarac_idseferwriteservice, update_sefersla, create_returnsefermevcut, add_sefer, ref_sefer_id, durumunu, sefer_repo, sefer_notahmini_tuketim, bos_agirlik_kg, sefer_status_transitions, ekle, cikis_yeri, hatasi, silindi, hatası, cikis_yerivaris_yeriascent_mdescent_mflat_distance_kmidbulk, seferrepository, seferden, sefer_status_planlandi, dolu_agirlik_kg, tarih, fcreatesefer, iptal, idreasonsuccess_countfailed_countfailedbulk_createsefertoplu, silinemedibulk, sehir_ici_mesafe_km
  File name itself: DIRTY (Turkish)

LANGUAGE — app\core\services\sefer_read_service.py:
  Turkish identifiers found: arac_id, kullanici, seferresponse, sofor_id, baslangic_tarih, seferrepository, get_sefer_by_id, seferreadservice, durum, sefer_id, get_sefer_timeline, sefer_repo, sefer, bitis_tarih, get_sefer_repo
  File name itself: DIRTY (Turkish)

LANGUAGE — app\core\services\dashboard_service.py:
  Turkish identifiers found: sefer_repo, isoformat, get_sefer_repo
  File name itself: DIRTY (Turkish)

LANGUAGE — app\core\ml\ensemble_predictor.py:
  Turkish identifiers found: get_dorse_repo, mesafe_km, isoformat, get_arac_repo, arac_entity, dorse_id, sofor_service, filo_karsilastirma, ensure_ascii, dorse_bos_agirlik, dorse, get_sefer_repo, arac_repo, _dorse_repo, sofor_id, arac_yasi, trailer_rolling_resistance, dorse_repo, sefer, arac, arac_id, _arac_repo, test_sefer, sofor_katsayi, enriched_seferler, sofor_analiz_service, sefer_repo, tarih_str, measurements, fromisoformat, get_sofor_analiz_service, tarih, dorse_lastik_sayisi, _sefer_repo, seferler, mesafe
  File name itself: DIRTY (Turkish)

LANGUAGE — app\core\ml\physics_fuel_predictor.py:
  Turkish identifiers found: f_roll_tractor, rolling_resistance, e_rolling_total, arac_yasi, f_roll, f_roll_trailer, trailer_rolling_resistance
  File name itself: DIRTY (Turkish)

LANGUAGE — app\database\repositories\sefer_repo.py:
  Turkish identifiers found: mesafe_km, sofor, get_bugunun_seferleri, isoformat, dorse_id, guzergah_id, sefer_status_tamamlandi, otoban_mesafe_km, dorse, get_sefer_repo, sefer_no, sofor_id, update_sefer, guzergah, ensure_canonical_sefer_status, bos_sefer, toplam_sefer, tahmini_tuketim, sefer_status_iptal, sefer_status, sefer, arac, arac_id, exclude_sefer_id, baslangic_tarih, durum, rollback, iptal_nedeni, bos_agirlik_kg, tuketim, cikis_yeri, get_by_sefer_no, seferrepository, fromisoformat, sefer_status_planlandi, dolu_agirlik_kg, tarih, seferler, bitis_tarih, sehir_ici_mesafe_km
  File name itself: DIRTY (Turkish)

LANGUAGE — app\database\repositories\analiz_repo.py:
  Turkish identifiers found: arac_id, rollback, yakitformul, isoformat, get_filo_ortalama_tuketim, get_training_seferler, sefer_status_tamamlandi, sefer_status, sefer
  File name itself: DIRTY (Turkish)

LANGUAGE — app\api\v1\endpoints\trips.py:
  Turkish identifiers found: resilience, read_seferler, seferbulkcancel, seferresponse, isoformat, sefer_import_service, read_bugunun_seferleri, sefer_in, kullanici, sofor_id, update_sefer, get_sefer_by_id, seferupdate, seferbulkdelete, sefer_ids, sefer_id, seferbulkstatusupdate, get_sefer_import_service, sefercreate, sefer, get_sefer_timeline, delete_sefer, create_sefer, new_sefer_id, arac_id, sefer_service, baslangic_tarih, durum, seferstatsresponse, add_sefer, export_seferler, read_sefer, seferservice, iptal_nedeni, seferlistresponse, seferbulkresponse, get_sefer_service, fromisoformat, tarih, upload_sefer_excel, seferler, bitis_tarih
  File name itself: DIRTY (Turkish)

LANGUAGE — app\infrastructure\events\contracts.py:
  Turkish identifiers found: none
  File name itself: CLEAN (English)

LANGUAGE — app\core\utils\sefer_status.py:
  Turkish identifiers found: sefer_status_transitions, legacy_sefer_status_devam_ediyor, legacy_sefer_status_yolda, canonical_sefer_statuses, read_completed_sefer_statuses, normalize_sefer_status, legacy_sefer_status_tamam, read_open_sefer_statuses, ensure_canonical_sefer_status, legacy_sefer_status_bekliyor, sefer_status_planlandi, sefer_status_tamamlandi, sefer_status_iptal, canonical_sefer_status_set
  File name itself: DIRTY (Turkish)

## FINAL SUMMARY TABLE

| Track | Status | Count |
|-------|--------|-------|
| B-code DONE | | 14 |
| B-code NOT STARTED | | 16 |
| B-code PARTIAL | | 4 |
| B-code NOT FOUND | | 0 |
| B-code BROKEN | | 0 |
| B-code REMOVED | | 0 |
| Language CLEAN | | 14 |
| Language DIRTY | | 9 |
| Language MIXED | | 9 |
| Language SKIP | | 2 |
| Truth CLEAN | | 29 |
| Truth FAKE | | 0 |
| Truth PARTIAL | | 3 |
| Truth SKIP | | 2 |

### Highest Risk NOT STARTED Items
- B-DS-01 (dashboard metrics failure)
- B-SW-02 (legacy prediction pipeline block)
- B-31 (unreachable exception masking)
- B-111 (attribution fallback)
- B-ML-03 (Dorse ML misrouting)
- B-115 (Zero isolation filtering)
- B-23 (Double mevsim multiplier count)
