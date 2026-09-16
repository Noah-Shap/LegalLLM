# Legal facts extraction service (C10) — FastAPI + uvicorn.
#   docker build -t legallm-api .
#   docker run -p 8000:8000 -e ANTHROPIC_API_KEY=... -e LEGALLM_DEFAULT_METHOD=llm-v3 legallm-api
# Render / Fly / Cloud Run: set the same env vars as secrets; the app reads $PORT.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    LEGALLM_LLM_BACKEND=api LEGALLM_DEFAULT_METHOD=llm-v3 \
    LEGALLM_REQUEST_LOG=/data/requests.jsonl LEGALLM_RATE_LIMIT_PER_MIN=20 LEGALLM_MAX_UPLOAD_MB=20

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --upgrade pip && pip install ".[api]" && mkdir -p /data

EXPOSE 8000
CMD ["sh", "-c", "uvicorn legallm.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
