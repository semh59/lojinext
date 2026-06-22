# 🚛 LojiNext — Backend & Frontend İletişim Mimarisi Raporu

---

## 1. Temel Mimari

| Katman | Teknoloji | Rol |
|--------|-----------|-----|
| **Backend** | **FastAPI (Python 3.12+)** | REST API + WebSocket sunucusu |
| **Frontend** | **React 19 + TypeScript + Vite** | SPA (Tek Sayfa Uygulama) |
| **Port** | Backend: `8080` → Frontend: `3000` | Vite proxy ile yönlendirme |

---

## 2. İletişim Kanalları

### 2.1. REST API (Ana İletişim)

- **Base URL (Frontend'den):** `/api/v1/*`
- **Vite Proxy (Dev):** `/api` → `http://127.0.0.1:8080` (vite.config.ts)
- **Prod:** Nginx reverse proxy ile `/api` backend'e yönlendirilir
- **İletişim Kütüphanesi:** Axios (axios-instance.ts)

### 2.2. WebSocket (Gerçek Zamanlı)

- **Admin WS:** `/admin/ws` — admin paneline canlı güncellemeler
- **Genel WS:** `/ws` — ticket tabanlı kimlik doğrulama ile WebSocket bağlantısı
- **Kullanım Alanları:** Bildirimler, canlı veri akışı, sürücü konum takibi

---

## 3. Kimlik Doğrulama (Auth)

```
Frontend                        Backend
  │                                │
  │  POST /auth/token              │
  │  ──────────────────────────►   │  access_token + refresh_token döner
  │  ◄──────────────────────────   │
  │                                │
  │  GET /routes (Bearer token)    │
  │  ──────────────────────────►   │  JWT doğrulama (HS256/RS256)
  │  ◄──────────────────────────   │
  │                                │
  │  401 → auto refresh → retry   │
```

- **Token Saklama:** `localStorage` (storage-service)
- **Refresh:** 401'de otomatik refresh token ile yenileme, o da başarısızsa → logout
- **JWKS Endpoint:** `/.well-known/jwks.json` (RS256 kullanımında)

---

## 4. API Uç Noktaları (30+ Modül)

| Modül | Prefix | Açıklama |
|-------|--------|----------|
| **Auth** | `/auth` | Giriş, kayıt, token yönetimi |
| **Routes** | `/routes` | Rota yönetimi |
| **Vehicles** | `/vehicles` | Araç CRUD |
| **Drivers** | `/drivers` | Sürücü yönetimi |
| **Trips** | `/trips` | Sefer kayıtları |
| **Fuel** | `/fuel` | Yakıt verileri |
| **Predictions** | `/predictions` | Yakıt tahminleri (ML) |
| **AI** | `/ai` | Yapay zeka sorguları (RAG + LLM) |
| **Locations** | `/locations` | Konum verileri |
| **Weather** | `/weather` | Hava durumu entegrasyonu |
| **Reports** | `/reports` | Raporlama |
| **Admin*** | `/admin/*` | Admin: kullanıcı, rol, ML, config, bakım vb. |
| **Trailers** | `/trailers` | Dorse yönetimi |
| **Preferences** | `/preferences` | Kullanıcı tercihleri |
| **Users** | `/users` | Kullanıcı profilleri |

---

## 5. Frontend Servis Katmanı

```
Page Component
     │
     ▼
Service (services/api/*.ts)
     │  Axios Instance (token ekleme, hata yönetimi)
     ▼
Backend API (/api/v1/*)
     │
     ▼
FastAPI Router → Service Layer → Repository → DB
```

**Servis Dosyaları:**
- `auth-service.ts` — kimlik doğrulama
- `trip-service.ts` — sefer CRUD
- `fuel-service.ts` — yakıt verileri
- `driver-service.ts` — sürücü işlemleri
- `vehicle-service.ts` — araç işlemleri
- `location-service.ts` — konum
- `weather-service.ts` — hava durumu
- `prediction-service.ts` — ML tahminleri
- `ai-service.ts` — AI sohbet/RAG
- `report-service.ts` — raporlar
- `ws-service.ts` — WebSocket bağlantısı
- `admin-service.ts` — admin işlemleri
- `notification-service.ts` — bildirimler
- `preference-service.ts` — kullanıcı tercihleri

---

## 6. Hata Yönetimi

**Backend (main.py):**
```
Tüm hatalar → {"error": {"code": "...", "message": "...", "trace_id": "..."}}
```
- 400, 401, 403, 404, 422, 500 → standart format
- `X-Correlation-ID` header ile her istek takip edilir

**Frontend (axios-instance.ts):**
```
401 → auto refresh → retry → logout (hepsi başarısızsa)
403 → toast: "Yetkisiz erişim"
400 → toast: hata mesajı
422 → toast: validasyon hatası
500 → toast: sunucu hatası
Network hatası → toast: bağlantı kontrolü
```

---

## 7. Özet

| Başlık | Detay |
|--------|-------|
| **İletişim Türü** | REST + WebSocket |
| **Proxy (Dev)** | Vite → Backend (`/api` → `127.0.0.1:8080`) |
| **Proxy (Prod)** | Nginx reverse proxy |
| **Auth** | JWT (access + refresh token) |
| **API Versiyonu** | v1 |
| **Modül Sayısı** | ~30 modül, ~100+ endpoint |
| **WebSocket** | Admin + genel kanallar |
| **Hata Formatı** | Standart JSON envelope (backend) → toast bildirimleri (frontend) |
