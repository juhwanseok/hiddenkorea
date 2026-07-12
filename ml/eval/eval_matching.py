"""W3 매칭 품질 평가 (재정의) — EVALUATION_GUIDELINES §2.

발견(DECISION_LOG #14): 유사도 골드셋은 '유명하지만 붐비는' 명소를 정답으로 요구하나,
본 서비스는 오버투어리즘 분산이 목적이라 붐비는 대안을 '의도적으로' 제외한다.
→ 유사도 nDCG는 부적합. 대신 (1)분류 정합률 (2)혼잡 저감 (3)정성 표로 평가.
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.services import matching  # noqa: E402
from app.services.congestion import norm_title  # noqa: E402

DB = ROOT / "data" / "hiddenkorea.db"
GOLD = ROOT / "data" / "goldset.jsonl"
DATE = "2026-07-18"
POOL = ("12", "14", "28", "38")
buf = io.StringIO()


def resolve(con, title):
    con.create_function("nt", 1, norm_title)
    r = con.execute(f"SELECT contentid,lclsSystm2 FROM places WHERE nt(title)=nt(?) "
                    f"AND contenttypeid IN ({','.join('?'*len(POOL))}) LIMIT 1", (title, *POOL)).fetchone()
    return (r[0], r[1]) if r else (None, None)


def main():
    con = sqlite3.connect(DB)
    idx = matching.get_index()
    gold = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]

    cat_hits, cat_tot, cong_deltas, evaluable = 0, 0, [], 0
    buf.write("# W3 매칭 정성 평가\n\n")
    for d in gold:
        cid, lcls2 = resolve(con, d["origin"])
        if not cid or cid not in idx.pos:
            continue
        evaluable += 1
        i = idx.pos[cid]
        alts = matching.alternatives(cid, DATE, k=3)
        # 원본 혼잡(링크 있으면)
        buf.write(f"## {d['origin']}  (분류 {idx.lcls2[i]})\n")
        for a in alts:
            j = idx.pos[a["contentId"]]
            same = idx.lcls2[j] == idx.lcls2[i]
            cat_hits += same; cat_tot += 1
            cong_deltas.append(a["congestion"])
            buf.write(f"  - {a['name']} | 분류 {idx.lcls2[j]}{'✓' if same else '✗'} "
                      f"| 유사도 {a['simPct']} | 혼잡 {a['congestion']} | {a['distanceKm']}km\n")
        buf.write("\n")

    con.close()
    cat_rate = cat_hits / cat_tot if cat_tot else 0
    avg_cong = sum(cong_deltas) / len(cong_deltas) if cong_deltas else 0
    summary = (f"평가 원본 {evaluable}개 / 추천 {cat_tot}건\n"
               f"- **분류 정합률(top3 동일 중분류)**: {cat_rate:.1%}\n"
               f"- **추천 대안 평균 혼잡지수**: {avg_cong:.1f} (자기조절 임계 {matching.ALT_EXCLUDE_INDEX} 미만 보장)\n")
    buf.write("\n---\n## 요약\n" + summary)
    (ROOT / "ml" / "eval" / "matching_review.md").write_text(buf.getvalue(), encoding="utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    print(summary)
    print("저장: ml/eval/matching_review.md")


if __name__ == "__main__":
    main()
