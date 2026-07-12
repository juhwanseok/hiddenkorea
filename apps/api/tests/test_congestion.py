"""W2 혼잡도 엔진 단위/통합 테스트 (CODING_GUIDELINES 필수 테스트 대상).

핵심 로직(등급 경계, 제목 정규화)과 API 계약을 검증. DB가 있으면 실데이터 스모크도 수행.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.constants import grade_of
from app.services.congestion import norm_title, ymd_to_iso

DB = Path(__file__).resolve().parents[3] / "data" / "hiddenkorea.db"


def test_grade_boundaries():
    assert grade_of(0)[0] == "여유"
    assert grade_of(19.9)[0] == "여유"
    assert grade_of(20)[0] == "보통"
    assert grade_of(59.9)[0] == "다소혼잡"
    assert grade_of(60)[0] == "혼잡"
    assert grade_of(85)[0] == "매우혼잡"
    assert grade_of(100)[0] == "매우혼잡"


def test_norm_title():
    assert norm_title("경복궁") == "경복궁"
    assert norm_title("묘각사 (서울)") == "묘각사"
    assert norm_title("KT&G  상상마당") == "kt&g상상마당"


def test_ymd_to_iso():
    assert ymd_to_iso("20261003") == "2026-10-03"


@pytest.mark.skipif(not DB.exists(), reason="DB 미적재 — 데이터 파이프라인 후 실행")
def test_health_and_congestion_contract():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["pois"] > 0

    # 실데이터: 경복궁(관광지) contentid 조회 → 200 & 필드 계약
    con_id = _find_gyeongbokgung()
    if con_id:
        r = client.get(f"/api/congestion?contentId={con_id}&date=2026-10-03")
        assert r.status_code == 200
        body = r.json()
        assert 0 <= body["index"] <= 100
        assert body["source"] in ("KTO_FORECAST", "HK_MODEL")
        assert body["grade"]


def _find_gyeongbokgung() -> str | None:
    import sqlite3
    con = sqlite3.connect(DB)
    row = con.execute("SELECT contentid FROM places WHERE title='경복궁' LIMIT 1").fetchone()
    con.close()
    return row[0] if row else None
