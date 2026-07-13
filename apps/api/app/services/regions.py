"""지역(시도/시군구) 목록 — region_map_d2.csv(행정표준코드+이름) 기반."""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

_CSV = Path(__file__).resolve().parents[4] / "data" / "region_map_d2.csv"


@lru_cache(maxsize=1)
def _load() -> dict:
    sido: dict[str, str] = {}
    sigungu: dict[str, list[dict]] = {}
    if _CSV.exists():
        with _CSV.open(encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                a, an = r["areaCd"], r["areaNm"]
                sido.setdefault(a, an)
                sigungu.setdefault(a, []).append({"code": r["signguCd"], "name": r["signguNm"]})
    return {"sido": sido, "sigungu": sigungu}


def sido_list() -> list[dict]:
    d = _load()
    return [{"code": c, "name": n} for c, n in sorted(d["sido"].items())]


def sigungu_list(area_cd: str) -> list[dict]:
    return sorted(_load()["sigungu"].get(area_cd, []), key=lambda x: x["code"])
