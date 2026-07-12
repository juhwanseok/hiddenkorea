"""W3 — 매칭 후보 풀 임베딩 (fastembed paraphrase-multilingual-MiniLM-L12-v2, CPU/ONNX).

대상: 관광지(12) + 문화시설(14) — 대안 추천 후보 풀 (DECISION_LOG #12: v0는 제목+분류+주소).
출력: data/embeddings.npz (ids: contentid[], vecs: float32[N,384])
모델: 한국어 지원 다국어 MiniLM(384d). fastembed 미지원인 e5-small 대신 채택(DECISION_LOG #13).

사용법: python pipelines/embed_pois.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "hiddenkorea.db"
OUT = ROOT / "data" / "embeddings.npz"
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
POOL_TYPES = ("12", "14", "28", "38")  # 관광지, 문화시설, 레포츠, 쇼핑(시장 등)
TYPE_LABEL = {"12": "관광지", "14": "문화시설", "28": "레포츠", "38": "쇼핑"}


def build_text(row: sqlite3.Row) -> str:
    parts = [row["title"] or "", TYPE_LABEL.get(row["contenttypeid"], ""), row["addr1"] or ""]
    return " ".join(p for p in parts if p).strip()


def main() -> int:
    if not DB.exists():
        print(f"{DB} 없음")
        return 1
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    q = f"SELECT contentid, title, contenttypeid, addr1 FROM places WHERE contenttypeid IN ({','.join('?'*len(POOL_TYPES))}) AND title<>''"
    rows = con.execute(q, POOL_TYPES).fetchall()
    con.close()
    ids = [r["contentid"] for r in rows]
    texts = [build_text(r) for r in rows]
    print(f"임베딩 대상 {len(texts)}건 (관광지+문화시설)")

    model = TextEmbedding(MODEL)
    vecs = np.array(list(model.embed(texts, batch_size=256)), dtype=np.float32)
    # 정규화(코사인=내적)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9
    np.savez(OUT, ids=np.array(ids), vecs=vecs)
    print(f"저장: {OUT}  shape={vecs.shape}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
