"""W1 — TourAPI 국문 관광정보 POI 마스터 전량 적재.

소스: KorService2/areaBasedList2 (총 ~50,674건, 페이지당 1000 → ~51콜)
저장: data/hiddenkorea.db (SQLite, 로컬 staging). 이후 Supabase Postgres 이관.
멱등: contentid PK upsert — 재실행해도 중복 없음, 갱신분만 반영.

핵심 필드 lDongRegnCd+lDongSignguCd = 집중률 API signguCd 조인키 (하이브리드 엔진 연결고리).
overview(임베딩 텍스트)는 여기 없음 → W3에서 detailCommon2로 별도 수집(쿼터 전략 필요).

사용법: python pipelines/ingest_pois.py
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

KEY = os.getenv("TOURAPI_KEY", "").strip()
BASE = "https://apis.data.go.kr/B551011/KorService2/areaBasedList2"
COMMON = {"MobileOS": "ETC", "MobileApp": "HiddenKorea", "_type": "json"}
ROWS = 1000
DB = Path(__file__).resolve().parent.parent / "data" / "hiddenkorea.db"

# (컬럼, TourAPI 필드) — 없으면 빈 문자열
COLS = [
    ("contentid", "contentid"), ("title", "title"), ("contenttypeid", "contenttypeid"),
    ("addr1", "addr1"), ("addr2", "addr2"), ("zipcode", "zipcode"),
    ("mapx", "mapx"), ("mapy", "mapy"), ("mlevel", "mlevel"),
    ("tel", "tel"), ("firstimage", "firstimage"), ("firstimage2", "firstimage2"),
    ("cpyrhtDivCd", "cpyrhtDivCd"),
    ("ldongRegnCd", "lDongRegnCd"), ("ldongSignguCd", "lDongSignguCd"),
    ("lclsSystm1", "lclsSystm1"), ("lclsSystm2", "lclsSystm2"), ("lclsSystm3", "lclsSystm3"),
    ("cat1", "cat1"), ("cat2", "cat2"), ("cat3", "cat3"),
    ("areacode", "areacode"), ("sigungucode", "sigungucode"),
    ("createdtime", "createdtime"), ("modifiedtime", "modifiedtime"),
]


def init_db(con: sqlite3.Connection) -> None:
    cols_ddl = ",\n  ".join(f"{c} TEXT" for c, _ in COLS)
    con.execute(f"CREATE TABLE IF NOT EXISTS places (\n  {cols_ddl},\n  PRIMARY KEY (contentid)\n)")
    # 조인/조회 인덱스
    con.execute("CREATE INDEX IF NOT EXISTS idx_places_signgu ON places(ldongRegnCd, ldongSignguCd)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_places_type ON places(contenttypeid)")
    con.commit()


def rows_of(payload: dict) -> list[dict]:
    body = payload["response"]["body"]
    items = body.get("items") or ""
    if items in ("", None):
        return []
    item = items.get("item") or []
    return [item] if isinstance(item, dict) else item


def upsert(con: sqlite3.Connection, items: list[dict]) -> int:
    col_names = [c for c, _ in COLS]
    placeholders = ",".join("?" for _ in col_names)
    updates = ",".join(f"{c}=excluded.{c}" for c, _ in COLS if c != "contentid")
    sql = (f"INSERT INTO places ({','.join(col_names)}) VALUES ({placeholders}) "
           f"ON CONFLICT(contentid) DO UPDATE SET {updates}")
    data = [[str(it.get(src, "") or "") for _, src in COLS] for it in items]
    con.executemany(sql, data)
    con.commit()
    return len(data)


def main() -> int:
    if not KEY:
        print("TOURAPI_KEY 미설정 (.env)")
        return 1
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    init_db(con)

    total, page, saved = None, 1, 0
    with httpx.Client() as client:
        while True:
            params = {"serviceKey": KEY, "numOfRows": ROWS, "pageNo": page, "arrange": "A", **COMMON}
            try:
                r = client.get(BASE, params=params, timeout=30.0)
                r.raise_for_status()
                data = r.json()
            except Exception as e:  # noqa: BLE001
                print(f"page {page} 실패: {e} — 5초 후 1회 재시도")
                try:
                    r = client.get(BASE, params=params, timeout=30.0)
                    data = r.json()
                except Exception as e2:  # noqa: BLE001
                    print(f"page {page} 재시도 실패: {e2} — 중단")
                    break
            items = rows_of(data)
            if not items:
                break
            saved += upsert(con, items)
            total = int(data["response"]["body"].get("totalCount", total or 0))
            print(f"  page {page}: 누적 {saved}/{total}")
            if total and page * ROWS >= total:
                break
            page += 1
            if page > 200:
                print("200페이지 초과 — 중단(안전장치)")
                break

    cnt = con.execute("SELECT COUNT(*) FROM places").fetchone()[0]
    by_type = con.execute(
        "SELECT contenttypeid, COUNT(*) FROM places GROUP BY contenttypeid ORDER BY 2 DESC"
    ).fetchall()
    con.close()

    print(f"\n=== POI 적재 완료 ===")
    print(f"DB: {DB}")
    print(f"총 레코드: {cnt}")
    print("콘텐츠타입별(12관광지/14문화/15축제/25코스/28레포츠/32숙박/38쇼핑/39음식):")
    for t, c in by_type:
        print(f"  type {t or '(빈값)'}: {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
