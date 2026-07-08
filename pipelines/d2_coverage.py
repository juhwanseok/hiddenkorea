"""RISKS R1 게이트 — 집중률 예측 API(D2)의 커버 관광지 수 확정.

프로젝트 최대 미지수를 해소하는 스크립트. 전체 페이지를 순회하며
고유 관광지 목록을 수집해 data/d2_coverage.json 으로 저장한다.

사용법: python pipelines/d2_coverage.py
출력: 커버 POI 수, 지역별 분포, 판정(R1 발동 여부)

주의: 오퍼레이션/필드명은 활용신청 승인 후 스웨거(개방 데이터 활용 매뉴얼 v4.1)로
검증할 것. 응답 구조가 다르면 RAW 출력을 보고 FIELD_* 상수만 고치면 된다.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = "https://apis.data.go.kr/B551011/TatsCnctrRateService/tatsCnctrRatedList"
COMMON = {"MobileOS": "ETC", "MobileApp": "HiddenKorea", "_type": "json"}
ROWS = 1000  # 페이지당 최대 (쿼터 절약)

# 응답 필드명 (스웨거 확인 후 필요 시 수정)
FIELD_POI_ID = "tAtsCd"    # 관광지 코드
FIELD_POI_NM = "tAtsNm"    # 관광지명
FIELD_AREA = "areaNm"      # 지역명


def fetch_page(key: str, page: int) -> dict:
    r = httpx.get(BASE, params={"serviceKey": key, "numOfRows": ROWS, "pageNo": page, **COMMON}, timeout=15.0)
    r.raise_for_status()
    return r.json()


def main() -> int:
    key = os.getenv("KTO_CONGESTION_KEY", "").strip()
    if not key:
        print("KTO_CONGESTION_KEY 미설정 (.env)")
        return 1

    pois: dict[str, str] = {}
    areas: Counter[str] = Counter()
    page, total = 1, None

    while True:
        try:
            data = fetch_page(key, page)
        except Exception as e:  # noqa: BLE001
            print(f"페이지 {page} 실패: {e}")
            break
        try:
            body = data["response"]["body"]
            items = body.get("items") or {}
            rows = items.get("item") or []
            if isinstance(rows, dict):
                rows = [rows]
            total = body.get("totalCount", total)
        except (KeyError, TypeError):
            print("예상과 다른 응답 구조 — RAW 500자:")
            print(json.dumps(data, ensure_ascii=False)[:500])
            return 1

        if not rows:
            break
        for it in rows:
            pid = str(it.get(FIELD_POI_ID, "")) or str(it.get(FIELD_POI_NM, ""))
            if pid:
                pois[pid] = it.get(FIELD_POI_NM, "")
                areas[it.get(FIELD_AREA, "미상")] += 1
        print(f"  page {page}: 누적 고유 POI {len(pois)} / totalCount={total}")
        if total is not None and page * ROWS >= int(total):
            break
        page += 1
        if page > 300:  # 쿼터 보호
            print("300페이지 초과 — 중단 (쿼터 보호)")
            break

    out = Path(__file__).resolve().parent.parent / "data" / "d2_coverage.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"count": len(pois), "areas": dict(areas), "pois": pois},
                              ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== D2 커버리지 판정 ===")
    print(f"고유 관광지 수: {len(pois)}")
    print(f"지역 분포 상위: {areas.most_common(10)}")
    verdict = "R1 미발동 — 하이브리드 설계 유지" if len(pois) >= 500 else "⚠️ R1 발동 — 자체 ML 비중 확대, DECISION_LOG 기록 필요"
    print(f"판정: {verdict}")
    print(f"저장: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
