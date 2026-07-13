# 배포 가이드 — Vercel(프론트) + Railway(백엔드)

> 목표: 어디서든 접속되는 고정 URL. 프론트=Vercel, 백엔드(FastAPI+데이터)=Railway.

## 0. 준비물
- GitHub 계정, Railway 계정(github 로그인 가능), Vercel 계정(github 로그인 가능)
- 이미 준비됨: `Dockerfile`(백엔드), 데이터 파일 git 추적, CORS·PORT 환경변수화

## 1. GitHub에 올리기
```bash
# (이미 로컬 git 있음) GitHub에서 빈 repo 생성 후:
git remote add origin https://github.com/<계정>/hiddenkorea.git
git branch -M main
git push -u origin main
```
> 데이터 파일 포함 ~110MB 업로드(파일당 100MB 미만이라 OK). 몇 분 걸릴 수 있음.

## 2. Railway — 백엔드 배포
1. railway.app → New Project → **Deploy from GitHub repo** → hiddenkorea 선택
2. Railway가 루트 `Dockerfile` 자동 감지 → 빌드
3. **Variables**(환경변수) 추가:
   - `TOURAPI_KEY` = (관광지 설명용)
   - `KMA_KEY` = (날씨용)
   - `SEOUL_KEY` = (서울 실시간 혼잡용, 선택)
   - `ANTHROPIC_API_KEY` = (LLM 문장, 선택)
   - `ALLOWED_ORIGINS` = (2단계 Vercel 주소 정해지면 입력, 예: `https://hiddenkorea.vercel.app`)
   > 핵심 기능(검색·예보·대안·일정)은 키 없이도 동작. 위 키는 부가 기능용.
4. Settings → Networking → **Generate Domain** → 백엔드 공개 URL 확보(예: `https://hiddenkorea-api.up.railway.app`)
5. 확인: `<백엔드URL>/api/health` → `{"status":"ok",...}`

## 3. Vercel — 프론트 배포
1. vercel.com → Add New Project → hiddenkorea import
2. **Root Directory** = `apps/web` (중요)
3. **Environment Variables**:
   - `NEXT_PUBLIC_API_BASE` = 2단계 Railway 백엔드 URL
   - `NEXT_PUBLIC_KAKAO_MAP_KEY` = `d7d10e806dfe592c05ecc74d83001aec`
4. Deploy → 프론트 URL 확보(예: `https://hiddenkorea.vercel.app`)

## 4. 마무리 연결
1. **Railway ALLOWED_ORIGINS** 에 Vercel URL 입력 → 백엔드 재배포(자동)
2. **카카오 개발자콘솔** → JS 키 → JS SDK 도메인에 Vercel URL 추가(지도용)
3. 완료: Vercel URL을 어디서든 접속 → 배포 완료 🎉

## 참고
- Railway 무료 크레딧 소진 시 유료 전환 필요할 수 있음(심사 기간만 유지 권장)
- 백엔드 첫 요청 시 임베딩/모델 로드로 수 초 걸릴 수 있음(이후 캐시)
- 데이터 갱신 시: 로컬에서 파이프라인 재실행 → 데이터 파일 커밋 → push → 자동 재배포
