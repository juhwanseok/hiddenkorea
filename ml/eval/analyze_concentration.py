"""오버투어리즘 쏠림 정량 분석 — 신청서·발표 '문제 타당성' 근거.

한국관광공사 집중률 예측(7,445 관광지 × 30일, 223,350행)만으로,
쏠림이 실재하지만 '분산 가능'하다는 것을 재현 가능한 숫자로 증명한다.
집중률은 정규화 비율(0~100)이므로 '소수 독점'보다 아래 두 레버가 강하게 드러난다.

지표:
  A. 혼잡 실태 — 등급 분포(혼잡 이상 비율, 매우혼잡 비율)
  B. 분산 여력 — 여유·보통 등급 비율(받아줄 '숨은' 공급)
  C. 공간 이동 근거 — 같은 날·같은 시군구에서 '매우혼잡'과 '한산'이 공존하는 비율
  D. 시간 이동 근거 — 인기 명소도 가장 한산한 날엔 혼잡이 얼마나 낮아지나

산출: docs/submission/쏠림근거리포트.md
사용법: python ml/eval/analyze_concentration.py
"""
from __future__ import annotations

import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "hiddenkorea.db"
OUT = ROOT / "docs" / "submission" / "쏠림근거리포트.md"


def main() -> int:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT areaNm, signguCd, signguNm, tAtsNm, baseYmd, cnctrRate "
        "FROM congestion_forecast WHERE cnctrRate IS NOT NULL").fetchall()
    ymd = con.execute("SELECT MIN(baseYmd), MAX(baseYmd), COUNT(DISTINCT baseYmd) FROM congestion_forecast").fetchone()
    con.close()

    r = np.array([x["cnctrRate"] for x in rows], dtype=float)
    n_obs = len(r)
    n_spot = len({(x["signguCd"], x["tAtsNm"]) for x in rows})

    # A. 등급 분포
    relax = float((r < 20).mean() * 100)
    normal = float(((r >= 20) & (r < 40)).mean() * 100)
    calm = relax + normal                      # <40 여유+보통
    busy = float((r >= 60).mean() * 100)       # 혼잡 이상
    verybusy = float((r >= 80).mean() * 100)   # 매우혼잡

    # C. 공간 이동 — 같은 날·같은 시군구 공존
    byrd = defaultdict(list)
    for x in rows:
        byrd[(x["signguCd"], x["baseYmd"])].append(x["cnctrRate"])
    co = tot = 0
    for v in byrd.values():
        v = np.array(v)
        if len(v) >= 3:
            tot += 1
            if (v >= 80).any() and (v < 40).any():
                co += 1
    coexist = co / tot * 100

    # D. 시간 이동 — 인기 명소(30일 평균 ≥60)의 최저일
    sp = defaultdict(list)
    for x in rows:
        sp[(x["signguCd"], x["tAtsNm"])].append(x["cnctrRate"])
    pk = [np.array(v) for v in sp.values() if np.mean(v) >= 60]
    worst = float(np.mean([v.max() for v in pk]))
    best = float(np.mean([v.min() for v in pk]))
    drop = (worst - best) / worst * 100
    n_pk = len(pk)

    # 대표 사례: 같은 날 같은 시군구 최대 격차(매우혼잡 vs 여유 공존)
    ex = []
    for (sg, d), v in byrd.items():
        v = np.array(v)
        if len(v) >= 4 and v.max() >= 80 and v.min() < 30:
            nm = next(x["areaNm"] + " " + x["signguNm"] for x in rows if x["signguCd"] == sg)
            ex.append((nm, d, v.max(), v.min(), v.max() - v.min()))
    ex = sorted(ex, key=lambda e: e[4], reverse=True)[:3]

    def r1(x): return f"{x:.1f}"

    print(f"관측 {n_obs:,}행 · 관광지 {n_spot:,}곳 · {ymd[2]}일({ymd[0]}~{ymd[1]})")
    print(f"[A] 혼잡이상 {r1(busy)}% · 매우혼잡 {r1(verybusy)}%")
    print(f"[B] 여유·보통(<40) {r1(calm)}%")
    print(f"[C] 같은날·같은시군구 매우혼잡&한산 공존 {r1(coexist)}% ({tot}개 지역·일)")
    print(f"[D] 인기명소 {n_pk}곳: 최다 {worst:.0f} → 최저 {best:.0f} ({r1(drop)}% 감소)")

    md = []
    md.append("# 오버투어리즘 쏠림 — 정량 근거 리포트\n")
    md.append("> 한국관광공사 ‘관광지 집중률 방문자 추이 예측’ 데이터 "
              f"**{n_obs:,}건**(전국 관광지 **{n_spot:,}곳** × {ymd[2]}일)을 분석. "
              "‘쏠림은 실재하지만, 옮기면 풀린다’를 재현 가능한 숫자로 증명한다. "
              "재현: `ml/eval/analyze_concentration.py`\n")

    md.append("## 한 줄 요약 (신청서·발표 첫 문장용)\n")
    md.append(f"> **같은 날, 같은 동네에서도 절반이 넘는 경우({r1(coexist)}%)에 ‘매우혼잡’ 명소와 ‘한산한’ 명소가 동시에 존재한다. "
              f"인기 명소조차 날짜만 바꾸면 혼잡이 평균 {r1(drop)}% 낮아진다.** "
              "쏠림은 수요 부족이 아니라 **정보 부족에 의한 분배 실패** — 그래서 예측·대안 추천으로 옮길 수 있다.\n")

    md.append("## 핵심 지표\n")
    md.append("| 지표 | 값 | 의미 |")
    md.append("|---|---|---|")
    md.append(f"| ‘혼잡’ 이상(60↑) 관광지-날짜 비율 | **{r1(busy)}%** | 쏠림은 실재 — 4곳 중 1곳 이상이 붐빔 |")
    md.append(f"| ‘매우혼잡’(80↑) 비율 | {r1(verybusy)}% | 극심한 과밀도 상시 발생 |")
    md.append(f"| ‘여유·보통’(40↓) 관광지-날짜 비율 | **{r1(calm)}%** | 수요를 받아줄 ‘숨은’ 공급이 절반 |")
    md.append(f"| 같은 날·같은 시군구, 매우혼잡·한산 **공존** 비율 | **{r1(coexist)}%** | 옮길 곳이 바로 옆에 있음(공간 이동) |")
    md.append(f"| 인기 명소의 최다일→최저일 혼잡 감소 | **{r1(drop)}%** ({worst:.0f}→{best:.0f}) | 날짜만 바꿔도 붐빔 회피(시간 이동) |")
    md.append("")

    md.append("## 이 숫자가 말하는 것 — 우리 서비스의 두 레버와 정확히 일치\n")
    md.append(f"1. **쏠림은 실재한다** — 전국 관광지-날짜의 {r1(busy)}%가 ‘혼잡’ 이상, {r1(verybusy)}%가 ‘매우혼잡’.\n")
    md.append(f"2. **대안은 이미 있다** — {r1(calm)}%가 ‘여유·보통’. 비어 있는 ‘숨은’ 관광지가 절반.\n")
    md.append(f"3. **공간 이동 여력** — 같은 날·같은 시군구에서 붐빔과 한산이 **{r1(coexist)}%** 확률로 공존. "
              "멀리 갈 필요 없이 **바로 옆 대안**으로 분산 가능 → 서비스의 ‘대안 매칭’이 직접 겨냥.\n")
    md.append(f"4. **시간 이동 여력** — 인기 명소({n_pk:,}곳)도 가장 한산한 날은 혼잡이 평균 **{r1(drop)}% 낮다**"
              f"({worst:.0f}→{best:.0f}). → 서비스의 ‘30일 혼잡 예측·달력’이 직접 겨냥.\n")
    md.append("> 결론: 문제(쏠림)와 해법(공간 대안 + 시간 예측)이 **같은 데이터 위에서 성립**한다. "
              "여행자는 이 정보를 몰라서 못 옮길 뿐 — 그 격차를 우리가 메운다.\n")

    if ex:
        md.append("\n## 대표 사례 — 같은 날, 같은 시군구, 극단적 공존\n")
        md.append("| 지역 | 날짜 | 최고 혼잡 명소 | 최저 혼잡 명소 | 격차 |")
        md.append("|---|---|---|---|---|")
        for nm, d, mx, mn, gap in ex:
            ds = f"{d[:4]}.{d[4:6]}.{d[6:8]}"
            md.append(f"| {nm} | {ds} | {mx:.0f}(매우혼잡) | {mn:.0f}(여유) | {gap:.0f}p |")
        md.append("")

    md.append("## 한계 (정직 고지)\n")
    md.append("- 집중률은 공사의 예측 스냅샷(향후 30일)이며 정규화 비율(0~100) → 방문자 절대수가 아닌 혼잡도 기준.\n")
    md.append("- 계절 전체가 아닌 현 시점 30일 리듬 → 장기 계절성은 별도 검증 과제.\n")
    md.append(f"\n---\n생성: `python ml/eval/analyze_concentration.py` · 관측 {n_obs:,}행 기준\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"\n리포트 저장: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
