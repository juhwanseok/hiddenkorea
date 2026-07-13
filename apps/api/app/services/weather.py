"""기상청 단기예보 연동 — 날씨 연동 추천용.

기상청 getVilageFcst는 today~+2~3일만 제공 → 예보창 밖 날짜는 None(날씨 미반영).
좌표(위경도) → 기상청 격자(nx,ny) 변환(LCC DFS) 후 해당 날짜 낮(14시) 예보 요약.
악천후(강수/폭염/한파) 시 indoorPref=True → 일정에서 실내(문화시설) 우선.
"""
from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

KST = timezone(timedelta(hours=9))   # 배포 서버(UTC)에서도 한국시간 기준 발표시각 계산

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[4] / ".env")   # 레포 루트 .env


def _key() -> str:
    return os.getenv("KMA_KEY", "").strip()


BASE = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
SKY_LABEL = {"1": "맑음", "3": "구름많음", "4": "흐림"}
PTY_LABEL = {"0": "", "1": "비", "2": "비/눈", "3": "눈", "4": "소나기", "5": "빗방울",
             "6": "빗방울/눈날림", "7": "눈날림"}


def dfs_xy(lat: float, lon: float) -> tuple[int, int]:
    """위경도 → 기상청 격자 nx,ny (기상청 공식 LCC 변환)."""
    RE, GRID, SLAT1, SLAT2, OLON, OLAT, XO, YO = 6371.00877, 5.0, 30.0, 60.0, 126.0, 38.0, 43, 136
    D = math.pi / 180.0
    re = RE / GRID
    slat1, slat2, olon, olat = SLAT1 * D, SLAT2 * D, OLON * D, OLAT * D
    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)
    ra = math.tan(math.pi * 0.25 + lat * D * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lon * D - olon
    theta = theta - 2 * math.pi if theta > math.pi else theta + 2 * math.pi if theta < -math.pi else theta
    theta *= sn
    return int(ra * math.sin(theta) + XO + 0.5), int(ro - ra * math.cos(theta) + YO + 0.5)


def _base() -> tuple[str, str]:
    """가장 최근 발표시각(0200~2300, 3시간 간격). 발표+10분 전이면 이전 회차."""
    now = datetime.now(KST) - timedelta(minutes=15)
    slots = [2, 5, 8, 11, 14, 17, 20, 23]
    h = now.hour
    chosen = max([s for s in slots if s <= h], default=None)
    if chosen is None:
        now -= timedelta(days=1); chosen = 23
    return now.strftime("%Y%m%d"), f"{chosen:02d}00"


@lru_cache(maxsize=512)
def _fetch(nx: int, ny: int, base_date: str, base_time: str) -> tuple:
    key = _key()
    if not key:
        return ()
    try:
        r = httpx.get(BASE, params={"serviceKey": key, "numOfRows": 1000, "pageNo": 1,
                                    "dataType": "JSON", "base_date": base_date, "base_time": base_time,
                                    "nx": nx, "ny": ny}, timeout=10.0)
        items = r.json()["response"]["body"]["items"]["item"]
        return tuple((it["fcstDate"], it["fcstTime"], it["category"], it["fcstValue"]) for it in items)
    except Exception:  # noqa: BLE001
        return ()


def for_date(lat: float, lon: float, date_iso: str) -> dict | None:
    """(좌표, 날짜) → 낮 예보 요약. 예보창 밖/실패 시 None."""
    if not _key() or lat is None or lon is None:
        return None
    nx, ny = dfs_xy(lat, lon)
    bd, bt = _base()
    rows = _fetch(nx, ny, bd, bt)
    if not rows:
        return None
    ymd = date_iso.replace("-", "")
    day = [r for r in rows if r[0] == ymd]
    if not day:
        return None  # 예보 범위 밖(보통 +3일 초과)
    # 낮 대표: 14시 우선, 없으면 정오 근처
    def pick(cat):
        cands = [r for r in day if r[2] == cat]
        if not cands:
            return None
        return (next((r for r in cands if r[1] == "1400"), None) or
                min(cands, key=lambda r: abs(int(r[1]) - 1400)))[3]
    sky, pty, tmp = pick("SKY"), pick("PTY"), pick("TMP")
    try:
        tmp_v = float(tmp) if tmp is not None else None
    except ValueError:
        tmp_v = None
    rain = pty not in (None, "0")
    hot = tmp_v is not None and tmp_v >= 33
    cold = tmp_v is not None and tmp_v <= -9
    indoor_pref = bool(rain or hot or cold)
    label = PTY_LABEL.get(pty or "0") or SKY_LABEL.get(sky or "", "")
    emoji = ("🌧️" if rain else "☀️" if sky == "1" else "⛅" if sky == "3" else "☁️")
    note = None
    if rain:
        note = "이 날 비 예보 — 실내 명소 위주로 구성했어요"
    elif hot:
        note = "폭염 예보 — 실내 위주로 구성했어요"
    elif cold:
        note = "한파 예보 — 실내 위주로 구성했어요"
    return {"label": label or "정보없음", "emoji": emoji, "tmp": tmp_v,
            "rain": rain, "indoorPref": indoor_pref, "note": note}
