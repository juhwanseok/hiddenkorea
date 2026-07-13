"""여행 일정 추천 — 가이드북형 슬롯 배치 (DECISION_LOG #18, #19).

실제 여행가이드처럼 하루를 시간대 슬롯으로 구성:
  오전 관광 → 점심(식당) → 오후 관광/쇼핑 → 카페 → (오후 관광) → 저녁(식당)
- 식사는 실제 식사 시간(12:00 점심 / 18:30 저녁)에 고정 배치.
- 장르 다중 선택. 관광류만 고르면 식사 자동 삽입, 식도락만 고르면 관광 자동 연계.
- 각 슬롯은 해당 지역·카테고리에서 '그날 덜 붐비는 곳'을 중복 없이 선택.
혼잡: 링크 POI=집중률 예보, 미링크=ML 갭모델 배치.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from ..core.constants import GENRES
from . import gap_model
from .regions import _load as _rload

WD = ["월", "화", "수", "목", "금", "토", "일"]
MAX_DAYS = 5
CAND_LIMIT = 120
FOOD_CT = ["39"]        # 음식점
CAFE_HINT = ("카페", "커피", "베이커리", "디저트", "빵", "브런치")

# 하루 슬롯 (시각, 종류, 라벨). 종류: act=관광/쇼핑, meal=식사, cafe=카페
SLOTS = [
    ("09:30", "act", "오전 관광"),
    ("12:00", "meal", "점심"),
    ("14:00", "act", "오후 관광"),
    ("15:30", "cafe", "카페·디저트"),
    ("17:00", "act", "관광·쇼핑"),
    ("18:30", "meal", "저녁"),
]


def _dates(start: str, end: str) -> list[str]:
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    if e < s:
        s, e = e, s
    n = min((e - s).days + 1, MAX_DAYS)
    return [(s + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]


def _resolve_cts(genres: list[str]) -> tuple[list[str], bool]:
    """선택 장르 → (관광/쇼핑 활동 타입, 식도락 포함여부). 활동 없으면 관광지 기본."""
    act: list[str] = []
    food = False
    for g in genres:
        if g == "식도락":
            food = True
        else:
            act += GENRES.get(g, [])
    act = list(dict.fromkeys(act)) or ["12"]   # 기본 관광지
    return act, food


def _candidates(con: sqlite3.Connection, area: str, signgu: str, ctids: list[str]) -> list[dict]:
    where = ["p.ldongRegnCd=?", "p.mapx<>''", "p.title<>''",
             f"p.contenttypeid IN ({','.join('?'*len(ctids))})"]
    args: list = [area, *ctids]
    if signgu:
        where.insert(1, "p.ldongSignguCd=?")
        args.insert(1, signgu[len(area):] if signgu.startswith(area) else signgu)
    rows = con.execute(
        f"""SELECT p.contentid, p.title, p.mapx, p.mapy, p.firstimage, p.contenttypeid,
                   p.ldongRegnCd, p.lclsSystm1, p.lclsSystm2,
                   (p.ldongRegnCd||p.ldongSignguCd) AS signguCd,
                   (SELECT 1 FROM poi_congestion_link l WHERE l.contentid=p.contentid) AS linked
            FROM places p WHERE {' AND '.join(where)}
            ORDER BY (p.firstimage<>'') DESC, LENGTH(p.title) ASC
            LIMIT {CAND_LIMIT}""", args).fetchall()
    return [dict(r) for r in rows]


def _congestion(con: sqlite3.Connection, cands: list[dict], days: list[str]) -> dict:
    m: dict[tuple[str, str], float] = {}
    ymds = [d.replace("-", "") for d in days]
    linked = [c for c in cands if c["linked"]]
    if linked:
        ph = ",".join("?" * len(linked)); yph = ",".join("?" * len(ymds))
        rows = con.execute(
            f"""SELECT l.contentid c, cf.baseYmd y, cf.cnctrRate r FROM poi_congestion_link l
                JOIN congestion_forecast cf ON l.signguCd=cf.signguCd AND l.tAtsNm=cf.tAtsNm
                WHERE l.contentid IN ({ph}) AND cf.baseYmd IN ({yph})""",
            [c["contentid"] for c in linked] + ymds).fetchall()
        for r in rows:
            m[(r["c"], f"{r['y'][:4]}-{r['y'][4:6]}-{r['y'][6:8]}")] = float(r["r"])
    unl = [c for c in cands if not c["linked"]]
    batch, keys = [], []
    for c in unl:
        for d in days:
            batch.append((c["ldongRegnCd"], c["lclsSystm1"], c["lclsSystm2"], d)); keys.append((c["contentid"], d))
    preds = gap_model.predict_batch(batch) if batch else None
    if preds:
        for k, v in zip(keys, preds):
            m[k] = v
    for c in cands:
        for d in days:
            m.setdefault((c["contentid"], d), 50.0)
    return m


def _is_cafe(c: dict) -> bool:
    return any(h in (c["title"] or "") for h in CAFE_HINT)


def _mk_stop(c: dict, seq: int, time: str, label: str, kind: str, cong: float) -> dict:
    return {"seq": seq, "contentId": c["contentid"], "name": c["title"], "arrive": time,
            "label": label, "kind": kind, "lat": float(c["mapy"]), "lon": float(c["mapx"]),
            "image": c["firstimage"] or None, "congestion": round(cong, 1)}


def build_itinerary(con: sqlite3.Connection, area: str, signgu: str, genres: list[str],
                    start: str, end: str) -> dict | None:
    act_ct, want_food = _resolve_cts(genres)
    days = _dates(start, end)
    act_pool = _candidates(con, area, signgu, act_ct)
    food_pool = _candidates(con, area, signgu, FOOD_CT)
    if not act_pool and not food_pool:
        return None
    cong = _congestion(con, act_pool + food_pool, days)

    # 슬롯 구성: 식도락만 골랐어도 관광 섞고, 관광만 골랐어도 식사 자동 삽입.
    slots = list(SLOTS)
    if not food_pool:                       # 식당 없으면 식사/카페 슬롯 제거
        slots = [s for s in slots if s[1] == "act"]

    used: set[str] = set()

    def pick(pool: list[dict], day: str, cafe=False) -> dict | None:
        cand = [c for c in pool if c["contentid"] not in used]
        if cafe:
            cafes = [c for c in cand if _is_cafe(c)]
            cand = cafes or cand            # 카페 우선, 없으면 일반 식당
        if not cand:
            return None
        cand.sort(key=lambda c: cong[(c["contentid"], day)])   # 덜 붐비는 순
        return cand[0]

    day_plans = []
    for d in days:
        stops = []
        seq = 1
        for time, kind, label in slots:
            pool = food_pool if kind in ("meal", "cafe") else act_pool
            c = pick(pool, d, cafe=(kind == "cafe"))
            if not c:
                continue
            used.add(c["contentid"])
            stops.append(_mk_stop(c, seq, time, label, kind, cong[(c["contentid"], d)]))
            seq += 1
        act_stops = [s for s in stops if s["kind"] == "act"]
        avg = round(sum(s["congestion"] for s in act_stops) / len(act_stops), 1) if act_stops else 0.0
        wd = WD[datetime.strptime(d, "%Y-%m-%d").weekday()]
        day_plans.append({"date": d, "weekday": wd, "avgCongestion": avg, "stops": stops})

    rl = _rload()
    area_nm = rl["sido"].get(area, area)
    sg_nm = next((s["name"] for s in rl["sigungu"].get(area, []) if s["code"] == signgu), None) if signgu else None
    return {"areaName": area_nm, "signguName": sg_nm, "genre": ", ".join(genres) or "관광지",
            "startDate": days[0], "endDate": days[-1], "days": day_plans}
