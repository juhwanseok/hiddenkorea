"""숨은한국 FastAPI — W2 혼잡도 엔진.

로컬 실행: uvicorn app.main:app --reload  (apps/api 에서)
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .core.db import connect
from .schemas import CongestionResponse, Health
from .services import congestion as cong

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
