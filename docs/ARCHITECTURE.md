# ARCHITECTURE — 숨은한국

> 버전 1.0 (2026-07-08). 변경 시 DECISION_LOG.md에 기록할 것.
> 설계 원칙: **솔로 개발 / 2개월 / 무료~저비용 / 심사위원이 만졌을 때 안 죽는 것이 최우선.**

## 1. 전체 구조

```
[사용자 브라우저]
      │ HTTPS
[Next.js 프론트엔드 (Vercel)]          ← UI, 카카오맵 SDK, 히트맵 캘린더
      │ REST (JSON)
[FastAPI 백엔드 (Cloud Run 또는 Railway)]
      ├─ /api/congestion  ← 혼잡도 엔진 (예측 조회+모델 추론)
      ├─ /api/alternatives ← 대안지 매칭 (벡터 검색 + HiddenScore)
      ├─ /api/course      ← LLM 코스 생성
      └─ /api/places      ← POI 검색/상세 (TourAPI 프록시+캐시)
      │
[PostgreSQL + pgvector (Supabase 무료 티어)]
      ├─ places (TourAPI POI 스냅샷 + overview 임베딩)
      ├─ congestion_forecast (공사 집중률 API 일배치 적재)
      ├─ congestion_model_features (시군구 방문자수·기상·달력 피처)
      └─ courses / share_links
      │
[배치 파이프라인 (GitHub Actions cron, Python)]
      ├─ TourAPI POI 수집 (초기 1회 + 주간 동기화)
      ├─ 집중률 예측 API 일일 적재
      ├─ 데이터랩 방문자수·기상 피처 갱신
      └─ ML 모델 재학습 (주간)
```

## 2. 기술 스택과 선택 이유

| 레이어 | 선택 | 이유 (대안 대비) |
|---|---|---|
| Frontend | **Next.js 14 + TypeScript + Tailwind + shadcn/ui** | 사용자가 프론트 약점 → AI 코딩 지원이 가장 잘 되는 스택. Vercel 무료 배포. (Streamlit은 "완성 서비스" 인상 미달로 기각 — DECISION_LOG #3) |
| 지도 | **카카오맵 JS SDK** | 무료 쿼터 충분, 국내 POI 표시 품질, 카카오내비 딥링크. 공모전 공동주최가 카카오인 점도 감점 없음 |
| Backend | **FastAPI (Python 3.12)** | 사용자 주력 언어. ML 추론·임베딩·LLM 호출 동일 런타임 |
| DB | **Supabase Postgres + pgvector** | 무료, 벡터검색·일반쿼리 단일 DB (FAISS 별도 운영 복잡성 회피) |
| ML | **LightGBM** (혼잡 근사 모델) | 표 형식 피처에 최적, 학습 수분, 해석 가능(피처 중요도 → 발표자료) |
| 임베딩 | **multilingual-e5-small** (로컬) 또는 OpenAI text-embedding-3-small | POI 26만 건 배치 임베딩 비용: 로컬 무료 / OpenAI ~수 달러. 1회 배치라 둘 다 가능 |
| LLM | **Claude Haiku 4.5** (코스 생성·추천 근거 문장화) | 저비용·한국어 품질. 캐시로 호출 최소화. 프롬프트는 PROMPTS.md |
| 캐시 | Postgres 테이블 캐시 + FastAPI in-memory TTL | Redis 추가 운영 부담 회피. 트래픽 규모상 충분 |
| CI/CD | GitHub Actions (lint+test → Vercel/Cloud Run 자동 배포) | |
| 모니터링 | Sentry 무료 티어 + 구조화 로그(JSON) | 심사 기간 크래시 즉시 감지 |

## 3. 핵심 컴포넌트 설계

### 3.1 하이브리드 혼잡도 엔진 (차별화 핵심 ①)
```
입력: (POI id, 날짜)
1) 공사 "관광지 집중률 방문자 추이 예측" API 커버 POI인가?
   YES → 집중률 예측치 사용 (source: "KTO_FORECAST")
   NO  → 자체 LightGBM 근사 모델 (source: "HK_MODEL")
         피처: 해당 시군구 일별 방문자수 시계열(데이터랩 API), 요일/공휴일/방학,
               기상청 단기예보, POI 카테고리, 계절성(월), 인근 행사 여부(TourAPI 행사)
2) 0~100 지수로 정규화 + 5등급 (여유/보통/붐빔/혼잡/매우혼잡)
3) 서울 121개 명소는 citydata 실시간값으로 예측 검증(정확도 리포트 → 발표자료)
```
- **커버리지 리스크 헤지**: 개발 D1에 집중률 API 실호출로 커버 POI 수 확정 (RISKS.md R1)

### 3.2 대안지 매칭 엔진 (차별화 핵심 ②)
```
후보 생성: 같은 카테고리(cat1~3) + 반경 N km (또는 동일 광역권) POI
스코어링: HiddenScore = α·cos_sim(overview 임베딩) + β·(1 − 혼잡지수)
                        + γ·접근성(거리 감쇠) + δ·품질 프록시(이미지 유무, 정보 완결도)
초기 가중치 α=0.4, β=0.3, γ=0.2, δ=0.1 — EVALUATION_GUIDELINES.md 절차로 튜닝
보너스 소스: 공사 "관광지별 연관 관광지"(Tmap) API를 후보 생성에 병합
출력: 상위 3곳 + 근거(유사도%, 예상 혼잡, 거리) — 설명가능성이 심사 어필 포인트
```

### 3.3 LLM 코스 생성
- 입력: 확정 POI 목록 + 혼잡·운영시간·좌표. LLM은 **순서·시간배분·서사**만 담당 (사실 정보는 전부 DB에서 주입 → 환각 차단).
- 거리 행렬 기반 순서는 코드(nearest-neighbor + 2-opt)로 계산, LLM은 결과를 문장화. 실패 시 템플릿 문장으로 폴백 (LLM 죽어도 서비스 동작 — graceful degradation).

## 4. API 계약 (요약)

```
GET /api/congestion?contentId=&date=          → {index, grade, source, series30d[]}
GET /api/alternatives?contentId=&date=&k=3    → [{poi, hiddenScore, simPct, congestion, distanceKm, reason}]
POST /api/course {date, poiIds[], startTime}  → {legs[], narrative, kakaoMapLink}
GET /api/places/search?q=&areaCode=           → TourAPI 프록시(캐시 TTL 24h)
```

## 5. 보안·비용·확장성

- **보안**: 모든 외부 API 키는 백엔드 env로만 (프론트 노출 금지). CORS 화이트리스트. 입력 검증(Pydantic). LLM 프롬프트 인젝션: 사용자 자유 텍스트를 시스템 프롬프트와 격리.
- **비용 상한**: Vercel 0원 / Supabase 0원 / Cloud Run ~0원(콜드스타트 허용) / LLM+임베딩 월 1~2만원 이하 목표. 총 **월 2만원 이하**.
- **API 쿼터**: TourAPI 개발계정 일 1,000건 → **전 요청 DB 캐시 필수**. POI 초기 수집은 운영계정 신청 또는 수일 분할 배치.
- **확장성 스토리(발표용)**: 배치 파이프라인이 데이터소스 추가에 열려있음(외국인 관광객 데이터, 지자체 대시보드).

## 6. 로그 구조

```json
{"ts":"...","level":"INFO","route":"/api/alternatives","contentId":"126508",
 "date":"2026-10-03","latencyMs":142,"cacheHit":true,"congestionSource":"KTO_FORECAST"}
```
- 추천 노출/클릭 이벤트 로그 → 추천 수용률 산출 (발표 지표).
