"""API 입출력 Pydantic 스키마 (프론트 lib/api-types.ts와 수동 동기화)."""
from __future__ import annotations

from pydantic import BaseModel


class DayCongestion(BaseModel):
    date: str          # YYYY-MM-DD
    index: float       # 0~100 혼잡 지수
    grade: str
    color: str


class CongestionResponse(BaseModel):
    contentId: str | None = None
    name: str
    signguCd: str
    date: str
    index: float
    grade: str
    color: str
    source: str        # KTO_FORECAST | HK_MODEL
    note: str | None = None
    series30d: list[DayCongestion]


class Health(BaseModel):
    status: str
    pois: int
    congestion_rows: int
