# syntax=docker/dockerfile:1
# Multi-stage build tuned for reliable pulls and small pushes
# - Builder uses Microsoft registry image to avoid Docker Hub CDN hiccups
# - Runtime uses python:3.11-slim so Docker Hub already has base layers (smaller push)

ARG BUILDER_IMAGE=mcr.microsoft.com/devcontainers/python:3.11
ARG RUNTIME_IMAGE=python:3.11-slim

# Builder stage: install build tools and Python deps into /install
FROM ${BUILDER_IMAGE} AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
# Install into a separate prefix we can copy into the runtime image
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# Runtime stage: copy only installed deps and app code
FROM ${RUNTIME_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
# Runtime libs for psycopg/asyncpg (no compilers)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*
# Ensure Python deps are available in runtime (alembic/uvicorn/etc.)
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
# Copy application code (after deps for better layer caching)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
