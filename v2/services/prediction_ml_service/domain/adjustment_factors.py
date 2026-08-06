"""Yakıt tüketimi multiplicative düzeltme faktörleri (Phase 4.2).

Plan §12.6 (P4.D5 literatür sentezi):

| Faktör | Mevcut kod | Bu modül | Literatür |
|---|---|---|---|
| Driver (sofor_score) | predict_consumption:676 | reuse | HDV %15-29 → ±%20 OK |
| Vehicle age (yıpranma) | Arac.yas_faktoru | reuse | VECTO 1-2%/yıl |
| Maintenance | compute_maintenance_factor | reuse | 0.95-1.25 clamp |
| Seasonal (kış/yaz) | WeatherService.get_seasonal_factor | reuse | 1.0/1.03/1.05/1.10 |
| **Hava sıcaklığı (gerçek)** | YOK | YENİ | EPA cold -10°C %15-24 |
| **Rüzgar (head/tailwind)** | YOK | YENİ | 10 km/h headwind ~%10 yakıt |
| **Yağış / kar** | YOK | YENİ | EPA winter poor %7-35 |

Bu modül **sadece yeni hava faktörlerini** + birleştirme helper'ını içerir.
Mevcut faktörleri yeniden yazmaz — caller (P4.3 SeferFuelEstimator) onları
predict_consumption mantığından alır.

ÇİFT SAYMA UYARISI: temperature_factor ve seasonal_factor ikisi de hava
etkisi. Kullanım: ``combine_factors`` içinde ``max(temp_factor, seasonal)``
alınır — gerçek sıcaklık varsa o, yoksa seasonal fallback.
"""

from __future__ import annotations

from typing import Optional

from app.config import settings


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def weather_temperature_factor(temp_c: Optional[float]) -> float:
    """Anlık sıcaklığa göre yakıt çarpanı.

    Plan §3.4.1 (D5 literatür uyumlu):
      - <5°C  → cold start + warmup penalty: 1.0 + (5 - temp) × 0.012
                örn. -10°C → +%18 (EPA %15-24 bandı içinde)
      - >28°C → AC yükü: 1.0 + (temp - 28) × 0.008
                örn. 40°C → +%10 (literatür %5-10)
      - Aralık → 1.0 (no-op)

    Args:
        temp_c: Anlık sıcaklık (°C). None → 1.0 (no-op, weather verisi yok).

    Returns:
        Çarpan clamp(0.95, 1.20).
    """
    if temp_c is None:
        return 1.0
    if temp_c < 5:
        factor = 1.0 + (5.0 - temp_c) * 0.012
    elif temp_c > 28:
        factor = 1.0 + (temp_c - 28.0) * 0.008
    else:
        factor = 1.0
    return _clamp(factor, 0.95, 1.20)


def weather_wind_factor(
    wind_speed_kmh: Optional[float],
    wind_bearing_deg: Optional[float] = None,
    segment_bearing_deg: Optional[float] = None,
) -> float:
    """Rüzgarın yakıta etkisi — headwind / tailwind / crosswind ayrımı.

    Plan §3.4.2 (D5 düzeltme: coefficient 0.010, clamp genişletildi):
      - Headwind (relative 135°-225°): +0.010 × wind_speed (10 km/h → +%10)
      - Tailwind (relative <45° veya >315°): -0.002 × wind_speed
      - Crosswind: +0.001 × wind_speed
      - Yön bilinmiyorsa: orta seviye +0.005 × wind_speed (kabaca)

    Args:
        wind_speed_kmh: Rüzgar hızı (km/h). None → 1.0.
        wind_bearing_deg: Rüzgarın GELDİĞİ yön (0-360°). None → orta hesap.
        segment_bearing_deg: Sefer rotasının GİTTİĞİ yön. None → orta hesap.

    Returns:
        Çarpan clamp(0.85, 1.30). Headwind 30 km/h fırtınada +%30 üst sınır.
    """
    if wind_speed_kmh is None or wind_speed_kmh <= 0:
        return 1.0

    if wind_bearing_deg is None or segment_bearing_deg is None:
        # Yön yok — orta katsayı (literatürün ortalama davranışı)
        factor = 1.0 + wind_speed_kmh * 0.005
    else:
        # Rüzgar geldiği yön; segment gittiği yön. Headwind = ters yönler.
        # relative = wind direction - segment direction
        relative = (wind_bearing_deg - segment_bearing_deg) % 360
        if relative > 180:
            relative = 360 - relative  # 0-180° banda indir

        if relative <= 45:
            # Tailwind (yardımcı rüzgar): yakıt azalır
            factor = 1.0 - wind_speed_kmh * 0.002
        elif relative >= 135:
            # Headwind (ters rüzgar): drag ²× artar, yakıt %10/10km/h
            factor = 1.0 + wind_speed_kmh * 0.010
        else:
            # Crosswind: az etki
            factor = 1.0 + wind_speed_kmh * 0.001

    # Faz 7 — üst sınır config cap (fiziksel: ağır araç highway drag tipik
    # +%5-10; tipik rüzgârda >cap fiziksel beklenmez, compound taşmayı keser).
    return _clamp(factor, 0.85, settings.WEATHER_WIND_FACTOR_MAX)


def weather_precipitation_factor(
    precip_mm: Optional[float], snowfall_cm: Optional[float] = None
) -> float:
    """Yağış (yağmur + kar) yakıt çarpanı.

    Plan §3.4.3 (D5 EPA winter poor road %7-35 bandı uyumlu):
      - Kuru (<0.5mm): 1.0
      - Hafif yağmur (<5mm/h): 1.03
      - Orta yağmur (<20mm/h): 1.06
      - Şiddetli yağmur (≥20mm/h): 1.10
      - Kar varsa: minimum 1.12 (slippery sürüş, alt-vites)

    Args:
        precip_mm: Mevcut saatte birikim (mm). None → 1.0.
        snowfall_cm: Kar (cm). None veya 0 → atlanır.

    Returns:
        Çarpan clamp(1.0, 1.20).
    """
    if precip_mm is None or precip_mm < 0:
        precip_mm = 0.0

    if precip_mm < 0.5:
        rain_factor = 1.0
    elif precip_mm < 5:
        rain_factor = 1.03
    elif precip_mm < 20:
        rain_factor = 1.06
    else:
        rain_factor = 1.10

    if snowfall_cm and snowfall_cm > 0:
        rain_factor = max(rain_factor, 1.12)

    return _clamp(rain_factor, 1.0, 1.20)


def combine_factors(
    driver: float = 1.0,
    vehicle_age: float = 1.0,
    maintenance: float = 1.0,
    weather_temperature: float = 1.0,
    weather_wind: float = 1.0,
    weather_precipitation: float = 1.0,
    seasonal: float = 1.0,
) -> float:
    """Tüm faktörleri tek bir multiplicative çarpana indir.

    ÇİFT SAYMA KONTROLÜ:
    - ``weather_temperature`` ve ``seasonal`` ikisi de hava → ``max()`` alınır.
      Gerçek sıcaklık varsa o (cold start +%18); yoksa seasonal fallback
      (kış genel +%10).

    Returns:
        Toplam çarpan clamp(0.7, 1.5). Sıra dışı kombinasyon koruması.
    """
    # Hava: temperature gerçekse o, değilse seasonal
    weather_combined = max(weather_temperature, seasonal)
    total = (
        driver
        * vehicle_age
        * maintenance
        * weather_combined
        * weather_wind
        * weather_precipitation
    )
    return _clamp(total, 0.7, 1.5)


__all__ = [
    "weather_temperature_factor",
    "weather_wind_factor",
    "weather_precipitation_factor",
    "combine_factors",
]
