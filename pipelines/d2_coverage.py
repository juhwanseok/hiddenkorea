"""RISKS R1 게이트 — 집중률 예측 API(D2)의 전국 커버 관광지 수 확정.

실측으로 확정한 API 스펙 (2026-07-11):
- 엔드포인트: TatsCnctrRateService/tatsCnctrRatedList
- 필수 파라미터: areaCd(시도 2자리 행정표준코드), signguCd(시군구 5자리 = 시도2 + 법정동 시군구3)
- 응답 필드: baseYmd, areaCd, areaNm, signguCd, signguNm, tAtsNm(관광지명), cnctrRate(집중률%)
- 시군구 코드 열거: KorService2/ldongCode2 (parent 없으면 시도, lDongRegnCd=<시도> 면 시군구)

산출물:
- data/d2_coverage.json  : 요약(총 관광지 수, 시도별 분포, 예측 지평)
- data/d2_spots.csv       : 관광지 마스터(areaCd,signguCd,signguNm,tAtsNm)
- data/region_map_d2.csv  : (areaCd,areaNm,signguCd,signguNm) — region_map 기초자료

사용법: python pipelines/d2_coverage.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Windows 콘솔(cp949)에서 한글·em대시 출력 시 UnicodeEncodeError 방지
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

load_dotenv()

KEY = os.getenv("KTO_CONGESTION_KEY", "").strip()
TOUR_KEY = os.getenv("TOURAPI_KEY", "").strip()
COMMON = {"MobileOS": "ETC", "MobileApp": "HiddenKorea", "_type": "json"}
LDONG = "https://apis.data.go.kr/B551011/KorService2/ldongCode2"
CONGEST = "https://apis.data.go.kr/B551011/TatsCnctrRateService/tatsCnctrRatedList"
PAGE_ROWS = 1000
PAGE_CAP = 8  # 시군구당 최대 페이지(쿼터 보호). 초과 시 capped 로그
DATA = Path(__file__).resolve().parent.parent / "data"


def _rows(payload: dict) -> list[dict]:
    body = payload["response"]["body"]
    items = body.get("items") or ""
    if items in ("", None):
        return []
    item = items.get("item") or []
    return [item] if isinstance(item, dict) else item


def get(client: httpx.Client, url: str, params: dict) -> dict:
    r = client.get(url, params={**COMMON, **params}, timeout=20.0)
    r.raise_for_status()
    return r.json()


def list_sido(client: httpx.Client) -> list[tuple[str, str]]:
    data = get(client, LDONG, {"serviceKey": TOUR_KEY or KEY, "numOfRows": 100, "pageNo": 1})
    return [(str(r["code"]), r["name"]) for r in _rows(data)]


def list_sigungu(client: httpx.Client, sido: str) -> list[tuple[str, str]]:
    data = get(client, LDONG, {"serviceKey": TOUR_KEY or KEY, "numOfRows": 100, "pageNo": 1, "lDongRegnCd": sido})
    return [(str(r["code"]), r["name"]) for r in _rows(data)]


def main() -> int:
    if not KEY:
        print("KTO_CONGESTION_KEY 미설정 (.env)")
        return 1
    DATA.mkdir(exist_ok=True)

    spots: dict[tuple[str, str], str] = {}      # (signguCd, tAtsNm) -> areaNm|signguNm
    per_sido: Counter[str] = Counter()
    region_rows: list[tuple[str, str, str, str]] = []
    base_ymds: set[str] = set()
    capped: list[str] = []
    calls = 0

    with httpx.Client() as client:
        sidos = list_sido(client)
        print(f"시도 {len(sidos)}개 열거 완료")

        for sido_cd, sido_nm in sidos:
            sigungus = list_sigungu(client, sido_cd)
            for sg3, sg_nm in sigungus:
                signgu_cd = f"{sido_cd}{sg3}"
                region_rows.append((sido_cd, sido_nm, signgu_cd, sg_nm))
                page = 1
                seen_before = len(spots)
                while page <= PAGE_CAP:
                    try:
                        data = get(client, CONGEST, {"serviceKey": KEY, "numOfRows": PAGE_ROWS,
                                                     "pageNo": page, "areaCd": sido_cd, "signguCd": signgu_cd})
                        calls += 1
                    except Exception as e:  # noqa: BLE001
                        print(f"  {signgu_cd} {sg_nm} p{page} 실패: {e}")
                        break
                    rows = _rows(data)
                    if not rows:
                        break
                    for it in rows:
                        nm = it.get("tAtsNm", "").strip()
                        if nm:
                            spots[(signgu_cd, nm)] = f"{it.get('areaNm','')}|{it.get('signguNm','')}"
                            base_ymds.add(it.get("baseYmd", ""))
                    total = int(data["response"]["body"].get("totalCount", 0))
                    if page * PAGE_ROWS >= total:
                        break
                    page += 1
                else:
                    capped.append(f"{signgu_cd} {sg_nm}")
                added = len(spots) - seen_before
                per_sido[f"{sido_cd} {sido_nm}"] += added
            print(f"  [{sido_cd} {sido_nm}] 누적 관광지 {len(spots)}")

    # 저장
    with (DATA / "d2_spots.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["signguCd", "tAtsNm", "areaNm", "signguNm"])
        for (sg, nm), meta in sorted(spots.items()):
            a, s = meta.split("|", 1); w.writerow([sg, nm, a, s])
    with (DATA / "region_map_d2.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["areaCd", "areaNm", "signguCd", "signguNm"])
        w.writerows(sorted(set(region_rows)))

    horizon = len([y for y in base_ymds if y])
    summary = {
        "distinct_spots": len(spots),
        "forecast_horizon_days": horizon,
        "api_calls": calls,
        "per_sido": dict(per_sido.most_common()),
        "capped_sigungu": capped,
    }
    (DATA / "d2_coverage.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== D2 커버리지 판정 ===")
    print(f"전국 고유 관광지 수: {len(spots)}")
    print(f"예측 지평(일수): {horizon}")
    print(f"API 호출 수: {calls}")
    print("시도별 분포:")
    for k, v in per_sido.most_common():
        print(f"  {k}: {v}")
    if capped:
        print(f"⚠️ PAGE_CAP({PAGE_CAP}) 도달로 일부 누락 가능 시군구: {len(capped)}곳 — {capped[:5]}")
    verdict = ("R1 미발동 — 하이브리드 설계 유지, 집중률 API가 1차 소스"
               if len(spots) >= 500 else
               "⚠️ R1 발동 — 자체 ML 비중 확대 필요, DECISION_LOG 기록")
    print(f"판정: {verdict}")
    print(f"저장: {DATA/'d2_coverage.json'}, d2_spots.csv, region_map_d2.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
