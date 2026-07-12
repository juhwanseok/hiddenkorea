"""숨은한국 FastAPI — W2 혼잡도 엔진.

로컬 실행: uvicorn app.main:app --reload  (apps/api 에서)
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .core.db import connect
from .schemas import (
    AlternativesResponse, CongestionResponse, CourseResponse, Health, PlaceHit,
)
from .services import congestion as cong
from .services import course as course_svc
from .services import matching
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


@app.get("/api/places/search", response_model=list[PlaceHit])
def search_places(
    q: str = Query(..., min_length=1, description="관광지명 검색"),
    limit: int = Query(10, ge=1, le=30),
) -> list[PlaceHit]:
    con = connect()
    try:
        # 집중률 링크(예보 가능) POI 우선, 이미지 있는 것 우선
        rows = con.execute(
            """SELECT p.contentid, p.title, p.addr1, p.contenttypeid, p.firstimage, p.mapx, p.mapy,
                      (SELECT 1 FROM poi_congestion_link l WHERE l.contentid=p.contentid) linked
               FROM places p
               WHERE p.title LIKE ? AND p.mapx<>''
               ORDER BY linked DESC, (p.firstimage<>'') DESC, LENGTH(p.title) ASC
               LIMIT ?""", (f"%{q}%", limit)).fetchall()
        def num(v):
            try: return float(v)
            except (TypeError, ValueError): return None
        return [PlaceHit(contentId=r["contentid"], title=r["title"], addr=r["addr1"] or None,
                         contentTypeId=r["contenttypeid"], image=r["firstimage"] or None,
                         lat=num(r["mapy"]), lon=num(r["mapx"])) for r in rows]
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
            "SELECT title, ldongRegnCd, ldongSignguCd FROM places WHERE contentid=?", (contentId,)
        ).fetchone()
        if not poi:
            raise HTTPException(404, "존재하지 않는 contentId")
        signgu = f"{poi['ldongRegnCd']}{poi['ldongSignguCd']}"
        spot = cong.resolve_spot(con, contentId)
        if spot:
            result = cong.congestion_by_spot(con, spot["signguCd"], spot["tAtsNm"], date, contentId)
            if result:
                return CongestionResponse(**result)
        # 미커버 → 폴백
        return CongestionResponse(**cong.congestion_fallback(con, signgu, poi["title"], date, contentId))
    finally:
        con.close()


@app.get("/api/alternatives", response_model=AlternativesResponse)
def alternatives(
    contentId: str = Query(..., description="원본 POI contentid"),
    date: str = Query(..., description="YYYY-MM-DD"),
    k: int = Query(3, ge=1, le=10),
) -> AlternativesResponse:
    con = connect()
    try:
        origin = con.execute("SELECT title FROM places WHERE contentid=?", (contentId,)).fetchone()
        if not origin:
            raise HTTPException(404, "존재하지 않는 contentId")
        alts = matching.alternatives(contentId, date, k=k)
        if not alts:
            raise HTTPException(422, "대안 후보 없음(임베딩 풀 밖이거나 인근 대안 부재)")
        for a in alts:
            a["reason"] = llm_reason(origin["title"], "", a, a.get("addr") or "")
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
