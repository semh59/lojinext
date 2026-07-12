# FAZ0 — Kalite Baseline Sonuçları (2026-07-12)

Modüler monolit refaktörü (bkz. `MEMORY/PROGRESS.md`, `TASKS/faz0-baseline-olcum-ve-rapor-modu.md`) için dondurulmuş ölçüm. Ham `radon cc -j` / `wc -l` çıktıları yerel çalışma dosyaları olarak üretildi (`docs/superpowers/audits/faz0-{radon,loc}-baseline.{json,txt}`) — repo kuralı gereği (`.gitignore:140,143` — bu dizinde yalnız `.md` raporlar commit'lenir, ham `.json`/`.txt` dump'lar değil) bu dosya onların yerine geçen özet rapordur; ham dosyalar gerekirse aynı komutlarla yeniden üretilebilir.

## LOC dağılımı (327 dosya, `app/` — tests/`__pycache__`/archive hariç)
- Toplam: 71.858 satır (dosya-başı wc -l toplamı; `find ... | xargs wc -l` "total" satırı 72.190 — fark klasör-toplamı çoklu-sayım artefaktı, dosya listesi 327/71.858 doğrulanmış rakamdır, bkz. MEMORY §A.1)
- **33 dosya >500 satır, 7 dosya >1000 satır**
- En büyük 7: `models.py` 1988, `sefer_write_service.py` 1590, `ensemble_core.py` 1328, `analiz_repo.py` 1085, `sefer_repo.py` 1076, `import_service.py` 1073, `trips.py` 1020

## Cyclomatic Complexity (radon, 2097 fonksiyon/metot bloğu)
- median CC=3, p90=9, max=61
- **CC>10: 156 blok, CC>15: 56 blok, CC>30: 8 blok**

| CC | Dosya | Fonksiyon |
|---|---|---|
| 61 | app/core/ml/ensemble_core.py | fit |
| 58 | app/core/services/sefer_write_service.py | bulk_add_sefer |
| 56 | app/domain/services/route_analyzer.py | analyze_segments |
| 50 | app/services/prediction_service.py | predict_consumption |
| 47 | app/core/ml/physics_fuel_predictor.py | _build_segments |
| 39 | app/core/services/excel_exporter.py | _export_data_sync |
| 36 | app/core/ml/ensemble_core.py | prepare_features |
| 33 | app/core/ml/ensemble_core.py | predict |
| 29 | app/main.py | _sentry_before_send |
| 28 | app/core/services/sefer_write_service.py | _update_sefer_uow |

Bu tablo FAZ1'in `arch/quality_baseline.json`'unun (`TASKS/faz1-dosya-kalite-ve-kisalik-gate.md`) ham girdisidir — hiçbir dosya/fonksiyon burada değiştirilmedi, yalnız ölçüldü ve dondurulacak liste belirlendi.

## Yeniden üretim komutları
```bash
radon cc app -j -i tests > docs/superpowers/audits/faz0-radon-baseline.json
find app -name "*.py" -not -path "*/tests/*" -not -path "*__pycache__*" -not -path "*archive*" | \
  xargs wc -l | sort -rn > docs/superpowers/audits/faz0-loc-baseline.txt
```
