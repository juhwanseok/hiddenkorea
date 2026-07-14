"""여행 일정 추천 — 가이드북형 슬롯 배치 (DECISION_LOG #18, #19).

실제 여행가이드처럼 하루를 시간대 슬롯으로 구성:
  오전 관광 → 점심(식당) → 오후 관광/쇼핑 → 카페 → (오후 관광) → 저녁(식당)
- 식사는 실제 식사 시간(12:00 점심 / 18:30 저녁)에 고정 배치.
- 장르 다중 선택. 관광류만 고르면 식사 자동 삽입, 식도락만 고르면 관광 자동 연계.
- 각 슬롯은 해당 지역·카테고리에서 '그날 덜 붐비는 곳'을 중복 없이 선택.
혼잡: 링크 POI=집중률 예보, 미링크=ML 갭모델 배치.
"""
from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timedelta

from ..core.constants import GENRES, FOOD_CATS
from . import gap_model
from . import weather as weather_svc
from .regions import _load as _rload

INDOOR_CT = ["14"]       # 문화시설(박물관·미술관·전시 등 = 실내). 악천후 시 우선

WD = ["월", "화", "수", "목", "금", "토", "일"]
MAX_DAYS = 5
CAND_LIMIT = 120
FOOD_CT = ["39"]         # 음식점(contenttypeid)
CAFE_LCLS2 = "FD05"      # 소분류 중분류: 카페·찻집(FD0501 카페 / FD0502 찻집 / FD0503 차) — 식사와 구분

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


def _sgu_code(area: str, sg: str) -> str:
    """전달된 시군구코드가 시도+시군구(예: 11110) 형태면 시군구부(110/11110→11110 저장형)로 정규화."""
    return sg[len(area):] if sg.startswith(area) and len(sg) > len(area) else sg


def _candidates(con: sqlite3.Connection, area: str, signgus: list[str], ctids: list[str],
                lcls2_in: str | None = None, lcls2_not: str | None = None,
                lcls3_in: list[str] | None = None) -> list[dict]:
    where = ["p.ldongRegnCd=?", "p.mapx<>''", "p.title<>''",
             f"p.contenttypeid IN ({','.join('?'*len(ctids))})"]
    args: list = [area, *ctids]
    if signgus:
        codes = [_sgu_code(area, s) for s in signgus if s]
        if codes:
            where.insert(1, f"p.ldongSignguCd IN ({','.join('?'*len(codes))})")
            for i, c in enumerate(codes):
                args.insert(1 + i, c)
    if lcls2_in:
        where.append("p.lclsSystm2=?"); args.append(lcls2_in)
    if lcls2_not:
        where.append("p.lclsSystm2<>?"); args.append(lcls2_not)
    if lcls3_in:
        where.append(f"p.lclsSystm3 IN ({','.join('?'*len(lcls3_in))})"); args += lcls3_in
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


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 간 거리(km)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# 거리 가중치: 점수 = 혼잡도(0~100) + DIST_W × 직전장소로부터 거리(km).
# 예) 5km 떨어지면 혼잡도 +15점과 동급 → 덜 붐비면서도 가까운 곳을 우선.
DIST_W = 3.0


def _mk_stop(c: dict, seq: int, time: str, label: str, kind: str, cong: float) -> dict:
    return {"seq": seq, "contentId": c["contentid"], "name": c["title"], "arrive": time,
            "label": label, "kind": kind, "lat": float(c["mapy"]), "lon": float(c["mapx"]),
            "image": c["firstimage"] or None, "congestion": round(cong, 1)}


def build_itinerary(con: sqlite3.Connection, area: str, signgus: list[str], genres: list[str],
                    start: str, end: str, food_cat: str = "") -> dict | None:
    act_ct, want_food = _resolve_cts(genres)
    days = _dates(start, end)
    act_pool = _candidates(con, area, signgus, act_ct)
    # 식사 풀: 음식 종류 선택 시 해당 카테고리(한식/중식/일식/양식/분식)로 필터
    spec = FOOD_CATS.get(food_cat)
    if spec:
        meal_pool = _candidates(con, area, signgus, FOOD_CT,
                                lcls2_in=spec.get("l2"), lcls3_in=spec.get("l3"))
    else:
        meal_pool = _candidates(con, area, signgus, FOOD_CT, lcls2_not=CAFE_LCLS2)   # 식사(카페 제외)
    cafe_pool = _candidates(con, area, signgus, FOOD_CT, lcls2_in=CAFE_LCLS2)    # 카페·찻집(FD05)
    indoor_pool = _candidates(con, area, signgus, INDOOR_CT)                     # 문화시설(악천후 실내 대안)
    if not act_pool and not meal_pool and not cafe_pool:
        return None
    cong = _congestion(con, act_pool + meal_pool + cafe_pool + indoor_pool, days)

    # 지역 대표 좌표(날씨 조회용) — 후보 좌표 평균
    coords = [(float(c["mapy"]), float(c["mapx"])) for c in (act_pool or meal_pool)[:20]
              if c["mapy"] and c["mapx"]]
    rep_lat = sum(a for a, _ in coords) / len(coords) if coords else None
    rep_lon = sum(o for _, o in coords) / len(coords) if coords else None

    # 슬롯 구성: 식도락만 골랐어도 관광 섞고, 관광만 골랐어도 식사 자동 삽입.
    slots = list(SLOTS)
    if not (meal_pool or cafe_pool):        # 식당 전무하면 식사/카페 슬롯 제거
        slots = [s for s in slots if s[1] == "act"]

    used: set[str] = set()

    def _xy(c: dict) -> tuple[float, float] | None:
        try:
            return float(c["mapy"]), float(c["mapx"])
        except (TypeError, ValueError):
            return None

    def pick(pools: list[list[dict]], day: str, last: tuple[float, float] | None) -> dict | None:
        """우선순위 풀에서 사용 가능한 후보 중 '덜 붐비면서 직전 장소와 가까운' 곳.
        점수 = 혼잡도 + DIST_W×거리(km). 첫 장소(last=None)는 혼잡도만으로 선택."""
        for pool in pools:
            cand = [c for c in pool if c["contentid"] not in used]
            if not cand:
                continue

            def score(c: dict) -> float:
                s = cong[(c["contentid"], day)]
                xy = _xy(c)
                if last and xy:
                    s += DIST_W * _haversine(last[0], last[1], xy[0], xy[1])
                return s

            return min(cand, key=score)
        return None

    day_plans = []
    for d in days:
        w = weather_svc.for_date(rep_lat, rep_lon, d) if rep_lat is not None else None
        indoor = bool(w and w["indoorPref"])
        # 악천후일: 관광 슬롯은 실내(문화시설) 우선, 없으면 원래 관광 풀
        act_pools = ([indoor_pool, act_pool] if indoor and indoor_pool else [act_pool])
        stops, seq = [], 1
        last: tuple[float, float] | None = None   # 직전 방문 좌표(거리 기반 동선)
        for time, kind, label in slots:
            if kind == "cafe":
                pools = [cafe_pool, meal_pool]     # 카페 없으면 식당 대체
            elif kind == "meal":
                pools = [meal_pool]
            else:
                pools = act_pools
            c = pick(pools, d, last)
            if not c:
                continue
            used.add(c["contentid"])
            stops.append(_mk_stop(c, seq, time, label, kind, cong[(c["contentid"], d)]))
            last = _xy(c) or last
            seq += 1
        act_stops = [s for s in stops if s["kind"] == "act"]
        avg = round(sum(s["congestion"] for s in act_stops) / len(act_stops), 1) if act_stops else 0.0
        # 동선 총거리(km): 순서대로 인접 정류지 거리 합
        dist = 0.0
        for a, b in zip(stops, stops[1:]):
            dist += _haversine(a["lat"], a["lon"], b["lat"], b["lon"])
        wd = WD[datetime.strptime(d, "%Y-%m-%d").weekday()]
        day_plans.append({"date": d, "weekday": wd, "avgCongestion": avg,
                          "totalDistanceKm": round(dist, 1), "weather": w, "stops": stops})

    rl = _rload()
    area_nm = rl["sido"].get(area, area)
    sg_all = rl["sigungu"].get(area, [])
    codes = {_sgu_code(area, s) for s in signgus if s}
    names = [s["name"] for s in sg_all if _sgu_code(area, s["code"]) in codes]
    sg_nm = ", ".join(names) if names else None
    return {"areaName": area_nm, "signguName": sg_nm, "genre": ", ".join(genres) or "관광지",
            "startDate": days[0], "endDate": days[-1], "days": day_plans}
