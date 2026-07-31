# prediction_ml — Bağımsız Servise Ayrıştırma (Tasarım)

## Bağlam ve Motivasyon

Kullanıcı, mevcut modüler-monolit mimariden (15 `v2/modules` iş modülü, tek
FastAPI process, tek Postgres, import-linter ile zorlanan sınırlar)
"mikroservise en yakın performans ve güç" hedefiyle gerçek servis
ayrıştırmasına geçmek istiyor. İki servis zaten `v2/services/` altında ayrı
deploy ediliyor (`ocr_service`, `telegram_bot`, kendi Dockerfile+
requirements.txt'leri var) — bu, kanıtlanmış bir desen.

Deployment hedefi: şu an tek makine (docker-compose), ama kullanıcı
ileride gerçek çok-host/VPS dağıtımı planlıyor — bu yüzden servis
ayrıştırması bugünden hazırlık olarak anlamlı.

**Seçilen modül**: `prediction_ml` — 5-model ensemble ML pipeline (fizik +
LightGBM + XGBoost + GradientBoosting + RandomForest), Kalman online-learning,
ARIMA zaman serisi, model eğitim/versiyonlama. CPU-ağır işlemler barındırıyor,
ana backend'in HTTP request döngüsünden en fazla izolasyon kazanacak modül.

**Kritik bulgu (kod okumasıyla doğrulandı)**: `prediction_ml.public` 18
farklı dosyada, 7 farklı modülden (trip, route_simulation, location, driver,
anomaly, analytics_executive, ai_assistant) senkron/in-process fonksiyon
çağrısıyla kullanılıyor. Bunlardan biri — sefer create yolu
(`SeferFuelEstimator`) — 2.5 saniyelik sıkı bir timeout altında çalışıyor
(kök `CLAUDE.md`'de dokümante). Bu, ayrıştırmanın kapsamını ve riskini
belirleyen en önemli kısıt.

## Mimari

- Yeni `v2/services/prediction_ml_service/` — `ocr_service` deseniyle kendi
  `Dockerfile` + `requirements.txt`'i olan bağımsız bir FastAPI servisi.
- `v2/modules/prediction_ml`'in mevcut `domain/`/`application/`/
  `infrastructure/` kodu **mekanik olarak** yeni servise taşınır (davranış
  değişmez — projenin "önce mekanik taşı, sonra davranış değiştir" ilkesiyle
  tutarlı, bu repoda 17+ dalga boyunca kanıtlanmış desen).
- Eski konumda (`v2/modules/prediction_ml/public.py`) yalnızca **ince bir HTTP
  client** kalır. `public.py`'nin fonksiyon imzaları/dönüş tipleri BİREBİR
  aynı kalır — 18 çağrı noktasının hiçbiri değişmez, yalnızca `public.py`'nin
  içinde "in-process çağrı" yerine "HTTP çağrısı" olur.
- **Auth**: mevcut `X-Internal-Token`/`INTERNAL_API_SECRET` deseni (zaten
  `telegram_bot` servislerinde kullanılıyor, `admin_platform/api/
  internal_routes.py` tarafında doğrulanıyor) yeniden kullanılır — yeni auth
  mekanizması icat edilmez.
- **Ağ topolojisi**: Traefik'e dış rota açılmaz (OCR/Telegram gibi yalnız iç
  Docker network, host port yok).
- **DB erişimi**: `m_prediction_ml` PostgreSQL rolü FAZ2'den zaten var — yeni
  servis bu rolün kimlik bilgileriyle DOĞRUDAN bağlanır. Bu, ana backend'in
  contextvar-tabanlı `SET LOCAL ROLE` dansına ihtiyaç duymaz (ayrı process/
  connection olduğu için basitleşir) — servis ayrıştırmasının FAZ2 rol-
  izolasyonu için doğal bir sadeleştirme getirdiği görülüyor.

## Hızlı Yol / Ağır Yol Ayrımı

- **Hızlı yol** (tekil tahmin okumaları — sefer create, XAI explain, driver
  stats): `public.py`'nin HTTP client'ı, mevcut `with_async_retry` +
  `CircuitBreakerRegistry` (`platform_infra.resilience`'ta zaten var) ile
  sarılır. Hata/timeout → **mevcut "tahminsiz kaydet" deseni** devreye girer
  (Mapbox/Open-Meteo için zaten var olan davranışın aynısı, `prediction_ml`'e
  de genişletilir); ayrıca cold-start'ta zaten var olan "physics-only bypass"
  (pw=1.0) fallback yolu ağ hatasında da tetiklenir.
- **Ağır yol** (ensemble training, haftalık retrain, DLQ drain, backfill):
  bu Celery task'ları (`infrastructure/{scheduler_task,
  prediction_backfill_tasks}.py` + ilgili beat schedule girişleri) **yeni
  servise taşınır** — kendi worker + beat schedule'ı olur, ana backend'in
  `celery_app.py`'si artık bunları çalıştırmaz/register etmez.
- Model `.pkl` dosyaları için mevcut `model_data` Docker volume'u tek-host'ta
  paylaşılmaya devam eder. **Not**: çok-host'a geçildiğinde daha önce
  ertelenen object-storage (S3/MinIO) migrasyonu o zaman gerçekten gerekli
  olur — bu, bu planın kapsamı dışında, ayrı bir gelecek iş olarak kalır.

## Bu Taşımayla Birlikte Yapılacak 3 Gerçek İyileştirme

Yalnız mekanik taşıma değil — modülün kendi `CLAUDE.md`'sinde zaten
belgelenmiş, taze `grep` ile doğrulanmış 3 gerçek sorun bu fırsatla ele
alınır:

1. **Sıfır-çağıranlı ölü kodun silinmesi**: `domain/kalman_estimator.py`
   (`KalmanEstimatorService`/`get_kalman_service`),
   `domain/physics_fuel_predictor.py`'nin `HybridFuelPredictor`'ı,
   `domain/lightgbm_predictor.py`'nin `LightGBMFuelPredictor`/
   `LightGBMAnomalyClassifier`'ı, `domain/benchmark.py`'nin tamamı
   (`MLBenchmark`/`ABTestFramework`/`EnsembleBenchmark`) — hepsi grep ile
   doğrulandı: repo genelinde sıfır prod çağıranı var (yalnız kendi test
   dosyaları). Yeni servise taşınmaz, bu dosyalar + onların dedike test
   dosyaları silinir. `time_series_predictor.py`'nin legacy LSTM sınıfları
   HARİÇ tutulur (kendi docstring'i "yalnızca test fixture'ları için
   tutuluyor" diyerek KASITLI tutulduğunu zaten belirtiyor — farklı kategori).
2. **Multi-worker LRU cache → Redis-backed paylaşımlı cache**:
   `EnsemblePredictorService`'in 20-slot `OrderedDict` LRU'su her worker
   process'inde ayrı (paylaşılmıyor). Yeni servis birden fazla replica ile
   ölçeklenebileceği için (asıl ayrıştırmanın motivasyonu budur), bu sorun
   şimdi katlanarak büyür. `platform_infra.cache.RedisCache`/
   `CacheManager` (zaten var, başka modüllerde kullanılıyor) kullanılarak
   predictor cache'i Redis'e taşınır — cache key `f"predictor:{arac_id}"`,
   serileştirme mevcut disk-persist mekanizmasıyla aynı (pickle/joblib,
   zaten kullanılıyor).
3. **`ensemble_core.py::fit()` (CC=61) bölünmesi**: modül taşınırken zaten
   yeniden yazıldığı için, önceki fazda "bölünmedi" diye bırakılan bu
   fonksiyon şimdi mantıksal alt-adımlara ayrılır (veri hazırlama / model
   eğitimi / ağırlık hesaplama / persist) — davranış değişmez, yalnız
   okunabilirlik ve test edilebilirlik artar.

## Kademeli Devreye Alma (Risk Azaltma)

1. Yeni servisi kur, kodu mekanik taşı (+ yukarıdaki 3 iyileştirme) —
   davranış (iyileştirmeler hariç) aynı kalır.
2. Eski `public.py`'de `PREDICTION_ML_REMOTE` feature-flag'i (mevcut
   `USE_SEFER_FUEL_ESTIMATOR`/`USE_SEGMENT_TRACTIVE_MODEL` deseniyle aynı
   kategori) — varsayılan `false` (eski in-process davranış — **bu fazda
   eski kod SİLİNMEZ**, yalnız yeni servis paralel kurulur), `true` yeni HTTP
   client'ı devreye sokar. Anlık geri-dönüş kolu.
3. Dev'de gerçek docker-compose ile (yeni container + ana backend) tam test
   suite'i flag=true ile koştur — 18 çağrı noktasının testleri, `public.py`
   contract'ı aynı kaldığı için assertion değiştirmez, yalnız mock'lama HTTP
   sınırına taşınır (bu oturumda kurulan `api_stub`/0-mock desenine benzer
   bir iç-servis stub'ı gerekebilir, ya da doğrudan yeni servisin dev
   container'ına karşı gerçek HTTP round-trip).
4. CI'da yeni bir `--profile test` container'ı (mevcut `api_stub`'la aynı
   desen) eklenir, flag=true ile hard-gates yeşile çekilir.
5. Flag varsayılanı `true` yapılır; eski in-process yol bir sonraki turda
   (bu planın kapsamı dışında, ayrı bir "temizlik" fazı olarak) silinir.

## Test Stratejisi

- Yeni servisin kendi test suite'i: mevcut `app/tests/unit/test_ml/`
  dosyaları (20+ dosya) mekanik taşınır, import path'leri güncellenir.
- Ana backend tarafında: yeni servise karşı gerçek HTTP round-trip testleri
  (0-mock ilkesiyle tutarlı — mock değil, gerçek container).
- 3 iyileştirmenin kendi testleri: silinen dosyaların dedike test dosyaları
  kaldırılır (kod silindiği için); Redis-backed cache için gerçek Redis'e
  karşı test (mevcut `mock_redis_for_cache_manager` fixture deseni — gerçek
  Redis, mock değil); `fit()` bölünmesi için mevcut testler DEĞİŞMEDEN
  geçmeli (davranış aynı, yalnız iç yapı değişti).

## Kapsam Dışı (Bilinçli Olarak Ertelenen)

- Object storage (S3/MinIO) migrasyonu — yalnız gerçek çok-host dağıtımı
  geldiğinde gerekli.
- Eski in-process kodun silinmesi — flag=true kanıtlandıktan bir tur sonra,
  ayrı bir iş.
- Diğer modüllerin (route_simulation, ai_assistant) ayrı servise
  taşınması — bu plan yalnızca `prediction_ml`'i kapsıyor.
