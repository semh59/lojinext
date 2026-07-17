"""ai_assistant event tanımları.

Bu modül kendi CRUD/lifecycle event'ini YAYINLAMAZ (DB tablosu sahibi
değil). ONLY bir event SUBSCRIBER'ı var: `infrastructure/rag/rag_sync_service.py`
`ARAC_ADDED/UPDATED`, `SOFOR_ADDED/UPDATED`, `SEFER_ADDED/UPDATED`
event'lerine abone olur ve FAISS RAG indeksini günceller.

🔴 Diğer modüllerin (notification/fleet/driver/fuel) dalgalarındaki
"event subscriber hiç wire edilmemiş, register_handlers() çağrılmıyor"
bulgusundan FARKLI olarak bu abonelik CANLI: `app/main.py`'nin lifespan
startup'ı `RAGSyncService().initialize()`'ı gerçekten çağırıyor (satır
~339, main.py taşınırken import path güncellendi).
"""
