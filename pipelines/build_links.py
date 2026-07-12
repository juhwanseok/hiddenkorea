"""POI ↔ 집중률 관광지 링크 테이블 구축 (85.2% 매칭 → 조인 영속화).

places(TourAPI) 와 congestion_forecast(집중률)를 (signguCd + 정규화 제목)으로 매칭해
poi_congestion_link(contentid, signguCd, tAtsNm) 생성. API가 contentid→집중률 시계열 해석에 사용.

사용법: python pipelines/build_links.py  (ingest_pois + ingest_congestion 이후)
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

DB = Path(__file__).resolve().parent.parent / "data" / "hiddenkorea.db"
_WS = re.compile(r"\s+")
_PAREN = re.compile(r"\(.*?\)")


def norm(s: str) -> str:
    return _PAREN.sub("", _WS.sub("", (s or ""))).lower()


def main() -> int:
    con = sqlite3.connect(DB)
    con.create_function("norm", 1, norm)
    con.execute("DROP TABLE IF EXISTS poi_congestion_link")
    con.execute("""CREATE TABLE poi_congestion_link (
        contentid TEXT PRIMARY KEY, signguCd TEXT, tAtsNm TEXT)""")
    # 시군구코드(=ldongRegnCd+ldongSignguCd) + 정규화 제목 일치. 관광지·문화시설 우선.
    con.execute("""
        INSERT OR IGNORE INTO poi_congestion_link (contentid, signguCd, tAtsNm)
        SELECT p.contentid, c.signguCd, c.tAtsNm
        FROM places p
        JOIN (SELECT DISTINCT signguCd, tAtsNm FROM congestion_forecast) c
          ON (p.ldongRegnCd || p.ldongSignguCd) = c.signguCd
         AND norm(p.title) = norm(c.tAtsNm)
    """)
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM poi_congestion_link").fetchone()[0]
    spots = con.execute("SELECT COUNT(DISTINCT signguCd||tAtsNm) FROM congestion_forecast").fetchone()[0]
    con.execute("CREATE INDEX IF NOT EXISTS idx_link_spot ON poi_congestion_link(signguCd, tAtsNm)")
    con.commit()
    con.close()
    print(f"링크 생성: {n}건 (집중률 관광지 {spots}곳 대비 {n/spots:.1%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
