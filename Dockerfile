# Backend Dockerfile - Multi-stage Build
# Base image digest-pinned (python:3.12-slim) for reproducible builds — 2026-06-17.
# Refresh: docker buildx imagetools inspect python:3.12-slim --format '{{.Manifest.Digest}}'
# ============================================================
# Builder Stage
FROM python:3.12-slim@sha256:d764629ce0ddd8c71fd371e9901efb324a95789d2315a47db7e4d27e78f1b0e9 AS builder

ARG INSTALL_DEV=false

WORKDIR /app

# Install system dependencies needed for building requirements
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt ./
COPY app/requirements.txt ./app/requirements.txt
# Fixed B-04: Ensure requirements-dev exists or handle gracefully
COPY requirements-dev.txt* ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt && \
    if [ "$INSTALL_DEV" = "true" ] && [ -f requirements-dev.txt ]; then \
    pip install --no-cache-dir --prefix=/install -r requirements-dev.txt; \
    fi

# ============================================================
# Final Stage
FROM python:3.12-slim@sha256:d764629ce0ddd8c71fd371e9901efb324a95789d2315a47db7e4d27e78f1b0e9

ARG INSTALL_DEV=false

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    libgomp1 \
    postgresql-client \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
# [B-05] Standardize structure
COPY . .
RUN chmod +x /app/entrypoint.sh

# Non-root user — reduce blast radius if container is compromised
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup --no-create-home appuser && \
    chown -R appuser:appgroup /app

USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# [B-01] Health check — path matches the app route + compose healthcheck (trailing slash)
HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=30s \
    CMD curl -f http://localhost:8000/api/v1/health/ || exit 1

# Run the application via entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
