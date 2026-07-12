"""[보류/참고] W3 — HiddenScore 가중치 그리드서치 + nDCG@3.

⚠️ DECISION_LOG #15: 유사도 nDCG는 오버투어리즘 분산 목적과 상충(붐비는 명소를 정답 요구)해
   본 지표는 폐기하고 eval_matching.py(분류정합률+혼잡저감)로 대체함. 이 스크립트는 진단용으로만 보존.

원문 설명:

골드셋(data/goldset.jsonl)의 원본→유사 관광지 관계로 매칭 품질 평가.
- 원본/정답 제목을 정규화해 매칭(제목 기반). 임베딩 풀에 없는 원본은 스킵(커버리지 리포트).
- 가중치 조합을 그리드서치, 평균 nDCG@3 최대 조합 선정.

사용법: python ml/eval/tune_weights.py
"""
from __future__ import annotations

import json
import math
import sqlite3
import sys
from itertools import product
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.services import matching  # noqa: E402
from app.services.congestion import norm_title  # noqa: E402

DB = ROOT / "data" / "hiddenkorea.db"
GOLD = ROOT / "data" / "goldset.jsonl"
DATE = "2026-07-18"
POOL_TYPES = ("12", "14", "28", "38")


def resolve(con: sqlite3.Connection, title: str) -> str | None:
    """제목 → contentid (임베딩 풀 타입 우선, 정규화 일치)."""
    con.create_function("nt", 1, norm_title)
    q = (f"SELECT contentid FROM places WHERE nt(title)=nt(?) "
         f"AND contenttypeid IN ({','.join('?'*len(POOL_TYPES))}) LIMIT 1")
    row = con.execute(q, (title, *POOL_TYPES)).fetchone()
    return row[0] if row else None


def _is_rel(title: str, relevant: set[str]) -> bool:
    """정답 판정 — 접미어 차이 허용(포함 관계). 예: '창덕궁낙선재' ⊃ '창덕궁'."""
    nt = norm_title(title)
    return any(r and (r in nt or nt in r) for r in relevant)


def ndcg_at_k(rec_titles: list[str], relevant: set[str], k: int = 3) -> float:
    rels = [1.0 if _is_rel(t, relevant) else 0.0 for t in rec_titles[:k]]
    dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rels))
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(k, len(relevant))))
    return dcg / ideal if ideal else 0.0


def load_gold():
    items = []
    for line in GOLD.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            items.append((d["origin"], {norm_title(x) for x in d["relevant"]}))
    return items


def evaluate(weights: dict, gold, con) -> tuple[float, int]:
    scores, n = [], 0
    for origin, relevant in gold:
        cid = resolve(con, origin)
        if not cid or cid not in matching.get_index().pos:
            continue
        alts = matching.alternatives(cid, DATE, k=3, weights=weights)
        scores.append(ndcg_at_k([a["name"] for a in alts], relevant))
        n += 1
    return (sum(scores) / n if n else 0.0), n


def main() -> int:
    con = sqlite3.connect(DB)
    gold = load_gold()

    # 그리드서치 (0.1 스텝, 합=1)
    grid = [w for w in product([round(x * 0.1, 1) for x in range(11)], repeat=4)
            if abs(sum(w) - 1.0) < 1e-9 and w[0] > 0]  # sim>0 강제
    best, best_ndcg = None, -1.0
    for sim, cong, dist, qual in grid:
        w = {"sim": sim, "cong": cong, "dist": dist, "qual": qual}
        ndcg, n = evaluate(w, gold, con)
        if ndcg > best_ndcg:
            best, best_ndcg, cov = w, ndcg, n

    default = {"sim": 0.4, "cong": 0.3, "dist": 0.2, "qual": 0.1}
    def_ndcg, cov = evaluate(default, gold, con)
    con.close()

    print(f"골드셋 원본 {len(gold)}개 중 평가 가능 {cov}개")
    print(f"기본 가중치 {default} → nDCG@3 = {def_ndcg:.3f}")
    print(f"최적 가중치 {best} → nDCG@3 = {best_ndcg:.3f}")
    print(f"합격선 0.70 {'통과' if best_ndcg >= 0.70 else '미달'}")
    out = ROOT / "ml" / "eval" / "weights_result.json"
    out.write_text(json.dumps({"default": default, "default_ndcg": def_ndcg,
                               "best": best, "best_ndcg": best_ndcg, "coverage": cov},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
