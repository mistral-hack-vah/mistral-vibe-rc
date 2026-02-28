# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

# ---- System dependencies ---------------------------------------------------
# No ffmpeg needed — STT is API-based (Voxtral), not local inference.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- Python dependencies ---------------------------------------------------
# Install uv for fast, reproducible installs
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

# Install into the system Python (not a venv) for simplicity in containers
RUN uv pip install --system --no-cache .

# ---- Application source ----------------------------------------------------
COPY python/ python/

# ---- Runtime ----------------------------------------------------------------
EXPOSE 8000

# MISTRAL_API_KEY must be injected at run time via:
#   docker run -e MISTRAL_API_KEY=sk-... ...
# or via a secrets manager / k8s secret.
ENV PYTHONUNBUFFERED=1 \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

CMD ["uvicorn", "python.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1"]
