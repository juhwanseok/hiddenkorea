"""W3 매칭 엔진 테스트 — 임베딩 산출물이 있을 때만 실행."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "data" / "hiddenkorea.db"
EMB = ROOT / "data" / "embeddings.npz"

pytestmark = pytest.mark.skipif(
    not (DB.exists() and EMB.exists()), reason="DB/임베딩 미생성 — W3 파이프라인 후 실행"
)


def _cid(title: str) -> str | None:
    con = sqlite3.connect(DB)
    row = con.execute("SELECT contentid FROM places WHERE title=? LIMIT 1", (title,)).fetchone()
    con.close()
    return row[0] if row else None


def test_alternatives_contract():
    from app.services import matching
    cid = _cid("경복궁")
    assert cid, "경복궁 POI 존재해야 함"
    alts = matching.alternatives(cid, "2026-07-18", k=3)
    assert 1 <= len(alts) <= 3
    for a in alts:
        assert a["contentId"] != cid                 # 원본 제외
        assert 0 <= a["congestion"] < 70             # 자기조절: 혼잡 대안 제외
        assert 0 <= a["simPct"] <= 100
        assert a["distanceKm"] >= 0


def test_api_alternatives():
    from fastapi.testclient import TestClient
    from app.main import app
    cid = _cid("경복궁")
    r = TestClient(app).get(f"/api/alternatives?contentId={cid}&date=2026-07-18&k=3")
    assert r.status_code == 200
    body = r.json()
    assert body["origin"] == "경복궁" and body["count"] >= 1
    assert all(a["reason"] for a in body["alternatives"])   # 이유 문장 필수(폴백 포함)
