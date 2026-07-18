"""route_simulation event tanımları.

Yok — bu modül hiçbir lifecycle/CRUD event'i yayınlamıyor ve dinlemiyor.
Simülasyon sonuçları (`route_simulations`/`route_segments`) senkron
persist edilir (`SimulationRepository`), event bus'a hiçbir `publish`
çağrısı yok (2026-07-18 denetiminde grep ile doğrulandı). İleride bir
SIMULATION_COMPLETED event'i gerekirse DTO'su buraya eklenir.
"""
