"""ML 갭 모델 — 커버리지 밖 POI 혼잡 근사 (ML_GUIDELINES 계층1, HK_MODEL).

학습: 집중률 커버 spot(congestion_forecast) ⋈ poi_congestion_link ⋈ places(카테고리)
      → (지역 areaCd + 카테고리 lclsSystm1/2 + 달력) 로 cnctrRate 회귀.
전이: 미커버 POI는 자신의 지역·카테고리·날짜로 혼잡지수를 추론.

한계(정직히): 학습 데이터가 예측 스냅샷(today~+30)이라 계절 범위가 좁음 → 현 30일 리듬 전이에 특화.
평가: 시간분할(마지막 5일 홀드아웃) MAE + Spearman 순위상관.

산출: data/congestion_gap_model.txt, data/congestion_gap_meta.json
사용법: python ml/train/train_congestion_gap.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "hiddenkorea.db"
MODEL_OUT = ROOT / "data" / "congestion_gap_model.txt"
META_OUT = ROOT / "data" / "congestion_gap_meta.json"

# 2026 대한민국 공휴일(간이) — 예보창(7~8월)엔 광복절만 걸리나 일반화 위해 포함
HOLIDAYS_2026 = {"2026-01-01", "2026-02-16", "2026-02-17", "2026-02-18", "2026-03-01",
                 "2026-05-05", "2026-05-24", "2026-06-06", "2026-08-15",
                 "2026-09-24", "2026-09-25", "2026-09-26", "2026-10-03", "2026-10-09", "2026-12-25"}
CAT_COLS = ["areaCd", "lcls1", "lcls2"]
NUM_COLS = ["days_ahead", "dow", "is_weekend", "is_holiday", "month"]


def load() -> pd.DataFrame:
    con = sqlite3.connect(DB)
    df = pd.read_sql("""
        SELECT cf.baseYmd, cf.areaCd, cf.cnctrRate, p.lclsSystm1 AS lcls1, p.lclsSystm2 AS lcls2
        FROM congestion_forecast cf
        JOIN poi_congestion_link l ON cf.signguCd=l.signguCd AND cf.tAtsNm=l.tAtsNm
        JOIN places p ON l.contentid=p.contentid
        WHERE cf.cnctrRate IS NOT NULL
    """, con)
    con.close()
    return df


def featurize(df: pd.DataFrame, base_min: str | None = None) -> tuple[pd.DataFrame, str]:
    d = pd.to_datetime(df["baseYmd"], format="%Y%m%d")
    iso = d.dt.strftime("%Y-%m-%d")
    base_min = base_min or df["baseYmd"].min()
    bm = pd.to_datetime(base_min, format="%Y%m%d")
    out = pd.DataFrame({
        "days_ahead": (d - bm).dt.days,
        "dow": d.dt.dayofweek,
        "is_weekend": (d.dt.dayofweek >= 5).astype(int),
        "is_holiday": iso.isin(HOLIDAYS_2026).astype(int),
        "month": d.dt.month,
        "areaCd": df["areaCd"].astype(str),
        "lcls1": df["lcls1"].astype(str),
        "lcls2": df["lcls2"].astype(str),
    })
    return out, base_min


def main() -> int:
    df = load()
    print(f"학습 원천 {len(df):,}행 / 커버 spot 카테고리 결합")
    X, base_min = featurize(df)
    y = df["cnctrRate"].astype(float).values

    # 카테고리 인코딩(정수) + 매핑 저장
    maps = {}
    for c in CAT_COLS:
        cats = sorted(X[c].unique())
        m = {v: i for i, v in enumerate(cats)}
        maps[c] = m
        X[c] = X[c].map(m).astype(int)

    # 시간분할: 마지막 5 days_ahead 홀드아웃
    cut = X["days_ahead"].max() - 5
    tr, va = X["days_ahead"] <= cut, X["days_ahead"] > cut
    feats = NUM_COLS + CAT_COLS
    dtr = lgb.Dataset(X.loc[tr, feats], y[tr.values], categorical_feature=CAT_COLS)
    dva = lgb.Dataset(X.loc[va, feats], y[va.values], reference=dtr, categorical_feature=CAT_COLS)
    params = {"objective": "regression_l1", "metric": "l1", "num_leaves": 63,
              "learning_rate": 0.05, "feature_fraction": 0.9, "verbose": -1}
    model = lgb.train(params, dtr, num_boost_round=400, valid_sets=[dva],
                      callbacks=[lgb.early_stopping(30, verbose=False)])

    pred = model.predict(X.loc[va, feats])
    mae = float(np.mean(np.abs(pred - y[va.values])))
    rho = float(spearmanr(pred, y[va.values]).correlation)
    imp = dict(zip(feats, model.feature_importance().tolist()))

    # LightGBM C 라이브러리가 한글 경로 쓰기 불가 → 파이썬으로 문자열 저장
    MODEL_OUT.write_text(model.model_to_string(), encoding="utf-8")
    META_OUT.write_text(json.dumps({
        "base_min": base_min, "maps": maps, "num_cols": NUM_COLS, "cat_cols": CAT_COLS,
        "holidays": sorted(HOLIDAYS_2026), "val_mae": mae, "val_spearman": rho,
        "feature_importance": imp,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"검증(마지막5일) MAE={mae:.2f}  Spearman={rho:.3f}")
    print(f"피처 중요도: {sorted(imp.items(), key=lambda x:-x[1])}")
    print(f"저장: {MODEL_OUT.name}, {META_OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
