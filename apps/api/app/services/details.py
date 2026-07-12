"""POI 상세(overview '무엇을 할 수 있는지') 조회 — TourAPI detailCommon2 + DB 캐시.

쿼터 절약: 한 번 조회한 overview는 poi_detail 테이블에 캐시(재호출 없음).
"""
from __future__ import annotations

import re
import sqlite3

import httpx

from ..core.config import KOR_BASE, TOUR_COMMON, TOURAPI_KEY

_TAG = re.compile(r"<[^>]+>")


def _ensure_table(con: sqlite3.Connection) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS poi_detail (
        contentid TEXT PRIMARY KEY, overview TEXT, homepage TEXT, tel TEXT)""")


def _clean(s: str, limit: int = 600) -> str:
    s = _TAG.sub("", s or "").replace("&nbsp;", " ").strip()
    return s[:limit]


def get_detail(con: sqlite3.Connection, content_id: str) -> dict:
    _ensure_table(con)
    row = con.execute("SELECT overview, homepage, tel FROM poi_detail WHERE contentid=?",
                      (content_id,)).fetchone()
    if row:
        return {"contentId": content_id, "overview": row["overview"],
                "homepage": _clean(row["homepage"] or "", 300) or None, "tel": row["tel"] or None}

    overview = homepage = tel = ""
    if TOURAPI_KEY:
        try:
            r = httpx.get(f"{KOR_BASE}/detailCommon2",
                          params={"serviceKey": TOURAPI_KEY, "contentId": content_id, **TOUR_COMMON},
                          timeout=10.0)
            item = (r.json().get("response", {}).get("body", {}).get("items", {}) or {}).get("item", [])
            if isinstance(item, list):
                item = item[0] if item else {}
            overview = _clean(item.get("overview", ""))
            homepage = item.get("homepage", "")
            tel = item.get("tel", "")
        except Exception:  # noqa: BLE001 — 상세 실패해도 서비스 지속
            pass

    con.execute("INSERT OR REPLACE INTO poi_detail (contentid, overview, homepage, tel) VALUES (?,?,?,?)",
                (content_id, overview, homepage, tel))
    con.commit()
    return {"contentId": content_id, "overview": overview,
            "homepage": _clean(homepage, 300) or None, "tel": tel or None}
