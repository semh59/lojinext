# LojiNext AI - TIR Yakıt Takip Sistemi Backend API

Modern, RESTful API tabanlı lojistik yönetim ve yakıt takip sistemi.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🚀 Hızlı Başlangıç

```bash
cd app
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API Dokümantasyonu: `http://localhost:8000/docs`

---

## ✨ Özellikler

- 📊 **RESTful API** - FastAPI ile modern, async API
- ⛽ **Yakıt Takibi** - Fiş CRUD, fiyat/litre/KM takibi
- 🚚 **Sefer Yönetimi** - Route planlama (OpenRouteService)
- 🚛 **Filo Yönetimi** - Araç ve sürücü yönetimi
- 📈 **Raporlar** - Filo özeti, araç detayı, şoför karşılaştırma
- 🤖 **AI Tahminler** - Yakıt tüketimi tahmini (ML modeli)
- 🔐 **JWT Auth** - Güvenli kimlik doğrulama
- 💾 **PostgreSQL** - Async veritabanı desteği

---

## 📁 Proje Yapısı

```
app/
├── main.py                  # FastAPI uygulama giriş noktası
├── config.py                # Uygulama ayarları (.env)
├── requirements.txt         # Python bağımlılıkları
├── api/
│   └── v1/
│       ├── api.py           # Router birleşimi
│       └── endpoints/       # API endpoint'leri
├── core/
│   ├── ai/                  # AI modelleri
│   ├── entities/            # Pydantic modeller
│   ├── ml/                  # ML tahmin modelleri
│   └── services/            # İş mantığı katmanı
├── database/
│   ├── connection.py        # Async DB bağlantısı
│   ├── models.py            # SQLAlchemy ORM modelleri
│   └── repositories/        # Data access layer
├── infrastructure/
│   ├── cache/               # Önbellekleme
│   ├── events/              # Event bus
│   └── logging/             # Loglama
└── schemas/                 # Pydantic request/response
```

---

## 🔌 API Endpoints

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| POST | `/api/v1/auth/login` | JWT token al |
| GET | `/api/v1/vehicles` | Araç listesi |
| POST | `/api/v1/vehicles` | Araç ekle |
| GET | `/api/v1/drivers` | Sürücü listesi |
| POST | `/api/v1/drivers` | Sürücü ekle |
| GET | `/api/v1/trips` | Sefer listesi |
| POST | `/api/v1/trips` | Sefer oluştur |
| GET | `/api/v1/fuel` | Yakıt kayıtları |
| POST | `/api/v1/fuel` | Yakıt kaydı ekle |
| GET | `/api/v1/reports/summary` | Filo özeti |
| POST | `/api/v1/predictions/fuel` | Yakıt tahmini |

---

## 🛠️ Teknolojiler

| Bileşen | Teknoloji |
|---------|-----------|
| Dil | Python 3.11+ |
| API Framework | FastAPI |
| Veritabanı | PostgreSQL (asyncpg) |
| ORM | SQLAlchemy 2.0 (async) |
| Auth | JWT (python-jose) |
| ML | scikit-learn, XGBoost |
| Route API | OpenRouteService |
| Validation | Pydantic v2 |

---

## 🏗️ Mimari

```
┌─────────────────────────────────────────────────────┐
│              API Layer (FastAPI Endpoints)          │
│   auth │ vehicles │ drivers │ trips │ fuel │ reports│
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│               Service Layer (Business Logic)        │
│  arac_service │ sefer_service │ yakit_service │ ... │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│             Repository Layer (Data Access)          │
│  SQLAlchemy ORM Models + Async Sessions             │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                PostgreSQL Database                  │
└─────────────────────────────────────────────────────┘

---

## 📄 Lisans

MIT License - Ticari ve kişisel kullanıma açıktır.

---

*LojiNext AI Backend v2.0 | 2026*
