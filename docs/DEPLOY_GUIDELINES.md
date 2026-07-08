# DEPLOY_GUIDELINES — 배포·운영

## 환경
- **web**: Vercel (main 푸시 자동 배포, PR 프리뷰)
- **api**: Cloud Run (Dockerfile, GitHub Actions로 배포). 평시 min-instances=0, **10월 심사 기간 min-instances=1** (콜드스타트 제거, 월 ~1만원)
- **db**: Supabase (일 백업 자동). 배치: GitHub Actions cron (UTC 주의 — KST 새벽 3시 = UTC 18시)

## 환경변수 (Secrets)
`TOURAPI_KEY, KTO_CONGESTION_KEY, KTO_VISITOR_KEY, KMA_KEY, SEOUL_KEY, ANTHROPIC_API_KEY, DATABASE_URL, ALLOWED_ORIGINS`

## 릴리스 절차
1. PR → CI 통과 → squash merge → 자동 배포
2. 배포 후 smoke: `/api/health` + 해피패스 E2E 1회 (Playwright 스크립트)
3. 실패 시 Vercel/Cloud Run 이전 리비전 즉시 롤백 (콘솔 원클릭)

## 심사 기간 운영 수칙 (10월)
- 기능 동결 (9/22~). 배포는 hotfix만
- keep-alive: 외부 cron(GitHub Actions 5분)으로 `/api/health` 핑
- Sentry 알림 → 폰 푸시. 장애 시 프론트는 캐시 데이터로 degrade (배너: "실시간 갱신 지연 중")
- 도메인: 가급적 커스텀 도메인(예: hiddenkorea.kr) — 신청서에 기재할 URL 안정성
