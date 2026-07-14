"""Use-case: periyot yakıtını seferlere dağıtma + periyot-sefer eşleştirme (Async wrapper)."""

import asyncio
from typing import List

from app.core.entities import Sefer, YakitPeriyodu
from v2.modules.fuel.domain.period_matcher import (
    PeriyotSeferMatch,
    sync_distribute_fuel_to_trips,
    sync_match_periods_with_trips,
)


async def distribute_fuel_to_trips(
    period: YakitPeriyodu, trips: List[Sefer]
) -> List[Sefer]:
    """Periyottaki yakıtı seferlere Ton-Km oranında dağıt (Async)"""
    return await asyncio.to_thread(sync_distribute_fuel_to_trips, period, trips)


async def match_periods_with_trips(
    periods: List[YakitPeriyodu], all_trips: List[Sefer]
) -> List[PeriyotSeferMatch]:
    """Periyotları ilgili seferlerle eşleştir (Async)"""
    return await asyncio.to_thread(sync_match_periods_with_trips, periods, all_trips)
