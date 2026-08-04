FROM python:3.12-slim@sha256:d764629ce0ddd8c71fd371e9901efb324a95789d2315a47db7e4d27e78f1b0e9

# libgomp1: OpenMP runtime lightgbm's native extension needs (same as the
# main backend's own Dockerfile) -- without it, `import lightgbm` fails at
# runtime with "OSError: libgomp.so.1: cannot open shared object file"
# (caught live via a real `docker run` import check, 2026-08-04).
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY v2/services/prediction_ml_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Own package (domain/application/infrastructure/routers/tests, main.py).
COPY v2/services/prediction_ml_service/ ./prediction_ml_service/
# Vendored: platform_infra + shared_kernel never import business modules
# back (see their own CLAUDE.md), so a second physical copy here carries
# no reverse-coupling risk -- avoids a network hop for logging/cache/DB
# session/UnitOfWork, which this service's own repos need directly anyway.
# app/config.py is vendored too -- platform_infra's own files import
# `from app.config import settings` throughout, and config.py itself has
# zero v2.modules dependencies (pure pydantic_settings).
COPY v2/__init__.py ./v2/__init__.py
COPY v2/modules/__init__.py ./v2/modules/__init__.py
COPY v2/modules/platform_infra/ ./v2/modules/platform_infra/
COPY v2/modules/shared_kernel/ ./v2/modules/shared_kernel/
COPY app/__init__.py ./app/__init__.py
COPY app/config.py ./app/config.py

ENV PYTHONPATH=/app

CMD ["uvicorn", "prediction_ml_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
