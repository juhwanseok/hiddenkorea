"""여행 일정 추천 — 지역+기간+장르 → 날짜별 한적한 곳 배치 다일정.

핵심: 오버투어리즘 분산 목적에 맞게, 선택 지역·장르의 POI를 '그날 덜 붐비는' 순으로
      날짜에 배분(중복 없이)하고, 각 날의 방문 순서는 동선 최적화(2-opt).
혼잡: 집중률 커버 POI는 예보값, 미커버는 ML 갭모델(배치).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from ..core.constants import GENRES
from . import gap_model
from .course import _haversine_matrix, _nearest_neighbor, _two_opt

WD = ["월", "화", "수", "목", "금", "토", "일"]
MAX_DAYS = 5
CAND_LIMIT = 90
SPOTS_PER_DAY = 4
SPEED_KMH = 25.0
DWELL_MIN = 90


def _dates(start: str, end: str) -> list[str]:
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    if e < s:
        s, e = e, s
    n = min((e - s).days + 1, MAX_DAYS)
    return [(s + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]


def _candidates(con: sqlite3.Connection, area: str, signgu: str, ctids: list[str]) -> list[dict]:
    where = ["p.ldongRegnCd=?", "p.mapx<>''", "p.title<>''",
             f"p.contenttypeid IN ({','.join('?'*len(ctids))})"]
    args: list = [area, *ctids]
    if signgu:
        where.insert(1, "p.ldongSignguCd=?")
        args.insert(1, signgu[len(area):] if signgu.startswith(area) else signgu)
    rows = con.execute(
        f"""SELECT p.contentid, p.title, p.mapx, p.mapy, p.firstimage, p.contenttypeid,
                   p.ldongRegnCd, p.ldongSignguCd, p.lclsSystm1, p.lclsSystm2,
                   (p.ldongRegnCd||p.ldongSignguCd) AS signguCd,
                   (SELECT 1 FROM poi_congestion_link l WHERE l.contentid=p.contentid) AS linked
            FROM places p WHERE {' AND '.join(where)}
            ORDER BY (p.firstimage<>'') DESC, LENGTH(p.title) ASC
            LIMIT {CAND_LIMIT}""", args).fetchall()
    return [dict(r) for r in rows]


def _congestion_matrix(con: sqlite3.Connection, cands: list[dict], days: list[str]) -> dict:
    """(contentid, date) → 혼잡지수. 링크=예보, 미링크=ML배치."""
    m: dict[tuple[str, str], float] = {}
    ymds = [d.replace("-", "") for d in days]
    linked = [c for c in cands if c["linked"]]
    if linked:
        ph = ",".join("?" * len(linked))
        yph = ",".join("?" * len(ymds))
        rows = con.execute(
            f"""SELECT l.contentid c, cf.baseYmd y, cf.cnctrRate r
                FROM poi_congestion_link l
                JOIN congestion_forecast cf ON l.signguCd=cf.signguCd AND l.tAtsNm=cf.tAtsNm
                WHERE l.contentid IN ({ph}) AND cf.baseYmd IN ({yph})""",
            [c["contentid"] for c in linked] + ymds).fetchall()
        for r in rows:
            m[(r["c"], f"{r['y'][:4]}-{r['y'][4:6]}-{r['y'][6:8]}")] = float(r["r"])
    # 미링크 → ML 배치
    unl = [c for c in cands if not c["linked"]]
    batch, keys = [], []
    for c in unl:
        for d in days:
            batch.append((c["ldongRegnCd"], c["lclsSystm1"], c["lclsSystm2"], d))
            keys.append((c["contentid"], d))
    preds = gap_model.predict_batch(batch) if batch else None
    if preds:
        for k, v in zip(keys, preds):
            m[k] = v
    # 남은 결측(모델 없음) → 중립값
    for c in cands:
        for d in days:
            m.setdefault((c["contentid"], d), 50.0)
    return m


def _order_day(spots: list[dict]) -> list[dict]:
    if len(spots) < 2:
        return spots
    D = _haversine_matrix([s["mapy"] and float(s["mapy"]) for s in spots],
                          [s["mapx"] and float(s["mapx"]) for s in spots])
    order = _two_opt(_nearest_neighbor(D, 0), D)
    t = datetime.strptime("09:00", "%H:%M")
    out = []
    for seq, idx in enumerate(order):
        s = spots[idx]
        if seq > 0:
            km = float(D[order[seq - 1], idx])
            t += timedelta(minutes=km / SPEED_KMH * 60)
        out.append({**s, "seq": seq + 1, "arrive": t.strftime("%H:%M")})
        t += timedelta(minutes=DWELL_MIN)
    return out


def build_itinerary(con: sqlite3.Connection, area: str, signgu: str, genre: str,
                    start: str, end: str) -> dict | None:
    ctids = GENRES.get(genre, GENRES["관광지"])
    days = _dates(start, end)
    cands = _candidates(con, area, signgu, ctids)
    if not cands:
        return None
    cong = _congestion_matrix(con, cands, days)

    used: set[str] = set()
    day_plans = []
    for d in days:
        pool = [c for c in cands if c["contentid"] not in used]
        pool.sort(key=lambda c: cong[(c["contentid"], d)])   # 그날 덜 붐비는 순
        pick = pool[:SPOTS_PER_DAY]
        used.update(c["contentid"] for c in pick)
        legs = _order_day([{
            "contentId": c["contentid"], "name": c["title"],
            "mapx": c["mapx"], "mapy": c["mapy"],
            "lat": float(c["mapy"]), "lon": float(c["mapx"]),
            "image": c["firstimage"] or None,
            "congestion": round(cong[(c["contentid"], d)], 1),
        } for c in pick])
        avg = round(sum(l["congestion"] for l in legs) / len(legs), 1) if legs else 0
        wd = WD[datetime.strptime(d, "%Y-%m-%d").weekday()]
        day_plans.append({"date": d, "weekday": wd, "avgCongestion": avg,
                          "stops": [{k: v for k, v in l.items() if k not in ("mapx", "mapy")} for l in legs]})

    from .regions import _load as _rload
    rl = _rload()
    area_nm = rl["sido"].get(area, area)
    sg_nm = next((s["name"] for s in rl["sigungu"].get(area, []) if s["code"] == signgu), None) if signgu else None
    return {"areaName": area_nm, "signguName": sg_nm, "genre": genre,
            "startDate": days[0], "endDate": days[-1], "days": day_plans}
