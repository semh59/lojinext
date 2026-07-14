"""Saf hesaplama: yakıt periyodu türetme + sefer eşleştirme (DB'siz).

``application/calculate_period.py`` ve ``application/distribute_fuel_to_trips.py``
bu fonksiyonları ``asyncio.to_thread`` ile sarar.
"""

from dataclasses import dataclass
from itertools import groupby
from typing import Dict, List

from app.config import settings
from app.core.entities import Sefer, YakitAlimi, YakitPeriyodu
from app.infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PeriyotSeferMatch:
    """Periyot-sefer eşleştirme sonucu"""

    periyot: YakitPeriyodu
    seferler: List[Sefer]
    toplam_mesafe: float
    dagitim_yapildi: bool


def evaluate_consumption_status(consumption: float) -> str:
    """Tüketim durumunu değerlendir"""
    if consumption < 10:
        return "VERI HATASI"
    elif consumption < 28:
        return "MÜKEMMEL"
    elif consumption < 32:
        return "İYİ"
    elif consumption < 38:
        return "NORMAL"
    elif consumption < 45:
        return "YÜKSEK"
    else:
        return "KRİTİK"


def sync_create_fuel_periods(fuel_records: List[YakitAlimi]) -> List[YakitPeriyodu]:
    """İki yakıt alımı arası periyotları oluştur (Sync)"""
    if len(fuel_records) < 2:
        return []

    sorted_records = fuel_records
    periods = []

    for arac_id, group in groupby(sorted_records, key=lambda x: x.arac_id):
        records = list(group)

        # Find the first FULL tank to start calculations reliably
        start_idx = -1
        for k in range(len(records)):
            status = str(getattr(records[k], "depo_durumu", "") or "").lower()
            if "dolu" in status or "full" in status:
                start_idx = k
                break

        if start_idx == -1:
            logger.info(f"Vehicle {arac_id} has no 'full' tank records. Skipping.")
            continue

        i = start_idx
        while i < len(records) - 1:
            r1 = records[i]

            # Aggregate liters until next FULL tank
            aggregated_liters = 0.0
            next_full_idx = -1

            for j in range(i + 1, len(records)):
                current_r = records[j]
                aggregated_liters += current_r.litre

                depo_status = str(getattr(current_r, "depo_durumu", "") or "").lower()
                if "dolu" in depo_status or "full" in depo_status:
                    next_full_idx = j
                    break

            if next_full_idx == -1:
                # No full tank record found after this point, cannot accurately calculate consumption
                break

            r2 = records[next_full_idx]
            distance = r2.km_sayac - r1.km_sayac

            if distance <= 0:
                i = next_full_idx
                continue

            consumption = (aggregated_liters / distance) * 100

            period = YakitPeriyodu(
                arac_id=arac_id,
                alim1_id=r1.id,
                alim2_id=r2.id,
                alim1_tarih=r1.tarih,
                alim1_km=r1.km_sayac,
                alim1_litre=r1.litre,
                alim2_tarih=r2.tarih,
                alim2_km=r2.km_sayac,
                ara_mesafe=distance,
                toplam_yakit=round(aggregated_liters, 2),
                ort_tuketim=round(consumption, 2),
                durum=evaluate_consumption_status(consumption),
            )
            periods.append(period)
            i = next_full_idx

    return periods


def sync_distribute_fuel_to_trips(
    period: YakitPeriyodu, trips: List[Sefer]
) -> List[Sefer]:
    """Periyottaki yakıtı seferlere Ton-Km oranında dağıt (Sync)"""
    if not trips:
        return trips

    # HGV_EMPTY_WEIGHT config'de kg cinsinden; load_ton ton cinsinden.
    # Birim tutarlılığı için kg'ı tona çevir.
    empty_weight_ton = settings.HGV_EMPTY_WEIGHT / 1000.0
    trip_factors = []
    total_factor = 0.0

    for trip in trips:
        load_ton = (trip.net_kg or 0) / 1000.0 if trip.net_kg else (trip.ton or 0.0)
        total_mass = empty_weight_ton + load_ton
        factor = trip.mesafe_km * total_mass if trip.mesafe_km > 0 else 0
        trip_factors.append(factor)
        total_factor += factor

    if total_factor <= 0:
        total_distance = sum(t.mesafe_km for t in trips)
        if total_distance == 0:
            return trips
        remaining_fuel = period.toplam_yakit
        for i, trip in enumerate(trips):
            weight = trip.mesafe_km / total_distance
            fuel = (
                round(period.toplam_yakit * weight, 2)
                if i < len(trips) - 1
                else round(remaining_fuel, 2)
            )
            remaining_fuel -= fuel
            trip.dagitilan_yakit, trip.tuketim, trip.periyot_id = (
                fuel,
                round((fuel / trip.mesafe_km * 100), 2) if trip.mesafe_km else 0,
                period.id,
            )
        return trips

    remaining_fuel = period.toplam_yakit
    for i, trip in enumerate(trips):
        ratio = trip_factors[i] / total_factor
        fuel_allocated = (
            round(period.toplam_yakit * ratio, 2)
            if i < len(trips) - 1
            else round(remaining_fuel, 2)
        )
        remaining_fuel -= fuel_allocated
        trip.dagitilan_yakit = fuel_allocated
        trip.tuketim = (
            round((fuel_allocated / trip.mesafe_km) * 100, 2)
            if trip.mesafe_km > 0
            else 0.0
        )
        trip.periyot_id = period.id
    return trips


def sync_match_periods_with_trips(
    periods: List[YakitPeriyodu], all_trips: List[Sefer]
) -> List[PeriyotSeferMatch]:
    """Periyotları ilgili seferlerle eşleştir (Sync)"""
    matches = []
    trip_index: Dict[int, List[Sefer]] = {}
    for trip in all_trips:
        if trip.arac_id not in trip_index:
            trip_index[trip.arac_id] = []
        trip_index[trip.arac_id].append(trip)

    for period in periods:
        matching_trips = [
            t
            for t in trip_index.get(period.arac_id, [])
            if period.alim1_tarih <= t.tarih < period.alim2_tarih
        ]
        if matching_trips:
            matching_trips = sync_distribute_fuel_to_trips(period, matching_trips)
        matches.append(
            PeriyotSeferMatch(
                periyot=period,
                seferler=matching_trips,
                toplam_mesafe=sum((t.mesafe_km for t in matching_trips), 0.0),
                dagitim_yapildi=len(matching_trips) > 0,
            )
        )
    return matches
