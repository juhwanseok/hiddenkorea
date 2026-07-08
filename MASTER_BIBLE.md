# MASTER DEVELOPMENT BIBLE — 숨은한국 (HiddenKorea)

> **이 파일 하나를 어떤 LLM(Claude Sonnet/Opus, GPT 등)에게 주면 프로젝트를 이어받을 수 있다.**
> 상세는 docs/ 의 문서가 진실의 원천이며, 이 파일은 그 압축 진입점이다. 최종 갱신: 2026-07-08.

---

## 1. 무엇을 왜 만드는가 (30초 요약)

- **대회**: 2026 관광데이터 활용 공모전 ②-2 웹·앱 구현 부문. 지정과제 2(오버투어리즘 분산) 선택.
- **서비스**: 방문 예정일의 관광지 혼잡도를 예측하고, 취향은 유지한 채 혼잡만 제거한 "비슷하지만 한적한" 대안지 3곳과 재구성 코스를 근거와 함께 추천하는 웹 서비스.
- **왜 이 주제**: 15개 후보 → 가중 매트릭스 1위(8.35). 데이터 실증 완료(공사 집중률 예측 API·연관관광지 API·시군구 방문자 API 모두 실존·무료 확인).
- **개발자**: 학부생 1인(AI/ML 강점, 프론트 약점) + AI 어시스턴트. 예산 월 2만원 이하.

## 2. 절대 제약 (위반 = 실격/치명)

1. 한국관광공사 OpenAPI가 **핵심 경로**에 필수 (장식 사용 시 데이터활용 0점)
2. 지정과제 2 부합 (부적합 판정 = 심사 제외)
3. **접수 마감 2026-07-21(화) 16:00** — api.visitkorea.or.kr, 회원가입 선행
4. 1차 기능심사(10월)까지 "개발 완료된 완성 서비스" — 심사위원 직접 조작 전제
5. ①부문/②-1과 동일 서비스 중복 출품 불가

## 3. 심사 배점 = 개발 우선순위

| 1차 심사 | 배점 | 우리 대응 |
|---|---|---|
| 구현성 (완결성·안정성·완성도) | 30 | 화면 4개 범위 동결, 폴백·캐시·keep-alive, 크래시 제로 |
| 기획력 (타당성·구체성·독창성) | 30 | "취향 유지 + 혼잡 제거" 독창 포지션, 정량 근거 |
| 데이터 활용 (공사 API 필수) | 20 | 공사 API 4종이 핵심 경로 + AI로 커버리지 확장 서사 |
| 발전성 (지속·확장) | 20 | 월 2만원 운영 구조, 다국어→지자체 B2B 로드맵 |

최종 PT(상위 3팀): 적정성 30/완성도 30/실용성 25/발표 15. 대상(장관상 1,000만)은 ①부문 상위 5팀과 통합 경쟁.

## 4. 시스템 한 장 요약

```
Next.js(Vercel) ─ REST ─ FastAPI(Cloud Run) ─ Supabase Postgres+pgvector
                              │
              ┌───────────────┼────────────────┐
        혼잡도 엔진        매칭 엔진         코스 엔진
   (공사 집중률 API      (e5 임베딩 +      (2-opt 동선 +
    + LightGBM 근사)     HiddenScore)      LLM 서사·폴백)
                              │
        배치(GitHub Actions cron): POI·집중률·방문자·기상 적재 + 주간 재학습
```

- **HiddenScore** = α·유사도 + β·(1−혼잡) + γ·접근성 + δ·정보품질 (α..δ는 골드셋 nDCG@3로 튜닝)
- LLM(Claude Haiku 4.5)은 문장화만 — 사실은 전부 DB 주입, 실패 시 템플릿 폴백
- 상세: docs/ARCHITECTURE.md, ML_GUIDELINES.md, DATA_GUIDELINES.md

## 5. 지금 해야 할 일 (이어받는 AI의 첫 행동)

1. `docs/PROJECT.md` 현재 상태 체크박스 확인
2. `docs/TASKS.md`에서 첫 ⬜ Task 수행 — 초기 상태라면 **E0 (접수 + API 키 + D2 커버리지 확정)**이 전부에 우선
3. D2(집중률 API) 커버 POI 수가 500 미만이면 RISKS R1 발동: ML 근사 비중 확대, DECISION_LOG 기록

## 6. 운영 규칙 (요약)

- 문서 지도·불변 원칙: docs/PROJECT.md / 작업자 행동: docs/AI_GUIDELINES.md / 프롬프트: docs/PROMPTS.md
- 설계 변경 → DECISION_LOG 추가 (기존 항목 수정 금지) / 새 위험 → RISKS / 완료 → TASKS 갱신
- main 상시 배포 가능, Conventional Commits, 키 커밋 금지
- 주간 리듬: 금요일 통합 배포 + ROADMAP DoD 체크. 밀리면 컷 순서: US4 → US5 (US1~3 사수)

## 7. 마감 캘린더

| 날짜 | 이벤트 |
|---|---|
| **7/17(금)** | 접수 완료 목표 (마감 4일 전) |
| 7/21(화) 16:00 | 접수 마감 (엄수) |
| 7월 말 | 예비심사·온라인 OT |
| 9/22 | 기능 동결 |
| 10월 중 | 1차 기능심사 → 최종 PT |
| 11월 | 시상식 |

## 8. 리스크 Top 3 (전체는 docs/RISKS.md)

1. **R1 D2 커버리지 미확인** → 개발 첫날 실호출 확정 (헤지: 자체 ML 확장)
2. **R3 심사 중 다운** → 10월 min-instance=1 + keep-alive + Sentry
3. **R11 접수 실수** → 7/17 완료, 마감 직전 시스템 과부하는 지원자 책임(공고 명시)

## 9. 문서 인덱스

PRD · ARCHITECTURE · ML_GUIDELINES · DATA_GUIDELINES · UI_GUIDELINES · ROADMAP · TASKS · CONTRIBUTING · CODING_GUIDELINES · AI_GUIDELINES · PROMPTS · EVALUATION_GUIDELINES · DEPLOY_GUIDELINES · DECISION_LOG · RISKS · VISION · PROJECT · JUDGING_STRATEGY · DEMO_SCRIPT · PRESENTATION_GUIDELINES · RED_TEAM_REVIEW (모두 docs/)
