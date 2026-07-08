"""W0 스모크 테스트 — API 키 5종이 살아있는지 확인.

사용법:
    1) .env.example을 .env로 복사하고 키 입력
    2) pip install -r requirements.txt
    3) python pipelines/smoke_test.py

각 API에 최소 요청을 보내고 [OK]/[FAIL]과 응답 요약을 출력한다.
파라미터 오류(FAIL이지만 HTTP 200 + 에러 코드)는 키 문제가 아니라 명세 차이이므로
원시 응답을 보고 파라미터를 조정할 것.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()

TIMEOUT = 10.0
COMMON = {"MobileOS": "ETC", "MobileApp": "HiddenKorea", "_type": "json"}


def _get(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        print(f"[SKIP] {name} 미설정 (.env 확인)")
    return v


def call(label: str, url: str, params: dict) -> None:
    try:
        r = httpx.get(url, params=params, timeout=TIMEOUT)
        body = r.text[:300].replace("\n", " ")
        ok = r.status_code == 200 and ("resultCode" not in r.text or '"0000"' in r.text or "<resultCode>0000" in r.text or '"00"' in r.text)
        print(f"[{'OK' if ok else 'FAIL'}] {label} (HTTP {r.status_code})")
        if not ok:
            print(f"       응답: {body}")
    except Exception as e:  # noqa: BLE001 — 스모크 테스트는 전 예외 리포트
        print(f"[FAIL] {label} — {type(e).__name__}: {e}")


def main() -> None:
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    # 1) TourAPI 국문 관광정보 (KorService2)
    if k := _get("TOURAPI_KEY"):
        call(
            "TourAPI areaBasedList2",
            "https://apis.data.go.kr/B551011/KorService2/areaBasedList2",
            {"serviceKey": k, "numOfRows": 1, "pageNo": 1, **COMMON},
        )

    # 2) 관광지 집중률 예측 (정확한 오퍼레이션명은 활용신청 후 스웨거로 확정 — d2_coverage.py 참고)
    if k := _get("KTO_CONGESTION_KEY"):
        call(
            "집중률 예측 tatsCnctrRatedList",
            "https://apis.data.go.kr/B551011/TatsCnctrRateService/tatsCnctrRatedList",
            {"serviceKey": k, "numOfRows": 1, "pageNo": 1, **COMMON},
        )

    # 3) 지역별 방문자수 (DataLabService)
    if k := _get("KTO_VISITOR_KEY"):
        call(
            "지역별 방문자수 locgoRegnVisitrDDList",
            "https://apis.data.go.kr/B551011/DataLabService/locgoRegnVisitrDDList",
            {"serviceKey": k, "numOfRows": 1, "pageNo": 1, "startYmd": yesterday, "endYmd": yesterday, **COMMON},
        )

    # 4) 기상청 단기예보
    if k := _get("KMA_KEY"):
        call(
            "기상청 getVilageFcst",
            "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst",
            {"serviceKey": k, "numOfRows": 1, "pageNo": 1, "dataType": "JSON",
             "base_date": yesterday, "base_time": "0500", "nx": 60, "ny": 127},
        )

    # 5) 서울 실시간 도시데이터 (URL 경로에 키 포함 방식)
    if k := _get("SEOUL_KEY"):
        try:
            r = httpx.get(f"http://openapi.seoul.go.kr:8088/{k}/json/citydata/1/5/광화문·덕수궁 일대", timeout=TIMEOUT)
            ok = r.status_code == 200 and "CITYDATA" in r.text
            print(f"[{'OK' if ok else 'FAIL'}] 서울 citydata (HTTP {r.status_code})")
            if not ok:
                print(f"       응답: {r.text[:300]}")
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] 서울 citydata — {type(e).__name__}: {e}")

    print("\n완료. FAIL 항목은 응답 본문을 보고 (a) 키 승인 대기 (b) 파라미터 명세 차이를 구분할 것.")


if __name__ == "__main__":
    sys.exit(main())
