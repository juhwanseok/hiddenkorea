"""대안지 매칭 엔진 — 분류체계 우선 + HiddenScore (ML_GUIDELINES 계층2).

후보 생성: **origin과 동일 lclsSystm2(중분류)** POI (예: 경복궁 HS01 → 고궁·종묘·성곽 등) + 거리 필터.
  → 신뢰도 높은 공식 분류로 "같은 종류의 명소"를 보장. 임베딩은 그 안에서 순위 보조.
랭킹: HiddenScore = α·유사도 + β·(1−혼잡) + γ·접근성 + δ·품질.
자기조절: 혼잡 임계 초과 후보 제외(RED_TEAM A5).

혼잡 주의: cnctrRate는 관광지 자체기준 상대치 → v0 근사. (관광지간 절대비교는 시군구 방문량 보정이 후속)
"""
from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path

import numpy as np

from ..core.constants import (
    ALT_EXCLUDE_INDEX, ALT_MIN_DIST_KM, ALT_NAME_BLOCK, ALT_SAME_SUBCAT_BONUS,
)
from ..core.db import connect

EMB = Path(__file__).resolve().parents[4] / "data" / "embeddings.npz"

# HiddenScore 기본 가중치 (골드셋 nDCG로 튜닝 — ml/eval/tune_weights.py 결과 반영)
W = {"sim": 0.4, "cong": 0.3, "dist": 0.2, "qual": 0.1}
DIST_HALF_KM = 25.0    # 거리 감쇠 반감 거리
MAX_DIST_KM = 80.0     # 후보 최대 거리
CAND_LIMIT = 400       # 후보 상한


class Index:
    """임베딩 + POI 메타(좌표·분류·이미지). 프로세스 1회 로드."""
    def __init__(self) -> None:
        z = np.load(EMB, allow_pickle=True)
        self.ids: list[str] = [str(x) for x in z["ids"]]
        self.vecs: np.ndarray = z["vecs"].astype(np.float32)
        self.pos = {cid: i for i, cid in enumerate(self.ids)}
        con = connect()
        rows = {r["contentid"]: r for r in con.execute(
            f"SELECT contentid, title, mapx, mapy, ldongRegnCd, ldongSignguCd, firstimage, addr1, "
            f"lclsSystm1, lclsSystm2, lclsSystm3 FROM places WHERE contentid IN ({','.join('?'*len(self.ids))})",
            self.ids)}
        con.close()

        def f(v):
            try: return float(v)
            except (TypeError, ValueError): return np.nan
        g = lambda c, k: (rows[c][k] if c in rows else "") or ""
        self.lon = np.array([f(g(c, "mapx")) for c in self.ids])
        self.lat = np.array([f(g(c, "mapy")) for c in self.ids])
        self.signgu = [g(c, "ldongRegnCd") + g(c, "ldongSignguCd") for c in self.ids]
        self.regn = np.array([g(c, "ldongRegnCd") for c in self.ids])   # 시도코드(타지역 대안용)
        self.title = [g(c, "title") for c in self.ids]
        self.addr = [g(c, "addr1") for c in self.ids]
        self.lcls1 = np.array([g(c, "lclsSystm1") for c in self.ids])
        self.lcls2 = np.array([g(c, "lclsSystm2") for c in self.ids])
        self.lcls3 = np.array([g(c, "lclsSystm3") for c in self.ids])
        self.img = np.array([1.0 if g(c, "firstimage") else 0.0 for c in self.ids])


@lru_cache(maxsize=1)
def get_index() -> Index:
    return Index()


def _haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def _cong_on_date(con: sqlite3.Connection, date_ymd: str) -> dict[str, float]:
    rows = con.execute(
        """SELECT l.contentid c, cf.cnctrRate r FROM poi_congestion_link l
           JOIN congestion_forecast cf ON l.signguCd=cf.signguCd AND l.tAtsNm=cf.tAtsNm
           WHERE cf.baseYmd=?""", (date_ymd,)).fetchall()
    return {row["c"]: float(row["r"]) for row in rows}


def alternatives(content_id: str, date_iso: str, k: int = 3, weights: dict | None = None) -> list[dict]:
    idx = get_index()
    if content_id not in idx.pos:
        return []
    w = weights or W
    i = idx.pos[content_id]

    # 1) 후보 = 동일 중분류(lclsSystm2). 없으면 대분류(lclsSystm1) 폴백.
    if idx.lcls2[i]:
        cand = np.where((idx.lcls2 == idx.lcls2[i]))[0]
    elif idx.lcls1[i]:
        cand = np.where((idx.lcls1 == idx.lcls1[i]))[0]
    else:
        cand = np.arange(len(idx.ids))

    # 2) 거리 필터
    dist = _haversine(idx.lat[i], idx.lon[i], idx.lat[cand], idx.lon[cand])
    keep = np.isfinite(dist) & (dist <= MAX_DIST_KM)
    cand, dist = cand[keep], dist[keep]
    if len(cand) == 0:
        return []
    sims = idx.vecs[cand] @ idx.vecs[i]
    # 유사도 상위 후보로 제한
    if len(cand) > CAND_LIMIT:
        top = np.argsort(-sims)[:CAND_LIMIT]
        cand, dist, sims = cand[top], dist[top], sims[top]

    date_ymd = date_iso.replace("-", "")
    con = connect()
    cong = _cong_on_date(con, date_ymd)
    con.close()

    origin_title = idx.title[i]
    out = []
    for pos_c, j in enumerate(cand):
        if j == i:
            continue
        d = float(dist[pos_c])
        if d < ALT_MIN_DIST_KM:                           # 노이즈: 같은 명소 하위 구성물(예: 건청궁)
            continue
        name = idx.title[j]
        if any(b in name for b in ALT_NAME_BLOCK):        # 노이즈: 학교·동상 등 비관광
            continue
        if origin_title and origin_title in name:         # 노이즈: 원본의 부속(예: 창경궁→창경궁 명정전)
            continue
        cid = idx.ids[j]
        c_idx = cong.get(cid, 45.0)                       # 링크 없으면 중립 근사
        if c_idx >= ALT_EXCLUDE_INDEX:                    # 자기조절: 붐비는 대안 제외
            continue
        sim = float(sims[pos_c])
        dist_decay = DIST_HALF_KM / (DIST_HALF_KM + d)
        score = (w["sim"] * sim + w["cong"] * (1 - c_idx / 100)
                 + w["dist"] * dist_decay + w["qual"] * float(idx.img[j]))
        if idx.lcls3[j] and idx.lcls3[j] == idx.lcls3[i]:  # 동일 소분류 미세 가산
            score += ALT_SAME_SUBCAT_BONUS
        out.append({
            "contentId": cid, "name": idx.title[j], "addr": idx.addr[j],
            "hiddenScore": round(score, 4), "simPct": round(sim * 100, 1),
            "congestion": round(c_idx, 1), "distanceKm": round(d, 1),
        })
    out.sort(key=lambda x: -x["hiddenScore"])
    return out[:k]


# 타지역(전국) 대안 가중치: 거리 무시, 유사도+비혼잡 위주
W_NATION = {"sim": 0.5, "cong": 0.4, "qual": 0.1}


def alternatives_nationwide(content_id: str, date_iso: str, k: int = 3) -> list[dict]:
    """전국에서 '비슷한 느낌인데 더 한적한 다른 지역' 명소. 같은 시도 제외, 지역 다양성 보장."""
    from .regions import _load as rload
    sido = rload()["sido"]
    idx = get_index()
    if content_id not in idx.pos:
        return []
    i = idx.pos[content_id]
    origin_regn = idx.regn[i]

    # 느낌 매칭: 소분류(lclsSystm3) 우선, 없으면 중분류
    if idx.lcls3[i]:
        cand = np.where(idx.lcls3 == idx.lcls3[i])[0]
    elif idx.lcls2[i]:
        cand = np.where(idx.lcls2 == idx.lcls2[i])[0]
    else:
        return []
    cand = cand[(idx.regn[cand] != origin_regn) & (idx.regn[cand] != "")]  # 다른 시도만
    if len(cand) == 0:
        return []
    sims = idx.vecs[cand] @ idx.vecs[i]
    dist = _haversine(idx.lat[i], idx.lon[i], idx.lat[cand], idx.lon[cand])

    date_ymd = date_iso.replace("-", "")
    con = connect()
    cong = _cong_on_date(con, date_ymd)
    con.close()

    origin_title = idx.title[i]
    scored = []
    for pos_c, j in enumerate(cand):
        name = idx.title[j]
        if any(b in name for b in ALT_NAME_BLOCK) or (origin_title and origin_title in name):
            continue
        cid = idx.ids[j]
        c_idx = cong.get(cid, 45.0)
        if c_idx >= ALT_EXCLUDE_INDEX:                    # 붐비는 곳 제외 (핵심: '더 한적한')
            continue
        sim = float(sims[pos_c])
        score = W_NATION["sim"] * sim + W_NATION["cong"] * (1 - c_idx / 100) + W_NATION["qual"] * float(idx.img[j])
        scored.append({
            "contentId": cid, "name": name, "addr": idx.addr[j],
            "region": sido.get(idx.regn[j], idx.regn[j]),
            "hiddenScore": round(score, 4), "simPct": round(sim * 100, 1),
            "congestion": round(c_idx, 1), "distanceKm": round(float(dist[pos_c]), 1),
            "_regn": idx.regn[j],
        })
    # 지역 다양성: 시도별 최고 1곳만 → 서로 다른 지역 k곳
    best_by_regn: dict[str, dict] = {}
    for s in sorted(scored, key=lambda x: -x["hiddenScore"]):
        best_by_regn.setdefault(s["_regn"], s)
    picks = sorted(best_by_regn.values(), key=lambda x: -x["hiddenScore"])[:k]
    for p in picks:
        p.pop("_regn", None)
    return picks
