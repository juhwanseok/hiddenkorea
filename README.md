# 숨은한국 (HiddenKorea)

> 붐비는 곳 말고, 숨은 한국 — AI 혼잡도 예측 기반 오버투어리즘 분산 여행 추천

2026 관광데이터 활용 공모전 ②-2 웹·앱 구현 부문 (지정과제 2) 출품작.

**프로젝트를 이어받는 사람/AI는 [MASTER_BIBLE.md](MASTER_BIBLE.md)부터 읽을 것.**

## 빠른 시작 (W0)

```bash
pip install -r requirements.txt
copy .env.example .env   # 키 입력
python pipelines/smoke_test.py    # API 5종 생존 확인
python pipelines/d2_coverage.py   # R1 게이트: 집중률 API 커버리지 확정
```

## 한국관광공사 OpenAPI 활용 명세 (심사용)

| 공사 API | 서비스 내 역할 |
|---|---|
| 국문 관광정보(TourAPI 4.0) | POI 마스터 26만 건 — 검색·상세·이미지·**대안지 매칭 임베딩의 원천** |
| 관광지 집중률 방문자 추이 예측 | 혼잡도 예보의 1차 소스 (향후 30일) |
| 빅데이터 지역별 방문자수 | 자체 ML 혼잡 근사 모델의 핵심 피처 |
| 관광지별 연관 관광지 | 대안 후보 생성 보강 |

외부 보강: 기상청 단기예보, 서울 실시간 도시데이터(예측 검증용).

## 구조

`docs/` 프로젝트 하네스 문서 · `pipelines/` 데이터 배치 · `ml/` 학습/평가 · `apps/` web(Next.js)+api(FastAPI)

---
데이터 출처: 한국관광공사 TourAPI (공공누리), 기상청, 서울열린데이터광장
