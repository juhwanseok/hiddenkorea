# CODING_GUIDELINES — 숨은한국

## Python (api, pipelines, ml)
- 3.12, ruff (line 100), 타입힌트 필수(공개 함수), Pydantic v2 스키마로 모든 API 입출력 검증
- 외부 API 호출은 반드시 `core/http.py`의 공용 클라이언트 경유: timeout 5s, 재시도 2회(지수 백오프), 캐시 데코레이터
- 예외 삼키기 금지 — 폴백 경로로 명시적 분기 + WARN 로그
- 배치 스크립트는 멱등(idempotent): 재실행해도 중복 적재 없음 (upsert)

## TypeScript (web)
- strict 모드, API 응답 타입은 `lib/api-types.ts` 한 곳 (백엔드 Pydantic과 수동 동기화 — 변경 시 양쪽 커밋)
- 서버 컴포넌트 기본, 클라이언트 컴포넌트는 지도·인터랙션만
- fetch는 `lib/api.ts` 래퍼만 사용 (에러·로딩 상태 일원화)

## 공통
- 매직넘버 금지 → `core/constants.py` / `lib/constants.ts` (혼잡 등급 경계, HiddenScore 가중치 등 — 튜닝 대상은 env 오버라이드 가능)
- TODO는 `TODO(#이슈번호)` 형식만 허용
- 테스트 우선순위: ① region_map 매핑 ② 혼잡 정규화 ③ HiddenScore ④ API 계약 (이 4개는 필수, 나머지는 여유 시)
