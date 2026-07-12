"""ML 갭 모델 테스트 — 모델 산출물이 있을 때만."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "data" / "hiddenkorea.db"
MODEL = ROOT / "data" / "congestion_gap_model.txt"

pytestmark = pytest.mark.skipif(not (DB.exists() and MODEL.exists()),
                                reason="DB/갭모델 미생성 — train_congestion_gap 후 실행")


def test_gap_predict_range():
    from app.services import gap_model
    assert gap_model.available()
    v = gap_model.predict_index("11", "HS", "HS01", "2026-07-18")
    assert v is not None and 0 <= v <= 100
    series = gap_model.predict_series("11", "HS", "HS01")
    assert len(series) == 30 and all(0 <= s["index"] <= 100 for s in series)


def test_uncovered_poi_uses_model():
    """poi_congestion_link 없는 POI는 source=HK_MODEL + 30일 시계열 생성."""
    from fastapi.testclient import TestClient
    from app.main import app
    con = sqlite3.connect(DB)
    row = con.execute(
        """SELECT p.contentid FROM places p
           LEFT JOIN poi_congestion_link l ON p.contentid=l.contentid
           WHERE l.contentid IS NULL AND p.contenttypeid='12' AND p.mapx<>''
                 AND p.ldongRegnCd<>'' AND p.lclsSystm2<>'' LIMIT 1""").fetchone()
    con.close()
    assert row, "미커버 관광지 POI가 있어야 함"
    r = TestClient(app).get(f"/api/congestion?contentId={row[0]}&date=2026-07-18")
    assert r.status_code == 200
    b = r.json()
    assert b["source"] == "HK_MODEL"
    assert 0 <= b["index"] <= 100
    assert len(b["series30d"]) == 30      # 모델이 미커버 POI에도 30일 캘린더 제공
