"""코스 엔진 테스트 — 동선 최적화·시간계산·API 계약."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "data" / "hiddenkorea.db"

from app.services.course import _haversine_matrix, _nearest_neighbor, _two_opt  # noqa: E402


def test_two_opt_shortens_route():
    # 사각형 4점 — 교차 경로를 2-opt가 개선
    lat = [0.0, 0.0, 1.0, 1.0]; lon = [0.0, 1.0, 0.0, 1.0]
    D = _haversine_matrix(lat, lon)
    order = _two_opt(_nearest_neighbor(D, 0), D)
    length = sum(D[order[i], order[i + 1]] for i in range(len(order) - 1))
    naive = sum(D[i, i + 1] for i in range(len(lat) - 1))
    assert length <= naive + 1e-9


@pytest.mark.skipif(not DB.exists(), reason="DB 미적재")
def test_api_course_contract():
    from fastapi.testclient import TestClient
    from app.main import app
    con = sqlite3.connect(DB)
    ids = [r[0] for r in con.execute(
        "SELECT contentid FROM places WHERE ldongRegnCd='11' AND mapx<>'' LIMIT 3").fetchall()]
    con.close()
    r = TestClient(app).get(f"/api/course?poiIds={','.join(ids)}&date=2026-07-18")
    assert r.status_code == 200
    b = r.json()
    assert b["stops"] == 3 and len(b["legs"]) == 3
    assert b["legs"][0]["seq"] == 1
    # 도착시간 단조 증가
    times = [leg["arrive"] for leg in b["legs"]]
    assert times == sorted(times)
    assert b["kakaoMapUrl"].startswith("https://map.kakao.com")
    assert b["narrative"]
