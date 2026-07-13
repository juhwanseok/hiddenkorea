"""서울 실시간 도시데이터(citydata) 연동 — 예측과 실시간을 병기(신뢰성 증명).

서울 열린데이터광장 citydata: 주요 명소 실시간 인구·혼잡레벨(여유/보통/약간 붐빔/붐빔) + 예측.
POI(서울) → citydata 인구밀집지역명 매핑 후 조회. SEOUL_KEY 없으면 None(폴백).
* 데모/심사에서 서울 주요 관광지의 '예측 vs 실측'을 보여주는 용도.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[4] / ".env")

BASE = "http://openapi.seoul.go.kr:8088"

# POI 제목 키워드 → citydata 인구밀집지역명 (주요 관광지). 포함 매칭.
POI_TO_AREA = {
    "경복궁": "경복궁", "광화문": "광화문·덕수궁", "덕수궁": "광화문·덕수궁",
    "창덕궁": "창덕궁·종묘", "종묘": "창덕궁·종묘", "창경궁": "창덕궁·종묘",
    "북촌": "북촌한옥마을", "익선동": "익선동", "인사동": "인사동",
    "명동": "명동 관광특구", "남산": "남산공원", "n서울타워": "남산공원", "서울타워": "남산공원",
    "홍대": "홍대 관광특구", "이태원": "이태원 관광특구", "동대문": "동대문 관광특구",
    "잠실": "잠실 관광특구", "롯데월드": "잠실 관광특구", "석촌호수": "잠실 관광특구",
    "강남": "강남역", "코엑스": "강남 MICE 관광특구", "삼성역": "강남 MICE 관광특구",
    "여의도": "여의도", "63": "여의도", "청계천": "청계산입구역",
    "서울숲": "서울숲공원", "성수": "성수카페거리", "가로수길": "가로수길",
    "광장시장": "광장(전통)시장", "국립중앙박물관": "용산역",
    "월드컵공원": "월드컵공원", "하늘공원": "월드컵공원", "노들섬": "여의도",
}


def _key() -> str:
    return os.getenv("SEOUL_KEY", "").strip()


def match_area(title: str, area_code: str) -> str | None:
    if area_code != "11" or not title:      # 서울만
        return None
    for kw, area in POI_TO_AREA.items():
        if kw in title.lower() or kw in title:
            return area
    return None


@lru_cache(maxsize=256)
def _fetch(area: str) -> dict | None:
    key = _key()
    if not key:
        return None
    try:
        # 한글 지역명은 URL 인코딩 필요 → httpx가 처리
        r = httpx.get(f"{BASE}/{key}/json/citydata/1/5/{area}", timeout=10.0)
        data = r.json()
        live = data["CITYDATA"]["LIVE_PPLTN_STTS"]
        live = live[0] if isinstance(live, list) else live
        return {
            "level": live.get("AREA_CONGEST_LVL"),
            "msg": live.get("AREA_CONGEST_MSG"),
            "min": live.get("AREA_PPLTN_MIN"),
            "max": live.get("AREA_PPLTN_MAX"),
            "time": live.get("PPLTN_TIME"),
        }
    except Exception:  # noqa: BLE001
        return None


def for_poi(title: str, area_code: str) -> dict | None:
    """서울 주요 관광지면 실시간 혼잡 반환, 아니면 None."""
    area = match_area(title, area_code)
    if not area:
        return None
    res = _fetch(area)
    if not res or not res.get("level"):
        return None
    return {"area": area, **res}
