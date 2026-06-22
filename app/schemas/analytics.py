"""Faz 3 — kullanım analitiği request/response şemaları."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PageViewCreate(BaseModel):
    route: str = Field(..., min_length=1, max_length=255)


class RouteCount(BaseModel):
    route: str
    count: int


class PageViewStats(BaseModel):
    period_days: int
    total_views: int
    top_routes: list[RouteCount]
    bottom_routes: list[RouteCount]
