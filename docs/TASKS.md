# TASKS — Epic → Feature → Task 분해

> STEP 12 Task Harness. 상태: ⬜ 대기 / 🔄 진행 / ✅ 완료. AI 작업자는 Task 단위로 집어 수행하고 상태 갱신.
> 모든 Task는 [입력 → 출력 / DoD / 실패 조건 / 검증 / 다음]을 갖는다. 대표 Epic만 전개, 나머지는 동일 패턴.

## E0. 공모전 접수 (W0) — 🔴 최우선
- **F0.1 접수**
  - ⬜ T0.1.1 콘텐츠랩 회원가입 → 계정 / DoD: 로그인 성공 / 실패: 이메일 인증 막힘→운영국 문의 / 다음: T0.1.2
  - ⬜ T0.1.2 신청서 초안 (서비스명·과제2·기획요약 500자) → docs/submission/apply.md / 검증: PRD와 문구 일치 / 다음: T0.1.3
  - ⬜ T0.1.3 접수 제출 (**≤7/17**) / DoD: 접수번호 스크린샷
- **F0.2 API 키 5종** (TourAPI·D2·D3·기상·citydata)
  - ⬜ T0.2.1 발급 → .env / DoD: 각 API 200 응답 스크립트 `pipelines/smoke_test.py` 통과
  - ⬜ T0.2.2 **D2 커버리지 확정** → ml/eda/d2_coverage.ipynb / DoD: 커버 POI 수·지역 분포 리포트 / 실패(POI<500): RISKS R1 대응 발동, DECISION_LOG 기록 / 다음: E2 설계 확정

## E1. 데이터 플랫폼 (W1)
- F1.1 인프라: ⬜ Supabase/Vercel/CloudRun 프로비저닝 · ⬜ 스키마 마이그레이션(places, congestion_forecast, features, courses)
- F1.2 수집: ⬜ ingest_pois (DoD: 20만+ rows) · ⬜ region_map.csv (DoD: 3개 코드계 전 시군구 매핑, 단위테스트) · ⬜ ingest_visitors/weather/congestion cron 가동
- F1.3 EDA: ⬜ 노트북 4종 (DATA_GUIDELINES §4) → 발표 소재 스크린샷 폴더에 저장

## E2. 혼잡도 엔진 (W2)
- ⬜ T2.1 집중률 정규화 로직 (분위수) + 단위테스트
- ⬜ T2.2 LightGBM 학습 파이프라인 → ml/train/congestion_v0 / DoD: 시간분할 MAE·순위상관 기록 / 검증: citydata 등급 일치율 ≥80%(인접 허용)
- ⬜ T2.3 `/api/congestion` (source 필드 포함) / DoD: 임의 POI 100개 랜덤 샘플 응답 100%

## E3. 매칭 엔진 (W3)
- ⬜ T3.1 임베딩 배치+pgvector 인덱스 / DoD: 유사도 스팟체크 10건 수동 검수
- ⬜ T3.2 goldset.jsonl 30쌍 구축 (관광 상식 기반, 본인+지인 검수)
- ⬜ T3.3 HiddenScore + 가중치 그리드서치 / DoD: nDCG@3 ≥ 0.7 / 실패: 후보 필터 완화→재튜닝
- ⬜ T3.4 `/api/alternatives` + LLM 이유 문장화(폴백 포함)

## E4. 프론트 (W4~W6)
- F4.1 S1 홈+검색 / F4.2 S2 예보+히트맵 / F4.3 S3 대안 카드 / F4.4 S4 코스+공유+카카오맵
- 각 화면 DoD: 모바일 375px에서 완주 + skeleton 로딩 + 에러 폴백

## E5. 코스 엔진 (W6)
- ⬜ T5.1 거리행렬+2-opt 순서 최적화 (LLM 아님) · ⬜ T5.2 LLM 서사(golden test 20케이스) · ⬜ T5.3 shareId 영속화

## E6. 품질·측정 (W7~W8)
- ⬜ Sentry+구조화 로그 · ⬜ 부하 20동시 · ⬜ keep-alive · ⬜ 베타 10명 (수용률·SUS) · ⬜ citydata 검증 리포트 v2

## E7. 심사 대응 (W9~)
- ⬜ 기능설명서(해시태그 매핑) · ⬜ 3분 시연 영상 · ⬜ README 데이터활용 명세 · ⬜ (통과 시) PT 덱
