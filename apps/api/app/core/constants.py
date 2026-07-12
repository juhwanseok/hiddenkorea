"""튜닝·정책 상수 (CODING_GUIDELINES: 매직넘버 금지)."""
from __future__ import annotations

# 혼잡 지수(0~100) → 5등급. (하한 이상, 상한 미만)
CONGESTION_GRADES = [
    (0, 20, "여유", "#22c55e"),
    (20, 40, "보통", "#eab308"),
    (40, 60, "다소혼잡", "#f97316"),
    (60, 80, "혼잡", "#ef4444"),
    (80, 101, "매우혼잡", "#991b1b"),
]

# 혼잡도 출처
SRC_FORECAST = "KTO_FORECAST"   # 공사 집중률 예측 직접
SRC_MODEL = "HK_MODEL"          # 자체 ML 근사 (커버리지 갭)

# 대안 추천 제외 임계 (RED_TEAM A5: 자기조절 — 붐비는 곳은 대안에서 제외)
ALT_EXCLUDE_INDEX = 70


def grade_of(index: float) -> tuple[str, str]:
    """혼잡 지수 → (등급명, 색). 색+텍스트 병기(접근성)."""
    for lo, hi, name, color in CONGESTION_GRADES:
        if lo <= index < hi:
            return name, color
    return ("매우혼잡", "#991b1b") if index >= 80 else ("여유", "#22c55e")
