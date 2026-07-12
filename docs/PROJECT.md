# PROJECT.md — 숨은한국 (HiddenKorea) 진입점

> **AI 작업자는 반드시 이 파일부터 읽는다.** 이후 필요한 문서로 이동.

## 한 줄 정의
방문 예정일의 관광지 혼잡도를 AI로 예측하고, "비슷하지만 한적한" 대안지와 코스를 추천해 오버투어리즘을 분산하는 웹 서비스.

## 컨텍스트
- **목적**: 2026 관광데이터 활용 공모전 ②-2 웹·앱 구현 부문 수상 (지정과제 2 택함)
- **개발자**: 정보통신공학과 학부생 1인 (AI/ML 강점, 프론트 약점, Python 주력) + AI 코딩 어시스턴트
- **데드라인**: 접수 7/21 16:00 → 개발 ~9월 → 1차 기능심사 10월 → PT 최종심사 10월
- **절대 제약**: ① 한국관광공사 OpenAPI 필수 활용 ② 지정과제 2에 부합 ③ 심사위원이 직접 조작해도 안 죽는 완성 서비스

## 문서 지도 (읽는 순서)
| 알고 싶은 것 | 문서 |
|---|---|
| 무엇을 만드나 | PRD.md → VISION.md |
| 어떻게 만드나 | ARCHITECTURE.md → ML_GUIDELINES.md → DATA_GUIDELINES.md → UI_GUIDELINES.md |
| 언제 무엇을 | ROADMAP.md → TASKS.md |
| 왜 이렇게 결정했나 | DECISION_LOG.md |
| 뭐가 위험한가 | RISKS.md |
| 작업 규칙 | CONTRIBUTING.md → CODING_GUIDELINES.md → AI_GUIDELINES.md |
| AI 프롬프트 | PROMPTS.md |
| 품질 측정 | EVALUATION_GUIDELINES.md |
| 배포 | DEPLOY_GUIDELINES.md |
| 심사 대비 | JUDGING_STRATEGY.md → DEMO_SCRIPT.md → PRESENTATION_GUIDELINES.md |
| 전체 통합 | MASTER_BIBLE.md |

## 현재 상태 (작업자가 갱신할 것)
- [x] 주제 확정·데이터 실증 (2026-07-08)
- [x] W0 검증: API 키 5종 활성화 ✅ / D2 커버리지 확정 ✅ (전국 7,445곳·30일, R1 해소)
- [ ] W0 잔여: **공모전 접수 제출** (7/17 목표) ← **지금 여기** (사용자 액션)
- [x] W1: POI 50,674 적재 + EDA (매칭 85.2%)
- [x] W2: 혼잡도 엔진 — 집중률 223,350행 적재, /api/congestion 하이브리드(예측+폴백) 동작, pytest 4통과
- [x] W3: 매칭엔진 — lclsSystm 분류필터 + HiddenScore, /api/alternatives, 분류정합 100%·평균혼잡 31.8
- [x] W6(선행): 코스엔진 — 2-opt 동선최적화 + LLM 서사, /api/course. **백엔드 3대 API 완성**
- [x] W4~6: Next.js 프론트 — 검색→예보→대안→코스 **full flow 브라우저 E2E 검증 완료** (로컬 SQLite+FastAPI 연동)
- [x] UX 강화: 요일 헤더 달력, POI 상세 설명(detailCommon2 '이곳에서는'), 로고 클릭 리셋 + 트랜지션/폴백. 프로덕션 빌드 통과
- [ ] 남음: 인프라 배포(Supabase/Vercel — 클라우드 계정), 카카오맵 실제 키, 공유링크, W7~9 품질·베타·심사자료
- [ ] W4~W6: 프론트·LLM·코스
- [ ] W7~W9: 품질·베타·심사자료

## 불변 원칙 (모든 AI 작업자 공통)
1. 심사 배점(구현성30/기획30/데이터20/발전성20)에 기여하지 않는 작업은 하지 않는다.
2. 기능 추가보다 기존 기능 안정화가 항상 우선.
3. 모든 설계 변경은 DECISION_LOG.md에 한 줄이라도 기록.
4. TourAPI가 서비스 핵심 경로에 있어야 한다 (장식 취급 금지 — 실격 사유).
