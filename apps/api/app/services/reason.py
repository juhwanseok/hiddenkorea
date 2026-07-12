"""대안 추천 이유 문장화 (ML_GUIDELINES 계층3, PROMPTS.md P1).

Claude Haiku 호출 — 키 없거나 실패 시 템플릿 폴백(서비스 무중단). 사실은 컨텍스트 주입(환각 차단).
"""
from __future__ import annotations

import os

_MODEL = os.getenv("HK_LLM_MODEL", "claude-haiku-4-5-20251001")


def template_reason(origin_name: str, alt: dict) -> str:
    return f"{origin_name}과(와) 비슷한 분위기의 명소로, 예상 혼잡 {alt['congestion']:.0f}%로 여유롭습니다."


def llm_reason(origin_name: str, origin_ov: str, alt: dict, alt_ov: str) -> str:
    """P1 프롬프트. 실패 시 템플릿."""
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return template_reason(origin_name, alt)
    try:
        import anthropic  # 지연 임포트
        client = anthropic.Anthropic(api_key=key)
        prompt = (
            f"원본: {origin_name} ({origin_ov[:150]})\n"
            f"대안: {alt['name']} ({alt_ov[:150]})\n"
            f"유사도: {alt['simPct']}% / 대안 예상 혼잡: {alt['congestion']}% / 거리: {alt['distanceKm']}km\n"
            "위 [데이터]의 사실만 사용해, 원본 대신 대안을 추천하는 이유를 한국어 한 문장(45자 이내)으로. "
            "과장·확인 불가 정보 금지. 이유 문장만 출력."
        )
        msg = client.messages.create(
            model=_MODEL, max_tokens=80,
            system="너는 한국 관광 큐레이터다. 간결하고 정확하게.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
        return text or template_reason(origin_name, alt)
    except Exception:  # noqa: BLE001 — LLM 장애는 폴백
        return template_reason(origin_name, alt)
