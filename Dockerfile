# 숨은한국 백엔드(FastAPI) — Railway 배포용
# 런타임은 임베딩/모델 추론만 하므로 fastembed·torch 불필요(경량).
FROM python:3.12-slim

WORKDIR /app

# 의존성 먼저(캐시)
COPY apps/api/requirements.txt ./apps/api/requirements.txt
RUN pip install --no-cache-dir -r apps/api/requirements.txt

# 앱 코드
COPY apps/api ./apps/api
# 데이터 산출물(POI DB·임베딩·ML모델·지역매핑) — 서비스 필수
COPY data/hiddenkorea.db data/embeddings.npz data/congestion_gap_model.txt \
     data/congestion_gap_meta.json data/region_map_d2.csv ./data/

ENV PYTHONUNBUFFERED=1
WORKDIR /app/apps/api
# Railway가 주입하는 $PORT 사용
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
