# Multi-stage build for the SurgiScan FastAPI backend (Supabase-backed).
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y \
    gcc g++ libmagic1 libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
FROM python:3.11-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

# libmagic1 (python-magic file sniffing), curl (healthcheck).
RUN apt-get update && apt-get install -y \
    libmagic1 curl \
    && rm -rf /var/lib/apt/lists/* && apt-get clean

COPY --from=builder /opt/venv /opt/venv

RUN groupadd -r appuser && useradd -r -g appuser appuser
WORKDIR /app

# The app is `server:app` and imports the api/, app/ and ontology/ packages.
# All three must be in the image (the previous Dockerfile copied only app/
# and targeted a non-existent app.main:app).
COPY app/ ./app/
COPY api/ ./api/
COPY ontology/ ./ontology/
COPY *.py ./

RUN mkdir -p /app/storage /app/logs && chown -R appuser:appuser /app
USER appuser

# Health endpoint is /api/health (api_router is mounted under /api).
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT}/api/health" || exit 1

EXPOSE $PORT

# Bind to Render's injected $PORT (shell form so it expands at runtime).
CMD ["sh", "-c", "python -m uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
