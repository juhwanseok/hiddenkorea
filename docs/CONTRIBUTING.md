# CONTRIBUTING — 레포 구조·규약

> STEP 10 산출물. 솔로+AI 협업 전제의 경량 규약.

## 레포 구조 (모노레포)

```
hiddenkorea/
├── docs/                  # 본 하네스 문서 전체 (진실의 원천)
├── apps/
│   ├── web/               # Next.js 14 (TypeScript)
│   │   └── src/{app,components,lib}/
│   └── api/               # FastAPI
│       └── app/{routers,services,models,core}/
│           ├── services/{congestion,matching,course}/   # 3 AI 계층 = 3 서비스 모듈
├── pipelines/             # 배치 (Python) — ingest_*.py, retrain_model.py
├── ml/                    # 학습 코드·노트북: eda/, train/, eval/
├── data/                  # region_map.csv, goldset.jsonl (소용량 정적만; 원천 데이터는 커밋 금지)
├── .github/workflows/     # ci.yml, cron_*.yml
└── README.md
```

## 브랜치·커밋

- `main` = 항상 배포 가능. 기능은 `feat/<이슈번호>-<slug>` 브랜치 → squash merge. 솔로여도 PR 셀프 리뷰 (AI 코드리뷰 활용).
- Conventional Commits: `feat:` `fix:` `data:` `ml:` `docs:` `chore:`. 예) `ml: LightGBM v0 시간분할 MAE 8.2`
- 금지: main 직접 푸시(hotfix 제외), API 키 커밋 (.env + Secrets만)

## Issue/PR 템플릿 (.github/ISSUE_TEMPLATE/task.md)

```markdown
## 목적 (US/로드맵 링크)
## 입력 / 출력
## 완료 조건 (DoD)
## 검증 방법
```

PR 템플릿: 변경 요약 / 스크린샷(UI 시) / DoD 체크 / 배포 영향.

## README.md 필수 섹션 (심사위원도 볼 수 있음을 전제)
서비스 한 줄 소개 + 배포 URL / 아키텍처 다이어그램 / **한국관광공사 TourAPI 활용 명세**(어떤 API를 어느 기능에 — 데이터활용 20점 증빙) / 로컬 실행법 / 라이선스·출처 표기

## 품질 게이트 (CI)
- web: eslint + tsc + build 통과
- api: ruff + pytest (서비스 모듈 단위테스트, LLM은 mock)
- 커버리지 강박 금지 — 심사 배점은 "돌아가는 것"에 있음. 핵심 로직(스코어링·정규화·코드매핑)만 테스트 필수.
