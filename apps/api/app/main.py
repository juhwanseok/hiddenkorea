"""숨은한국 FastAPI — W2 혼잡도 엔진.

로컬 실행: uvicorn app.main:app --reload  (apps/api 에서)
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .core.db import connect
import random

from .core.constants import GENRE_ORDER, FOOD_CAT_ORDER
from .schemas import (
    AlternativesResponse, CongestionResponse, CourseResponse, Health, HighlightRegion,
    HighlightSpot, ItineraryResponse, PlaceDetail, PlaceHit, Region,
)
from .services import congestion as cong
from .services import course as course_svc
from .services import itinerary as itin
from .services import matching
from .services import regions as regions_svc
from .services import weather as weather_svc
from .services import realtime as realtime_svc
from .services.details import get_detail
from .services.reason import llm_reason

app = FastAPI(title="숨은한국 API", version="0.2.0")

origins = [o for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=["*"],
)


@app.get("/api/health", response_model=Health)
def health() -> Health:
    con = connect()
    try:
        pois = con.execute("SELECT COUNT(*) c FROM places").fetchone()["c"]
        try:
            cf = con.execute("SELECT COUNT(*) c FROM congestion_forecast").fetchone()["c"]
        except Exception:  # noqa: BLE001 — 적재 전이면 0
            cf = 0
        return Health(status="ok", pois=pois, congestion_rows=cf)
    finally:
        con.close()


@app.get("/api/regions", response_model=list[Region])
def regions(areaCd: str | None = Query(None, description="시도코드 주면 시군구, 없으면 시도 목록")):
    return regions_svc.sigungu_list(areaCd) if areaCd else regions_svc.sido_list()


@app.get("/api/genres", response_model=list[str])
def genres() -> list[str]:
    return GENRE_ORDER


@app.get("/api/food-categories", response_model=list[str])
def food_categories() -> list[str]:
    return FOOD_CAT_ORDER


@app.get("/api/itinerary", response_model=ItineraryResponse)
def itinerary(
    areaCd: str = Query(..., description="시도 행정표준코드"),
    startDate: str = Query(..., description="YYYY-MM-DD"),
    endDate: str = Query(..., description="YYYY-MM-DD"),
    genres: str = Query("관광지", description="장르 콤마구분 다중선택"),
    signguCd: str = Query("", description="시군구 5자리(선택)"),
    foodCat: str = Query("", description="음식 종류(한식/중식/일식/양식/분식·간식). 식도락 선택 시"),
) -> ItineraryResponse:
    glist = [g.strip() for g in genres.split(",") if g.strip()] or ["관광지"]
    con = connect()
    try:
        result = itin.build_itinerary(con, areaCd, signguCd, glist, startDate, endDate, food_cat=foodCat)
        if not result:
            raise HTTPException(404, "해당 지역·장르에 추천할 장소가 없습니다")
        return ItineraryResponse(**result)
    finally:
        con.close()


@app.get("/api/places/search", response_model=list[PlaceHit])
def search_places(
    q: str = Query(..., min_length=1, description="관광지명 검색"),
    areaCd: str | None = Query(None, description="시도 필터"),
    contentTypeId: str | None = Query(None, description="콘텐츠타입 필터"),
    limit: int = Query(10, ge=1, le=30),
) -> list[PlaceHit]:
    con = connect()
    try:
        where = ["p.title LIKE ?", "p.mapx<>''"]
        args: list = [f"%{q}%"]
        if areaCd:
            where.append("p.ldongRegnCd=?"); args.append(areaCd)
        if contentTypeId:
            where.append("p.contenttypeid=?"); args.append(contentTypeId)
        args.append(limit)
        # 집중률 링크(예보 가능) POI 우선, 이미지 있는 것 우선
        rows = con.execute(
            f"""SELECT p.contentid, p.title, p.addr1, p.contenttypeid, p.firstimage, p.mapx, p.mapy,
                      (SELECT 1 FROM poi_congestion_link l WHERE l.contentid=p.contentid) linked
               FROM places p
               WHERE {' AND '.join(where)}
               ORDER BY linked DESC, (p.firstimage<>'') DESC, LENGTH(p.title) ASC
               LIMIT ?""", args).fetchall()
        def num(v):
            try: return float(v)
            except (TypeError, ValueError): return None
        return [PlaceHit(contentId=r["contentid"], title=r["title"], addr=r["addr1"] or None,
                         contentTypeId=r["contenttypeid"], image=r["firstimage"] or None,
                         lat=num(r["mapy"]), lon=num(r["mapx"])) for r in rows]
    finally:
        con.close()


@app.get("/api/places/popular", response_model=list[PlaceHit])
def popular_places(n: int = Query(8, ge=1, le=20)) -> list[PlaceHit]:
    """검색창 포커스용 인기 관광지 — 집중률 커버+이미지 있는 관광지에서 랜덤(매번 바뀜)."""
    con = connect()
    try:
        rows = con.execute(
            """SELECT p.contentid, p.title, p.addr1, p.contenttypeid, p.firstimage, p.mapx, p.mapy
               FROM places p JOIN poi_congestion_link l ON p.contentid=l.contentid
               WHERE p.contenttypeid='12' AND p.firstimage<>''
               ORDER BY RANDOM() LIMIT ?""", (n,)).fetchall()
        def num(v):
            try: return float(v)
            except (TypeError, ValueError): return None
        return [PlaceHit(contentId=r["contentid"], title=r["title"], addr=r["addr1"] or None,
                         contentTypeId=r["contenttypeid"], image=r["firstimage"] or None,
                         lat=num(r["mapy"]), lon=num(r["mapx"])) for r in rows]
    finally:
        con.close()


@app.get("/api/highlights", response_model=list[HighlightRegion])
def highlights(
    date: str = Query(..., description="YYYY-MM-DD"),
    perRegion: int = Query(3, ge=1, le=6),
    regionsN: int = Query(6, ge=1, le=17),
) -> list[HighlightRegion]:
    """선택일에 '평소(자기 30일 평균)보다 한적한' 명소를 지역별로. 날짜 바뀌면 결과도 바뀜."""
    ymd = date.replace("-", "")
    con = connect()
    try:
        rows = con.execute(
            """SELECT l.contentid, p.title, p.firstimage, p.ldongRegnCd AS area,
                      st.today, st.avg_rate
               FROM (
                 SELECT signguCd, tAtsNm, AVG(cnctrRate) avg_rate,
                        AVG(CASE WHEN baseYmd=? THEN cnctrRate END) today
                 FROM congestion_forecast GROUP BY signguCd, tAtsNm
               ) st
               JOIN poi_congestion_link l ON st.signguCd=l.signguCd AND st.tAtsNm=l.tAtsNm
               JOIN places p ON l.contentid=p.contentid
               WHERE st.today IS NOT NULL AND st.avg_rate>0
                     AND st.today < st.avg_rate*0.85 AND st.today < 45 AND p.firstimage<>''""",
            (ymd,)).fetchall()
        from .services.regions import _load as rload
        sido = rload()["sido"]
        by_area: dict[str, list[dict]] = {}
        for r in rows:
            drop = int(round((1 - r["today"] / r["avg_rate"]) * 100))
            by_area.setdefault(r["area"], []).append({
                "contentId": r["contentid"], "name": r["title"],
                "today": round(r["today"], 1), "avg": round(r["avg_rate"], 1),
                "dropPct": drop, "image": r["firstimage"] or None})
        # 후보 지역(2곳 이상) 중 랜덤 선택 → 유동적
        areas = [a for a, v in by_area.items() if len(v) >= 2]
        random.shuffle(areas)
        out = []
        for a in areas[:regionsN]:
            spots = sorted(by_area[a], key=lambda s: s["today"])[:perRegion]
            out.append(HighlightRegion(areaName=sido.get(a, a),
                                       spots=[HighlightSpot(**s) for s in spots]))
        return out
    finally:
        con.close()


@app.get("/api/places/detail", response_model=PlaceDetail)
def place_detail(contentId: str = Query(..., description="TourAPI contentid")) -> PlaceDetail:
    con = connect()
    try:
        return PlaceDetail(**get_detail(con, contentId))
    finally:
        con.close()


@app.get("/api/congestion", response_model=CongestionResponse)
def congestion(
    contentId: str = Query(..., description="TourAPI contentid"),
    date: str = Query(..., description="YYYY-MM-DD"),
) -> CongestionResponse:
    con = connect()
    try:
        poi = con.execute(
            "SELECT title, ldongRegnCd, ldongSignguCd, lclsSystm1, lclsSystm2, mapx, mapy "
            "FROM places WHERE contentid=?", (contentId,)
        ).fetchone()
        if not poi:
            raise HTTPException(404, "존재하지 않는 contentId")
        signgu = f"{poi['ldongRegnCd']}{poi['ldongSignguCd']}"
        spot = cong.resolve_spot(con, contentId)
        if spot:
            result = cong.congestion_by_spot(con, spot["signguCd"], spot["tAtsNm"], date, contentId)
        else:  # 미커버 → ML 갭모델 폴백
            result = cong.congestion_fallback(
                con, signgu, poi["title"], date, contentId,
                area=poi["ldongRegnCd"] or "", lcls1=poi["lclsSystm1"] or "", lcls2=poi["lclsSystm2"] or "")
        # 날씨 연동(예보창 내 날짜만)
        try:
            result["weather"] = weather_svc.for_date(float(poi["mapy"]), float(poi["mapx"]), date)
        except (TypeError, ValueError):
            result["weather"] = None
        # 서울 주요 관광지 실시간 혼잡(citydata) — 예측과 병기
        result["realtime"] = realtime_svc.for_poi(poi["title"], poi["ldongRegnCd"] or "")
        return CongestionResponse(**result)
    finally:
        con.close()


@app.get("/api/alternatives", response_model=AlternativesResponse)
def alternatives(
    contentId: str = Query(..., description="원본 POI contentid"),
    date: str = Query(..., description="YYYY-MM-DD"),
    k: int = Query(3, ge=1, le=10),
    scope: str = Query("nearby", description="nearby(인근) | nationwide(전국 타지역)"),
) -> AlternativesResponse:
    con = connect()
    try:
        origin = con.execute("SELECT title FROM places WHERE contentid=?", (contentId,)).fetchone()
        if not origin:
            raise HTTPException(404, "존재하지 않는 contentId")
        alts = (matching.alternatives_nationwide(contentId, date, k=k) if scope == "nationwide"
                else matching.alternatives(contentId, date, k=k))
        if not alts:
            raise HTTPException(422, "대안 후보 없음(임베딩 풀 밖이거나 대안 부재)")
        for a in alts:
            a["reason"] = llm_reason(origin["title"], "", a, a.get("addr") or "")
            ov = get_detail(con, a["contentId"]).get("overview") or ""
            a["overview"] = ov[:160] or None      # 카드용 짧은 '무엇을 할 수 있는지'
        return AlternativesResponse(origin=origin["title"], date=date, count=len(alts), alternatives=alts)
    finally:
        con.close()


@app.get("/api/course", response_model=CourseResponse)
def course(
    poiIds: str = Query(..., description="쉼표구분 contentid (2개 이상)"),
    date: str = Query(..., description="YYYY-MM-DD"),
    startTime: str = Query("09:00"),
) -> CourseResponse:
    ids = [x.strip() for x in poiIds.split(",") if x.strip()]
    if len(ids) < 2:
        raise HTTPException(422, "코스는 2개 이상 장소 필요")
    con = connect()
    try:
        result = course_svc.build_course(con, ids, date, startTime)
        if not result:
            raise HTTPException(404, "유효한 좌표 POI가 2개 미만")
        return CourseResponse(**result)
    finally:
        con.close()
