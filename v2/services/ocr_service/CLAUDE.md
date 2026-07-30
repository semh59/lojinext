# Servis: ocr_service

## Sorumluluk sınırı (ne yapar / ne YAPMAZ)

Standalone bir mikroservis — FastAPI `app`/`v2/modules` içine import edilmez,
kendi `Dockerfile`+`requirements.txt`'i ile ayrı bir container'da çalışır
(`docker-compose.yml`: `ocr-service`, port 8001). 2026-07-30'da repo
kökünden (`ocr_service/`) buraya taşındı (`v2/modules/<name>/` deseninden
FARKLI — bu bir FastAPI iş modülü DEĞİL, sadece dosya konumu düzenlendi;
`public.py`/`events.py`/DI-container wiring YOK).

- `main.py` — tek endpoint yüzeyi: `POST /ocr/process` (multipart
  `file` + `belge_tipi` form alanı, opsiyonel `OCR_SERVICE_API_KEY`
  yapılandırılmışsa `Authorization: Bearer` zorunlu), `GET /health`.
  `OcrProcessor` singleton, FastAPI `lifespan` içinde oluşturulur (ağır
  EasyOCR model yükü yalnız process başlangıcında bir kez).
- `ocr_processor.py` — `OcrProcessor.process()`: EasyOCR ile görüntüden
  metin çıkarır, `belge_tipi`'ye göre (`yakit_fisi`/`sefer_fisi`) regex
  tabanlı alan ayrıştırması yapar (litre/tutar/km gibi).

Çağıranlar: `v2/services/telegram_bot/driver_bot.py`'nin fotoğraf akışı
DEĞİL (o backend'e yükler, backend OCR'ı tetikler) — asıl çağıran
backend'in kendi OCR entegrasyon noktası (`fuel` modülünün
`ocr_preview`/belge-işleme akışı, bkz. `v2/modules/fuel/CLAUDE.md`).

## Bağımlılık riski (Python sürüm göçü bağlamı)

`requirements.txt` `easyocr==1.7.1` pin'liyor ama onun transitive
bağımlılıkları (`torch`/`torchvision`/`opencv-python`/`numpy`) HİÇBİRİ
kendisi pin'li değil — build zamanında hangi sürümün çözüleceği
belirsiz. Python sürümü değiştirilirken (3.11→3.12 gibi) bu servisin
build'i **izole bir denemeyle** doğrulanmalı (`docker build
v2/services/ocr_service/`), diğer servislerin aksine sıfıra yakın risk
varsayılamaz.

## Ortam değişkenleri

`OCR_SERVICE_API_KEY` (boşsa auth devre dışı — dev/test varsayılanı,
prod'da mutlaka set edilmeli).
