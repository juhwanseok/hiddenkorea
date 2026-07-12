"""W2 — 집중률 예측 시계열 전량 적재.

소스: TatsCnctrRateService/tatsCnctrRatedList (areaCd+signguCd별, 7,445곳 × 30일 ≈ 22만 행)
저장: data/hiddenkorea.db 테이블 congestion_forecast
멱등: (signguCd, tAtsNm, baseYmd) PK upsert.
시군구 열거: KorService2/ldongCode2 (d2_coverage와 동일 로직)

사용법: python pipelines/ingest_congestion.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

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
ROWS = 1000
PAGE_CAP = 8
DB = Path(__file__).resolve().parent.parent / "data" / "hiddenkorea.db"


def _rows(payload: dict) -> list[dict]:
    body = payload["response"]["body"]
    items = body.get("items") or ""
    if items in ("", None):
        return []
    item = items.get("item") or []
    return [item] if isinstance(item, dict) else item


def get(client, url, params):
    r = client.get(url, params={**COMMON, **params}, timeout=20.0)
    r.raise_for_status()
    return r.json()


def init_db(con):
    con.execute("""CREATE TABLE IF NOT EXISTS congestion_forecast (
        signguCd TEXT, signguNm TEXT, areaCd TEXT, areaNm TEXT,
        tAtsNm TEXT, baseYmd TEXT, cnctrRate REAL,
        PRIMARY KEY (signguCd, tAtsNm, baseYmd))""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_cf_spot ON congestion_forecast(signguCd, tAtsNm)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_cf_date ON congestion_forecast(baseYmd)")
    con.commit()


def upsert(con, items):
    sql = """INSERT INTO congestion_forecast
        (signguCd, signguNm, areaCd, areaNm, tAtsNm, baseYmd, cnctrRate)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(signguCd, tAtsNm, baseYmd) DO UPDATE SET cnctrRate=excluded.cnctrRate"""
    data = []
    for it in items:
        try:
            rate = float(it.get("cnctrRate", "") or 0)
        except ValueError:
            rate = 0.0
        data.append((it.get("signguCd", ""), it.get("signguNm", ""),
                     it.get("areaCd", ""), it.get("areaNm", ""),
                     it.get("tAtsNm", ""), it.get("baseYmd", ""), rate))
    con.executemany(sql, data)
    con.commit()
    return len(data)


def main() -> int:
    if not KEY:
        print("KTO_CONGESTION_KEY 미설정")
        return 1
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    init_db(con)

    saved, calls = 0, 0
    with httpx.Client() as client:
        sidos = [(str(r["code"]), r["name"]) for r in
                 _rows(get(client, LDONG, {"serviceKey": TOUR_KEY or KEY, "numOfRows": 100, "pageNo": 1}))]
        for sido_cd, sido_nm in sidos:
            sgs = [(str(r["code"]), r["name"]) for r in
                   _rows(get(client, LDONG, {"serviceKey": TOUR_KEY or KEY, "numOfRows": 100,
                                             "pageNo": 1, "lDongRegnCd": sido_cd}))]
            for sg3, sg_nm in sgs:
                signgu = f"{sido_cd}{sg3}"
                page = 1
                while page <= PAGE_CAP:
                    try:
                        data = get(client, CONGEST, {"serviceKey": KEY, "numOfRows": ROWS,
                                                     "pageNo": page, "areaCd": sido_cd, "signguCd": signgu})
                        calls += 1
                    except Exception as e:  # noqa: BLE001
                        print(f"  {signgu} p{page} 실패: {e}")
                        break
                    rows = _rows(data)
                    if not rows:
                        break
                    saved += upsert(con, rows)
                    total = int(data["response"]["body"].get("totalCount", 0))
                    if page * ROWS >= total:
                        break
                    page += 1
            print(f"  [{sido_cd} {sido_nm}] 누적 행 {saved}")

    cnt = con.execute("SELECT COUNT(*) FROM congestion_forecast").fetchone()[0]
    spots = con.execute("SELECT COUNT(DISTINCT signguCd||tAtsNm) FROM congestion_forecast").fetchone()[0]
    days = con.execute("SELECT COUNT(DISTINCT baseYmd) FROM congestion_forecast").fetchone()[0]
    con.close()
    print(f"\n=== 집중률 적재 완료 ===\n행 {cnt} / 관광지 {spots} / 일자 {days} / API콜 {calls}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
