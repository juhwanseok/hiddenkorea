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


class PlaceDetail(BaseModel):
    contentId: str
    overview: str | None = None
    homepage: str | None = None
    tel: str | None = None


class Alternative(BaseModel):
    contentId: str
    name: str
    addr: str | None = None
    hiddenScore: float
    simPct: float
    congestion: float
    distanceKm: float
    reason: str
    overview: str | None = None


class AlternativesResponse(BaseModel):
    origin: str
    date: str
    count: int
    alternatives: list[Alternative]


class CourseLeg(BaseModel):
    seq: int
    contentId: str
    name: str
    arrive: str
    lat: float
    lon: float
    congestion: float | None = None
    image: str | None = None
    travelKmFromPrev: float


class CourseResponse(BaseModel):
    date: str
    startTime: str
    totalDistanceKm: float
    stops: int
    legs: list[CourseLeg]
    kakaoMapUrl: str
    narrative: str


class PlaceHit(BaseModel):
    contentId: str
    title: str
    addr: str | None = None
    contentTypeId: str
    image: str | None = None
    lat: float | None = None
    lon: float | None = None


class Region(BaseModel):
    code: str
    name: str


class ItineraryStop(BaseModel):
    seq: int
    contentId: str
    name: str
    arrive: str
    lat: float
    lon: float
    congestion: float
    image: str | None = None


class ItineraryDay(BaseModel):
    date: str
    weekday: str
    avgCongestion: float
    stops: list[ItineraryStop]


class ItineraryResponse(BaseModel):
    areaName: str
    signguName: str | None = None
    genre: str
    startDate: str
    endDate: str
    days: list[ItineraryDay]


class Health(BaseModel):
    status: str
    pois: int
    congestion_rows: int
