"""설정 — 레포 루트 .env 로드 + 외부 키/상수 노출."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# 레포 루트 .env (apps/api/app/core/config.py → parents[4] = repo root)
_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(_ROOT / ".env")

TOURAPI_KEY = os.getenv("TOURAPI_KEY", "").strip()
TOUR_COMMON = {"MobileOS": "ETC", "MobileApp": "HiddenKorea", "_type": "json"}
KOR_BASE = "https://apis.data.go.kr/B551011/KorService2"
