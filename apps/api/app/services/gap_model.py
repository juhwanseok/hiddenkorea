"""ML 갭 모델 추론 — 커버리지 밖 POI 혼잡 근사 (source=HK_MODEL).

data/congestion_gap_model.txt (LightGBM) + congestion_gap_meta.json 로드.
지역·카테고리·달력 피처로 (POI, 날짜) 혼잡지수 예측 + 30일 시계열 생성.
모델 없거나 실패 시 None 반환 → 호출측이 시군구 평균으로 폴백.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

_DATA = Path(__file__).resolve().parents[4] / "data"
_MODEL = _DATA / "congestion_gap_model.txt"
_META = _DATA / "congestion_gap_meta.json"


@lru_cache(maxsize=1)
def _load():
    import json
    import lightgbm as lgb
    if not (_MODEL.exists() and _META.exists()):
        return None
    meta = json.loads(_META.read_text(encoding="utf-8"))
    booster = lgb.Booster(model_str=_MODEL.read_text(encoding="utf-8"))
    return booster, meta


def available() -> bool:
    return _load() is not None


def _feat_row(meta: dict, area: str, lcls1: str, lcls2: str, date_iso: str) -> dict:
    d = datetime.strptime(date_iso, "%Y-%m-%d")
    bm = datetime.strptime(meta["base_min"], "%Y%m%d")
    enc = lambda col, v: meta["maps"][col].get(str(v), -1)
    return {
        "days_ahead": (d - bm).days,
        "dow": d.weekday(),
        "is_weekend": int(d.weekday() >= 5),
        "is_holiday": int(date_iso in set(meta["holidays"])),
        "month": d.month,
        "areaCd": enc("areaCd", area),
        "lcls1": enc("lcls1", lcls1),
        "lcls2": enc("lcls2", lcls2),
    }


def _predict(meta, booster, rows: list[dict]) -> np.ndarray:
    cols = meta["num_cols"] + meta["cat_cols"]
    X = pd.DataFrame(rows)[cols]
    return np.clip(booster.predict(X), 0, 100)


def predict_index(area: str, lcls1: str, lcls2: str, date_iso: str) -> float | None:
    m = _load()
    if not m:
        return None
    booster, meta = m
    val = _predict(meta, booster, [_feat_row(meta, area, lcls1, lcls2, date_iso)])[0]
    return round(float(val), 1)


def predict_batch(items: list[tuple[str, str, str, str]]) -> list[float] | None:
    """(area, lcls1, lcls2, date_iso) 배치 → 혼잡지수 리스트. 일정 추천용."""
    m = _load()
    if not m or not items:
        return None
    booster, meta = m
    rows = [_feat_row(meta, a, l1, l2, dt) for a, l1, l2, dt in items]
    return [round(float(v), 1) for v in _predict(meta, booster, rows)]


def predict_series(area: str, lcls1: str, lcls2: str) -> list[dict]:
    """모델 학습 예보창(base_min~+29)에 대한 30일 시계열."""
    m = _load()
    if not m:
        return []
    booster, meta = m
    bm = datetime.strptime(meta["base_min"], "%Y%m%d")
    dates = [(bm + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
    rows = [_feat_row(meta, area, lcls1, lcls2, dt) for dt in dates]
    vals = _predict(meta, booster, rows)
    return [{"date": dt, "index": round(float(v), 1)} for dt, v in zip(dates, vals)]
