"""Use-case: yakıt periyodu türetme (Async wrapper)."""

import asyncio
from typing import List

from app.core.entities import YakitAlimi, YakitPeriyodu
from v2.modules.fuel.domain.period_matcher import sync_create_fuel_periods


async def create_fuel_periods(fuel_records: List[YakitAlimi]) -> List[YakitPeriyodu]:
    """İki yakıt alımı arası periyotları oluştur (Async)"""
    return await asyncio.to_thread(sync_create_fuel_periods, fuel_records)
