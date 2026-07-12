"""W1 EDA — POI 분포 + 집중률 커버리지 교차 분석.

입력: data/hiddenkorea.db (ingest_pois 결과), data/d2_spots.csv (집중률 7,445곳)
출력: ml/eda/out/*.png (발표 소재), ml/eda/out/eda_report.md (요약 수치)

분석:
 1) POI 콘텐츠타입/시도 분포
 2) 이미지 보유율(임베딩·카드 UI 품질 프록시)
 3) 집중률 커버 관광지(d2_spots) ↔ TourAPI POI 매칭률 (signgu+제목)
 4) 좌표 결측률(지도 표시 가능 비율)

사용법: python ml/eda/eda_pois.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# 한글 폰트 (Windows 기본)
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent.parent
DB = ROOT / "data" / "hiddenkorea.db"
D2 = ROOT / "data" / "d2_spots.csv"
OUT = ROOT / "ml" / "eda" / "out"

TYPE_LABEL = {"12": "관광지", "14": "문화시설", "15": "축제공연행사", "25": "여행코스",
              "28": "레포츠", "32": "숙박", "38": "쇼핑", "39": "음식점"}
SIDO_LABEL = {"11": "서울", "26": "부산", "27": "대구", "28": "인천", "30": "대전",
              "31": "울산", "36": "세종", "41": "경기", "43": "충북", "44": "충남",
              "47": "경북", "48": "경남", "50": "제주", "51": "강원", "52": "전북",
              "12": "광주/전남통합", "46": "전남"}


def norm(s: pd.Series) -> pd.Series:
    """제목 정규화 — 매칭용(공백·괄호 제거, 소문자)."""
    return (s.fillna("").str.replace(r"\s+", "", regex=True)
            .str.replace(r"\(.*?\)", "", regex=True).str.lower())


def main() -> int:
    if not DB.exists():
        print(f"{DB} 없음 — 먼저 ingest_pois.py 실행")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    df = pd.read_sql("SELECT * FROM places", con)
    con.close()
    n = len(df)
    lines: list[str] = [f"# W1 EDA 리포트\n", f"- 총 POI: **{n:,}**\n"]

    # 1) 콘텐츠타입 분포
    t = df["contenttypeid"].value_counts()
    t.index = [f"{TYPE_LABEL.get(str(i), i)}({i})" for i in t.index]
    ax = t.plot.bar(figsize=(9, 4), title="콘텐츠타입별 POI 수", color="#0d9488")
    ax.set_ylabel("건수"); plt.tight_layout(); plt.savefig(OUT / "poi_by_type.png", dpi=120); plt.close()
    lines.append("## 콘텐츠타입 분포\n" + t.to_frame("건수").to_markdown() + "\n")

    # 2) 시도 분포
    s = df["ldongRegnCd"].value_counts()
    s.index = [f"{SIDO_LABEL.get(str(i), i)}({i})" for i in s.index]
    ax = s.head(17).plot.bar(figsize=(10, 4), title="시도별 POI 수", color="#f97316")
    ax.set_ylabel("건수"); plt.tight_layout(); plt.savefig(OUT / "poi_by_sido.png", dpi=120); plt.close()
    lines.append("## 시도 분포(상위)\n" + s.head(17).to_frame("건수").to_markdown() + "\n")

    # 3) 품질: 이미지/좌표 보유율
    img_rate = (df["firstimage"].fillna("").str.len() > 0).mean()
    xy_rate = ((df["mapx"].fillna("").str.len() > 0) & (df["mapy"].fillna("").str.len() > 0)).mean()
    lines.append(f"## 데이터 품질\n- 대표이미지 보유율: **{img_rate:.1%}** (카드 UI·임베딩 품질 프록시)\n"
                 f"- 좌표 보유율: **{xy_rate:.1%}** (지도 표시 가능)\n")

    # 4) 집중률 커버 관광지 ↔ TourAPI 매칭
    if D2.exists():
        d2 = pd.read_csv(D2, dtype=str)
        df["signguCd"] = df["ldongRegnCd"].fillna("") + df["ldongSignguCd"].fillna("")
        df["_k"] = norm(df["title"])
        d2["_k"] = norm(d2["tAtsNm"])
        poi_keys = set(zip(df["signguCd"], df["_k"]))
        d2["matched"] = [(sg, k) in poi_keys for sg, k in zip(d2["signguCd"], d2["_k"])]
        mrate = d2["matched"].mean()
        lines.append(f"## 집중률 커버 관광지 ↔ TourAPI 매칭\n"
                     f"- 집중률 관광지 {len(d2):,}곳 중 TourAPI POI와 (시군구+제목) 매칭: "
                     f"**{d2['matched'].sum():,}곳 ({mrate:.1%})**\n"
                     f"- 매칭분 → 이미지·좌표·상세 확보 / 미매칭분 → 좌표 근사 또는 상세조회 대상\n")
        # 미매칭 샘플
        miss = d2[~d2["matched"]]["tAtsNm"].head(15).tolist()
        lines.append(f"- 미매칭 샘플: {', '.join(miss)}\n")

    (OUT / "eda_report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n저장: {OUT}/ (poi_by_type.png, poi_by_sido.png, eda_report.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
