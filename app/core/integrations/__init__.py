"""3rd party provider entegrasyonları (AVL + Fuel Card).

Read-only akış: Provider → LojiNext. Periyodik poll veya webhook ile
veri çekilir, normalize edilir, idempotent insert yapılır (external_id
ile dedup).

Klasör yapısı:
  avl/         — Araç takip provider'ları (Mobiliz, Arvento, Vodafone, ...)
  fuel/        — Akaryakıt kart sistemleri (OPET, Shell, BP Truckmaster, ...)
  registry.py  — Provider key → adapter sınıfı eşleme
"""

"""
"""
