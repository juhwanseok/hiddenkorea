"""SQLite 접근 헬퍼 (W2 로컬 staging. W1 인프라에서 Supabase Postgres로 이관 예정)."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# 레포 루트/data/hiddenkorea.db — 환경변수로 오버라이드 가능(테스트/배포)
_DEFAULT = Path(__file__).resolve().parents[4] / "data" / "hiddenkorea.db"
DB_PATH = Path(os.getenv("HK_DB_PATH", str(_DEFAULT)))


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con
