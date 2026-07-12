"""혼잡도 서비스 — 하이브리드 엔진의 조회 계층.

설계 (ML_GUIDELINES 계층1):
- 집중률 커버 관광지: 공사 예측(cnctrRate) 직접 사용 → source=KTO_FORECAST
- 미커버 POI: 자체 ML 근사 (W2 후속) → source=HK_MODEL. v0는 시군구 평균 폴백.

cnctrRate 의미: 관광지 자체 기준 상대 혼잡(그 관광지 30일 중 피크=100).
→ 동일 관광지의 날짜 비교(US1/US4)에 정확. 관광지 '간' 절대 비교(US2)는 W3에서 시군구 방문량 보정.
"""
from __future__ import annotations

import re
import sqlite3

from ..core.constants import SRC_FORECAST, SRC_MODEL, grade_of

_WS = re.compile(r"\s+")
_PAREN = re.compile(r"\(.*?\)")


def norm_title(s: str) -> str:
    return _PAREN.sub("", _WS.sub("", (s or ""))).lower()


def ymd_to_iso(ymd: str) -> str:
    return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}" if len(ymd) == 8 else ymd


def resolve_spot(con: sqlite3.Connection, content_id: str) -> dict | None:
    """contentid → 집중률 관광지(signguCd, tAtsNm) 매핑. 링크 테이블 우선, 없으면 즉석 매칭."""
    row = con.execute(
        "SELECT signguCd, tAtsNm FROM poi_congestion_link WHERE contentid=?", (content_id,)
    ).fetchone()
    if row:
        return {"signguCd": row["signguCd"], "tAtsNm": row["tAtsNm"]}
    return None


def _series(con: sqlite3.Connection, signgu: str, name: str) -> list[dict]:
    rows = con.execute(
        """SELECT baseYmd, cnctrRate FROM congestion_forecast
           WHERE signguCd=? AND tAtsNm=? ORDER BY baseYmd""",
        (signgu, name),
    ).fetchall()
    out = []
    for r in rows:
        idx = round(float(r["cnctrRate"]), 1)
        g, c = grade_of(idx)
        out.append({"date": ymd_to_iso(r["baseYmd"]), "index": idx, "grade": g, "color": c})
    return out


def congestion_by_spot(con: sqlite3.Connection, signgu: str, name: str,
                       date_iso: str, content_id: str | None = None) -> dict | None:
    """집중률 커버 관광지의 (관광지, 날짜) 혼잡 조회 + 30일 시계열."""
    series = _series(con, signgu, name)
    if not series:
        return None
    day = next((d for d in series if d["date"] == date_iso), None)
    if day is None:  # 요청일이 예측 범위 밖 → 가장 가까운 마지막 값
        day = series[-1]
    return {
        "contentId": content_id, "name": name, "signguCd": signgu, "date": day["date"],
        "index": day["index"], "grade": day["grade"], "color": day["color"],
        "source": SRC_FORECAST, "note": None, "series30d": series,
    }


def congestion_fallback(con: sqlite3.Connection, signgu: str, name: str, date_iso: str,
                        content_id: str | None = None) -> dict:
    """미커버 POI 폴백 — 동일 시군구 평균 혼잡(자체 ML 대체 전 v0). source=HK_MODEL."""
    rows = con.execute(
        "SELECT AVG(cnctrRate) a FROM congestion_forecast WHERE signguCd=?", (signgu,)
    ).fetchone()
    idx = round(float(rows["a"]), 1) if rows and rows["a"] is not None else 50.0
    g, c = grade_of(idx)
    return {
        "contentId": content_id, "name": name, "signguCd": signgu, "date": date_iso,
        "index": idx, "grade": g, "color": c, "source": SRC_MODEL,
        "note": "집중률 미커버 지역 — 시군구 평균 기반 근사(추정)", "series30d": [],
    }
