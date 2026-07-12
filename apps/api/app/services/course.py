"""코스 엔진 — 동선 최적화 + 서사 (ARCHITECTURE 3.3).

순서 최적화는 코드(nearest-neighbor + 2-opt)가 담당, LLM은 서사만(사실 주입, 폴백 보장).
거리는 haversine, 이동시간은 도심 평균 25km/h 가정, 체류 90분 기본.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta

import numpy as np

from .congestion import norm_title

SPEED_KMH = 25.0
DWELL_MIN = 90


def _haversine_matrix(lat, lon):
    lat = np.radians(np.array(lat)); lon = np.radians(np.array(lon))
    dlat = lat[:, None] - lat[None, :]
    dlon = lon[:, None] - lon[None, :]
    a = np.sin(dlat / 2) ** 2 + np.cos(lat)[:, None] * np.cos(lat)[None, :] * np.sin(dlon / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def _nearest_neighbor(D: np.ndarray, start: int = 0) -> list[int]:
    n = len(D); unvisited = set(range(n)); order = [start]; unvisited.discard(start)
    while unvisited:
        last = order[-1]
        nxt = min(unvisited, key=lambda j: D[last, j])
        order.append(nxt); unvisited.discard(nxt)
    return order


def _two_opt(order: list[int], D: np.ndarray) -> list[int]:
    improved = True
    while improved:
        improved = False
        for i in range(1, len(order) - 1):
            for k in range(i + 1, len(order)):
                a, b = order[i - 1], order[i]
                c = order[k]; d = order[k + 1] if k + 1 < len(order) else None
                delta = D[a, c] + (D[b, d] if d is not None else 0) - D[a, b] - (D[c, d] if d is not None else 0)
                if delta < -1e-9:
                    order[i:k + 1] = order[i:k + 1][::-1]; improved = True
    return order


def build_course(con: sqlite3.Connection, poi_ids: list[str], date_iso: str,
                 start_time: str = "09:00") -> dict | None:
    rows = []
    for cid in poi_ids:
        r = con.execute("SELECT contentid,title,mapx,mapy,ldongRegnCd,ldongSignguCd,firstimage "
                        "FROM places WHERE contentid=?", (cid,)).fetchone()
        if r:
            rows.append(r)
    if len(rows) < 2:
        return None

    lat = [float(r["mapy"]) for r in rows]; lon = [float(r["mapx"]) for r in rows]
    D = _haversine_matrix(lat, lon)
    order = _two_opt(_nearest_neighbor(D, 0), D)

    date_ymd = date_iso.replace("-", "")
    t = datetime.strptime(f"{date_iso} {start_time}", "%Y-%m-%d %H:%M")
    legs, total_km = [], 0.0
    for seq, idx in enumerate(order):
        r = rows[idx]
        if seq > 0:
            km = float(D[order[seq - 1], idx]); total_km += km
            t += timedelta(minutes=km / SPEED_KMH * 60)
        # 정류장 혼잡(링크 있으면)
        link = con.execute(
            """SELECT cf.cnctrRate FROM poi_congestion_link l
               JOIN congestion_forecast cf ON l.signguCd=cf.signguCd AND l.tAtsNm=cf.tAtsNm
               WHERE l.contentid=? AND cf.baseYmd=?""", (r["contentid"], date_ymd)).fetchone()
        cong = round(float(link["cnctrRate"]), 1) if link else None
        legs.append({
            "seq": seq + 1, "contentId": r["contentid"], "name": r["title"],
            "arrive": t.strftime("%H:%M"), "lat": lat[idx], "lon": lon[idx],
            "congestion": cong, "image": r["firstimage"] or None,
            "travelKmFromPrev": round(float(D[order[seq - 1], idx]), 1) if seq > 0 else 0.0,
        })
        t += timedelta(minutes=DWELL_MIN)

    return {
        "date": date_iso, "startTime": start_time,
        "totalDistanceKm": round(total_km, 1), "stops": len(legs),
        "legs": legs, "kakaoMapUrl": _kakao_url(legs),
        "narrative": _narrative(legs, date_iso),
    }


def _kakao_url(legs: list[dict]) -> str:
    last = legs[-1]
    return f"https://map.kakao.com/link/to/{last['name']},{last['lat']},{last['lon']}"


def _narrative(legs: list[dict], date_iso: str) -> str:
    """LLM 서사(PROMPTS P2) — 키 없거나 실패 시 템플릿."""
    seq = " → ".join(f"{l['arrive']} {l['name']}" for l in legs)
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            prompt = (f"다음 일정의 순서·시간·장소명을 절대 바꾸지 말고 하루 흐름을 소개하는 "
                      f"한국어 3문장. 없는 정보 언급 금지.\n일정: {seq}")
            msg = client.messages.create(
                model=os.getenv("HK_LLM_MODEL", "claude-haiku-4-5-20251001"),
                max_tokens=200, system="너는 여행 코스 안내문 작성자다.",
                messages=[{"role": "user", "content": prompt}])
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
            if text:
                return text
        except Exception:  # noqa: BLE001
            pass
    n = len(legs)
    return (f"{date_iso} 하루, 혼잡을 피해 {n}곳을 여유롭게 도는 코스입니다. "
            f"{legs[0]['name']}에서 시작해 {legs[-1]['name']}에서 마무리합니다. "
            f"이동은 총 동선을 최소화하도록 배치했습니다.")
