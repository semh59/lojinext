# LojiNext AI Backend: Elite Logistics Intelligence

LojiNext, TIR filoları için AI destekli yakıt takibi, rota optimizasyonu ve anomali tespiti sunan, yüksek performanslı ve "Zero-Defect" mimarisine sahip bir backend sistemidir.

## 🚀 Mimari Vizyon (The Sovereign Architecture)

Sistem, modern kurumsal yazılım prensiplerini (SOLID, Clean Architecture) "Elite Engineering" dokunuşuyla birleştirir:

- **Service-Oriented Design**: Tüm iş mantığı API katmanından izole edilmiş, tekrar kullanılabilir servislerde toplanmıştır.
- **Unit of Work (UoW) & Repository Pattern**: Veritabanı işlemleri atomik, güvenli ve test edilebilir bir yapıda yönetilir.
- **Data Sovereignty & Security**: RBAC (Role-Based Access Control) ve Tenant/User bazlı dinamik veri izolasyonu (`apply_isolation`) ile maksimum güvenlik.
- **Smart Resilience**: Kendi kendini iyileştiren (Self-Healing) hata yakalama mekanizmaları ve gelişmiş diagnostic önerileri.
- **AI-Native Core**: Groq/RAG tabanlı akıllı analiz motoru ile sistem loglarından ve olaylardan otonom öğrenme.

## 🛠 Teknoloji Yığını

- **Core**: Python 3.12+, FastAPI
- **Database**: PostgreSQL (SQLAlchemy Async ORM)
- **AI/ML**: Groq Cloud Inference, RAG (Retrieval-Augmented Generation), Scikit-learn
- **Infrastructure**: Redis (Pattern-based Caching), Pydantic v2 (Strict Typing), EventBus (Async Events)
- **Quality**: Zero-Defect QA Strategy, Audit Logging, Automated Verification Suite

## 🏁 Geliştirme Fazları (Zero-Defect Journey)

1.  **Phase 1: Foundation Hardening**: DI, Repository katmanı ve UoW pattern kurulumu.
2.  **Phase 2: Security & RBAC**: Kimlik doğrulama, yetkilendirme ve veri izolasyonu.
3.  **Phase 3: Logic Precision**: Outlier Guard, fizik tabanlı yakıt modelleri ve finansal tutarlılık.
4.  **Phase 4: Resilience & Frontend Synergy**: AI Context entegrasyonu, EEI (Energy Efficiency Index) ve Pattern Cache.
5.  **Phase 5: Final Certification**: Endpoint-Service senkronizasyonu, 422 hata giderimi ve tam sistem doğrulaması.

## 📦 Kurulum ve Çalıştırma

```bash
# Bağımlılıkları yükle
pip install -r requirements.txt

# Veritabanı tablolarını oluştur (Dev ortamı)
python -m app.main

# Sunucuyu başlat
uvicorn app.main:app --reload
```

## 🧪 Doğrulama

Sistemin tam state'ini doğrulamak için:

```bash
python verify_certification.py
```

---

"Simple solutions to complex problems." - **Elite AI Team**
